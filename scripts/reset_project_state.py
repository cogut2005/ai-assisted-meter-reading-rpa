from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = PROJECT_ROOT / "data" / "input"
OUTPUT_DIR = PROJECT_ROOT / "data" / "output"
DB_PATH = PROJECT_ROOT / "data" / "history" / "master.db"

BASELINE_CUSTOMERS = [
    (1, "ACC-1001", "Emma Carter", "12 Oak Street, Berlin", 1, "2026-07-01"),
    (2, "ACC-1002", "Liam Foster", "48 River Lane, Berlin", 1, "2026-07-01"),
    (3, "ACC-1003", "Noah Bennett", "9 Linden Avenue, Berlin", 0, "2026-07-01"),
    (4, "ACC-1004", "Olivia Hayes", "23 Maple Court, Berlin", 1, "2026-07-01"),
]

BASELINE_CUSTOMER_CONTACTS = [
    (1, "emma.carter@example.com"),
    (2, "liam.foster@example.com"),
    (3, "inactive.customer@example.com"),
    (4, "olivia.hayes@example.com"),
]

BASELINE_METERS = [
    (
        1,
        1,
        "MTR-0001",
        "electricity",
        "kWh",
        1,
        "2026-07-01",
        "Migrated from customers table.",
    ),
    (
        2,
        2,
        "MTR-0002",
        "electricity",
        "kWh",
        1,
        "2026-07-01",
        "Migrated from customers table.",
    ),
    (
        3,
        1,
        "MTR-0003",
        "gas",
        "m3",
        1,
        "2026-07-01",
        "Second meter added for customer 1.",
    ),
    (
        4,
        3,
        "MTR-0004",
        "electricity",
        "kWh",
        1,
        "2026-07-01",
        "Meter assigned to inactive customer for exception-routing test case.",
    ),
    (
        5,
        4,
        "MTR-0005",
        "electricity",
        "kWh",
        1,
        "2026-07-01",
        "Meter for new active customer; image-based reading demo.",
    ),
]

BASELINE_HISTORY = [
    (
        740001,
        1,
        "2026-04-01",
        15230,
        None,
        "portal",
        "valid",
        "Baseline reading loaded into master history.",
    ),
    (
        740002,
        1,
        "2026-05-01",
        15410,
        180,
        "portal",
        "valid",
        "Monthly customer submission.",
    ),
    (
        740003,
        1,
        "2026-06-01",
        15605,
        195,
        "portal",
        "valid",
        "Monthly customer submission.",
    ),
    (
        740004,
        2,
        "2026-04-01",
        8840,
        None,
        "portal",
        "valid",
        "Baseline reading loaded into master history.",
    ),
    (
        740005,
        2,
        "2026-05-01",
        8965,
        125,
        "portal",
        "valid",
        "Monthly customer submission.",
    ),
    (
        740006,
        2,
        "2026-06-01",
        9090,
        125,
        "portal",
        "valid",
        "Monthly customer submission.",
    ),
    (
        740007,
        3,
        "2026-06-01",
        3205,
        None,
        "portal",
        "valid",
        "Initial historical reading for customer 1 second meter; same date as another meter reading.",
    ),
    (
        740008,
        5,
        "2026-06-01",
        5120,
        None,
        "portal",
        "valid",
        "Initial historical reading for new customer's meter.",
    ),
]

INPUT_COLUMNS = [
    "customer_id",
    "meter_number",
    "reading_date",
    "reading_value",
    "source",
    "image",
    "notes",
]

