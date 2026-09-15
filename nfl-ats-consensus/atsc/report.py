"""
The weekly card, rendered as markdown and committed to the repo.

This is the artifact you actually read on Sunday morning, and the permanent
record that settles any later argument about what a model said and when.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

STARS = {1: "★", 2: "★★", 3: "★★★", 4: "★★★★", 5: "★★★★★"}


def _stars(n: Any) -> str:
    try:
        return STARS.get(int(n), "?")
    except (TypeError, ValueError):
        return "?"


def _line_text(g: dict) -> str:
    sp = float(g["cbs_spread_home"])
    if sp == 0:
        return "PK"
    fav = g["home_team"] if sp < 0 else g["away_team"]
    return f"{fav} {-abs(sp):.1f}"


def weekly_card(lock: dict, submissions: list[dict], disagreements: dict,
                house: dict | None = None, violations: list[dict] | None = None) -> str:
    season, week = lock["season"], lock["week"]
    games = {g["game_id"]: g for g in lock["games"]}
    models = [s.get("model") for s in submissions]

    out: list[str] = []
    A = out.append

    A(f"# {season} Week {week} — consensus card")
    A("")
    A(f"**Locked CBS Tuesday line** · digest `{lock['lock']['sha256'][:24]}…` · "
      f"locked {lock['lock']['locked_at_utc']} by {lock['lock']['locked_by']}")
    A("")
    A(f"Field: {', '.join(models)} ({len(models)} models)")
    A("")

    if violations:
        A("## Line violations")
        A("")
        A("Picks made against a number other than the locked line. Voided, not down-weighted.")
        A("")
        for v in violations:
            A(f"- `{v['model']}` on `{v['game_id']}` — {v['kind']}: "
              f"used {v['used']} vs locked {v['locked']} → **{v['action']}**")
        A("")

    if house:
        A("## House card")
        A("")
        hc = house.get("house_card", {})
        if hc.get("best_bet"):
            A(f"- **Best bet:** {hc['best_bet']}")
        for label, key in (("4★", "four_star"), ("3★", "three_star"), ("Avoid", "avoid")):
            vals = hc.get(key) or []
            if vals:
                A(f"- **{label}:** {', '.join(str(v) for v in vals)}")
        if house.get("slate_notes"):
            A("")
            A(f"> {house['slate_notes']}")
        A("")

    # The full grid: every model's position on every game, at a glance.
    A("## Every model, every game")
    A("")
    header = "| matchup | locked | " + " | ".join(models) + " |"
    A(header)
    A("|" + "---|" * (len(models) + 2))

    by_model_game: dict[str, dict[str, dict]] = {
        s.get("model"): {p.get("game_id"): p for p in s.get("picks", [])} for s in submissions}

    for gid, g in games.items():
        cells = []
        for m in models:
            p = by_model_game.get(m, {}).get(gid)
            cells.append(f"{p.get('pick_team')} {_stars(p.get('stars'))}" if p else "—")
        A(f"| {g['away_team']} @ {g['home_team']} | {_line_text(g)} | " + " | ".join(cells) + " |")
    A("")

    # Contested games, with each model's one-line reason, because that is where
    # the value is and where the rebuttal round gets spent.
    contested = disagreements.get("split", []) + disagreements.get("majority", [])
    if contested:
        A("## Contested games")
        A("")
        for e in contested:
            A(f"### {e['matchup']} — locked home {e['locked_spread_home']:+.1f}")
            A("")
            for p in e["positions"]:
                A(f"- **{p['model']}** → {p['pick']} {_stars(p['stars'])} — {p['headline']}")
            A("")

    fragile = disagreements.get("fragile_consensus", [])
    if fragile:
        A("## Fragile consensus")
        A("")
        A("Unanimous, but every model gave substantially the same reason. That is one "
          "argument counted N times, not N pieces of evidence — the classic shape of a "
          "correlated miss.")
        A("")
        for e in fragile:
            A(f"- **{e['matchup']}** — all {e['n_models']} on "
              f"{e['positions'][0]['pick']}, headline overlap {e['headline_overlap']}")
        A("")

    unanimous = disagreements.get("unanimous", [])
    if unanimous:
        A("## Unanimous (independent reasoning)")
        A("")
        for e in unanimous:
            A(f"- **{e['matchup']}** — all on {e['positions'][0]['pick']}")
        A("")

    A("---")
    A("")
    A("Dossiers built from nflfastR/nflverse open data. Spread and total from CBS "
      "Sports, entered once on Tuesday and frozen. Every model above was given a "
      "byte-identical evidence packet.")
    return "\n".join(out)


def results_card(lock: dict, reports: list[dict], board: str) -> str:
    season, week = lock["season"], lock["week"]
    out: list[str] = []
    A = out.append

    A(f"# {season} Week {week} — results")
    A("")
    A(f"Graded against locked digest `{lock['lock']['sha256'][:24]}…`")
    A("")
    A("## Leaderboard")
    A("")
    A(board)
    A("")
    A("Score is stars-weighted and asymmetric — a 5★ loss costs more than a 5★ win "
      "gains. A model can win the record and lose the score by being confident in "
      "the wrong places, which is the failure the raw record hides.")
    A("")

    A("## Calibration")
    A("")
    for r in sorted(reports, key=lambda x: -x["score"]):
        c = r["calibration"]
        A(f"- **{r['model']}** — {c['verdict']}: {c['detail']}")
        if r.get("voided_picks"):
            A(f"  - voided for line violations: {', '.join(r['voided_picks'])}")
    A("")

    A("## Declared methods")
    A("")
    A("Each model chose its own approach. Nothing in the prompt prescribes one, so "
      "over the season this table is how a method earns or loses credibility.")
    A("")
    A("| model | approach | why | record | score |")
    A("|---|---|---|---|---|")
    for r_ in sorted(reports, key=lambda x: -x["score"]):
        m = r_.get("method") or {}
        A(f"| {r_['model']} | {m.get('approach', '—')} | {m.get('why_this_one', '—')} | "
          f"{r_['record']} | {r_['score']:+.1f} |")
    A("")
    gaps = {r_["model"]: r_.get("data_gaps") for r_ in reports if r_.get("data_gaps")}
    if gaps:
        A("Data the field said it wanted and did not have:")
        A("")
        for model, gl in gaps.items():
            A(f"- **{model}** — {'; '.join(gl)}")
        A("")

    A("## Every pick")
    A("")
    for r in sorted(reports, key=lambda x: -x["score"]):
        A(f"### {r['model']} — {r['record']} (score {r['score']:+.1f})")
        A("")
        A("| matchup | pick | stars | ATS margin | result |")
        A("|---|---|---|---|---|")
        for g in sorted(r["games"], key=lambda x: -x["stars"]):
            mark = {"win": "W", "loss": "L", "push": "P"}[g["result"]]
            A(f"| {g['matchup']} | {g['pick_team']} {g['pick_line']:+.1f} | "
              f"{_stars(g['stars'])} | {g['ats_margin']:+.1f} | **{mark}** |")
        A("")
    return "\n".join(out)


def load_house(path: Path) -> dict | None:
    """The adjudicator's reply, if you have saved it."""
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
