"""
Grading and the model leaderboard.

Two scores, because they answer different questions:

RECORD          straight ATS win rate — did the picks cash?
WEIGHTED SCORE  stars-weighted, so a confident loss hurts more than a lean loss.
                This is what exposes a model that is right often but confident
                in the wrong places.

Calibration is reported separately, because a model whose 4-stars lose and whose
1-stars win has a fixable problem that the raw record hides.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

# A 5-star loss should cost more than a 5-star win gains: the asymmetry is what
# discourages confidence inflation.
STAR_WIN = {1: 1.0, 2: 1.6, 3: 2.4, 4: 3.4, 5: 4.5}
STAR_LOSS = {1: -1.0, 2: -1.8, 3: -3.0, 4: -4.6, 5: -6.5}


def grade_pick(pick: dict, home_score: float, away_score: float,
               locked_spread_home: float) -> dict:
    """
    ATS result for one pick against the locked number.

    Convention: `locked_spread_home` is negative when the home team is laying
    points. The home side covers when (home margin + spread) > 0.
    """
    margin = float(home_score) - float(away_score)
    adjusted = margin + float(locked_spread_home)

    if abs(adjusted) < 1e-9:
        result = "push"
    else:
        cover_side = "home" if adjusted > 0 else "away"
        result = "win" if pick.get("pick_side") == cover_side else "loss"

    stars = int(pick.get("stars") or 1)
    pts = 0.0 if result == "push" else (STAR_WIN if result == "win" else STAR_LOSS)[stars]

    proj = pick.get("projected_margin_home")
    return {
        "game_id": pick.get("game_id"),
        "matchup": pick.get("matchup"),
        "pick_team": pick.get("pick_team"),
        "pick_side": pick.get("pick_side"),
        "pick_line": float(pick.get("pick_line", locked_spread_home)),
        "locked_spread_home": float(locked_spread_home),
        "stars": stars,
        "actual_margin_home": margin,
        "ats_margin": round(adjusted, 1),
        "result": result,
        "points": pts,
        "projection_error": (round(abs(float(proj) - margin), 1) if proj is not None else None),
        "key_risk": pick.get("key_risk"),
        "headline_reason": pick.get("headline_reason"),
    }


def grade_submission(submission: dict, lock: dict, results: dict[str, tuple[float, float]],
                     violations: list[dict] | None = None) -> dict:
    """
    `results` maps game_id -> (home_score, away_score).

    Picks voided by the line audit are excluded outright rather than scored. A
    model that priced a game off a different number did not answer the same
    question, so neither a win nor a loss there carries information.
    """
    locked = {g["game_id"]: float(g["cbs_spread_home"]) for g in lock["games"]}
    voided = {v["game_id"] for v in (violations or [])
              if v["action"] == "voided" and v.get("model") == submission.get("model")}

    graded = []
    for p in submission.get("picks", []):
        gid = p.get("game_id")
        if gid not in results or gid not in locked or gid in voided:
            continue
        hs, as_ = results[gid]
        graded.append(grade_pick(p, hs, as_, locked[gid]))

    wins = sum(1 for g in graded if g["result"] == "win")
    losses = sum(1 for g in graded if g["result"] == "loss")
    pushes = sum(1 for g in graded if g["result"] == "push")
    decided = wins + losses

    by_star: dict[int, dict[str, int]] = defaultdict(lambda: {"win": 0, "loss": 0, "push": 0})
    for g in graded:
        by_star[g["stars"]][g["result"]] += 1

    errs = [g["projection_error"] for g in graded if g["projection_error"] is not None]

    return {
        "model": submission.get("model"),
        "season": lock["season"],
        "week": lock["week"],
        "lock_sha256": lock["lock"]["sha256"],
        "voided_picks": sorted(voided),
        # Carried through so the season-long question — which methods actually
        # work — can be answered from the graded record rather than from vibes.
        "method": submission.get("method"),
        "data_gaps": submission.get("data_gaps"),
        "games": graded,
        "wins": wins, "losses": losses, "pushes": pushes,
        "record": f"{wins}-{losses}" + (f"-{pushes}" if pushes else ""),
        "win_pct": (wins / decided) if decided else 0.0,
        "score": round(sum(g["points"] for g in graded), 2),
        "by_stars": {str(k): f"{v['win']}-{v['loss']}" + (f"-{v['push']}" if v["push"] else "")
                     for k, v in sorted(by_star.items(), reverse=True)},
        "weighted_summary": " | ".join(
            f"{k}★ {v['win']}-{v['loss']}" for k, v in sorted(by_star.items(), reverse=True)),
        "mean_projection_error": round(sum(errs) / len(errs), 2) if errs else None,
        "calibration": _calibration(by_star),
    }


def _calibration(by_star: dict[int, dict[str, int]]) -> dict[str, Any]:
    """Does higher confidence actually mean a higher hit rate?"""
    pts = []
    for stars, r in by_star.items():
        d = r["win"] + r["loss"]
        if d:
            pts.append((stars, r["win"] / d, d))
    if len(pts) < 2:
        return {"verdict": "insufficient_sample", "detail": "need picks at 2+ star levels"}

    pts.sort()
    lo = [p for p in pts if p[0] <= 2]
    hi = [p for p in pts if p[0] >= 4]
    lo_rate = sum(r * n for _, r, n in lo) / sum(n for _, _, n in lo) if lo else None
    hi_rate = sum(r * n for _, r, n in hi) / sum(n for _, _, n in hi) if hi else None

    if lo_rate is None or hi_rate is None:
        verdict = "insufficient_sample"
    elif hi_rate >= lo_rate + 0.10:
        verdict = "well_calibrated"
    elif hi_rate <= lo_rate - 0.10:
        verdict = "inverted"
    else:
        verdict = "flat"
    return {
        "verdict": verdict,
        "low_conf_rate": round(lo_rate, 3) if lo_rate is not None else None,
        "high_conf_rate": round(hi_rate, 3) if hi_rate is not None else None,
        "detail": {
            "well_calibrated": "high-confidence picks hit meaningfully more often — the star scale is carrying information",
            "inverted": "high-confidence picks hit LESS often than leans — the confidence signal is backwards, fix this before anything else",
            "flat": "stars carry no information; every pick is effectively the same confidence",
            "insufficient_sample": "not enough picks across star levels to judge",
        }[verdict],
    }


def leaderboard(reports: list[dict]) -> str:
    rows = sorted(reports, key=lambda r: (-r["score"], -r["win_pct"]))
    out = ["| # | model | ATS | win% | score | by stars | mean proj err | calibration |",
           "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        out.append(
            f"| {i} | {r['model']} | {r['record']} | {r['win_pct']:.1%} | {r['score']:+.1f} | "
            f"{r['weighted_summary']} | "
            f"{r['mean_projection_error'] if r['mean_projection_error'] is not None else '—'} | "
            f"{r['calibration']['verdict']} |")
    return "\n".join(out)


def conformity_audit(lock: dict, rebuttals: list[dict],
                     results: dict[str, tuple[float, float]]) -> dict[str, Any]:
    """
    Did arguing help, and did anyone fold?

    For every Round 2 decision, grade the position the model ended on. Two failure
    modes matter and they are opposite:

    PUSHOVER   flips that lost — moved off a correct read under argument.
    STUBBORN   holds that lost where the opposing case was right.

    Over a season this is the most honest measure of whether a model is thinking
    independently. A model whose flips are consistently wrong is being persuaded by
    social pressure rather than by evidence, and its Round 2 output should be
    discounted — or it should be dropped from the rebuttal round entirely.
    """
    locked = {g["game_id"]: float(g["cbs_spread_home"]) for g in lock["games"]}
    per_model: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"flip_win": 0, "flip_loss": 0, "hold_win": 0, "hold_loss": 0,
                 "adjust": 0, "detail": []})

    for r in rebuttals:
        gid = r.get("game_id")
        model = r.get("model")
        team = r.get("final_pick_team")
        if gid not in results or gid not in locked or not team:
            continue

        hs, as_ = results[gid]
        game = next((g for g in lock["games"] if g["game_id"] == gid), None)
        if game is None:
            continue
        side = "home" if team == game["home_team"] else "away"
        graded = grade_pick({"game_id": gid, "pick_side": side,
                             "stars": r.get("final_stars", 1)}, hs, as_, locked[gid])

        decision = (r.get("decision") or "").lower()
        # An adjustment keeps the side, so it counts as a hold for win/loss
        # purposes and is tallied separately as a confidence move.
        bucket = "flip" if decision == "flip" else "hold"
        if decision == "adjust_confidence":
            per_model[model]["adjust"] += 1
        if graded["result"] != "push":
            per_model[model][f"{bucket}_{graded['result']}"] += 1

        per_model[model]["detail"].append({
            "game_id": gid, "decision": decision, "final": team,
            "result": graded["result"],
            "reason": r.get("reason_for_decision") or r.get("defense"),
        })

    out: dict[str, Any] = {}
    for model, d in per_model.items():
        flips = d["flip_win"] + d["flip_loss"]
        holds = d["hold_win"] + d["hold_loss"]
        if flips >= 2 and d["flip_loss"] > d["flip_win"]:
            verdict = ("pushover — changing position under argument cost more than it "
                       "gained; discount this model's Round 2 moves")
        elif flips >= 2 and d["flip_win"] > d["flip_loss"]:
            verdict = "persuadable in a good way — flips improved the card"
        elif holds and not flips:
            verdict = "never moved; no evidence either way on persuadability"
        else:
            verdict = "too few decisions to judge"
        out[model] = {
            "flips": f"{d['flip_win']}-{d['flip_loss']}",
            "holds": f"{d['hold_win']}-{d['hold_loss']}",
            "confidence_adjustments": d["adjust"],
            "verdict": verdict,
            "detail": d["detail"],
        }
    return out


def contrarian_games(reports: list[dict], model: str) -> str:
    """Games where one model stood alone — the most informative rows in the week."""
    picks: dict[str, dict[str, dict]] = defaultdict(dict)
    for r in reports:
        for g in r["games"]:
            picks[g["game_id"]][r["model"]] = g

    lines = []
    for gid, by_model in picks.items():
        if model not in by_model or len(by_model) < 3:
            continue
        mine = by_model[model]
        others = [g["pick_team"] for m, g in by_model.items() if m != model]
        if others and all(o != mine["pick_team"] for o in others):
            lines.append(
                f"- **{mine['matchup']}** — you took {mine['pick_team']} ({mine['stars']}★) "
                f"alone against {len(others)} models. Result: **{mine['result'].upper()}** "
                f"(ATS margin {mine['ats_margin']:+.1f}). Your reason: {mine['headline_reason']}")
    return "\n".join(lines) or "- You did not stand alone on any game this week."
