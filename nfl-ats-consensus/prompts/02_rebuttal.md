You previously made a pick on this game. Other AI models disagreed with you.

**This is the round where you use everything you have.** Turn on deep research /
extended thinking. Go back to the source material, look up what you did not look
up the first time, and check the specific claims below. Round 1 was deliberately
terse; this round is where the reasoning has to hold up.

Your job is **not** to be agreeable and **not** to be stubborn. It is to be right.
Both caving to a weak argument and digging in against a strong one are scored as
failures. If another model saw something you missed, taking their side is the
correct move and is scored as such.

# THE GAME

- Matchup: {MATCHUP}
- **Locked CBS Tuesday line: {LINE_TEXT}** (home spread `{SPREAD_HOME:+.1f}`)
- Line lock digest: `{LOCK_SHA256}`

The line has not moved and will not move. If any argument below cites a different
number, that argument is disqualified on that point — say so.

# YOUR ORIGINAL POSITION

- Pick: **{YOUR_PICK}** at {YOUR_LINE:+.1f} — {YOUR_STARS} stars
- Your one-line reason: {YOUR_HEADLINE}
- Risk you named: {YOUR_RISK}

# THE OPPOSING CASES

{OPPOSING}

# WHAT TO DO

1. **Steelman the strongest opposing argument.** State it in one sentence, in its
   best form, before you respond to it.
2. **Check it for factual error.** Does it use the locked line? Does it cite a stat
   that contradicts the dossier? Does it lean on a small-sample result the variance
   ledger already flags as luck? Name specific errors; do not wave them away.
3. **Identify what it got right that you missed.** There is almost always something.
   Saying "nothing" is usually a sign you did not look.
4. **Decide.** Hold, adjust confidence, or flip. All three are honourable. Only an
   unreasoned decision is not.
5. **Restate the locked line** in your output to confirm you are still on it.

A flip is not a loss of face. An unjustified hold is.

# OUTPUT — JSON only

```json
{{
  "model": "<your model name>",
  "game_id": "{GAME_ID}",
  "spread_restated": "<the locked line, restated>",
  "steelman": "<strongest opposing argument, stated fairly in one sentence>",
  "errors_found_in_opposition": ["<specific factual or logical error>"],
  "points_conceded": ["<what they got right that you had missed>"],
  "decision": "hold | adjust_confidence | flip",
  "final_pick_team": "<team>",
  "final_stars": 3,
  "stars_changed_from": 4,
  "defense": "<why your final position survives the strongest attack on it>",
  "confidence_in_own_reasoning": 0.72
}}
```
