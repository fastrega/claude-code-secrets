"""
Builds the per-game evidence dossier.

The dossier is deliberately *not* an opinion. It is the identical evidence packet
handed to every model in the consensus, so that when two models disagree the
disagreement is about reasoning rather than about who happened to look up which
number. Every section is sourced and every gap is labelled as a gap.
"""

from __future__ import annotations

import pandas as pd

from .features.context import game_context, injury_report, unit_health
from .features.players import breakout_candidates, personnel_losses, snap_trends


def last_game_forensics(pbp: pd.DataFrame, sched: pd.DataFrame, team: str) -> dict:
    """
    What actually happened the last time out, with the noise separated from the
    signal: turnovers, missed kicks, penalties, explosive plays, weather, and the
    gap between the EPA battle and the scoreboard.
    """
    played = sched[(sched["result"].notna())
                   & ((sched["home_team"] == team) | (sched["away_team"] == team))]
    if played.empty:
        return {"available": False, "note": f"{team} has no completed games in this sample."}

    gm = played.sort_values(["week"]).iloc[-1]
    gid = gm["game_id"]
    g = pbp[pbp["game_id"] == gid]
    if g.empty:
        return {"available": False, "note": f"no play-by-play for {gid}"}

    opp = gm["away_team"] if gm["home_team"] == team else gm["home_team"]
    is_home = gm["home_team"] == team
    margin = float(gm["home_score"] - gm["away_score"]) * (1 if is_home else -1)

    scrim = g[g["play_type"].isin(["pass", "run"]) & g["epa"].notna()]
    off_epa = scrim[scrim["posteam"] == team]["epa"].sum()
    def_epa = scrim[scrim["defteam"] == team]["epa"].sum()
    epa_margin = off_epa - def_epa

    to_lost = int(g[(g["posteam"] == team)][["interception", "fumble_lost"]].fillna(0).sum().sum())
    to_won = int(g[(g["defteam"] == team)][["interception", "fumble_lost"]].fillna(0).sum().sum())

    fg = g[(g["posteam"] == team) & g["field_goal_result"].notna()]
    missed = fg[fg["field_goal_result"] != "made"]
    missed_desc = [f"{int(r.kick_distance)}yd {r.field_goal_result}" for r in missed.itertuples()]

    pen = g[(g["penalty"] == 1) & (g["penalty_team"] == team)]
    pen_yds = int(pen["penalty_yards"].fillna(0).sum())

    big = scrim[(scrim["posteam"] == team) & (scrim["epa"] >= 3.0)]
    big_allowed = scrim[(scrim["defteam"] == team) & (scrim["epa"] >= 3.0)]

    # A spread-sized gap between how the game was played and how it finished.
    luck = margin - epa_margin
    if luck > 7:
        verdict = (f"{team} finished {luck:.1f} points BETTER than they played. "
                   f"The record flatters them; the market may not have caught up.")
    elif luck < -7:
        verdict = (f"{team} finished {abs(luck):.1f} points WORSE than they played. "
                   f"Live buy-low candidate if the market is pricing the scoreboard.")
    else:
        verdict = f"Scoreboard matched the play ({luck:+.1f}). Result is broadly honest."

    return {
        "available": True,
        "game_id": gid,
        "opponent": opp,
        "site": "home" if is_home else "away",
        "score": f"{int(gm['home_score'])}-{int(gm['away_score'])} "
                 f"({gm['home_team']} vs {gm['away_team']})",
        "margin": margin,
        "epa_margin": round(float(epa_margin), 1),
        "luck_gap": round(float(luck), 1),
        "luck_verdict": verdict,
        "turnovers_lost": to_lost,
        "turnovers_forced": to_won,
        "turnover_diff": to_won - to_lost,
        "missed_fgs": missed_desc,
        "penalty_yards": pen_yds,
        "explosive_plays_made": len(big),
        "explosive_plays_allowed": len(big_allowed),
        "conditions": _conditions(g, gm),
    }


def _conditions(g: pd.DataFrame, gm) -> str:
    roof = str(gm.get("roof") or "").lower()
    if roof in {"dome", "closed"}:
        return "indoors — no weather factor"
    temp = g["temp"].dropna()
    wind = g["wind"].dropna()
    if temp.empty and wind.empty:
        return "conditions not recorded"
    t = f"{temp.iloc[0]:.0f}°F" if not temp.empty else "temp n/a"
    w = f"{wind.iloc[0]:.0f} mph wind" if not wind.empty else "wind n/a"
    note = ""
    if not wind.empty and wind.iloc[0] >= 15:
        note = "  <-- wind at or above the level that measurably suppresses passing and long FGs"
    return f"{t}, {w}{note}"


