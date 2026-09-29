"""Offline end-to-end test: fake LLM + fake network. Run:  python -m pytest -q"""
import json


import pytest
from crewai import BaseLLM

import agrodecision.agents as A
import agrodecision.pipeline as P
from agrodecision import config
from agrodecision.schemas import CaseInput


class FakeLLM(BaseLLM):
    def __init__(self):
        super().__init__(model="fake/fake")

    def call(self, messages, tools=None, callbacks=None, available_functions=None, from_task=None,
             from_agent=None, response_model=None):
        text = messages if isinstance(messages, str) else " ".join(str(m.get("content", "")) for m in messages)
        if "Crop Monitoring" in text:
            out = {"findings": [{"text": "Hot dry spell", "source_ids": ["W1", "X99"]}], "data_gaps": ["no EC"], "severity": "moderate"}
        elif "Biological Diagnosis" in text:
            out = {"hypotheses": [{"name": "Water stress", "likelihood": "moderate", "evidence_for": ["heat"],
                                   "evidence_against": [], "source_ids": ["W1"]}],
                   "primary_hypothesis": "Water stress", "evidence_confidence": "low",
                   "additional_evidence_needed": ["EC"], "follow_up_questions": ["When irrigated?"]}
        elif "Intervention Agent" in text:
            out = {"options": [
                {"key": "A", "title": "Test", "quantities": {"soil_test_sample": "2", "labor_hour": 4, "bogus_key": 3}, "p_loss": 0.5},
                {"key": "B", "title": "Irrigate", "quantities": {"pump_hour": 10, "gypsum_kg": 200}, "p_loss": 1.7, "delay_days": 2},
                {"key": "C", "title": "Full", "quantities": {"labor_hour": 20}, "p_loss": 0.2}]}
        elif "Risk & Compliance" in text:
            out = {"per_option": [{"option_key": "A", "flags": [
                {"text": "check label", "status": "verified", "source_ids": []},
                {"text": "PPE", "status": "verified", "source_ids": ["D2"]}]}], "overall_notes": []}
        elif "Critic Agent" in text:
            out = {"issues": [{"severity": "high", "text": "unconfirmed"}], "missing_data": ["EC"],
                   "overconfident_claims": [], "confidence_adjustment": "lower", "note_to_reviewer": "test first"}
        else:
            out = {"headline": "h", "likely_cause_plain": "c", "options_plain": [{"key": "A", "title": "t", "one_line": "o"}],
                   "next_steps": ["n"], "warnings": ["w"]}
        # wrap in a code fence + chatter, to exercise the JSON extractor
        return "Sure!\n```json\n" + json.dumps(out) + "\n```"


@pytest.fixture(autouse=True)
def patch(monkeypatch):
    monkeypatch.setenv("TPM_LIMIT", "1000000")
    monkeypatch.setenv("DEMO_MODE", "false")
    monkeypatch.setenv("GROQ_API_KEY", "x")
    monkeypatch.setattr(A, "make_crew_llm", lambda model, max_tokens=1800: FakeLLM())
    monkeypatch.setattr(P.weather, "fetch_weather", lambda lat, lon: {
        "daily": {"temperature_2m_max": [30] * 21, "temperature_2m_min": [20] * 21, "precipitation_sum": [0] * 21,
                  "et0_fao_evapotranspiration": [5] * 21}, "current": {"temperature_2m": 33, "relative_humidity_2m": 30}})
    monkeypatch.setattr(P.soil, "fetch_soil", lambda lat, lon: None)


def test_full_pipeline():
    case = CaseInput(crop="citrus", lat=33.7, lon=72.8, symptoms=["wilting"], description_en="slow growth",
                     crop_value_at_risk=10000, area=2)
    up = P.Uploads(files=[], lite=True)
    steps = []
    rep = P.run_analysis(case, up, progress=lambda p, m: steps.append(m))
    assert len(rep.options) == 3
    assert [o.key for o in rep.options] == ["A", "B", "C"]
    assert rep.options[1].p_loss == 1.0                       # clipped
    assert rep.costs[0].unknown_items == ["bogus_key"]        # unknown catalogue key flagged
    assert rep.costs[0].c_total > 0 and rep.costs[0].exposure == rep.costs[0].c_total + rep.costs[0].expected_loss
    assert rep.monitoring.findings[0].source_ids == ["W1"]    # invented X99 removed
    flags = rep.risk.per_option[0].flags
    assert flags[0].status == "needs_confirmation"            # 'verified' without a source is downgraded
    assert flags[1].status == "verified" or flags[1].source_ids == []  # D2 exists only if SOP default registered
    assert any("placeholder" in q.lower() for q in rep.data_quality)
    assert steps[-1].startswith("Analysis complete")
    # report must be JSON-serialisable for storage
    json.dumps(rep.model_dump())
