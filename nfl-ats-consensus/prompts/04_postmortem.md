The games are final. Here is how you actually did.

This is not a formality. The point of the post-mortem is to find the *systematic*
error in your reasoning, so that next week is better. "Variance" is a true
explanation and a useless one — use it only where the evidence supports it, and
never for more than a couple of losses.

# YOUR RESULTS — {SEASON} Week {WEEK}

- Record against the spread: **{RECORD}** ({WIN_PCT})
- Weighted by stars: {WEIGHTED_RECORD}
- Line lock digest: `{LOCK_SHA256}` (all grading used these spreads)

{RESULTS_TABLE}

# THE FIELD

{FIELD_COMPARISON}

# GAMES WHERE YOU WERE ALONE

You went against the other models here. These are the most informative games you
have, in both directions.

{CONTRARIAN_GAMES}

# QUESTIONS TO ANSWER

1. **Your 4- and 5-star picks.** Highest confidence is where a systematic bias shows
   up most clearly. For each loss at 4+ stars: was the reasoning wrong, or was the
   reasoning right and the result unlucky? Justify the distinction with what actually
   happened in the game, not with assertion.
2. **Your stated risks.** For each loss, check whether the `key_risk` you named is
   what actually beat you. If it was, your analysis was sound and your sizing was
   wrong — a different problem with a different fix. If something you never
   considered beat you, name the blind spot.
3. **Calibration.** Compare your hit rate at each star level to what the rating
   implies. If your 4-stars went 1-3 and your 2-stars went 5-2, your confidence
   signal is inverted and that is the single most valuable thing you learned.
4. **Rebuttal round.** Where you flipped, did flipping help? Where you held, did
   holding help? Are you too easily moved, or too rigid?
5. **Factor audit.** Across all your losses, which factor category misled you most —
   efficiency, variance, injuries, environment, coaching, emerging players, market?
   One category usually dominates.
6. **The concrete change.** State one specific, checkable adjustment for next week.
   "Be more careful" is not an answer. "Stop upgrading teams off a single-game EPA
   margin when the variance ledger flags a luck gap above 7 points" is an answer.

# OUTPUT — JSON only

```json
{{
  "model": "<your model name>",
  "season": {SEASON},
  "week": {WEEK},
  "record_ats": "{RECORD}",
  "self_assessment": {{
    "sound_reasoning_bad_luck": ["<game_id>"],
    "flawed_reasoning": ["<game_id>"],
    "right_for_wrong_reasons": ["<game_id>"]
  }},
  "risk_audit": [
    {{"game_id": "", "named_risk": "", "what_actually_happened": "",
      "risk_materialised": true, "lesson": "analysis_ok_sizing_wrong | blind_spot"}}
  ],
  "calibration": {{
    "by_stars": {{"5": "0-1", "4": "1-2", "3": "4-2", "2": "3-1", "1": "2-2"}},
    "verdict": "well_calibrated | overconfident | underconfident | inverted",
    "evidence": ""
  }},
  "rebuttal_round_value": "<did arguing with the other models improve or worsen your card?>",
  "dominant_factor_error": "efficiency | variance | injuries | environment | rest_travel | coaching | emerging_players | market",
  "blind_spots": ["<specific, not generic>"],
  "concrete_adjustment_next_week": "<one checkable rule change>",
  "disagreement_with_grading": "<null, or a specific objection>"
}}
```
