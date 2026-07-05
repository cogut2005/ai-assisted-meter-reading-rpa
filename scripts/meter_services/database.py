from __future__ import annotations

import sqlite3

from .contracts import DatabaseInsertRequest, DatabaseInsertResult


def insert_valid_reading(
    conn: sqlite3.Connection, request: DatabaseInsertRequest
) -> DatabaseInsertResult:
    """Insert an already-approved reading row into SQLite."""
    cursor = conn.execute(
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
            request.meter_id,
            request.reading_date,
            request.reading_value,
            request.consumption_since_last,
            request.source,
            request.validation_status,
            request.notes,
        ),
    )
    conn.commit()
    return DatabaseInsertResult(
        inserted=True,
        reading_id=cursor.lastrowid,
        message="Reading inserted successfully.",
    )
