"""Shared Streamlit chrome for Phase 1 (theme, sidebar, session)."""

from __future__ import annotations

import hashlib
import html
import uuid
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from db import CURATED_DEMOS, get_encounter_meta, get_lab_results
from parsing.csv_parser import NONE_LABEL, ROLES
from parsing.pipeline import ParseOutcome, parse_report

PAGE_TITLE = "AI Personal Lab Report Interpreter"
PAGE_CHOOSE = "pages/choose_a_report.py"
PAGE_EXTRACTED = "pages/extracted_results.py"
PAGE_AI = "pages/ai_summary.py"
PAGE_LIFESTYLE = "pages/lifestyle_doctor_questions.py"
UPLOAD_TYPES = ["pdf", "png", "jpg", "jpeg", "csv"]
SIDEBAR_YOUR_REPORT = "Your Report"
SIDEBAR_NOT_SELECTED = "Not selected"
CSV_ROLE_LABELS = {
    "test_name": "Test name column",
    "value": "Result / value column",
    "unit": "Unit column",
    "reference_range": "Reference range column",
    "range_low": "Range low column",
    "range_high": "Range high column",
    "flag": "Flag column (optional)",
}

THEME_CSS = """
<style>
@import url("https://fonts.googleapis.com/css2?family=Libre+Baskerville:ital,wght@0,400;0,700;1,400&display=swap");

html, body, [data-testid="stAppViewContainer"],
[data-testid="stSidebar"], [data-testid="stHeader"],
.stApp, .stMarkdown, .stCaption, .stText, .stAlert,
p, h1, h2, h3, h4, h5, h6, span, label, li, a,
div, input, textarea, button, select,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"],
[data-testid="stWidgetLabel"], [data-testid="stDataFrame"],
[data-testid="stDataFrame"] *,
[data-baseweb="tab"], [data-baseweb="tab"] *,
.stTabs, .stButton > button, .stDownloadButton > button {
  font-family: "Times New Roman", Times, "Libre Baskerville", serif !important;
}

/* The broad rule above also caught Streamlit's Material Symbols icon font
   (used by the sidebar collapse arrow, the file-uploader icon, expander
   arrows, etc.) -- Times New Roman has no glyph for those ligatures, so
   the browser fell back to printing the raw icon name as text (e.g.
   "keyboard_double_arrow_right", "upload"). Restore the icon font for
   anything that is actually an icon, so those render as glyphs again. */
[data-testid="stIconMaterial"],
[data-testid="stIconMaterial"] *,
.material-symbols-rounded,
.material-symbols-outlined,
[class*="material-symbols"] {
  font-family: "Material Symbols Rounded", "Material Symbols Outlined",
    "Material Icons" !important;
}

html, body, .stApp {
  font-size: 20px;
}

.stApp {
  background: linear-gradient(180deg, #eef5fa 0%, #f5f8fb 180px, #f5f8fb 100%);
}

/* Faint diagonal watermark across the whole app. Fixed + pointer-events:
   none so it never blocks clicks or scrolling; low opacity so it reads as
   a subtle texture rather than competing with real content. */
body::before {
  content: "";
  position: fixed;
  inset: 0;
  z-index: 9999;
  pointer-events: none;
  opacity: 0.12;
  background-repeat: repeat;
  background-image: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='340'%20height='170'%3E%3Ctext%20x='10'%20y='100'%20font-family='Times%20New%20Roman,serif'%20font-size='24'%20fill='%232c4a63'%20transform='rotate(-28%20170%2085)'%3EZiqi%20(Ankit)%20Cao%3C/text%3E%3C/svg%3E");
}

/* Fixed name/date/LinkedIn badge, top-right on every page -- sits just
   below Streamlit's own toolbar icons (Share/GitHub/menu) so it never
   overlaps them. */
.corner-badge {
  position: fixed;
  top: 3.35rem;
  right: 1rem;
  z-index: 999999;
  font-family: "Times New Roman", Times, "Libre Baskerville", serif;
  font-size: 1.05rem;
  font-weight: 700;
  line-height: 1.4;
  color: #2c4a63;
  text-align: right;
  background: rgba(231, 240, 247, 0.95);
  border: 1px solid #c5d9eb;
  padding: 0.25rem 0.75rem;
  border-radius: 6px;
  pointer-events: auto;
}

.corner-badge a {
  color: #3d6b8c;
  text-decoration: underline;
}

p, label, li, .stMarkdown, .stCaption, .stText,
[data-testid="stMarkdownContainer"] p,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
[data-testid="stWidgetLabel"] p {
  font-size: 1.2rem !important;
  line-height: 1.55;
}

[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p,
.stCaption {
  font-size: 1.2rem !important;
  color: #4a6578 !important;
}

[data-testid="stVerticalBlockBorderWrapper"] [data-testid="element-container"],
[data-testid="stVerticalBlockBorderWrapper"] .stElementContainer {
  margin-top: 0.1rem !important;
  margin-bottom: 0.1rem !important;
}

[data-testid="stSlider"] {
  padding-top: 0 !important;
  padding-bottom: 0.1rem !important;
}

[data-testid="stSliderThumbValue"],
[data-testid="stSliderTickBarMin"],
[data-testid="stSliderTickBarMax"],
[data-testid="stTextInput"] input {
  font-size: 1.2rem !important;
}

/* The deployed Streamlit version renders this as a compact single
   "Upload" button plus a small "200MB per file..." caption, laid out as
   a flex row with align-items:flex-start -- which left everything
   pinned to the top-left corner of the taller box, with a big dead
   patch of empty space to the right and below. Force the row to wrap
   and center as a group instead, and add a headline line above the
   caption (this version has no "Drag and drop file here" text of its
   own) so the enlarged area reads as one deliberate control. */
[data-testid="stFileUploaderDropzone"] {
  min-height: 170px !important;
  align-items: center !important;
  justify-content: flex-start !important;
  padding-left: 2rem !important;
  flex-wrap: wrap !important;
  row-gap: 0.6rem !important;
}

[data-testid="stFileUploaderDropzone"] [data-testid="stIconMaterial"] {
  font-size: 2.8rem !important;
}

[data-testid="stFileUploaderDropzone"] span {
  font-size: 1.4rem !important;
}

[data-testid="stFileUploaderDropzone"] small {
  font-size: 1.1rem !important;
}

[data-testid="stFileUploaderDropzone"] button {
  font-size: 1.4rem !important;
  font-weight: 700 !important;
  padding: 0.75rem 1.5rem !important;
}

[data-testid="stFileUploaderDropzoneInstructions"] {
  flex-direction: column !important;
  align-items: flex-start !important;
  justify-content: center !important;
  text-align: left !important;
  line-height: 1.1 !important;
  row-gap: 0 !important;
}

[data-testid="stFileUploaderDropzoneInstructions"] span {
  line-height: 1.1 !important;
  font-size: 1.05rem !important;
  font-weight: 400 !important;
}

/* Two Streamlit selectbox implementations have shipped over time: an
   older BaseWeb one ([data-baseweb="select"], a plain value div) and a
   newer React Aria combobox (a real <input> plus a [role="option"] list
   rendered in a portal). Cover both. */
[data-testid="stSelectbox"] [data-baseweb="select"] > div:first-child {
  min-height: 3rem !important;
  display: flex !important;
  align-items: center !important;
}

[data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stSelectbox"] input,
[data-baseweb="popover"] [role="option"],
[data-baseweb="menu"] [role="option"],
ul[data-baseweb="menu"] li,
[role="option"] {
  font-size: 1.35rem !important;
}

/* Sidebar collapse/expand arrow -- make it as visible as the rest of the
   sidebar chrome, both while the sidebar is open (stSidebarCollapseButton)
   and after it has been collapsed (stSidebarCollapsedControl). Streamlit
   fades this button in only on hover by default (via opacity on some
   versions, visibility:hidden on others); force it fully visible at all
   times on both mechanisms. */
[data-testid="stSidebarCollapseButton"] [data-testid="stIconMaterial"],
[data-testid="stSidebarCollapsedControl"] [data-testid="stIconMaterial"] {
  font-size: 2rem !important;
}

[data-testid="stSidebarCollapseButton"],
[data-testid="stSidebarCollapseButton"] *,
[data-testid="stSidebarCollapsedControl"],
[data-testid="stSidebarCollapsedControl"] * {
  opacity: 1 !important;
  visibility: visible !important;
}

[data-testid="stHeader"] {
  background: rgba(245, 248, 251, 0.85);
}

[data-testid="stSidebar"] {
  background-color: #e7f0f7;
  border-right: 1px solid #c5d9eb;
  font-size: 1.15rem !important;
}

[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] li,
[data-testid="stSidebar"] a,
[data-testid="stSidebar"] .stMarkdown {
  font-size: 1.15rem !important;
  line-height: 1.55;
}

[data-testid="stSidebar"] h3,
[data-testid="stSidebar"] h2 {
  color: #3d6b8c;
  letter-spacing: 0.02em;
  font-size: 1.4rem !important;
}

[data-testid="stSidebarNav"] a,
[data-testid="stSidebarNavLink"],
[data-testid="stSidebarNavLink"] span,
[data-testid="stSidebarNavLink"] p {
  font-size: 1.35rem !important;
  text-transform: none;
}

[data-testid="stSidebarNav"] [data-testid="stSidebarNavSection"] span,
[data-testid="stSidebarNav"] header,
[data-testid="stSidebarNav"] small {
  font-size: 1.05rem !important;
  letter-spacing: 0.04em;
  color: #3d6b8c !important;
  font-weight: 700 !important;
}

h1 {
  font-size: 2.6rem !important;
}

h2 {
  font-size: 1.85rem !important;
}

h3 {
  font-size: 1.5rem !important;
}

h1, h2, h3 {
  color: #2c4a63 !important;
  font-weight: 700 !important;
}

p.lead,
[data-testid="stMarkdownContainer"] p.lead {
  font-size: 1.45rem !important;
  line-height: 1.6 !important;
  color: #2c4a63 !important;
  margin: 0.35rem 0 1.1rem 0 !important;
  max-width: none !important;
  width: 100% !important;
  font-weight: 400;
}

.hero-kicker {
  color: #5b8fb9;
  font-size: 1.05rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  margin-bottom: 0.25rem;
}

.section-head {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.65rem 0.85rem;
  margin: 0.35rem 0 0.55rem 0;
}

.section-head .badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2rem;
  height: 2rem;
  border-radius: 50%;
  background: #6ba3c7;
  color: #ffffff;
  font-weight: 700;
  font-size: 1.15rem;
}

.section-head h1,
.section-head h2 {
  margin: 0 !important;
  display: inline;
}

.page-head {
  margin: 0 0 0.85rem 0;
}

.page-head h1 {
  font-size: 2.6rem !important;
}

.section-head .contains-tag {
  display: inline-block;
  background: #e7f0f7;
  color: #3d6b8c;
  border: 1px dashed #6ba3c7;
  border-radius: 999px;
  padding: 0.15rem 0.75rem;
  font-size: 0.98rem;
}

.section-head .muted {
  color: #6b7c8a;
  font-size: 1.05rem;
  width: 100%;
  margin: 0;
}

.usages-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.55rem 1.15rem;
  margin: 0.35rem 0 0.85rem 0;
  color: #2c4a63;
  font-size: 1.12rem;
}

.usages-row .usages-label {
  font-weight: 700;
  margin-right: 0.15rem;
}

.usages-row .usage-item {
  display: inline-flex;
  align-items: center;
  gap: 0.4rem;
}

.usages-row .badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.55rem;
  height: 1.55rem;
  border-radius: 50%;
  background: #6ba3c7;
  color: #ffffff;
  font-weight: 700;
  font-size: 0.95rem;
}

.choice-card, .demo-card {
  background: #ffffff;
  border: 1px solid #c5d9eb;
  border-top: 4px solid #6ba3c7;
  border-radius: 12px;
  padding: 1.15rem 1.2rem 1.05rem 1.2rem;
  box-shadow: 0 6px 18px rgba(107, 163, 199, 0.12);
  height: 100%;
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

.demo-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 12px 24px rgba(107, 163, 199, 0.22);
}

.demo-card .nest-index {
  display: inline-block;
  color: #6ba3c7;
  font-size: 0.95rem;
  letter-spacing: 0.04em;
  margin-bottom: 0.2rem;
}

.demo-card h4 {
  color: #2c4a63;
  margin: 0 0 0.35rem 0;
  font-size: 1.35rem;
}

.demo-card .count {
  font-size: 2.2rem;
  line-height: 1.1;
  color: #3d6b8c;
  margin: 0.35rem 0 0.15rem 0;
}

.demo-card .muted, .choice-card .muted {
  color: #6b7c8a;
  font-size: 1.15rem;
  margin: 0.15rem 0;
}

.session-card {
  background: #f8fbfe;
  border: 1px solid #c5d9eb;
  border-radius: 10px;
  padding: 1rem 1.05rem;
  margin-bottom: 0.85rem;
}

.session-card p,
.session-card .muted {
  color: #2c4a63;
  font-size: 1.12rem !important;
  line-height: 1.6;
  margin: 0.2rem 0;
}

.session-card .muted {
  color: #4a6578;
}

.status-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.85rem;
  margin: 0.35rem 0 1.15rem 0;
}

.status-legend .item {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  background: #ffffff;
  border: 1px solid #c5d9eb;
  border-radius: 10px;
  padding: 0.7rem 1.05rem;
  font-size: 1.12rem;
  color: #2c4a63;
  box-shadow: 0 4px 12px rgba(107, 163, 199, 0.10);
}

.status-legend .swatch {
  width: 1.35rem;
  height: 1.35rem;
  border-radius: 4px;
  flex-shrink: 0;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.status-legend .swatch.high { background: #c62828; }
.status-legend .swatch.low { background: #1565c0; }
.status-legend .swatch.normal { background: #ffffff; border: 1px solid #b0bec5; }

.status-legend strong {
  font-size: 1.15rem;
}

div.stButton > button {
  font-family: "Times New Roman", Times, serif !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  letter-spacing: 0.01em;
  font-size: 1.12rem !important;
  padding: 0.6rem 1.05rem !important;
}

div.stButton > button[kind="primary"],
div.stButton > button[data-testid="baseButton-primary"] {
  background-color: #6ba3c7 !important;
  border: 1px solid #5a93b8 !important;
  color: #ffffff !important;
}

div.stButton > button[kind="primary"]:hover,
div.stButton > button[data-testid="baseButton-primary"]:hover {
  background-color: #5b93b8 !important;
  border-color: #4d84aa !important;
}

div.stButton > button[kind="secondary"],
div.stButton > button[data-testid="baseButton-secondary"] {
  background-color: #f4f8fb !important;
  border: 1px solid #b7d0e4 !important;
  color: #2c4a63 !important;
}

/* Two Streamlit tab implementations have shipped over time: an older
   BaseWeb one (data-baseweb="tab"/"tab-list") and a newer React Aria one
   (data-testid="stTab", role="tablist"). Cover both so the tab labels
   stay large and evenly spaced regardless of which version is deployed. */
[data-baseweb="tab-list"],
[role="tablist"] {
  gap: 2.25rem !important;
}

[data-baseweb="tab"],
[data-testid="stTab"] {
  font-size: 2.05rem !important;
  font-weight: 700 !important;
  padding: 0.75rem 0.85rem !important;
  color: #2c4a63 !important;
}

[data-baseweb="tab"] p,
[data-baseweb="tab"] span,
button[data-baseweb="tab"],
.stTabs [data-baseweb="tab"] *,
[data-testid="stMarkdownContainer"] [data-baseweb="tab"],
[data-testid="stTab"] p,
[data-testid="stTab"] span {
  font-size: 2.05rem !important;
  font-weight: 700 !important;
}

[data-baseweb="tab-highlight"] {
  background-color: #3d6b8c !important;
  height: 4px !important;
}

[data-baseweb="tab"][aria-selected="true"] {
  color: #1b4f72 !important;
  font-weight: 800 !important;
}

[data-testid="stMetricValue"] {
  color: #3d6b8c !important;
  font-size: 1.85rem !important;
}

[data-testid="stMetricLabel"] {
  font-size: 1.15rem !important;
}

[data-testid="stDataFrame"],
[data-testid="stDataEditor"] {
  font-size: 1.4rem !important;
}

[data-testid="stDataFrame"] [role="checkbox"],
[data-testid="stDataFrame"] input[type="checkbox"] {
  accent-color: #1b4f72 !important;
  width: 1.35rem !important;
  height: 1.35rem !important;
  outline: 2px solid #1b4f72 !important;
  outline-offset: 1px;
  border-radius: 3px;
}

.mimic-th {
  font-size: 1.25rem !important;
  font-weight: 700 !important;
  color: #3d6b8c !important;
  margin: 0 0 0.45rem 0 !important;
}

.mimic-td {
  font-size: 1.4rem !important;
  color: #2c4a63 !important;
  margin: 0.25rem 0 !important;
  line-height: 1.45 !important;
}

footer, #MainMenu, .stDeployButton {
  visibility: hidden;
}

.finding-card {
  background: #ffffff;
  border: 1px solid #c5d9eb;
  border-radius: 10px;
  padding: 0.85rem 1rem;
  margin-bottom: 0.7rem;
}

.finding-card .status-high {
  color: #c62828;
  font-weight: 700;
}

.finding-card .status-low {
  color: #1565c0;
  font-weight: 700;
}

.source-pill {
  display: inline-block;
  border-radius: 999px;
  padding: 0.15rem 0.7rem;
  font-size: 0.95rem;
  font-weight: 700;
  margin-left: 0.4rem;
}

.source-pill.curated {
  background: #c8e6c9;
  color: #1b5e20;
}

.source-pill.llm {
  background: #ffe0b2;
  color: #e65100;
}
</style>
"""


