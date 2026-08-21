"""Turn an uploaded file into app_lab_results-shaped rows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import pandas as pd

from parsing.biomarker_matcher import match_to_dictionary
from parsing.csv_parser import (
    apply_column_mapping,
    extract_patient_meta,
    guess_column_mapping,
    load_csv,
    mapping_is_complete,
)
from parsing.fields import age_from_dob, normalize_dob, parse_number, parse_reference_range
from parsing.pdf_parser import (
    RawLabRow,
    extract_tables,
    extract_text,
    parse_lines,
    parse_patient_meta,
    parse_table_rows,
    render_page_images,
)
from utils.curated_ranges import fill_reference_range
from utils.status import compute_status

TEXT_PDF_MIN_ROWS = 3
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
CSV_EXTS = {".csv"}
PDF_EXTS = {".pdf"}


@dataclass
class ParseOutcome:
    ok: bool
    error: str | None = None
    needs_mapping: bool = False
    csv_df: pd.DataFrame | None = None
    csv_mapping: dict[str, str | None] = field(default_factory=dict)
    labs: pd.DataFrame | None = None
    meta: dict | None = None
    unmatched_count: int = 0
    source_kind: str = ""
    filename: str = ""


def _dedupe_rows(rows: list[RawLabRow]) -> list[RawLabRow]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[RawLabRow] = []
    for row in rows:
        key = (row.test_name.lower(), row.value, row.unit.lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def labs_from_raw_rows(
    rows: list[RawLabRow],
    *,
    patient_meta: dict | None = None,
    filename: str = "",
) -> tuple[pd.DataFrame, dict]:
    patient_meta = patient_meta or {}
    dob = normalize_dob(patient_meta.get("dob"))
    if dob:
        patient_meta = {**patient_meta, "dob": dob}
    charttime = patient_meta.get("charttime") or datetime.now().isoformat(
        timespec="seconds"
    )
    gender = patient_meta.get("gender")
    age = patient_meta.get("anchor_age")
    if age is None:
        age = age_from_dob(dob)

    records = []
    unmatched = 0
    for index, raw in enumerate(_dedupe_rows(rows), start=1):
        canonical, group, source = match_to_dictionary(raw.test_name)
        if canonical is None:
            unmatched += 1
            test_name = raw.test_name.strip()
            lab_group = "UNMATCHED"
        else:
            test_name = canonical
            lab_group = group or "UNMATCHED"
        value_num = parse_number(raw.value)
        low, high = parse_reference_range(raw.reference_range)
        low, high = fill_reference_range(test_name, low, high)
        status = compute_status(
            value_num, low, high, raw.flag, test_name=test_name
        )
        records.append(
            {
                "subject_id": 0,
                "hadm_id": 0,
                "gender": gender,
                "anchor_age": age,
                "anchor_year": None,
                "charttime": charttime,
                "itemid": index,
                "mimic_test_name": raw.test_name,
                "test_name": test_name,
                "lab_group": lab_group,
                "value_text": str(raw.value).strip(),
                "value_num": value_num,
                "value_unit": raw.unit.strip() or None,
                "ref_range_lower": low,
                "ref_range_upper": high,
                "mimic_flag": raw.flag or None,
                "status": status,
                "knowledge_source": source,
            }
        )

    labs = pd.DataFrame.from_records(records)
    if labs.empty:
        labs = pd.DataFrame(
            columns=[
                "subject_id",
                "hadm_id",
                "gender",
                "anchor_age",
                "anchor_year",
                "charttime",
                "itemid",
                "mimic_test_name",
                "test_name",
                "lab_group",
                "value_text",
                "value_num",
                "value_unit",
                "ref_range_lower",
                "ref_range_upper",
                "mimic_flag",
                "status",
                "knowledge_source",
            ]
        )

    groups = set(labs["lab_group"].dropna().astype(str)) if not labs.empty else set()
    abnormal = (
        int(labs["status"].isin(["HIGH", "LOW", "ABNORMAL"]).sum())
        if not labs.empty
        else 0
    )
    meta = {
        "subject_id": 0,
        "hadm_id": 0,
        "gender": gender or "—",
        "anchor_age": age if age is not None else "—",
        "first_lab_time": charttime,
        "last_lab_time": charttime,
        "lab_record_count": int(len(labs)),
        "biomarker_count": int(labs["test_name"].nunique()) if not labs.empty else 0,
        "abnormal_result_count": abnormal,
        "has_cbc": int("CBC" in groups),
        "has_metabolic": int("METABOLIC" in groups),
        "has_lipid": int("LIPID" in groups),
        "has_a1c": int("A1C" in groups),
        "patient_name": patient_meta.get("patient_name"),
        "dob": patient_meta.get("dob"),
        "filename": filename,
        "unmatched_count": unmatched,
    }
    return labs, meta


def _pdf_rows(data: bytes) -> tuple[list[RawLabRow], dict, str | None]:
    text = extract_text(data)
    tables = extract_tables(data)
    table_rows = parse_table_rows(tables)
    line_rows = parse_lines(text or "")
    rows = table_rows if len(table_rows) >= len(line_rows) else line_rows
    if len(table_rows) >= TEXT_PDF_MIN_ROWS and len(line_rows) >= TEXT_PDF_MIN_ROWS:
        rows = table_rows
        extras = [
            row
            for row in line_rows
            if row.test_name.lower()
            not in {r.test_name.lower() for r in table_rows}
        ]
        rows = table_rows + extras
    meta = parse_patient_meta(text or "")
    if len(rows) >= TEXT_PDF_MIN_ROWS:
        return rows, meta, None
    if text is None:
        return [], meta, "empty_text"
    return rows, meta, "few_rows"


def _vision_rows(
    images: list[bytes], filename: str
) -> tuple[list[RawLabRow], dict]:
    from parsing.image_parser import extract_from_images

    return extract_from_images(images, filename=filename)


def parse_report(
    filename: str,
    data: bytes,
    *,
    csv_mapping: dict[str, str | None] | None = None,
    allow_vision: bool = True,
) -> ParseOutcome:
    """Parse PDF / CSV / PNG / JPG bytes into lab rows."""
    name = filename or "upload"
    ext = Path(name).suffix.lower()
    outcome = ParseOutcome(ok=False, filename=name, source_kind=ext.lstrip("."))

    try:
        if ext in CSV_EXTS:
            df = load_csv(data)
            mapping = csv_mapping or guess_column_mapping(df)
            outcome.csv_df = df
            outcome.csv_mapping = mapping
            if not mapping_is_complete(mapping):
                outcome.needs_mapping = True
                outcome.error = (
                    "This CSV needs a column match: choose which column is "
                    "the test name and which column is the result."
                )
                return outcome
            rows = apply_column_mapping(df, mapping)
            if not rows:
                outcome.error = (
                    "No lab rows were found after applying the column mapping."
                )
                return outcome
            patient_meta = extract_patient_meta(df, mapping, data)
            labs, meta = labs_from_raw_rows(
                rows, patient_meta=patient_meta, filename=name
            )
            outcome.ok = True
            outcome.labs = labs
            outcome.meta = meta
            outcome.unmatched_count = int(meta["unmatched_count"])
            return outcome

        if ext in PDF_EXTS:
            rows, patient_meta, reason = _pdf_rows(data)
            if len(rows) >= TEXT_PDF_MIN_ROWS:
                labs, meta = labs_from_raw_rows(
                    rows, patient_meta=patient_meta, filename=name
                )
                outcome.ok = True
                outcome.labs = labs
                outcome.meta = meta
                outcome.unmatched_count = int(meta["unmatched_count"])
                outcome.source_kind = "pdf"
                return outcome
            if not allow_vision:
                outcome.error = (
                    "We can't read this PDF's text layer. Try a selectable-text "
                    "PDF or a CSV export."
                )
                return outcome
            images = render_page_images(data)
            if not images:
                if reason == "empty_text":
                    outcome.error = (
                        "We can't read this yet — the PDF has no selectable "
                        "text (scanned or photo). OCR for image-only PDFs "
                        "needs page images; try a CSV instead."
                    )
                else:
                    outcome.error = (
                        "No lab rows were found in this PDF. Try a CSV with "
                        "columns for test name, result, unit, and range."
                    )
                return outcome
            try:
                vis_rows, vis_meta = _vision_rows(images, name)
            except RuntimeError as exc:
                outcome.error = str(exc)
                return outcome
            except Exception:
                outcome.error = (
                    "We can't read this PDF yet. Try a selectable-text PDF "
                    "or a CSV export."
                )
                return outcome
            patient_meta = {**patient_meta, **{k: v for k, v in vis_meta.items() if v}}
            rows = vis_rows or rows
            if not rows:
                outcome.error = (
                    "We can't read this yet — OCR is on the roadmap, try CSV "
                    "instead."
                )
                return outcome
            labs, meta = labs_from_raw_rows(
                rows, patient_meta=patient_meta, filename=name
            )
            outcome.ok = True
            outcome.labs = labs
            outcome.meta = meta
            outcome.unmatched_count = int(meta["unmatched_count"])
            outcome.source_kind = "pdf-image"
            return outcome

        if ext in IMAGE_EXTS:
            if not allow_vision:
                outcome.error = (
                    "Photos of lab reports need an OpenAI key to read, or "
                    "upload a selectable-text PDF / CSV instead."
                )
                return outcome
            try:
                rows, patient_meta = _vision_rows([data], name)
            except RuntimeError as exc:
                outcome.error = str(exc)
                return outcome
            except Exception:
                outcome.error = (
                    "We couldn't read this image. Try a clearer photo, a "
                    "selectable-text PDF, or a CSV."
                )
                return outcome
            if not rows:
                outcome.error = (
                    "No lab rows were visible in this image. Try a CSV or a "
                    "selectable-text PDF."
                )
                return outcome
            labs, meta = labs_from_raw_rows(
                rows, patient_meta=patient_meta, filename=name
            )
            outcome.ok = True
            outcome.labs = labs
            outcome.meta = meta
            outcome.unmatched_count = int(meta["unmatched_count"])
            return outcome

        outcome.error = (
            f"Unsupported file type '{ext or 'unknown'}'. "
            "Accepted: PDF, PNG, JPG, JPEG, CSV."
        )
        return outcome
    except Exception:
        outcome.error = (
            "This file could not be parsed. Try another export (CSV works "
            "best) or a selectable-text PDF."
        )
        return outcome
