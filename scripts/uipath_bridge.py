from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _db_path(raw_db_path: str) -> Path:
    path = Path(raw_db_path).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _json(data: object) -> str:
    return json.dumps(data, ensure_ascii=True)


def validate_submission_for_uipath(
    db_path: str,
    submission_id: str,
    customer_id: str,
    meter_number: str,
    reading_date: str,
    reading_value: str,
    source: str,
    image_file: str = "",
    notes: str = "",
) -> str:
    from meter_services.contracts import InputSubmission
    from meter_services.validation import validate_submission

    submission = InputSubmission(
        submission_id=submission_id,
        customer_id=customer_id,
        meter_number=meter_number,
        reading_date=reading_date,
        reading_value=reading_value,
        source=source,
        image_file=image_file,
        notes=notes,
    )

    conn = sqlite3.connect(_db_path(db_path))
    conn.row_factory = sqlite3.Row
    try:
        result = validate_submission(conn, submission)
    finally:
        conn.close()

    payload = asdict(result)
    payload["decision"] = result.decision.value
    return _json(payload)


def insert_valid_reading_for_uipath(
    db_path: str,
    meter_id: int,
    reading_date: str,
    reading_value: int,
    consumption_since_last: int | None,
    source: str,
    validation_status: str = "processed",
    notes: str = "",
) -> str:
    from meter_services.contracts import DatabaseInsertRequest
    from meter_services.database import insert_valid_reading

    request = DatabaseInsertRequest(
        meter_id=int(meter_id),
        reading_date=reading_date,
        reading_value=int(reading_value),
        consumption_since_last=(
            None if consumption_since_last in ("", None) else int(consumption_since_last)
        ),
        source=source,
        validation_status=validation_status,
        notes=notes,
    )

    conn = sqlite3.connect(_db_path(db_path))
    try:
        result = insert_valid_reading(conn, request)
    finally:
        conn.close()
    return _json(asdict(result))


def build_mail_draft_for_uipath(
    submission_id: str,
    draft_type: str,
    recipient_type: str,
    recipient: str,
    customer_name: str = "",
    meter_number: str = "",
    reading_date: str = "",
    reading_value: str = "",
    unit: str = "",
    reason: str = "",
) -> str:
    from meter_services.contracts import MailDraftRequest
    from meter_services.mails import build_mail_draft

    request = MailDraftRequest(
        submission_id=submission_id,
        draft_type=draft_type,
        recipient_type=recipient_type,
        recipient=recipient,
        customer_name=customer_name,
        meter_number=meter_number,
        reading_date=reading_date,
        reading_value=reading_value,
        unit=unit,
        reason=reason,
    )
    result = build_mail_draft(request)
    return _json(asdict(result))


def build_summary_report_for_uipath(
    run_timestamp: str,
    input_path: str,
    database_path: str,
    total_submissions: int,
    processed_successfully: int,
    human_review_required: int,
    exceptions: int,
    new_customer_candidates: int,
    database_records_inserted: int,
    image_based_cases_routed_to_review: int,
    mail_drafts_created: int,
    generated_output_files_json: str,
) -> str:
    from meter_services.contracts import SummaryReportRequest
    from meter_services.reporting import build_summary_report

    request = SummaryReportRequest(
        run_timestamp=run_timestamp,
        input_path=input_path,
        database_path=database_path,
        total_submissions=int(total_submissions),
        processed_successfully=int(processed_successfully),
        human_review_required=int(human_review_required),
        exceptions=int(exceptions),
        new_customer_candidates=int(new_customer_candidates),
        database_records_inserted=int(database_records_inserted),
        image_based_cases_routed_to_review=int(image_based_cases_routed_to_review),
        mail_drafts_created=int(mail_drafts_created),
        generated_output_files=json.loads(generated_output_files_json),
    )
    return build_summary_report(request)
