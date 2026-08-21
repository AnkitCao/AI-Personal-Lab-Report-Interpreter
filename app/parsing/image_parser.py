"""Read lab rows from PNG / JPG using the configured OpenAI vision model.

Status is still computed locally from extracted numbers. The model is only
asked to transcribe what is visible on the page.
"""

from __future__ import annotations

import base64
import json
from typing import Any

from parsing.pdf_parser import RawLabRow, parse_patient_meta

EXTRACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "patient_name": {"type": ["string", "null"]},
        "sex": {"type": ["string", "null"]},
        "dob": {"type": ["string", "null"]},
        "age": {"type": ["integer", "null"]},
        "collected": {"type": ["string", "null"]},
        "full_text": {"type": "string"},
        "rows": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "test_name": {"type": "string"},
                    "value": {"type": "string"},
                    "unit": {"type": "string"},
                    "reference_range": {"type": "string"},
                    "flag": {"type": "string"},
                },
                "required": [
                    "test_name",
                    "value",
                    "unit",
                    "reference_range",
                    "flag",
                ],
            },
        },
    },
    "required": [
        "patient_name",
        "sex",
        "dob",
        "age",
        "collected",
        "full_text",
        "rows",
    ],
}

EXTRACT_PROMPT = """\
Transcribe a laboratory report from the image(s).

Read the header first: patient name, sex/gender, date of birth (DOB),
age if printed, and collection date. Copy them exactly.

Then transcribe each lab row: test name, numeric result, unit, reference
range as printed (for example "70 - 99" or "< 200"), and flag if printed
(HIGH/LOW/empty).

Return only values you can actually read. Do not invent tests, numbers,
units, names, or dates. If a field is missing, use an empty string
(or null for patient fields).
"""


def _data_url(image_bytes: bytes, mime: str) -> str:
    b64 = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _mime_for_name(filename: str) -> str:
    lower = (filename or "").lower()
    if lower.endswith(".png"):
        return "image/png"
    if lower.endswith(".jpg") or lower.endswith(".jpeg"):
        return "image/jpeg"
    if lower.endswith(".webp"):
        return "image/webp"
    return "image/png"


def extract_from_images(
    images: list[bytes],
    *,
    filename: str = "report.png",
) -> tuple[list[RawLabRow], dict]:
    """Return (raw rows, patient meta). Raises RuntimeError on failure."""
    if not images:
        raise RuntimeError("No image data was provided.")

    from config import ConfigError, get_openai_settings
    from openai import OpenAI

    try:
        api_key, model = get_openai_settings()
    except ConfigError as exc:
        raise RuntimeError(str(exc)) from None

    content: list[dict[str, Any]] = [{"type": "text", "text": EXTRACT_PROMPT}]
    mime = _mime_for_name(filename)
    for image in images[:4]:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": _data_url(image, mime)},
            }
        )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": content}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "lab_report_extract",
                "strict": True,
                "schema": EXTRACT_SCHEMA,
            },
        },
        temperature=0,
        timeout=90.0,
    )
    raw = response.choices[0].message.content
    if not raw:
        raise RuntimeError("The image reader returned an empty result.")
    parsed = json.loads(raw)
    rows = [
        RawLabRow(
            test_name=str(item.get("test_name") or "").strip(),
            value=str(item.get("value") or "").strip(),
            unit=str(item.get("unit") or "").strip(),
            reference_range=str(item.get("reference_range") or "").strip(),
            flag=str(item.get("flag") or "").strip(),
        )
        for item in parsed.get("rows") or []
        if str(item.get("test_name") or "").strip()
    ]
    meta = parse_patient_meta(str(parsed.get("full_text") or ""))
    if parsed.get("patient_name"):
        meta["patient_name"] = str(parsed["patient_name"]).strip()
    if parsed.get("sex"):
        meta["gender"] = str(parsed["sex"]).strip()[:1].upper()
    if parsed.get("dob"):
        meta["dob"] = str(parsed["dob"]).strip()
    if parsed.get("age") is not None:
        try:
            meta["anchor_age"] = int(parsed["age"])
        except (TypeError, ValueError):
            pass
    if parsed.get("collected"):
        meta["charttime"] = str(parsed["collected"]).strip()
    return rows, meta
