"""CSV lab-report loading and column mapping (Section 19.3)."""

from __future__ import annotations

import csv
import io

import pandas as pd

from parsing.fields import normalize_dob
from parsing.pdf_parser import RawLabRow, parse_patient_meta

TEST_ALIASES = {
    "test",
    "test_name",
    "test name",
    "analyte",
    "name",
    "biomarker",
    "item",
    "lab",
    "lab test",
    "label",
    "mimic_test_name",
}
VALUE_ALIASES = {
    "result",
    "value",
    "valuenum",
    "value_num",
    "value num",
    "result value",
    "numeric result",
    "numeric_value",
    "numeric value",
}
UNIT_ALIASES = {"unit", "units", "uom", "value_unit", "valueuom"}
RANGE_ALIASES = {
    "reference range",
    "ref range",
    "range",
    "reference",
    "ref_range",
    "reference_range",
    "ref",
}
LOW_ALIASES = {
    "ref_range_lower",
    "low",
    "lower",
    "ref low",
    "range low",
    "lower limit",
}
HIGH_ALIASES = {
    "ref_range_upper",
    "high",
    "upper",
    "ref high",
    "range high",
    "upper limit",
}
FLAG_ALIASES = {"flag", "status", "mimic_flag"}
PATIENT_NAME_ALIASES = {
    "patient",
    "patient name",
    "patientname",
    "full name",
    "fullname",
    "subject name",
}
DOB_ALIASES = {
    "dob",
    "date of birth",
    "birth date",
    "birthday",
    "birthdate",
}
SEX_ALIASES = {"sex", "gender"}
AGE_ALIASES = {"age", "anchor age", "anchor_age"}
COLLECTED_ALIASES = {
    "collected",
    "collected at",
    "collection date",
    "charttime",
    "draw date",
}
PATIENT_META_ALIASES = (
    PATIENT_NAME_ALIASES
    | DOB_ALIASES
    | SEX_ALIASES
    | AGE_ALIASES
    | COLLECTED_ALIASES
)

ROLES = ("test_name", "value", "unit", "reference_range", "range_low", "range_high", "flag")
NONE_LABEL = "(not in this file)"


