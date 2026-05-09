---
name: deeplearning
description: Onboard a user into a personal high-signal information radar, learn what content they want to follow, remember push timing, and send curated updates as Feishu/Lark interactive cards. Use when the user mentions DeepLearning, personal news radar, daily briefing, Feishu card push, AI news, content preferences, onboarding, or changing what the radar should follow.
author: 徐尚
---

# DeepLearning

DeepLearning 是一个个人高信号信息雷达 Skill。它让用户用自然语言告诉 Agent 想看什么、在哪收、什么时候收；Agent 负责记住偏好、发现高质量信息、筛选内容，并用合适的平台形态推送。

## Core Behavior

When triggered, first determine the user's state:

- If `assets/user_profile.json`, `assets/push_schedule.json`, or delivery preference is missing, incomplete, or obviously empty, run onboarding before any news pipeline.
- If onboarding is complete, use the saved preferences and schedule. Do not ask setup questions again unless the user wants to change preferences.
- If the user says anything like "多发...", "少发...", "不要...", "加上...", "改成每天...", treat it as a one-sentence preference update.
- Default delivery should use the strongest native format available for the selected platform. Feishu/Lark should use interactive cards when possible; weak platforms should receive a compact message plus HTML digest fallback.

For the full onboarding script and exact wording, read `references/onboarding.md`.
For source selection strategy, read `references/source_strategy.md`.
For content candidate selection rules, read `references/content_selection.md`.
For scoring and daily ranking rules, read `references/scoring.md`.
For output presentation rules, read `references/presentation.md`.
For architecture and execution strategy, read `references/architecture.md`.

## Onboarding Flow

Only ask three things during first setup:

1. Content preferences: what the user wants to follow.
2. Delivery platform: where the user wants to receive it.
3. Push time: when the user wants to receive updates.

### Step 1: Content Preferences

Ask:

```text
你想长期关注什么？
可以选择推荐方向，也可以直接用一句话描述。
```

Show these recommended directions:

1. AI 与 Agent
2. 产品与商业
3. 设计与体验
4. 前端与开发工具
5. 高价值开源项目
6. 金融与量化
7. 学术与研究
8. 行业趋势

The user may answer with numbers, free text, or both. Parse the response into:

- `selected_packs`
- `include_keywords`
- `exclude_keywords`

After the user chooses, always confirm their radar profile and explicitly tell them they can change it later with one sentence. This is required because it gives the user ownership over the content.

### Step 2: Delivery Platform

Ask where the user wants to receive updates:

1. Feishu / Lark
2. WeCom
3. DingTalk
4. Slack
5. Discord
6. Telegram
7. Email

Store this as delivery intent, not a complete technical integration. The Agent should resolve the actual delivery method from the current environment, local tools, inner skills, scripts, MCP servers, or available credentials. Do not force users to configure webhooks or tokens during onboarding.

### Step 3: Push Time

Ask the user to choose one push time:

1. `09:00` morning
2. `12:00` noon
3. `18:00` evening
4. custom `HH:mm`

Use the user's local timezone when available. If timezone detection fails, use `Asia/Shanghai`. Store the result in `assets/push_schedule.json`.

## Saved Files

- `assets/content_packs.json`: recommended content directions and matching keywords.
- `assets/user_profile.example.json`: example profile schema.
- `assets/push_schedule.example.json`: example schedule schema.
- `assets/delivery.example.json`: example delivery intent schema.
- `assets/user_profile.json`: generated per user after onboarding.
- `assets/push_schedule.json`: generated per user after onboarding.
- `assets/delivery.json`: generated per user after onboarding or delivery resolution.

Do not overwrite a real user profile unless the user asks to update preferences.

## Source Strategy

Users choose what they want to read; DeepLearning decides where to find it.

Do not expose source engineering terms to the user during onboarding. Internally, each content pack maintains its own source mix:

- `anchor`: stable, trusted, high-signal sources.
- `expert`: high-quality people, teams, authors, or maintainers.
- `discovery`: noisy but useful places to discover new signals.
- `candidate`: sources under observation before becoming trusted.

Important rules:

- Do not punish an entire platform or content pack because some items scored low.
- Reputation updates should apply to the concrete source, such as one RSS feed, one X account, one GitHub repo, or one discovery query.
- Source learning should not rely only on Top 10 hit rate; consider source role, sample size, candidate rate, final score, reject reasons, and user feedback.
- Platform-level weights may be light risk hints only; they must not decide elimination.
- Anchor sources are protected: they may be reduced in frequency, but should not be automatically blocked.
- Separate content quality from user relevance. A strong source can publish content that is irrelevant to one user without becoming a bad source.
- DeepLearning is text-first but not text-only. It may use podcasts, videos, transcripts, show notes, public summaries, and public discussions when they can be converted into reliable text.
- Do not bypass login or paywalls. If original content is inaccessible, use only public high-quality echoes such as detailed analysis, transcripts, interviews, or discussions, and keep attribution clear.
- Paid access is not a quality signal. Paid or paywall-adjacent content must pass the same quality bar as free content.
- The source library should renew itself. New sources enter as `candidate` or `discovery` and earn trust through actual content performance.

