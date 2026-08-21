"""OpenAI client: one structured call per encounter (Sections 12, 16, 19.7)."""

from __future__ import annotations

import json
import time
from typing import Any

import pandas as pd
from openai import (
    APIConnectionError,
    APITimeoutError,
    AuthenticationError,
    OpenAI,
    RateLimitError,
)
from openai import APIError

from config import ConfigError, get_openai_settings
from db import get_encounter_meta, get_lab_results
from llm.prompts import (
    LAB_INTERPRETATION_SCHEMA,
    PROMPT_REVISION,
    build_system_prompt,
    build_user_prompt,
)

RETRYABLE = (APITimeoutError, RateLimitError, APIConnectionError)


def _panel_list(meta: dict) -> list[str]:
    panels = []
    if meta.get("has_cbc"):
        panels.append("CBC")
    if meta.get("has_metabolic"):
        panels.append("METABOLIC")
    if meta.get("has_lipid"):
        panels.append("LIPID")
    if meta.get("has_a1c"):
        panels.append("A1C")
    return panels


class LLMError(Exception):
    """User-facing failure. Never include secrets in the message."""

    def __init__(self, user_message: str):
        self.user_message = user_message
        super().__init__(user_message)


def encounter_cache_key(subject_id: int, hadm_id: int) -> str:
    return f"{int(subject_id)}:{int(hadm_id)}|{PROMPT_REVISION}"


def has_cached_summary(
    subject_id: int | None = None,
    hadm_id: int | None = None,
    *,
    cache_key: str | None = None,
) -> bool:
    import streamlit as st

    key = cache_key
    if key is None and subject_id is not None and hadm_id is not None:
        key = encounter_cache_key(subject_id, hadm_id)
    if not key:
        return False
    if "|" not in key:
        key = f"{key}|{PROMPT_REVISION}"
    cache = st.session_state.get("ai_cache") or {}
    return key in cache


def get_cached_summary(
    subject_id: int | None = None,
    hadm_id: int | None = None,
    *,
    cache_key: str | None = None,
) -> dict | None:
    import streamlit as st

    key = cache_key
    if key is None and subject_id is not None and hadm_id is not None:
        key = encounter_cache_key(subject_id, hadm_id)
    if not key:
        return None
    if "|" not in key:
        key = f"{key}|{PROMPT_REVISION}"
    cache = st.session_state.get("ai_cache") or {}
    return cache.get(key)


def assemble_encounter_data(meta: dict, labs: pd.DataFrame) -> dict:
    """Compact HIGH/LOW rows for the prompt (latest value per test_name)."""
    n_total = int(len(labs))
    n_normal = int((labs["status"] == "NORMAL").sum())
    abn = labs[labs["status"].isin(["HIGH", "LOW"])].copy()
    n_abnormal = int(len(abn))

    compact: list[dict[str, Any]] = []
    if not abn.empty:
        abn["charttime"] = abn["charttime"].astype(str)
        sorted_abn = abn.sort_values("charttime")
        counts = sorted_abn.groupby("test_name").size().to_dict()
        latest = sorted_abn.groupby("test_name", as_index=False).tail(1)
        for _, row in latest.iterrows():
            compact.append(
                {
                    "test_name": row["test_name"],
                    "lab_group": row["lab_group"],
                    "value_num": None if pd.isna(row["value_num"]) else row["value_num"],
                    "value_unit": "" if pd.isna(row["value_unit"]) else row["value_unit"],
                    "ref_range_lower": (
                        None
                        if pd.isna(row["ref_range_lower"])
                        else row["ref_range_lower"]
                    ),
                    "ref_range_upper": (
                        None
                        if pd.isna(row["ref_range_upper"])
                        else row["ref_range_upper"]
                    ),
                    "status": row["status"],
                    "knowledge_source": row["knowledge_source"],
                    "charttime": row["charttime"],
                    "abnormal_count": int(counts.get(row["test_name"], 1)),
                }
            )

    unique_abnormal = len(compact)
    panels_abnormal = {row["lab_group"] for row in compact if row.get("lab_group")}
    many_unique = unique_abnormal >= 8
    many_rows = n_abnormal >= 40
    multi_panel = unique_abnormal >= 6 and len(panels_abnormal) >= 3
    caution_level = (
        "high" if (many_unique or many_rows or multi_panel) else "routine"
    )

    return {
        "gender": meta.get("gender"),
        "anchor_age": meta.get("anchor_age"),
        "panel_list": _panel_list(meta),
        "n_abnormal": n_abnormal,
        "n_total": n_total,
        "n_normal": n_normal,
        "unique_abnormal": unique_abnormal,
        "abnormal_panels": sorted(panels_abnormal),
        "caution_level": caution_level,
        "abnormal_rows": compact,
    }


