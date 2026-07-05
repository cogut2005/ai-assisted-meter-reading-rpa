from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT_CANDIDATES = (
    PROJECT_ROOT / "data" / "input" / "portal_export.csv",
    PROJECT_ROOT / "data" / "input" / "portal_export1.csv",
)
DEFAULT_DB_CANDIDATES = (
    PROJECT_ROOT / "data" / "database" / "master.db",
    PROJECT_ROOT / "data" / "history" / "master.db",
)
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output"


ALLOWED_SOURCES = {"portal", "mobile_app", "app_photo"}
ANOMALY_THRESHOLD = 5000
IMAGE_REVIEW_REASON = "Image-based submission requires AI image reading and human review"
INACTIVE_METER_REASON = "User's meter is inactive and needs to be activated first"

PROCESSED_COLUMNS = [
    "submission_id",
    "customer_id",
    "customer_name",
    "meter_id",
    "meter_number",
    "meter_type",
    "reading_date",
    "previous_reading",
    "new_reading",
    "consumption_since_last",
    "source",
    "validation_status",
    "database_update",
    "notes",
]
EXCEPTION_COLUMNS = [
    "submission_id",
    "customer_id",
    "meter_number",
    "reading_date",
    "reading_value",
    "source",
    "reason",
    "notes",
]
REVIEW_COLUMNS = [
    "submission_id",
    "customer_id",
    "meter_number",
    "reading_date",
    "reading_value",
    "source",
    "reason",
    "notes",
]
NEW_CUSTOMER_COLUMNS = [
    "submission_id",
    "customer_id",
    "meter_number",
    "reading_date",
    "reading_value",
    "source",
    "reason",
    "notes",
]
MAIL_COLUMNS = [
    "submission_id",
    "draft_type",
    "recipient_type",
    "recipient",
    "subject",
    "body",
    "status",
]


@dataclass
class RuntimeConfig:
    input_path: Path
    db_path: Path
    output_dir: Path


@dataclass
class ProcessingContext:
    submission_id: str
    input_row: dict[str, str]
    customer: dict[str, Any] | None = None
    meter: dict[str, Any] | None = None
    reading_date: date | None = None
    reading_value: int | None = None
    previous_reading: int | None = None
    consumption_since_last: int | None = None
    reason: str = ""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Process meter reading submissions from a CSV file."
    )
    parser.add_argument("--input", help="Optional path to the input CSV.")
    parser.add_argument("--db", help="Optional path to the SQLite database.")
    parser.add_argument("--output", help="Optional path to the output directory.")
    return parser.parse_args()


def resolve_optional_path(raw_path: str | None, default_candidates: tuple[Path, ...]) -> Path:
    if raw_path:
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = (PROJECT_ROOT / candidate).resolve()
        return candidate

    for candidate in default_candidates:
        if candidate.exists():
            return candidate
    return default_candidates[0]


def build_runtime_config(args: argparse.Namespace) -> RuntimeConfig:
    input_path = resolve_optional_path(args.input, DEFAULT_INPUT_CANDIDATES)
    db_path = resolve_optional_path(args.db, DEFAULT_DB_CANDIDATES)

    if args.output:
        output_dir = Path(args.output).expanduser()
        if not output_dir.is_absolute():
            output_dir = (PROJECT_ROOT / output_dir).resolve()
    else:
        output_dir = DEFAULT_OUTPUT_DIR

    output_dir.mkdir(parents=True, exist_ok=True)

    return RuntimeConfig(
        input_path=input_path,
        db_path=db_path,
        output_dir=output_dir,
    )


def display_path(path: Path) -> str:
    try:
        return path.relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def load_input_rows(input_path: Path) -> list[dict[str, str]]:
    if not input_path.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_path}")

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

    required_columns = {
        "customer_id",
        "meter_number",
        "reading_date",
        "reading_value",
        "source",
        "image_file",
        "notes",
    }
    missing_columns = sorted(required_columns - set(columns))
    if missing_columns:
        raise ValueError(
            "Input CSV is missing required columns: " + ", ".join(missing_columns)
        )

    normalized_rows: list[dict[str, str]] = []
    with input_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            return normalized_rows

        raw_fieldnames = [column.strip() for column in reader.fieldnames]
        use_image_alias = "image" in raw_fieldnames and "image_file" not in raw_fieldnames
        normalized_fieldnames = [
            "image_file" if use_image_alias and column == "image" else column
            for column in raw_fieldnames
        ]
        reader.fieldnames = normalized_fieldnames
        for row in reader:
            normalized_rows.append(
                {
                    str(key).strip(): "" if value is None else str(value).strip()
                    for key, value in row.items()
                }
            )
    return normalized_rows


