from __future__ import annotations

import sqlite3
from datetime import date, datetime

from .contracts import InputSubmission, RouteDecision, ValidationResult

ALLOWED_SOURCES = {"portal", "mobile_app", "app_photo"}
ANOMALY_THRESHOLD = 5000
IMAGE_REVIEW_REASON = "Image-based submission requires AI image reading and human review"
INACTIVE_METER_REASON = "User's meter is inactive and needs to be activated first"


def fetch_one(
    conn: sqlite3.Connection, query: str, params: tuple[object, ...]
) -> dict[str, object] | None:
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
) -> dict[str, object] | None:
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


def validate_submission(
    conn: sqlite3.Connection, submission: InputSubmission
) -> ValidationResult:
    """
    Validate a single submission and return a contract object for UiPath.

    UiPath should branch on `decision` and use the rest of the fields as the
    normalized validation payload.
    """
    if not submission.customer_id.isdigit():
        return ValidationResult(
            decision=RouteDecision.EXCEPTION,
            reason="customer_id must be numeric",
            meter_number=submission.meter_number,
        )

    customer_id = int(submission.customer_id)
    customer = fetch_one(
        conn,
        """
        SELECT customer_id, customer_name, is_active
        FROM customers
        WHERE customer_id = ?
        """,
        (customer_id,),
    )
    if customer is None:
        return ValidationResult(
            decision=RouteDecision.NEW_CUSTOMER,
            reason="customer_id does not exist in customers table",
            meter_number=submission.meter_number,
        )
    if int(customer["is_active"]) != 1:
        return ValidationResult(
            decision=RouteDecision.EXCEPTION,
            reason=INACTIVE_METER_REASON,
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_number=submission.meter_number,
        )

    meter = fetch_one(
        conn,
        """
        SELECT meter_id, customer_id, meter_number, meter_type, unit, is_active
        FROM meters
        WHERE meter_number = ?
        """,
        (submission.meter_number,),
    )
    if meter is None:
        return ValidationResult(
            decision=RouteDecision.EXCEPTION,
            reason="meter_number does not exist in meters table",
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_number=submission.meter_number,
        )
    if int(meter["customer_id"]) != customer_id:
        return ValidationResult(
            decision=RouteDecision.EXCEPTION,
            reason="Meter does not belong to submitted customer_id",
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_id=int(meter["meter_id"]),
            meter_number=str(meter["meter_number"]),
            meter_type=str(meter["meter_type"]),
            unit=str(meter["unit"]),
        )
    if int(meter["is_active"]) != 1:
        return ValidationResult(
            decision=RouteDecision.EXCEPTION,
            reason=INACTIVE_METER_REASON,
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_id=int(meter["meter_id"]),
            meter_number=str(meter["meter_number"]),
            meter_type=str(meter["meter_type"]),
            unit=str(meter["unit"]),
        )

    if not submission.reading_date:
        return ValidationResult(
            decision=RouteDecision.EXCEPTION,
            reason="reading_date is required",
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_id=int(meter["meter_id"]),
            meter_number=str(meter["meter_number"]),
            meter_type=str(meter["meter_type"]),
            unit=str(meter["unit"]),
        )
    try:
        reading_date = parse_reading_date(submission.reading_date)
    except ValueError:
        return ValidationResult(
            decision=RouteDecision.EXCEPTION,
            reason="reading_date must be a valid YYYY-MM-DD date",
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_id=int(meter["meter_id"]),
            meter_number=str(meter["meter_number"]),
            meter_type=str(meter["meter_type"]),
            unit=str(meter["unit"]),
        )
    if reading_date > date.today():
        return ValidationResult(
            decision=RouteDecision.HUMAN_REVIEW,
            reason="reading_date must not be in the future",
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_id=int(meter["meter_id"]),
            meter_number=str(meter["meter_number"]),
            meter_type=str(meter["meter_type"]),
            unit=str(meter["unit"]),
            metadata={"reading_date": submission.reading_date},
        )

    if submission.source not in ALLOWED_SOURCES:
        return ValidationResult(
            decision=RouteDecision.EXCEPTION,
            reason="source must be one of: " + ", ".join(sorted(ALLOWED_SOURCES)),
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_id=int(meter["meter_id"]),
            meter_number=str(meter["meter_number"]),
            meter_type=str(meter["meter_type"]),
            unit=str(meter["unit"]),
        )

    if submission.image_file:
        return ValidationResult(
            decision=RouteDecision.HUMAN_REVIEW,
            reason=IMAGE_REVIEW_REASON,
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_id=int(meter["meter_id"]),
            meter_number=str(meter["meter_number"]),
            meter_type=str(meter["meter_type"]),
            unit=str(meter["unit"]),
            image_review_required=True,
            metadata={"reading_date": submission.reading_date},
        )

    try:
        new_reading = parse_reading_value(submission.reading_value)
    except ValueError as error:
        return ValidationResult(
            decision=RouteDecision.EXCEPTION,
            reason=str(error),
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_id=int(meter["meter_id"]),
            meter_number=str(meter["meter_number"]),
            meter_type=str(meter["meter_type"]),
            unit=str(meter["unit"]),
        )

    duplicate = existing_month_reading(conn, int(meter["meter_id"]), reading_date)
    if duplicate is not None:
        return ValidationResult(
            decision=RouteDecision.EXCEPTION,
            reason="Duplicate monthly reading detected for this meter",
            customer_id=customer_id,
            customer_name=str(customer["customer_name"]),
            meter_id=int(meter["meter_id"]),
            meter_number=str(meter["meter_number"]),
            meter_type=str(meter["meter_type"]),
            unit=str(meter["unit"]),
            new_reading=new_reading,
        )

    previous_reading = latest_previous_reading(conn, int(meter["meter_id"]), reading_date)
    consumption_since_last = None
    if previous_reading is not None:
        if new_reading < previous_reading:
            return ValidationResult(
                decision=RouteDecision.HUMAN_REVIEW,
                reason="New reading is lower than previous reading",
                customer_id=customer_id,
                customer_name=str(customer["customer_name"]),
                meter_id=int(meter["meter_id"]),
                meter_number=str(meter["meter_number"]),
                meter_type=str(meter["meter_type"]),
                unit=str(meter["unit"]),
                previous_reading=previous_reading,
                new_reading=new_reading,
            )
        consumption_since_last = new_reading - previous_reading
        if consumption_since_last > ANOMALY_THRESHOLD:
            return ValidationResult(
                decision=RouteDecision.HUMAN_REVIEW,
                reason="Unusually high consumption",
                customer_id=customer_id,
                customer_name=str(customer["customer_name"]),
                meter_id=int(meter["meter_id"]),
                meter_number=str(meter["meter_number"]),
                meter_type=str(meter["meter_type"]),
                unit=str(meter["unit"]),
                previous_reading=previous_reading,
                new_reading=new_reading,
                consumption_since_last=consumption_since_last,
            )

    return ValidationResult(
        decision=RouteDecision.PROCESSED,
        reason="Normal meter reading processed successfully.",
        customer_id=customer_id,
        customer_name=str(customer["customer_name"]),
        meter_id=int(meter["meter_id"]),
        meter_number=str(meter["meter_number"]),
        meter_type=str(meter["meter_type"]),
        unit=str(meter["unit"]),
        previous_reading=previous_reading,
        new_reading=new_reading,
        consumption_since_last=consumption_since_last,
        database_update_allowed=True,
        metadata={"reading_date": submission.reading_date},
    )