def _decode_csv_bytes(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _cells_from_line(line: str) -> list[str]:
    try:
        return next(csv.reader([line]))
    except Exception:
        return [line]


def _row_looks_like_header(cells: list[str]) -> bool:
    norms = {_norm_header(c) for c in cells if str(c).strip()}
    has_test = bool(norms & TEST_ALIASES) or any("test" in n for n in norms)
    has_value = bool(norms & VALUE_ALIASES)
    return has_test and has_value and len(norms) >= 2


def _find_header_index(text: str) -> int:
    for index, line in enumerate(text.splitlines()[:40]):
        if _row_looks_like_header(_cells_from_line(line)):
            return index
    return 0


def load_csv(file) -> pd.DataFrame:
    """pandas read with basic type coercion."""
    if hasattr(file, "read"):
        data = file.read()
        if hasattr(file, "seek"):
            try:
                file.seek(0)
            except Exception:
                pass
    elif isinstance(file, (bytes, bytearray)):
        data = bytes(file)
    else:
        return pd.read_csv(file)

    text = _decode_csv_bytes(bytes(data))
    header_idx = _find_header_index(text)
    last_error: Exception | None = None
    for kwargs in (
        {},
        {"sep": None, "engine": "python"},
    ):
        try:
            df = pd.read_csv(io.StringIO(text), skiprows=header_idx, **kwargs)
            if df.shape[1] >= 2:
                return df
        except Exception as exc:
            last_error = exc
            continue
    if last_error:
        raise last_error
    return pd.read_csv(io.StringIO(text), skiprows=header_idx)


def _norm_header(name: str) -> str:
    return " ".join(str(name).strip().lower().replace("_", " ").split())


def guess_column_mapping(df: pd.DataFrame) -> dict[str, str | None]:
    headers = {col: _norm_header(col) for col in df.columns}
    mapping: dict[str, str | None] = {role: None for role in ROLES}

    def pick(aliases: set[str], role: str) -> None:
        if mapping[role]:
            return
        for col, norm in headers.items():
            if role == "test_name" and norm in PATIENT_META_ALIASES:
                continue
            if norm in aliases and col not in mapping.values():
                mapping[role] = col
                return

    pick(TEST_ALIASES, "test_name")
    pick(VALUE_ALIASES, "value")
    pick(UNIT_ALIASES, "unit")
    pick(RANGE_ALIASES, "reference_range")
    pick(LOW_ALIASES, "range_low")
    pick(HIGH_ALIASES, "range_high")
    pick(FLAG_ALIASES, "flag")
    return mapping


def mapping_is_complete(mapping: dict[str, str | None]) -> bool:
    return bool(mapping.get("test_name") and mapping.get("value"))


def apply_column_mapping(
    df: pd.DataFrame, mapping: dict[str, str | None]
) -> list[RawLabRow]:
    """Apply the user's column-mapping choices from the UI step."""
    rows: list[RawLabRow] = []
    test_col = mapping.get("test_name")
    value_col = mapping.get("value")
    if not test_col or not value_col:
        return rows
    unit_col = mapping.get("unit")
    range_col = mapping.get("reference_range")
    low_col = mapping.get("range_low")
    high_col = mapping.get("range_high")
    flag_col = mapping.get("flag")

    for _, row in df.iterrows():
        name = "" if pd.isna(row.get(test_col)) else str(row.get(test_col)).strip()
        if not name or name.lower() in {"nan", "none", "test"}:
            continue
        value = "" if pd.isna(row.get(value_col)) else str(row.get(value_col)).strip()
        unit = ""
        if unit_col and unit_col in row.index and pd.notna(row.get(unit_col)):
            unit = str(row.get(unit_col)).strip()
        ref = ""
        if range_col and range_col in row.index and pd.notna(row.get(range_col)):
            ref = str(row.get(range_col)).strip()
        elif low_col or high_col:
            low = (
                ""
                if not low_col or pd.isna(row.get(low_col))
                else str(row.get(low_col)).strip()
            )
            high = (
                ""
                if not high_col or pd.isna(row.get(high_col))
                else str(row.get(high_col)).strip()
            )
            if low and high:
                ref = f"{low} - {high}"
            elif high:
                ref = f"< {high}"
            elif low:
                ref = f"> {low}"
        flag = ""
        if flag_col and flag_col in row.index and pd.notna(row.get(flag_col)):
            flag = str(row.get(flag_col)).strip()
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


def _clean_meta_value(raw) -> str | None:
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    text = str(raw).strip()
    if not text or text.lower() in {"nan", "none", "null", "—", "-"}:
        return None
    return text


def _first_column_value(
    df: pd.DataFrame, aliases: set[str], skip_cols: set[str]
) -> str | None:
    for col in df.columns:
        if col in skip_cols:
            continue
        if _norm_header(col) not in aliases:
            continue
        for value in df[col].tolist():
            cleaned = _clean_meta_value(value)
            if cleaned:
                return cleaned
    return None


def _norm_sex(raw: str | None) -> str | None:
    if not raw:
        return None
    text = raw.strip().lower()
    if text in {"f", "female", "woman", "w"}:
        return "F"
    if text in {"m", "male", "man"}:
        return "M"
    if text[:1] in {"f", "m"}:
        return text[:1].upper()
    return raw.strip()


def _meta_from_preamble(text: str) -> dict:
    meta = parse_patient_meta(text or "")
    header_idx = _find_header_index(text or "")
    for line in (text or "").splitlines()[:header_idx]:
        cells = [c.strip() for c in _cells_from_line(line) if str(c).strip()]
        if len(cells) != 2:
            continue
        key = _norm_header(cells[0])
        value = _clean_meta_value(cells[1])
        if not value:
            continue
        if key in PATIENT_NAME_ALIASES or key == "name":
            meta["patient_name"] = value
        elif key in DOB_ALIASES:
            meta["dob"] = normalize_dob(value)
        elif key in SEX_ALIASES:
            meta["gender"] = _norm_sex(value)
        elif key in AGE_ALIASES:
            try:
                meta["anchor_age"] = int(float(value))
            except ValueError:
                pass
        elif key in COLLECTED_ALIASES:
            meta["charttime"] = value
    return meta


def extract_patient_meta(
    df: pd.DataFrame,
    mapping: dict[str, str | None] | None = None,
    raw: bytes | str | None = None,
) -> dict:
    """Read name / DOB / sex / age from CSV columns, preamble rows, or header text."""
    skip_cols = {col for col in (mapping or {}).values() if col}
    text = raw if isinstance(raw, str) else _decode_csv_bytes(bytes(raw or b""))
    meta = _meta_from_preamble(text)

    name_aliases = set(PATIENT_NAME_ALIASES)
    test_col = (mapping or {}).get("test_name")
    if not test_col or _norm_header(test_col) != "name":
        name_aliases.add("name")

    name = _first_column_value(df, name_aliases, skip_cols)
    dob = _first_column_value(df, DOB_ALIASES, skip_cols)
    sex = _first_column_value(df, SEX_ALIASES, skip_cols)
    age = _first_column_value(df, AGE_ALIASES, skip_cols)
    collected = _first_column_value(df, COLLECTED_ALIASES, skip_cols)

    if name:
        meta["patient_name"] = name
    if dob:
        meta["dob"] = normalize_dob(dob)
    elif meta.get("dob"):
        meta["dob"] = normalize_dob(str(meta["dob"]))
    if sex:
        meta["gender"] = _norm_sex(sex)
    if age:
        try:
            meta["anchor_age"] = int(float(age))
        except ValueError:
            pass
    if collected:
        meta["charttime"] = collected
    return meta
