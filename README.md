# AI-assisted Meter Reading Validation RPA

A proof-of-concept automation that validates recurring energy-company **meter reading submissions**.
UiPath is the visible orchestrator; Python does the deterministic business validation; SQLite stores
customer/meter history; and a GPT vision model assists (only as a reviewer aid) for photo-based readings.

---

## What it does

- Reads all `data/input/*.csv` portal/mobile exports, one row at a time.
- Validates each submission against business rules using local SQLite history (`data/history/master.db`).
- Routes each row to one of:
  - **processed** – clean, non-image reading → inserted into the database automatically.
  - **human_review** – photo submissions and uncertain cases → GPT reads the image as a *suggestion*,
    a human approves the value in a UiPath form, then the value is **re-validated** before insert.
  - **exception** – hard validation errors (invalid source, duplicate month, etc.) → shown with the
    specific reason, not inserted.
- Generates a customer confirmation e-mail draft (from a strict template) and can send it via Gmail
  after human review.

## How it works (architecture)

```
CSV exports  ->  UiPath (Main.xaml)  ->  Python CLIs  ->  SQLite + outputs
                 row loop + PowerShell    business rules    DB, charts, mail drafts
```

- **UiPath** (`rpa/Main.xaml`): orchestration, row loop, PowerShell calls, review forms, Gmail send.
- **Python** (`scripts/`): validation, DB inserts, image extraction, mail-draft generation, reporting.
- **Data** (`data/history/master.db`): `customers`, `meters`, `meter_reading_history`, `customer_contacts`.

---

## Prerequisites

- **UiPath Studio 26.x** (Windows) with these packages (already referenced in `rpa/project.json`):
  `UiPath.System`, `UiPath.Python`, `UiPath.Mail`, `UiPath.Form`, `UiPath.Excel` Activities.
- **Python 3.10+** installed on Windows.
- An **OpenAI API key** (used for image reading and mail-draft generation).
- A **Gmail account** (used to send the customer confirmation e-mail).

Install the Python dependencies:

```cmd
pip install -r requirements.txt
```

---

## Setup

There are **three things you must configure** before the automation runs cleanly.

### 1. Tell UiPath where your Python is

The workflow calls Python through PowerShell, so it needs the full path to your `python.exe`.

1. Open **Command Prompt (cmd)** and run:

   ```cmd
   where python
   ```

2. Copy the **real** interpreter path, for example:

   ```text
   C:\Users\<you>\AppData\Local\Programs\Python\Python313\python.exe
   ```

   > ⚠️ Do **not** use the Microsoft Store stub path
   > (`...\AppData\Local\Microsoft\WindowsApps\python.exe`) — it will not work reliably.

3. In UiPath Studio, open `rpa/Main.xaml`. The **first `Assign` activity** sets the variable
   `pythonExePath`. Replace its value with the path you copied.

### 2. Create a `.env` file with your OpenAI API key

The Python scripts read the OpenAI key from a `.env` file in the **repository root**.

1. In the project root, create a file named exactly `.env`.
2. Add your key:

   ```dotenv
   OPENAI_API_KEY=sk-your-key-here
   ```

   You can optionally pin the model (defaults to `gpt-4.1-mini`):

   ```dotenv
   OPENAI_MODEL=gpt-4.1-mini
   ```

> `.env` is listed in `.gitignore`, so **your API key is never committed**.

### 3. Configure your mail account (for sending)

To let the automation actually send the confirmation e-mail:

1. In `rpa/Main.xaml`, find the **"Use Gmail"** activity (the `GmailApplicationCard`, near the
   mail-sending sequence).
2. Set its **Account** / **EmailAddress** to **your own Gmail address**
   (the committed value is a placeholder, `your-email@gmail.com`).
3. Authenticate your Google account when UiPath prompts you.

> The first delivered message may land in **spam**. For a demo, mark it as "not spam" / add the sender
> to contacts on the recipient side. For production, use a proper domain mailbox with SPF/DKIM/DMARC.

---

## Running the automation

1. Complete the three setup steps above.
2. Make sure input CSVs exist in `data/input/` (the reset script recreates the baseline set — see below).
3. Open `rpa/Main.xaml` in UiPath Studio and **Run**.
4. The workflow processes every CSV in `data/input/`, shows review/exception messages where needed,
   sends the confirmation mail after review, and deletes each CSV once processed.

## Resetting to the baseline state

To wipe outputs, restore the seed database, and recreate the baseline input CSVs:

```cmd
python scripts/reset_project_state.py
```

This reseeds the customers, contacts, meters, and reading history, and regenerates
`data/input/portal_export1.csv` … `portal_export6.csv` (covering clean, image-review, invalid-source,
inactive-customer, and new-customer cases).

---

## Repository structure

```text
ai-assisted-meter-reading-rpa/
├── rpa/                     UiPath project (Main.xaml is the entry point)
├── scripts/                Python CLIs + meter_services package (validation, DB, charts, mail)
│   └── reset_project_state.py   Rebuilds the baseline DB + input CSVs
├── data/
│   ├── input/              portal_export*.csv exports + images/
│   ├── history/master.db   SQLite seed database
│   └── templates/          customer confirmation mail template
├── bpmn/                   To-Be process diagram
├── requirements.txt        Python dependencies
└── README.md
```

---

## Notes

- **Data is fictional.** All customer names and e-mail addresses in the seed database are placeholders
  (`*@example.com`). This is a proof of concept, not a production system.
- The seed database and input CSVs are meant to be regenerated with `reset_project_state.py`.
