# atsc — NFL ATS multi-model consensus

A pipeline that builds one identical evidence packet per game, hands it to several
AI models, makes the models that disagree argue with each other, adjudicates the
fight, grades the week, and forces every model to explain what it got wrong.

The whole thing is built around one rule:

> **Every model prices every game off the same CBS Sports Tuesday line, and that
> line is frozen, hashed, and verified on every read.**

If the models are not using the same number, their disagreement is meaningless —
you are not comparing analysis, you are comparing arithmetic. So the line is a
signed artifact, checked three ways, and any pick made against a different number
is voided rather than down-weighted.

## The weekly cadence

| When | Command | What happens |
|---|---|---|
| **Tuesday** | `atsc lock` → `atsc verify` | CBS posts. You enter the line once. It is hashed and frozen for the week. |
| **Tuesday** | `atsc build` | Dossiers + one shared prompt pack. Send to every model. |
| **Wednesday** | `atsc battle` | Line audit, disagreement map, rebuttal packs for contested games only. |
| **Wednesday** | `atsc adjudicate` | Adjudicator prompt → the house card. |
| **Thursday AM** | `atsc build` again | Refreshed injuries/weather. **The line does not move.** TNF picks lock. |
| **Saturday/Sunday AM** | `atsc build` again | Final refresh for the Sunday slate. Line still does not move. |
| **Tuesday (next)** | `atsc grade` | Leaderboard, calibration, per-model post-mortem packs. |

Re-running `build` on Thursday and Sunday is the point: injuries, practice reports,
snap trends and weather all move. The spread never does.

## Quick start

```bash
pip install -r requirements.txt

# 1. Freeze the CBS Tuesday line
python -m atsc.cli lock --season 2026 --week 2 \
    --csv cbs_week2.csv --captured-at 2026-09-15 --locked-by you

# 2. Triple-check it before anything else sees it
python -m atsc.cli verify --season 2026 --week 2

# 3. Build the dossiers and the shared prompt pack
python -m atsc.cli build --season 2026 --week 2

# 4. Send data/dossiers/2026/week02/PROMPT_PACK.md to every model.
#    Save each reply as data/picks/2026/week02/<model>.json

# 5. Make them fight
python -m atsc.cli battle --season 2026 --week 2
python -m atsc.cli adjudicate --season 2026 --week 2

# 6. After the games
python -m atsc.cli grade --season 2026 --week 2
```

### The CBS CSV

```csv
game_id,cbs_spread_home,cbs_total,cbs_favorite
2026_02_DET_BUF,-4.5,53.5,BUF
2026_02_CAR_ATL,1.5,43.5,CAR
```

`cbs_spread_home` is **negative when the home team is favoured**. `cbs_favorite` is
optional but recommended — the structural check uses it to catch a flipped side,
which is the single easiest mistake to make when transcribing sixteen games.

Running `lock` without `--csv` seeds placeholders from the open market and marks
the file `verified: false`. `build` refuses to run on an unverified lock. That is
deliberate: a placeholder must never reach a model.

## The three checks

Run on every single read of the file, not just at lock time.

**CHECK 1 — structural.** Schema version, all 16 games present and no extras,
valid team codes, `game_id` agreeing with the named teams, half-point increments,
plausible ranges, and the favourite label agreeing with the sign of the spread.

**CHECK 2 — cross-source.** Every CBS spread is compared against an independent
market reference from nflverse. A gap ≥ 1.0 is escalated and blocks the lock; 0.5
to 1.0 is noted. This does not override CBS — it catches transposed digits and
flipped sides.

**CHECK 3 — immutability.** SHA-256 over the canonical serialisation, recomputed
on every load. Edit one digit by hand and every downstream command refuses to run
until you re-lock with a written reason. The old digest is retained in the audit
trail, so a silent edit is impossible.

The digest is printed in the prompt pack and every model echoes it back in
`lock_sha256`. Mismatch is flagged before a single pick is counted.

## What's in a dossier

Per game, from free and open data:

- **Locked line** with its provenance and cross-check delta
- **Environment** — roof, surface, altitude, travel miles, time-zone shift, body-clock
  kickoff hour, rest asymmetry, dome-team-outdoors and surface-change flags, and
  a wind reading banded by its *actual measured effect* (nothing below 8 mph
  matters; 15+ is where passing and long field goals genuinely degrade)
