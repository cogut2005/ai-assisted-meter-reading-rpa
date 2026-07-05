from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class RouteDecision(str, Enum):
    PROCESSED = "processed"
    EXCEPTION = "exception"
    HUMAN_REVIEW = "human_review"
    NEW_CUSTOMER = "new_customer"


@dataclass(slots=True)
class InputSubmission:
    submission_id: str
    customer_id: str
    meter_number: str
    reading_date: str
    reading_value: str
    source: str
    image_file: str
    notes: str = ""


@dataclass(slots=True)
class ValidationResult:
    decision: RouteDecision
    reason: str
    customer_id: int | None = None
    customer_name: str = ""
    meter_id: int | None = None
    meter_number: str = ""
    meter_type: str = ""
    unit: str = ""
    previous_reading: int | None = None
    new_reading: int | None = None
    consumption_since_last: int | None = None
    database_update_allowed: bool = False
    image_review_required: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class DatabaseInsertRequest:
    meter_id: int
    reading_date: str
    reading_value: int
    consumption_since_last: int | None
    source: str
    validation_status: str
    notes: str


@dataclass(slots=True)
class DatabaseInsertResult:
    inserted: bool
    reading_id: int | None
    message: str


@dataclass(slots=True)
class MailDraftRequest:
    submission_id: str
    draft_type: str
    recipient_type: str
    recipient: str
    customer_name: str = ""
    meter_number: str = ""
    reading_date: str = ""
    reading_value: str = ""
    unit: str = ""
    reason: str = ""


@dataclass(slots=True)
class MailDraftResult:
    submission_id: str
    draft_type: str
    recipient_type: str
    recipient: str
    subject: str
    body: str
    status: str


@dataclass(slots=True)
class SummaryReportRequest:
    run_timestamp: str
    input_path: str
    database_path: str
    total_submissions: int
    processed_successfully: int
    human_review_required: int
    exceptions: int
    new_customer_candidates: int
    database_records_inserted: int
    image_based_cases_routed_to_review: int
    mail_drafts_created: int
    generated_output_files: list[str]
