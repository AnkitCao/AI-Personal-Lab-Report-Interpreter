"""LLM prompts and structured-output schema (Sections 13–14)."""

from __future__ import annotations

PROMPT_REVISION = "lifestyle-specific-v1"

LAB_INTERPRETATION_SCHEMA: dict = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "summary": {
            "type": "string",
            "description": (
                "2-4 short paragraphs in plain language, grouped by lab panel. "
                "Write as a note to the patient, not as a clinician. Prefer "
                "'worth bringing up with your doctor' over 'needs further evaluation'."
            ),
        },
        "key_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "test_name": {"type": "string"},
                    "status": {"type": "string", "enum": ["HIGH", "LOW"]},
                    "plain_explanation": {
                        "type": "string",
                        "description": "1-2 sentences. Do not re-judge the status.",
                    },
                    "knowledge_source": {
                        "type": "string",
                        "enum": ["Curated Database", "LLM General Knowledge"],
                    },
                },
                "required": [
                    "test_name",
                    "status",
                    "plain_explanation",
                    "knowledge_source",
                ],
            },
        },
        "lifestyle_suggestions": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "6-8 specific bullets tied to the HIGH/LOW tests. Must include: "
                "(1) foods often encouraged, with named examples (oats, beans, "
                "leafy greens, yogurt, fatty fish); (2) foods commonly limited, "
                "with named examples (soda, candy, fried food, processed meat, "
                "very salty snacks); (3) a concrete activity plan: the activity "
                "(e.g. brisk walking), minutes per session, days per week, and "
                "weekly total hours. Forbidden: vague lines such as 'eat a "
                "balanced diet', 'stay hydrated', 'get more exercise', or "
                "'a variety of nutrients'. Never name a medication or supplement."
            ),
        },
        "doctor_questions": {
            "type": "array",
            "items": {"type": "string"},
            "description": "3-6 questions the reader can ask their doctor. Not a diagnosis.",
        },
        "trend_analysis": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "test_name": {"type": "string"},
                    "narrative": {"type": "string"},
                },
                "required": ["test_name", "narrative"],
            },
        },
    },
    "required": [
        "summary",
        "key_findings",
        "lifestyle_suggestions",
        "doctor_questions",
        "trend_analysis",
    ],
}


def build_system_prompt() -> str:
    """Fixed system prompt from Section 13.1 plus Phase 2 safety constraints."""
    return """You are a health-literacy assistant inside a lab-report reader.

You will be given a patient's lab results as structured JSON. Each row
already has a computed status (HIGH / LOW / NORMAL) and a
knowledge_source ("Curated Database" or "LLM General Knowledge") —
these are FACTS, already decided outside of you. Never re-derive or
contradict a status. Never compare a number to a reference range yourself
to decide if it is abnormal; that work is already done.

Hard rules:
1. Never diagnose a condition or disease.
2. Never name a specific medication, supplement, dose, or treatment.
   Lifestyle suggestions may cover diet, exercise, and sleep only.
3. For any row whose knowledge_source is "LLM General Knowledge",
   explicitly say that specific biomarker was not checked against a
   curated reference source.
4. Only discuss HIGH/LOW rows in detail; mention NORMAL rows only as a
   brief aggregate count ("12 other results were within range").
5. Write in a calm, clear, product-quality tone. No alarming language.
6. Copy knowledge_source from each input row into key_findings. Do not
   change it.
7. If there are no HIGH/LOW rows, say that the reported results were
   within range. Do not invent abnormal findings.
8. If no historical / trend table is provided, return trend_analysis as
   an empty list.
9. Speak to the patient, not to a clinician. Do not write like a medical
   note. Avoid phrases such as "further evaluation", "clinical correlation",
   "workup", or "these findings suggest a need for". Prefer patient-facing
   wording such as "these are worth bringing up with your doctor" or
   "you may want to ask your doctor about this".
10. Lifestyle suggestions must be specific and tied to the HIGH/LOW tests.
    Never write filler such as "eat a balanced diet", "stay well-hydrated",
    "a variety of nutrients", or "get more exercise".
    Required content:
    - Foods often encouraged for these flags, with named examples.
    - Foods commonly limited for these flags, with named examples
      (say "often asked to cut back on", not "you are forbidden").
    - Activity with numbers: what to do, minutes per session, how many
      days per week, and total hours per week (typical checkup starting
      point is brisk walking 20-30 minutes, 5 days per week, about
      2-2.5 hours per week — adjust if walking is a poor fit).
    - Optional: a sleep target in hours per night if relevant.
    If Caution level is "high", the FIRST bullet must tell the reader to
    confirm this plan with their doctor before changing diet or activity.
    Then still give the specific food and walking details as discussion
    points, not as medical orders. Never encourage strenuous workouts
    (HIIT, heavy lifting, long runs) when blood counts, kidney markers,
    or liver markers are among the HIGH/LOW rows — keep it to easy
    walking unless the flags are only lipids/A1C/glucose. Still never
    name a medication.
"""


