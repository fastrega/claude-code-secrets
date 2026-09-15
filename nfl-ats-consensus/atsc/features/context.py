"""
Situational context: rest, travel, body-clock, altitude, surface change, roof
change, and game-day weather.

Weather is fetched from Open-Meteo (free, no API key, no registration). If the
host's network blocks it the fetch degrades to a clearly-labelled UNKNOWN rather
than a silent zero — a model told "wind 0 mph" when nobody checked will make a
confident wrong call about a total or a kicking game.
"""

from __future__ import annotations

import json
import math
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

CONFIG = Path(__file__).resolve().parents[2] / "config" / "team_meta.json"
TEAMS: dict[str, Any] = json.loads(CONFIG.read_text())

TZ_OFFSET = {"America/New_York": 0, "America/Chicago": -1, "America/Denver": -2,
             "America/Phoenix": -2, "America/Los_Angeles": -3}

# Wind is the weather variable with the largest well-replicated effect on passing
# and kicking. Temperature on its own has a much smaller measured effect. Bands
# below describe what has been measured, not what to do about it.
WIND_BANDS = [
    (0, 8, "negligible", "No measurable effect on passing or kicking in the data."),
    (8, 12, "mild", "Small measured drag on deep attempts; FG accuracy inside 45 unchanged."),
    (12, 15, "notable", "Deep passing efficiency measurably declines; 50+ FG accuracy declines."),
    (15, 20, "significant", "Passing EPA and deep accuracy decline measurably; observed pass rates fall."),
    (20, 99, "severe", "Large measured declines in passing efficiency and FG accuracy beyond 45."),
]


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def wind_band(mph: float | None) -> tuple[str, str]:
    if mph is None:
        return "unknown", "Weather not retrieved — treat wind as an open question, not a zero."
    for lo, hi, label, meaning in WIND_BANDS:
        if lo <= mph < hi:
            return label, meaning
    return "unknown", ""


def fetch_weather(lat: float, lon: float, date: str, hour: int) -> dict[str, Any]:
    """Open-Meteo forecast for kickoff hour. Returns {'available': False, ...} if blocked."""
    url = (f"https://api.open-meteo.com/v1/forecast?latitude={lat:.4f}&longitude={lon:.4f}"
           f"&hourly=temperature_2m,precipitation_probability,wind_speed_10m,wind_gusts_10m"
           f"&temperature_unit=fahrenheit&wind_speed_unit=mph&start_date={date}&end_date={date}"
           f"&timezone=auto")
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            data = json.loads(r.read())
        h = data["hourly"]
        idx = min(range(len(h["time"])),
                  key=lambda i: abs(int(h["time"][i][11:13]) - hour))
        return {
            "available": True,
            "temp_f": h["temperature_2m"][idx],
            "wind_mph": h["wind_speed_10m"][idx],
            "gust_mph": h["wind_gusts_10m"][idx],
            "precip_pct": h["precipitation_probability"][idx],
            "source": "open-meteo",
        }
    except Exception as e:  # network policy, DNS, upstream outage
        return {"available": False, "reason": f"{type(e).__name__}: {e}", "source": "open-meteo"}


def game_context(game: dict[str, Any], *, with_weather: bool = True) -> dict[str, Any]:
    """Everything environmental about one matchup, for both teams."""
    home, away = game["home_team"], game["away_team"]
    hm, am = TEAMS[home], TEAMS[away]

    venue_roof = str(game.get("roof") or hm["roof"] or "").lower()
    indoor = venue_roof in {"dome", "closed"}

    ctx: dict[str, Any] = {
        "venue": hm["stadium"],
        "roof": venue_roof or "unknown",
        "indoor": indoor,
        "surface": game.get("surface") or hm["surface"],
        "altitude_ft": hm["alt_ft"],
        "altitude_note": ("~17% lower air density than sea level; measurably affects "
                          "kick distance and ball carry." if hm["alt_ft"] > 4000 else ""),
        "travel_miles": round(haversine_miles(am["lat"], am["lon"], hm["lat"], hm["lon"])),
        "tz_shift_hours": TZ_OFFSET.get(hm["tz"], 0) - TZ_OFFSET.get(am["tz"], 0),
        "home_rest_days": game.get("home_rest"),
        "away_rest_days": game.get("away_rest"),
        "kickoff_local": f"{game.get('gameday')} {game.get('gametime')} ({game.get('weekday')})",
    }

    # Body clock: a West Coast team playing a 1pm Eastern kickoff starts at 10am
    # body time. Reported as the hour; the size of the effect is the analyst's call.
    shift = ctx["tz_shift_hours"]
    try:
        kick_hour = int(str(game.get("gametime", "13:00")).split(":")[0])
    except Exception:
        kick_hour = 13
    ctx["away_body_clock_hour"] = kick_hour - shift
    if shift >= 2 and kick_hour <= 13:
        ctx["body_clock_note"] = (f"{away} travels {shift}h east for a {kick_hour}:00 kick — "
                                  f"{ctx['away_body_clock_hour']}:00 body time.")
    elif shift <= -2 and kick_hour >= 20:
        ctx["body_clock_note"] = (f"{away} travels {abs(shift)}h west for a night game — "
                                  f"{ctx['away_body_clock_hour']}:00 body time.")
    else:
        ctx["body_clock_note"] = ""

    # Rest asymmetry (the Thursday-game hangover, the mini-bye, the true bye).
    hr, ar = ctx["home_rest_days"], ctx["away_rest_days"]
    if hr is not None and ar is not None:
        diff = hr - ar
        ctx["rest_edge_days"] = diff
        ctx["rest_note"] = (
            f"{home} +{diff} days rest" if diff >= 2 else
            f"{away} +{-diff} days rest" if diff <= -2 else "even rest"
        )
    else:
        ctx["rest_edge_days"] = None
        ctx["rest_note"] = "rest unknown"

    # Surface / roof transitions — the dome-offence-outdoors problem.
    ctx["away_home_roof"] = am["roof"]
    ctx["away_home_surface"] = am["surface"]
    ctx["roof_change"] = (am["roof"] in {"dome", "closed"}) and not indoor
    ctx["surface_change"] = (am["surface"] == "grass") != (str(ctx["surface"]) == "grass")
    if ctx["roof_change"]:
        ctx["roof_change_note"] = f"{away} plays home games indoors; this game is outdoors."
    else:
        ctx["roof_change_note"] = ""

    if indoor:
        ctx["weather"] = {"available": True, "indoor": True,
                          "summary": "Indoors — weather is a non-factor."}
    elif with_weather:
        w = fetch_weather(hm["lat"], hm["lon"], str(game.get("gameday")), kick_hour)
        if w.get("available"):
            band, meaning = wind_band(w["wind_mph"])
            w["wind_band"] = band
            w["wind_meaning"] = meaning
            w["summary"] = (f"{w['temp_f']:.0f}°F, wind {w['wind_mph']:.0f} mph "
                            f"(gusts {w['gust_mph']:.0f}), precip {w['precip_pct']}% — {band}. {meaning}")
        else:
            w["summary"] = ("WEATHER UNAVAILABLE — do not assume calm conditions. "
                            "Fill this in manually from NFLWeather.com before finalising.")
        ctx["weather"] = w
    else:
        ctx["weather"] = {"available": False, "summary": "weather fetch disabled"}

    return ctx


