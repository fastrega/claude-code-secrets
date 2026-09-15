"""atsc — NFL ATS multi-model consensus pipeline."""

from __future__ import annotations

import argparse
import csv
import getpass
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import battle, grade, linelock, prompt, report
from .dossier import build as build_dossier
from .sources import nflverse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


def _paths(season: int, week: int) -> dict[str, Path]:
    tag = f"{season}/week{week:02d}"
    p = {
        "lock": DATA / "lines" / tag / "cbs_line_lock.json",
        "dossiers": DATA / "dossiers" / tag,
        "picks": DATA / "picks" / tag,
        "rebuttals": DATA / "picks" / tag / "rebuttals",
        "results": DATA / "results" / tag,
    }
    for k, v in p.items():
        (v.parent if k == "lock" else v).mkdir(parents=True, exist_ok=True)
    return p


def _load_lock(season: int, week: int, strict: bool = True) -> dict:
    p = _paths(season, week)["lock"]
    sched = nflverse.week_games(season, week)
    return linelock.load(
        p,
        market=nflverse.market_reference(season, week),
        expected_game_ids=set(sched["game_id"]),
        strict=strict,
    )


# ---------------------------------------------------------------- lock

def cmd_lock(args: argparse.Namespace) -> int:
    season, week = args.season, args.week
    paths = _paths(season, week)
    sched = nflverse.week_games(season, week)
    market = nflverse.market_reference(season, week)

    if paths["lock"].exists() and not args.relock:
        print(f"A locked line already exists at {paths['lock']}")
        print("It is frozen for the week on purpose. Use --relock \"<reason>\" to replace it.")
        return 1

    previous = None
    if args.relock and paths["lock"].exists():
        previous = json.loads(paths["lock"].read_text()).get("lock", {}).get("sha256")

    games: list[dict] = []
    if args.csv:
        # Expected header: game_id,cbs_spread_home,cbs_total  (favorite optional)
        with open(args.csv, newline="") as f:
            supplied = {r["game_id"]: r for r in csv.DictReader(f)}
        blank = []
        for r in sched.itertuples():
            row = supplied.get(r.game_id)
            if row is None:
                print(f"  ! {r.game_id} missing from {args.csv}")
                continue
            if not str(row.get("cbs_spread_home", "")).strip():
                blank.append(r.game_id)
                continue
            games.append({
                "game_id": r.game_id,
                "away_team": r.away_team, "home_team": r.home_team,
                "kickoff": f"{r.gameday} {r.gametime}",
                "cbs_spread_home": float(row["cbs_spread_home"]),
                "cbs_total": float(row["cbs_total"]) if row.get("cbs_total") else None,
                "cbs_favorite": row.get("cbs_favorite") or None,
                "source_url": args.source_url,
                "captured_at": args.captured_at or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                "verified": True,
            })
        if blank:
            print(f"\nREFUSING TO LOCK: {len(blank)} row(s) have no cbs_spread_home.")
            print("Fill in every CBS number before locking — a partial lock would let "
                  "different models price different games.")
            for gid in blank:
                print(f"  - {gid}")
            return 1
    else:
        print("No --csv supplied: seeding from the open market reference.")
        print("These are PLACEHOLDERS. Replace every number with the CBS Tuesday line "
              "before distributing to any model.\n")
        for r in sched.itertuples():
            ref = market.get(r.game_id)
            games.append({
                "game_id": r.game_id,
                "away_team": r.away_team, "home_team": r.home_team,
                "kickoff": f"{r.gameday} {r.gametime}",
                "cbs_spread_home": float(ref) if ref is not None else 0.0,
                "cbs_total": float(r.total_line) if pd.notna(r.total_line) else None,
                "cbs_favorite": None,
                "source_url": "PLACEHOLDER — NOT CBS",
                "captured_at": None,
                "verified": False,
            })

    payload = {
        "schema_version": linelock.SCHEMA_VERSION,
        "season": season, "week": week,
        "line_source": "CBS Sports — Tuesday posting",
        "convention": "cbs_spread_home is negative when the HOME team is favoured",
        "all_verified": all(g["verified"] for g in games),
        "games": games,
    }
    payload = linelock.sign(
        payload,
        locked_by=args.locked_by or getpass.getuser(),
        reason=args.relock or "initial lock",
        previous=previous,
    )
    paths["lock"].write_text(json.dumps(payload, indent=2) + "\n")

    print(f"Wrote {paths['lock']}")
    print(f"  digest {payload['lock']['sha256']}\n")
    results = linelock.verify(payload, market=market, expected_game_ids=set(sched["game_id"]))
    print(linelock.format_report(results))
    if not payload["all_verified"]:
        print("\n  NOT CBS-VERIFIED. Edit the spreads, then re-run with "
              "--relock \"entered CBS Tuesday line\" to re-sign.")
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    paths = _paths(args.season, args.week)
    payload = json.loads(paths["lock"].read_text())
    sched = nflverse.week_games(args.season, args.week)
    results = linelock.verify(payload,
                              market=nflverse.market_reference(args.season, args.week),
                              expected_game_ids=set(sched["game_id"]))
    print(f"Line lock: {paths['lock']}")
    print(f"Digest:    {payload.get('lock', {}).get('sha256')}")
    print(f"CBS-verified numbers: {payload.get('all_verified')}\n")
    print(linelock.format_report(results))
    print("\n| game | CBS home spread | market ref | delta |")
    print("|---|---|---|---|")
    for g in payload["games"]:
        ref = g.get("_market_reference_spread_home")
        d = g.get("_market_divergence")
        print(f"| {g['away_team']} @ {g['home_team']} | {g['cbs_spread_home']:+.1f} | "
              f"{ref if ref is None else f'{ref:+.1f}'} | {d if d is None else f'{d:+.1f}'} |")
    return 0 if all(r.passed for r in results) else 2


