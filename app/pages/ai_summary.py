"""AI Summary: show this encounter's narrative as soon as you open the page."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import openai_key_configured
from ui import (
    PAGE_LIFESTYLE,
    action_button_column,
    ensure_ai_result,
    has_active_report,
    prepare_page,
    render_generate_button,
    render_go_home,
    render_page_title,
    render_summary_body,
)

prepare_page()
render_page_title("AI Summary")

if not has_active_report():
    st.warning("No encounter selected yet. Pick a demo patient or upload a report first.")
    with action_button_column():
        render_go_home("ai_no_patient")
    st.stop()

result = ensure_ai_result()

if result is None:
    if st.session_state.get("ai_error"):
        st.error(st.session_state["ai_error"])
    elif not openai_key_configured():
        st.info("Add an OpenAI key to generate this page.")
    with action_button_column():
        render_generate_button()
        render_go_home("ai_need_generate")
    st.stop()

render_summary_body(result)

with action_button_column():
    if st.button(
        "Lifestyle & Questions",
        type="primary",
        use_container_width=True,
        key="ai_to_lifestyle",
    ):
        st.switch_page(PAGE_LIFESTYLE)
    render_go_home("ai")
