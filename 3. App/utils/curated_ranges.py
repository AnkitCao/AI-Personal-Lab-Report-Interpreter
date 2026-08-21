"""Fallback reference ranges when MIMIC left them blank.

Only used when both ref_range_lower and ref_range_upper are missing.
Published adult thresholds (not invented per-row):

- Cholesterol Ratio (Total/HDL): desirable below 5; ideal often cited near 3.5
  (Healthline; Medical News Today; UMass Memorial Health library).
- HDL Cholesterol: matches the range MIMIC already stores on non-blank HDL
  rows in this sample (41–999 mg/dL).
"""

from __future__ import annotations

# test_name -> (ref_range_lower, ref_range_upper); None = open-ended side
FALLBACK_RANGES: dict[str, tuple[float | None, float | None]] = {
    "Cholesterol Ratio (Total/HDL)": (None, 5.0),
    "HDL Cholesterol": (41.0, 999.0),
}


def fill_reference_range(
    test_name: str | None,
    ref_low: float | None,
    ref_high: float | None,
) -> tuple[float | None, float | None]:
    """Keep source ranges when present; otherwise apply a curated fallback."""
    if ref_low is not None or ref_high is not None:
        return ref_low, ref_high
    if not test_name:
        return None, None
    return FALLBACK_RANGES.get(str(test_name), (None, None))