def fetch_one(
    conn: sqlite3.Connection, query: str, params: tuple[Any, ...]
) -> dict[str, Any] | None:
    row = conn.execute(query, params).fetchone()
    return dict(row) if row else None


def parse_reading_date(raw_value: str) -> date:
    return datetime.strptime(raw_value, "%Y-%m-%d").date()


def parse_reading_value(raw_value: str) -> int:
    if raw_value == "":
        raise ValueError("reading_value is required when image_file is empty")

    try:
        if "." in raw_value:
            numeric_value = float(raw_value)
            if not numeric_value.is_integer():
                raise ValueError
            parsed_value = int(numeric_value)
        else:
            parsed_value = int(raw_value)
    except ValueError as error:
        raise ValueError("reading_value must be numeric") from error

    if parsed_value < 0:
        raise ValueError("reading_value must be greater than or equal to 0")
    return parsed_value


def latest_previous_reading(
    conn: sqlite3.Connection, meter_id: int, reading_date: date
) -> int | None:
    row = fetch_one(
        conn,
        """
        SELECT reading_value
        FROM meter_reading_history
        WHERE meter_id = ? AND reading_date < ?
        ORDER BY reading_date DESC, reading_id DESC
        LIMIT 1
        """,
        (meter_id, reading_date.isoformat()),
    )
    if row is None:
        return None
    return int(row["reading_value"])


def existing_month_reading(
    conn: sqlite3.Connection, meter_id: int, reading_date: date
) -> dict[str, Any] | None:
    return fetch_one(
        conn,
        """
        SELECT reading_id, reading_date, reading_value
        FROM meter_reading_history
        WHERE meter_id = ? AND substr(reading_date, 1, 7) = ?
        LIMIT 1
        """,
        (meter_id, reading_date.strftime("%Y-%m")),
    )


def base_row(context: ProcessingContext) -> dict[str, str]:
    return {
        "submission_id": context.submission_id,
        "customer_id": context.input_row.get("customer_id", ""),
        "meter_number": context.input_row.get("meter_number", ""),
        "reading_date": context.input_row.get("reading_date", ""),
        "reading_value": context.input_row.get("reading_value", ""),
        "source": context.input_row.get("source", ""),
        "reason": context.reason,
        "notes": context.input_row.get("notes", ""),
    }


def make_mail_draft(draft_type: str, context: ProcessingContext) -> dict[str, str]:
    if draft_type == "customer_confirmation":
        subject = "Meter reading received"
        unit = str(context.meter["unit"]).strip()
        unit_suffix = f" {unit}" if unit else ""
        body = (
            f"Dear customer, your meter reading for meter {context.meter['meter_number']} "
            f"on {context.reading_date.isoformat()} has been received and processed successfully. "
            f"The recorded reading is {context.reading_value}{unit_suffix}. "
            "Best regards, Customer Service Team"
        )
        recipient_type = "customer"
        recipient = f"customer_{context.customer['customer_id']}@example.com"
    elif draft_type == "customer_correction":
        subject = "Meter reading correction required"
        body = (
            "Dear customer, your submitted meter reading could not be processed because "
            f"{context.reason.lower()}. Please submit the reading again or upload a clear meter image. "
            "Best regards, Customer Service Team"
        )
        recipient_type = "customer"
        recipient = f"customer_{context.input_row.get('customer_id', 'unknown')}@example.com"
    else:
        subject = "Meter reading requires manual review"
        body = (
            f"Submission {context.submission_id} requires manual review. Reason: {context.reason}. "
            f"Meter: {context.input_row.get('meter_number', '')}. "
            f"Reading date: {context.input_row.get('reading_date', '')}. "
            "Please verify the case before database update."
        )
        recipient_type = "review_team"
        recipient = "meter-review@example.com"

    return {
        "submission_id": context.submission_id,
        "draft_type": draft_type,
        "recipient_type": recipient_type,
        "recipient": recipient,
        "subject": subject,
        "body": body,
        "status": "draft_created",
    }


