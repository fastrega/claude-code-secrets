"""
Prompt pack rendering.

One function, one guarantee: every model receives byte-identical instructions and
byte-identical evidence. The only thing that varies between models is the model.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROMPTS = Path(__file__).resolve().parents[1] / "prompts"


def _tpl(name: str) -> str:
    return (PROMPTS / name).read_text()


def _fill(template: str, mapping: dict[str, Any]) -> str:
    """
    Placeholder substitution that leaves the JSON examples alone.

    The templates escape their literal braces as {{ }}, so a plain str.format on
    an unescaped template would explode on the schema blocks. We do targeted
    replacement instead and then unescape.
    """
    out = template
    for k, v in mapping.items():
        out = out.replace("{" + k + "}", str(v))
    return out.replace("{{", "{").replace("}}", "}")


def pick_pack(lock: dict, dossiers: dict[str, str], order_seed: str | None = None) -> str:
    """
    Render the shared pack.

    `order_seed` shuffles the game order deterministically per model. Position in a
    long document measurably affects how much attention a model gives an item, so a
    fixed order would hand every model the same positional bias — and correlated
    bias across the field is exactly what makes a consensus worthless. Seeding by
    model name keeps each model's own pack reproducible.
    """
    gids = sorted(dossiers)
    if order_seed:
        import random
        random.Random(order_seed).shuffle(gids)
    joined = "\n\n---\n\n".join(dossiers[g] for g in gids)
    return _fill(_tpl("01_pick.md"), {
        "LOCK_SHA256": lock["lock"]["sha256"],
        "LOCKED_AT": lock["lock"]["locked_at_utc"],
        "SEASON": lock["season"],
        "WEEK": lock["week"],
        "N_GAMES": len(dossiers),
        "DOSSIERS": joined,
    })


def rebuttal_pack(lock: dict, game: dict, mine: dict, opposing: list[dict]) -> str:
    spread = float(game["cbs_spread_home"])
    home, away = game["home_team"], game["away_team"]
    fav, dog = (home, away) if spread < 0 else (away, home)
    line_text = (f"{fav} {-abs(spread):.1f} / {dog} +{abs(spread):.1f}"
                 if spread else "PICK'EM")

    blocks = []
    for o in opposing:
        blocks.append(
            f"## {o.get('model', 'unknown model')} — picks **{o.get('pick_team')}** "
            f"({o.get('stars')} stars)\n\n"
            f"- Their reason: {o.get('headline_reason')}\n"
            f"- Projected home margin: {o.get('projected_margin_home')}\n"
            f"- Risk they named: {o.get('key_risk')}\n"
            + (f"\n{o['analysis']}\n" if o.get("analysis") else "")
        )

    return _fill(_tpl("02_rebuttal.md"), {
        "MATCHUP": f"{away} @ {home}",
        "LINE_TEXT": line_text,
        "SPREAD_HOME:+.1f": f"{spread:+.1f}",
        "SPREAD_HOME": f"{spread:+.1f}",
        "LOCK_SHA256": lock["lock"]["sha256"],
        "GAME_ID": game["game_id"],
        "YOUR_PICK": mine.get("pick_team"),
        "YOUR_LINE:+.1f": f"{float(mine.get('pick_line', 0)):+.1f}",
        "YOUR_LINE": f"{float(mine.get('pick_line', 0)):+.1f}",
        "YOUR_STARS": mine.get("stars"),
        "YOUR_HEADLINE": mine.get("headline_reason"),
        "YOUR_RISK": mine.get("key_risk"),
        "OPPOSING": "\n\n".join(blocks) or "(no opposing submissions)",
    })


def adjudicate_pack(lock: dict, submissions: list[dict], rebuttals: list[dict],
                    line_audit: str) -> str:
    subs = "\n\n".join(
        f"## {s.get('model')}\n```json\n{json.dumps(s, indent=2)}\n```" for s in submissions)
    rebs = "\n\n".join(
        f"## {r.get('model')} on {r.get('game_id')}\n```json\n{json.dumps(r, indent=2)}\n```"
        for r in rebuttals) or "(no rebuttal round was run)"
    return _fill(_tpl("03_adjudicate.md"), {
        "SEASON": lock["season"], "WEEK": lock["week"],
        "LOCK_SHA256": lock["lock"]["sha256"],
        "LINE_AUDIT": line_audit,
        "SUBMISSIONS": subs,
        "REBUTTALS": rebs,
    })


def postmortem_pack(lock: dict, model: str, report: dict, field_table: str,
                    contrarian: str) -> str:
    rows = ["| game | pick | line | stars | result | margin |",
            "|---|---|---|---|---|---|"]
    for g in report["games"]:
        rows.append(f"| {g['matchup']} | {g['pick_team']} | {g['pick_line']:+.1f} | "
                    f"{g['stars']} | {g['result']} | {g['actual_margin_home']:+.0f} |")
    return _fill(_tpl("04_postmortem.md"), {
        "SEASON": lock["season"], "WEEK": lock["week"],
        "LOCK_SHA256": lock["lock"]["sha256"],
        "RECORD": report["record"],
        "WIN_PCT": f"{report['win_pct']:.1%}",
        "WEIGHTED_RECORD": report["weighted_summary"],
        "RESULTS_TABLE": "\n".join(rows),
        "FIELD_COMPARISON": field_table,
        "CONTRARIAN_GAMES": contrarian,
    })
