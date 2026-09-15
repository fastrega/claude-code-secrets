"""
The battle stage: validate submissions against the locked line, find genuine
disagreements, and generate the rebuttal packs that make models argue.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any


def load_submissions(directory: str | Path) -> list[dict]:
    """Every *.json in the picks directory is one model's card."""
    out = []
    for p in sorted(Path(directory).glob("*.json")):
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError as e:
            raise ValueError(f"{p.name} is not valid JSON: {e}") from e
        data.setdefault("model", p.stem)
        data["_file"] = p.name
        out.append(data)
    return out


def audit_lines(lock: dict, submissions: list[dict]) -> tuple[list[dict], str]:
    """
    The enforcement arm of the line-lock contract.

    A model that priced a game off a different number did not answer the same
    question as everyone else, so its pick on that game cannot enter the
    consensus. This returns machine-readable violations plus a human-readable
    audit block for the adjudicator prompt.
    """
    locked = {g["game_id"]: float(g["cbs_spread_home"]) for g in lock["games"]}
    violations: list[dict] = []

    for s in submissions:
        if s.get("lock_sha256") and s["lock_sha256"] != lock["lock"]["sha256"]:
            violations.append({
                "model": s.get("model"), "game_id": "*",
                "used": s.get("lock_sha256"), "locked": lock["lock"]["sha256"],
                "action": "flagged", "kind": "digest_mismatch",
            })
        for p in s.get("picks", []):
            gid = p.get("game_id")
            if gid not in locked:
                violations.append({"model": s.get("model"), "game_id": gid,
                                   "used": None, "locked": None,
                                   "action": "voided", "kind": "unknown_game"})
                continue
            used = p.get("spread_used_home")
            if used is None:
                violations.append({"model": s.get("model"), "game_id": gid,
                                   "used": None, "locked": locked[gid],
                                   "action": "voided", "kind": "no_spread_stated"})
            elif abs(float(used) - locked[gid]) > 1e-9:
                violations.append({"model": s.get("model"), "game_id": gid,
                                   "used": float(used), "locked": locked[gid],
                                   "action": "voided", "kind": "wrong_line"})

    if not violations:
        lines = [f"All {len(submissions)} submissions used the locked line "
                 f"(`{lock['lock']['sha256'][:16]}…`). No violations."]
    else:
        lines = ["LINE VIOLATIONS DETECTED — the picks below are voided:", ""]
        for v in violations:
            lines.append(f"- `{v['model']}` on `{v['game_id']}`: {v['kind']}, "
                         f"used {v['used']} vs locked {v['locked']} → {v['action']}")
    return violations, "\n".join(lines)


def _valid_picks(lock: dict, submissions: list[dict], violations: list[dict]) -> dict[str, list[dict]]:
    voided = {(v["model"], v["game_id"]) for v in violations if v["action"] == "voided"}
    by_game: dict[str, list[dict]] = defaultdict(list)
    for s in submissions:
        for p in s.get("picks", []):
            if (s.get("model"), p.get("game_id")) in voided:
                continue
            q = dict(p)
            q["model"] = s.get("model")
            by_game[p.get("game_id")].append(q)
    return by_game


def find_disagreements(lock: dict, submissions: list[dict],
                       violations: list[dict] | None = None) -> dict[str, Any]:
    """
    Classify every game by how the field split.

    `fragile_consensus` is the interesting category: unanimous agreement where
    every model leaned on the same single reason. That is one argument wearing
    five hats, and it is where a correlated miss comes from.
    """
    by_game = _valid_picks(lock, submissions, violations or [])
    games = {g["game_id"]: g for g in lock["games"]}
    report: dict[str, Any] = {"split": [], "majority": [], "unanimous": [], "fragile_consensus": []}

    for gid, picks in by_game.items():
        sides = {p["pick_team"] for p in picks}
        g = games.get(gid, {})
        entry = {
            "game_id": gid,
            "matchup": f"{g.get('away_team')} @ {g.get('home_team')}",
            "locked_spread_home": g.get("cbs_spread_home"),
            "positions": [
                {"model": p["model"], "pick": p["pick_team"], "stars": p.get("stars"),
                 "headline": p.get("headline_reason"),
                 "projected_margin_home": p.get("projected_margin_home")}
                for p in sorted(picks, key=lambda x: -(x.get("stars") or 0))
            ],
            "n_models": len(picks),
        }

        if len(sides) > 1:
            counts = defaultdict(int)
            for p in picks:
                counts[p["pick_team"]] += 1
            entry["tally"] = dict(counts)
            # A close split with high stars on both sides is the sharpest test.
            entry["heat"] = sum(p.get("stars") or 0 for p in picks) / max(len(picks), 1)
            bucket = "split" if min(counts.values()) >= len(picks) / 3 else "majority"
            report[bucket].append(entry)
        else:
            # Unanimous. Is it independent agreement or one shared assumption?
            heads = [(p.get("headline_reason") or "").lower() for p in picks]
            words = [set(h.split()) for h in heads if h]
            overlap = 0.0
            if len(words) > 1:
                pairs = [(a & b, a | b) for i, a in enumerate(words) for b in words[i + 1:]]
                overlap = sum(len(i) / max(len(u), 1) for i, u in pairs) / max(len(pairs), 1)
            entry["headline_overlap"] = round(overlap, 2)
            if overlap > 0.45 and len(picks) > 2:
                entry["warning"] = ("every model gave substantially the same reason — "
                                    "treat as one argument, not N")
                report["fragile_consensus"].append(entry)
            else:
                report["unanimous"].append(entry)

    for k in report:
        report[k].sort(key=lambda e: -e.get("heat", 0))
    report["summary"] = {k: len(v) for k, v in report.items() if isinstance(v, list)}
    return report


def rebuttal_assignments(lock: dict, submissions: list[dict], disagreements: dict,
                         include_majority: bool = True) -> list[dict]:
    """
    Who has to answer whom. Each model on a contested game gets the full opposing
    case and must hold, adjust, or flip.
    """
    games = {g["game_id"]: g for g in lock["games"]}
    contested = list(disagreements["split"])
    if include_majority:
        contested += disagreements["majority"]

    by_game = _valid_picks(lock, submissions, [])
    out = []
    for entry in contested:
        gid = entry["game_id"]
        picks = by_game.get(gid, [])
        for mine in picks:
            opposing = [p for p in picks if p["pick_team"] != mine["pick_team"]]
            if not opposing:
                continue
            out.append({"game_id": gid, "game": games[gid], "model": mine["model"],
                        "mine": mine, "opposing": opposing})
    return out