def _team_block(team: str, tt: pd.DataFrame) -> str:
    if team not in tt.index:
        return f"  (no efficiency rows for {team})"
    r = tt.loc[team]

    def f(key, dp=3, suffix=""):
        v = r.get(key)
        return f"{v:.{dp}f}{suffix}" if pd.notna(v) else "n/a"

    def rank(key):
        v = r.get(key)
        return f" (#{int(v)})" if pd.notna(v) else ""

    return "\n".join([
        f"  Opponent-adjusted net EPA/play : {f('net_epa_adj')}{rank('net_epa_adj_rank')}",
        f"  Offence adj EPA/play           : {f('off_epa_adj')}{rank('off_epa_adj_rank')}"
        f"   (raw {f('off_epa')}, success {f('off_sr', 3)})",
        f"  Defence adj EPA/play allowed   : {f('def_epa_adj')}{rank('def_epa_adj_rank')}"
        f"   (raw {f('def_epa')}, success allowed {f('def_sr', 3)})",
        f"  Pass / Rush offence EPA        : {f('off_pass_epa')} / {f('off_rush_epa')}",
        f"  Early-down offence EPA         : {f('off_early_epa')}",
        f"  Explosive rate made / allowed  : {f('off_explosive_rate')} / {f('def_explosive_rate')}",
        f"  Pass rate over expected (PROE) : {f('off_proe')}",
        f"  Sack rate taken / generated    : {f('off_sack_rate')} / {f('def_sack_rate')}",
        "",
        f"  SCHEDULE CHECK — avg opponent defence faced: {f('opp_def_faced')}, "
        f"offence faced: {f('opp_off_faced')}",
        f"      (a strong rating against weak opponents is the 'fake good' pattern; "
        f"the adjusted numbers above already net this out)",
        "",
        f"  VARIANCE LEDGER",
        f"    EPA-implied margin/game : {f('epa_margin_per_game', 1)}",
        f"    Actual margin/game      : {f('actual_margin_per_game', 1)}",
        f"    Luck gap                : {f('luck_margin', 1)}   {r.get('regression_flag') or ''}",
        f"    Fumble-recovery luck    : {f('fumble_luck_pts', 1, ' pts')}",
        f"    Kicking luck            : {f('fg_luck_pts', 1, ' pts')} over {int(r.get('fg_attempts') or 0)} attempts",
        f"    Penalty yards/game      : {f('penalty_yds_per_game', 1)}",
    ])