def route_exception(
    exceptions_rows: list[dict[str, Any]],
    mail_rows: list[dict[str, Any]],
    context: ProcessingContext,
    draft_type: str,
) -> None:
    exceptions_rows.append(base_row(context))
    mail_rows.append(make_mail_draft(draft_type, context))


def route_review(
    review_rows: list[dict[str, Any]],
    mail_rows: list[dict[str, Any]],
    context: ProcessingContext,
) -> None:
    review_rows.append(base_row(context))
    mail_rows.append(make_mail_draft("internal_review", context))


def insert_reading(conn: sqlite3.Connection, context: ProcessingContext) -> None:
    conn.execute(
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
            int(context.meter["meter_id"]),
            context.reading_date.isoformat(),
            context.reading_value,
            context.consumption_since_last,
            context.input_row["source"],
            "processed",
            context.reason,
        ),
    )
    conn.commit()


def processed_row(context: ProcessingContext) -> dict[str, Any]:
    return {
        "submission_id": context.submission_id,
        "customer_id": context.customer["customer_id"],
        "customer_name": context.customer["customer_name"],
        "meter_id": context.meter["meter_id"],
        "meter_number": context.meter["meter_number"],
        "meter_type": context.meter["meter_type"],
        "reading_date": context.reading_date.isoformat(),
        "previous_reading": (
            "" if context.previous_reading is None else context.previous_reading
        ),
        "new_reading": context.reading_value,
        "consumption_since_last": (
            "" if context.consumption_since_last is None else context.consumption_since_last
        ),
        "source": context.input_row["source"],
        "validation_status": "processed",
        "database_update": "yes",
        "notes": context.reason,
    }


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def write_summary_report(
    config: RuntimeConfig,
    total_submissions: int,
    processed_rows: list[dict[str, Any]],
    exceptions_rows: list[dict[str, Any]],
    review_rows: list[dict[str, Any]],
    new_customer_rows: list[dict[str, Any]],
    mail_rows: list[dict[str, Any]],
    image_review_count: int,
) -> str:
    generated_files = [
        "processed_readings.csv",
        "exceptions.csv",
        "human_review_queue.csv",
        "new_customer_candidates.csv",
        "mail_drafts.csv",
        "summary_report.txt",
    ]

    summary = f"""AI-assisted Meter Reading Validation RPA
=======================================

Run timestamp: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

Input file:
{display_path(config.input_path)}

Database:
{display_path(config.db_path)}

Processing Summary
------------------
Total submissions: {total_submissions}
Processed successfully: {len(processed_rows)}
Human review required: {len(review_rows)}
Exceptions: {len(exceptions_rows)}
New customer candidates: {len(new_customer_rows)}
Database records inserted: {len(processed_rows)}
Image-based cases routed to review: {image_review_count}
Mail drafts created: {len(mail_rows)}

Generated Output Files
----------------------
{chr(10).join(generated_files)}

Automation Status
-----------------
Completed successfully
"""

    (config.output_dir / "summary_report.txt").write_text(summary, encoding="utf-8")
    return summary