# ---------------------------------------------------------------- build

# Kickoff windows, so a refresh close to a game only touches the games about to
# start. Times are the venue-local kickoff hour recorded in the schedule.
WINDOWS = {
    "thu": lambda r: str(r["weekday"]).startswith("Thu"),
    "sun_early": lambda r: str(r["weekday"]) == "Sunday" and _hour(r) < 16,
    "sun_late": lambda r: str(r["weekday"]) == "Sunday" and 16 <= _hour(r) < 19,
    "snf": lambda r: str(r["weekday"]) == "Sunday" and _hour(r) >= 19,
    "mnf": lambda r: str(r["weekday"]).startswith("Mon"),
    "all": lambda r: True,
}


def _hour(row) -> int:
    try:
        return int(str(row["gametime"]).split(":")[0])
    except Exception:
        return 13


def _select_games(sched: pd.DataFrame, window: str | None,
                  games: list[str] | None) -> set[str] | None:
    """None means the whole slate."""
    if games:
        return set(games)
    if window and window != "all":
        pred = WINDOWS[window]
        return {r["game_id"] for _, r in sched.iterrows() if pred(r)}
    return None

def cmd_build(args: argparse.Namespace) -> int:
    season, week = args.season, args.week
    paths = _paths(season, week)
    lock = _load_lock(season, week, strict=not args.allow_unverified)

    if not lock.get("all_verified") and not args.allow_unverified:
        print("REFUSING TO BUILD: the locked line is not marked CBS-verified.")
        print("Enter the CBS Tuesday numbers and re-lock, or pass --allow-unverified "
              "for a dry run you must not distribute.")
        return 1

    print(f"Loading nflverse data for {season} week {week} …")
    sched_all = nflverse.schedules()
    sched = sched_all[sched_all.season == season]
    pbp_cur = nflverse.pbp(season)
    pbp_prior = nflverse.pbp(season - 1)
    inj = nflverse.injuries(season)
    snaps = nflverse.snap_counts(season)
    prior_snaps = nflverse.snap_counts(season - 1)
    stats = nflverse.player_stats(season)
    depth = nflverse.depth_charts(season)

    from .features.team import team_table
    games_played = int(sched[sched["result"].notna()]["week"].nunique())
    print(f"  {len(pbp_cur):,} plays, {games_played} week(s) complete — "
          f"blending with {season - 1} prior")
    tt = team_table(pbp_cur, pbp_prior, sched, games_played)

    week_sched_df = nflverse.week_games(season, week)
    week_sched = week_sched_df.set_index("game_id")
    lock_games = {g["game_id"]: g for g in lock["games"]}

    selected = _select_games(week_sched_df, args.window, args.games)
    if selected is not None:
        print(f"  scoped to {len(selected)} game(s): {', '.join(sorted(selected))}")

    from .dossier import volatile_fingerprint
    snap_path = paths["dossiers"] / ".snapshot.json"
    previous = json.loads(snap_path.read_text()) if snap_path.exists() else {}
    snapshot: dict[str, str] = dict(previous)

    dossiers: dict[str, str] = {}
    changed: list[str] = []
    unchanged: list[str] = []

    for gid, lg in lock_games.items():
        if gid not in week_sched.index:
            print(f"  ! {gid} not on the schedule, skipping")
            continue
        if selected is not None and gid not in selected:
            continue
        row = week_sched.loc[gid].to_dict()
        row["game_id"] = gid
        md = build_dossier(row, lg, tt, pbp_cur, sched, inj, snaps, stats, depth,
                           week, prior_snaps=prior_snaps, with_weather=not args.no_weather)

        fp = volatile_fingerprint(md)
        if gid in previous and previous[gid] == fp:
            unchanged.append(gid)
        elif gid in previous:
            changed.append(gid)
        snapshot[gid] = fp

        dossiers[gid] = md
        (paths["dossiers"] / f"{gid}.md").write_text(md)

    snap_path.write_text(json.dumps(snapshot, indent=2))

    if previous:
        print(f"\n  Since the last build: {len(changed)} game(s) materially changed, "
              f"{len(unchanged)} unchanged")
        for gid in changed:
            print(f"    CHANGED    {gid}  (injuries, weather or snap roles moved)")
        if args.changed_only and changed:
            dossiers = {g: dossiers[g] for g in changed}
            print(f"  --changed-only: pack limited to the {len(changed)} changed game(s)")
        elif args.changed_only and not changed:
            print("  --changed-only: nothing moved, no pack written. "
                  "Re-asking would spend tokens on identical inputs.")
            return 0

    tag = args.window if args.window and args.window != "all" else None
    if args.changed_only:
        tag = f"{tag}-changed" if tag else "changed"
    name = f"PROMPT_PACK{'_' + tag if tag else ''}.md"
    pack = prompt.pick_pack(lock, dossiers)
    out = paths["dossiers"] / name
    out.write_text(pack)

    print(f"\nWrote {len(dossiers)} dossier(s) to {paths['dossiers']}")
    print(f"Prompt pack: {out}  ({len(pack):,} chars, ~{len(pack)//4:,} tokens)")
    print(f"Line digest: {lock['lock']['sha256']}  (unchanged — the line never moves)")
    print(f"\n  python -m atsc.cli poll --season {season} --week {week} --pack {name}")
    return 0


