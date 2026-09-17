# claude-code-secrets

## nfl-ats-consensus

Multi-model NFL against-the-spread consensus pipeline. See
`nfl-ats-consensus/README.md` for how it runs and `ARCHITECTURE.md` for the
automation plan.

### Standing rules for this project

**The CBS Tuesday line is the only line.** It is entered once a week, signed with
SHA-256, and verified on every read. Never substitute a live line, another book, or
a remembered number. A pick priced off a different spread is voided, not
down-weighted. When the market drifts away from CBS during the week — it will —
that is expected and gets recorded as an acknowledgement, never as a correction to
the locked number.

**Stadium roof and surface come from `nfl-ats-consensus/config/STADIUMS.md`**, which
is authoritative for the 2026 season, not from nflverse `games.csv` and never from
memory. nflverse lags stadium changes by a season or more — in Week 2 of 2026 it
still had Buffalo on turf (Highmark is new and grass) and Tennessee on grass (Nissan
is Matrix Helix turf). `config/team_meta.json` is the machine-readable copy and must
agree with the markdown. Roof semantics: `fixed` means weather never matters,
`retractable` is a gameday decision declared ~90 minutes before kickoff, `canopy` is
SoFi only — overhead cover with open sides, so rain no but wind yes — and `open`
means weather always can matter.

**The dossier reports, it does not conclude.** No FADE/BUY labels, no "expect
regression", no "historically a real drag". State the measurement and let each model
interpret it. Shared interpretation manufactures agreement that reads like
independent confirmation.

**Models are never told how many disagree with them.** Round 2 shows deduplicated,
anonymised opposing arguments only. A lone correct read is the most valuable output
the system can produce and it is destroyed by conformity pressure.
