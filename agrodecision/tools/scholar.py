"""OpenAlex scholarly search.

Since February 2026 OpenAlex asks for a (free) API key: without one the daily allowance is tiny and shared
requests quickly return "429 Too Many Requests". Get a free key at https://openalex.org/settings/api and
put it in the app Secrets as OPENALEX_API_KEY. Without a key this step simply gets skipped when the limit is hit."""
from __future__ import annotations

import re
import time

import requests

URL = "https://api.openalex.org/works"


class ScholarUnavailable(RuntimeError):
    """Rate limit / budget used up. The analysis carries on without papers."""


_CACHE: dict[str, list[dict]] = {}
_BLOCKED_UNTIL = 0.0


def clean_query(text: str, max_words: int = 8) -> str:
    words = re.findall(r"[A-Za-z0-9\-]+", text or "")
    return " ".join(words[:max_words])


def _abstract(inv: dict | None, limit: int = 500) -> str:
    if not inv:
        return ""
    pos: list[tuple[int, str]] = []
    for word, idxs in inv.items():
        for i in idxs:
            pos.append((i, word))
    pos.sort()
    text = " ".join(w for _, w in pos)
    return text[:limit] + ("..." if len(text) > limit else "")


def search_papers(query: str, api_key: str | None = None, mailto: str | None = None, n: int = 4) -> list[dict]:
    global _BLOCKED_UNTIL
    q = clean_query(query)
    if not q:
        return []
    if q in _CACHE:
        return _CACHE[q]
    if time.monotonic() < _BLOCKED_UNTIL:
        raise ScholarUnavailable("OpenAlex's free limit was reached a moment ago.")
    params = {"search": q, "per-page": n, "select": "id,doi,title,publication_year,abstract_inverted_index"}
    if api_key:
        params["api_key"] = api_key
    elif mailto:
        params["mailto"] = mailto
    r = requests.get(URL, params=params, timeout=25)
    if r.status_code in (401, 403, 429):
        _BLOCKED_UNTIL = time.monotonic() + 600  # do not keep retrying for 10 minutes
        hint = ("Its free daily limit is used up or a key is required. Add a free OPENALEX_API_KEY in the app Secrets "
                "(get one at openalex.org/settings/api)." if not api_key else
                "The daily limit for your OPENALEX_API_KEY seems to be used up, or the key was rejected.")
        raise ScholarUnavailable(f"OpenAlex answered HTTP {r.status_code}. {hint}")
    r.raise_for_status()
    out = []
    for w in r.json().get("results", []) or []:
        abs_ = _abstract(w.get("abstract_inverted_index"))
        if not abs_:
            continue  # no abstract -> cannot support a claim
        out.append({"title": (w.get("title") or "")[:200], "year": w.get("publication_year"),
                    "url": w.get("doi") or w.get("id") or "", "abstract": abs_})
    _CACHE[q] = out
    return out
