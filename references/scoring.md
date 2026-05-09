# DeepLearning Scoring

Scoring is not qualification.

The previous stages already handled:

- user preferences
- high-signal source strategy
- fetching and source metadata
- content candidate selection

Scoring should not redo those jobs.

Scoring has two responsibilities:

1. Final Gate: veto obvious misses that slipped through earlier stages.
2. Daily Ranking: choose the best 10-item daily composition from qualified candidates.

## Step 1: Final Gate

Final Gate is a lightweight sanity check. It is not a full second content-selection pass.

Use it only to reject obvious problems:

- clearly unrelated to the user's selected or adjacent interests
- clickbait, reposting, or generic filler that slipped through
- insufficient evidence: conclusion without facts or context
- attribution problem: secondary interpretation presented as original source
- personal opinion presented as official action
- unclear claim actor or unsupported official attribution
- duplicate of a stronger candidate with no new information
- repeat story with no new angle or information gain
- risky content: paid hype, emotional investment calls, unverifiable performance claims, leaked or private details

Output:

```json
{
  "pass_final_gate": true,
  "final_reject_reason": ""
}
```

Rejected example:

```json
{
  "pass_final_gate": false,
  "final_reject_reason": "insufficient_evidence"
}
```

Recommended `final_reject_reason` values:

- `clearly_unrelated`
- `low_quality_slipped_through`
- `insufficient_evidence`
- `bad_attribution`
- `unclear_claim_actor`
- `duplicate_without_gain`
- `repeat_story_without_new_angle`
- `risky_paid_hype`
- `privacy_or_leak_risk`

## Step 2: Daily Ranking

Daily Ranking answers:

> Which qualified candidates deserve today's card slots?

It is not an absolute quality score. It is a daily prioritization and composition score.

Use four dimensions.

### daily_priority

Whether this item should be seen today.

Consider:

- represents an important change in today's context
- is timely enough to matter now
- is more urgent than other qualified candidates
- connects to current platform, market, product, or workflow movement

### information_gain

Whether this item adds something beyond similar candidates.

Consider:

- adds facts, detail, explanation, data, or angle
- is not just duplicate coverage
- is more complete than adjacent candidates
- improves understanding of the topic

### portfolio_value

Whether this item improves the final daily card composition.

Consider:

- balances the user's selected content packs
- prevents over-concentration on one source, company, platform, or event
- adds useful adjacent or cross-domain signal
- helps complete the 10-item card without lowering quality

### attention_return

Whether this item deserves one card slot.

Consider:

- user is likely to gain judgment, method, context, or action clue
- item is clear enough to be understood
- item is worth reading compared with other candidates

## Recommended Weights

Use:

```json
{
  "daily_priority": 0.35,
  "information_gain": 0.25,
  "portfolio_value": 0.25,
  "attention_return": 0.15
}
```

Reasoning:

- `daily_priority` is highest because scoring is about today's card.
- `information_gain` prevents repeated or shallow items from crowding the card.
- `portfolio_value` ensures the final 10 items are a useful set, not just a mechanical top list.
- `attention_return` protects the user's limited reading attention.

## Output Schema

```json
{
  "pass_final_gate": true,
  "final_reject_reason": "",
  "daily_priority": 86,
  "information_gain": 78,
  "portfolio_value": 82,
  "attention_return": 75,
  "final_score": 81.55,
  "ranking_reasons": [
    "represents_today_key_change",
    "adds_new_angle_vs_similar_items",
    "balances_selected_pack"
  ],
  "ranking_penalties": [
    "adjacent_interest_not_main"
  ]
}
```

Calculate:

```text
final_score =
  daily_priority * 0.35 +
  information_gain * 0.25 +
  portfolio_value * 0.25 +
  attention_return * 0.15
```

Scores use a `0-100` scale.

## After Scoring

Do not mechanically take the top 10 by raw score without review.

After scoring:

1. Group same-topic candidates.
2. Prefer primary source when it has enough information.
3. Prefer expert secondary analysis when it adds much better explanation.
4. Check story lifecycle state and keep only repeat-story items with clear new information gain.
5. Avoid letting one event, company, source, or platform occupy too many slots.
6. Select the final 10-item composition.

## Relationship to User Profile

Do not permanently change the user's profile because of scoring.

If adjacent content is included to complete a daily card, record it as `fill_reason`, not as a new user preference.

Only update the user profile when the user explicitly says something like:

- "多发这个"
- "少发这个"
- "以后关注这个方向"
- "不要再看这个来源"

## Relationship to Source Reputation

Scoring can inform source reputation, but be careful:

- High quality and relevant: may improve source quality and relevance.
- High quality but irrelevant to this user: do not punish source quality.
- Low quality: may reduce source quality after enough samples.
- Too few samples: observe only.

Keep source quality and user relevance separate.
