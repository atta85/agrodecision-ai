import json

import pytest

from agrodecision import costing
from agrodecision.llm import TokenRateLimiter, extract_json, parse_retry_seconds, estimate_tokens
from agrodecision.media import prepare_image
from agrodecision.rag_lite import top_chunks
from agrodecision.schemas import InterventionOption
from agrodecision.sources import SourceRegistry
from agrodecision.tools.weather import summarize_weather


def test_cost_formulas():
    prices = costing.default_prices()
    c = costing.compute_cost("A", {"labor_hour": 10, "gypsum_kg": 100, "pump_hour": 5, "extra_monitoring_visit": 2,
                                   "soil_test_sample": 1, "nope": 3}, 0.4, 10000, prices)
    assert c.unknown_items == ["nope"]
    assert c.c_labor == 10 * 200 and c.c_materials == 100 * 40 and c.c_equipment == 5 * 400
    assert c.c_operation == 2 * 500 and c.c_diagnostic == 2000
    assert c.c_total == c.c_materials + c.c_labor + c.c_equipment + c.c_operation + c.c_diagnostic
    assert c.expected_loss == pytest.approx(4000)
    assert c.exposure == pytest.approx(c.c_total + 4000)


def test_supply_shortage_and_moq():
    prices = costing.default_prices()
    inv = costing.parse_inventory_csv("key,on_hand,lead_time_days,min_order_qty\ngypsum_kg,60,5,50\nlabor_hour,40,0,0\n")
    opt = InterventionOption(key="B", title="t", quantities={"gypsum_kg": 100, "labor_hour": 10, "pump_hour": 2}, delay_days=1)
    sc = costing.check_supply(opt, inv, prices)
    assert sc.feasible_now is False and sc.est_delay_days == 5
    assert sc.shortages[0].shortfall == 40 and sc.shortages[0].order_qty == 50
    assert sc.not_in_inventory == ["pump_hour"]
    assert costing.check_supply(opt, None, prices).inventory_provided is False


def test_price_csv_merge():
    up = costing.parse_prices_csv("key,unit_cost\ngypsum_kg,99\nnew_item,5\n")
    merged = costing.merge_prices(costing.default_prices(), up)
    assert merged["gypsum_kg"]["unit_cost"] == 99 and merged["gypsum_kg"]["label"]
    assert "new_item" in merged
    with pytest.raises(ValueError):
        costing.parse_prices_csv("a,b\n1,2\n")


def test_extract_json_variants():
    assert extract_json('Here you go:\n```json\n{"a": 1, "b": [1,2,],}\n```') == {"a": 1, "b": [1, 2]}
    assert extract_json('noise {"s": "a } brace"} trailing') == {"s": "a } brace"}
    with pytest.raises(ValueError):
        extract_json("no json here")


def test_retry_parse_and_estimate():
    assert parse_retry_seconds("Please try again in 7.5s.") == pytest.approx(8.5)
    assert parse_retry_seconds("try again in 1m3.2s") == pytest.approx(64.2)
    assert estimate_tokens("hello world") < estimate_tokens("سلام دنیا " * 20)


def test_limiter_blocks_then_releases(monkeypatch):
    import agrodecision.llm as m
    t = {"now": 0.0}
    monkeypatch.setattr(m.time, "monotonic", lambda: t["now"])
    monkeypatch.setattr(m.time, "sleep", lambda s: t.__setitem__("now", t["now"] + s))
    lim = TokenRateLimiter(1000)
    lim.wait(600)
    lim.wait(600)              # would exceed -> must "sleep" ~60s
    assert t["now"] >= 59


def test_registry_rejects_invented_ids():
    r = SourceRegistry()
    a = r.add("weather", "w", "x")
    b = r.add("user", "u", "y")
    assert (a, b) == ("W1", "U1")
    assert r.clean_ids(["W1", "Z9", "[U1]", "W1"]) == ["W1", "U1"]


def test_weather_summary():
    data = {"daily": {"temperature_2m_max": [36] * 21, "temperature_2m_min": [22] * 21, "precipitation_sum": [0, None] + [0] * 19,
                      "et0_fao_evapotranspiration": [6] * 21}, "current": {"temperature_2m": 35, "relative_humidity_2m": 20}}
    text, nums = summarize_weather(data)
    assert nums["past14_days_ge_35C"] == 14 and nums["past14_water_balance_mm"] == -84
    assert "water balance" in text


def test_top_chunks():
    sop = "Chemicals must be registered. " * 30 + "Workers wear gloves when spraying. " * 30
    assert top_chunks(sop, "gloves spraying workers", k=1)


def test_prepare_image_downsizes():
    from PIL import Image
    import io
    buf = io.BytesIO()
    Image.new("RGB", (4000, 3000), (10, 200, 30)).save(buf, "PNG")
    jpeg, b64 = prepare_image(buf.getvalue())
    im = Image.open(io.BytesIO(jpeg))
    assert max(im.size) == 1280 and len(b64) > 100