# ---------------------------------------------------------------- poll

def cmd_models(args: argparse.Namespace) -> int:
    from .adapters import openrouter

    if args.roster:
        for m in openrouter.load_roster(include_disabled=True):
            flag = " " if m.get("enabled", True) else "×"
            print(f" {flag} {m['name']:<10} {m.get('lane'):<12} "
                  f"{m.get('slug') or '(manual lane)'}")
        print("\nEdit config/models.json to change the field. "
              "× means benched (enabled: false).")
        return 0

    rows = openrouter.list_models(args.search)
    print(f"{len(rows)} model(s) reachable with your key"
          + (f" matching {args.search!r}" if args.search else "") + ":\n")
    for m in rows[:args.limit]:
        pricing = m.get("pricing", {})
        print(f"  {m.get('id'):<48} in ${pricing.get('prompt', '?')}/tok  "
              f"out ${pricing.get('completion', '?')}/tok")
    if len(rows) > args.limit:
        print(f"\n  … {len(rows) - args.limit} more. Narrow with --search.")
    return 0


def cmd_poll(args: argparse.Namespace) -> int:
    """Round 1: send the shared prompt pack to the whole field."""
    from .adapters import openrouter

    season, week = args.season, args.week
    paths = _paths(season, week)
    lock = _load_lock(season, week)

    pack_path = paths["dossiers"] / args.pack
    if not pack_path.exists():
        print(f"No prompt pack at {pack_path} — run `atsc build` first.")
        available = sorted(p.name for p in paths["dossiers"].glob("PROMPT_PACK*.md"))
        if available:
            print("Available packs: " + ", ".join(available))
        return 1
    pack = pack_path.read_text()

    # A refresh poll must not overwrite the Tuesday card — keep both, so the
    # post-mortem can ask whether the late news actually improved the pick.
    suffix = args.suffix or ("" if args.pack == "PROMPT_PACK.md"
                             else "." + args.pack.replace("PROMPT_PACK_", "")
                             .replace("PROMPT_PACK", "").removesuffix(".md").strip("._"))

    models = openrouter.load_roster(args.only)
    if not models:
        print("No models enabled. Check config/models.json.")
        return 1

    print(f"Polling {len(models)} model(s) on {season} week {week} "
          f"[{args.pack}{' → ' + suffix if suffix else ''}]")
    print(f"  pack {len(pack):,} chars (~{len(pack)//4:,} tokens), "
          f"digest {lock['lock']['sha256'][:16]}…")

    # Recompose the pack per model so each gets its own game ordering. Same
    # dossiers, same line, same instructions — only the sequence differs, which
    # keeps positional bias from landing identically on every model.
    gids = [p.stem for p in sorted(paths["dossiers"].glob("*.md"))
            if not p.stem.startswith("PROMPT_PACK")]
    packed = {g: (paths["dossiers"] / f"{g}.md").read_text() for g in gids
              if g in {x["game_id"] for x in lock["games"]}}

    if args.same_order or not packed:
        prompt_for = pack
        print("  game order: identical for every model\n")
    else:
        # Only the games actually in the requested pack.
        in_pack = {g for g in packed if f"# {g.split('_')[2]} @ {g.split('_')[3]}" in pack}
        subset = {g: packed[g] for g in (in_pack or packed)}

        def prompt_for(m: dict, _subset=subset) -> str:
            return prompt.pick_pack(lock, _subset, order_seed=m["name"])

        print(f"  game order: randomised per model over {len(subset)} game(s)\n")

    res = openrouter.fan_out(models, prompt_for, paths["picks"],
                             max_workers=args.workers, suffix=suffix)

    print(f"\n{len(res['ok'])} ok, {len(res['failed'])} failed, "
          f"{len(res['manual'])} manual")
    if res["failed"]:
        print("Failed models can be retried with --only, or pasted in by hand.")
    return 0 if res["ok"] else 1