def build(game: dict, lock_game: dict, tt: pd.DataFrame, pbp: pd.DataFrame,
          sched: pd.DataFrame, inj: pd.DataFrame, snaps: pd.DataFrame,
          stats: pd.DataFrame, depth: pd.DataFrame, week: int,
          prior_snaps: pd.DataFrame | None = None, with_weather: bool = True) -> str:
    home, away = game["home_team"], game["away_team"]
    ctx = game_context(game, with_weather=with_weather)

    spread = lock_game["cbs_spread_home"]
    fav, dog = (home, away) if spread < 0 else (away, home)
    line_txt = (f"{fav} {-abs(spread):.1f} / {dog} +{abs(spread):.1f}"
                if spread != 0 else "PICK'EM")

    out: list[str] = []
    A = out.append

    A(f"# {away} @ {home} — Week {week} dossier")
    A("")
    A("## LOCKED LINE (CBS Sports, Tuesday) — USE THIS AND ONLY THIS")
    A("```")
    A(f"  {line_txt}")
    A(f"  home spread : {spread:+.1f}   ({home} {'favoured' if spread < 0 else 'underdog' if spread > 0 else 'pickem'})")
    A(f"  total       : {lock_game.get('cbs_total', 'n/a')}")
    A(f"  captured    : {lock_game.get('captured_at', 'n/a')}  from {lock_game.get('source_url', 'CBS Sports')}")
    if "_market_divergence" in lock_game:
        A(f"  cross-check : broad-market reference {lock_game['_market_reference_spread_home']:+.1f}, "
          f"divergence {lock_game['_market_divergence']:+.1f}")
    A("```")
    A("Do not substitute a live line, a different book, or a number you remember. "
      "Every model in this consensus is grading against the figure above.")
    A("")

    A("## ENVIRONMENT & SITUATION")
    A(f"- Venue: {ctx['venue']} — roof `{ctx['roof']}`, surface `{ctx['surface']}`, "
      f"altitude {ctx['altitude_ft']} ft")
    if ctx["altitude_note"]:
        A(f"  - {ctx['altitude_note']}")
    A(f"- Kickoff: {ctx['kickoff_local']}")
    A(f"- Travel: {away} covers {ctx['travel_miles']} miles, {ctx['tz_shift_hours']:+d} time zones")
    if ctx["body_clock_note"]:
        A(f"  - {ctx['body_clock_note']}")
    A(f"- Rest: {home} {ctx['home_rest_days']}d vs {away} {ctx['away_rest_days']}d — {ctx['rest_note']}")
    if ctx["roof_change_note"]:
        A(f"- {ctx['roof_change_note']}")
    if ctx["surface_change"]:
        A(f"- Surface change: {away} normally plays on `{ctx['away_home_surface']}`, "
          f"this week on `{ctx['surface']}`")
    A(f"- Weather: {ctx['weather'].get('summary')}")
    A("")

    for team, label in ((away, "AWAY"), (home, "HOME")):
        A(f"## {label} — {team}")
        A("")
        A("### Efficiency (opponent-adjusted)")
        A("```")
        A(_team_block(team, tt))
        A("```")
        A("")

        lg = last_game_forensics(pbp, sched, team)
        A("### Last game forensics")
        if not lg.get("available"):
            A(f"- {lg.get('note')}")
        else:
            A(f"- {lg['site']} vs {lg['opponent']} — final {lg['score']} (margin {lg['margin']:+.0f})")
            A(f"- EPA margin {lg['epa_margin']:+.1f} vs scoreboard {lg['margin']:+.0f} "
              f"→ gap {lg['luck_gap']:+.1f}")
            A(f"  - **{lg['luck_verdict']}**")
            A(f"- Turnovers: lost {lg['turnovers_lost']}, forced {lg['turnovers_forced']} "
              f"(diff {lg['turnover_diff']:+d})")
            A(f"- Missed field goals: {', '.join(lg['missed_fgs']) if lg['missed_fgs'] else 'none'}")
            A(f"- Penalty yards: {lg['penalty_yards']}")
            A(f"- Explosive plays (EPA>=3) made {lg['explosive_plays_made']}, "
              f"allowed {lg['explosive_plays_allowed']}")
            A(f"- Conditions: {lg['conditions']}")
        A("")

        rows = injury_report(inj, team, week)
        A("### Injury report & unit health")
        if not rows:
            A("- No official report rows available yet for this week.")
        else:
            designated = [r for r in rows if r["has_game_status"]]
            practice_only = [r for r in rows if not r["has_game_status"]]
            if designated:
                for r in designated[:10]:
                    A(f"- {r['player']} ({r['pos']}) — **{r['status']}**, {r['injury']}"
                      + (f" [practice: {r['practice']}]" if r["practice"] else ""))
            else:
                A("- No game designations (Out/Doubtful/Questionable) posted yet for this week.")
            if practice_only:
                A(f"- Practice report only, no game designation: "
                  + ", ".join(f"{r['player']} ({r['pos']}, {r['practice'] or 'n/a'})"
                              for r in practice_only[:8]))
            A("")
            A("Unit health (public-report triage, 0-100):")
            for unit, val in unit_health(rows).items():
                A(f"- `{unit:<10}` {val}")
        A("")

        st = snap_trends(snaps, team, week, prior_snaps)
        bo = breakout_candidates(st, stats, team, week)
        A("### Emerging / role changes")
        losses = personnel_losses(depth, inj, team, week)
        if losses:
            A("Durable causes (players ruled out):")
            for m in losses[:6]:
                A(f"- {m}")
            A("")
        if not bo:
            A("- No significant snap-share movement detected.")
        else:
            for b in bo:
                base = "NEW TO ROLE" if b["new_to_role"] else f"{b['snap_pct_baseline']}% → {b['snap_pct_now']}%"
                A(f"- **{b['player']}** ({b['pos']}, {b['unit']}) — {base}"
                  + (f", {b['snap_pct_delta']:+.1f} pts" if b.get("snap_pct_delta") else ""))
                A(f"  - usage: {b.get('usage')}")
                A(f"  - repeatability: {b.get('repeatability')}")
        A("")

    A("## MATCHUP NOTES TO RESOLVE")
    A("These are the questions the numbers above cannot answer on their own. "
      "Address each explicitly in your pick rationale:")
    A("")
    A(f"1. Does {away}'s pass offence attack the specific area where {home}'s coverage "
      f"is weakest (outside CB vs slot vs seam), or does the matchup cancel their strength?")
    A(f"2. Which offensive line gets the worse individual matchup, and does the locked "
      f"spread already price it?")
    A(f"3. Coaching: prior head-to-head history, and whether either coordinator has "
      f"shown a scheme answer for the other (motion rate vs man, play-action vs light boxes, "
      f"pressure without blitzing).")
    A(f"4. Pace and pass-rate-over-expected: does the projected game script let the "
      f"underdog stay in it, or does an early lead turn this into a clock-killing rout?")
    A(f"5. Is any edge identified above already the reason the line sits where it does?")
    A("")

    A("## DATA PROVENANCE")
    A("- Play-by-play, injuries, snap counts, depth charts, weekly rosters: "
      "nflverse / nflfastR open data")
    A("- Schedule, rest days, roof, surface: nflverse `games.csv`")
    A(f"- Weather: {ctx['weather'].get('source', 'n/a')} "
      f"({'retrieved' if ctx['weather'].get('available') else 'UNAVAILABLE — fill manually'})")
    A("- Spread and total: CBS Sports Tuesday line, frozen and hash-verified")
    A("")
    A("Gaps this packet does not cover (paid sources; supply manually if you have them): "
      "PFF WR/CB alignment grades and shadow-coverage usage, SIS charting (motion rate, "
      "time-to-throw, pressure without blitzing), SICScore physician health grades.")

    return "\n".join(out)
