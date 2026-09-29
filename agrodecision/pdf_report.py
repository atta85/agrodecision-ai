"""PDF export of a finished analysis (PyMuPDF only - no extra dependency, no AI tokens).

English is always complete. The farmer-language summary is added for Urdu, Punjabi (Shahmukhi) and Roman Urdu.
Sindhi letters are NOT reliably drawn by the built-in PDF font, so a Sindhi summary is left out of the PDF
(it stays on screen) rather than printing wrong letters."""
from __future__ import annotations

import io
from datetime import datetime, timezone
from html import escape as _e

import pymupdf

from . import __version__
from .schemas import CostBreakdown, Report

CSS = """
body { font-family: sans-serif; font-size: 9.5pt; line-height: 1.35; color: #1b1b1b; }
h1 { font-size: 19pt; color: #1b5e20; margin: 0 0 2pt 0; }
h2 { font-size: 13pt; color: #1b5e20; margin: 12pt 0 3pt 0; border-bottom: 1pt solid #a5d6a7; }
h3 { font-size: 10.5pt; margin: 8pt 0 2pt 0; }
p { margin: 2pt 0 4pt 0; }
li { margin: 0 0 2pt 0; }
table { border-collapse: collapse; width: 100%; margin: 3pt 0 6pt 0; }
th { background-color: #e8f5e9; text-align: left; font-size: 8.5pt; }
td, th { border: 0.6pt solid #9e9e9e; padding: 2.5pt 3pt; font-size: 8.5pt; vertical-align: top; }
.note { color: #555555; font-size: 8.5pt; }
.warn { background-color: #fff8e1; border: 0.6pt solid #f9a825; padding: 3pt; }
.demo { background-color: #ffebee; border: 0.8pt solid #c62828; padding: 4pt; font-weight: bold; }
.ok { color: #2e7d32; font-weight: bold; } .mid { color: #ef6c00; font-weight: bold; } .bad { color: #c62828; font-weight: bold; }
.id { font-family: monospace; color: #0d47a1; }
.rtl { direction: rtl; text-align: right; font-size: 11pt; width: 100%; }
.rtl p { direction: rtl; text-align: right; width: 100%; }
"""

RTL_LANGS = {"ur", "pa"}
LANG_NAMES = {"en": "English", "ur": "Urdu", "pa": "Punjabi (Shahmukhi)", "sd": "Sindhi", "ur_roman": "Roman Urdu"}


def _ids(ids: list[str]) -> str:
    return f' <span class="id">[{_e(", ".join(ids))}]</span>' if ids else ' <span class="note">(model reasoning, no source)</span>'


def _ul(items: list[str]) -> str:
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>" if items else ""


def _money(v: float, cur: str) -> str:
    return f"{cur} {v:,.0f}"


def _link(url: str) -> str:
    return f'<a href="{_e(url)}">{_e(url)}</a>' if url else ""


