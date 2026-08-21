"""Start: choose a demo, search the sample database, or upload a report."""

from __future__ import annotations

import html
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db import (
    CURATED_DEMOS,
    encounter_keys_for_finding,
    get_demo_encounters,
    get_encounter_meta,
)
from ui import (
    PAGE_EXTRACTED,
    PAGE_TITLE,
    UPLOAD_TYPES,
    ingest_uploaded_file,
    prepare_page,
    render_csv_mapping_ui,
    render_upload_preview,
    select_encounter,
)

prepare_page(home=True)

st.title(PAGE_TITLE)
st.markdown(
    '<p class="lead">This app turns the flagged results in your lab reports '
    "into an easy-to-understand conclusion, lifestyle suggestions, "
    "and recommended questions to take to your doctor.</p>",
    unsafe_allow_html=True,
)
st.caption(
    "All demo data in this app is a synthetic lab-report sample I built for "
    "demonstration purposes: 100 fictional patients, 100 encounters, and "
    "1,300 lab results. It is not derived from any real patient records."
)


def _go_to_results(subject_id: int, hadm_id: int, source: str = "demo") -> None:
    select_encounter(
        subject_id,
        hadm_id,
        source=source,
        clear_upload=source == "demo",
    )
    st.switch_page(PAGE_EXTRACTED)


def _panels_covered(row: pd.Series) -> str:
    panels = []
    if row.get("has_cbc"):
        panels.append("CBC")
    if row.get("has_metabolic"):
        panels.append("METABOLIC")
    if row.get("has_lipid"):
        panels.append("LIPID")
    if row.get("has_a1c"):
        panels.append("A1C")
    return ", ".join(panels)


PAGE_SIZE = 6
SEARCH_COL_WEIGHTS = [0.42, 1.2, 1.25, 0.55, 0.7, 2.15, 1.2, 0.75, 1.0]
SEARCH_HEADERS = [
    "",
    "Patient id",
    "Encounter id",
    "Age",
    "Gender",
    "Panels covered",
    "Abnormal count",
    "Labs",
    "Biomarkers",
]


def _search_cell(text, *, header: bool = False) -> None:
    klass = "mimic-th" if header else "mimic-td"
    st.markdown(
        f'<p class="{klass}">{html.escape(str(text))}</p>',
        unsafe_allow_html=True,
    )


tab_demo, tab_search, tab_upload = st.tabs(
    [
        "Three Patients' Demo",
        "Search Sample Database by id",
        "Upload Your Report",
    ]
)