BASELINE_INPUT_FILES = {
    "portal_export1.csv": [
        [
            "1",
            "MTR-0001",
            "2026-07-01",
            "15652",
            "portal",
            "",
            "New weekly portal submission for customer 1.",
        ],
    ],
    "portal_export2.csv": [
        [
            "2",
            "MTR-0002",
            "2026-07-02",
            "",
            "portal",
            "data/input/images/reading1.png",
            "Photo-based meter image for GPT-assisted human review.",
        ],
    ],
    "portal_export3.csv": [
        [
            "1",
            "MTR-0003",
            "2026-07-02",
            "3210",
            "email",
            "",
            "Invalid source should trigger exception.",
        ],
    ],
    "portal_export4.csv": [
        [
            "1",
            "MTR-0003",
            "2026-07-04",
            "",
            "portal",
            "data/input/images/reading2.png",
            "Photo-based meter image for GPT-assisted human review.",
        ],
    ],
    "portal_export5.csv": [
        [
            "3",
            "MTR-0004",
            "2026-07-03",
            "1185",
            "portal",
            "",
            "Submission for inactive customer; should be routed to exception.",
        ],
    ],
    "portal_export6.csv": [
        [
            "4",
            "MTR-0005",
            "2026-07-05",
            "",
            "portal",
            "data/input/images/reading3.png",
            "Photo-based meter image for GPT-assisted human review.",
        ],
    ],
}


def clear_output_directory() -> int:
    if not OUTPUT_DIR.exists():
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        return 0

    deleted_files = 0
    for path in sorted(OUTPUT_DIR.rglob("*"), reverse=True):
        if path.is_file():
            path.unlink()
            deleted_files += 1
        elif path.is_dir() and path != OUTPUT_DIR:
            try:
                path.rmdir()
            except OSError:
                pass

    return deleted_files


def reset_input_directory() -> tuple[int, int]:
    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    deleted_files = 0
    for path in sorted(INPUT_DIR.glob("*.csv")):
        if path.is_file():
            path.unlink()
            deleted_files += 1

    for file_name, rows in BASELINE_INPUT_FILES.items():
        output_path = INPUT_DIR / file_name
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(INPUT_COLUMNS)
            writer.writerows(rows)

    return deleted_files, len(BASELINE_INPUT_FILES)


def reset_database() -> tuple[int, int, int, int]:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute("PRAGMA foreign_keys = ON")
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS customer_contacts (
                    customer_id INTEGER PRIMARY KEY,
                    email TEXT NOT NULL UNIQUE,
                    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
                )
                """
            )
            conn.execute("DELETE FROM meter_reading_history")
            conn.execute("DELETE FROM meters")
            conn.execute("DELETE FROM customer_contacts")
            conn.execute("DELETE FROM customers")

            conn.executemany(
                """
                INSERT INTO customers (
                    customer_id,
                    account_number,
                    customer_name,
                    service_address,
                    is_active,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                BASELINE_CUSTOMERS,
            )
            conn.executemany(
                """
                INSERT INTO customer_contacts (
                    customer_id,
                    email
                )
                VALUES (?, ?)
                """,
                BASELINE_CUSTOMER_CONTACTS,
            )
            conn.executemany(
                """
                INSERT INTO meters (
                    meter_id,
                    customer_id,
                    meter_number,
                    meter_type,
                    unit,
                    is_active,
                    installed_at,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                BASELINE_METERS,
            )
            conn.executemany(
                """
                INSERT INTO meter_reading_history (
                    reading_id,
                    meter_id,
                    reading_date,
                    reading_value,
                    consumption_since_last,
                    source,
                    validation_status,
                    notes
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                BASELINE_HISTORY,
            )
        return (
            len(BASELINE_CUSTOMERS),
            len(BASELINE_CUSTOMER_CONTACTS),
            len(BASELINE_METERS),
            len(BASELINE_HISTORY),
        )
    finally:
        conn.close()


def main() -> None:
    deleted_files = clear_output_directory()
    deleted_input_files, recreated_input_files = reset_input_directory()
    customer_count, contact_count, meter_count, history_count = reset_database()

    print("Project state reset complete.")
    print(f"Deleted output files: {deleted_files}")
    print(f"Deleted input CSV files: {deleted_input_files}")
    print(f"Recreated input CSV files: {recreated_input_files}")
    print(f"Customers restored: {customer_count}")
    print(f"Customer contacts restored: {contact_count}")
    print(f"Meters restored: {meter_count}")
    print(f"History rows restored: {history_count}")
    print(f"Database: {DB_PATH}")
    print(f"Input directory: {INPUT_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
