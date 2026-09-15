Your pick on this game was contested. The opposing reasoning is below.

**This is the round where you use everything you have.** Turn on deep research /
extended thinking. Go back to the source material, look up what you did not look
up the first time, and check the specific claims below. Round 1 was deliberately
terse; this round is where the reasoning has to hold up.

Your job is **not** to be agreeable and **not** to be stubborn. It is to be right.
Both caving to a weak argument and digging in against a strong one are scored as
failures. If an opposing case saw something you missed, taking that side is the
correct move and is scored as such.

## What you are deliberately not being told

**You do not know how many models disagree with you, and you will not be told.**

The cases below are the *distinct arguments* on the other side, deduplicated. If
four models made the same point, you see that point once — because it is one
argument, not four. The cases are labelled "Case A", "Case B" and so on, with no
model identities.

This is intentional, and it cuts both ways:

- **You may be the only model on your side.** If so, nothing here will tell you,
  and you should not try to infer it. A lone correct read is the single most
  valuable output this exercise can produce, and it is destroyed by a model that
  folds because it feels outnumbered.
- **You may be in a comfortable majority.** That is not evidence either. Models
  fail in correlated ways — same training, same priors, same blind spots. Agreement
  is cheap; a mechanism nobody else identified is not.

So do not ask yourself "am I outnumbered?" You cannot know, and it is not a
reason. Ask only: **does the argument in front of me defeat mine?**

Change your mind for a reason you can state in one sentence. Never for a count.

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
  "reason_for_decision": "<one sentence — the specific argument or fact that moved you, or that failed to>",
  "final_pick_team": "<team>",
  "final_stars": 3,
  "stars_changed_from": 4,
  "defense": "<why your final position survives the strongest attack on it>",
  "confidence_in_own_reasoning": 0.72,
  "new_research": "<what you looked up this round that you had not in Round 1, or null>"
}}
```

`reason_for_decision` is graded. "The opposing case was more persuasive overall" is
not a reason — name the fact or the inference. If you cannot, you are moving on
feel, and holding is the better call.
