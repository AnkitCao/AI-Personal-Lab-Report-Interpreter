"""Lifestyle & Questions: show this encounter's advice as soon as you open the page."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import openai_key_configured
from ui import (
    PAGE_AI,
    action_button_column,
    ensure_ai_result,
    has_active_report,
    prepare_page,
    render_generate_button,
    render_go_home,
    render_lifestyle_body,
    render_page_title,
)

prepare_page()
render_page_title("Lifestyle & Questions")

if not has_active_report():
    st.warning("No encounter selected yet. Pick a demo patient or upload a report first.")
    with action_button_column():
        render_go_home("lifestyle_no_patient")
    st.stop()

result = ensure_ai_result()

if result is None:
    if st.session_state.get("ai_error"):
        st.error(st.session_state["ai_error"])
    elif not openai_key_configured():
        st.info("Add an OpenAI key to generate this page.")
    with action_button_column():
        render_generate_button()
        render_go_home("lifestyle_need_generate")
    st.stop()

render_lifestyle_body(result)

with action_button_column():
    if st.button(
        "AI Summary",
        type="primary",
        use_container_width=True,
        key="lifestyle_to_ai",
    ):
        st.switch_page(PAGE_AI)
    render_go_home("lifestyle")