def build_html(rep: Report, costs: list[CostBreakdown] | None, decisions: list[dict] | None, case_id: str,
               lang: str | None = None) -> str:
    costs = costs or rep.costs
    decisions = decisions or []
    c = rep.case
    cur = c.currency
    lang = lang or c.language
    h: list[str] = []
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    h.append("<h1>AgroDecision AI - decision-support report</h1>")
    h.append(f'<p class="note">Case {_e(case_id or "-")} | generated {now} | app build {__version__}</p>')
    if rep.demo:
        h.append('<p class="demo">DEMO MODE - sample output, not based on real data.</p>')
    loc = ", ".join(x for x in [c.city, c.province, c.country] if x) or "-"
    area = f"{c.area:g} {c.area_unit}" if c.area else "-"
    h.append(f"<p><b>Crop:</b> {_e(c.crop or '-')} &nbsp; <b>Stage:</b> {_e(c.growth_stage or '-')} &nbsp; <b>Area:</b> {_e(area)} &nbsp; "
             f"<b>Location:</b> {_e(loc)}</p>")

    # ---- summary
    s = rep.summary_en
    h.append("<h2>1. Summary</h2>")
    if s.headline:
        h.append(f"<p><b>{_e(s.headline)}</b></p>")
    h.append(f"<p><b>Most likely cause (NOT confirmed):</b> {_e(rep.diagnosis.primary_hypothesis or '-')} "
             f"- evidence confidence: {_e(rep.diagnosis.evidence_confidence)}</p>")
    if s.likely_cause_plain:
        h.append(f"<p>{_e(s.likely_cause_plain)}</p>")
    for w in s.warnings:
        h.append(f'<p class="warn">Warning: {_e(w)}</p>')
    if s.next_steps:
        h.append("<h3>Next steps</h3>" + _ul([_e(x) for x in s.next_steps]))

    loc_sum = rep.summary_local
    if loc_sum and lang != "en":
        if lang == "sd":
            h.append('<p class="note">A Sindhi summary was produced on screen. It is not printed in this PDF because the built-in PDF '
                     'font cannot draw all Sindhi letters correctly.</p>')
        else:
            rtl = lang in RTL_LANGS
            h.append(f"<h3>{_e(LANG_NAMES.get(lang, lang))} summary - machine-translated, please have it checked</h3>")
            box = ['<div class="rtl">' if rtl else "<div>"]
            if loc_sum.headline:
                box.append(f"<p><b>{_e(loc_sum.headline)}</b></p>")
            if loc_sum.likely_cause_plain:
                box.append(f"<p>{_e(loc_sum.likely_cause_plain)}</p>")
            for o in loc_sum.options_plain:
                box.append(f"<p>{_e(o.key)}: {_e(o.title)} - {_e(o.one_line)}</p>")
            for x in loc_sum.next_steps:
                box.append(f"<p>\u2022 {_e(x)}</p>")
            for x in loc_sum.warnings:
                box.append(f"<p>\u26a0 {_e(x)}</p>")
            box.append("</div>")
            h.append("".join(box))

    # ---- data quality
    h.append("<h2>2. What this analysis is based on</h2>")
    h.append(_ul([_e(q) for q in rep.data_quality] + [_e("Warning: " + w) for w in rep.warnings]) or "<p>-</p>")

    # ---- causes
    h.append("<h2>3. Possible causes</h2>")
    for hy in rep.diagnosis.hypotheses:
        h.append(f"<h3>{_e(hy.name)} <span class='note'>({_e(hy.likelihood)})</span>{_ids(hy.source_ids)}</h3>")
        h.append(_ul([f"for: {_e(x)}" for x in hy.evidence_for] + [f"against: {_e(x)}" for x in hy.evidence_against]))
    if rep.diagnosis.additional_evidence_needed:
        h.append("<h3>Evidence that would help</h3>" + _ul([_e(x) for x in rep.diagnosis.additional_evidence_needed]))
    if rep.monitoring.findings:
        h.append("<h3>Monitoring findings</h3>" + _ul([f"{_e(f.text)}{_ids(f.source_ids)}" for f in rep.monitoring.findings]))

    # ---- options and costs
    h.append("<h2>4. Options and estimated costs</h2>")
    h.append('<p class="note">Formulas: intervention cost = materials + labour + equipment + operation + diagnostics; '
             'expected loss = P(loss) x value at risk; total exposure = intervention cost + expected loss. '
             f"Prices: {_e(rep.prices_source)}. P(loss) is an assumption, not a measurement. Estimates, not forecasts.</p>")
    rows = ["<tr><th>Option</th><th>Intervention cost</th><th>P(loss)</th><th>Expected loss</th><th>Total exposure</th><th>Delay (days)</th></tr>"]
    sup = {x.option_key: x for x in rep.supply}
    for o in rep.options:
        cb = next((x for x in costs if x.option_key == o.key), None)
        if not cb:
            continue
        delay = sup[o.key].est_delay_days if o.key in sup else o.delay_days
        rows.append(f"<tr><td><b>{_e(o.key)}</b>: {_e(o.title)}</td><td>{_money(cb.c_total, cur)}</td><td>{cb.p_loss:.2f}</td>"
                    f"<td>{_money(cb.expected_loss, cur)}</td><td><b>{_money(cb.exposure, cur)}</b></td><td>{delay:g}</td></tr>")
    h.append("<table>" + "".join(rows) + "</table>")
    if costs and costs[0].c_loss:
        h.append(f'<p class="note">Value at risk used: {_money(costs[0].c_loss, cur)}.</p>')
    else:
        h.append('<p class="warn">No value at risk was entered, so expected loss is zero and the comparison only reflects intervention cost.</p>')
    for o in rep.options:
        cb = next((x for x in costs if x.option_key == o.key), None)
        h.append(f"<h3>Option {_e(o.key)}: {_e(o.title)}{_ids(o.source_ids)}</h3>")
        if o.description:
            h.append(f"<p>{_e(o.description)}</p>")
        h.append(_ul([f"action: {_e(a)}" for a in o.actions] + [f"assumption: {_e(a)}" for a in o.assumptions]
                     + ([f"main uncertainty: {_e(o.main_uncertainty)}"] if o.main_uncertainty else [])))
        if cb and cb.lines:
            r = ["<tr><th>Item</th><th>Qty</th><th>Unit</th><th>Unit cost</th><th>Category</th><th>Cost</th></tr>"]
            for ln in cb.lines:
                r.append(f"<tr><td>{_e(ln.label)}</td><td>{ln.quantity:g}</td><td>{_e(ln.unit)}</td><td>{ln.unit_cost:,.0f}</td>"
                         f"<td>{_e(ln.category)}</td><td>{ln.cost:,.0f}</td></tr>")
            h.append("<table>" + "".join(r) + "</table>")
        if cb and cb.unknown_items:
            h.append(f'<p class="warn">Not costed (not in the price list): {_e(", ".join(cb.unknown_items))}</p>')
        if o.key in sup:
            h.append(_ul([_e(n) for n in sup[o.key].notes]))
    if rep.cost_notes or rep.supply_notes:
        h.append("<h3>Cost and supply review notes</h3>" + _ul([_e(n) for n in rep.cost_notes + rep.supply_notes]))

    # ---- risk / critic
    h.append("<h2>5. Risk and compliance flags</h2>")
    for po in rep.risk.per_option:
        h.append(f"<h3>Option {_e(po.option_key)}</h3>")
        h.append(_ul([f"<b>{'VERIFIED' if f.status == 'verified' else 'needs human / regulatory confirmation'}</b>: "
                      f"{_e(f.text)}{_ids(f.source_ids)}" for f in po.flags]))
    h.append(_ul([_e(n) for n in rep.risk.overall_notes]))
    h.append("<h2>6. Independent critic review</h2>")
    h.append(_ul([f"<b>{_e(i.severity)}</b>: {_e(i.text)}" for i in rep.critic.issues]))
    if rep.critic.missing_data:
        h.append(f"<p><b>Missing data:</b> {_e('; '.join(rep.critic.missing_data))}</p>")
    if rep.critic.note_to_reviewer:
        h.append(f"<p><b>Note to the human reviewer:</b> {_e(rep.critic.note_to_reviewer)}</p>")

    # ---- decision record
    h.append("<h2>7. Decision record</h2>")
    if decisions:
        r = ["<tr><th>Time (UTC)</th><th>Decision</th><th>Option</th><th>Reason / added information</th></tr>"]
        for d in decisions:
            r.append(f"<tr><td>{_e(str(d.get('decided', '')))}</td><td><b>{_e(str(d.get('decision', '')))}</b></td>"
                     f"<td>{_e(str(d.get('option_key', '') or '-'))}</td><td>{_e(str(d.get('reason', '') or '-'))}</td></tr>")
        h.append("<table>" + "".join(r) + "</table>")
    else:
        h.append('<p class="note">No decision has been saved for this case yet. Save the decision in the app, then prepare the PDF again.</p>')

    # ---- citation check + references
    h.append("<h2>8. Citation check</h2>")
    h.append('<p class="note">Automatic keyword-overlap check between each statement and the sources it cites. '
             '"Supported" means its wording can be traced to the cited text; it does not prove the source backs the claim. '
             "Read the sources before relying on them.</p>")
    if rep.citation_checks:
        cls = {"supported": "ok", "partial": "mid", "weak": "bad", "unsourced": "bad"}
        r = ["<tr><th>Where</th><th>Statement</th><th>Cited</th><th>Traceability</th></tr>"]
        for x in rep.citation_checks:
            r.append(f"<tr><td>{_e(x['section'])}</td><td>{_e(x['claim'])}</td>"
                     f"<td class='id'>{_e(', '.join(x['source_ids']) or '-')}</td>"
                     f"<td class='{cls[x['level']]}'>{_e(x['level'])} ({x['score']:.2f})</td></tr>")
        h.append("<table>" + "".join(r) + "</table>")
    else:
        h.append("<p>-</p>")

    h.append("<h2>9. References and sources</h2>")
    order = {"library": 0, "web": 1, "scholar": 2, "soil": 3, "weather": 4, "org": 5, "user": 6, "photo": 7, "default": 8, "calc": 9}
    srcs = sorted(rep.sources, key=lambda x: (order.get(x.get("kind", ""), 9), x["id"]))
    for sdict in srcs:
        cite = sdict.get("citation") or sdict["title"]
        meta = " | ".join(x for x in [sdict.get("source_type", ""), sdict.get("reliability", ""),
                                     "retrieved " + sdict.get("retrieved", "")] if x)
        h.append(f"<p><span class='id'>[{_e(sdict['id'])}]</span> {_e(cite)}<br/><span class='note'>{_e(meta)}</span> "
                 f"{_link(sdict.get('url', ''))}</p>")

    h.append("<h2>Disclaimer</h2>")
    h.append("<p class='note'>This report supports, and does not replace, a qualified agronomist. Photo descriptions come from a vision model "
             "and are not a diagnosis. Farmer percentages are estimates. Placeholder prices and assumed loss probabilities must be "
             "replaced with local values. Confirm any chemical use with an expert and check local regulations. Weather: Open-Meteo.com "
             "(CC BY 4.0). Soil: ISRIC SoilGrids (CC BY 4.0).</p>")
    return "\n".join(h)


