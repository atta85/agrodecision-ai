"""The CrewAI agents and the prompts they receive.

Design notes
* Each agent runs as its own single-task Crew, one after another. This keeps every request small
  (Groq's free tier has a tokens-per-minute cap) and lets the human decision gate sit between phases.
* Agents cannot browse. All evidence is gathered by deterministic tools BEFORE the agents run and is
  handed to them as an EVIDENCE block with source IDs, so every claim can be traced.
"""
from __future__ import annotations

import json

from pydantic import BaseModel, ValidationError

from .config import settings
from .llm import LLMOutputError, chat_completion, extract_json, make_crew_llm
from .schemas import (CaseInput, CriticOut, DiagnosisOut, FarmerSummary, InterventionOut, MonitoringOut,
                      NarrativeOut, RiskOut)

RULES = (
    "RULES: Use ONLY the EVIDENCE block below; do not invent facts, numbers or references. "
    "Cite evidence by ID (for example U1, W1, P1, L1, T1, R1) in the source_ids fields. For statements about causes, "
    "thresholds or good practice, cite a reference source (L = curated library, T = trusted web page, R = paper) whenever one "
    "in the evidence covers the topic; do not cite a source for something it does not discuss. If a statement is not supported by the "
    "evidence, leave source_ids empty and begin that text with 'Model reasoning:'. "
    "Never present an uncertain diagnosis as established fact. Do not recommend specific pesticide brands or doses. "
    "Farmers may be reading a translation, so use clear, simple words. "
    "Reply with ONE JSON object only - no markdown, no commentary."
)

AGENT_SPECS: dict[str, dict] = {
    "monitoring": dict(
        role="Crop Monitoring Agent",
        goal="Spot unusual conditions and possible crop-health events in the data provided.",
        backstory="An agronomy data analyst who separates measured facts from estimates and says clearly what is missing.",
        model="light",
    ),
    "diagnosis": dict(
        role="Biological Diagnosis Agent",
        goal="List plausible causes of the problem with evidence for and against, and honest uncertainty.",
        backstory="A plant-health specialist who never over-claims: many symptoms share several causes.",
        model="reasoning",
    ),
    "intervention": dict(
        role="Intervention Agent",
        goal="Propose 3 practical response OPTIONS with the resources each would need.",
        backstory="A field-experienced crop advisor who offers options, not orders, and prefers confirming the cause before costly action.",
        model="reasoning",
    ),
    "cost_review": dict(
        role="Cost & Economic Analysis Agent",
        goal="Explain the computed costs and which inputs are placeholders or assumptions.",
        backstory="A farm economist who never invents prices and flags every assumption.",
        model="light",
    ),
    "supply_review": dict(
        role="Supply & Operations Agent",
        goal="Explain whether each option is operationally feasible with the stock, labour and equipment on hand.",
        backstory="An operations manager who checks inventory, lead times and minimum orders.",
        model="light",
    ),
    "risk": dict(
        role="Risk & Compliance Agent",
        goal="Check each option against the supplied rules and mark what is verified versus what needs human or regulatory confirmation.",
        backstory="A cautious compliance officer for agricultural inputs and worker safety.",
        model="reasoning",
    ),
    "critic": dict(
        role="Critic Agent",
        goal="Independently challenge the other agents' conclusions before a human sees them.",
        backstory="A sceptical reviewer who asks: what was assumed, what is missing, what else could explain this?",
        model="reasoning",
    ),
    "reporter": dict(
        role="Plain-Language Report Writer",
        goal="Turn the analysis into a short summary a farmer can understand.",
        backstory="A clear communicator who uses short sentences and never hides uncertainty.",
        model="light",
    ),
}


# ----------------------------------------------------------------------------- runner
RUN_NOTES: list[str] = []   # e.g. "monitoring: CrewAI wrapper failed (TimeoutError), used direct call"


def pop_notes() -> list[str]:
    out = list(RUN_NOTES)
    RUN_NOTES.clear()
    return out


