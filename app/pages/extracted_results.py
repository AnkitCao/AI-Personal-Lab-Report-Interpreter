"""Extracted Lab Results (Section 6.2 / 20)."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui import (
    PAGE_AI,
    PAGE_LIFESTYLE,
    action_button_column,
    current_labs,
    has_active_report,
    prepare_page,
    render_go_home,
    render_generate_button,
    render_page_title,
    render_status_legend,
)

prepare_page()

render_page_title("Extracted Lab Results")
render_status_legend()

if not has_active_report():
    st.warning("No encounter selected yet. Pick a demo patient or upload a report first.")
    with action_button_column():
        render_go_home("extracted_no_patient")
    st.stop()

rows = current_labs()
if rows.empty:
    st.error("No lab results found for this encounter.")
    with action_button_column():
        render_go_home("extracted_empty")
    st.stop()


def _format_range(low, high) -> str:
    low_missing = pd.isna(low)
    high_missing = pd.isna(high)
    if low_missing and high_missing:
        return "—"
    if low_missing:
        return f"≤ {high}"
    if high_missing:
        return f"≥ {low}"
    return f"{low} – {high}"


def _format_result(row: pd.Series):
    if pd.notna(row["value_num"]):
        return row["value_num"]
    if pd.notna(row["value_text"]) and str(row["value_text"]).strip():
        return row["value_text"]
    return "—"


display = pd.DataFrame(
    {
        "Test": rows["test_name"],
        "Group": rows["lab_group"],
        "Result": rows.apply(_format_result, axis=1),
        "Unit": rows["value_unit"].fillna("—"),
        "Reference Range": [
            _format_range(lo, hi)
            for lo, hi in zip(rows["ref_range_lower"], rows["ref_range_upper"])
        ],
        "Status": rows["status"],
        "Source": rows["knowledge_source"],
    }
)

ROW_TINTS = {
    "HIGH": "#f8d0d0",
    "LOW": "#d0e4f8",
    "UNKNOWN": "#e6e6e6",
    "ABNORMAL": "#f8e6c8",
}
STATUS_CELL = {
    "HIGH": "background-color: #c62828; color: white; font-weight: 600",
    "LOW": "background-color: #1565c0; color: white; font-weight: 600",
    "UNKNOWN": "background-color: #9e9e9e; color: white",
    "ABNORMAL": "background-color: #ef6c00; color: white; font-weight: 600",
}
SOURCE_CELL = {
    "Curated Database": (
        "background-color: #c8e6c9; color: #1b5e20; font-weight: 600"
    ),
    "LLM General Knowledge": (
        "background-color: #ffe0b2; color: #e65100; font-weight: 600"
    ),
}


def _row_style(row: pd.Series) -> list[str]:
    color = ROW_TINTS.get(row["Status"])
    if not color:
        return [""] * len(row)
    return [f"background-color: {color}"] * len(row)


def _status_style(val: str) -> str:
    return STATUS_CELL.get(val, "")


def _source_style(val: str) -> str:
    return SOURCE_CELL.get(val, "")


styler = (
    display.style.apply(_row_style, axis=1)
    .map(_status_style, subset=["Status"])
    .map(_source_style, subset=["Source"])
)

n_high = int((rows["status"] == "HIGH").sum())
n_low = int((rows["status"] == "LOW").sum())
n_normal = int((rows["status"] == "NORMAL").sum())
n_unknown = int((rows["status"] == "UNKNOWN").sum())

m1, m2, m3, m4 = st.columns(4)
m1.metric("Results", len(rows))
m2.metric("HIGH", n_high)
m3.metric("LOW", n_low)
m4.metric("NORMAL", n_normal)
if n_unknown:
    st.caption(
        f"{n_unknown} result(s) marked UNKNOWN "
        "(no numeric value, or no reference range to compare against)."
    )

st.dataframe(styler, use_container_width=True, hide_index=True, height=560)

st.divider()
if st.session_state.get("ai_error"):
    st.error(st.session_state["ai_error"])
with action_button_column():
    render_generate_button(after_page=PAGE_AI)
    if st.button(
        "Lifestyle & Questions",
        type="primary",
        use_container_width=True,
        key="extracted_to_lifestyle",
    ):
        st.switch_page(PAGE_LIFESTYLE)
    render_go_home("extracted")
