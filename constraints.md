# Data Constraints

## Input CSV

Expected file:

`data/input/portal_export.csv`

Required columns:

- `customer_id`
- `meter_number`
- `reading_date`
- `reading_value`
- `source`
- `image_file`
- `notes`

The input CSV must not contain `submission_id`.  
`submission_id` is generated internally by the automation.

---

## Customer Constraints

- `customer_id` must exist in the `customers` table.
- Customer must be active: `is_active = 1`.

---

## Meter Constraints

- `meter_number` must exist in the `meters` table.
- The meter must belong to the submitted `customer_id`.
- Meter must be active: `is_active = 1`.
- One customer can have multiple meters.
- One meter belongs to exactly one customer.

---

## Reading Date Constraints

- `reading_date` is required.
- `reading_date` must follow this format: `YYYY-MM-DD`.
- `reading_date` must be a valid date.
- `reading_date` must not be in the future.

---

## Reading Value Constraints

- A submission must contain either `reading_value` or `image_file`.
- If `image_file` is empty, `reading_value` is required.
- `reading_value` must be numeric.
- `reading_value` must be greater than or equal to `0`.
- New `reading_value` must not be lower than the latest previous reading for the same meter.

---

## Duplicate Constraint

- For each `meter_id`, only one reading is allowed per month.
- Duplicate detection is based on:
  - `meter_id`
  - reading month from `reading_date`
- Duplicate detection is not based on `submission_id`.

---

## Consumption Constraint

- `consumption_since_last` is calculated as:

`new_reading - previous_reading`

- If no previous reading exists, `consumption_since_last = null`.
- If `consumption_since_last > 5000`, the record is considered an anomaly.

---

## Source Constraint

Allowed `source` values:

- `portal`
- `mobile_app`
- `app_photo`

Any other source value is invalid.

---

## Image / AI Data Constraint

- If `reading_value` is empty and `image_file` exists, the image must be sent to the AI image-reading module.
- The AI-extracted value must still satisfy the same data constraints as a normal `reading_value`.
- AI-based readings must not be written directly to `meter_reading_history`.

---

## Database Insert Constraint

A new record can be inserted into `meter_reading_history` only if:

- customer exists
- customer is active
- meter exists
- meter belongs to the customer
- meter is active
- reading date is valid
- reading date is not in the future
- reading value is numeric
- reading value is non-negative
- no duplicate reading exists for the same meter and month
- new reading is not lower than the previous reading
- consumption is not above the anomaly threshold
- AI was not used