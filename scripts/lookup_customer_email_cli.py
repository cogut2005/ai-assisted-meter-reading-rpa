from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Look up a customer email address for UiPath."
    )
    parser.add_argument("--db-path", required=True, help="Path to the SQLite database.")
    parser.add_argument("--customer-id", required=True)
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to the JSON file that will receive the lookup result.",
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


def lookup_email(db_path: Path, customer_id: str) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            """
            SELECT email
            FROM customer_contacts
            WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()
    finally:
        conn.close()

    if row is None:
        return {
            "status": "not_found",
            "customer_id": customer_id,
            "email": "",
        }

    return {
        "status": "found",
        "customer_id": customer_id,
        "email": str(row[0]),
    }


def write_payload(payload: dict[str, Any], output_path: Path) -> None:
    result_json = json.dumps(payload, ensure_ascii=True, indent=2)
    output_path.write_text(result_json, encoding="utf-8")
    print(result_json)


def main() -> int:
    args = parse_args()
    output_path = resolve_output_path(args.output_json)

    try:
        payload = lookup_email(resolve_path(args.db_path), args.customer_id)
        write_payload(payload, output_path)
        return 0
    except Exception as error:  # pragma: no cover - CLI safety path
        payload = {
            "status": "error",
            "customer_id": args.customer_id,
            "email": "",
            "message": str(error),
        }
        write_payload(payload, output_path)
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
