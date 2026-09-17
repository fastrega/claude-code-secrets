"""
Compact paste-ready prompt.

The full prompt pack is ~45k tokens of dossiers, which is right for an API call
and hopeless for a chat box. This renders the same locked line and the same
evidence, condensed to something a person can paste into ChatGPT, Gemini, Grok
or Manus by hand.

It is a summary, not a different question: the line, the efficiency ratings, the
variance ledger, the practice report and the situational notes all come from the
same artifacts the full pack is built from, so a model answering this is still
answering against the identical locked number.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd


def _dnp_summary(inj: pd.DataFrame, team: str, week: int, limit: int = 6) -> str:
    """Wednesday practice reality, which is what exists before Friday."""
    d = inj[(inj.team == team) & (inj.week == week)]
    stale = False
    if d.empty:
        avail = inj[inj.team == team]["week"]
        if avail.empty:
            return "no injury rows"
        d = inj[(inj.team == team) & (inj.week == avail.max())]
        stale = True

    def clean(v):
        return "" if v is None or pd.isna(v) else str(v).strip()

    desig, dnp, ltd = [], [], []
    for r in d.itertuples():
        name, pos = r.full_name, r.position
        status = clean(getattr(r, "report_status", None))
        prac = clean(getattr(r, "practice_status", None))
        if status:
            desig.append(f"{name} ({pos}) {status}")
        elif "Did Not" in prac:
            dnp.append(f"{name} ({pos})")
        elif "Limited" in prac:
            ltd.append(f"{name} ({pos})")

    bits = []
    if desig:
        bits.append("DESIGNATED: " + ", ".join(desig[:limit]))
    if dnp:
        bits.append("DNP: " + ", ".join(dnp[:limit]))
    if ltd:
        bits.append("limited: " + ", ".join(ltd[:4]))
    out = " | ".join(bits) or "clean report"
    return ("[WEEK-1 FALLBACK, no current rows] " if stale else "") + out


def render(lock: dict, tt: pd.DataFrame, sched: pd.DataFrame, inj: pd.DataFrame,
           week: int, data_gaps: list[str]) -> str:
    L = {g["game_id"]: g for g in lock["games"]}
    srows = sched.set_index("game_id")

    def v(team: str, col: str) -> float:
        try:
            return float(tt.loc[team, col])
        except Exception:
            return float("nan")

    def f(x: float, dp: int = 3) -> str:
        return "n/a" if pd.isna(x) else f"{x:+.{dp}f}"

    out: list[str] = []
    A = out.append

    A("# NFL Week %d — against-the-spread picks" % week)
    A("")
    A("You are competing against several other AI models on the same slate, from the")
    A("same evidence. Your picks will be graded and then attacked by the models that")
    A("disagree with you.")
    A("")
    A("## RULE 1 — THE LINE IS FIXED")
    A("")
    A("Every pick must use the CBS Sports Tuesday line in the table below. That line is")
    A("frozen for the week and is what you will be graded against.")
    A("")
    A(f"- Line lock digest: `{lock['lock']['sha256']}`")
    A(f"- Captured: {lock['games'][0].get('captured_at')} from CBS Sports")
    A("")
    A("- Do NOT use a live line, another book, or a number you remember. Several of")
    A("  these have already moved in the market; the CBS number is still the one.")
    A("- News changes your CONFIDENCE. It never changes the NUMBER.")
    A("- Restate the spread in every pick. A pick made against a different number is")
    A("  VOIDED, not down-weighted.")
    A("")
    A("## RULE 2 — SHORT ANSWERS")
    A("")
    A("Do your full research. Report almost none of it. One line per game: the pick, a")
    A("star rating, one sentence of reasoning, one sentence of risk. You will be asked")
    A("to defend your reasoning in depth later, and only on the games where the field")
    A("splits. Long answers here are not rewarded.")
    A("")
    A("## RULE 3 — YOUR METHOD IS YOURS")
    A("")
    A("Nobody is telling you to run a simulation, build power ratings, browse, or reason")
    A("qualitatively. Choose your approach, and state it in one line at the top with why")
    A("you picked it over the alternatives. That declaration is scored against results")
    A("over the season, so describe what you actually did.")
    A("")
    A("You are answering alone. You have not seen any other model's picks. Do not guess")
    A("what the field thinks and position with or against it — contrarianism is not a")
    A("method and neither is consensus-chasing. Where the data below is thin, say so")
    A("rather than filling the gap from memory.")
    A("")
    A("## STARS")
    A("")
    A("| Stars | Meaning | Weekly cap |")
    A("|---|---|---|")
    A("| 1 | Lean, would not bet it | none |")
    A("| 2 | Slight edge | none |")
    A("| 3 | Solid researched edge | ~6 |")
    A("| 4 | Strong conviction, several factors agree | 3 |")
    A("| 5 | Best bet, market is wrong for a nameable reason | **1** |")
    A("")
    A("Grading is stars-weighted and asymmetric: a 5-star loss costs more than a 5-star")
    A("win gains. Going 9-7 with confidence in the right places beats 10-6 with it in")
    A("the wrong places. Every pick needs a named risk.")
    A("")
    A("## THE LOCKED LINES")
    A("")
    A("Negative = home team favoured.")
    A("")
    A("| # | Matchup | CBS line | home spread |")
    A("|---|---|---|---|")
    for i, (gid, g) in enumerate(L.items(), 1):
        sp = float(g["cbs_spread_home"])
        fav = g["home_team"] if sp < 0 else g["away_team"]
        txt = "PICK'EM" if sp == 0 else f"{fav} {-abs(sp):.1f}"
        A(f"| {i} | {g['away_team']} @ {g['home_team']} | {txt} | {sp:+.1f} |")
    A("")

    A("## EVIDENCE")
    A("")
    A("`adjNet` is opponent-adjusted EPA per play (offence minus defence), blended with")
    A("last season because one week is not a rating. `luck` is the gap between the")
    A("scoreboard margin and the EPA-implied margin in Week 1: positive means the team")
    A("won by more than it played, negative means it played better than the result.")
    A("Both are measurements. What they mean for a spread is your call, not ours.")
    A("")
    for gid, g in L.items():
        h, a = g["home_team"], g["away_team"]
        sp = float(g["cbs_spread_home"])
        row = srows.loc[gid] if gid in srows.index else None
        A(f"### {a} @ {h} — home {sp:+.1f}")
        A(f"- {a}: adjNet {f(v(a,'net_epa_adj'))} (off {f(v(a,'off_epa_adj'))}, "
          f"def {f(v(a,'def_epa_adj'))}), luck {f(v(a,'luck_margin'),1)}")
        A(f"- {h}: adjNet {f(v(h,'net_epa_adj'))} (off {f(v(h,'off_epa_adj'))}, "
          f"def {f(v(h,'def_epa_adj'))}), luck {f(v(h,'luck_margin'),1)}")
        if row is not None:
            roof = str(row.get("roof") or "")
            A(f"- venue: {row.get('stadium')}, roof {roof or 'n/a'}, "
              f"surface {row.get('surface')}; rest {h} {row.get('home_rest')}d vs "
              f"{a} {row.get('away_rest')}d; kickoff {row.get('weekday')} {row.get('gametime')}")
        A(f"- {a} practice: {_dnp_summary(inj, a, week)}")
        A(f"- {h} practice: {_dnp_summary(inj, h, week)}")
        A("")

    A("## WHAT THIS PACKET DOES NOT HAVE")
    A("")
    for gap in data_gaps:
        A(f"- {gap}")
    A("")
    A("If your method needs any of these and you can research them, do. If you cannot,")
    A("say so rather than inventing a value.")
    A("")

    A("## OUTPUT FORMAT")
    A("")
    A("Start with one line: `METHOD: <what you did> — <why over the alternatives>`")
    A("")
    A("Then one row per game, all 16, in this exact format:")
    A("")
    A("```")
    A("<AWAY> @ <HOME> | line: <the locked home spread> | PICK: <TEAM> | <N>★")
    A("  why: <one sentence, max 25 words>")
    A("  risk: <one sentence, max 15 words>")
    A("```")
    A("")
    A("Finish with:")
    A("")
    A("```")
    A("BEST BET: <the single 5-star game, or none>")
    A("GAPS: <data you wanted and did not have>")
    A("```")
    A("")
    A("No other prose.")
    return "\n".join(out)