def cmd_poll_rebuttals(args: argparse.Namespace) -> int:
    """Round 2: each model defends its position on the contested games only."""
    from .adapters import openrouter

    season, week = args.season, args.week
    paths = _paths(season, week)
    lock = _load_lock(season, week)

    packs = sorted(paths["rebuttals"].glob("*.md"))
    packs = [p for p in packs if p.name != "MANUAL_LANE.md"]
    if not packs:
        print(f"No rebuttal packs in {paths['rebuttals']} — run `atsc battle` first.")
        return 1

    roster = {m["name"]: m for m in openrouter.load_roster(args.only)}
    todo = []
    for p in packs:
        gid, model = p.stem.split("__", 1)
        if model in roster and roster[model].get("lane") == "openrouter":
            todo.append((p, gid, roster[model]))

    print(f"Round 2: {len(todo)} rebuttal(s) across "
          f"{len({g for _, g, _ in todo})} contested game(s)\n")

    ok = failed = 0
    for path, gid, model in todo:
        out = paths["rebuttals"] / f"{gid}__{model['name']}.reply.json"
        if out.exists() and not args.force:
            print(f"  skip    {model['name']:<10} {gid} (already answered)")
            continue
        try:
            parsed, meta = openrouter.ask(model, path.read_text(), max_tokens=8000)
            parsed.setdefault("game_id", gid)
            out.write_text(json.dumps(parsed, indent=2) + "\n")
            print(f"  ok      {model['name']:<10} {gid}  {parsed.get('decision', '?'):<18} "
                  f"{meta['seconds']:.1f}s")
            ok += 1
        except Exception as e:
            print(f"  FAILED  {model['name']:<10} {gid}  {type(e).__name__}: {e}")
            failed += 1

    print(f"\n{ok} answered, {failed} failed")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    """Render the weekly card into the repo as markdown."""
    season, week = args.season, args.week
    paths = _paths(season, week)
    lock = _load_lock(season, week)

    subs = battle.load_submissions(paths["picks"])
    if not subs:
        print(f"No submissions in {paths['picks']}")
        return 1
    violations, _ = battle.audit_lines(lock, subs)
    dis = battle.find_disagreements(lock, subs, violations)
    house = report.load_house(paths["results"] / "house.json")

    card = report.weekly_card(lock, subs, dis, house, violations)
    out = ROOT / "cards" / f"{season}-week{week:02d}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(card)
    print(f"Wrote {out}")

    graded = sorted(paths["results"].glob("graded__*.json"))
    if graded:
        reports = [json.loads(p.read_text()) for p in graded]
        rc = report.results_card(lock, reports, grade.leaderboard(reports))
        rout = ROOT / "cards" / f"{season}-week{week:02d}-results.md"
        rout.write_text(rc)
        print(f"Wrote {rout}")
    else:
        print("No graded reports yet — run `atsc grade` after the games for the results card.")
    return 0


