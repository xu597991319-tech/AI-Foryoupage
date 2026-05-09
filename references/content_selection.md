# DeepLearning Content Selection

Content selection is an internal backend rule. It is not card copy, user-facing terminology, or scoring.

The purpose of content selection is to decide whether a fetched item deserves to enter the candidate pool.

Selection answers:

> Is this item worth considering?

Scoring answers later:

> Which selected candidates should be pushed today?

Keep these two steps separate.

## Core Principle

DeepLearning does not chase every new item. It selects content that either shows an important change or gives useful understanding.

Freshness and depth are internal selection signals. Do not expose them to users as labels.

## Candidate Entry Rules

An item can enter the candidate pool if it matches at least one of these paths.

### Important Change

The item reflects a recent change that may matter to a user's work, judgment, or attention.

Examples:

- new product capability
- new API or platform change
- new tool or open-source project with a clear use case
- new workflow pattern
- ecosystem or market structure change
- official update from a high-signal source

Being new is not enough. The item must show a plausible impact, use case, or changed condition.

### Useful Understanding

The item helps the user understand something better, even if it is not breaking news.

Examples:

- method
- postmortem
- case study
- engineering detail
- design/product judgment
- research result
- market or workflow analysis
- practical framework

Length is not the rule. A short primary signal can be valuable, and a long post can still be empty.

### Workflow or Boundary Shift

The item suggests that a workflow, capability boundary, or decision context is changing.

Examples:

- AI changes how a team designs, ships, tests, researches, sells, or analyzes.
- A tool lowers the cost of a previously difficult task.
- A project makes a new workflow easier to try.
- A financial or market signal changes what a user should watch.

### High-Signal Original Source

The item comes from a trusted source and represents a primary or near-primary signal.

Examples:

- official release notes
- research team notes
- maintainer explanation
- important repo release
- expert's direct observation
- official data or documentation update

This path should still reject routine updates with no clear implication.

### High-Quality Public Echo

The original content may be inaccessible, paywalled, or hard to fetch, but a public video, podcast, transcript, article, thread, or discussion gives a detailed explanation of the original idea.

This can enter the candidate pool only when it provides real information or analysis, such as:

- core facts from the original content
- context or background
- structured explanation
- professional analysis
- cross-source verification
- detailed transcript or show notes

It must preserve attribution. If the item is based on public interpretation of an inaccessible original, do not claim that the original full text was read.

## Claim Actor Attribution

Before selecting or summarizing an item, identify who actually made the claim or performed the action.

Distinguish:

- company official action
- official team blog or product update
- employee or researcher personal opinion
- author blog or interview
- third-party analysis
- community interpretation
- public echo of an inaccessible source

Never turn an individual's opinion, employee blog, third-party analysis, or community interpretation into a company's official decision.

Risky examples:

- "Anthropic deprecated Markdown" when the source is a Claude Code team member's personal article.
- "OpenAI announced..." when the source is an employee interview or third-party interpretation.
- "Google abandoned..." when the source is a community discussion.

Use safer attribution:

- "Claude Code team member Thariq Shihipar argued..."
- "A public interpretation of a WSJ article said..."
- "The author believes..."
- "The official blog announced..."

Recommended metadata:

```json
{
  "claim_actor": "individual_author",
  "claim_actor_name": "Thariq Shihipar",
  "organization": "Anthropic / Claude Code",
  "claim_type": "personal_recommendation",
  "official_status": "not_official"
}
```

## Rejection Rules

Reject items before scoring when they are clearly low-value.

Reject:

- clickbait
- generic AI quick news
- second-hand reposts with no added information
- predictions without evidence
- funding or valuation news without product, industry, or workflow change
- pure emotion without facts
- performance screenshots without method
- stock tips or unverifiable market calls
- routine version bumps with no clear impact
- duplicated coverage with no new information
- shallow wrappers or projects with no clear use case
- marketing content without concrete detail
- paid or paywall-adjacent content that relies on anxiety, hype, membership conversion, or unverifiable claims
- public echoes that are only emotional reactions, simple reposts, or vague summaries
- content whose main claim actor cannot be attributed clearly

These should not enter the candidate pool and should not rely on scoring to be removed.

## Paid and Paywall-Adjacent Content

Paid access is not a quality signal.

Do not select content because it is paid, exclusive, private, or hard to access. Select it only when the accessible content contains quality.

Paid-source interpretations and free content must pass the same bar:

- facts
- context
- analysis chain
- verifiable information
- judgment density
- useful understanding

Reject paid or paywall-adjacent content when it relies on:

- anxiety
- hype
- "inside information" framing
- unverifiable performance claims
- membership or course conversion
- screenshots without method
- strong conclusions without reasoning
- macro narratives with low information density

This is especially important in finance, investing, AI side hustles, startup growth, and paid communities.

## Source Level Priority

When the same underlying topic appears through different source levels, prefer the highest-quality level available:

