"""Tavily web search restricted to an allow-list of agricultural domains.
Free plan: 1,000 credits/month, no card (check https://www.tavily.com/pricing)."""
from __future__ import annotations

import requests

from ..config import load_json

URL = "https://api.tavily.com/search"


def allowed_domains() -> list[str]:
    return load_json("allowed_domains.json")["domains"]


def web_search(query: str, api_key: str, max_results: int = 4) -> list[dict]:
    payload = {
        "query": query,
        "search_depth": "basic",
        "max_results": max_results,
        "include_domains": allowed_domains(),
        "include_answer": False,
    }
    r = requests.post(URL, json=payload, headers={"Authorization": f"Bearer {api_key}"}, timeout=30)
    r.raise_for_status()
    out = []
    for it in r.json().get("results", []) or []:
        out.append(
            {
                "title": (it.get("title") or "")[:160],
                "url": it.get("url", ""),
                "content": (it.get("content") or "")[:600],
            }
        )
    return out
