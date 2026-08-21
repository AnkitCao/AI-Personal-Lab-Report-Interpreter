"""Shared field parsers for uploaded lab rows."""

from __future__ import annotations

import re
from datetime import date

NUMBER_RE = re.compile(r"[-+]?\d+(?:\.\d+)?")


def parse_number(raw) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw).strip().replace(",", "")
    if not text or text in {".", "-", "—", "na", "n/a", "none"}:
        return None
    match = NUMBER_RE.search(text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def parse_reference_range(raw) -> tuple[float | None, float | None]:
    """Parse '70 - 99', '< 200', '> 40', '≤ 5.7', or separate low/high cells."""
    if raw is None:
        return None, None
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return None, float(raw)
    text = str(raw).strip()
    if not text or text in {"—", "-", ".", "n/a", "na", "none"}:
        return None, None
    text = (
        text.replace("–", "-")
        .replace("—", "-")
        .replace("≤", "<=")
        .replace("≥", ">=")
        .replace("to", "-")
    )
    text = re.sub(r"\s+", " ", text).strip()
    one_sided = re.match(
        r"^(<=|<|>=|>)\s*([-+]?\d+(?:\.\d+)?)\s*$", text
    )
    if one_sided:
        op, num = one_sided.group(1), float(one_sided.group(2))
        if op in {"<", "<="}:
            return None, num
        return num, None
    span = re.match(
        r"^([-+]?\d+(?:\.\d+)?)\s*-\s*([-+]?\d+(?:\.\d+)?)\s*$",
        text,
    )
    if span:
        return float(span.group(1)), float(span.group(2))
    lone = parse_number(text)
    if lone is not None and re.fullmatch(r"[-+]?\d+(?:\.\d+)?", text):
        return None, None
    return None, None


def looks_like_number(raw) -> bool:
    """True only when the whole cell is a numeric result, not a name like A1c."""
    if raw is None:
        return False
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return True
    text = str(raw).strip().replace(",", "")
    return bool(re.fullmatch(r"(?:[<>]=?)?\s*[-+]?\d+(?:\.\d+)?", text))


def parse_dob_date(raw: str | None) -> date | None:
    if not raw:
        return None
    text = str(raw).strip()
    match = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", text)
    if match:
        year, month, day = (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
    else:
        match = re.search(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", text)
        if not match:
            return None
        month, day, year = (
            int(match.group(1)),
            int(match.group(2)),
            int(match.group(3)),
        )
    try:
        return date(year, month, day)
    except ValueError:
        return None


def normalize_dob(raw: str | None) -> str | None:
    born = parse_dob_date(raw)
    if born is not None:
        return born.isoformat()
    text = str(raw).strip() if raw else ""
    return text or None


def age_from_dob(raw: str | None, as_of: date | None = None) -> int | None:
    born = parse_dob_date(raw)
    if born is None:
        return None
    today = as_of or date.today()
    years = today.year - born.year - (
        (today.month, today.day) < (born.month, born.day)
    )
    if years < 0 or years > 120:
        return None
    return years
