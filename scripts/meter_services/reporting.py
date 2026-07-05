from __future__ import annotations

import csv
from pathlib import Path

from .contracts import SummaryReportRequest


def write_output_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    """Write a CSV with headers even when the row list is empty."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=columns, extrasaction="ignore", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def build_summary_report(request: SummaryReportRequest) -> str:
    return f"""AI-assisted Meter Reading Validation RPA
=======================================

Run timestamp: {request.run_timestamp}

Input file:
{request.input_path}

Database:
{request.database_path}

Processing Summary
------------------
Total submissions: {request.total_submissions}
Processed successfully: {request.processed_successfully}
Human review required: {request.human_review_required}
Exceptions: {request.exceptions}
New customer candidates: {request.new_customer_candidates}
Database records inserted: {request.database_records_inserted}
Image-based cases routed to review: {request.image_based_cases_routed_to_review}
Mail drafts created: {request.mail_drafts_created}

Generated Output Files
----------------------
{chr(10).join(request.generated_output_files)}

Automation Status
-----------------
Completed successfully
"""
