"""Selectable-text PDF extraction (Section 19.2)."""

from __future__ import annotations

import io
import re
from dataclasses import dataclass

import pdfplumber

from parsing.fields import looks_like_number

SKIP_NAMES = {
    "test",
    "result",
    "units",
    "unit",
    "reference range",
    "flag",
    "laboratory report",
    "comprehensive metabolic panel",
    "lipid panel",
    "complete blood count",
    "complete blood count cbc",
    "cbc",
    "diabetes panel",
    "metabolic panel",
    "basic metabolic panel",
}

LINE_RE = re.compile(
    r"^(?P<name>.+?)\s+"
    r"(?P<value>(?:[<>]=?\s*)?\d+(?:\.\d+)?)\s+"
    r"(?P<unit>%|[A-Za-zµμ]+(?:/[A-Za-zµμ]+)?)\s+"
    r"(?P<range>(?:[<>≤≥]=?\s*)?\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?)"
    r"(?:\s+(?P<flag>HIGH|LOW|ABNORMAL))?\s*$",
    re.IGNORECASE,
)

PATIENT_RE = re.compile(
    r"\b(?:Patient(?:\s+Name)?|Name):\s*(.+?)(?:\s+Patient ID:|\s+DOB:|\s+Date of Birth:|$)",
    re.I,
)
SEX_RE = re.compile(r"\bSex:\s*([MF])\b", re.I)
DOB_RE = re.compile(
    r"\b(?:DOB|Date of Birth|Birth(?:date)?):\s*"
    r"([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2}|[0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{4})",
    re.I,
)
COLLECTED_RE = re.compile(
    r"\bCollected:\s*([0-9]{4}[-/][0-9]{1,2}[-/][0-9]{1,2})", re.I
)
AGE_RE = re.compile(r"\bAge:\s*(\d{1,3})\b", re.I)


@dataclass(frozen=True)
class RawLabRow:
    test_name: str
    value: str
    unit: str
    reference_range: str
    flag: str = ""


def _open_pdf(file):
    if hasattr(file, "read"):
        data = file.read()
        if hasattr(file, "seek"):
            try:
                file.seek(0)
            except Exception:
                pass
        return pdfplumber.open(io.BytesIO(data))
    if isinstance(file, (bytes, bytearray)):
        return pdfplumber.open(io.BytesIO(file))
    return pdfplumber.open(file)


def extract_text(file) -> str | None:
    """pdfplumber text extraction. None if the text layer is empty."""
    try:
        with _open_pdf(file) as pdf:
            chunks = []
            for page in pdf.pages:
                chunks.append(page.extract_text() or "")
    except Exception:
        return None
    text = "\n".join(chunks).strip()
    compact = re.sub(r"\s+", "", text)
    if len(compact) < 40:
        return None
    return text


def extract_tables(file) -> list[list[list[str | None]]]:
    tables: list[list[list[str | None]]] = []
    try:
        with _open_pdf(file) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    tables.append(table)
    except Exception:
        return []
    return tables


def render_page_images(file, *, resolution: int = 140) -> list[bytes]:
    """Rasterize PDF pages for image-only / scanned files."""
    images: list[bytes] = []
    try:
        with _open_pdf(file) as pdf:
            for page in pdf.pages:
                try:
                    im = page.to_image(resolution=resolution)
                    buf = io.BytesIO()
                    im.original.save(buf, format="PNG")
                    images.append(buf.getvalue())
                except Exception:
                    continue
    except Exception:
        return []
    return images


def parse_patient_meta(text: str) -> dict:
    meta: dict = {
        "patient_name": None,
        "gender": None,
        "dob": None,
        "anchor_age": None,
        "charttime": None,
    }
    if not text:
        return meta
    name = PATIENT_RE.search(text)
    if name:
        meta["patient_name"] = name.group(1).strip()
    sex = SEX_RE.search(text)
    if sex:
        meta["gender"] = sex.group(1).upper()
    dob = DOB_RE.search(text)
    if dob:
        meta["dob"] = dob.group(1)
    collected = COLLECTED_RE.search(text)
    if collected:
        meta["charttime"] = collected.group(1)
    age = AGE_RE.search(text)
    if age:
        meta["anchor_age"] = int(age.group(1))
    return meta


def _clean_cell(value) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value)).strip()


def _is_header_or_title(cells: list[str]) -> bool:
    nonempty = [c for c in cells if c]
    if not nonempty:
        return True
    first = nonempty[0].lower()
    joined = " ".join(nonempty).lower()
    if first in SKIP_NAMES or joined in SKIP_NAMES:
        return True
    if "reference range" in joined and joined.startswith("test"):
        return True
    if looks_like_number(cells[0] if cells else ""):
        return True
    return False


def parse_table_rows(tables: list[list[list[str | None]]]) -> list[RawLabRow]:
    rows: list[RawLabRow] = []
    for table in tables:
        for raw in table:
            cells = [_clean_cell(c) for c in (raw or [])]
            if _is_header_or_title(cells):
                continue
            if len(cells) < 3 or not cells[0] or not looks_like_number(cells[1]):
                continue
            name = cells[0]
            value = cells[1]
            unit = cells[2] if len(cells) > 2 else ""
            ref = cells[3] if len(cells) > 3 else ""
            flag = cells[4] if len(cells) > 4 else ""
            if name.lower() in SKIP_NAMES:
                continue
            rows.append(
                RawLabRow(
                    test_name=name,
                    value=value,
                    unit=unit,
                    reference_range=ref,
                    flag=flag,
                )
            )
    return rows


def parse_lines(text: str) -> list[RawLabRow]:
    """Regex line parser producing raw (name, value, unit, range) rows."""
    rows: list[RawLabRow] = []
    if not text:
        return rows
    for line in text.splitlines():
        line = re.sub(r"\s+", " ", line).strip()
        if not line or len(line) > 180:
            continue
        match = LINE_RE.match(line)
        if not match:
            continue
        name = match.group("name").strip()
        if name.lower() in SKIP_NAMES:
            continue
        if not any(ch.isalpha() for ch in name):
            continue
        rows.append(
            RawLabRow(
                test_name=name,
                value=match.group("value").strip(),
                unit=match.group("unit").strip(),
                reference_range=match.group("range").strip(),
                flag=(match.group("flag") or "").strip(),
            )
        )
    return rows
