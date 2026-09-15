"""
nflverse / nflfastR data access — free, open, no API key.

Everything here is pulled from the nflverse-data GitHub releases, which are the
same artifacts the R package `nflreadr` and the Python package `nfl_data_py`
read. We hit them directly so the pipeline has no heavy dependency and caches
on local disk (release assets are rebuilt nightly in season).
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pandas as pd

RELEASES = "https://github.com/nflverse/nflverse-data/releases/download"
NFLDATA = "https://raw.githubusercontent.com/nflverse/nfldata/master/data"

CACHE = Path(os.environ.get("ATSC_CACHE", Path.home() / ".cache" / "atsc"))
CACHE.mkdir(parents=True, exist_ok=True)

# In-season assets change nightly; the schedule changes constantly (injuries,
# flexed games). Keep TTLs short enough to stay current, long enough to iterate.
TTL_SECONDS = {"schedules": 3600, "default": 6 * 3600}


def _cached(name: str, url: str, kind: str = "default") -> Path:
    dest = CACHE / name
    ttl = TTL_SECONDS.get(kind, TTL_SECONDS["default"])
    if dest.exists() and (time.time() - dest.stat().st_mtime) < ttl:
        return dest
    import urllib.request

    tmp = dest.with_suffix(dest.suffix + ".tmp")
    with urllib.request.urlopen(url, timeout=180) as r, open(tmp, "wb") as f:
        f.write(r.read())
    tmp.replace(dest)
    return dest


def _parquet(name: str, url: str, kind: str = "default") -> pd.DataFrame:
    return pd.read_parquet(_cached(name, url, kind))


def schedules() -> pd.DataFrame:
    """Full historical + current schedule with results, rest days, roof, surface.

    Carries a `spread_line` column (home-favoured is POSITIVE in nflverse's
    convention). We flip it to the sportsbook convention used everywhere else in
    this project: negative means the home team is laying points.
    """
    df = pd.read_csv(_cached("games.csv", f"{NFLDATA}/games.csv", "schedules"), low_memory=False)
    df["market_spread_home"] = -df["spread_line"]
    return df


def pbp(season: int) -> pd.DataFrame:
    return _parquet(f"pbp_{season}.parquet", f"{RELEASES}/pbp/play_by_play_{season}.parquet")


def injuries(season: int) -> pd.DataFrame:
    return _parquet(f"injuries_{season}.parquet", f"{RELEASES}/injuries/injuries_{season}.parquet")


def snap_counts(season: int) -> pd.DataFrame:
    return _parquet(f"snaps_{season}.parquet", f"{RELEASES}/snap_counts/snap_counts_{season}.parquet")


def depth_charts(season: int) -> pd.DataFrame:
    return _parquet(f"depth_{season}.parquet", f"{RELEASES}/depth_charts/depth_charts_{season}.parquet")


def rosters(season: int) -> pd.DataFrame:
    return _parquet(f"rosters_{season}.parquet", f"{RELEASES}/weekly_rosters/roster_weekly_{season}.parquet")


def player_stats(season: int) -> pd.DataFrame:
    # nflverse renamed this release: player_stats/ -> stats_player/stats_player_week_
    return _parquet(f"pstats_{season}.parquet",
                    f"{RELEASES}/stats_player/stats_player_week_{season}.parquet")


def week_games(season: int, week: int) -> pd.DataFrame:
    s = schedules()
    return s[(s.season == season) & (s.week == week)].copy().reset_index(drop=True)


def market_reference(season: int, week: int) -> dict[str, float]:
    """game_id -> independent market spread (negative = home favoured).

    This is CHECK 2's cross-reference. It never overrides the CBS number.
    """
    w = week_games(season, week)
    return {
        r.game_id: float(r.market_spread_home)
        for r in w.itertuples()
        if pd.notna(r.market_spread_home)
    }