def run_agent_json(agent_key: str, task_text: str, out_model: type[BaseModel], max_tokens: int = 1800,
                   retries: int = 1) -> BaseModel:
    """Run one CrewAI agent (single task) and validate its JSON answer."""
    from crewai import Agent, Crew, Process, Task

    spec = AGENT_SPECS[agent_key]
    s = settings()
    model = s.model_reasoning if spec["model"] == "reasoning" else s.model_light
    llm = make_crew_llm(model, max_tokens=max_tokens)
    agent = Agent(
        role=spec["role"], goal=spec["goal"], backstory=spec["backstory"], llm=llm,
        allow_delegation=False, verbose=False, max_iter=3,
    )
    prompt = task_text
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            task = Task(description=prompt, expected_output="One valid JSON object and nothing else.", agent=agent)
            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
            result = crew.kickoff()
            raw = getattr(result, "raw", None) or str(result)
            if not raw.strip():
                raise RuntimeError("CrewAI returned an empty result")
        except Exception as e:  # noqa: BLE001
            # The CrewAI wrapper failed (for any reason). Ask the same agent persona directly, so one
            # framework problem cannot stop the whole analysis. Real Groq errors are raised again below.
            RUN_NOTES.append(f"{agent_key}: CrewAI wrapper failed ({type(e).__name__}: {str(e)[:120] or 'no message'}); "
                             "used a direct Groq call with the same prompt.")
            system = f"You are the {spec['role']}. Goal: {spec['goal']} Background: {spec['backstory']}"
            raw = chat_completion(model, [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
                                  max_tokens=max_tokens)
        try:
            return out_model.model_validate(extract_json(raw))
        except (ValueError, ValidationError) as e:
            last_err = e
            prompt = task_text + f"\n\nYour previous reply could not be used ({str(e)[:200]}). Reply again with ONLY the JSON object."
    raise LLMOutputError(f"{agent_key}: could not get valid JSON ({last_err})")


# ----------------------------------------------------------------------------- prompts
def case_text(c: CaseInput) -> str:
    area = f"{c.area:g} {c.area_unit}" if c.area else "not stated"
    lines = [
        f"Crop: {c.crop or 'not stated'}; growth stage: {c.growth_stage or 'not stated'}; area: {area}.",
        f"Location: {', '.join(x for x in [c.city, c.province, c.country] if x) or 'not stated'}.",
        f"Symptoms selected: {', '.join(c.symptoms) if c.symptoms else 'none selected'}.",
        f"Share of plants affected (farmer's estimate): {c.affected_range}; started: {c.onset}; spreading: {c.spread}.",
        f"Irrigation: {c.irrigation}; soil texture (farmer): {c.soil_texture_user}.",
    ]
    if c.description_en:
        lines.append(f"Farmer's description: {c.description_en}")
    if c.extra_info:
        lines.append(f"Additional information supplied later: {c.extra_info}")
    return "\n".join(lines)


def prompt_monitoring(evidence: str) -> str:
    return (
        "Task: review the evidence and identify unusual conditions or possible crop-health events. Separate measured "
        "values from farmer estimates. List data gaps (for example: no sensor data, no soil test).\n\n"
        f"{RULES}\n\nEVIDENCE:\n{evidence}\n\n"
        'JSON: {"findings":[{"text":"...","source_ids":["W1"]}],"data_gaps":["..."],"severity":"low|moderate|high|unknown"}'
    )


def prompt_diagnosis(evidence: str, monitoring: MonitoringOut) -> str:
    mon = json.dumps(monitoring.model_dump(), ensure_ascii=False)
    return (
        "Task: give up to 5 plausible causes of the problem, ranked. Consider abiotic causes (water stress, salinity, "
        "nutrients, heat, waterlogging) and biotic causes (fungal, bacterial, viral, insects, mites, nematodes). For each, "
        "give evidence for and against and how likely it is. State how confident the overall evidence is, what extra "
        "evidence would separate the causes, and up to 4 short follow-up questions for the farmer.\n\n"
        f"{RULES}\n\nMONITORING RESULT:\n{mon}\n\nEVIDENCE:\n{evidence}\n\n"
        'JSON: {"hypotheses":[{"name":"...","likelihood":"high|moderate|low","evidence_for":["..."],"evidence_against":["..."],'
        '"source_ids":["U1"]}],"primary_hypothesis":"...","evidence_confidence":"low|moderate|high",'
        '"additional_evidence_needed":["..."],"follow_up_questions":["..."]}'
    )


def prompt_intervention(evidence: str, diagnosis: DiagnosisOut, catalogue: str, case: CaseInput) -> str:
    dg = json.dumps(diagnosis.model_dump(), ensure_ascii=False)
    area = f"{case.area:g} {case.area_unit}" if case.area else "unknown area"
    return (
        "Task: propose exactly 3 response OPTIONS (keys A, B, C) for a human to choose from. Option A should be a low-cost "
        "'confirm the cause and monitor' option. Each option lists its actions and the resources needed as quantities using "
        "ONLY the item keys in the CATALOGUE (unknown keys are rejected). Size quantities for the stated area "
        f"({area}) and state your sizing assumptions. Give delay_days (time before the action can start), and p_loss = your "
        "assumed share (0 to 1) of the crop value at risk that would still be lost with this option; the human can edit it. "
        "Do not choose a chemical treatment unless the cause is confirmed; if you include one, use the generic catalogue key "
        "and say an agronomist must confirm the product.\n\n"
        f"{RULES}\n\nDIAGNOSIS:\n{dg}\n\nCATALOGUE:\n{catalogue}\n\nEVIDENCE:\n{evidence}\n\n"
        'JSON: {"options":[{"key":"A","title":"...","description":"...","addresses":["hypothesis names"],"actions":["..."],'
        '"quantities":{"labor_hour":8},"delay_days":0,"p_loss":0.4,"assumptions":["..."],"main_uncertainty":"...",'
        '"source_ids":["T1"]}]}'
    )


def prompt_cost_review(table: str, sources_note: str) -> str:
    return (
        "Task: the costs below were calculated by the app (formulas C_total = materials + labour + equipment + operation + "
        "diagnostics; exposure = C_total + P_loss x value at risk). Write 3-5 short notes: which numbers are placeholders "
        "or assumptions, which option is most sensitive to the assumed P_loss, and what the reviewer should double-check. "
        "Do not recalculate or change numbers.\n\n"
        f"{RULES}\n\nCOSTS:\n{table}\n\n{sources_note}\n\n"
        'JSON: {"notes":["..."]}'
    )


def prompt_supply_review(table: str) -> str:
    return (
        "Task: summarise in 3-5 short notes whether each option can be carried out with the stock, labour and equipment "
        "available, and the expected delay. Use only the SUPPLY CHECK below.\n\n"
        f"{RULES}\n\nSUPPLY CHECK:\n{table}\n\n"
        'JSON: {"notes":["..."]}'
    )


def prompt_risk(options_json: str, rules_block: str) -> str:
    return (
        "Task: for EACH option, list safety, application, regulatory or missing-information flags. Mark a flag 'verified' "
        "ONLY if a rule in RULES_AND_SOPS directly supports it (cite its ID); otherwise mark it 'needs_confirmation'. "
        "Flag any action that needs expert verification.\n\n"
        f"{RULES}\n\nOPTIONS:\n{options_json}\n\nRULES_AND_SOPS:\n{rules_block}\n\n"
        'JSON: {"per_option":[{"option_key":"A","flags":[{"text":"...","status":"verified|needs_confirmation","source_ids":["D1"]}]}],'
        '"overall_notes":["..."]}'
    )


def prompt_critic(bundle: str) -> str:
    return (
        "Task: act as an independent critic. Ask: what assumptions were made? Is the evidence sufficient? Are other "
        "explanations possible? Is important data missing? Are the cost estimates based on reliable inputs? Does any option "
        "depend on an uncertain diagnosis? List concrete issues (severity low/medium/high), missing data, and any "
        "overconfident claims. Say whether overall confidence should be lowered. Finish with one short note to the human reviewer.\n\n"
        f"{RULES}\n\nANALYSIS BUNDLE:\n{bundle}\n\n"
        'JSON: {"issues":[{"severity":"medium","text":"..."}],"missing_data":["..."],"overconfident_claims":["..."],'
        '"confidence_adjustment":"none|lower|higher","note_to_reviewer":"..."}'
    )


def prompt_reporter(bundle: str) -> str:
    return (
        "Task: write a SHORT plain-language summary for a farmer (simple words, short sentences). Say what the most likely "
        "cause is but stress that it is not confirmed unless it is. Give one plain line per option (A, B, C), the next steps "
        "(for example tests or photos to add), and warnings (for example: confirm any chemical with an agronomist, check "
        "local rules). Keep option keys A/B/C and keep amounts/currency as given.\n\n"
        f"{RULES}\n\nANALYSIS BUNDLE:\n{bundle}\n\n"
        'JSON: {"headline":"...","likely_cause_plain":"...","options_plain":[{"key":"A","title":"...","one_line":"..."}],'
        '"next_steps":["..."],"warnings":["..."]}'
    )


OUT_MODELS = dict(
    monitoring=MonitoringOut, diagnosis=DiagnosisOut, intervention=InterventionOut, cost_review=NarrativeOut,
    supply_review=NarrativeOut, risk=RiskOut, critic=CriticOut, reporter=FarmerSummary,
)
