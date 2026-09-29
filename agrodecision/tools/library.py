"""Curated reference library (data/references.json) - searched by simple keyword overlap.

No embeddings, no API. The owner controls exactly which documents can be cited from here."""
from __future__ import annotations

import re

from ..config import load_json

_STOP = set("the a an and or of to in on for with is are be by as at from that this it its if any not must should may can "
            "have has had was were been leaf leaves plant plants".split())
_CACHE: list[dict] | None = None


def load_library() -> list[dict]:
    global _CACHE
    if _CACHE is None:
        try:
            data = load_json("references.json")
            _CACHE = [e for e in data.get("references", []) if e.get("id") and e.get("title")]
        except Exception:  # noqa: BLE001
            _CACHE = []
    return _CACHE


def tokens(text: str) -> set[str]:
    out = set()
    for w in re.findall(r"[a-z0-9]+", (text or "").lower()):
        if len(w) < 3 or w in _STOP:
            continue
        if len(w) > 4 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.add(w)
    return out


def search_library(query: str, k: int = 3, exclude: set[str] | None = None, min_score: int = 4) -> list[dict]:
    q = tokens(query)
    exclude = exclude or set()
    scored = []
    for e in load_library():
        if e["id"] in exclude:
            continue
        topics = tokens(" ".join(e.get("topics", [])))
        title = tokens(e["title"])
        summ = tokens(e.get("summary", ""))
        score = 3 * len(q & topics) + 2 * len(q & title) + len(q & summ)
        if score >= min_score:
            scored.append((score, e))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [e for _, e in scored[:k]]


def auto_refs(kinds: set[str], exclude: set[str] | None = None) -> list[dict]:
    exclude = exclude or set()
    return [e for e in load_library() if e.get("auto_for") in kinds and e["id"] not in exclude]


def citation_string(e: dict) -> str:
    parts = [e.get("authors", "").strip(), f"({e.get('year', 'n.d.')})." if e.get("year") else "", e["title"] + ".",
             e.get("publisher", "") + ".", e.get("url", "")]
    return " ".join(p for p in parts if p).replace("..", ".")


def source_args(e: dict) -> dict:
    return dict(kind="library", title=e["title"], summary=e.get("summary", ""), url=e.get("url", ""),
                publisher=e.get("publisher", ""), year=str(e.get("year", "")), source_type=e.get("source_type", ""),
                citation=citation_string(e))