with tab_demo:
    st.markdown(
        """
        <div class="section-head">
          <span class="badge">1</span>
          <h2>Three Patients' Demo</h2>
          <span class="contains-tag">contains 3 demo patients</span>
          <p class="muted">Pick one checkup-style walkthrough. All three live inside this block.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        cols = st.columns(3, gap="medium")
        for col, demo in zip(cols, CURATED_DEMOS):
            meta = get_encounter_meta(demo["subject_id"], demo["hadm_id"])
            with col:
                if meta is None:
                    st.error("Encounter missing from the database.")
                    continue
                st.markdown(
                    f'<div class="demo-card">'
                    f"<h4>{demo['scenario']}</h4>"
                    f'<p class="muted">Abnormal results</p>'
                    f'<p class="count">{int(meta["abnormal_result_count"])}</p>'
                    f'<p class="muted">{meta["gender"]} / {meta["anchor_age"]} · '
                    f"{meta['lab_record_count']} labs / "
                    f"{meta['biomarker_count']} biomarkers</p>"
                    f'<p class="muted">{demo["notes"]}</p>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
                st.write("")
                if st.button(
                    "Extracted Results",
                    key=f"home_demo_{demo['subject_id']}_{demo['hadm_id']}",
                    use_container_width=True,
                    type="primary",
                ):
                    _go_to_results(demo["subject_id"], demo["hadm_id"])

with tab_search:
    st.markdown(
        """
        <div class="section-head">
          <span class="badge">2</span>
          <h2>Search Sample Database by id</h2>
          <span class="contains-tag">database</span>
          <p class="muted">Search the full sample database by id, then narrow by gender, age, panel, or lab pattern.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        encounters = get_demo_encounters({"full_panels_only": False})
        if encounters.empty:
            st.warning("No encounters found in the database.")
        else:
            search = st.text_input(
                "Filter by patient id or encounter id",
                placeholder="e.g. 90001 or 90101",
            )
            f1, f2, f3 = st.columns(3, gap="small")
            with f1:
                gender = st.selectbox("Filter by gender", ["Any", "F", "M"])
            with f2:
                age_lo, age_hi = st.slider(
                    "Filter by age",
                    min_value=int(encounters["anchor_age"].min()),
                    max_value=int(encounters["anchor_age"].max()),
                    value=(
                        int(encounters["anchor_age"].min()),
                        int(encounters["anchor_age"].max()),
                    ),
                )
            with f3:
                finding = st.selectbox(
                    "Filter by lab pattern",
                    [
                        "Any",
                        "High A1C",
                        "High glucose",
                        "High lipids",
                        "High creatinine",
                        "Low hemoglobin",
                        "No HIGH / LOW",
                    ],
                    help="Uses HIGH/LOW lab flags, not a diagnosis.",
                )
            min_abn, max_abn = st.slider(
                "Filter by abnormal result count",
                min_value=int(encounters["abnormal_result_count"].min()),
                max_value=int(encounters["abnormal_result_count"].max()),
                value=(
                    int(encounters["abnormal_result_count"].min()),
                    int(encounters["abnormal_result_count"].max()),
                ),
            )
            p1, p2, p3, p4 = st.columns(4, gap="small")
            with p1:
                need_cbc = st.checkbox("Has CBC", value=False)
            with p2:
                need_met = st.checkbox("Has metabolic", value=False)
            with p3:
                need_lipid = st.checkbox("Has lipid", value=False)
            with p4:
                need_a1c = st.checkbox("Has A1C", value=False)

            filtered = encounters[
                (encounters["abnormal_result_count"] >= min_abn)
                & (encounters["abnormal_result_count"] <= max_abn)
                & (encounters["anchor_age"] >= age_lo)
                & (encounters["anchor_age"] <= age_hi)
            ].copy()
            if gender != "Any":
                filtered = filtered[filtered["gender"] == gender]
            if need_cbc:
                filtered = filtered[filtered["has_cbc"] == 1]
            if need_met:
                filtered = filtered[filtered["has_metabolic"] == 1]
            if need_lipid:
                filtered = filtered[filtered["has_lipid"] == 1]
            if need_a1c:
                filtered = filtered[filtered["has_a1c"] == 1]
            if search.strip():
                needle = search.strip()
                filtered = filtered[
                    filtered["subject_id"].astype(str).str.contains(
                        needle, regex=False
                    )
                    | filtered["hadm_id"].astype(str).str.contains(
                        needle, regex=False
                    )
                ]
            if finding != "Any" and not filtered.empty:
                keys = encounter_keys_for_finding(finding) or set()
                mask = [
                    (int(sid), int(hid)) in keys
                    for sid, hid in zip(filtered["subject_id"], filtered["hadm_id"])
                ]
                filtered = filtered[mask]
            filtered = filtered.reset_index(drop=True)

            if filtered.empty:
                st.info(
                    "None. This database does not have a patient matching these filters."
                )
            else:
                table_sig = tuple(int(x) for x in filtered["subject_id"].tolist())
                n_rows = len(filtered)
                n_pages = max(1, (n_rows + PAGE_SIZE - 1) // PAGE_SIZE)
                if st.session_state.get("mimic_search_sig") != table_sig:
                    st.session_state["mimic_search_sig"] = table_sig
                    st.session_state["mimic_search_page"] = 1
                page = int(st.session_state.get("mimic_search_page", 1))
                page = min(max(page, 1), n_pages)
                st.session_state["mimic_search_page"] = page
                start = (page - 1) * PAGE_SIZE
                page_df = filtered.iloc[start : start + PAGE_SIZE].reset_index(
                    drop=True
                )

                st.caption(
                    f"{n_rows} encounters"
                    + (f" · page {page} of {n_pages}" if n_pages > 1 else "")
                )
                header_cols = st.columns(SEARCH_COL_WEIGHTS, gap="small")
                for col, title in zip(header_cols, SEARCH_HEADERS):
                    with col:
                        _search_cell(title, header=True)

                pick_prefix = f"mimic_pick_{hash(table_sig)}_{page}_"
                checked: list[int] = []
                for i, row in page_df.iterrows():
                    i = int(i)
                    cells = [
                        None,
                        int(row["subject_id"]),
                        int(row["hadm_id"]),
                        int(row["anchor_age"]),
                        row["gender"],
                        _panels_covered(row),
                        int(row["abnormal_result_count"]),
                        int(row["lab_record_count"]),
                        int(row["biomarker_count"]),
                    ]
                    cols = st.columns(SEARCH_COL_WEIGHTS, gap="small")
                    with cols[0]:
                        if st.checkbox(
                            "Select this encounter",
                            key=f"{pick_prefix}{i}",
                            label_visibility="collapsed",
                        ):
                            checked.append(i)
                    for col, value in zip(cols[1:], cells[1:]):
                        with col:
                            _search_cell(value)

                prev_key = f"{pick_prefix}checked"
                prev_checked = st.session_state.get(prev_key, [])
                if len(checked) > 1:
                    newly = [i for i in checked if i not in prev_checked]
                    keep = int(newly[-1] if newly else checked[0])
                    for i in checked:
                        if i != keep:
                            st.session_state[f"{pick_prefix}{i}"] = False
                    st.session_state[prev_key] = [keep]
                    st.session_state["_mimic_multi_check_warn"] = True
                    st.rerun()
                st.session_state[prev_key] = checked
                if st.session_state.pop("_mimic_multi_check_warn", False):
                    st.warning(
                        "You can only select one patient to view results."
                    )
                if n_pages > 1:
                    prev_col, info_col, next_col = st.columns([1, 2, 1])
                    with prev_col:
                        if st.button(
                            "Previous",
                            disabled=page <= 1,
                            use_container_width=True,
                            key="search_prev_page",
                        ):
                            st.session_state["mimic_search_page"] = page - 1
                            st.rerun()
                    with info_col:
                        st.markdown(
                            f"<p style='text-align:center;margin:0.35rem 0 0 0;'>"
                            f"Page {page} of {n_pages}</p>",
                            unsafe_allow_html=True,
                        )
                    with next_col:
                        if st.button(
                            "Next",
                            disabled=page >= n_pages,
                            use_container_width=True,
                            key="search_next_page",
                        ):
                            st.session_state["mimic_search_page"] = page + 1
                            st.rerun()

                if st.button(
                    "Extracted Results",
                    type="primary",
                    key="search_to_extracted",
                ):
                    if len(checked) != 1:
                        st.warning(
                            "Check one patient in the table first. "
                            "Only one patient can be opened at a time."
                        )
                    else:
                        row = page_df.iloc[int(checked[0])]
                        _go_to_results(
                            int(row["subject_id"]),
                            int(row["hadm_id"]),
                            source="search",
                        )

with tab_upload:
    st.markdown(
        """
        <div class="section-head">
          <span class="badge">3</span>
          <h2>Upload Your Report</h2>
          <span class="contains-tag">your file</span>
          <p class="muted">Accepted: PDF, PNG, JPG/JPEG, CSV. Not accepted: Word, Excel, or other file types.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.container(border=True):
        uploaded = st.file_uploader(
            "Upload a lab report",
            type=UPLOAD_TYPES,
            accept_multiple_files=False,
            key="home_upload",
        )
        outcome = ingest_uploaded_file(uploaded) if uploaded is not None else None
        labs = None
        meta = None
        if outcome is not None and outcome.needs_mapping:
            st.info(outcome.error)
            df = outcome.csv_df
            if df is None:
                df = st.session_state.get("upload_csv_df")
            if df is not None:
                st.caption("Preview of the first rows in this CSV:")
                st.dataframe(df.head(8), use_container_width=True, hide_index=True)
                render_csv_mapping_ui(df, "home_csv_map")
        elif outcome is not None and not outcome.ok:
            st.error(outcome.error or "This file could not be parsed.")
        elif outcome is not None and outcome.ok:
            labs, meta = outcome.labs, outcome.meta
        elif (
            st.session_state.get("source") == "upload"
            and isinstance(st.session_state.get("upload_labs"), pd.DataFrame)
            and not st.session_state["upload_labs"].empty
        ):
            labs = st.session_state["upload_labs"]
            meta = st.session_state.get("upload_meta")

        if labs is not None:
            render_upload_preview(labs, meta)
            if st.button(
                "Extracted Results",
                type="primary",
                key="upload_to_extracted",
            ):
                st.session_state["source"] = "upload"
                st.switch_page(PAGE_EXTRACTED)
        elif uploaded is None:
            st.caption(
                "Drop a report to extract tests, values, units, and ranges. "
                "Status (HIGH / LOW / NORMAL) is computed here from the "
                "file's own reference ranges."
            )
