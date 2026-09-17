"""
CBS Tuesday line lock — the single source of truth for every model in the consensus.

Design contract
---------------
1. The CBS Sports Tuesday line is entered ONCE per week and frozen.
2. The frozen file is canonicalised (sorted keys, fixed float format) and hashed
   with SHA-256. That digest travels with every prompt handed to every model.
3. Nothing downstream may fetch, infer, or "refresh" a spread. Any module that
   needs a number reads it from the locked artifact.
4. Re-locking requires an explicit --relock with a written reason, and the old
   digest is retained in the audit trail. Silent edits are impossible to hide.

Triple check
------------
CHECK 1  STRUCTURAL   schema, completeness vs. schedule, sign/half-point sanity
CHECK 2  CROSS-SOURCE every spread compared to the independent nflverse market
                      line; divergence > tolerance is escalated, not ignored
CHECK 3  IMMUTABILITY digest recomputed and matched against the manifest on
                      every single read, for the life of the week
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"

# A CBS spread that differs from the broad market by more than this is almost
# certainly a transcription error (transposed digit, wrong side, stale week).
DIVERGENCE_ESCALATE = 1.0
DIVERGENCE_NOTE = 0.5

VALID_TEAMS = {
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE", "DAL", "DEN", "DET",
    "GB", "HOU", "IND", "JAX", "KC", "LA", "LAC", "LV", "MIA", "MIN", "NE", "NO",
    "NYG", "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS",
}

GAME_ID_RE = re.compile(r"^\d{4}_\d{2}_[A-Z]{2,3}_[A-Z]{2,3}$")


class LineLockError(RuntimeError):
    """Raised whenever the locked line cannot be trusted. Never swallow this."""


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str
    escalations: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic serialisation. Same input -> same bytes -> same digest."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _strip_derived(obj: Any) -> Any:
    """
    Remove the lock block and every derived annotation before hashing.

    Verification itself writes notes back onto the payload (the market reference,
    the divergence). Those are computed, not authored, so they must not move the
    digest — otherwise merely checking the file would invalidate it.
    """
    if isinstance(obj, dict):
        return {k: _strip_derived(v) for k, v in obj.items()
                if not k.startswith("_") and k != "lock"}
    if isinstance(obj, list):
        return [_strip_derived(v) for v in obj]
    return obj


def digest_of(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_json(_strip_derived(payload)).encode("utf-8")).hexdigest()


def _half_point_ok(value: float) -> bool:
    """Spreads and totals move in half points. 3.25 is a typo, not a line."""
    return abs(value * 2 - round(value * 2)) < 1e-9


# --------------------------------------------------------------------------
# CHECK 1 — structural
# --------------------------------------------------------------------------

def check_structural(payload: dict[str, Any], expected_game_ids: set[str] | None) -> CheckResult:
    esc: list[str] = []
    notes: list[str] = []

    if payload.get("schema_version") != SCHEMA_VERSION:
        esc.append(f"schema_version is {payload.get('schema_version')!r}, expected {SCHEMA_VERSION!r}")

    games = payload.get("games") or []
    if not games:
        esc.append("no games in lock file")

    seen: set[str] = set()
    for g in games:
        gid = g.get("game_id", "<missing>")
        where = f"[{gid}]"

        if not GAME_ID_RE.match(str(gid)):
            esc.append(f"{where} malformed game_id")
        if gid in seen:
            esc.append(f"{where} duplicate game_id")
        seen.add(gid)

        for side in ("home_team", "away_team"):
            if g.get(side) not in VALID_TEAMS:
                esc.append(f"{where} {side}={g.get(side)!r} is not a valid team code")
        if g.get("home_team") == g.get("away_team"):
            esc.append(f"{where} home and away are the same team")

        # game_id encodes AWAY_HOME; it must agree with the named teams.
        parts = str(gid).split("_")
        if len(parts) == 4:
            if parts[2] != g.get("away_team") or parts[3] != g.get("home_team"):
                esc.append(
                    f"{where} game_id says {parts[2]}@{parts[3]} but fields say "
                    f"{g.get('away_team')}@{g.get('home_team')} — sides may be flipped"
                )

        spread = g.get("cbs_spread_home")
        if not isinstance(spread, (int, float)):
            esc.append(f"{where} cbs_spread_home missing or non-numeric")
        else:
            if not _half_point_ok(float(spread)):
                esc.append(f"{where} cbs_spread_home={spread} is not a half-point increment")
            if abs(float(spread)) > 27:
                esc.append(f"{where} cbs_spread_home={spread} is outside any plausible NFL range")
            if float(spread) == 0:
                notes.append(f"{where} pick'em (0) — confirm CBS shows PK and not a blank cell")

        total = g.get("cbs_total")
        if total is not None:
            if not isinstance(total, (int, float)):
                esc.append(f"{where} cbs_total non-numeric")
            elif not _half_point_ok(float(total)) or not (28 <= float(total) <= 65):
                esc.append(f"{where} cbs_total={total} implausible or not a half-point")

        # Favourite label must agree with the sign of the home spread.
        fav = g.get("cbs_favorite")
        if fav and isinstance(spread, (int, float)) and float(spread) != 0:
            implied = g["home_team"] if float(spread) < 0 else g["away_team"]
            if fav != implied:
                esc.append(
                    f"{where} cbs_favorite={fav} contradicts cbs_spread_home={spread} "
                    f"(sign implies {implied} is favoured)"
                )

    if expected_game_ids is not None:
        missing = expected_game_ids - seen
        extra = seen - expected_game_ids
        if missing:
            esc.append(f"missing {len(missing)} scheduled game(s): {sorted(missing)}")
        if extra:
            esc.append(f"{len(extra)} game(s) not on the schedule: {sorted(extra)}")

    return CheckResult(
        name="CHECK 1 structural",
        passed=not esc,
        detail=f"{len(games)} games inspected",
        escalations=esc,
        notes=notes,
    )


# --------------------------------------------------------------------------
# CHECK 2 — cross-source divergence
# --------------------------------------------------------------------------

def check_cross_source(payload: dict[str, Any], market: dict[str, float]) -> CheckResult:
    """
    `market` maps game_id -> independent spread, expressed the same way CBS shows
    it (negative = home favoured). We are NOT overriding CBS with it. We are using
    it to catch transcription errors: a real CBS line never sits 2 points off the
    entire market.
    """
    esc: list[str] = []
    notes: list[str] = []
    compared = 0

    # A divergence a human has looked at and confirmed is no longer an alarm. It
    # stays visible as a note, with the reason, so the audit trail records that
    # somebody checked rather than that the check was switched off.
    acknowledged: dict[str, str] = payload.get("acknowledged_divergences") or {}

    for g in payload.get("games", []):
        gid = g.get("game_id")
        cbs = g.get("cbs_spread_home")
        ref = market.get(gid)
        if ref is None or not isinstance(cbs, (int, float)):
            notes.append(f"[{gid}] no independent reference available — manual eyeball required")
            continue

        compared += 1
        delta = float(cbs) - float(ref)
        g["_market_reference_spread_home"] = float(ref)
        g["_market_divergence"] = round(delta, 2)

        if abs(delta) >= DIVERGENCE_ESCALATE:
            direction = "flipped side" if cbs * ref < 0 else "large gap"
            msg = (f"[{gid}] CBS home spread {cbs:+.1f} vs market {ref:+.1f} "
                   f"(delta {delta:+.1f}, {direction})")
            if gid in acknowledged:
                g["_divergence_acknowledged"] = acknowledged[gid]
                notes.append(f"{msg} — ACKNOWLEDGED: {acknowledged[gid]}")
            else:
                esc.append(f"{msg} — re-read the CBS page before locking, or record "
                           f"an acknowledgement if the market has simply moved since Tuesday")
        elif abs(delta) >= DIVERGENCE_NOTE:
            notes.append(f"[{gid}] CBS {cbs:+.1f} vs market {ref:+.1f} (delta {delta:+.1f}) — plausible, worth a glance")

    return CheckResult(
        name="CHECK 2 cross-source",
        passed=not esc,
        detail=f"{compared} spreads compared against independent market reference",
        escalations=esc,
        notes=notes,
    )


# --------------------------------------------------------------------------
# CHECK 3 — immutability
# --------------------------------------------------------------------------

def check_immutability(payload: dict[str, Any]) -> CheckResult:
    lock = payload.get("lock")
    if not lock:
        return CheckResult("CHECK 3 immutability", False, "file carries no lock block",
                           escalations=["unsigned line file — refuse to use"])

    recorded = lock.get("sha256")
    actual = digest_of(payload)
    if recorded != actual:
        return CheckResult(
            "CHECK 3 immutability", False, "digest mismatch",
            escalations=[
                "THE LOCKED LINE FILE HAS BEEN MODIFIED SINCE IT WAS SIGNED.",
                f"  signed:   {recorded}",
                f"  computed: {actual}",
                "Every model in this week's consensus must use identical numbers. "
                "Re-lock deliberately with --relock and a reason, or restore the file from git.",
            ],
        )
    return CheckResult("CHECK 3 immutability", True, f"digest verified {actual[:16]}…")


# --------------------------------------------------------------------------
# public API
# --------------------------------------------------------------------------

def verify(payload: dict[str, Any], *, market: dict[str, float] | None = None,
           expected_game_ids: set[str] | None = None) -> list[CheckResult]:
    return [
        check_structural(payload, expected_game_ids),
        check_cross_source(payload, market or {}),
        check_immutability(payload),
    ]


def sign(payload: dict[str, Any], *, locked_by: str, reason: str = "initial lock",
         previous: str | None = None) -> dict[str, Any]:
    payload = dict(payload)
    payload.pop("lock", None)
    payload["lock"] = {
        "sha256": digest_of(payload),
        "locked_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "locked_by": locked_by,
        "reason": reason,
        "supersedes_sha256": previous,
    }
    return payload


def load(path: str | Path, *, market: dict[str, float] | None = None,
         expected_game_ids: set[str] | None = None, strict: bool = True) -> dict[str, Any]:
    """
    Load the week's locked line and run all three checks. In strict mode (the
    default, and what every pick-generating command uses) any failed check is
    fatal: it is better to produce no picks than to produce picks off a line the
    other models are not using.
    """
    path = Path(path)
    if not path.exists():
        raise LineLockError(f"no locked line at {path} — run `atsc lock` first")

    payload = json.loads(path.read_text())
    results = verify(payload, market=market, expected_game_ids=expected_game_ids)

    failed = [r for r in results if not r.passed]
    if failed and strict:
        lines = [f"line lock verification FAILED for {path}", ""]
        for r in results:
            lines.append(f"  {'PASS' if r.passed else 'FAIL'}  {r.name}: {r.detail}")
            lines.extend(f"        ! {e}" for e in r.escalations)
        raise LineLockError("\n".join(lines))

    payload["_verification"] = [
        {"name": r.name, "passed": r.passed, "detail": r.detail,
         "escalations": r.escalations, "notes": r.notes}
        for r in results
    ]
    return payload


def format_report(results: list[CheckResult]) -> str:
    out = []
    for r in results:
        out.append(f"{'  PASS' if r.passed else '  FAIL'}  {r.name}  —  {r.detail}")
        out.extend(f"          ESCALATE: {e}" for e in r.escalations)
        out.extend(f"          note:     {n}" for n in r.notes)
    verdict = "ALL CHECKS PASSED — line is safe to distribute to every model" \
        if all(r.passed for r in results) else "LINE IS NOT SAFE TO USE — resolve escalations above"
    out += ["", f"  {verdict}"]
    return "\n".join(out)
