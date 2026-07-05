from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from uipath_bridge import insert_valid_reading_for_uipath


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Insert a processed validation result for UiPath."
    )
    parser.add_argument("--db-path", required=True, help="Path to the SQLite database.")
    parser.add_argument(
        "--validation-json",
        required=True,
        help="Path to the validation JSON file produced by validate_submission_cli.py.",
    )
    parser.add_argument("--source", required=True)
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to the JSON file that will receive the insert result.",
    )
    return parser.parse_args()


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    return path


def resolve_output_path(raw_path: str) -> Path:
    path = resolve_path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_validation_payload(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def require_string(value: object, field_name: str) -> str:
    if value in (None, ""):
        raise ValueError(f"{field_name} is missing in validation payload")
    return str(value)


def main() -> int:
    args = parse_args()
    validation_path = resolve_path(args.validation_json)
    output_path = resolve_output_path(args.output_json)

    try:
        payload = load_validation_payload(validation_path)

        decision = str(payload.get("decision", ""))
        database_update_allowed = bool(payload.get("database_update_allowed", False))
        if decision != "processed" or not database_update_allowed:
            raise ValueError(
                "validation payload is not insertable; expected processed decision with database_update_allowed=true"
            )

        meter_id = require_string(payload.get("meter_id"), "meter_id")
        reading_value = require_string(payload.get("new_reading"), "new_reading")
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("metadata must be an object in validation payload")
        reading_date = require_string(metadata.get("reading_date"), "metadata.reading_date")
        consumption_since_last = payload.get("consumption_since_last", "")

        result_json = insert_valid_reading_for_uipath(
            db_path=args.db_path,
            meter_id=int(meter_id),
            reading_date=reading_date,
            reading_value=int(reading_value),
            consumption_since_last=consumption_since_last,
            source=args.source,
            validation_status="processed",
            notes=args.notes,
        )
        output_path.write_text(result_json, encoding="utf-8")
        print(result_json)
        return 0
    except Exception as error:  # pragma: no cover - CLI safety path
        payload = {"status": "error", "message": str(error)}
        output_path.write_text(json.dumps(payload, ensure_ascii=True), encoding="utf-8")
        print(payload["message"], file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
