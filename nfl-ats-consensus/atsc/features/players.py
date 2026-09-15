"""
Emerging players: who is suddenly on the field more, and what the production on
those snaps was made of.

The separation test has three legs:

ROLE       how far the snap share moved against its baseline
VOLUME     whether touches and targets followed the snaps
EFFICIENCY how the production was distributed — volume, scores, or one long play

These three are reported separately and left uncombined. Whether a given
combination is projectable, already priced, or noise is exactly the judgment the
analyst is being paid to make, so the dossier does not make it for them.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

SKILL = {"QB", "RB", "FB", "WR", "TE"}


def snap_trends(snaps: pd.DataFrame, team: str, week: int,
                baseline: pd.DataFrame | None = None) -> pd.DataFrame:
    """Snap-share movement for one team's latest game vs. its recent baseline."""
    if snaps is None or snaps.empty:
        return pd.DataFrame()

    t = snaps[snaps["team"] == team].copy()
    if t.empty:
        return pd.DataFrame()

    cur = t[t["week"] == week]
    if cur.empty:
        week = int(t["week"].max())
        cur = t[t["week"] == week]

    prior = t[t["week"] < week]
    if prior.empty and baseline is not None and not baseline.empty:
        prior = baseline[baseline["team"] == team]

    def pct(df: pd.DataFrame, col: str) -> pd.Series:
        return df.groupby("player")[col].mean()

    rows = []
    for col, tag in (("offense_pct", "OFF"), ("defense_pct", "DEF")):
        if col not in cur.columns:
            continue
        now = pct(cur, col).dropna()
        was = pct(prior, col) if len(prior) else pd.Series(dtype=float)
        pos = cur.drop_duplicates("player").set_index("player")["position"]
        for player, share in now.items():
            before = float(was.get(player, np.nan)) if len(was) else np.nan
            rows.append({
                "player": player,
                "pos": pos.get(player, "?"),
                "unit": tag,
                "snap_pct_now": round(float(share) * 100, 1) if share <= 1 else round(float(share), 1),
                "snap_pct_baseline": (round(before * 100, 1) if before <= 1 else round(before, 1))
                                     if pd.notna(before) else None,
            })

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["snap_pct_delta"] = df.apply(
        lambda r: None if r["snap_pct_baseline"] is None
        else round(r["snap_pct_now"] - r["snap_pct_baseline"], 1), axis=1)
    return df.sort_values("snap_pct_now", ascending=False)


def breakout_candidates(snaps_df: pd.DataFrame, stats: pd.DataFrame, team: str,
                        week: int, min_delta: float = 12.0) -> list[dict]:
    """
    Players whose snap share moved materially, annotated with what the production
    behind the new role was made of.
    """
    if snaps_df is None or snaps_df.empty:
        return []

    # `week` is the week being previewed, which has not been played. Production
    # must be read from the most recent COMPLETED week or every skill player looks
    # like he was on the field and never touched the ball.
    if stats is not None and not stats.empty and "week" in stats.columns:
        week = min(week, int(stats["week"].max()))

    movers = snaps_df[
        (snaps_df["snap_pct_delta"].notna() & (snaps_df["snap_pct_delta"] >= min_delta))
        | (snaps_df["snap_pct_baseline"].isna() & (snaps_df["snap_pct_now"] >= 45))
    ]

    out = []
    for r in movers.itertuples():
        # A None written into a float column comes back out of itertuples as NaN,
        # so `is None` silently fails here. Test for missingness, not identity.
        base = r.snap_pct_baseline
        delta = r.snap_pct_delta
        has_base = base is not None and pd.notna(base)
        entry = {
            "player": r.player,
            "pos": r.pos,
            "unit": r.unit,
            "snap_pct_now": r.snap_pct_now,
            "snap_pct_baseline": float(base) if has_base else None,
            "snap_pct_delta": float(delta) if (delta is not None and pd.notna(delta)) else None,
            "new_to_role": not has_base,
        }
        entry.update(_production_profile(stats, r.player, team, week, r.unit, r.pos))
        out.append(entry)

    # A measured jump is worth more than "we have no baseline for this player", so
    # rank quantified movers first and let new faces fill the remaining slots.
    out.sort(key=lambda x: (x["new_to_role"], -(x.get("snap_pct_delta") or x["snap_pct_now"])))
    return out[:12]


