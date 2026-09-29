"""Everything that talks to Groq.

Design decision: the app calls Groq DIRECTLY with the official `groq` SDK. CrewAI agents use the small
`GroqLLM` class below instead of CrewAI's LiteLLM route. Reasons:
  * CrewAI adds private message keys (e.g. `cache_breakpoint`) that Groq rejects; here every message is
    rebuilt as {role, content} before it leaves the app, so unknown keys can never be sent.
  * fewer dependencies (no litellm), fewer version clashes.
  * one place for the token-per-minute limiter, retries and error messages.
"""
from __future__ import annotations

import json
import re
import threading
import time
from collections import deque
from typing import Any

from crewai import BaseLLM

from .config import settings

ALLOWED_MESSAGE_KEYS = ("role", "content")


class LLMOutputError(RuntimeError):
    pass


class MissingKeyError(RuntimeError):
    pass


class GroqCallError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- limiter
class TokenRateLimiter:
    def __init__(self, tpm_limit: int) -> None:
        self.limit = tpm_limit
        self._events: deque[tuple[float, int]] = deque()
        self._lock = threading.Lock()

    def wait(self, tokens: int, on_wait=None) -> None:
        tokens = max(1, int(tokens))
        with self._lock:
            while True:
                now = time.monotonic()
                while self._events and now - self._events[0][0] >= 60:
                    self._events.popleft()
                used = sum(t for _, t in self._events)
                if used + tokens <= self.limit or not self._events:
                    self._events.append((now, tokens))
                    return
                wait_s = 60 - (now - self._events[0][0]) + 0.25
                if on_wait:
                    on_wait(wait_s)
                time.sleep(max(0.25, wait_s))


_limiter: TokenRateLimiter | None = None
_status_cb = None  # optional callable(str) used by the UI to show waiting messages


def set_status_callback(cb) -> None:
    global _status_cb
    _status_cb = cb


def get_limiter() -> TokenRateLimiter:
    global _limiter
    limit = settings().tpm_limit
    if _limiter is None or _limiter.limit != limit:
        _limiter = TokenRateLimiter(limit)
    return _limiter


def throttle(tokens: int) -> None:
    def note(s: float) -> None:
        if _status_cb:
            _status_cb(f"Waiting {s:.0f}s to stay inside the free-tier token limit...")

    get_limiter().wait(tokens, on_wait=note)


def estimate_tokens(text: str) -> int:
    ascii_chars = sum(1 for c in text if ord(c) < 128)
    other = len(text) - ascii_chars
    return int(ascii_chars / 3.6 + other / 1.6) + 20


# ----------------------------------------------------------------------------- helpers
def is_rate_limit(err: Exception) -> bool:
    s = str(err).lower()
    return any(x in s for x in ("rate limit", "rate_limit", "429", "tokens per minute", "too many requests"))


def parse_retry_seconds(msg: str) -> float | None:
    m = re.search(r"try again in\s+(?:(\d+)m)?\s*(\d+(?:\.\d+)?)(ms|s)", msg)
    if not m:
        return None
    mins = float(m.group(1) or 0)
    val = float(m.group(2))
    secs = val / 1000 if m.group(3) == "ms" else val
    return mins * 60 + secs + 1.0


def clean_reply(text: str) -> str:
    """Remove hidden 'thinking' blocks that some models put inside the reply."""
    if not text:
        return ""
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"^.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)  # unmatched closing tag
    return text.strip()


