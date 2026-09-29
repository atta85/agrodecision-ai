"""End-to-end test through the REAL groq SDK and REAL CrewAI, against a strict local fake of Groq's API."""
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
import fake_groq  # noqa: E402
import pytest  # noqa: E402

import agrodecision.llm as L  # noqa: E402
import agrodecision.pipeline as P  # noqa: E402
from agrodecision.schemas import CaseInput  # noqa: E402


@pytest.fixture()
def server(monkeypatch):
    srv, url = fake_groq.start()
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setenv("GROQ_BASE_URL", url)
    monkeypatch.setenv("TPM_LIMIT", "1000000")
    monkeypatch.setenv("DEMO_MODE", "false")
    L._client_cache.clear()
    yield url
    srv.shutdown()


def test_crewai_agent_sends_only_role_and_content(server):
    from agrodecision import agents as A
    out = A.run_agent_json("critic", "Task: review.", A.CriticOut, 500)
    assert out.note_to_reviewer == "test first"           # <think> block and code fence were stripped
    assert fake_groq.Handler.log, "no request reached the fake Groq server"
    for req in fake_groq.Handler.log:
        for m in req["messages"]:
            assert set(m) <= {"role", "content"}, m       # 'cache_breakpoint' can never leave the app


def test_reasoning_effort_fallback(server, monkeypatch):
    monkeypatch.setenv("REASONING_EFFORT", "low")
    fake_groq.Handler.fail_reasoning = True
    text = L.chat_text("openai/gpt-oss-120b", [{"role": "user", "content": "translate please"}])
    assert "english_text" in text
    assert "reasoning_effort" not in fake_groq.Handler.log[-1]   # retried without it


def test_translation_calls(server):
    from agrodecision.translate import understand_input, translate_summary
    r = understand_input("ur", "میرے پتے پیلے ہیں", "crop=wheat")
    assert r["english_text"] == "my leaves are yellow"
    assert translate_summary("ur", {"headline": "x", "next_steps": []})["headline"] == "h"


def test_full_pipeline_over_wire(server, monkeypatch):
    monkeypatch.setattr(P.weather, "fetch_weather", lambda lat, lon: {
        "daily": {"temperature_2m_max": [30] * 21, "temperature_2m_min": [20] * 21, "precipitation_sum": [0] * 21,
                  "et0_fao_evapotranspiration": [5] * 21}, "current": {"temperature_2m": 33, "relative_humidity_2m": 30}})
    monkeypatch.setattr(P.soil, "fetch_soil", lambda lat, lon: None)
    case = CaseInput(crop="citrus", lat=33.7, lon=72.8, symptoms=["wilting"], description_en="slow growth",
                     crop_value_at_risk=10000, area=2)
    rep = P.run_analysis(case, P.Uploads(files=[], lite=True))
    assert [o.key for o in rep.options] == ["A", "B", "C"]
    assert rep.monitoring.findings[0].source_ids == ["W1"]      # invented X99 stripped
    assert rep.critic.issues and rep.summary_en.headline == "h"
    assert any(x["kind"] == "library" for x in rep.sources) and rep.citation_checks
    assert len(fake_groq.Handler.log) >= 6                      # monitoring, diagnosis, intervention, risk, critic, reporter
    for req in fake_groq.Handler.log:
        for m in req["messages"]:
            assert set(m) <= {"role", "content"}


def test_vision_message_shape(server):
    from agrodecision.media import describe_photo
    d = describe_photo("AAAA", "wheat", "photo.jpg")
    assert d["label"] == "photo.jpg"
    parts = fake_groq.Handler.log[-1]["messages"][0]["content"]
    assert parts[0]["type"] == "text" and parts[1]["type"] == "image_url"


def test_bad_key_message(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    monkeypatch.setenv("DEMO_MODE", "false")
    with pytest.raises(L.MissingKeyError):
        L.chat_text("m", [{"role": "user", "content": "x"}])


def test_selftest_against_fake_groq(server):
    from agrodecision.selftest import run_selftest
    res = run_selftest()
    names = {n: ok for n, ok, _ in res}
    assert all(ok for _, ok, _ in res), res
    assert any(n.startswith("CrewAI agent call (LLM class: GroqLLM)") for n in names)


def test_strip_extra_keys():
    msgs = [{"role": "system", "content": "x", "cache_breakpoint": True}]
    assert L._strip_extra_keys(msgs) == [{"role": "system", "content": "x"}]


def test_agent_falls_back_when_crewai_wrapper_breaks(server, monkeypatch):
    """Simulates the failure seen in the field: an exception with an EMPTY message inside CrewAI."""
    from crewai import Crew
    from agrodecision import agents as A

    def boom(self, *a, **k):
        raise Exception()

    monkeypatch.setattr(Crew, "kickoff", boom)
    out = A.run_agent_json("critic", "Task: review.", A.CriticOut, 500)
    assert out.note_to_reviewer == "test first"
    notes = A.pop_notes()
    assert notes and "CrewAI wrapper failed" in notes[0]


def test_empty_reply_gives_clear_error(server, monkeypatch):
    class R:  # empty content every time
        choices = [type("C", (), {"message": type("M", (), {"content": ""})(), "finish_reason": "length"})()]

    class Fake:
        class chat:
            class completions:
                @staticmethod
                def create(**kw):
                    return R()

    monkeypatch.setattr(L, "_client", lambda: Fake())
    with pytest.raises(L.GroqCallError) as ei:
        L.chat_text("openai/gpt-oss-120b", [{"role": "user", "content": "x"}])
    assert "empty reply" in str(ei.value)


def test_pipeline_survives_openalex_429(server, monkeypatch):
    import agrodecision.tools.scholar as sch

    def limited(*a, **k):
        raise sch.ScholarUnavailable("OpenAlex answered HTTP 429. Add a free OPENALEX_API_KEY.")

    monkeypatch.setattr(sch, "search_papers", limited)
    monkeypatch.setattr(P.weather, "fetch_weather", lambda lat, lon: {
        "daily": {"temperature_2m_max": [30] * 21, "temperature_2m_min": [20] * 21, "precipitation_sum": [0] * 21,
                  "et0_fao_evapotranspiration": [5] * 21}, "current": {"temperature_2m": 33, "relative_humidity_2m": 30}})
    monkeypatch.setattr(P.soil, "fetch_soil", lambda lat, lon: None)
    case = CaseInput(crop="wheat", lat=33.7, lon=72.8, symptoms=["yellowing"], description_en="yellow leaves", crop_value_at_risk=1000)
    rep = P.run_analysis(case, P.Uploads(files=[], lite=True))
    assert len(rep.options) == 3
    assert any("Paper search (OpenAlex) was skipped" in w and "OPENALEX_API_KEY" in w for w in rep.warnings)
