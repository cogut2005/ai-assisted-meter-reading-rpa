from __future__ import annotations

from .contracts import MailDraftRequest, MailDraftResult


def build_mail_draft(request: MailDraftRequest) -> MailDraftResult:
    """Create a deterministic mail draft contract for UiPath or CSV output."""
    if request.draft_type == "customer_confirmation":
        subject = "Meter reading received"
        unit_suffix = f" {request.unit}" if request.unit else ""
        reading_sentence = (
            f"The recorded reading is {request.reading_value}{unit_suffix}. "
            if request.reading_value
            else ""
        )
        body = (
            f"Dear customer, your meter reading for meter {request.meter_number} on "
            f"{request.reading_date} has been received and processed successfully. "
            f"{reading_sentence}"
            "Best regards, Customer Service Team"
        )
    elif request.draft_type == "customer_correction":
        subject = "Meter reading correction required"
        body = (
            "Dear customer, your submitted meter reading could not be processed because "
            f"{request.reason.lower()}. Please submit the reading again or upload a clear meter image. "
            "Best regards, Customer Service Team"
        )
    else:
        subject = "Meter reading requires manual review"
        body = (
            f"Submission {request.submission_id} requires manual review. Reason: {request.reason}. "
            f"Meter: {request.meter_number}. Reading date: {request.reading_date}. "
            "Please verify the case before database update."
        )

    return MailDraftResult(
        submission_id=request.submission_id,
        draft_type=request.draft_type,
        recipient_type=request.recipient_type,
        recipient=request.recipient,
        subject=subject,
        body=body,
        status="draft_created",
    )