def build_user_prompt(encounter_data: dict, trend_data: list | None = None) -> str:
    """Fill the Section 13.2 user-prompt template from a structured dict."""
    panels = encounter_data.get("panel_list") or []
    panel_list = ", ".join(panels) if panels else "not specified"
    rows = encounter_data.get("abnormal_rows") or []
    table_lines = [_format_abnormal_row(row) for row in rows]
    compact_table = "\n".join(table_lines) if table_lines else "(none)"

    trend_block = ""
    if trend_data:
        trend_lines = [
            f"- {item.get('test_name')}: {item.get('series')}"
            for item in trend_data
        ]
        trend_block = (
            "Historical values for trend analysis:\n"
            + "\n".join(trend_lines)
            + "\n"
        )

    caution = encounter_data.get("caution_level") or "routine"
    unique_abnormal = encounter_data.get("unique_abnormal", len(rows))
    abnormal_panels = encounter_data.get("abnormal_panels") or []
    caution_note = (
        "Caution level: high. Several tests or panels are outside range. "
        "First lifestyle bullet: confirm with a doctor before changing diet "
        "or activity. Remaining bullets must still be specific (named foods "
        "to eat more of, named foods to cut back on, and walking minutes / "
        "days per week / weekly hours). Do not recommend HIIT, heavy lifting, "
        "or long runs. No vague 'balanced diet' lines."
        if caution == "high"
        else (
            "Caution level: routine. Give specific named foods and a numbered "
            "walking plan (minutes per session, days per week, hours per week). "
            "No vague 'balanced diet' or 'get more exercise' lines."
        )
    )

    return f"""Patient context: {encounter_data.get('gender', 'unknown')}, age {encounter_data.get('anchor_age', 'unknown')}

Panels included: {panel_list}

Abnormal results ({encounter_data.get('n_abnormal', 0)} of {encounter_data.get('n_total', 0)} total lab rows; {unique_abnormal} unique HIGH/LOW tests; panels with HIGH/LOW: {', '.join(abnormal_panels) if abnormal_panels else 'none'}):

{compact_table}

Normal result count: {encounter_data.get('n_normal', 0)}

{caution_note}

Lifestyle suggestions: 6-8 bullets. Tie each food or activity bullet to the flagged tests above (for example "For high LDL and triglycerides: ..."). Include encouraged foods, limited foods, and a walking plan with minutes, days/week, and weekly hours.

{trend_block}Return the four sections defined in the JSON schema:
summary, lifestyle_suggestions, doctor_questions,
and trend_analysis (omit trend_analysis if no historical data given — use an empty list).
Write the summary as a note to the patient, not as a clinical assessment.
"""


def _format_abnormal_row(row: dict) -> str:
    low = row.get("ref_range_lower")
    high = row.get("ref_range_upper")
    if low is None and high is None:
        ref = "—"
    elif low is None:
        ref = f"≤ {high}"
    elif high is None:
        ref = f"≥ {low}"
    else:
        ref = f"{low} – {high}"
    unit = row.get("value_unit") or ""
    count = row.get("abnormal_count", 1)
    return (
        f"- {row.get('test_name')} | {row.get('lab_group')} | "
        f"{row.get('value_num')} {unit} | ref {ref} | "
        f"{row.get('status')} | {row.get('knowledge_source')} | "
        f"latest {row.get('charttime')} | {count} abnormal reading(s)"
    )
