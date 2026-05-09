# DeepLearning Source Strategy

DeepLearning should reduce the cost of finding high-quality information in an era where low-quality content is cheap to produce.

The product principle is:

> Users choose what they want to read. The system decides where to find it.

Do not expose source taxonomy to users. Users should only see content directions, excluded topics, push time, and Feishu card output.

## Content Formats

DeepLearning is text-first, but not text-only.

It may use different formats as long as they can be turned into reliable text before content selection and scoring:

- articles and blogs
- release notes and docs
- GitHub repositories and discussions
- social posts and threads
- newsletters with public archives
- podcast RSS, show notes, and transcripts
- videos with captions, transcripts, or detailed show notes
- conference talks with published notes

Do not build separate judgment logic for audio or video. Normalize them into text-based items, then apply the same source strategy, content selection, and scoring rules.

Recommended metadata:

```json
{
  "content_type": "podcast",
  "has_transcript": true,
  "speaker": "Researcher name",
  "guest": "Guest name",
  "organization": "Anthropic",
  "duration_seconds": 3600,
  "access_status": "transcript_available"
}
```

Suggested `content_type` values:

- `article`
- `release`
- `repo`
- `social`
- `newsletter`
- `podcast`
- `video`
- `transcript`
- `public_summary`
- `public_discussion`

Suggested `access_status` values:

- `full_text`
- `metadata_only`
- `summary_only`
- `transcript_available`
- `transcript_missing`
- `auth_required`
- `blocked`
- `failed`

If content cannot be reliably represented as text, keep it as metadata only or reject it before scoring.

## Source Roles

Use source roles internally for each content pack.

### Anchor

Stable, trusted, high-signal sources.

Use Anchor sources to establish baseline trust. They are usually first-party or close to first-party sources:

- official blogs
- research team blogs
- project release feeds
- serious long-running publications
- official data or documentation sources

Anchor sources should be protected. If their recent output is weak, reduce frequency before blocking them.

### Expert

High-quality people, teams, authors, or maintainers.

Expert sources are judged at the concrete source level, not the platform level:

- one X account
- one newsletter author
- one maintainer
- one research group
- one design system team

Do not say "X is low quality". Say "this specific X account is unstable for this user".

### Discovery

Noisy but useful channels for discovering new signals.

Examples:

- Hacker News
- Reddit communities
- GitHub Trending
- X search queries
- Product Hunt
- topic search results

Discovery sources are candidate pools, not trusted pools. They need stricter filtering and should not dominate the final card.

### Candidate

Sources under observation.

Use Candidate when a source looks promising but has not earned trust yet. Promote it only after enough high-quality samples.

## Per-Pack Source Mix

Do not use one global source mix for every content direction. Each pack needs its own mix because noise patterns differ.

Suggested defaults:

- `ai-agent`: anchor 55%, expert 30%, discovery 15%
- `design-experience`: anchor 50%, expert 35%, discovery 15%
- `product-business`: anchor 50%, expert 35%, discovery 15%
- `frontend-devtools`: anchor 45%, expert 30%, discovery 25%
- `open-source`: anchor 40%, expert 25%, discovery 35%
- `finance-quant`: anchor 65%, expert 25%, discovery 10%
- `research`: anchor 60%, expert 25%, discovery 15%
- `industry-trends`: anchor 50%, expert 25%, discovery 25%

These are starting points, not user-facing settings.

## Reputation Rules

Reputation must be tracked at the concrete source level:

- RSS feed
- website
- X account
- GitHub repo
- subreddit
- discovery query

Do not update reputation for an entire platform or entire content pack because of low-scoring content.

Do not use raw Top 10 hit rate as the only signal. A source can be useful even if it rarely enters the final 10, especially if its role is `discovery` or if it provides occasional but important signals.

Recommended fields for later implementation:

```json
{
  "source_id": "x:karpathy",
  "source_type": "x",
  "source_role": "expert",
  "fetch_count": 50,
  "candidate_count": 18,
  "selected_count": 4,
  "avg_final_score": 82.3,
  "reject_reasons": {
    "routine_update_without_impact": 8,
    "duplicate_without_new_information": 3
  },
  "quality_score": 0.92,
  "relevance_score": 0.75,
  "sample_count": 24,
  "protected": true
}
```

## Source Learning

Source reputation should evolve from actual content performance.

Use multiple signals:

- `fetch_count`: how many items were fetched from this source
- `candidate_count`: how many passed content selection
- `selected_count`: how many reached the final card
- `avg_final_score`: average score after final ranking
- `reject_reasons`: why items were rejected
- user feedback, when explicitly given
- source role: `anchor`, `expert`, `discovery`, or `candidate`
- sample size and recent trend

Interpret signals by source role:

- `anchor`: prioritize trust and stability. Do not auto-delete; reduce frequency first.
- `expert`: prioritize judgment density and selected-item quality.
- `discovery`: tolerate lower hit rate if it occasionally discovers strong signals.
- `candidate`: observe before promotion or removal.

Promotion signals:

- high candidate rate
- stable selected-item quality
- repeated high-quality items across time
- low rate of reject reasons such as reposting, marketing, hype, or unverifiable claims
- positive user feedback

Demotion signals:

- repeated low-quality reject reasons
- high fetch count with near-zero candidate count
- frequent duplication or reposting
- low relevance to selected or adjacent interests
- negative user feedback

Update path:

1. Reduce frequency.
2. Reduce ranking weight.
3. Move to observation.
4. Remove only after enough low-quality samples.

Do not punish a source globally when the real issue is user relevance. A strong source may be irrelevant to one user while still remaining high quality.

## Quality vs Relevance

Keep two judgments separate:

- `quality_score`: whether the content/source is good in general.
- `relevance_score`: whether it matches this user's current interests.