# ---------------------------------------------------------------- battle

def cmd_battle(args: argparse.Namespace) -> int:
    season, week = args.season, args.week
    paths = _paths(season, week)
    lock = _load_lock(season, week)

    subs = battle.load_submissions(paths["picks"])
    if not subs:
        print(f"No submissions in {paths['picks']}")
        return 1
    print(f"Loaded {len(subs)} submissions: {', '.join(s['model'] for s in subs)}\n")

    violations, audit = battle.audit_lines(lock, subs)
    print(audit + "\n")

    dis = battle.find_disagreements(lock, subs, violations)
    print("Field split: " + ", ".join(f"{k}={v}" for k, v in dis["summary"].items()))

    for entry in dis["split"]:
        print(f"\n  CONTESTED  {entry['matchup']}  (home {entry['locked_spread_home']:+.1f})")
        for p in entry["positions"]:
            print(f"    {p['model']:<22} {p['pick']:<4} {p['stars']}★  {p['headline']}")
    for entry in dis["fragile_consensus"]:
        print(f"\n  FRAGILE CONSENSUS  {entry['matchup']} — "
              f"headline overlap {entry['headline_overlap']}")
        print(f"    {entry['warning']}")

    (paths["results"] / "disagreements.json").write_text(json.dumps(dis, indent=2))

    assignments = battle.rebuttal_assignments(lock, subs, dis, include_majority=args.include_majority)
    paths["rebuttals"].mkdir(parents=True, exist_ok=True)
    for a in assignments:
        text = prompt.rebuttal_pack(lock, a["game"], a["mine"], a["opposing"])
        fn = paths["rebuttals"] / f"{a['game_id']}__{a['model']}.md"
        fn.write_text(text)
    print(f"\nWrote {len(assignments)} rebuttal packs to {paths['rebuttals']}")
    print("Send each file to the model named in its filename. Save replies as "
          f"{paths['rebuttals']}/<game_id>__<model>.reply.json")
    return 0


def cmd_adjudicate(args: argparse.Namespace) -> int:
    season, week = args.season, args.week
    paths = _paths(season, week)
    lock = _load_lock(season, week)
    subs = battle.load_submissions(paths["picks"])
    violations, audit = battle.audit_lines(lock, subs)

    rebuttals = []
    for p in sorted(paths["rebuttals"].glob("*.reply.json")):
        rebuttals.append(json.loads(p.read_text()))

    text = prompt.adjudicate_pack(lock, subs, rebuttals, audit)
    out = paths["results"] / "ADJUDICATOR_PROMPT.md"
    out.write_text(text)
    print(f"Wrote {out} ({len(text):,} chars) — {len(subs)} cards, {len(rebuttals)} rebuttals")
    return 0


# ---------------------------------------------------------------- grade

def cmd_grade(args: argparse.Namespace) -> int:
    season, week = args.season, args.week
    paths = _paths(season, week)
    lock = _load_lock(season, week)

    sched = nflverse.week_games(season, week)
    done = sched[sched["result"].notna()]
    if done.empty:
        print("No completed games for this week yet.")
        return 1
    results = {r.game_id: (float(r.home_score), float(r.away_score)) for r in done.itertuples()}
    print(f"{len(results)} of {len(sched)} games final.\n")

    subs = battle.load_submissions(paths["picks"])
    violations, audit = battle.audit_lines(lock, subs)
    if violations:
        print(audit + "\n")
    reports = [grade.grade_submission(s, lock, results, violations) for s in subs]
    reports = [r for r in reports if r["games"]]
    if not reports:
        print("No gradeable picks.")
        return 1

    board = grade.leaderboard(reports)
    print(board + "\n")

    for r in reports:
        c = r["calibration"]
        print(f"{r['model']}: {r['record']}  score {r['score']:+.1f}  "
              f"calibration {c['verdict']} — {c['detail']}")
        (paths["results"] / f"graded__{r['model']}.json").write_text(json.dumps(r, indent=2))

        pm = prompt.postmortem_pack(lock, r["model"], r, board,
                                    grade.contrarian_games(reports, r["model"]))
        (paths["results"] / f"POSTMORTEM__{r['model']}.md").write_text(pm)

    (paths["results"] / "leaderboard.md").write_text(
        f"# {season} Week {week} — ATS leaderboard\n\n"
        f"Line digest `{lock['lock']['sha256']}`\n\n{board}\n")
    print(f"\nWrote graded reports and post-mortem packs to {paths['results']}")
    return 0


