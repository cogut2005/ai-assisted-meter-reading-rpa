# Project Roadmap  
## AI-assisted Meter Reading Validation RPA

---

## 1. Project Idea

The project is a proof of concept for automating a recurring meter reading validation process in an energy-company context.

Customer meter readings are assumed to come from an online portal or mobile app as a structured CSV export. Existing customer and meter reading history data is stored in a local SQLite database. The automation validates new submissions, detects errors and anomalies, updates the history database for valid records, and routes uncertain cases to a human review queue.

For image-based meter submissions, an AI/API component can be used to extract a possible meter reading value. Since image recognition can be uncertain, the result is validated with confidence thresholds and business rules before being accepted.

---

## 2. Technologies Used

| Area | Technology | Purpose |
|---|---|---|
| RPA Orchestration | UiPath Studio | Starts the automation flow, triggers Python processing, organizes execution |
| Data Processing | Python | Cleans data, validates records, calculates consumption, creates outputs |
| Database | SQLite | Stores customer master data and historical meter readings |
| Data Handling | Python standard library `csv` | Reads CSV input and creates output reports without extra tabular dependencies |
| AI/API Support | OpenAI API or another vision-capable AI API | Optional image-based meter reading extraction |
| Secret Handling | `.env` / environment variables | Stores API key locally without committing secrets |
| Outputs | CSV / TXT | Processed records, exceptions, human review queue, summary report |
| Version Control | Git + GitHub | Stores code, UiPath workflow, documentation and test data |

---

## 3. Repository Structure

```text
ai-assisted-meter-reading-rpa/
│
├── README.md
├── roadmap.md
├── requirements.txt
├── .gitignore
├── .env.example
│
├── data/
│   ├── input/
│   │   ├── portal_export.csv
│   │   └── images/
│   │       ├── meter_001.jpg
│   │       └── meter_002.jpg
│   │
│   ├── database/
│   │   └── meter_reading.db
│   │
│   └── output/
│       ├── processed_readings.csv
│       ├── exceptions.csv
│       ├── human_review_queue.csv
│       ├── new_customer_candidates.csv
│       └── summary_report.txt
│
├── scripts/
│   ├── setup_database.py
│   ├── process_meter_readings.py
│   ├── ai_meter_reader.py
│   └── config.py
│
├── ui_path/
│   └── MeterReadingAutomation/
│       ├── Main.xaml
│       ├── project.json
│       └── entry-points.json
│
├── documentation/
│   ├── business_documentation.md
│   ├── technical_documentation.md
│   └── presentation_outline.md
│
└── screenshots/
    ├── workflow_overview.png
    ├── input_data.png
    ├── database_tables.png
    └── output_files.png
