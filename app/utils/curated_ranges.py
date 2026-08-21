"""Fallback reference ranges when MIMIC left them blank.

Only used when both ref_range_lower and ref_range_upper are missing.
Published adult thresholds (not invented per-row). Values are general
adult ranges, not split by sex. Where a source only publishes separate
male/female ranges, the two are combined into one span (lowest lower
bound to highest upper bound) from that same source, noted below.

- Cholesterol Ratio (Total/HDL): desirable below 5; ideal often cited near 3.5
  (Healthline; Medical News Today; UMass Memorial Health library).
- HDL Cholesterol: matches the range MIMIC already stores on non-blank HDL
  rows in this sample (41–999 mg/dL).
- Glucose, Total Calcium, Sodium, Potassium, Urea Nitrogen (BUN),
  Creatinine, Albumin, Total Bilirubin: MedlinePlus Medical Encyclopedia,
  "Comprehensive metabolic panel" (medlineplus.gov/ency/article/003468.htm).
  Creatinine on that page is already a single unisex range.
- Hematocrit, Hemoglobin, Red Blood Cells, White Blood Cells,
  Platelet Count: Cleveland Clinic, "Complete Blood Count (CBC)"
  (my.clevelandclinic.org/health/diagnostics/4053-complete-blood-count).
  Hematocrit/Hemoglobin/RBC are published there as separate
  female/male ranges; combined here into one span. WBC and platelet
  count are published there as single unisex ranges already.
- Triglycerides, Total Cholesterol, LDL Cholesterol (Calculated and
  Measured -- same clinical value, two lab methods): MedlinePlus,
  "Cholesterol Levels: What You Need To Know"
  (medlineplus.gov/cholesterollevelswhatyouneedtoknow.html). Desirable
  upper bounds only; lower side left open-ended, same convention as
  the Cholesterol Ratio row above.
- Hemoglobin A1c: MedlinePlus Medical Encyclopedia, "A1C test"
  (medlineplus.gov/ency/article/003640.htm) -- below 5.7% is normal.
"""

from __future__ import annotations

# test_name -> (ref_range_lower, ref_range_upper); None = open-ended side
FALLBACK_RANGES: dict[str, tuple[float | None, float | None]] = {
    "Cholesterol Ratio (Total/HDL)": (None, 5.0),
    "HDL Cholesterol": (41.0, 999.0),
    "Glucose": (70.0, 100.0),
    "Potassium": (3.7, 5.2),
    "Sodium": (135.0, 145.0),
    "Creatinine": (0.6, 1.3),
    "Urea Nitrogen": (6.0, 20.0),
    "Total Calcium": (8.5, 10.2),
    "Albumin": (3.4, 5.4),
    "Total Bilirubin": (0.1, 1.2),
    "Hematocrit": (36.0, 55.0),
    "Platelet Count": (150.0, 400.0),
    "Hemoglobin": (11.5, 17.0),
    "Red Blood Cells": (4.0, 6.1),
    "White Blood Cells": (4.0, 10.0),
    "Triglycerides": (None, 150.0),
    "Total Cholesterol": (None, 200.0),
    "LDL Cholesterol - Calculated": (None, 100.0),
    "LDL Cholesterol - Measured": (None, 100.0),
    "Hemoglobin A1c": (None, 5.7),
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
