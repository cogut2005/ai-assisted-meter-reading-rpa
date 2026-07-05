from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ALLOWED_SOURCES = {"portal", "mobile_app", "app_photo"}
ANOMALY_THRESHOLD = 5000


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert a human-approved meter reading after review."
    )
    parser.add_argument("--db-path", required=True, help="Path to the SQLite database.")
    parser.add_argument(
        "--validation-json",
        required=True,
        help="Path to the validation JSON that was routed to human review.",
    )
    parser.add_argument("--approved-reading-value", required=True)
    parser.add_argument(
        "--reading-date",
        default="",
        help="Optional override. Defaults to metadata.reading_date from validation JSON.",
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument("--validation-status", default="human_approved")
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to the JSON file that will receive the insert result.",
    )
    return parser.parse_args()


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def resolve_output_path(raw_path: str) -> Path:
    path = resolve_path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def parse_reading_value(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as error:
        raise ValueError("approved-reading-value must be an integer") from error
    if value < 0:
        raise ValueError("approved-reading-value must be greater than or equal to 0")
    return value


def parse_reading_date(raw_value: str) -> str:
    if not raw_value:
        raise ValueError("reading_date is missing")
    try:
        datetime.strptime(raw_value, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("reading_date must be a valid YYYY-MM-DD date") from error
    return raw_value


def latest_previous_reading(
    conn: sqlite3.Connection, meter_id: int, reading_date: str
) -> int | None:
    row = conn.execute(
        """
        SELECT reading_value
        FROM meter_reading_history
        WHERE meter_id = ? AND reading_date < ?
        ORDER BY reading_date DESC, reading_id DESC
        LIMIT 1
        """,
        (meter_id, reading_date),
    ).fetchone()
    if row is None:
        return None
    return int(row[0])


def existing_month_reading(
    conn: sqlite3.Connection, meter_id: int, reading_date: str
) -> dict[str, Any] | None:
    row = conn.execute(
        """
        SELECT reading_id, reading_date, reading_value
        FROM meter_reading_history
        WHERE meter_id = ? AND substr(reading_date, 1, 7) = substr(?, 1, 7)
        LIMIT 1
        """,
        (meter_id, reading_date),
    ).fetchone()
    if row is None:
        return None
    return {
        "reading_id": int(row[0]),
        "reading_date": str(row[1]),
        "reading_value": int(row[2]),
    }


def validation_failed(
    reason: str,
    meter_id: int,
    reading_date: str,
    approved_reading_value: int,
    previous_reading: int | None = None,
    consumption_since_last: int | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "status": "review_validation_failed",
        "inserted": False,
        "reason": reason,
        "meter_id": meter_id,
        "reading_date": reading_date,
        "reading_value": approved_reading_value,
        "previous_reading": previous_reading,
        "consumption_since_last": consumption_since_last,
    }
    if extra:
        payload.update(extra)
    return payload


def write_payload(payload: dict[str, Any], output_path: Path) -> None:
    result_json = json.dumps(payload, ensure_ascii=True, indent=2)
    output_path.write_text(result_json, encoding="utf-8")
    print(result_json)


def insert_reviewed_reading(args: argparse.Namespace) -> dict[str, Any]:
    validation_path = resolve_path(args.validation_json)
    payload = load_json(validation_path)

    decision = str(payload.get("decision", ""))
    if decision != "human_review":
        raise ValueError(
            "validation payload is not a human review item; expected decision=human_review"
        )

    meter_id_raw = payload.get("meter_id")
    if meter_id_raw in ("", None):
        raise ValueError("meter_id is missing in validation payload")
    meter_id = int(meter_id_raw)

    metadata = payload.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}

    reading_date = parse_reading_date(
        args.reading_date or str(metadata.get("reading_date", ""))
    )
    approved_reading_value = parse_reading_value(args.approved_reading_value)
    if args.source not in ALLOWED_SOURCES:
        return validation_failed(
            reason="source must be one of: " + ", ".join(sorted(ALLOWED_SOURCES)),
            meter_id=meter_id,
            reading_date=reading_date,
            approved_reading_value=approved_reading_value,
        )

    conn = sqlite3.connect(resolve_path(args.db_path))
    try:
        duplicate = existing_month_reading(conn, meter_id, reading_date)
        if duplicate is not None:
            return validation_failed(
                reason="Duplicate monthly reading detected for this meter",
                meter_id=meter_id,
                reading_date=reading_date,
                approved_reading_value=approved_reading_value,
                extra={"duplicate": duplicate},
            )

        previous_reading = latest_previous_reading(conn, meter_id, reading_date)
        consumption_since_last = (
            None
            if previous_reading is None
            else approved_reading_value - previous_reading
        )
        if previous_reading is not None and approved_reading_value < previous_reading:
            return validation_failed(
                reason="Approved reading is lower than previous reading",
                meter_id=meter_id,
                reading_date=reading_date,
                approved_reading_value=approved_reading_value,
                previous_reading=previous_reading,
                consumption_since_last=consumption_since_last,
            )
        if (
            consumption_since_last is not None
            and consumption_since_last > ANOMALY_THRESHOLD
        ):
            return validation_failed(
                reason="Approved reading creates unusually high consumption",
                meter_id=meter_id,
                reading_date=reading_date,
                approved_reading_value=approved_reading_value,
                previous_reading=previous_reading,
                consumption_since_last=consumption_since_last,
                extra={"anomaly_threshold": ANOMALY_THRESHOLD},
            )

        cursor = conn.execute(
            """
            INSERT INTO meter_reading_history (
                meter_id,
                reading_date,
                reading_value,
                consumption_since_last,
                source,
                validation_status,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                meter_id,
                reading_date,
                approved_reading_value,
                consumption_since_last,
                args.source,
                args.validation_status,
                args.notes,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "status": "inserted",
        "inserted": True,
        "reading_id": cursor.lastrowid,
        "meter_id": meter_id,
        "reading_date": reading_date,
        "reading_value": approved_reading_value,
        "previous_reading": previous_reading,
        "consumption_since_last": consumption_since_last,
        "source": args.source,
        "validation_status": args.validation_status,
    }


def main() -> int:
    args = parse_args()
    output_path = resolve_output_path(args.output_json)

    try:
        payload = insert_reviewed_reading(args)
        write_payload(payload, output_path)
        return 0
    except Exception as error:  # pragma: no cover - CLI safety path
        payload = {"status": "error", "inserted": False, "message": str(error)}
        write_payload(payload, output_path)
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