def call_openai(system_prompt: str, user_prompt: str) -> dict:
    """Single API call with json_schema output. Retry once on timeout/rate-limit."""
    try:
        api_key, model = get_openai_settings()
    except ConfigError as exc:
        raise LLMError(str(exc)) from None

    client = OpenAI(api_key=api_key)
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "lab_interpretation",
                        "strict": True,
                        "schema": LAB_INTERPRETATION_SCHEMA,
                    },
                },
                temperature=0.2,
                timeout=90.0,
            )
            content = response.choices[0].message.content
            if not content:
                raise LLMError(
                    "The model returned an empty summary. Please try again."
                )
            parsed = json.loads(content)
            if not isinstance(parsed, dict):
                raise LLMError(
                    "The summary was not valid structured data. Please try again."
                )
            return parsed
        except LLMError:
            raise
        except AuthenticationError:
            raise LLMError(
                "The OpenAI API key looks invalid. Check app/.env "
                "(do not share that file) and try again."
            ) from None
        except RETRYABLE as exc:
            last_error = exc
            if attempt == 0:
                time.sleep(2)
                continue
            raise LLMError(
                "Summary temporarily unavailable, please try again. "
                "Your extracted results are still visible."
            ) from None
        except APIError:
            raise LLMError(
                "The summary service returned an error. Please try again."
            ) from None
        except json.JSONDecodeError:
            raise LLMError(
                "The summary could not be read. Please try again."
            ) from None
        except Exception:
            raise LLMError(
                "Something went wrong while generating the summary. "
                "Please try again. Your extracted results are still visible."
            ) from None

    raise LLMError(
        "Summary temporarily unavailable, please try again."
    ) from last_error


def get_cached_or_generate(
    encounter_key: str,
    encounter_data: dict,
    trend_data: list | None = None,
) -> dict:
    """Session-state cache wrapper (Section 12.3). Does not call OpenAI on a hit."""
    import streamlit as st

    cache = st.session_state.setdefault("ai_cache", {})
    if "|" not in encounter_key:
        encounter_key = f"{encounter_key}|{PROMPT_REVISION}"
    if encounter_key in cache:
        return cache[encounter_key]

    result = call_openai(
        build_system_prompt(),
        build_user_prompt(encounter_data, trend_data),
    )
    cache[encounter_key] = result
    st.session_state["ai_cache"] = cache
    return result


def generate_for_encounter(
    subject_id: int,
    hadm_id: int,
    *,
    labs: pd.DataFrame | None = None,
    meta: dict | None = None,
    cache_key: str | None = None,
) -> dict:
    """Build encounter payload, then cache or call OpenAI once."""
    if meta is None:
        meta = get_encounter_meta(subject_id, hadm_id)
    if meta is None:
        raise LLMError("That encounter was not found in the demo database.")
    if labs is None:
        labs = get_lab_results(subject_id, hadm_id)
    if labs is None or labs.empty:
        raise LLMError("No lab results were found for this encounter.")
    payload = assemble_encounter_data(meta, labs)
    return get_cached_or_generate(
        cache_key or encounter_cache_key(subject_id, hadm_id), payload
    )
