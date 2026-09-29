"""Orchestrator: evidence gathering -> agents -> deterministic costing -> report.

The human decision gate lives in the Streamlit UI (app.py), AFTER this function returns.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable

from . import agents as A
from . import costing
from .config import load_json, settings
from .media import describe_photo, pdf_extract, prepare_image
from .rag_lite import top_chunks
from .schemas import (CaseInput, CostBreakdown, DiagnosisOut, InterventionOption, MonitoringOut, Report, RiskOut,
                      SupplyCheck)
from .sources import SourceRegistry, classify_url
from .citations import check_claims, summarize
from .tools import library, scholar, search, soil, weather

Progress = Callable[[float, str], None]


@dataclass
class Uploads:
    files: list[tuple[str, bytes]] = field(default_factory=list)   # photos / PDFs (name, bytes)
    sop_text: str = ""
    prices_override: dict | None = None
    inventory: dict | None = None
    lite: bool = True   # True = skip optional LLM "review note" agents (saves free-tier tokens)


def _photo_summary(d: dict) -> str:
    parts = []
    for k, label in [("organ", "organ"), ("visible_symptoms", "visible symptoms"), ("colour_and_pattern", "colour/pattern"),
                     ("distribution", "distribution"), ("pests_or_structures_visible", "pests/structures"),
                     ("image_quality", "image quality"), ("limitations", "limitations")]:
        v = d.get(k)
        if v:
            parts.append(f"{label}: {', '.join(v) if isinstance(v, list) else v}")
    return "; ".join(parts) or "no description"


def _sanitize(reg: SourceRegistry, monitoring, diagnosis, options, risk) -> tuple[int, int]:
    total = cited = 0
    for f in monitoring.findings:
        f.source_ids = reg.clean_ids(f.source_ids); total += 1; cited += bool(f.source_ids)
    for h in diagnosis.hypotheses:
        h.source_ids = reg.clean_ids(h.source_ids); total += 1; cited += bool(h.source_ids)
    for o in options:
        o.source_ids = reg.clean_ids(o.source_ids); total += 1; cited += bool(o.source_ids)
    for po in risk.per_option:
        for fl in po.flags:
            fl.source_ids = reg.clean_ids(fl.source_ids)
            if fl.status == "verified" and not fl.source_ids:
                fl.status = "needs_confirmation"  # cannot claim 'verified' without a source
            total += 1; cited += bool(fl.source_ids)
    return cited, total


def _costs_table(costs: list[CostBreakdown], options: list[InterventionOption], cur: str) -> str:
    rows = []
    for c in costs:
        t = next((o.title for o in options if o.key == c.option_key), "")
        rows.append(
            f"{c.option_key} ({t}): intervention {cur} {c.c_total:,.0f} [materials {c.c_materials:,.0f}, labour {c.c_labor:,.0f}, "
            f"equipment {c.c_equipment:,.0f}, operation {c.c_operation:,.0f}, diagnostics {c.c_diagnostic:,.0f}]; "
            f"P_loss {c.p_loss:.2f} x value at risk {c.c_loss:,.0f} = expected loss {c.expected_loss:,.0f}; "
            f"total exposure {c.exposure:,.0f}; unknown items: {c.unknown_items or 'none'}"
        )
    return "\n".join(rows)


def run_analysis(case: CaseInput, up: Uploads, progress: Progress | None = None) -> Report:
    s = settings()
    if s.demo_mode:
        from .demo import demo_report
        return demo_report(case, up)

    def prog(p: float, msg: str) -> None:
        if progress:
            progress(p, msg)

    reg = SourceRegistry()
    warnings: list[str] = []
    quality: list[str] = []
    prices = costing.merge_prices(costing.default_prices(), up.prices_override)
    prices_source = "user-provided price list merged over placeholder defaults" if up.prices_override else \
        "built-in PLACEHOLDER prices (not real market prices)"
    if not up.prices_override:
        reg.add("default", "Built-in placeholder unit costs", "Unit costs are placeholders, not market prices. Edit them.")
        quality.append("Costs use built-in placeholder prices - edit prices in the sidebar for realistic numbers.")

    # 1. farmer's own evidence ------------------------------------------------------------
    prog(0.03, "Recording the farmer's information")
    reg.add("user", "Farmer's report (selected options + description)", A.case_text(case))
    measured = []
    if case.ec_ds_m is not None:
        measured.append(f"root-zone/soil EC {case.ec_ds_m} dS/m")
    if case.ph is not None:
        measured.append(f"pH {case.ph}")
    if case.temp_c is not None:
        measured.append(f"temperature {case.temp_c} C")
    if measured:
        reg.add("user", "Measurements entered by the user", "; ".join(measured))
    else:
        quality.append("No sensor or lab measurements were provided; conclusions rely on descriptions, photos and public data.")
    if case.affected_range != "unknown":
        quality.append("The share of plants affected is the farmer's visual estimate, not a counted value.")

    # 2. files: photos and PDFs -------------------------------------------------------------
    prog(0.08, "Preparing photos and documents")
    images: list[tuple[str, str]] = []
    for name, raw in up.files[: s.max_images]:
        try:
            if name.lower().endswith(".pdf"):
                text, png = pdf_extract(raw)
                if text:
                    reg.add("org", f"Uploaded PDF text: {name}", text[:1500])
                if png:
                    _, b64 = prepare_image(png)
                    images.append((name, b64))
            else:
                _, b64 = prepare_image(raw)
                images.append((name, b64))
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Could not read file {name}: {e}")

    # 3. photo observer -----------------------------------------------------------------------
    photo_notes = []
    for i, (name, b64) in enumerate(images, 1):
        prog(0.10 + 0.08 * i / max(1, len(images)), f"Describing photo {i} of {len(images)}")
        try:
            d = describe_photo(b64, case.crop, name)
            photo_notes.append(d)
            reg.add("photo", f"Photo {i} ({name}) - description by vision model", _photo_summary(d))
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Photo {i} could not be analysed: {e}")
    if images:
        quality.append("Photo descriptions come from a vision model: they describe what is visible and are not a diagnosis.")
    else:
        quality.append("No photos were analysed.")

    # 4. weather + soil ---------------------------------------------------------------------------
    prog(0.20, "Fetching weather and soil data for the location")
    if case.lat is not None and case.lon is not None:
        try:
            wdata = weather.fetch_weather(case.lat, case.lon)
            wtext, _ = weather.summarize_weather(wdata)
            reg.add("weather", "Open-Meteo weather (last 14 days + 7-day outlook)", wtext, url="https://open-meteo.com")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Weather data unavailable: {e}")
        sg = soil.fetch_soil(case.lat, case.lon)
        if sg:
            reg.add("soil", "ISRIC SoilGrids estimate (0-30 cm)", soil.describe_soil(sg), url="https://soilgrids.org")
        else:
            warnings.append("SoilGrids soil data unavailable (its public API is beta and sometimes paused). "
                            "Soil information rests on the farmer's answer only.")
            quality.append("No public soil data could be retrieved; salinity in particular needs a soil/EC lab test.")
    else:
        warnings.append("No location coordinates: weather and soil lookups were skipped.")
        quality.append("Weather and soil data were not retrieved because the location was not confirmed.")

    # 5. curated reference library + web search (optional) ----------------------------------------------
    lib_used: set[str] = set()
    seen_urls: set[str] = set()

    def add_library(entries: list[dict]) -> None:
        for e in entries:
            if e["id"] not in lib_used:
                lib_used.add(e["id"])
                reg.add(**library.source_args(e))

    symptom_q = " ".join([case.crop, case.irrigation, case.soil_texture_user, *case.symptoms, case.description_en[:300]])
    add_library(library.search_library(symptom_q, k=3))
    kinds_now = {r["kind"] for r in reg.to_list()}
    add_library(library.auto_refs(kinds_now))

    def do_search(q: str) -> None:
        if not s.tavily_api_key:
            return
        try:
            for it in search.web_search(q, s.tavily_api_key):
                if it["url"] in seen_urls:
                    continue
                seen_urls.add(it["url"])
                host, label = classify_url(it["url"])
                reg.add("web", it["title"] or it["url"], it["content"], url=it["url"], publisher=host, source_type=label,
                        citation=f"{it['title']}. {host}. {it['url']}")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Web search failed: {e}")

    if s.tavily_api_key:
        prog(0.26, "Searching trusted agricultural sources")
        do_search(f"{case.crop} {' '.join(case.symptoms[:3])} causes diagnosis")
    else:
        quality.append("Web search is switched off (no TAVILY_API_KEY): references come from the curated library and papers only.")

    # 6. Monitoring agent -----------------------------------------------------------------------------
    prog(0.32, "Agent 1/6: Crop Monitoring")
    monitoring: MonitoringOut = A.run_agent_json("monitoring", A.prompt_monitoring(reg.evidence_block()), MonitoringOut, 1200)

    # 7. Diagnosis agent ----------------------------------------------------------------------------------
    prog(0.42, "Agent 2/6: Biological Diagnosis")
    diagnosis: DiagnosisOut = A.run_agent_json("diagnosis", A.prompt_diagnosis(reg.evidence_block(), monitoring), DiagnosisOut, 1800)

    # extra references about the leading hypotheses (feed interventions / risk / critic)
    if diagnosis.primary_hypothesis:
        hyp_names = " ".join(h.name for h in diagnosis.hypotheses[:3])
        add_library(library.search_library(f"{case.crop} {diagnosis.primary_hypothesis} {hyp_names}", k=3, exclude=lib_used))
        q = f"{case.crop} {diagnosis.primary_hypothesis} management"
        do_search(q)
        if len(diagnosis.hypotheses) > 1 and diagnosis.hypotheses[1].name != diagnosis.primary_hypothesis:
            do_search(f"{case.crop} {diagnosis.hypotheses[1].name} symptoms management")
        try:
            for p in scholar.search_papers(q, api_key=s.openalex_api_key, mailto=s.openalex_mailto, n=3):
                reg.add("scholar", f"{p['title']} ({p['year']})", p["abstract"], url=p["url"], publisher="OpenAlex index",
                        year=str(p["year"] or ""), source_type="scholarly literature (abstract only)",
                        citation=f"{p['title']} ({p['year']}). {p['url']}")
        except scholar.ScholarUnavailable as e:
            warnings.append(f"Paper search (OpenAlex) was skipped: {e} The analysis continued without papers.")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Paper search (OpenAlex) failed: {str(e)[:160]}. The analysis continued without papers.")

    # 8. Intervention agent --------------------------------------------------------------------------------------
    prog(0.55, "Agent 3/6: Intervention options")
    iv = A.run_agent_json("intervention", A.prompt_intervention(reg.evidence_block(500), diagnosis, costing.catalogue_text(prices), case),
                          A.InterventionOut, 2200)
    options = iv.options[:3]
    for idx, o in enumerate(options):
        o.key = "ABC"[idx]

    # 9. Cost + supply (deterministic) ------------------------------------------------------------------------------
    prog(0.68, "Calculating costs and checking supplies")
    value_at_risk = float(case.crop_value_at_risk or 0.0)
    if not value_at_risk:
        quality.append("Crop value at risk was not entered, so expected-loss figures are zero. Enter it to compare options fairly.")
    costs = [costing.cost_for_option(o, value_at_risk, prices) for o in options]
    supply: list[SupplyCheck] = [costing.check_supply(o, up.inventory, prices) for o in options]
    if not up.inventory:
        quality.append("No inventory file: availability of materials, labour and equipment was not checked.")
    for c in costs:
        if c.unknown_items:
            warnings.append(f"Option {c.option_key} used item keys missing from the price list: {', '.join(c.unknown_items)}")

    cost_notes: list[str] = []
    supply_notes: list[str] = []
    if not up.lite:
        try:
            cost_notes = A.run_agent_json("cost_review", A.prompt_cost_review(_costs_table(costs, options, case.currency), f"Prices: {prices_source}"),
                                          A.NarrativeOut, 900).notes
            supply_notes = A.run_agent_json("supply_review", A.prompt_supply_review(json.dumps([x.model_dump() for x in supply], ensure_ascii=False)[:2500]),
                                            A.NarrativeOut, 900).notes
        except Exception as e:  # noqa: BLE001
            warnings.append(f"Optional review-note agents failed: {e}")

    # 10. Risk & compliance --------------------------------------------------------------------------------------------
    prog(0.76, "Agent 4/6: Risk & Compliance")
    opt_brief = json.dumps([{"key": o.key, "title": o.title, "actions": o.actions, "quantities": o.quantities} for o in options],
                           ensure_ascii=False)
    if up.sop_text.strip():
        chunks = top_chunks(up.sop_text, opt_brief + " safety chemical protective registered application restriction", k=4)
        sid = reg.add("org", "Uploaded SOP / rules (matching excerpts)", "\n".join(chunks) or up.sop_text[:1500])
        rules_block = f"[{sid}] " + reg.get(sid).summary
    else:
        rules = load_json("sop_rules_default.json")["rules"]
        sid = reg.add("default", "Built-in generic rules (not legal advice, not your SOP)", " | ".join(rules))
        rules_block = f"[{sid}] " + " | ".join(rules)
        quality.append("No organisation SOP uploaded: built-in generic rules were used, so most flags need expert/regulatory confirmation.")
    risk: RiskOut = A.run_agent_json("risk", A.prompt_risk(opt_brief, rules_block), RiskOut, 1800)

    # 11. Critic --------------------------------------------------------------------------------------------------------------
    prog(0.86, "Agent 5/6: Critic review")
    bundle = (
        f"CASE:\n{A.case_text(case)}\n\nDATA QUALITY NOTES: {quality}\n\n"
        f"MONITORING: {json.dumps(monitoring.model_dump(), ensure_ascii=False)[:1200]}\n\n"
        f"DIAGNOSIS: {json.dumps(diagnosis.model_dump(), ensure_ascii=False)[:1800]}\n\n"
        f"OPTIONS AND COSTS:\n{_costs_table(costs, options, case.currency)}\n\n"
        f"OPTION ASSUMPTIONS: {json.dumps([{'key': o.key, 'assumptions': o.assumptions, 'uncertainty': o.main_uncertainty} for o in options], ensure_ascii=False)[:1200]}\n\n"
        f"RISK FLAGS: {json.dumps(risk.model_dump(), ensure_ascii=False)[:1500]}\n\nSOURCE IDS AVAILABLE: {', '.join(reg.ids())}"
    )
    critic = A.run_agent_json("critic", A.prompt_critic(bundle), A.CriticOut, 1500)

    # 12. plain-language summary ----------------------------------------------------------------------------------------------
    prog(0.93, "Agent 6/6: Writing the plain-language summary")
    summary = A.run_agent_json("reporter", A.prompt_reporter(bundle[:3800] + f"\n\nCRITIC NOTE: {critic.note_to_reviewer}"),
                               A.FarmerSummary, 1200)

    warnings.extend(A.pop_notes())
    cited, total = _sanitize(reg, monitoring, diagnosis, options, risk)
    checks = check_claims(reg, monitoring, diagnosis, options, risk)
    cs = summarize(checks)
    if total:
        quality.append(f"{cited} of {total} agent statements carry a source ID; the rest are marked as model reasoning. "
                       f"Keyword check of cited statements: {cs['supported']} well traceable, {cs['partial']} partly, "
                       f"{cs['weak']} weakly - this is a rough check, read the sources.")
    if not any(r["kind"] in ("library", "web", "scholar") for r in reg.to_list()):
        quality.append("No external reference sources matched this case, so scientific claims rest on model knowledge only.")

    prog(1.0, "Analysis complete - waiting for your decision")
    return Report(
        case=case, photo_notes=photo_notes, monitoring=monitoring, diagnosis=diagnosis, options=options,
        costs=costs, supply=supply, risk=risk, critic=critic, cost_notes=cost_notes, supply_notes=supply_notes,
        summary_en=summary, sources=reg.to_list(), citation_checks=checks, data_quality=quality, prices_source=prices_source, warnings=warnings,
    )