def main() -> None:
    args = parse_args()
    config = build_runtime_config(args)
    input_rows = load_input_rows(config.input_path)

    processed_rows: list[dict[str, Any]] = []
    exceptions_rows: list[dict[str, Any]] = []
    review_rows: list[dict[str, Any]] = []
    new_customer_rows: list[dict[str, Any]] = []
    mail_rows: list[dict[str, Any]] = []
    image_review_count = 0

    conn = sqlite3.connect(config.db_path)
    conn.row_factory = sqlite3.Row

    run_prefix = datetime.now().strftime("%Y%m%d")

    try:
        for index, row in enumerate(input_rows, start=1):
            context = ProcessingContext(
                submission_id=f"SUB-{run_prefix}-{index:04d}",
                input_row=row,
            )

            customer_id_text = row.get("customer_id", "")
            if not customer_id_text.isdigit():
                context.reason = "customer_id must be numeric"
                route_exception(exceptions_rows, mail_rows, context, "customer_correction")
                continue

            customer_id = int(customer_id_text)
            customer = fetch_one(
                conn,
                """
                SELECT customer_id, account_number, customer_name, service_address, is_active, created_at
                FROM customers
                WHERE customer_id = ?
                """,
                (customer_id,),
            )
            if customer is None:
                context.reason = "customer_id does not exist in customers table"
                new_customer_rows.append(base_row(context))
                route_review(review_rows, mail_rows, context)
                continue
            context.customer = customer

            if int(customer["is_active"]) != 1:
                context.reason = INACTIVE_METER_REASON
                route_exception(exceptions_rows, mail_rows, context, "customer_correction")
                continue

            meter_number = row.get("meter_number", "")
            meter = fetch_one(
                conn,
                """
                SELECT meter_id, customer_id, meter_number, meter_type, unit, is_active, installed_at
                FROM meters
                WHERE meter_number = ?
                """,
                (meter_number,),
            )
            if meter is None:
                context.reason = "meter_number does not exist in meters table"
                route_exception(exceptions_rows, mail_rows, context, "customer_correction")
                continue
            context.meter = meter

            if int(meter["customer_id"]) != customer_id:
                context.reason = "Meter does not belong to submitted customer_id"
                route_exception(exceptions_rows, mail_rows, context, "internal_review")
                continue

            if int(meter["is_active"]) != 1:
                context.reason = INACTIVE_METER_REASON
                route_exception(exceptions_rows, mail_rows, context, "customer_correction")
                continue

            reading_date_text = row.get("reading_date", "")
            if not reading_date_text:
                context.reason = "reading_date is required"
                route_exception(exceptions_rows, mail_rows, context, "customer_correction")
                continue
            try:
                reading_date = parse_reading_date(reading_date_text)
            except ValueError:
                context.reason = "reading_date must be a valid YYYY-MM-DD date"
                route_exception(exceptions_rows, mail_rows, context, "customer_correction")
                continue
            context.reading_date = reading_date

            if reading_date > date.today():
                context.reason = "reading_date must not be in the future"
                route_review(review_rows, mail_rows, context)
                continue

            source = row.get("source", "")
            if source not in ALLOWED_SOURCES:
                context.reason = (
                    "source must be one of: " + ", ".join(sorted(ALLOWED_SOURCES))
                )
                route_exception(exceptions_rows, mail_rows, context, "customer_correction")
                continue

            image_file = row.get("image_file", "")
            if image_file:
                context.reason = IMAGE_REVIEW_REASON
                image_review_count += 1
                route_review(review_rows, mail_rows, context)
                continue

            try:
                reading_value = parse_reading_value(row.get("reading_value", ""))
            except ValueError as error:
                context.reason = str(error)
                route_exception(exceptions_rows, mail_rows, context, "customer_correction")
                continue
            context.reading_value = reading_value

            duplicate = existing_month_reading(conn, int(meter["meter_id"]), reading_date)
            if duplicate is not None:
                context.reason = "Duplicate monthly reading detected for this meter"
                route_exception(exceptions_rows, mail_rows, context, "customer_correction")
                continue

            previous_reading = latest_previous_reading(conn, int(meter["meter_id"]), reading_date)
            context.previous_reading = previous_reading
            if previous_reading is not None:
                if reading_value < previous_reading:
                    context.reason = "New reading is lower than previous reading"
                    route_review(review_rows, mail_rows, context)
                    continue
                context.consumption_since_last = reading_value - previous_reading
                if context.consumption_since_last > ANOMALY_THRESHOLD:
                    context.reason = "Unusually high consumption"
                    route_review(review_rows, mail_rows, context)
                    continue
            else:
                context.consumption_since_last = None

            context.reason = "Normal meter reading processed successfully."
            insert_reading(conn, context)
            processed_rows.append(processed_row(context))
            mail_rows.append(make_mail_draft("customer_confirmation", context))
    finally:
        conn.close()

    write_csv(config.output_dir / "processed_readings.csv", processed_rows, PROCESSED_COLUMNS)
    write_csv(config.output_dir / "exceptions.csv", exceptions_rows, EXCEPTION_COLUMNS)
    write_csv(config.output_dir / "human_review_queue.csv", review_rows, REVIEW_COLUMNS)
    write_csv(
        config.output_dir / "new_customer_candidates.csv",
        new_customer_rows,
        NEW_CUSTOMER_COLUMNS,
    )
    write_csv(config.output_dir / "mail_drafts.csv", mail_rows, MAIL_COLUMNS)
    summary_text = write_summary_report(
        config=config,
        total_submissions=len(input_rows),
        processed_rows=processed_rows,
        exceptions_rows=exceptions_rows,
        review_rows=review_rows,
        new_customer_rows=new_customer_rows,
        mail_rows=mail_rows,
        image_review_count=image_review_count,
    )
    print(summary_text)


if __name__ == "__main__":
    main()
