"""Citation check: for every statement that cites sources, how much of its wording can be traced to those sources?

This is a transparent keyword-overlap check. It shows whether a cited source plausibly relates to the statement.
It does NOT prove that the source supports the claim - a human must still read the source."""
from __future__ import annotations

from .tools.library import tokens

STRONG, PARTIAL = 0.30, 0.12


def support_score(claim: str, source_texts: list[str]) -> float:
    ct = tokens(claim)
    if len(ct) < 2:
        return 0.0
    st: set[str] = set()
    for t in source_texts:
        st |= tokens(t)
    return len(ct & st) / len(ct)


def _level(ids: list[str], score: float) -> str:
    if not ids:
        return "unsourced"
    if score >= STRONG:
        return "supported"
    if score >= PARTIAL:
        return "partial"
    return "weak"


def check_claims(reg, monitoring, diagnosis, options, risk) -> list[dict]:
    items: list[tuple[str, str, list[str]]] = []
    for f in monitoring.findings:
        items.append(("Monitoring", f.text, f.source_ids))
    for h in diagnosis.hypotheses:
        items.append(("Possible cause", " ".join([h.name] + h.evidence_for), h.source_ids))
    for o in options:
        items.append((f"Option {o.key}", " ".join([o.title, o.description] + o.actions), o.source_ids))
    for po in risk.per_option:
        for fl in po.flags:
            items.append((f"Risk flag, option {po.option_key}", fl.text, fl.source_ids))
    out = []
    for section, claim, ids in items:
        if len(claim.strip()) < 8:
            continue
        texts = []
        for sid in ids:
            rec = reg.get(sid)
            if rec:
                texts.append(f"{rec.title} {rec.summary}")
        score = support_score(claim, texts) if texts else 0.0
        out.append({"section": section, "claim": claim.strip()[:220], "source_ids": list(ids),
                    "score": round(score, 2), "level": _level(ids, score)})
    return out


def summarize(checks: list[dict]) -> dict:
    n = len(checks)
    c = {k: sum(1 for x in checks if x["level"] == k) for k in ("supported", "partial", "weak", "unsourced")}
    c["total"] = n
    return c
