"""Markdown export of a report (with citations) for download / printing."""
from __future__ import annotations

from .schemas import CostBreakdown, Report


def _cite(ids: list[str]) -> str:
    return f" [{', '.join(ids)}]" if ids else " (model reasoning - no source)"


def to_markdown(rep: Report, costs: list[CostBreakdown] | None = None) -> str:
    costs = costs or rep.costs
    cur = rep.case.currency
    L: list[str] = []
    L.append("# AgroDecision AI - decision-support report")
    if rep.demo:
        L.append("\n> **DEMO MODE - sample output, not based on real data.**")
    c = rep.case
    L.append(f"\n**Crop:** {c.crop or '-'}  |  **Location:** {', '.join(x for x in [c.city, c.province, c.country] if x) or '-'}")
    L.append("\n## Summary\n" + (rep.summary_en.headline or "-"))
    L.append(f"\n**Most likely cause (NOT confirmed):** {rep.diagnosis.primary_hypothesis or '-'} "
             f"(evidence confidence: {rep.diagnosis.evidence_confidence})")
    L.append("\n## Data quality notes")
    L += [f"- {q}" for q in rep.data_quality] or ["- none"]
    L.append("\n## Possible causes")
    for h in rep.diagnosis.hypotheses:
        L.append(f"- **{h.name}** ({h.likelihood}){_cite(h.source_ids)}")
        for e in h.evidence_for:
            L.append(f"  - for: {e}")
        for e in h.evidence_against:
            L.append(f"  - against: {e}")
    L.append("\n## Options and estimated costs")
    L.append(f"| Option | Intervention cost | P_loss | Expected loss | Total exposure |\n|---|---|---|---|---|")
    for o in rep.options:
        cb = next((x for x in costs if x.option_key == o.key), None)
        if cb:
            L.append(f"| {o.key}: {o.title} | {cur} {cb.c_total:,.0f} | {cb.p_loss:.2f} | {cur} {cb.expected_loss:,.0f} | {cur} {cb.exposure:,.0f} |")
    L.append(f"\nPrices: {rep.prices_source}. Figures are estimates from user-configured prices and assumptions, not guarantees.")
    for o in rep.options:
        L.append(f"\n### Option {o.key}: {o.title}{_cite(o.source_ids)}\n{o.description}")
        L += [f"- action: {a}" for a in o.actions]
        L += [f"- assumption: {a}" for a in o.assumptions]
        if o.main_uncertainty:
            L.append(f"- main uncertainty: {o.main_uncertainty}")
    L.append("\n## Risk and compliance flags")
    for po in rep.risk.per_option:
        for f in po.flags:
            tag = "VERIFIED" if f.status == "verified" else "needs confirmation"
            L.append(f"- Option {po.option_key} [{tag}]: {f.text}{_cite(f.source_ids)}")
    L.append("\n## Critic review")
    L += [f"- ({i.severity}) {i.text}" for i in rep.critic.issues]
    if rep.critic.note_to_reviewer:
        L.append(f"\n**Note to reviewer:** {rep.critic.note_to_reviewer}")
    L.append("\n## Sources")
    for s in rep.sources:
        L.append(f"- **[{s['id']}]** {s['title']} - {s['reliability']} - retrieved {s['retrieved']} {s['url']}")
    L.append("\n---\nThis report supports, and does not replace, a qualified agronomist. Confirm any chemical use with an expert and local regulations.")
    return "\n".join(L)
