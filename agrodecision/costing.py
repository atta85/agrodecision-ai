"""Deterministic cost and supply maths. No LLM is involved, so numbers are auditable.

Formulas (from the project proposal):
    C_total = C_materials + C_labor + C_equipment + C_operation (+ C_diagnostic)
    EC      = C_intervention + P_loss x C_loss
"""
from __future__ import annotations

import io
from collections import defaultdict

import pandas as pd

from .config import load_json
from .schemas import CostBreakdown, CostLine, InterventionOption, ShortItem, SupplyCheck

CATEGORIES = ["material", "labor", "equipment", "operation", "diagnostic"]


def default_prices() -> dict[str, dict]:
    return load_json("default_prices.json")["items"]


def catalogue_text(prices: dict[str, dict]) -> str:
    """Compact list handed to the Intervention agent so it uses valid item keys only."""
    return "\n".join(f"- {k}: {v['label']} [{v['unit']}] ({v['category']})" for k, v in prices.items())


def parse_prices_csv(raw: bytes | str) -> dict[str, dict]:
    """CSV columns: key,label,unit,category,unit_cost (label/unit/category optional)."""
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip().lower() for c in df.columns]
    if "key" not in df.columns or "unit_cost" not in df.columns:
        raise ValueError("Price CSV needs at least the columns: key, unit_cost")
    out = {}
    for _, r in df.iterrows():
        key = str(r["key"]).strip()
        if not key:
            continue
        out[key] = {
            "label": str(r.get("label", key)) if pd.notna(r.get("label", None)) else key,
            "unit": str(r.get("unit", "unit")) if pd.notna(r.get("unit", None)) else "unit",
            "category": str(r.get("category", "material")).strip().lower() if pd.notna(r.get("category", None)) else "material",
            "unit_cost": float(r["unit_cost"]),
        }
    return out


def merge_prices(base: dict[str, dict], override: dict[str, dict] | None) -> dict[str, dict]:
    merged = {k: dict(v) for k, v in base.items()}
    for k, v in (override or {}).items():
        if k in merged:
            merged[k].update(v)
        else:
            merged[k] = dict(v)
    return merged


def parse_inventory_csv(raw: bytes | str) -> dict[str, dict]:
    """CSV columns: key,on_hand,lead_time_days,min_order_qty (last two optional)."""
    text = raw.decode("utf-8-sig") if isinstance(raw, bytes) else raw
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip().lower() for c in df.columns]
    if "key" not in df.columns or "on_hand" not in df.columns:
        raise ValueError("Inventory CSV needs at least the columns: key, on_hand")
    inv = {}
    for _, r in df.iterrows():
        inv[str(r["key"]).strip()] = {
            "on_hand": float(r["on_hand"]),
            "lead_time_days": float(r.get("lead_time_days", 0) or 0),
            "min_order_qty": float(r.get("min_order_qty", 0) or 0),
        }
    return inv


def compute_cost(
    option_key: str,
    quantities: dict[str, float],
    p_loss: float,
    crop_value_at_risk: float,
    prices: dict[str, dict],
) -> CostBreakdown:
    by_cat: dict[str, float] = defaultdict(float)
    lines: list[CostLine] = []
    unknown: list[str] = []
    for key, qty in quantities.items():
        item = prices.get(key)
        if item is None:
            unknown.append(key)
            continue
        cost = float(qty) * float(item["unit_cost"])
        cat = item.get("category", "material")
        by_cat[cat] += cost
        lines.append(
            CostLine(
                key=key,
                label=item.get("label", key),
                unit=item.get("unit", ""),
                quantity=float(qty),
                unit_cost=float(item["unit_cost"]),
                category=cat,
                cost=cost,
            )
        )
    c_total = sum(by_cat.values())
    p = max(0.0, min(1.0, float(p_loss)))
    c_loss = float(crop_value_at_risk or 0.0)
    expected_loss = p * c_loss
    return CostBreakdown(
        option_key=option_key,
        lines=lines,
        unknown_items=unknown,
        c_materials=by_cat["material"],
        c_labor=by_cat["labor"],
        c_equipment=by_cat["equipment"],
        c_operation=by_cat["operation"],
        c_diagnostic=by_cat["diagnostic"],
        c_total=c_total,
        p_loss=p,
        c_loss=c_loss,
        expected_loss=expected_loss,
        exposure=c_total + expected_loss,
    )


def cost_for_option(opt: InterventionOption, crop_value_at_risk: float, prices: dict[str, dict]) -> CostBreakdown:
    return compute_cost(opt.key, opt.quantities, opt.p_loss, crop_value_at_risk, prices)


def check_supply(
    opt: InterventionOption,
    inventory: dict[str, dict] | None,
    prices: dict[str, dict],
) -> SupplyCheck:
    if not inventory:
        return SupplyCheck(
            option_key=opt.key,
            inventory_provided=False,
            est_delay_days=float(opt.delay_days),
            notes=["No inventory data was provided, so availability of materials, labour and equipment was NOT checked."],
        )
    shortages: list[ShortItem] = []
    missing: list[str] = []
    max_lead = 0.0
    for key, need in opt.quantities.items():
        inv = inventory.get(key)
        if inv is None:
            missing.append(key)
            continue
        short = max(0.0, need - inv["on_hand"])
        if short > 0:
            order_qty = max(short, inv.get("min_order_qty", 0.0))
            unit_cost = float(prices.get(key, {}).get("unit_cost", 0.0))
            lead = float(inv.get("lead_time_days", 0.0))
            max_lead = max(max_lead, lead)
            shortages.append(
                ShortItem(
                    key=key,
                    needed=need,
                    on_hand=inv["on_hand"],
                    shortfall=short,
                    order_qty=order_qty,
                    lead_time_days=lead,
                    extra_cost=order_qty * unit_cost,
                )
            )
    notes = []
    if shortages:
        notes.append(
            "Shortfall on: " + ", ".join(f"{s.key} (need {s.needed:g}, have {s.on_hand:g})" for s in shortages)
        )
    if missing:
        notes.append("Not listed in the inventory file: " + ", ".join(missing))
    return SupplyCheck(
        option_key=opt.key,
        inventory_provided=True,
        shortages=shortages,
        not_in_inventory=missing,
        est_delay_days=max(float(opt.delay_days), max_lead),
        feasible_now=(len(shortages) == 0),
        notes=notes,
    )


def fmt_money(value: float, currency: str) -> str:
    return f"{currency} {value:,.0f}"
