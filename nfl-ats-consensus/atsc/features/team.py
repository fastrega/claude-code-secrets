"""
Team efficiency and variance features from nflfastR play-by-play.

Two jobs:

EFFICIENCY  — opponent-adjusted EPA/success-rate splits. This is the open-source
              stand-in for DVOA: rate every play, then subtract out how good the
              opponent has been against everyone else. It is what exposes the
              "fake good" defence that has only played bad offences.

VARIANCE    — the results that sat outside the standard deviation. Fumble-recovery
              luck, kicking luck, one-score-game record, and above all the gap
              between a team's EPA-implied margin and the margin on the scoreboard.
              A team that won by 14 while losing the EPA battle is a fade candidate;
              a team that lost by 3 while winning EPA by 10 is next week's value.

Early in a season there is not enough current-year data to adjust against, so
everything is blended with the prior season using a shrinkage weight that decays
as real games accumulate.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Plays that describe a real offensive snap.
_SCRIMMAGE = "(pass == 1 or rush == 1) and play_type in ('pass','run') and season_type == season_type"

# Weight on the prior season, by number of current-season games played.
# 1 game in, the prior still carries most of the signal; by week 6 it is noise.
PRIOR_WEIGHT = {0: 1.00, 1: 0.72, 2: 0.55, 3: 0.42, 4: 0.32, 5: 0.24, 6: 0.18, 7: 0.13}
PRIOR_FLOOR = 0.08

# League-average FG make rate by distance bucket (long-run, stable).
FG_BASELINE = {(0, 29): 0.975, (30, 39): 0.935, (40, 49): 0.845, (50, 59): 0.665, (60, 99): 0.375}


def _prior_weight(games_played: int) -> float:
    return PRIOR_WEIGHT.get(games_played, PRIOR_FLOOR)


def _scrimmage(pbp: pd.DataFrame) -> pd.DataFrame:
    df = pbp[(pbp["play_type"].isin(["pass", "run"]))
             & pbp["posteam"].notna()
             & pbp["epa"].notna()].copy()
    df["explosive"] = ((df["pass"] == 1) & (df["yards_gained"] >= 20)) | \
                      ((df["rush"] == 1) & (df["yards_gained"] >= 12))
    df["early_down"] = df["down"].isin([1, 2])
    return df


def raw_splits(pbp: pd.DataFrame) -> pd.DataFrame:
    """Per-team offensive and defensive rates, unadjusted."""
    df = _scrimmage(pbp)

    def side(group_col: str, tag: str) -> pd.DataFrame:
        g = df.groupby(group_col)
        out = pd.DataFrame({
            f"{tag}_epa": g["epa"].mean(),
            f"{tag}_sr": g["success"].mean(),
            f"{tag}_pass_epa": g.apply(lambda x: x.loc[x["pass"] == 1, "epa"].mean(), include_groups=False),
            f"{tag}_rush_epa": g.apply(lambda x: x.loc[x["rush"] == 1, "epa"].mean(), include_groups=False),
            f"{tag}_early_epa": g.apply(lambda x: x.loc[x["early_down"], "epa"].mean(), include_groups=False),
            f"{tag}_explosive_rate": g["explosive"].mean(),
            f"{tag}_plays": g.size(),
        })
        out.index.name = "team"
        return out

    off = side("posteam", "off")
    de = side("defteam", "def")

    # Pass-rate over expectation: the tell for how a coach actually calls games.
    pr = df[df["xpass"].notna()].groupby("posteam").apply(
        lambda x: (x["pass"] - x["xpass"]).mean(), include_groups=False)
    off["off_proe"] = pr

    # Pressure proxies available in public pbp.
    dropbacks = pbp[(pbp["qb_dropback"] == 1) & pbp["posteam"].notna()]
    off["off_sack_rate"] = dropbacks.groupby("posteam")["sack"].mean()
    de["def_sack_rate"] = dropbacks.groupby("defteam")["sack"].mean()

    out = off.join(de, how="outer")
    out["net_epa"] = out["off_epa"] - out["def_epa"]
    return out


def opponent_adjust(pbp: pd.DataFrame, iterations: int = 6) -> pd.DataFrame:
    """
    Iterative opponent adjustment. Each team's offensive rating is its raw EPA
    minus the average defensive rating it has faced, and vice versa; repeat until
    it settles. This is the mechanism that makes DVOA useful and raw EPA
    misleading in September.
    """
    df = _scrimmage(pbp)
    teams = sorted(set(df["posteam"]) | set(df["defteam"]))
    off = pd.Series(0.0, index=teams)
    de = pd.Series(0.0, index=teams)
    league = df["epa"].mean()

    for _ in range(iterations):
        df["_adj"] = df["epa"] - df["defteam"].map(de).fillna(0.0)
        off = df.groupby("posteam")["_adj"].mean() - league
        df["_adj"] = df["epa"] - df["posteam"].map(off).fillna(0.0)
        de = df.groupby("defteam")["_adj"].mean() - league

    out = pd.DataFrame({"off_epa_adj": off, "def_epa_adj": de})
    out.index.name = "team"
    out["net_epa_adj"] = out["off_epa_adj"] - out["def_epa_adj"]

    # Strength of schedule faced, so "fake good" is visible, not just corrected.
    sos_off = df.groupby("posteam")["defteam"].apply(lambda s: de.reindex(s).mean())
    sos_def = df.groupby("defteam")["posteam"].apply(lambda s: off.reindex(s).mean())
    out["opp_def_faced"] = sos_off
    out["opp_off_faced"] = sos_def
    return out


def variance_ledger(pbp: pd.DataFrame, sched: pd.DataFrame) -> pd.DataFrame:
    """
    Per-team accounting of results that will not repeat.

    epa_margin_per_game   EPA-implied scoring margin
    actual_margin         what the scoreboard said
    luck_margin           actual minus implied. Large positive = due for regression.
    fumble_luck           recoveries above/below the 50% baseline, in expected points
    fg_luck               makes above/below distance-adjusted expectation
    one_score_record      W-L in games decided by <= 8
    """
    played = sched[sched["result"].notna()].copy()
    df = _scrimmage(pbp)

    # EPA margin per game, per team.
    off = df.groupby(["game_id", "posteam"])["epa"].sum().rename("off_epa_sum")
    de = df.groupby(["game_id", "defteam"])["epa"].sum().rename("def_epa_sum")
    g = pd.concat([off, de], axis=1).fillna(0.0)
    g.index.names = ["game_id", "team"]
    g["epa_margin"] = g["off_epa_sum"] - g["def_epa_sum"]

    rows = []
    for gid, gm in played.set_index("game_id").iterrows():
        margin = float(gm["home_score"] - gm["away_score"])
        for team, actual in ((gm["home_team"], margin), (gm["away_team"], -margin)):
            try:
                implied = float(g.loc[(gid, team), "epa_margin"])
            except KeyError:
                continue
            rows.append({
                "team": team, "game_id": gid,
                "epa_margin": implied, "actual_margin": actual,
                "luck": actual - implied,
                "one_score": abs(margin) <= 8,
                "won": actual > 0,
            })
    gl = pd.DataFrame(rows)
    if gl.empty:
        return pd.DataFrame()

    agg = gl.groupby("team").agg(
        games=("game_id", "count"),
        epa_margin_per_game=("epa_margin", "mean"),
        actual_margin_per_game=("actual_margin", "mean"),
        luck_margin=("luck", "mean"),
        one_score_games=("one_score", "sum"),
        one_score_wins=("won", lambda s: int((s & gl.loc[s.index, "one_score"]).sum())),
    )

    # Fumble luck: recoveries are close to a coin flip, so anything away from
    # 50% is noise that will not carry into next week.
    fum = pbp[pbp["fumble"] == 1]
    if len(fum):
        forced = fum.groupby("posteam").size().rename("off_fumbles")
        lost = fum.groupby("posteam")["fumble_lost"].sum().rename("off_fumbles_lost")
        f = pd.concat([forced, lost], axis=1).fillna(0)
        # ~ -4 expected points per turnover swing
        agg["fumble_luck_pts"] = ((f["off_fumbles"] * 0.5) - f["off_fumbles_lost"]) * 4.0
    else:
        agg["fumble_luck_pts"] = 0.0

    # Kicking luck against a distance-adjusted baseline.
    fgs = pbp[pbp["field_goal_result"].notna() & pbp["kick_distance"].notna()].copy()
    if len(fgs):
        def expected(d: float) -> float:
            for (lo, hi), p in FG_BASELINE.items():
                if lo <= d <= hi:
                    return p
            return 0.5
        fgs["exp_make"] = fgs["kick_distance"].map(expected)
        fgs["made"] = (fgs["field_goal_result"] == "made").astype(float)
        k = fgs.groupby("posteam").agg(att=("made", "size"), made=("made", "sum"), exp=("exp_make", "sum"))
        agg["fg_luck_pts"] = ((k["made"] - k["exp"]) * 3.0).reindex(agg.index).fillna(0.0)
        agg["fg_attempts"] = k["att"].reindex(agg.index).fillna(0).astype(int)
    else:
        agg["fg_luck_pts"] = 0.0
        agg["fg_attempts"] = 0

    # Penalty burden.
    pen = pbp[(pbp["penalty"] == 1) & pbp["penalty_team"].notna()]
    if len(pen):
        agg["penalty_yds_per_game"] = (
            pen.groupby("penalty_team")["penalty_yards"].sum().reindex(agg.index).fillna(0) / agg["games"]
        )
    else:
        agg["penalty_yds_per_game"] = 0.0

    # Stated as measurement, not advice. Whether a luck gap is a fade, a buy, or
    # already priced in is the analyst's call — the dossier's job is to report the
    # size of the gap and how unusual it is, then get out of the way.
    sd = agg["luck_margin"].std(ddof=0) or 1.0
    agg["luck_margin_z"] = (agg["luck_margin"] / sd).round(2)
    agg["luck_note"] = np.where(
        agg["luck_margin"].abs() > 7,
        "scoreboard and play diverged by more than a touchdown",
        "",
    )
    return agg.reset_index()


def blend_prior(current: pd.DataFrame, prior: pd.DataFrame, games_played: int,
                cols: list[str]) -> pd.DataFrame:
    """Shrink a thin current-season sample toward last year's rating."""
    w = _prior_weight(games_played)
    out = current.copy()
    for c in cols:
        if c in prior.columns:
            p = prior[c].reindex(out.index)
            out[c] = (1 - w) * out[c].astype(float) + w * p.astype(float).fillna(out[c].astype(float))
    out["_prior_weight"] = w
    return out


