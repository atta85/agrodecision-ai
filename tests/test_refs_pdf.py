import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

from agrodecision.citations import check_claims, summarize, support_score
from agrodecision.demo import demo_report
from agrodecision.pdf_report import build_pdf
from agrodecision.pipeline import Uploads
from agrodecision.schemas import CaseInput, FarmerSummary
from agrodecision.sources import SourceRegistry, classify_url
from agrodecision.tools import library

APP = os.path.join(os.path.dirname(__file__), "..", "app.py")


def test_library_entries_are_complete():
    lib = library.load_library()
    assert len(lib) >= 5
    ids = [e["id"] for e in lib]
    assert len(ids) == len(set(ids))
    for e in lib:
        for k in ("title", "publisher", "url", "summary", "topics", "source_type"):
            assert e.get(k), (e["id"], k)
        assert e["url"].startswith("https://")


def test_library_search_and_auto_refs():
    assert "fao-iddp29" in [e["id"] for e in library.search_library("citrus salinity irrigation water quality leaching")]
    assert library.search_library("zzzz qqqq nonsense") == []
    assert [e["id"] for e in library.auto_refs({"soil"})] == ["soilgrids-2021"]
    reg = SourceRegistry()
    sid = reg.add(**library.source_args(library.load_library()[0]))
    assert sid == "L1" and reg.get("L1").publisher and "FAO" in reg.get("L1").citation


def test_classify_url():
    assert classify_url("https://www.fao.org/x")[1].startswith("UN")
    assert classify_url("https://ipm.ucanr.edu/a")[1] == "university / extension"
    assert classify_url("https://random.example/x")[1] == "other web source"


def test_support_score_levels():
    src = ["Salinity control and management of poor-quality irrigation water; salts affect crops and soils."]
    assert support_score("Salinity from irrigation water can affect crops", src) > 0.3
    assert support_score("Fungal rust on wheat needs fungicide spraying", src) < 0.12


def test_demo_report_has_references_and_checks():
    rep = demo_report(CaseInput(crop="citrus", crop_value_at_risk=100000), Uploads())
    assert any(s["kind"] == "library" for s in rep.sources)
    assert rep.citation_checks
    cs = summarize(rep.citation_checks)
    assert cs["total"] == len(rep.citation_checks)
    # every cited id exists in the source list
    ids = {s["id"] for s in rep.sources}
    assert all(i in ids for c in rep.citation_checks for i in c["source_ids"])


@pytest.mark.parametrize("lang", ["en", "ur", "pa", "sd", "ur_roman"])
def test_pdf_builds_for_every_language(lang):
    rep = demo_report(CaseInput(crop="citrus", crop_value_at_risk=100000, language=lang), Uploads())
    rep.summary_local = FarmerSummary(headline="پانی کی کمی", next_steps=["ٹیسٹ کروائیں"])
    pdf = build_pdf(rep, None, [{"decided": "2026-01-01 00:00:00", "decision": "APPROVE", "option_key": "A", "reason": "ok"}], "abc123", lang)
    assert pdf[:4] == b"%PDF" and len(pdf) > 5000
    import pymupdf
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    text = "\n".join(p.get_text() for p in doc)
    assert "Decision record" in text and "References and sources" in text and "APPROVE" in text
    assert "Page 1 of" in text


def test_pdf_button_in_app(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("AGRO_RUNTIME_DIR", tempfile.mkdtemp())
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    at.multiselect(key="f_symptoms").set_value(["wilting"])
    at.button(key="btn_continue").click().run()
    at.button(key="btn_yes").click().run()
    assert at.session_state["stage"] == "results", [e.value for e in at.exception]
    cid = at.session_state["case_id"]
    at.button(key=f"res_prep_{cid}").click().run()
    assert not at.exception, at.exception
    assert at.session_state[f"res_pdf_{cid}"][:4] == b"%PDF"
