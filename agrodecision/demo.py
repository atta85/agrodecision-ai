"""DEMO_MODE: a canned citrus example (from the project proposal) so the app can be tried without any API key.
Costs are still computed by the real cost engine, using the current price table."""
from __future__ import annotations

from . import costing
from .schemas import (CaseInput, CriticOut, DiagnosisOut, FarmerSummary, Finding, Hypothesis, InterventionOption,
                      Issue, MonitoringOut, OptionLine, OptionRisk, Report, RiskFlag, RiskOut)
from .citations import check_claims
from .sources import SourceRegistry
from .tools import library


def demo_report(case: CaseInput, up) -> Report:
    reg = SourceRegistry()
    reg.add("user", "Farmer's report (DEMO)", f"Crop: {case.crop or 'citrus'}; symptoms and description as entered.")
    reg.add("weather", "Open-Meteo weather (DEMO sample text)", "Last 14 days: hot and dry, few rain days. DEMO DATA - not fetched.")
    reg.add("default", "Built-in generic rules (DEMO)", "Chemical treatments must be registered locally and confirmed by an agronomist.")
    lib_ids = []
    for e in library.search_library("citrus irrigation salinity leaching water stress evapotranspiration", k=3):
        lib_ids.append(reg.add(**library.source_args(e)))
    prices = costing.merge_prices(costing.default_prices(), up.prices_override)

    monitoring = MonitoringOut(
        findings=[Finding(text="Hot weather and low soil moisture reported together with slower growth.", source_ids=["U1", "W1"])],
        data_gaps=["No soil EC or pH measurement", "No plant tissue analysis"], severity="moderate")
    diagnosis = DiagnosisOut(
        hypotheses=[
            Hypothesis(name="Water stress with possible salinity interaction", likelihood="moderate",
                       evidence_for=["Hot, dry conditions", "Low soil moisture reported"],
                       evidence_against=["No EC measurement to confirm salts"], source_ids=["U1", "W1"] + lib_ids[:1]),
            Hypothesis(name="Nutrient imbalance", likelihood="low", evidence_for=["Leaf symptoms reported"],
                       evidence_against=["No tissue test"], source_ids=["U1"]),
            Hypothesis(name="Root or foliar disease", likelihood="low", evidence_for=[],
                       evidence_against=["No pathogen test"], source_ids=[]),
        ],
        primary_hypothesis="Possible salinity / water-stress interaction", evidence_confidence="low",
        additional_evidence_needed=["Root-zone EC and pH", "Plant tissue analysis", "Irrigation history"],
        follow_up_questions=["When was the last irrigation?", "Are older or younger leaves affected first?"])
    options = [
        InterventionOption(key="A", title="Test first and monitor", description="Confirm the cause before spending on treatment.",
                           actions=["Take soil and tissue samples", "Extra monitoring visits"],
                           quantities={"soil_test_sample": 3, "tissue_test_sample": 2, "extra_monitoring_visit": 3, "labor_hour": 6},
                           delay_days=0, p_loss=0.6, assumptions=["Cause stays the same while waiting for lab results"],
                           main_uncertainty="Cause not confirmed", source_ids=["U1"]),
        InterventionOption(key="B", title="Adjust irrigation and flush root zone", description="Extra water with leaching to reduce salts.",
                           actions=["Longer irrigation cycles", "Leaching irrigation"],
                           quantities={"leaching_water_m3": 60, "pump_hour": 12, "labor_hour": 10, "gypsum_kg": 100, "soil_test_sample": 2},
                           delay_days=2, p_loss=0.4, assumptions=["Water is available and of acceptable quality"],
                           main_uncertainty="Needs water and drainage", source_ids=["W1"]),
        InterventionOption(key="C", title="Full programme: irrigation, nutrients and lab tests", description="Combine water, nutrient and diagnostic steps.",
                           actions=["Irrigation change", "Nutrient adjustment", "Diagnostic tests"],
                           quantities={"leaching_water_m3": 60, "pump_hour": 12, "labor_hour": 24, "skilled_labor_hour": 4,
                                       "fertilizer_npk_kg": 50, "micronutrient_foliar_l": 4, "tissue_test_sample": 2, "pathogen_test_sample": 1},
                           delay_days=5, p_loss=0.25, assumptions=["Nutrient plan matches actual deficiency"],
                           main_uncertainty="Higher cost; some inputs may need ordering", source_ids=[]),
    ]
    value = float(case.crop_value_at_risk or 0.0)
    costs = [costing.cost_for_option(o, value, prices) for o in options]
    supply = [costing.check_supply(o, up.inventory, prices) for o in options]
    risk = RiskOut(
        per_option=[OptionRisk(option_key=o.key, flags=[
            RiskFlag(text="Any chemical use must be locally registered for this crop and confirmed by an agronomist.",
                     status="verified", source_ids=["D1"]),
            RiskFlag(text="Check water quality and drainage before flushing.", status="needs_confirmation")]) for o in options],
        overall_notes=["DEMO: built-in generic rules only."])
    critic = CriticOut(
        issues=[Issue(severity="high", text="The diagnosis is unconfirmed; options B and C partly assume salinity."),
                Issue(severity="medium", text="P_loss values are assumptions and change the ranking.")],
        missing_data=["Soil EC/pH", "Tissue analysis", "Irrigation records"], overconfident_claims=[],
        confidence_adjustment="lower", note_to_reviewer="Consider Option A first, then choose based on lab results.")
    summary = FarmerSummary(
        headline="DEMO: the problem may be linked to water stress and salts, but this is not confirmed.",
        likely_cause_plain="Hot, dry weather and low soil moisture can cause slow growth. Salts in the soil may also play a part.",
        options_plain=[OptionLine(key=o.key, title=o.title, one_line=o.description) for o in options],
        next_steps=["Take soil and leaf samples for a lab test", "Add clear photos of leaves (top and underside)"],
        warnings=["Confirm any chemical with an agronomist and check local rules."])
    checks = check_claims(reg, monitoring, diagnosis, options, risk)
    return Report(
        case=case, citation_checks=checks, monitoring=monitoring, diagnosis=diagnosis, options=options, costs=costs, supply=supply, risk=risk,
        critic=critic, summary_en=summary, sources=reg.to_list(), demo=True,
        data_quality=["DEMO MODE: this is a sample analysis, not based on your data.",
                      "Costs use built-in PLACEHOLDER prices."],
        prices_source="built-in PLACEHOLDER prices (demo)")