def build_pdf(rep: Report, costs: list[CostBreakdown] | None = None, decisions: list[dict] | None = None,
              case_id: str = "", lang: str | None = None) -> bytes:
    html = build_html(rep, costs, decisions, case_id, lang)
    buf = io.BytesIO()
    writer = pymupdf.DocumentWriter(buf)
    story = pymupdf.Story(html=html, user_css=CSS)
    mediabox = pymupdf.paper_rect("a4")
    where = mediabox + (46, 46, -46, -58)
    more = 1
    while more:
        dev = writer.begin_page(mediabox)
        more, _ = story.place(where)
        story.draw(dev)
        writer.end_page()
    writer.close()
    doc = pymupdf.open(stream=buf.getvalue(), filetype="pdf")
    n = len(doc)
    for i, page in enumerate(doc, 1):
        page.insert_text((46, page.rect.height - 30), f"AgroDecision AI  |  case {case_id or '-'}  |  decision support only - not a substitute for an agronomist",
                         fontsize=7, color=(0.4, 0.4, 0.4))
        page.insert_text((page.rect.width - 96, page.rect.height - 30), f"Page {i} of {n}", fontsize=8, color=(0.3, 0.3, 0.3))
    doc.set_metadata({"title": "AgroDecision AI - decision-support report", "author": "AgroDecision AI", "subject": f"Case {case_id}"})
    return doc.tobytes(garbage=3, deflate=True)
