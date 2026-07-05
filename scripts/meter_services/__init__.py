"""Service-layer package for UiPath-driven meter reading automation."""

from .contracts import (
    DatabaseInsertRequest,
    DatabaseInsertResult,
    InputSubmission,
    MailDraftRequest,
    MailDraftResult,
    RouteDecision,
    SummaryReportRequest,
    ValidationResult,
)

__all__ = [
    "DatabaseInsertRequest",
    "DatabaseInsertResult",
    "InputSubmission",
    "MailDraftRequest",
    "MailDraftResult",
    "RouteDecision",
    "SummaryReportRequest",
    "ValidationResult",
]
