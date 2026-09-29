"""ISRIC SoilGrids (CC BY 4.0, 250 m resolution).

IMPORTANT: ISRIC has stated that the public REST API is beta, has a fair-use limit
(about 5 calls per minute) and has at times been paused. This module therefore
fails gracefully: if the API is down the app continues and asks the user for soil type.
SoilGrids has no salinity layer - use a soil/EC lab test for salinity.
"""
from __future__ import annotations

import requests

URL = "https://rest.isric.org/soilgrids/v2.0/properties/query"
UA = {"User-Agent": "AgroDecisionAI/0.1 (research prototype)"}
DEPTHS = [("0-5cm", 5), ("5-15cm", 10), ("15-30cm", 15)]
PROPS = ["clay", "sand", "silt", "phh2o", "soc", "cec"]


def usda_texture(sand: float, silt: float, clay: float) -> str:
    """USDA texture class from percentages."""
    if clay >= 40 and sand <= 45 and silt < 40:
        return "clay"
    if clay >= 40 and silt >= 40:
        return "silty clay"
    if clay >= 35 and sand > 45:
        return "sandy clay"
    if clay >= 27 and sand <= 20:
        return "silty clay loam"
    if clay >= 27 and sand <= 45:
        return "clay loam"
    if clay >= 20 and sand > 45 and silt < 28:
        return "sandy clay loam"
    if silt >= 80 and clay < 12:
        return "silt"
    if silt >= 50 and (clay >= 12 or silt < 80):
        if clay < 27:
            return "silt loam"
    if clay < 20 and (sand > 52 or (clay < 7 and silt < 50 and sand > 43)):
        if sand >= 85 and clay < 10 and (silt + 1.5 * clay) < 15:
            return "sand"
        if (silt + 1.5 * clay) >= 15 and (silt + 2 * clay) < 30:
            return "loamy sand"
        return "sandy loam"
    return "loam"


def fetch_soil(lat: float, lon: float) -> dict | None:
    """Return a dict of 0-30 cm weighted means, or None if the service is unavailable."""
    params = [("lon", lon), ("lat", lat), ("value", "mean")]
    params += [("property", p) for p in PROPS]
    params += [("depth", d) for d, _ in DEPTHS]
    try:
        r = requests.get(URL, params=params, headers=UA, timeout=25)
        r.raise_for_status()
        js = r.json()
    except Exception:
        return None
    weights = dict(DEPTHS)
    out: dict[str, float] = {}
    try:
        for layer in js["properties"]["layers"]:
            name = layer["name"]
            d_factor = float(layer.get("unit_measure", {}).get("d_factor", 1) or 1)
            tot, wsum = 0.0, 0.0
            for dep in layer["depths"]:
                v = dep["values"].get("mean")
                w = weights.get(dep["label"])
                if v is None or w is None:
                    continue
                tot += (float(v) / d_factor) * w
                wsum += w
            if wsum:
                out[name] = tot / wsum
    except (KeyError, TypeError, ValueError):
        return None
    if not out:
        return None
    # SoilGrids texture fractions are in g/kg after dividing by d_factor -> percent = /10
    for k in ("clay", "sand", "silt"):
        if k in out:
            out[k] = out[k] / 10.0
    if all(k in out for k in ("clay", "sand", "silt")):
        out["texture_class"] = usda_texture(out["sand"], out["silt"], out["clay"])
    return out


def describe_soil(s: dict) -> str:
    parts = []
    if "texture_class" in s:
        parts.append(
            f"estimated texture (0-30 cm) {s['texture_class']} (sand {s['sand']:.0f}%, silt {s['silt']:.0f}%, clay {s['clay']:.0f}%)"
        )
    if "phh2o" in s:
        parts.append(f"pH(H2O) about {s['phh2o']:.1f}")
    if "soc" in s:
        parts.append(f"soil organic carbon about {s['soc']:.1f} g/kg")
    if "cec" in s:
        parts.append(f"CEC about {s['cec']:.1f} cmol(c)/kg")
    return "; ".join(parts) + ". 250 m grid estimate with uncertainty; does not include salinity."