- **Opponent-adjusted efficiency** — iteratively adjusted EPA for offence and
  defence, plus the average opponent quality faced, so a "fake good" unit that has
  only played bad offences is visible rather than just silently corrected
- **Variance ledger** — EPA-implied margin vs actual margin, fumble-recovery luck,
  kicking luck against a distance-adjusted baseline, penalty burden, one-score
  record, with explicit FADE / BUY regression flags
- **Last-game forensics** — turnovers, missed field goals, penalty yards, explosive
  plays made and allowed, conditions, and the gap between how the game was played
  and how it finished
- **Injuries** — official report rows separated from practice-report-only noise,
  plus a 0-100 triage score per unit (QB, OL, pass-catchers, RB, secondary, front seven)
- **Emerging players** — snap-share movement against a prior baseline, with an
  explicit repeatability verdict: volume-driven roles are projectable, two
  touchdowns on four touches is not, and snaps without usage is called out as a decoy
- **Named gaps** — what the packet does *not* have (PFF alignment grades, SIS
  charting, SICScore) so no model can quietly pretend it does

Early in the season, current-year ratings are blended with the prior season on a
shrinkage weight that decays as games accumulate — one week of data is not a rating.

## The battle stage

`battle` classifies every game:

- **split** — the field genuinely disagrees. Rebuttal packs generated.
- **majority** — one holdout. Also gets a rebuttal pack.
- **unanimous** — agreement from different reasoning.
- **fragile_consensus** — agreement where every model gave substantially the *same*
  reason. This is the dangerous one: it is one argument wearing five hats, and it is
  where correlated misses come from. Flagged separately and never counted as
  five pieces of evidence.

Round 1 asks for stars and one sentence. Round 2 — only on contested games — is
where models turn on deep research to defend, concede, or flip. Flipping is
explicitly not scored as a loss of face; an unjustified hold is.

## Grading

Two numbers, because they answer different questions. **Record** is the raw ATS
result. **Score** is stars-weighted and asymmetric — a 5-star loss (−6.5) costs more
than a 5-star win (+4.5) gains, which is what discourages confidence inflation.

Calibration is reported separately, and it is the most useful output of the whole
system. A model whose 4-star picks lose while its 1-star leans win has an *inverted*
confidence signal, and that is a fixable problem the raw record completely hides.

## Data sources

All free, no API keys:

- **nflfastR / nflverse** (<https://nflfastr.com>) — play-by-play with EPA, WP, CPOE,
  air yards and success rate; injuries; snap counts; depth charts; weekly rosters;
  weekly player stats. Pulled straight from the `nflverse-data` GitHub releases, the
  same artifacts `nflreadr` and `nfl_data_py` read, cached locally.
- **nflverse `games.csv`** — schedule, rest days, roof, surface, and the independent
  market reference used by CHECK 2.
- **Open-Meteo** — kickoff-hour forecast. No key, no registration. If the network
  blocks it the dossier says `WEATHER UNAVAILABLE` rather than implying calm
  conditions; a model told "wind 0 mph" when nobody checked will make a confident
  wrong call on a total.
- **CBS Sports** — the spread and total, entered by hand on Tuesday. This is the one
  input that is deliberately manual.

Not included, because they are paid: PFF WR/CB matchup grades and shadow-coverage
usage, SIS charting (motion rate, time-to-throw, pressure without blitzing),
SICScore physician health grades. The dossier names these gaps explicitly so the
models treat them as unknowns rather than filling them in from memory.

## Repository layout

```
atsc/
  linelock.py          the three checks, signing, canonical hashing
  dossier.py           per-game evidence packet
  prompt.py            renders the identical prompt pack
  battle.py            line audit, disagreement mapping, rebuttal assignment
  grade.py             ATS grading, weighted scoring, calibration, leaderboard
  cli.py               lock / verify / build / battle / adjudicate / grade
  sources/nflverse.py  cached nflfastR data access
  features/
    team.py            opponent-adjusted EPA, variance ledger, prior blending
    context.py         rest, travel, altitude, surface, weather, unit health
    players.py         snap-share movement and repeatability
prompts/
  01_pick.md           Round 1 — short form, stars and one reason
  02_rebuttal.md       Round 2 — deep research, defend or flip
  03_adjudicate.md     the house position
  04_postmortem.md     what went wrong and the one rule change
config/team_meta.json  stadium coordinates, altitude, roof, surface, time zone
data/                  lines / dossiers / picks / results, by season and week
```
