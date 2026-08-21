"""AI Personal Lab Report Interpreter — navigation entrypoint."""

from __future__ import annotations

import streamlit as st

from ui import configure_page

configure_page()

pg = st.navigation(
    {
        "Start": [
            st.Page(
                "pages/choose_a_report.py",
                title="Choose a Report",
                default=True,
            ),
        ],
        "Results": [
            st.Page("pages/extracted_results.py", title="Extracted Results"),
            st.Page("pages/ai_summary.py", title="AI Summary"),
            st.Page(
                "pages/lifestyle_doctor_questions.py",
                title="Lifestyle Doctor Questions",
            ),
        ],
    }
)
pg.run()
