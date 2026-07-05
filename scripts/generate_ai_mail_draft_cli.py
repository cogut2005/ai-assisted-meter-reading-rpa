from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
DEFAULT_TEMPLATE_PATH = (
    PROJECT_ROOT / "data" / "templates" / "customer_confirmation_mail_template.txt"
)


MAIL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "subject": {
            "type": "string",
            "description": "Customer-facing email subject line.",
        },
        "body": {
            "type": "string",
            "description": "Customer-facing email body.",
        },
    },
    "required": ["subject", "body"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a customer mail draft from a template using a GPT model."
    )
    parser.add_argument("--submission-id", required=True)
    parser.add_argument("--recipient", required=True)
    parser.add_argument("--customer-name", default="")
    parser.add_argument("--meter-number", required=True)
    parser.add_argument("--reading-date", required=True)
    parser.add_argument("--reading-value", required=True)
    parser.add_argument("--unit", default="")
    parser.add_argument("--consumption-since-last", default="")
    parser.add_argument("--language", default="English")
    parser.add_argument("--template-path", default=str(DEFAULT_TEMPLATE_PATH))
    parser.add_argument("--output-json", required=True)
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"OpenAI model to use. Default: {DEFAULT_MODEL}",
    )
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_path(raw_path: str) -> Path:
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def resolve_output_path(raw_path: str) -> Path:
    path = resolve_path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)

    if hasattr(response, "model_dump"):
        payload = response.model_dump()
    else:
        payload = json.loads(response.model_dump_json())

    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if text:
                return str(text)

    raise ValueError("OpenAI response did not include output text")


def generate_mail(args: argparse.Namespace) -> dict[str, Any]:
    from openai import OpenAI

    template_path = resolve_path(args.template_path)
    if not template_path.exists():
        raise FileNotFoundError(f"Mail template not found: {template_path}")

    template = template_path.read_text(encoding="utf-8")
    facts = {
        "submission_id": args.submission_id,
        "recipient": args.recipient,
        "customer_name": args.customer_name,
        "meter_number": args.meter_number,
        "reading_date": args.reading_date,
        "reading_value": args.reading_value,
        "unit": args.unit,
        "consumption_since_last": args.consumption_since_last,
        "language": args.language,
    }

    prompt = (
        "Generate an email draft using the template and facts below. "
        "Follow the template rules exactly. Return only JSON matching the schema.\n\n"
        f"TEMPLATE:\n{template}\n\n"
        "FACTS:\n"
        f"{json.dumps(facts, ensure_ascii=True, indent=2)}"
    )

    client = OpenAI()
    response = client.responses.create(
        model=args.model,
        input=[
            {
                "role": "user",
                "content": [{"type": "input_text", "text": prompt}],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "customer_mail_draft",
                "strict": True,
                "schema": MAIL_SCHEMA,
            }
        },
    )

    mail = json.loads(extract_response_text(response))
    return {
        "submission_id": args.submission_id,
        "recipient": args.recipient,
        "subject": mail["subject"],
        "body": mail["body"],
        "status": "draft_created",
        "model": args.model,
        "template_path": str(template_path),
    }


def fallback_mail(args: argparse.Namespace, error: Exception) -> dict[str, Any]:
    unit_suffix = f" {args.unit}" if args.unit else ""
    greeting = f"Dear {args.customer_name}," if args.customer_name else "Dear customer,"
    return {
        "submission_id": args.submission_id,
        "recipient": args.recipient,
        "subject": "Meter reading received",
        "body": (
            f"{greeting}\n\n"
            f"Your meter reading for meter {args.meter_number} on {args.reading_date} "
            f"has been received and processed successfully. The recorded reading is "
            f"{args.reading_value}{unit_suffix}.\n\n"
            "Best regards,\nCustomer Service Team"
        ),
        "status": "fallback_draft_created",
        "error": str(error),
    }


def write_or_print(payload: dict[str, Any], output_path: Path) -> None:
    result_json = json.dumps(payload, ensure_ascii=True, indent=2)
    output_path.write_text(result_json, encoding="utf-8")
    print(result_json)


def main() -> int:
    args = parse_args()
    load_env_file(PROJECT_ROOT / ".env")
    output_path = resolve_output_path(args.output_json)

    try:
        payload = generate_mail(args)
        write_or_print(payload, output_path)
        return 0
    except Exception as error:  # pragma: no cover - CLI safety path
        payload = fallback_mail(args, error)
        write_or_print(payload, output_path)
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