def extract_json(text: str) -> dict:
    """Pull the first JSON object out of a model reply (handles code fences, chatter)."""
    text = clean_reply(text)
    if not text:
        raise ValueError("empty reply")
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE | re.MULTILINE).strip()
    start = t.find("{")
    if start == -1:
        raise ValueError("no JSON object found")
    depth, in_str, esc = 0, False, False
    for i in range(start, len(t)):
        ch = t[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                chunk = t[start : i + 1]
                try:
                    return json.loads(chunk)
                except json.JSONDecodeError:
                    return json.loads(re.sub(r",\s*([}\]])", r"\1", chunk))  # trailing commas
    raise ValueError("unterminated JSON object")


def sanitize_messages(messages: Any) -> list[dict]:
    """Rebuild messages so that ONLY keys Groq understands are sent."""
    if isinstance(messages, str):
        return [{"role": "user", "content": messages}]
    out = []
    for m in messages or []:
        if not isinstance(m, dict):
            continue
        role = m.get("role", "user")
        if role not in ("system", "user", "assistant"):
            role = "user"
        content = m.get("content", "")
        if content is None:
            content = ""
        if isinstance(content, list):  # vision content parts: keep type/text/image_url only
            parts = []
            for p in content:
                if isinstance(p, dict) and p.get("type") == "text":
                    parts.append({"type": "text", "text": str(p.get("text", ""))})
                elif isinstance(p, dict) and p.get("type") == "image_url":
                    parts.append({"type": "image_url", "image_url": p["image_url"]})
            content = parts
        out.append({"role": role, "content": content})
    return out


def _msg_tokens(messages: list[dict], image_count: int) -> int:
    n = 0
    for m in messages:
        c = m["content"]
        n += estimate_tokens(c if isinstance(c, str) else " ".join(p.get("text", "") for p in c if p.get("type") == "text"))
    return n + 8 * len(messages) + image_count * 2048


# ----------------------------------------------------------------------------- Groq call
_client_cache: dict[tuple, Any] = {}


def _client():
    s = settings()
    if not s.groq_api_key:
        raise MissingKeyError("GROQ_API_KEY is not set. Add it in Streamlit secrets (or turn on DEMO_MODE).")
    key = (s.groq_api_key, s.groq_base_url)
    if key not in _client_cache:
        from groq import Groq

        kwargs: dict[str, Any] = dict(api_key=s.groq_api_key, timeout=90, max_retries=0)
        if s.groq_base_url:
            kwargs["base_url"] = s.groq_base_url
        _client_cache[key] = Groq(**kwargs)
    return _client_cache[key]


def _friendly(err: Exception, model: str) -> GroqCallError:
    msg = str(err)
    low = msg.lower()
    if any(x in low for x in ("model_not_found", "does not exist", "decommissioned", "not found")) and "model" in low:
        return GroqCallError(f"Groq does not accept the model '{model}'. Open console.groq.com/docs/rate-limits, "
                             f"pick a current model ID and set it in the app Secrets (MODEL_REASONING / MODEL_LIGHT / "
                             f"MODEL_VISION / MODEL_TRANSLATE). Original message: {msg[:300]}")
    if "invalid api key" in low or "401" in low:
        return GroqCallError("Groq rejected the API key. Check GROQ_API_KEY in the app Secrets.")
    return GroqCallError(msg[:600])


def chat_completion(model: str, messages: Any, max_tokens: int = 800, temperature: float = 0.2,
                    stop: list[str] | None = None, image_count: int = 0) -> str:
    """One Groq chat call with throttling, retries and clean output. Returns the reply text."""
    s = settings()
    msgs = sanitize_messages(messages)
    in_tokens = _msg_tokens(msgs, image_count)
    budget = s.tpm_limit - 250
    if in_tokens >= budget:
        raise GroqCallError(f"The request (about {in_tokens} tokens) is larger than the per-minute limit "
                            f"({s.tpm_limit}). Use fewer/smaller photos or shorter text.")
    max_tokens = int(min(max_tokens, budget - in_tokens))
    client = _client()
    use_effort = bool(s.reasoning_effort) and model.startswith("openai/gpt-oss")
    empty_retry = False
    rate_tries = 0
    while True:
        throttle(in_tokens + int(max_tokens * 0.8))
        kwargs: dict[str, Any] = dict(model=model, messages=msgs, temperature=temperature, max_tokens=max_tokens)
        if stop:
            kwargs["stop"] = stop[:4]
        if use_effort:
            kwargs["extra_body"] = {"reasoning_effort": s.reasoning_effort}
        try:
            resp = client.chat.completions.create(**kwargs)
        except Exception as e:  # noqa: BLE001
            low = str(e).lower()
            if use_effort and "reasoning_effort" in low:
                use_effort = False      # this model/API does not take the parameter: retry without it
                continue
            if is_rate_limit(e) and rate_tries < 4:
                rate_tries += 1
                time.sleep(parse_retry_seconds(str(e)) or 20)
                continue
            raise _friendly(e, model) from e
        choice = resp.choices[0]
        text = clean_reply(choice.message.content or "")
        if not text and not empty_retry:
            # reasoning models can spend the whole budget thinking: retry once with more room
            empty_retry = True
            max_tokens = int(min(max_tokens * 1.6, budget - in_tokens))
            continue
        if not text:
            raise GroqCallError(f"Groq returned an empty reply from model '{model}' (finish_reason="
                                f"{getattr(choice, 'finish_reason', '?')}). Try REASONING_EFFORT = \"low\" or a different model in Secrets.")
        return text


def chat_text(model: str, messages: list[dict], max_tokens: int = 800, temperature: float = 0.2,
              image_count: int = 0) -> str:
    return chat_completion(model, messages, max_tokens=max_tokens, temperature=temperature, image_count=image_count)


# ----------------------------------------------------------------------------- CrewAI adapter
class GroqLLM(BaseLLM):
    """CrewAI LLM that sends requests straight to Groq (no LiteLLM)."""

    def __init__(self, model: str, max_tokens: int = 1800, temperature: float = 0.2) -> None:
        super().__init__(model=model, temperature=temperature, max_tokens=max_tokens, provider="groq")

    def call(self, messages, tools=None, callbacks=None, available_functions=None, from_task=None,
             from_agent=None, response_model=None):
        stop = [x for x in (self.stop or []) if isinstance(x, str) and x][:4] or None
        return chat_completion(self.model, messages, max_tokens=int(self.max_tokens or 1800),
                               temperature=float(self.temperature or 0.2), stop=stop)

    def supports_function_calling(self) -> bool:
        return False

    def supports_stop_words(self) -> bool:
        return True

    def get_context_window_size(self) -> int:
        return 128000


def make_crew_llm(model: str, max_tokens: int = 1800) -> GroqLLM:
    if not settings().groq_api_key:
        raise MissingKeyError("GROQ_API_KEY is not set. Add it in Streamlit secrets (or turn on DEMO_MODE).")
    return GroqLLM(model=model, max_tokens=max_tokens)


# ----------------------------------------------------------------------------- safety net for LiteLLM
def _strip_extra_keys(messages):
    if isinstance(messages, list):
        for m in messages:
            if isinstance(m, dict):
                m.pop("cache_breakpoint", None)
    return messages


def _patch_litellm_if_present() -> bool:
    """Belt and braces: this app does not use LiteLLM, but if it happens to be installed and some CrewAI
    component still routes a request through it, remove the private key Groq rejects."""
    try:
        import litellm
    except Exception:  # noqa: BLE001
        return False
    if getattr(litellm, "_agro_patched", False):
        return True
    orig = litellm.completion

    def completion(*args, **kwargs):
        if "messages" in kwargs:
            kwargs["messages"] = _strip_extra_keys(kwargs["messages"])
        return orig(*args, **kwargs)

    litellm.completion = completion
    orig_a = getattr(litellm, "acompletion", None)
    if orig_a is not None:
        async def acompletion(*args, **kwargs):
            if "messages" in kwargs:
                kwargs["messages"] = _strip_extra_keys(kwargs["messages"])
            return await orig_a(*args, **kwargs)

        litellm.acompletion = acompletion
    litellm._agro_patched = True
    return True


LITELLM_PATCHED = _patch_litellm_if_present()