DEFENSIVE = {"DE", "DT", "DL", "NT", "EDGE", "LB", "ILB", "OLB", "MLB",
             "CB", "S", "FS", "SS", "DB"}
TRENCH = {"T", "LT", "RT", "G", "LG", "RG", "C", "OL", "OT", "OG"}


def _production_profile(stats: pd.DataFrame, player: str, team: str, week: int,
                        unit: str = "OFF", pos: str = "?") -> dict:
    """Usage and the shape of that usage, for the latest completed week."""
    p = str(pos).upper()

    # Box-score stats only describe skill players. For everyone else the snap
    # share IS the finding, and pretending otherwise produces noise.
    if p in TRENCH:
        return {"usage": "offensive line — snap share is the usage measure",
                "usage_shape": "OL snap share; cross-reference the injury list for the cause"}
    if p in DEFENSIVE or unit == "DEF":
        return {"usage": f"defensive snap-share change ({p}); public box score does not cover defence at this level",
                "usage_shape": "cross-reference the injury list and depth chart for the cause"}

    if stats is None or stats.empty:
        return {"usage": "no weekly stat file", "usage_shape": "unknown"}

    name_col = "player_display_name" if "player_display_name" in stats.columns else "player_name"
    s = stats[(stats[name_col] == player)]
    if s.empty:
        return {"usage": "no stat rows under this name", "usage_shape": "unknown"}

    cur = s[s["week"] == week]
    if cur.empty:
        return {"usage": "on the field, no touches or targets recorded",
                "usage_shape": "snap share without usage"}
    row = cur.iloc[0]

    def num(c):
        v = row.get(c)
        return float(v) if pd.notna(v) else 0.0

    tgts, rec, ryds, rtd = num("targets"), num("receptions"), num("receiving_yards"), num("receiving_tds")
    car, rush, rtds = num("carries"), num("rushing_yards"), num("rushing_tds")

    bits = []
    if tgts:
        bits.append(f"{int(rec)}/{int(tgts)} for {int(ryds)} yds, {int(rtd)} TD")
    if car:
        bits.append(f"{int(car)} carries for {int(rush)} yds, {int(rtds)} TD")
    usage = "; ".join(bits) or "no touches"

    # Reported as structure, not as a verdict. What a TD-heavy line on four touches
    # means for this week's spread is the analyst's call, not the dossier's.
    flags = []
    tds = rtd + rtds
    touches = tgts + car
    ypt = (ryds + rush) / touches if touches else 0.0

    if touches >= 8:
        flags.append(f"{int(touches)} touches — production came from volume")
    if tds >= 2 and touches <= 6:
        flags.append(f"{int(tds)} TDs on {int(touches)} touches — production concentrated in scores")
    if ypt >= 14 and touches <= 5:
        flags.append(f"{ypt:.1f} yards per touch on {int(touches)} touches — "
                     f"check whether one play carries the line")
    if tgts >= 8:
        flags.append(f"{int(tgts)} targets")
    if not flags:
        flags.append("no distinctive usage pattern")

    return {"usage": usage, "yards_per_touch": round(ypt, 1), "usage_shape": "; ".join(flags)}


def personnel_losses(depth: pd.DataFrame, injuries: pd.DataFrame, team: str, week: int) -> list[str]:
    """Starters listed out — the durable cause behind most genuine role changes."""
    if injuries is None or injuries.empty:
        return []
    out_players = injuries[
        (injuries["team"] == team)
        & (injuries["week"] <= week)
        & (injuries["report_status"].isin(["Out", "Doubtful", "Injured Reserve"]))
    ]
    if out_players.empty:
        return []

    starters: set[str] = set()
    if depth is not None and not depth.empty:
        col = "depth_team" if "depth_team" in depth.columns else None
        d = depth[depth["team"] == team]
        if col:
            d = d[d[col].astype(str) == "1"]
        namecol = "full_name" if "full_name" in d.columns else "player_name"
        starters = set(d[namecol].dropna())

    msgs = []
    for r in out_players.drop_duplicates("full_name").itertuples():
        tag = "STARTER" if r.full_name in starters else "rotational"
        msgs.append(f"{r.full_name} ({r.position}, {tag}) — {r.report_status}"
                    + (f", {r.report_primary_injury}" if pd.notna(r.report_primary_injury) else ""))
    return msgs[:10]
