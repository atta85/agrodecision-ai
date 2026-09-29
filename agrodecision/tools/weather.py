"""Open-Meteo: free for non-commercial use, no API key. Attribution: CC BY 4.0.
Docs: https://open-meteo.com  (fair use; contact them above 10,000 requests/day
or for commercial use)."""
from __future__ import annotations

import requests

GEO_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
UA = {"User-Agent": "AgroDecisionAI/0.1 (research prototype)"}


def geocode(name: str, country_code: str = "", count: int = 8) -> list[dict]:
    params = {"name": name, "count": count, "language": "en", "format": "json"}
    if country_code:
        params["countryCode"] = country_code
    r = requests.get(GEO_URL, params=params, headers=UA, timeout=15)
    r.raise_for_status()
    out = []
    for it in r.json().get("results", []) or []:
        if country_code and it.get("country_code") and it["country_code"].upper() != country_code.upper():
            continue
        out.append(
            {
                "name": it.get("name"),
                "admin1": it.get("admin1", ""),
                "admin2": it.get("admin2", ""),
                "country": it.get("country", ""),
                "lat": it.get("latitude"),
                "lon": it.get("longitude"),
                "elevation": it.get("elevation"),
            }
        )
    return out


def fetch_weather(lat: float, lon: float) -> dict:
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum,et0_fao_evapotranspiration",
        "current": "temperature_2m,relative_humidity_2m",
        "past_days": 14,
        "forecast_days": 7,
        "timezone": "auto",
    }
    r = requests.get(FORECAST_URL, params=params, headers=UA, timeout=20)
    r.raise_for_status()
    return r.json()


def _clean(seq):
    return [float(x) for x in (seq or []) if x is not None]


def _mean(seq):
    s = _clean(seq)
    return sum(s) / len(s) if s else None


def summarize_weather(data: dict) -> tuple[str, dict]:
    """Return (text summary for the agents, numbers dict). Index 0-13 = past 14 days,
    14 = today, 15-20 = next 6 days."""
    d = data.get("daily", {})
    tmax, tmin = d.get("temperature_2m_max", []), d.get("temperature_2m_min", [])
    rain, et0 = d.get("precipitation_sum", []), d.get("et0_fao_evapotranspiration", [])
    past = slice(0, 14)
    fut = slice(14, None)
    nums = {
        "past14_mean_tmax": _mean(tmax[past]),
        "past14_mean_tmin": _mean(tmin[past]),
        "past14_max_tmax": max(_clean(tmax[past]), default=None),
        "past14_days_ge_35C": sum(1 for x in _clean(tmax[past]) if x >= 35),
        "past14_rain_mm": sum(_clean(rain[past])),
        "past14_et0_mm": sum(_clean(et0[past])),
        "next7_rain_mm": sum(_clean(rain[fut])),
        "next7_mean_tmax": _mean(tmax[fut]),
        "current_temp": (data.get("current") or {}).get("temperature_2m"),
        "current_rh": (data.get("current") or {}).get("relative_humidity_2m"),
    }
    nums["past14_water_balance_mm"] = nums["past14_rain_mm"] - nums["past14_et0_mm"]

    def f(v, nd=1):
        return "n/a" if v is None else f"{v:.{nd}f}"

    text = (
        f"Last 14 days: mean daily max {f(nums['past14_mean_tmax'])} C, mean daily min {f(nums['past14_mean_tmin'])} C, "
        f"hottest day {f(nums['past14_max_tmax'])} C, days at or above 35 C: {nums['past14_days_ge_35C']}. "
        f"Rain total {f(nums['past14_rain_mm'])} mm vs reference evapotranspiration {f(nums['past14_et0_mm'])} mm "
        f"(water balance {f(nums['past14_water_balance_mm'])} mm; negative = atmosphere demanded more water than rain supplied). "
        f"Next 7 days (incl. today): rain {f(nums['next7_rain_mm'])} mm, mean max {f(nums['next7_mean_tmax'])} C. "
        f"Now: {f(nums['current_temp'])} C, humidity {f(nums['current_rh'],0)} %."
    )
    return text, nums