def injury_report(inj_df, team: str, week: int) -> list[dict[str, Any]]:
    """Latest official report rows for a team, ordered by how much they matter."""
    if inj_df is None or len(inj_df) == 0:
        return []
    d = inj_df[(inj_df["team"] == team) & (inj_df["week"] == week)]
    if d.empty:  # report may not be posted yet; fall back to the most recent week
        avail = inj_df[inj_df["team"] == team]["week"]
        if avail.empty:
            return []
        d = inj_df[(inj_df["team"] == team) & (inj_df["week"] == avail.max())]

    weight = {"Out": 3, "Doubtful": 3, "Injured Reserve": 3, "Questionable": 2}
    pos_weight = {"QB": 10, "LT": 6, "T": 5, "WR": 4, "CB": 4, "EDGE": 4, "DE": 4,
                  "RB": 3, "TE": 3, "G": 3, "C": 3, "S": 3, "LB": 2, "DT": 3}

    def clean(value) -> str:
        """nflverse leaves blanks as NaN; NaN is truthy, so `or` will not catch it."""
        import pandas as _pd
        return "" if value is None or _pd.isna(value) else str(value).strip()

    rows = []
    for r in d.itertuples():
        st = clean(getattr(r, "report_status", None))
        pr = clean(getattr(r, "practice_status", None))
        inj = clean(getattr(r, "report_primary_injury", None)) or \
            clean(getattr(r, "practice_primary_injury", None))
        rows.append({
            "player": r.full_name,
            "pos": r.position,
            # No game status means the player appears on the practice report only —
            # a limited rep on Wednesday is not a game designation and must not read
            # like one.
            "status": st or "practice-report only (no game designation)",
            "has_game_status": bool(st),
            "injury": inj or "unspecified",
            "practice": pr,
            "_severity": weight.get(st, 1) * pos_weight.get(str(r.position), 2),
        })
    rows.sort(key=lambda x: -x["_severity"])
    return rows


def unit_health(rows: list[dict[str, Any]]) -> dict[str, str]:
    """
    A crude 0-100 health score per unit, in the spirit of SICScore, from public
    report data only. It is a triage tool: it tells a model which unit to go
    read about, it does not replace a physician's grade.
    """
    units = {"QB": ["QB"], "OL": ["T", "LT", "RT", "G", "LG", "RG", "C", "OL"],
             "PASS_CATCH": ["WR", "TE"], "RB": ["RB", "FB"],
             "SECONDARY": ["CB", "S", "FS", "SS", "DB"],
             "FRONT7": ["DE", "DT", "EDGE", "LB", "ILB", "OLB", "NT"]}
    cost = {"Out": 34, "Injured Reserve": 34, "Doubtful": 26, "Questionable": 10}
    out = {}
    for unit, positions in units.items():
        score = 100
        hits = []
        for r in rows:
            if str(r["pos"]).upper() in positions:
                c = cost.get(r["status"], 4)
                score -= c
                if c >= 10:
                    hits.append(f"{r['player']} ({r['pos']}, {r['status']})")
        score = max(0, score)
        label = "healthy" if score >= 90 else "dinged" if score >= 70 else "compromised" if score >= 45 else "gutted"
        out[unit] = f"{score}/100 {label}" + (f" — {', '.join(hits[:3])}" if hits else "")
    return out
