from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from uipath_bridge import validate_submission_for_uipath


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate a single meter reading submission for UiPath."
    )
    parser.add_argument("--db-path", required=True, help="Path to the SQLite database.")
    parser.add_argument("--submission-id", required=True)
    parser.add_argument("--customer-id", required=True)
    parser.add_argument("--meter-number", required=True)
    parser.add_argument("--reading-date", required=True)
    parser.add_argument("--reading-value", default="")
    parser.add_argument("--source", required=True)
    parser.add_argument("--image-file", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument(
        "--output-json",
        required=True,
        help="Path to the JSON file that will receive the validation result.",
    )
    return parser.parse_args()


def resolve_output_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (Path.cwd() / path).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def main() -> int:
    args = parse_args()
    output_path = resolve_output_path(args.output_json)

    try:
        result_json = validate_submission_for_uipath(
            db_path=args.db_path,
            submission_id=args.submission_id,
            customer_id=args.customer_id,
            meter_number=args.meter_number,
            reading_date=args.reading_date,
            reading_value=args.reading_value,
            source=args.source,
            image_file=args.image_file,
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
