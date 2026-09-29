"""Headless UI test in DEMO_MODE (no network, no API key).  Run: python -m pytest -q"""
import os
import tempfile

import pytest
from streamlit.testing.v1 import AppTest

APP = os.path.join(os.path.dirname(__file__), "..", "app.py")


@pytest.fixture(autouse=True)
def demo_env(monkeypatch):
    # set inside a fixture so the variable cannot leak into other test modules
    monkeypatch.setenv("DEMO_MODE", "true")
    monkeypatch.setenv("AGRO_RUNTIME_DIR", tempfile.mkdtemp())
    monkeypatch.setenv("TPM_LIMIT", "1000000")


def _run():
    at = AppTest.from_file(APP, default_timeout=90)
    at.run()
    assert not at.exception, at.exception
    return at


@pytest.mark.parametrize("lang", ["en", "ur", "sd", "ur_roman"])
def test_full_flow(lang):
    at = _run()
    at.selectbox(key="lang").set_value(lang).run()
    assert not at.exception, at.exception
    at.multiselect(key="f_symptoms").set_value(["yellowing", "wilting"])
    at.text_area(key="f_desc").set_value("test description")
    at.number_input(key="f_value").set_value(100000.0)
    at.button(key="btn_continue").click().run()
    assert not at.exception, at.exception
    assert at.session_state["stage"] == "confirm"
    at.button(key="btn_yes").click().run()
    assert not at.exception, at.exception
    assert at.session_state["stage"] == "results"
    assert at.session_state["report"]["demo"] is True
    # decision gate: approve option B and save
    cid = at.session_state["case_id"]
    at.button(key=f"dec_save_{cid}").click().run()
    assert not at.exception, at.exception
    from agrodecision import storage
    got = storage.get_case(cid)
    assert got and got["decisions"][-1]["decision"] == "APPROVE"


def test_validation_blocks_empty_form():
    at = _run()
    at.button(key="btn_continue").click().run()
    assert at.session_state["stage"] == "form"
    assert any("symptom" in e.value for e in at.error)


def test_modify_and_reject_paths():
    at = _run()
    at.multiselect(key="f_symptoms").set_value(["spots"])
    at.button(key="btn_continue").click().run()
    at.button(key="btn_yes").click().run()
    cid = at.session_state["case_id"]
    at.radio(key=f"dec_choice_{cid}_en").set_value("MODIFY").run()
    assert not at.exception, at.exception
    at.button(key=f"dec_save_{cid}").click().run()
    assert not at.exception, at.exception
    at.radio(key=f"dec_choice_{cid}_en").set_value("REJECT").run()
    at.text_area(key=f"dec_reason_{cid}_reject").set_value("too costly")
    at.button(key=f"dec_save_{cid}").click().run()
    assert not at.exception, at.exception
    from agrodecision import storage
    decisions = [d["decision"] for d in storage.get_case(cid)["decisions"]]
    assert decisions == ["MODIFY", "REJECT"]
