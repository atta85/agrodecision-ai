"""Language handling: input -> English (agents work in English), English -> user's language.

Two short calls only, to protect the free-tier token budget.
"""
from __future__ import annotations

import csv
import json

from .config import DATA_DIR, settings
from .llm import chat_text, extract_json

LANG_NAMES = {
    "en": "English",
    "ur": "Urdu (Nastaliq script, as used in Pakistan)",
    "pa": "Punjabi in Shahmukhi script (Perso-Arabic script, as used in Pakistan)",
    "sd": "Sindhi (Perso-Arabic script, as used in Pakistan)",
    "ur_roman": "Roman Urdu (Urdu written in Latin letters)",
}


def glossary_hint(max_rows: int = 30) -> str:
    try:
        with open(DATA_DIR / "glossary.csv", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))[:max_rows]
        return "; ".join(f"{r['english']} = {r['urdu']} / {r['roman_urdu']}" for r in rows)
    except Exception:  # noqa: BLE001
        return ""


def understand_input(lang: str, description: str, structured_en: str) -> dict:
    """Return {'english_text': str, 'understood_local': str}.

    understood_local is a short read-back in the farmer's language so that they can confirm
    we understood correctly. For English input no model call is needed."""
    if lang == "en" or not description.strip():
        return {"english_text": description.strip(), "understood_local": ""}
    s = settings()
    if s.demo_mode:
        return {"english_text": "(demo) " + description.strip(), "understood_local": "(demo) " + description.strip()[:120]}
    sys_msg = (
        "You are a careful agricultural translator for farmers in Pakistan. "
        "Translate faithfully. Do not add advice, diagnoses or facts. Keep numbers and units unchanged. "
        "Reply with ONE JSON object only."
    )
    user = (
        f"The farmer wrote in {LANG_NAMES.get(lang, lang)}.\n"
        f"Farmer text: \"\"\"{description}\"\"\"\n"
        f"Structured answers already selected by the farmer (English): {structured_en}\n"
        f"Glossary hints: {glossary_hint()}\n\n"
        'Return JSON: {"english_text": "<faithful English translation of the farmer text>", '
        f'"understood_local": "<2-3 short sentences in {LANG_NAMES.get(lang, lang)} saying what you understood, '
        'so the farmer can confirm - use simple words>"}'
    )
    raw = chat_text(s.model_translate, [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}],
                    max_tokens=700)
    data = extract_json(raw)
    return {
        "english_text": str(data.get("english_text", "")).strip(),
        "understood_local": str(data.get("understood_local", "")).strip(),
    }


def translate_summary(lang: str, summary: dict) -> dict:
    """Translate the short farmer summary (dict of strings/lists) into the chosen language."""
    if lang == "en":
        return summary
    s = settings()
    if s.demo_mode:
        return summary  # demo: no translation call
    sys_msg = (
        "You translate short agricultural advice summaries for farmers. Use simple, clear words. "
        "Keep numbers, currency codes, option letters (A, B, C) and product/chemical names unchanged. "
        "Do not add or remove advice. Reply with ONE JSON object having exactly the same keys and structure."
    )
    user = f"Translate every string value into {LANG_NAMES.get(lang, lang)}.\nJSON:\n{json.dumps(summary, ensure_ascii=False)}"
    raw = chat_text(s.model_translate, [{"role": "system", "content": sys_msg}, {"role": "user", "content": user}],
                    max_tokens=1400)
    return extract_json(raw)
