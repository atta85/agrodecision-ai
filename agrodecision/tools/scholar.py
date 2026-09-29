"""OpenAlex scholarly search (free, no key; a contact e-mail via OPENALEX_MAILTO is polite)."""
from __future__ import annotations

import requests

URL = "https://api.openalex.org/works"


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


def search_papers(query: str, mailto: str | None = None, n: int = 4) -> list[dict]:
    params = {
        "search": query,
        "per-page": n,
        "select": "id,doi,title,publication_year,abstract_inverted_index",
    }
    if mailto:
        params["mailto"] = mailto
    r = requests.get(URL, params=params, timeout=25)
    r.raise_for_status()
    out = []
    for w in r.json().get("results", []) or []:
        abs_ = _abstract(w.get("abstract_inverted_index"))
        if not abs_:
            continue  # no abstract -> cannot support a claim
        out.append(
            {
                "title": (w.get("title") or "")[:200],
                "year": w.get("publication_year"),
                "url": w.get("doi") or w.get("id") or "",
                "abstract": abs_,
            }
        )
    return out
