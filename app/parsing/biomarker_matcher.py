"""Map extracted test names onto the curated 20-biomarker set (Section 19.4)."""

from __future__ import annotations

import re

# Canonical names and panels currently in app_lab_results (Section 9).
CURATED = {
    "Glucose": "METABOLIC",
    "Potassium": "METABOLIC",
    "Sodium": "METABOLIC",
    "Creatinine": "METABOLIC",
    "Urea Nitrogen": "METABOLIC",
    "Total Calcium": "METABOLIC",
    "Albumin": "METABOLIC",
    "Total Bilirubin": "METABOLIC",
    "Hematocrit": "CBC",
    "Platelet Count": "CBC",
    "Hemoglobin": "CBC",
    "Red Blood Cells": "CBC",
    "White Blood Cells": "CBC",
    "Triglycerides": "LIPID",
    "Total Cholesterol": "LIPID",
    "HDL Cholesterol": "LIPID",
    "Cholesterol Ratio (Total/HDL)": "LIPID",
    "LDL Cholesterol - Calculated": "LIPID",
    "LDL Cholesterol - Measured": "LIPID",
    "Hemoglobin A1c": "A1C",
}

_EXTRA_ALIASES = {
    "bun": "Urea Nitrogen",
    "urea nitrogen bun": "Urea Nitrogen",
    "blood urea nitrogen": "Urea Nitrogen",
    "urea": "Urea Nitrogen",
    "calcium": "Total Calcium",
    "calcium total": "Total Calcium",
    "ca": "Total Calcium",
    "bilirubin": "Total Bilirubin",
    "bilirubin total": "Total Bilirubin",
    "tbil": "Total Bilirubin",
    "hba1c": "Hemoglobin A1c",
    "hb a1c": "Hemoglobin A1c",
    "a1c": "Hemoglobin A1c",
    "glycated hemoglobin": "Hemoglobin A1c",
    "glycohemoglobin": "Hemoglobin A1c",
    "hemoglobin a1c": "Hemoglobin A1c",
    "hdl": "HDL Cholesterol",
    "cholesterol hdl": "HDL Cholesterol",
    "ldl calculated": "LDL Cholesterol - Calculated",
    "ldl cholesterol calculated": "LDL Cholesterol - Calculated",
    "cholesterol ldl calculated": "LDL Cholesterol - Calculated",
    "ldl": "LDL Cholesterol - Calculated",
    "ldl cholesterol": "LDL Cholesterol - Calculated",
    "ldl measured": "LDL Cholesterol - Measured",
    "ldl cholesterol measured": "LDL Cholesterol - Measured",
    "cholesterol ldl measured": "LDL Cholesterol - Measured",
    "cholesterol total": "Total Cholesterol",
    "cholesterol": "Total Cholesterol",
    "chol": "Total Cholesterol",
    "trig": "Triglycerides",
    "trigs": "Triglycerides",
    "tg": "Triglycerides",
    "cholesterol ratio": "Cholesterol Ratio (Total/HDL)",
    "chol hdl ratio": "Cholesterol Ratio (Total/HDL)",
    "total hdl ratio": "Cholesterol Ratio (Total/HDL)",
    "wbc": "White Blood Cells",
    "white cell count": "White Blood Cells",
    "leukocytes": "White Blood Cells",
    "rbc": "Red Blood Cells",
    "erythrocytes": "Red Blood Cells",
    "hgb": "Hemoglobin",
    "hb": "Hemoglobin",
    "hct": "Hematocrit",
    "plt": "Platelet Count",
    "platelets": "Platelet Count",
    "platelet": "Platelet Count",
    "k": "Potassium",
    "na": "Sodium",
    "creat": "Creatinine",
    "cr": "Creatinine",
    "glu": "Glucose",
    "blood glucose": "Glucose",
    "alb": "Albumin",
}


def normalize_name(raw_name: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    text = str(raw_name or "").lower()
    text = text.replace("total/hdl", "total hdl")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _alias_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for canonical in CURATED:
        mapping[normalize_name(canonical)] = canonical
    mapping.update(_EXTRA_ALIASES)
    return mapping


_ALIAS_MAP = _alias_map()


def match_to_dictionary(
    raw_name: str,
) -> tuple[str | None, str | None, str]:
    """Return (canonical_name, lab_group, knowledge_source).

    Unmatched names keep knowledge_source = 'LLM General Knowledge'.
    """
    key = normalize_name(raw_name)
    if not key:
        return None, None, "LLM General Knowledge"
    canonical = _ALIAS_MAP.get(key)
    if canonical is None and key.endswith(" calculated"):
        canonical = _ALIAS_MAP.get(key[: -len(" calculated")])
    if canonical is None:
        return None, None, "LLM General Knowledge"
    return canonical, CURATED[canonical], "Curated Database"