def configure_page() -> None:
    st.set_page_config(
        page_title=PAGE_TITLE,
        page_icon="🩺",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    apply_theme()


def prepare_page(*, home: bool = False) -> None:
    """Theme + sidebar for pages run through st.navigation (no set_page_config)."""
    st.session_state["_on_home"] = bool(home)
    if home:
        # Home Session card is empty until Extracted Results / a parsed upload.
        clear_search_session()
    apply_theme()
    render_sidebar()


def apply_theme() -> None:
    st.markdown(THEME_CSS, unsafe_allow_html=True)
    st.markdown(
        '<div class="corner-badge">Ziqi (Ankit) Cao &middot; '
        f"{date.today().isoformat()} &middot; "
        '<a href="https://www.linkedin.com/in/ziqi-ankit-cao" '
        'target="_blank" rel="noopener noreferrer">LinkedIn</a></div>',
        unsafe_allow_html=True,
    )


def init_session_state() -> None:
    st.session_state.setdefault("subject_id", None)
    st.session_state.setdefault("hadm_id", None)
    st.session_state.setdefault("source", None)
    st.session_state.setdefault("ai_cache", {})
    st.session_state.setdefault("pending_generate", False)
    st.session_state.setdefault("ai_error", None)
    st.session_state.setdefault("upload_id", None)
    st.session_state.setdefault("upload_labs", None)
    st.session_state.setdefault("upload_meta", None)
    st.session_state.setdefault("upload_filename", None)
    st.session_state.setdefault("upload_error", None)


def _clear_upload_state() -> None:
    dismissed = list(st.session_state.get("dismissed_upload_ids") or [])
    last_id = st.session_state.get("last_upload_file_id")
    if last_id and last_id not in dismissed:
        dismissed.append(last_id)
        st.session_state["dismissed_upload_ids"] = dismissed
    for key in (
        "upload_id",
        "upload_labs",
        "upload_meta",
        "upload_filename",
        "upload_fp",
        "upload_error",
        "upload_needs_mapping",
        "upload_csv_df",
        "upload_csv_mapping",
    ):
        st.session_state.pop(key, None)


def _queue_sidebar_choice(label: str | None) -> None:
    """Remember the radio value for the next run. Never write sidebar_demo here.

    Streamlit forbids changing a widget key after that widget has been drawn,
    and upload parsing happens after the sidebar radio.
    """
    if label:
        st.session_state["_queued_sidebar_choice"] = label


def _take_queued_sidebar_choice() -> str | None:
    pending = st.session_state.pop("_queued_sidebar_choice", None)
    if pending is None:
        pending = st.session_state.pop("_pending_sidebar_demo", None)
    return pending


def select_encounter(
    subject_id: int,
    hadm_id: int,
    source: str = "demo",
    *,
    clear_upload: bool = True,
) -> None:
    if source != "upload" and clear_upload:
        _clear_upload_state()
    st.session_state["subject_id"] = int(subject_id)
    st.session_state["hadm_id"] = int(hadm_id)
    st.session_state["source"] = source
    st.session_state["pending_generate"] = False
    st.session_state["ai_error"] = None
    if source == "upload":
        _queue_sidebar_choice(SIDEBAR_YOUR_REPORT)
        return
    if source == "search":
        st.session_state["search_subject_id"] = int(subject_id)
        st.session_state["search_hadm_id"] = int(hadm_id)
        _queue_sidebar_choice(_search_radio_label())
        return
    if source != "demo":
        return
    for demo in CURATED_DEMOS:
        if int(demo["subject_id"]) == int(subject_id) and int(demo["hadm_id"]) == int(
            hadm_id
        ):
            _queue_sidebar_choice(demo["scenario"])
            break


def restore_search_session() -> None:
    sid = st.session_state.get("search_subject_id")
    hid = st.session_state.get("search_hadm_id")
    if sid is None or hid is None:
        return
    st.session_state["source"] = "search"
    st.session_state["subject_id"] = int(sid)
    st.session_state["hadm_id"] = int(hid)
    st.session_state["pending_generate"] = False
    st.session_state["ai_error"] = None
    _queue_sidebar_choice(_search_radio_label())


def _search_radio_label() -> str | None:
    sid = st.session_state.get("search_subject_id")
    if sid is None and st.session_state.get("source") == "search":
        sid = st.session_state.get("subject_id")
    if sid is None:
        return None
    return f"patient_id {int(sid)}"


def restore_upload_session() -> None:
    """Switch the sidebar back to an already-parsed upload without re-reading it."""
    labs = st.session_state.get("upload_labs")
    if not isinstance(labs, pd.DataFrame) or labs.empty:
        return
    st.session_state["source"] = "upload"
    st.session_state["subject_id"] = 0
    st.session_state["hadm_id"] = 0
    st.session_state["pending_generate"] = False
    st.session_state["ai_error"] = None
    _queue_sidebar_choice(SIDEBAR_YOUR_REPORT)


def _has_parsed_upload() -> bool:
    labs = st.session_state.get("upload_labs")
    return isinstance(labs, pd.DataFrame) and not labs.empty


def ensure_demo_selected() -> None:
    """Keep session keys initialized. Do not auto-pick a demo patient."""
    init_session_state()


def clear_session() -> None:
    st.session_state.clear()
    init_session_state()


def current_patient_label() -> str:
    """Label in page titles: Patient 1, patient_id 123, or Your Report."""
    source = st.session_state.get("source")
    if source == "upload":
        return "Your Report"
    sid = st.session_state.get("subject_id")
    hid = st.session_state.get("hadm_id")
    if sid is None or hid is None:
        return "No patient selected"
    if source == "search":
        return f"patient_id {int(sid)}"
    for demo in CURATED_DEMOS:
        if int(demo["subject_id"]) == int(sid) and int(demo["hadm_id"]) == int(hid):
            return demo["scenario"].split(" - ")[0].strip()
    return f"patient_id {int(sid)}"


def has_active_report() -> bool:
    if st.session_state.get("source") == "upload":
        labs = st.session_state.get("upload_labs")
        return labs is not None and not getattr(labs, "empty", True)
    return (
        st.session_state.get("subject_id") is not None
        and st.session_state.get("hadm_id") is not None
    )


def current_ai_key() -> str | None:
    if st.session_state.get("source") == "upload":
        uid = st.session_state.get("upload_id")
        return f"upload:{uid}" if uid else None
    sid = st.session_state.get("subject_id")
    hid = st.session_state.get("hadm_id")
    if sid is None or hid is None:
        return None
    return f"{int(sid)}:{int(hid)}"


def current_labs() -> pd.DataFrame:
    if st.session_state.get("source") == "upload":
        labs = st.session_state.get("upload_labs")
        return labs if isinstance(labs, pd.DataFrame) else pd.DataFrame()
    sid = st.session_state.get("subject_id")
    hid = st.session_state.get("hadm_id")
    if sid is None or hid is None:
        return pd.DataFrame()
    return get_lab_results(sid, hid)


def current_meta() -> dict | None:
    if st.session_state.get("source") == "upload":
        meta = st.session_state.get("upload_meta")
        return dict(meta) if isinstance(meta, dict) else None
    sid = st.session_state.get("subject_id")
    hid = st.session_state.get("hadm_id")
    if sid is None or hid is None:
        return None
    return get_encounter_meta(sid, hid)


def apply_upload_outcome(outcome: ParseOutcome) -> None:
    st.session_state["source"] = "upload"
    st.session_state["upload_id"] = uuid.uuid4().hex
    st.session_state["subject_id"] = 0
    st.session_state["hadm_id"] = 0
    st.session_state["upload_labs"] = outcome.labs
    st.session_state["upload_meta"] = outcome.meta
    st.session_state["upload_filename"] = outcome.filename
    st.session_state["upload_error"] = None
    st.session_state["upload_needs_mapping"] = False
    st.session_state["pending_generate"] = False
    st.session_state["ai_error"] = None
    _queue_sidebar_choice(SIDEBAR_YOUR_REPORT)
    file_id = st.session_state.get("last_upload_file_id")
    if file_id:
        dismissed = [
            item
            for item in (st.session_state.get("dismissed_upload_ids") or [])
            if item != file_id
        ]
        st.session_state["dismissed_upload_ids"] = dismissed


def ingest_uploaded_file(uploaded, *, allow_vision: bool = True) -> ParseOutcome | None:
    """Parse a Streamlit UploadedFile once per content hash / CSV mapping."""
    if uploaded is None:
        return None
    data = uploaded.getvalue()
    fingerprint = hashlib.sha256(data).hexdigest()
    file_id = getattr(uploaded, "file_id", None) or fingerprint
    dismissed = st.session_state.get("dismissed_upload_ids") or []
    if file_id in dismissed:
        return None
    mapping = st.session_state.get("upload_csv_mapping")
    mapping_sig = tuple(sorted((mapping or {}).items()))
    cache_token = (fingerprint, mapping_sig)
    labs = st.session_state.get("upload_labs")
    if (
        st.session_state.get("upload_fp") == cache_token
        and isinstance(labs, pd.DataFrame)
        and not labs.empty
        and st.session_state.get("source") == "upload"
    ):
        return ParseOutcome(
            ok=True,
            labs=labs,
            meta=st.session_state.get("upload_meta"),
            filename=st.session_state.get("upload_filename") or uploaded.name,
            unmatched_count=int(
                (st.session_state.get("upload_meta") or {}).get("unmatched_count") or 0
            ),
            source_kind=Path(uploaded.name).suffix.lstrip(".").lower(),
        )
    # Same file still sitting in the uploader after the user switched to a demo.
    if (
        file_id == st.session_state.get("last_upload_file_id")
        and st.session_state.get("upload_fp") == cache_token
        and st.session_state.get("source") != "upload"
        and not st.session_state.get("upload_needs_mapping")
        and isinstance(labs, pd.DataFrame)
        and not labs.empty
    ):
        restore_upload_session()
        st.rerun()

    suffix = Path(uploaded.name).suffix.lower()
    use_spinner = suffix in {".png", ".jpg", ".jpeg", ".webp", ".pdf"}
    if use_spinner:
        with st.spinner("Reading your report..."):
            outcome = parse_report(
                uploaded.name,
                data,
                csv_mapping=mapping,
                allow_vision=allow_vision,
            )
    else:
        outcome = parse_report(
            uploaded.name,
            data,
            csv_mapping=mapping,
            allow_vision=allow_vision,
        )
    st.session_state["upload_fp"] = cache_token
    st.session_state["upload_filename"] = uploaded.name
    if outcome.needs_mapping:
        st.session_state["upload_needs_mapping"] = True
        st.session_state["upload_csv_df"] = outcome.csv_df
        if not st.session_state.get("upload_csv_mapping"):
            st.session_state["upload_csv_mapping"] = outcome.csv_mapping
        st.session_state["upload_error"] = outcome.error
        st.session_state["upload_labs"] = None
        return outcome
    if not outcome.ok:
        st.session_state["upload_error"] = outcome.error
        st.session_state["upload_labs"] = None
        st.session_state["upload_needs_mapping"] = False
        return outcome
    st.session_state["last_upload_file_id"] = file_id
    apply_upload_outcome(outcome)
    if st.session_state.get("_sidebar_upload_fp") != cache_token:
        st.session_state["_sidebar_upload_fp"] = cache_token
        st.rerun()
    return outcome


def render_csv_mapping_ui(df: pd.DataFrame, key_prefix: str) -> dict[str, str | None]:
    mapping = dict(st.session_state.get("upload_csv_mapping") or {})
    options = [NONE_LABEL, *[str(col) for col in df.columns]]
    cols = st.columns(2)
    updated: dict[str, str | None] = {}
    for index, role in enumerate(ROLES):
        with cols[index % 2]:
            current = mapping.get(role)
            if current not in options:
                current = NONE_LABEL
            chosen = st.selectbox(
                CSV_ROLE_LABELS[role],
                options,
                index=options.index(current) if current in options else 0,
                key=f"{key_prefix}_{role}",
            )
            updated[role] = None if chosen == NONE_LABEL else chosen
    if st.button("Apply column mapping", key=f"{key_prefix}_apply"):
        st.session_state["upload_csv_mapping"] = updated
        st.session_state.pop("upload_labs", None)
        st.session_state.pop("upload_fp", None)
        st.rerun()
    return updated


def render_upload_preview(labs: pd.DataFrame, meta: dict | None) -> None:
    if labs is None or labs.empty:
        return
    unmatched = int((meta or {}).get("unmatched_count") or 0)
    filename = html.escape(str((meta or {}).get("filename") or "your report"))
    st.success(f"Parsed **{len(labs)}** lab rows from **{filename}**.")
    if unmatched:
        st.caption(
            f"{unmatched} test name(s) were not in the curated dictionary and "
            "are marked LLM General Knowledge."
        )
    preview = labs[
        [
            "test_name",
            "lab_group",
            "value_num",
            "value_unit",
            "status",
            "knowledge_source",
        ]
    ].head(12)
    st.dataframe(preview, use_container_width=True, hide_index=True)


def render_page_title(base: str) -> None:
    """Big page title with the current patient in the tag beside it."""
    label = current_patient_label()
    st.markdown(
        f"""
        <div class="section-head page-head">
          <h1>{html.escape(base)} - {html.escape(label)}</h1>
          <span class="contains-tag">{html.escape(label)}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def panels_label(meta: dict) -> str:
    panels = []
    if meta.get("has_cbc"):
        panels.append("CBC")
    if meta.get("has_metabolic"):
        panels.append("METABOLIC")
    if meta.get("has_lipid"):
        panels.append("LIPID")
    if meta.get("has_a1c"):
        panels.append("A1C")
    return ", ".join(panels) if panels else "—"


def _desired_sidebar_choice() -> str:
    """Radio label that matches the active source, not a widget default."""
    source = st.session_state.get("source")
    if source == "upload" and _has_parsed_upload():
        return SIDEBAR_YOUR_REPORT
    search_label = _search_radio_label()
    if source == "search" and search_label:
        return search_label
    sid = st.session_state.get("subject_id")
    hid = st.session_state.get("hadm_id")
    for demo in CURATED_DEMOS:
        if sid is None or hid is None:
            break
        if int(demo["subject_id"]) == int(sid) and int(demo["hadm_id"]) == int(hid):
            return demo["scenario"]
    if _is_choose_page() and not has_active_report():
        return SIDEBAR_NOT_SELECTED
    return CURATED_DEMOS[0]["scenario"]


def _sidebar_page_id() -> str:
    import traceback

    for frame in traceback.extract_stack():
        path = frame.filename.replace("\\", "/")
        if "/pages/" in path:
            return path.rsplit("/", 1)[-1]
    return ""


def _is_choose_page() -> bool:
    if st.session_state.get("_on_home"):
        return True
    return _sidebar_page_id() == "choose_a_report.py"


def _session_card_is_idle() -> bool:
    """Empty Session until Extracted Results (demo/search) or a parsed upload."""
    if _has_parsed_upload() and st.session_state.get("source") == "upload":
        return False
    if _is_choose_page():
        return True
    return not has_active_report()


def _session_meta_lines(meta: dict) -> str:
    """Shared Session body: label: value; multi-values use English commas."""
    gender = html.escape(str(meta.get("gender") or "—"))
    age = html.escape(str(meta.get("anchor_age") if meta.get("anchor_age") is not None else "—"))
    panels = html.escape(panels_label(meta) or "—")
    labs = html.escape(str(meta.get("lab_record_count", "—")))
    biomarkers = html.escape(str(meta.get("biomarker_count", "—")))
    abnormal = html.escape(str(meta.get("abnormal_result_count", "—")))
    return (
        f"Gender: {gender}, Age: {age}<br>"
        f"Panels: {panels}<br>"
        f"Labs: {labs}, Biomarkers: {biomarkers}, Abnormal: {abnormal}"
    )


def _render_idle_session_card() -> None:
    st.markdown(
        '<div class="session-card">'
        "<p>Patient id: —<br>"
        "Encounter id: —</p>"
        '<p class="muted">'
        "Gender: —, Age: —<br>"
        "Panels: —<br>"
        "Labs: —, Biomarkers: —, Abnormal: —</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_id_session_card(meta: dict) -> None:
    sid = html.escape(str(meta["subject_id"]))
    hid = html.escape(str(meta["hadm_id"]))
    st.markdown(
        f'<div class="session-card">'
        f"<p>Patient id: {sid}<br>"
        f"Encounter id: {hid}</p>"
        f'<p class="muted">{_session_meta_lines(meta)}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )


def _render_upload_session_card(meta: dict) -> None:
    name = html.escape(str(meta.get("patient_name") or "").strip() or "—")
    dob = html.escape(str(meta.get("dob") or "").strip() or "—")
    st.markdown(
        f'<div class="session-card">'
        f"<p>Name: {name}<br>"
        f"DOB: {dob}</p>"
        f'<p class="muted">{_session_meta_lines(meta)}</p>'
        f"</div>",
        unsafe_allow_html=True,
    )


def render_sidebar() -> None:
    """Persistent sidebar: demo switcher, upload, session, Start over."""
    init_session_state()
    ensure_demo_selected()

    demo_labels = [demo["scenario"] for demo in CURATED_DEMOS]
    labels: list[str] = []
    on_home = _is_choose_page()
    idle_home = on_home and not (
        _has_parsed_upload() and st.session_state.get("source") == "upload"
    )
    if idle_home:
        labels.append(SIDEBAR_NOT_SELECTED)
    labels.extend(demo_labels)
    search_label = _search_radio_label()
    if search_label and not idle_home:
        labels.append(search_label)
    if _has_parsed_upload():
        labels.append(SIDEBAR_YOUR_REPORT)

    desired = _desired_sidebar_choice()
    if desired not in labels:
        desired = labels[0]
    page_id = "choose_a_report.py" if on_home else _sidebar_page_id()
    page_changed = page_id != st.session_state.get("_sidebar_page_id")
    st.session_state["_sidebar_page_id"] = page_id

    pending = _take_queued_sidebar_choice()
    if idle_home:
        st.session_state["sidebar_demo"] = SIDEBAR_NOT_SELECTED
        st.session_state["_applied_sidebar_demo"] = SIDEBAR_NOT_SELECTED
    elif pending is not None and pending in labels:
        st.session_state["sidebar_demo"] = pending
        st.session_state["_applied_sidebar_demo"] = pending
    elif page_changed:
        # st.navigation can reset the radio; do not treat that as a click.
        st.session_state["sidebar_demo"] = desired
        st.session_state["_applied_sidebar_demo"] = desired
    elif st.session_state.get("sidebar_demo") not in labels:
        st.session_state["sidebar_demo"] = desired

    with st.sidebar:
        extra_in_list = (
            (search_label is not None and not idle_home)
            or SIDEBAR_YOUR_REPORT in labels
        )
        if idle_home:
            st.markdown("## Current report")
            st.caption("Not selected yet — open Extracted Results or upload a report.")
        elif extra_in_list:
            st.markdown("## Current report")
            source = st.session_state.get("source")
            if source == "upload":
                st.caption("Your Report is selected. You can switch to a demo anytime.")
            elif source == "search":
                st.caption("This searched patient is selected. You can switch anytime.")
            else:
                st.caption("A demo is selected. Your other reports stay in this list.")
        else:
            st.markdown("## Demo patient")
            st.caption("Switch anytime — results, summary, and suggestions stay in sync.")
        choice = st.radio(
            "Current report",
            labels,
            key="sidebar_demo",
            label_visibility="collapsed",
        )
        last_choice = st.session_state.get("_applied_sidebar_demo")
        if (
            last_choice is not None
            and choice != last_choice
            and not on_home
            and choice != SIDEBAR_NOT_SELECTED
        ):
            if choice == SIDEBAR_YOUR_REPORT:
                restore_upload_session()
            elif search_label and choice == search_label:
                restore_search_session()
            else:
                chosen = next(
                    demo for demo in CURATED_DEMOS if demo["scenario"] == choice
                )
                select_encounter(
                    int(chosen["subject_id"]),
                    int(chosen["hadm_id"]),
                    source="demo",
                    clear_upload=False,
                )
        st.session_state["_applied_sidebar_demo"] = choice

        st.markdown("## Session")
        if _session_card_is_idle():
            _render_idle_session_card()
        else:
            meta = current_meta()
            if meta is None:
                _render_idle_session_card()
            elif st.session_state.get("source") == "upload":
                _render_upload_session_card(meta)
            else:
                _render_id_session_card(meta)

        if st.button("Start over", use_container_width=True):
            clear_session()
            st.switch_page(PAGE_CHOOSE)


@contextmanager
def action_button_column():
    """Keep stacked page actions the same width."""
    col, _ = st.columns([1, 2.6])
    with col:
        yield


def clear_search_session() -> None:
    """Drop demo/search selection so Home shows an empty session card."""
    st.session_state.pop("search_subject_id", None)
    st.session_state.pop("search_hadm_id", None)
    if st.session_state.get("source") == "upload" and _has_parsed_upload():
        return
    st.session_state["subject_id"] = None
    st.session_state["hadm_id"] = None
    st.session_state["source"] = None
    st.session_state["_applied_sidebar_demo"] = None


def render_go_home(key: str = "go_home") -> None:
    """Escape hatch on result pages. Do not use on Choose a Report."""
    if st.button("Go Home", type="primary", key=key, use_container_width=True):
        clear_search_session()
        st.switch_page(PAGE_CHOOSE)


def render_status_legend() -> None:
    """Color key for HIGH / LOW / NORMAL (Section 6.2)."""
    st.markdown(
        """
        <div class="status-legend">
          <div class="item">
            <span class="swatch high"></span>
            <span><strong>HIGH</strong> (above range)</span>
          </div>
          <div class="item">
            <span class="swatch low"></span>
            <span><strong>LOW</strong> (below range)</span>
          </div>
          <div class="item">
            <span class="swatch normal"></span>
            <span><strong>NORMAL</strong> (within range)</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_source_badge(source: str) -> str:
    if source == "Curated Database":
        klass = "curated"
    else:
        klass = "llm"
        source = source or "LLM General Knowledge"
    return f'<span class="source-pill {klass}">{source}</span>'


def render_generate_button(*, after_page: str | None = None) -> None:
    """Retry generate, or jump to a results page that will load/generate."""
    from config import openai_key_configured
    from llm.client import has_cached_summary

    cache_key = current_ai_key()
    if cache_key is None or not has_active_report():
        return

    if not openai_key_configured():
        st.button(
            "Generate AI Summary",
            type="primary",
            disabled=True,
            use_container_width=True,
        )
        st.caption(
            "Add OPENAI_API_KEY to 3. App/.env to enable AI summary. "
            "Extracted results above do not need a key."
        )
        return

    cached = has_cached_summary(cache_key=cache_key)
    label = "AI Summary" if cached else "Generate AI Summary"
    if st.button(label, type="primary", use_container_width=True):
        st.session_state["pending_generate"] = not cached
        st.session_state["ai_error"] = None
        if after_page:
            st.switch_page(after_page)
        else:
            st.rerun()


def ensure_ai_result() -> dict | None:
    """Return cached AI JSON, or generate once when this page is opened."""
    from config import openai_key_configured
    from llm.client import LLMError, generate_for_encounter, get_cached_summary

    cache_key = current_ai_key()
    labs = current_labs()
    meta = current_meta()
    if cache_key is None or meta is None or labs.empty:
        return None

    cached = get_cached_summary(cache_key=cache_key)
    if cached is not None:
        st.session_state["pending_generate"] = False
        return cached

    if not openai_key_configured():
        return None

    if st.session_state.get("ai_error") and not st.session_state.get(
        "pending_generate"
    ):
        return None

    try:
        with st.spinner("Generating..."):
            result = generate_for_encounter(
                st.session_state.get("subject_id") or 0,
                st.session_state.get("hadm_id") or 0,
                labs=labs,
                meta=meta,
                cache_key=cache_key,
            )
        st.session_state["pending_generate"] = False
        st.session_state["ai_error"] = None
        return result
    except LLMError as exc:
        st.session_state["pending_generate"] = False
        st.session_state["ai_error"] = exc.user_message
        return None


def render_summary_body(result: dict) -> None:
    import html as html_lib

    st.markdown(result.get("summary") or "")
    findings = result.get("key_findings") or []
    if not findings:
        st.caption("No HIGH / LOW findings were sent to the model for this encounter.")
        return
    st.subheader("Key findings")
    for item in findings:
        status = html_lib.escape(str(item.get("status") or ""))
        status_class = "status-high" if status == "HIGH" else "status-low"
        test_name = html_lib.escape(str(item.get("test_name") or ""))
        explanation = html_lib.escape(str(item.get("plain_explanation") or ""))
        badge = render_source_badge(str(item.get("knowledge_source") or ""))
        st.markdown(
            f'<div class="finding-card">'
            f"<p><strong>{test_name}</strong> "
            f'<span class="{status_class}">{status}</span> {badge}</p>'
            f"<p>{explanation}</p>"
            f"</div>",
            unsafe_allow_html=True,
        )


def render_lifestyle_body(result: dict) -> None:
    left, right = st.columns(2, gap="large")
    with left:
        st.subheader("Lifestyle suggestions")
        suggestions = result.get("lifestyle_suggestions") or []
        if suggestions:
            for item in suggestions:
                st.markdown(f"- {item}")
        else:
            st.caption("No lifestyle suggestions were returned.")
    with right:
        st.subheader("Questions to ask your doctor")
        questions = result.get("doctor_questions") or []
        if questions:
            for item in questions:
                st.markdown(f"- {item}")
        else:
            st.caption("No doctor questions were returned.")
