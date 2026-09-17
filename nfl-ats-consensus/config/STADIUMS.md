# NFL stadium surfaces & weather exposure — 2026

Authoritative reference for this project. **Overrides nflverse `games.csv`**, whose
`surface` and `roof` columns lag stadium changes by a season or more (it still had
Buffalo on turf and Tennessee on grass in Week 2 of 2026).

Machine-readable form lives in `config/team_meta.json`; that file and this one must
agree. 32 teams, 30 stadiums.

## How to apply (first filter)

1. **Roof** — Fixed enclosed → weather NEVER matters. Retractable → check open/closed
   (declared ~90 min before kick; the NFL may force it closed for precipitation,
   lightning, roughly under 40°F, or high wind). SoFi canopy → sometimes, because the
   sides are open. Open-air → weather always can matter.
2. **Surface** — Grass/hybrid vs turf, for speed, footing and the soft-tissue
   narrative. Pair it with that week's forecast, not with the venue's stereotype.
3. **Climate tags** — Cold/wind (BUF, GB, CLE, CHI, NE, MetLife), altitude (DEN),
   heat/humidity (MIA, JAX, TB, early-season South), Northwest rain (SEA).

## Quick groups

**Weather NEVER matters (fixed enclosed):** DET Ford Field · NO Caesars Superdome ·
LV Allegiant · MIN U.S. Bank Stadium

**Retractable (sometimes):** ARI State Farm · ATL Mercedes-Benz · DAL AT&T ·
HOU NRG · IND Lucas Oil — heat venues and Indianapolis in cold months are usually
closed.

**Canopy hybrid (sometimes):** LAR + LAC SoFi — fixed translucent canopy with
**open sides**. Not a sealed dome; wind and rain can intrude.

**Open-air (always can matter):** BAL · BUF · CAR · CHI · CIN · CLE · DEN · GB ·
JAX · KC · MIA (seat canopy only) · NE · NYG+NYJ · PHI · PIT · SF · SEA · TB ·
TEN · WAS

**Natural grass or hybrid (16 teams).** Grass: ARI, BAL, BUF, CHI, CLE, DEN, JAX,
KC, LV (indoor Bermuda), MIA, PIT, SF, TB, WAS. Hybrid: GB (SISGrass),
PHI (GrassMaster).

**Artificial turf (16 teams / 14 stadiums):** ATL, CAR, CIN, DAL, DET, HOU, IND,
LAR+LAC, MIN, NE, NO, NYG+NYJ, SEA, TEN.

## Full table

| Team(s) | Stadium | Roof | Weather | Surface | Notes |
| --- | --- | --- | --- | --- | --- |
| ARI | State Farm | Retractable | Sometimes | Bermuda grass (tray) | Desert heat; often closed |
| ATL | Mercedes-Benz | Retractable | Sometimes | FieldTurf CORE | SE humidity; often closed |
| BAL | M&T Bank | Open | Yes | Bermuda–rye grass | Mid-Atlantic cold/wind/rain |
| BUF | Highmark (new 2026) | Open | Yes | Kentucky bluegrass | Cold + lake-effect; **was turf at old stadium** |
| CAR | Bank of America | Open | Yes | FieldTurf CORE | Humid subtropical |
| CHI | Soldier Field | Open | Yes | Bermuda grass | Lake wind; late freeze |
| CIN | Paycor | Open | Yes | FieldTurf CORE | Late-season cold/wind |
| CLE | Huntington Bank | Open | Yes | Kentucky bluegrass | Lake Erie snow/wind |
| DAL | AT&T | Retractable | Sometimes | Hellas Matrix Helix | Usually closed |
| DEN | Empower Field | Open | Yes | Kentucky bluegrass | **Altitude ~5280 ft** |
| DET | Ford Field | Fixed dome | No | FieldTurf CORE | Fully indoor |
| GB | Lambeau | Open | Yes | Hybrid (bluegrass + SISGrass) | Frozen Tundra |
| HOU | NRG | Retractable | Sometimes | Hellas Matrix Helix | Usually closed (heat) |
| IND | Lucas Oil | Retractable | Sometimes | Hellas Matrix Helix | Often closed Nov–Jan |
| LAC / LAR | SoFi | Fixed canopy, open sides | Sometimes | Hellas Matrix Helix | Mild; wind/rain can intrude |
| LV | Allegiant | Fixed enclosed skylight | No | Indoor Bermuda grass | Climate-controlled |
| MIA | Hard Rock | Open (seat canopy) | Yes | Bermuda grass | Heat/humidity; field exposed |
| MIN | U.S. Bank | Fixed enclosed | No | Act Global turf | Fully indoor |
| NE | Gillette | Open | Yes | FieldTurf CORE | Nor'easter wind/snow |
| NO | Caesars Superdome | Fixed dome | No | Turf Nation S5 | Fully indoor |
| NYG / NYJ | MetLife | Open | Yes | FieldTurf CORE | Wind-tunnel reputation |
| PHI | Lincoln Financial | Open | Yes | Hybrid GrassMaster | Cold/rain late season |
| PIT | Acrisure | Open | Yes | Tahoma 31 Bermuda (2026) | Cold/wet; surface watched |
| SF | Levi's | Open | Yes | Bermuda grass | Cool evenings; wind |
| SEA | Lumen | Open | Yes | FieldTurf CORE | NW rain; damp |
| TB | Raymond James | Open | Yes | Bermuda grass | Heat; afternoon storms |
| TEN | Nissan | Open | Yes | Hellas Matrix Helix | Humid; cool late season |
| WAS | Northwest | Open | Yes | Bermuda grass | Mid-Atlantic heat→cold |

## Common outdated myths (2026)

These are exactly the errors a model reasoning from memory will make, and several
are errors nflverse itself still carries:

- BUF Highmark = turf → **false** (new stadium is grass)
- LV Allegiant = turf → **false** (indoor Bermuda)
- ATL Mercedes-Benz = fixed dome → **false** (retractable)
- GB Lambeau = turf → **false** (hybrid grass)
- NE Gillette = grass → **false** (FieldTurf)
- CHI Soldier Field = turf → **false** (grass)

## Maintenance

If a team announces a mid-season re-sod or turf reinstall (World Cup aftermath,
NFLPA surface grades), update this table **and** `config/team_meta.json` before
relying on brand or cultivar detail.

Roof open/closed for any given kickoff comes from that week's announcement, never
from this list alone. This file says what is *possible* at a venue; only the
gameday declaration says what is *actual*.