def team_table(pbp_cur: pd.DataFrame, pbp_prior: pd.DataFrame, sched: pd.DataFrame,
               games_played: int) -> pd.DataFrame:
    """The single per-team feature table every dossier is built from."""
    raw = raw_splits(pbp_cur)
    adj = opponent_adjust(pbp_cur)
    cur = raw.join(adj, how="outer")

    prior = raw_splits(pbp_prior).join(opponent_adjust(pbp_prior), how="outer")
    blend_cols = ["off_epa", "def_epa", "off_sr", "def_sr", "off_pass_epa", "off_rush_epa",
                  "off_early_epa", "def_early_epa", "off_explosive_rate", "def_explosive_rate",
                  "off_epa_adj", "def_epa_adj", "net_epa_adj", "off_proe",
                  "off_sack_rate", "def_sack_rate"]
    blended = blend_prior(cur, prior, games_played, blend_cols)

    var = variance_ledger(pbp_cur, sched)
    if not var.empty:
        blended = blended.join(var.set_index("team"), how="left")

    # Rank everything so a model reading the dossier sees position, not just value.
    for c in ["off_epa_adj", "net_epa_adj"]:
        if c in blended:
            blended[f"{c}_rank"] = blended[c].rank(ascending=False).astype("Int64")
    if "def_epa_adj" in blended:
        blended["def_epa_adj_rank"] = blended["def_epa_adj"].rank(ascending=True).astype("Int64")

    return blended
