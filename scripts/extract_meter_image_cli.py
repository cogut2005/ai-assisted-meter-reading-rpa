from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")


EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "reading_value": {
            "type": "string",
            "description": "Meter reading digits only, without unit, decimal part, spaces, or separators. Empty string if unreadable.",
        },
        "confidence_score": {
            "type": "integer",
            "minimum": 1,
            "maximum": 10,
            "description": "Confidence score from 1 to 10, where 1 is worst and 10 is best.",
        },
    },
    "required": [
        "reading_value",
        "confidence_score",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract meter reading data from an image using a GPT vision model."
    )
    parser.add_argument("--image-path", required=True, help="Path to the meter image.")
    parser.add_argument(
        "--output-json",
        help="Optional path where the JSON result should be written.",
    )
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


def resolve_output_path(raw_path: str | None) -> Path | None:
    if not raw_path:
        return None

    path = resolve_path(raw_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def image_to_data_url(image_path: Path) -> str:
    if not image_path.exists():
        raise FileNotFoundError(f"Image file not found: {image_path}")
    if not image_path.is_file():
        raise ValueError(f"Image path is not a file: {image_path}")

    mime_type, _ = mimetypes.guess_type(str(image_path))
    if mime_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
        raise ValueError(
            "Unsupported image type. Use jpeg, png, webp, or gif: "
            f"{image_path}"
        )

    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


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


def extract_meter_data(image_path: Path, model: str) -> dict[str, Any]:
    data_url = image_to_data_url(image_path)
    client = OpenAI()

    prompt = (
        "Analyze this utility meter image. Extract the visible meter reading. "
        "Return only the main black meter reading digits, not the red decimal "
        "or fractional wheel, and do not include unit text. If the reading is "
        "unreadable, return an empty reading_value and confidence_score 1. "
        "The confidence_score must be an integer from 1 to 10, where 1 is "
        "worst and 10 is best. This result is only a reviewer aid; a human "
        "will approve it before database insertion."
    )

    response = client.responses.create(
        model=model,
        input=[
            {
                "role": "user",
                "content": [
                    {"type": "input_text", "text": prompt},
                    {"type": "input_image", "image_url": data_url},
                ],
            }
        ],
        text={
            "format": {
                "type": "json_schema",
                "name": "meter_image_extraction",
                "strict": True,
                "schema": EXTRACTION_SCHEMA,
            }
        },
    )

    extraction = json.loads(extract_response_text(response))
    return {
        "reading_value": extraction["reading_value"],
        "confidence_score": extraction["confidence_score"],
    }


def write_or_print(payload: dict[str, Any], output_path: Path | None) -> None:
    result_json = json.dumps(payload, ensure_ascii=True, indent=2)
    if output_path is not None:
        output_path.write_text(result_json, encoding="utf-8")
    print(result_json)


def main() -> int:
    args = parse_args()
    load_env_file(PROJECT_ROOT / ".env")

    image_path = resolve_path(args.image_path)
    output_path = resolve_output_path(args.output_json)

    try:
        payload = extract_meter_data(image_path=image_path, model=args.model)
        write_or_print(payload, output_path)
        return 0
    except Exception as error:  # pragma: no cover - CLI safety path
        payload = {
            "reading_value": "",
            "confidence_score": 1,
            "error": str(error),
        }
        write_or_print(payload, output_path)
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
