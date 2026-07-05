from __future__ import annotations

import csv
from pathlib import Path

from .contracts import InputSubmission


REQUIRED_COLUMNS = {
    "customer_id",
    "meter_number",
    "reading_date",
    "reading_value",
    "source",
    "image_file",
    "notes",
}


def load_submissions(input_path: Path, run_prefix: str) -> list[InputSubmission]:
    """Read CSV input and convert each row into an InputSubmission contract."""
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Input CSV is missing a header row")

        raw_columns = [column.strip() for column in reader.fieldnames]
        use_image_alias = "image" in raw_columns and "image_file" not in raw_columns
        columns = [
            "image_file" if use_image_alias and column == "image" else column
            for column in raw_columns
        ]

    missing_columns = sorted(REQUIRED_COLUMNS - set(columns))
    if missing_columns:
        raise ValueError(
            "Input CSV is missing required columns: " + ", ".join(missing_columns)
        )

    submissions: list[InputSubmission] = []
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return submissions

        raw_fieldnames = [column.strip() for column in reader.fieldnames]
        use_image_alias = "image" in raw_fieldnames and "image_file" not in raw_fieldnames
        reader.fieldnames = [
            "image_file" if use_image_alias and column == "image" else column
            for column in raw_fieldnames
        ]
        for index, row in enumerate(reader, start=1):
            normalized = {
                str(key).strip(): "" if value is None else str(value).strip()
                for key, value in row.items()
            }
            submissions.append(
                InputSubmission(
                    submission_id=f"SUB-{run_prefix}-{index:04d}",
                    customer_id=normalized["customer_id"],
                    meter_number=normalized["meter_number"],
                    reading_date=normalized["reading_date"],
                    reading_value=normalized["reading_value"],
                    source=normalized["source"],
                    image_file=normalized["image_file"],
                    notes=normalized.get("notes", ""),
                )
            )
    return submissions
