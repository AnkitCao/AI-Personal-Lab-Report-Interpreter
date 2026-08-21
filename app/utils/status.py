"""Deterministic HIGH / LOW / NORMAL rules (Section 19.5).

Mirrors the SQL CASE in 1. Data Extraction/build_database.py so uploaded
rows never touch SQLite but still get identical status labels.
"""

from __future__ import annotations

from utils.curated_ranges import fill_reference_range


def compute_status(
    value_num: float | None,
    ref_low: float | None,
    ref_high: float | None,
    flag: str | None = None,
    *,
    test_name: str | None = None,
) -> str:
    """Return HIGH / LOW / NORMAL / ABNORMAL / UNKNOWN.

    Boundary rule: value equal to a bound is NORMAL (SQL uses ``<`` and ``>``,
    not ``<=`` / ``>=``). When both bounds are missing, a curated fallback
    range may be filled from ``test_name`` (see utils/curated_ranges.py).
    """
    ref_low, ref_high = fill_reference_range(test_name, ref_low, ref_high)
    if value_num is None:
        return "UNKNOWN"
    if ref_low is not None and value_num < ref_low:
        return "LOW"
    if ref_high is not None and value_num > ref_high:
        return "HIGH"
    if ref_low is not None or ref_high is not None:
        return "NORMAL"
    if str(flag or "").strip().lower() == "abnormal":
        return "ABNORMAL"
    return "UNKNOWN"
