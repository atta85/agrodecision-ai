"""Connection self-test: three tiny checks that show exactly where a problem is."""
from __future__ import annotations

import importlib.util
import sys

from . import __version__
from .config import settings


def run_selftest() -> list[tuple[str, bool, str]]:
    s = settings()
    out: list[tuple[str, bool, str]] = []
    out.append(("Build / Python", True, f"build {__version__}, Python {sys.version_info.major}.{sys.version_info.minor}"))
    out.append(("LiteLLM installed (should not matter)", True, "yes" if importlib.util.find_spec("litellm") else "no"))
    if not s.groq_api_key:
        out.append(("GROQ_API_KEY present", False, "missing - add it in the app Secrets"))
        return out
    out.append(("GROQ_API_KEY present", True, "yes"))
    from .llm import chat_completion

    try:
        reply = chat_completion(s.model_light, [{"role": "user", "content": "Reply with the single word: ok"}], max_tokens=200)
        out.append((f"Direct Groq call ({s.model_light})", True, f"reply: {reply[:60]!r}"))
    except Exception as e:  # noqa: BLE001
        out.append((f"Direct Groq call ({s.model_light})", False, str(e)[:500]))
        return out
    try:
        from .agents import NarrativeOut, run_agent_json
        from .llm import make_crew_llm

        llm_cls = type(make_crew_llm(s.model_light)).__name__
        res = run_agent_json("cost_review", 'Reply with exactly this JSON: {"notes": ["ok"]}', NarrativeOut, 300)
        out.append((f"CrewAI agent call (LLM class: {llm_cls})", True, f"notes: {res.notes}"))
    except Exception as e:  # noqa: BLE001
        out.append(("CrewAI agent call", False, str(e)[:500]))
    return out