1. `primary_source`: original article, official announcement, official report, author original.
2. `official_summary`: official abstract, show notes, transcript, or release summary.
3. `expert_secondary_analysis`: detailed analysis by a credible expert.
4. `multi_source_public_echo`: multiple public sources converging on the same point.
5. `simple_repost`: simple forwarding or title-level summary.
6. `emotional_reaction`: emotion, stance, hype, or commentary without facts.

The first four may enter the candidate pool if they pass selection rules.

`simple_repost` should usually be rejected unless it points to a better source.

`emotional_reaction` should be rejected.

## Ten-Item Delivery Target

DeepLearning should normally try to deliver 10 items.

Do not fill the card with low-quality content. Instead, use an ordered fallback strategy:

1. Main interests: candidates from the user's selected packs.
2. Adjacent interests: related packs that naturally connect to the selected packs.
3. High-signal general content: important cross-domain signals from strong sources.
4. Discovery expansion: carefully filtered discovery sources.

If quality is still weak, reduce explanation density rather than lowering the quality bar.

The goal is:

> Keep the daily card useful and complete without polluting it with filler.

## Fill Reasons

When a candidate is included outside the user's main selected packs, record why.

Suggested `fill_reason` values:

- `main_interest`
- `adjacent_interest`
- `high_signal_general`
- `discovery_expansion`

Do not treat fill content as a permanent user preference change. User profile changes only when the user explicitly asks.

## Story Lifecycle and Repeat Control

Do not treat duplicate control as simple URL deduplication. A technology, product launch, market event, or public debate can have a lifecycle.

A story may appear over several days:

- official release
- early user testing
- implementation details
- limitations or risks
- ecosystem integration
- expert analysis
- public echo or market reaction

The original release should normally be pushed once. Later items about the same story can enter the candidate pool only if they add meaningful information.

Allow repeat-story candidates only when they provide at least one new angle:

- `new_evidence`: new facts, data, or documentation
- `new_use_case`: new usage scenario
- `new_limitation`: limitation, risk, failure case, or caveat
- `new_implementation_detail`: architecture, deployment, cost, security, or workflow detail
- `new_ecosystem_impact`: integration, adoption, or platform impact
- `new_expert_analysis`: high-quality expert interpretation
- `new_public_echo_consensus`: multiple public sources converge on a new interpretation

Reject repeat stories when they only show continuing popularity, reposting, or repeated summaries.

Recommended metadata:

```json
{
  "story_id": "openai-new-tech-2026-05",
  "is_repeat_story": true,
  "has_information_gain": true,
  "new_angle": "deployment_limitations",
  "previous_angles": ["official_release"]
}
```

Use a cooldown window for repeated stories. Within the cooldown window, require stronger information gain before allowing the story back into the candidate pool.

Suggested defaults:

- default cooldown: 2-3 days
- allow repeat inside cooldown only for strong new evidence, limitation, implementation detail, or official update

## Candidate Metadata

Each fetched item should receive selection metadata before scoring:

```json
{
  "candidate": true,
  "selection_reason": ["important_change", "workflow_shift"],
  "fill_reason": "main_interest",
  "reject_reason": ""
}
```

Rejected example:

```json
{
  "candidate": false,
  "selection_reason": [],
  "fill_reason": "",
  "reject_reason": "generic_repost_without_new_information"
}
```

## Recommended Selection Reasons

Use short, stable reason tokens:

- `important_change`
- `useful_understanding`
- `workflow_shift`
- `capability_boundary_shift`
- `high_signal_original_source`
- `high_quality_public_echo`
- `method_or_framework`
- `case_study`
- `engineering_detail`
- `design_or_product_judgment`
- `market_or_quant_signal`
- `open_source_with_clear_use_case`

## Recommended Reject Reasons

Use short, stable reject tokens:

- `clickbait`
- `generic_quick_news`
- `second_hand_repost`
- `prediction_without_evidence`
- `funding_without_substance`
- `emotion_without_facts`
- `performance_claim_without_method`
- `stock_tip_or_unverifiable_call`
- `routine_update_without_impact`
- `duplicate_without_new_information`
- `shallow_wrapper_project`
- `marketing_without_detail`
- `paid_hype_or_anxiety`
- `public_echo_without_analysis`
- `secondary_interpretation_without_attribution`

## Adjacent Interest Examples

Use adjacent interests only to complete the daily card, not to rewrite the user's profile.

Examples:

- If selected pack is `design-experience`, adjacent packs can include `ai-agent`, `frontend-devtools`, and `open-source`.
- If selected pack is `finance-quant`, adjacent packs can include `research`, `industry-trends`, and `ai-agent`.
- If selected pack is `product-business`, adjacent packs can include `industry-trends`, `ai-agent`, and `design-experience`.
- If selected pack is `open-source`, adjacent packs can include `frontend-devtools`, `ai-agent`, and `research`.

## Relationship to Source Strategy

Source strategy decides where items come from.

Content selection decides whether fetched items deserve candidate status.

Scoring decides final priority.

Keep all three separate:

1. Source strategy: where to look.
2. Content selection: what deserves consideration.
3. Scoring: what gets pushed today.