# ---------------------------------------------------------------- main

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="atsc", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--season", type=int, required=True)
        p.add_argument("--week", type=int, required=True)

    p = sub.add_parser("lock", help="freeze the CBS Tuesday line for the week")
    common(p)
    p.add_argument("--csv", help="CSV of CBS lines: game_id,cbs_spread_home,cbs_total[,cbs_favorite]")
    p.add_argument("--relock", metavar="REASON", help="replace an existing lock (audited)")
    p.add_argument("--locked-by")
    p.add_argument("--source-url", default="https://www.cbssports.com/nfl/odds/")
    p.add_argument("--captured-at", help="date you read the CBS page, YYYY-MM-DD")
    p.set_defaults(func=cmd_lock)

    p = sub.add_parser("verify", help="run the three line-integrity checks")
    common(p)
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("build", help="build dossiers and the shared prompt pack")
    common(p)
    p.add_argument("--window", choices=sorted(WINDOWS),
                   help="scope to one kickoff window: thu, sun_early, sun_late, snf, mnf")
    p.add_argument("--games", nargs="+", metavar="GAME_ID", help="scope to specific games")
    p.add_argument("--changed-only", action="store_true",
                   help="pack only games whose injuries, weather or snap roles moved "
                        "since the last build")
    p.add_argument("--no-weather", action="store_true")
    p.add_argument("--allow-unverified", action="store_true",
                   help="dry run against placeholder lines — never distribute the output")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("models", help="list the roster, or what your OpenRouter key can reach")
    p.add_argument("--roster", action="store_true", help="show config/models.json instead of querying")
    p.add_argument("--search", help="filter live model slugs, e.g. 'claude'")
    p.add_argument("--limit", type=int, default=60)
    p.set_defaults(func=cmd_models)

    p = sub.add_parser("poll", help="Round 1 — send the prompt pack to the whole field")
    common(p)
    p.add_argument("--only", nargs="+", metavar="MODEL", help="poll only these roster names")
    p.add_argument("--pack", default="PROMPT_PACK.md",
                   help="which pack to send (a windowed build writes its own)")
    p.add_argument("--suffix", help="tag the output files, e.g. '.sunday' for a refresh poll")
    p.add_argument("--same-order", action="store_true",
                   help="send every model an identical game order (default: randomised "
                        "per model so positional bias does not correlate across the field)")
    p.add_argument("--workers", type=int, default=4)
    p.set_defaults(func=cmd_poll)

    p = sub.add_parser("poll-rebuttals", help="Round 2 — models defend on contested games")
    common(p)
    p.add_argument("--only", nargs="+", metavar="MODEL")
    p.add_argument("--force", action="store_true", help="re-ask models that already answered")
    p.set_defaults(func=cmd_poll_rebuttals)

    p = sub.add_parser("report", help="render the weekly card to cards/ as markdown")
    common(p)
    p.set_defaults(func=cmd_report)

    p = sub.add_parser("battle", help="audit lines, find disagreements, write rebuttal packs")
    common(p)
    p.add_argument("--include-majority", action="store_true", default=True)
    p.set_defaults(func=cmd_battle)

    p = sub.add_parser("adjudicate", help="build the adjudicator prompt")
    common(p)
    p.set_defaults(func=cmd_adjudicate)

    p = sub.add_parser("grade", help="grade the week and write post-mortem packs")
    common(p)
    p.set_defaults(func=cmd_grade)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except linelock.LineLockError as e:
        print(f"\nLINE LOCK ERROR\n{e}\n", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