A good source can publish something irrelevant to one user. That should not make the source low-quality.

## Minimum Sample Rule

Do not strongly penalize a source based on too little data.

Suggested behavior:

- fewer than 5 samples: observe only
- 5 to 20 samples: adjust gently
- more than 20 samples: normal reputation adjustment

Use a recent window, such as recent 30 days or recent 50 items, so sources can recover.

## Source Renewal

The high-signal source library must be a living system. If it only demotes weak sources and never discovers new ones, it will become narrower over time.

Do not transfer source-selection work to the user. Users should not be asked to approve every new source. They only choose what they want to read; DeepLearning should handle source discovery and quality judgment in the background.

### Renewal Principle

AI may help discover, review, and observe new sources, but source trust must be earned through content performance.

New sources should not immediately become trusted. They should enter as `candidate` or `discovery`, then be promoted only after their fetched content repeatedly passes content selection and scoring.

### Where New Sources Come From

Candidate sources can be discovered from:

- sources linked or cited by high-scoring items
- authors repeatedly appearing in high-quality content
- maintainers of high-value open-source projects
- official docs, release feeds, or blogs found from trusted items
- recurring domains from Discovery results
- user one-sentence requests, such as "以后也关注这个网站"

### AI Source Review

When a new source is discovered, AI can write a short internal review:

```json
{
  "source_id": "x:some_author",
  "suggested_role": "candidate",
  "packs": ["ai-agent", "open-source"],
  "why_watch": "持续讨论 Agent 工具链，包含实践内容而非纯转述。",
  "risk": "偶尔转发较多，需要观察原创比例。",
  "recommended_action": "observe"
}
```

This review is internal. Do not show it to the user unless they ask why a source was followed.

### Promotion by Content Performance

Promote a source based on its actual content, not its appearance.

Suggested promotion path:

1. `candidate`: newly discovered or user-mentioned source.
2. `discovery`: produces occasional useful items, but quality is not stable enough.
3. `expert`: repeatedly produces high-quality, relevant items.
4. `anchor`: only for manually curated or extremely stable first-party/high-trust sources.

Promotion signals:

- multiple items pass content selection
- selected items score well after relevance and quality checks
- low rate of rejected clickbait, reposts, marketing, or unverifiable claims
- content is useful across more than one user interest or strongly useful within one selected pack

Demotion signals:

- repeated rejection for low-quality reasons
- frequent reposting without original value
- weak relevance to any selected or adjacent pack
- unstable quality after enough samples

### User Experience Rule

Users should not manage source lists during normal use.

The user-facing control remains simple:

- "多关注这个人/网站/项目"
- "少发这个来源"
- "不要再看这个方向"

DeepLearning translates those requests into source and preference updates internally.

## Public Echo Discovery

Some high-value ideas originate in paid, private, or hard-to-access sources, but later appear in public discussions, videos, podcasts, notes, or analyses.

DeepLearning may discover these public echoes, but must not claim to have read the original inaccessible content.

Use public echoes when:

- the original source is inaccessible or paywalled
- the public echo is accessible
- the echo contains detailed analysis, context, explanation, transcript, or structured summary
- attribution can clearly distinguish original content from interpretation

Reject public echoes when they are only:

- emotional reactions
- simple reposts
- one-line claims
- clickbait summaries
- audience bait for paid conversion
- claims with no evidence or context

Priority order:

1. primary source or original text
2. official summary or official transcript
3. expert secondary analysis
4. multi-source public echo
5. simple repost
6. emotional reaction

Only the first four should normally be eligible for candidate selection.

Recommended metadata:

```json
{
  "source_level": "secondary_analysis",
  "original_source": "Wall Street Journal",
  "original_access": "paywalled",
  "analysis_quality": "detailed",
  "attribution_note": "Based on public interpretation of a WSJ article, not the original full text."
}
```

## Access Boundary

DeepLearning should not bypass login, paywalls, access control, or platform restrictions.

It can use:

- public pages
- public transcripts
- public captions
- public show notes
- public summaries
- public discussions and detailed analyses
- content the user explicitly and legitimately authorizes

It must not:

- bypass paywalls
- bypass login walls
- scrape private or unauthorized content
- pretend metadata-only content was fully read
- present secondary interpretation as the original source

Paid access is an access attribute, not a quality signal.

A paid source, paid-source interpretation, or free public source must pass the same quality bar.

## Field-Specific Notes

### Finance and Quant

Finance and quant content needs higher caution because low-quality claims are common.

Prefer:

- reproducible research
- methods and frameworks
- official data
- market structure analysis
- risk, execution, and portfolio thinking

Downrank:

- unverifiable performance screenshots
- pure market calls
- stock tips
- vague alpha claims
- hype without method

Finance and quant should start with a higher Anchor ratio.

### AI and Agent

Prefer first-party product updates, research teams, tool builders, and practitioners who show real workflow changes.

Discovery can be useful, but it should not dominate because AI hype cycles are noisy.

### Design and Experience

Prefer design systems, product design teams, design engineering, interaction patterns, accessibility, and design-to-code workflows.

Visual inspiration communities should usually be Discovery, not Anchor.

### Open Source

Open source can tolerate more Discovery because new useful tools often appear outside established sources.

Still downrank:

- shallow wrapper projects
- repos with no maintenance signal
- projects with stars but weak docs or unclear use case

## Source Admission Checklist

Before adding a source to the default catalog, ask:

1. Is it close to first-party information?
2. Does it produce stable high-signal content over time?
3. Does it have judgment density: method, evidence, detail, or lived experience?
4. Is it low in marketing, reposting, and title-driven noise?
5. Does it have value across more than one user interest?

If unsure, add it as `candidate` or `discovery`, not `anchor`.
