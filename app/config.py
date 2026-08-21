"""Load OpenAI settings from app/.env (Section 19.9).

Never log or print the API key.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

APP_DIR = Path(__file__).resolve().parent
DEFAULT_MODEL = "gpt-4o-mini"
ENV_PATH = APP_DIR / ".env"


class ConfigError(Exception):
    """Missing or unusable OpenAI configuration — safe to show in the UI."""


def _load_env() -> None:
    load_dotenv(ENV_PATH, override=False)


def get_openai_settings() -> tuple[str, str]:
    """Return (api_key, model). Raises ConfigError if the key is missing."""
    _load_env()
    api_key = (os.getenv("OPENAI_API_KEY") or "").strip()
    if not api_key:
        raise ConfigError(
            "OPENAI_API_KEY is not set. Create app/.env with "
            "OPENAI_API_KEY=... (see .env.example). The Generate AI Summary "
            "button stays disabled until a key is present."
        )
    model = (os.getenv("OPENAI_MODEL") or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return api_key, model


def openai_key_configured() -> bool:
    try:
        get_openai_settings()
        return True
    except ConfigError:
        return False