## Content Selection

Content selection is a backend candidate-pool rule, not a user-facing presentation rule.

After fetching, decide whether each item deserves to enter the candidate pool before scoring. Selection answers: "Is this worth considering?" Scoring later answers: "Which candidates should be pushed today?"

Candidate content should satisfy at least one of these:

- It reflects an important recent change.
- It gives useful understanding, method, evidence, or judgment.
- It changes a workflow, ability boundary, product pattern, toolchain, market signal, or decision context.
- It comes from a high-signal source and represents an original signal.

Do not select low-quality filler just to fill a card. DeepLearning should normally try to deliver 10 items by expanding from the user's main interests to adjacent interests and then to high-signal general content.

Always verify the claim actor before generating the final brief. Do not turn an individual's opinion, employee blog, third-party analysis, or community interpretation into a company's official decision.

Repeat stories should only re-enter the candidate pool when they add a clear new angle, such as new evidence, use case, limitation, implementation detail, ecosystem impact, or expert analysis.

Selection should keep debug reasons:

- `candidate`
- `selection_reason`
- `fill_reason`
- `reject_reason`

For the detailed rules, read `references/content_selection.md`.

## Scoring

Scoring is not qualification. It is final gating and daily ranking.

After content selection, scoring should:

1. Keep veto power for obvious misses with a lightweight final gate.
2. Rank qualified candidates into the best daily card composition.

Daily ranking should consider:

- `daily_priority`: whether this item should be seen today.
- `information_gain`: whether it adds something beyond similar candidates.
- `portfolio_value`: whether it improves the balance of the final 10 items.
- `attention_return`: whether it deserves one card slot.

For the detailed rules, read `references/scoring.md`.

## Presentation

The final output should be easy to scan and worth reading, without clickbait or marketing tone.

Each item should render as:

```text
1. 【Tag】brief_text

Source · 查看原文
[optional image]
```

Rules:

- Use the user's preferred language, not necessarily the source language.
- Use one concise `brief_text`, not separate title/subtitle/summary layers.
- `brief_text` should help the user quickly understand and digest the content.
- Keep `brief_text` concise but complete: Chinese target 120-220 characters, hard max 260; English target 70-130 words, hard max 160.
- Keep one lightweight tag and source attribution.
- Sort by the final scoring/ranking order.
- Do not add recurring feedback prompts at the bottom; users can talk to the Agent directly.
- Use rich native cards when the platform supports them. If not, send a compact notification with an HTML digest fallback.
- Do not expose scoring fields, source roles, selection reasons, or other backend metadata in the final card.

For full rules, read `references/presentation.md`.

## One-Sentence Preference Updates

Users can modify the radar naturally. Do not force them into fixed feedback flows.

Examples:

- "多发 Figma 和设计系统"
- "少发 GitHub 小项目"
- "加上金融与量化"
- "不要再推融资新闻"
- "每天只看 5 条"
- "改成每天晚上 6 点发"

When this happens, update only the relevant part of the profile, schedule, delivery preference, source preference, or exclusion rule. Confirm the change briefly.

## Execution

DeepLearning is currently Skill-led, with local scripts as the execution layer. MCP may come later when the workflow is stable.

Execution principles:

- Skill defines product behavior and judgment rules.
- Scripts handle repeatable work: fetching, deduplication, prefiltering, source reputation, story lifecycle, rendering, delivery, logs.
- Agent/LLM handles judgment-heavy work: natural-language preference updates, public echo judgment, claim actor attribution, content selection, scoring, and `brief_text`.
- Code should shrink the candidate pool before Agent/LLM calls to control token cost.
- First version should be triggered by local tasks, not GitHub Actions by default.

References:

- Current pipeline commands and legacy rules: `references/execution_pipeline.md`
- AI digest prompt: `references/ai_digest_prompt.md`
- Onboarding script: `references/onboarding.md`
- Source strategy: `references/source_strategy.md`
- Content selection: `references/content_selection.md`
- Scoring: `references/scoring.md`
- Presentation: `references/presentation.md`
- Architecture: `references/architecture.md`

## Failure Handling

The Agent should diagnose failures by stage and recover when possible.

Non-critical failures should degrade gracefully:

- image failure: send without image
- one source fails: continue with other sources
- rich card fails: send compact message or HTML fallback
- HTML generation fails: send native card if available
- platform delivery fails: save artifacts and explain what credential or tool is missing

Critical failures should be explained with the failed stage and next fix:

- missing user profile
- no usable source data
- content selection/scoring fails completely
- no deliverable output
