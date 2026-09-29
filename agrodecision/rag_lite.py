"""Tiny keyword retrieval over uploaded SOP text. No embeddings, no extra API."""
from __future__ import annotations

import re

_STOP = set(
    "the a an and or of to in on for with is are be by as at from that this it its if any not must should may can".split()
)


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[A-Za-z0-9\u0600-\u06FF]+", text.lower()) if t not in _STOP and len(t) > 2]


def chunk_text(text: str, size: int = 700, overlap: int = 100) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    chunks, i = [], 0
    while i < len(text):
        chunks.append(text[i : i + size])
        i += size - overlap
    return chunks


def top_chunks(text: str, query: str, k: int = 4) -> list[str]:
    q = set(_tokens(query))
    scored = []
    for ch in chunk_text(text):
        toks = set(_tokens(ch))
        score = len(q & toks)
        if score:
            scored.append((score, ch))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored[:k]]
