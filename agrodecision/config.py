"""Central settings. Values come from environment variables or Streamlit secrets."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RUNTIME_DIR = Path(os.environ.get("AGRO_RUNTIME_DIR", str(ROOT / "runtime_data")))
RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


def get_setting(name: str, default: str | None = None) -> str | None:
    """Read a setting from the environment first, then from Streamlit secrets."""
    val = os.environ.get(name)
    if val:
        return val
    try:
        import streamlit as st

        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # no secrets file, or not running under Streamlit
        pass
    return default


def _flag(name: str, default: bool = False) -> bool:
    v = get_setting(name)
    if v is None:
        return default
    return str(v).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    groq_api_key: str | None
    groq_base_url: str | None
    tavily_api_key: str | None
    openalex_mailto: str | None
    openalex_api_key: str | None
    access_code: str | None
    demo_mode: bool
    model_reasoning: str
    model_light: str
    model_vision: str
    model_translate: str
    reasoning_effort: str
    tpm_limit: int
    max_images: int
    max_upload_mb: int


def settings() -> Settings:
    return Settings(
        groq_api_key=get_setting("GROQ_API_KEY"),
        groq_base_url=get_setting("GROQ_BASE_URL"),  # only for tests / proxies
        tavily_api_key=get_setting("TAVILY_API_KEY"),
        openalex_mailto=get_setting("OPENALEX_MAILTO"),
        openalex_api_key=get_setting("OPENALEX_API_KEY"),
        access_code=get_setting("APP_ACCESS_CODE"),
        demo_mode=_flag("DEMO_MODE", False),
        # Model IDs change over time. Check https://console.groq.com/docs/rate-limits
        # and override these in secrets if a model is retired.
        model_reasoning=get_setting("MODEL_REASONING", "openai/gpt-oss-120b"),
        model_light=get_setting("MODEL_LIGHT", "openai/gpt-oss-20b"),
        model_vision=get_setting("MODEL_VISION", "qwen/qwen3.8-27b"),
        model_translate=get_setting("MODEL_TRANSLATE", "openai/gpt-oss-120b"),
        reasoning_effort=get_setting("REASONING_EFFORT", "low") or "",
        tpm_limit=int(get_setting("TPM_LIMIT", "8000") or 8000),
        max_images=int(get_setting("MAX_IMAGES", "3") or 3),
        max_upload_mb=int(get_setting("MAX_UPLOAD_MB", "10") or 10),
    )


def load_json(name: str):
    with open(DATA_DIR / name, "r", encoding="utf-8") as f:
        return json.load(f)


COUNTRIES = {
    "Pakistan": "PK",
    "India": "IN",
    "Afghanistan": "AF",
    "Bangladesh": "BD",
    "Iran": "IR",
    "Saudi Arabia": "SA",
    "United Arab Emirates": "AE",
    "Turkey": "TR",
    "Egypt": "EG",
    "Kenya": "KE",
    "Nigeria": "NG",
    "United Kingdom": "GB",
    "United States": "US",
    "Other / any": "",
}
