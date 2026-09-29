"""Source registry: every piece of evidence gets an ID so that claims can be cited."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone

PREFIX = {
    "user": "U",        # typed/selected by the farmer or manager
    "photo": "P",       # description extracted from a photo (model-derived)
    "weather": "W",     # Open-Meteo
    "soil": "S",        # SoilGrids
    "web": "T",         # Tavily search on an allow-listed domain
    "scholar": "R",     # OpenAlex
    "org": "O",         # uploaded organisation document (SOP, lab report, ...)
    "default": "D",     # built-in placeholder data (prices, generic rules)
    "calc": "C",        # deterministic calculation done by the app
}

RELIABILITY = {
    "user": "user-stated",
    "photo": "model-derived (verify)",
    "weather": "public dataset (modelled)",
    "soil": "public dataset (250 m estimate)",
    "web": "public web page (check original)",
    "scholar": "published literature (abstract only)",
    "org": "user-provided document",
    "default": "placeholder - edit before relying on it",
    "calc": "calculated by the app",
}


@dataclass
class SourceRecord:
    id: str
    kind: str
    title: str
    url: str
    retrieved: str
    reliability: str
    summary: str


class SourceRegistry:
    def __init__(self) -> None:
        self._items: dict[str, SourceRecord] = {}
        self._counts: dict[str, int] = {}

    def add(self, kind: str, title: str, summary: str, url: str = "") -> str:
        self._counts[kind] = self._counts.get(kind, 0) + 1
        sid = f"{PREFIX[kind]}{self._counts[kind]}"
        self._items[sid] = SourceRecord(
            id=sid,
            kind=kind,
            title=title,
            url=url,
            retrieved=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            reliability=RELIABILITY.get(kind, ""),
            summary=summary.strip(),
        )
        return sid

    def has(self, sid: str) -> bool:
        return sid in self._items

    def get(self, sid: str) -> SourceRecord | None:
        return self._items.get(sid)

    def ids(self) -> list[str]:
        return list(self._items)

    def evidence_block(self, max_chars_each: int = 700, kinds: set[str] | None = None) -> str:
        """Text block given to agents. Agents may cite ONLY the IDs shown here."""
        lines = []
        for rec in self._items.values():
            if kinds and rec.kind not in kinds:
                continue
            body = rec.summary if len(rec.summary) <= max_chars_each else rec.summary[:max_chars_each] + "..."
            lines.append(f"[{rec.id}] ({rec.reliability}) {rec.title}: {body}")
        return "\n".join(lines) if lines else "(no evidence available)"

    def clean_ids(self, ids: list[str]) -> list[str]:
        """Drop citations that do not exist (prevents invented references)."""
        seen, out = set(), []
        for i in ids or []:
            i = str(i).strip().strip("[]")
            if i in self._items and i not in seen:
                seen.add(i)
                out.append(i)
        return out

    def to_list(self) -> list[dict]:
        return [asdict(r) for r in self._items.values()]
