# AI Headlines Architecture

AI Headlines should start as a Skill-led product, with scripts as the execution layer. MCP can come later when the workflow is stable.

## Decision

Use this order:

1. Skill
2. Local scripts
3. Optional MCP later

Do not start by building a full MCP server. First validate that the product logic, onboarding, source strategy, content selection, scoring, and presentation work well.

## Why Skill First

The Skill defines product behavior:

- how onboarding works
- how users express content preferences
- how one-sentence feedback updates the radar
- how source strategy should behave
- how content selection differs from scoring
- how final briefs should be written
- how the Agent should recover from failure

These are product and judgment rules. They belong in the Skill and references.

## Why Scripts Next

Repeated execution should not rely on the Agent improvising every step.

Use scripts for deterministic work:

- reading config
- fetching sources
- deduplicating URLs and titles
- generating story IDs
- applying simple include/exclude filters
- tracking source reputation
- tracking story lifecycle
- preparing candidate payloads
- rendering HTML or platform cards
- sending messages
- saving logs and artifacts

Scripts reduce token cost, improve repeatability, and make failures easier to debug.

## Where Agent/LLM Should Be Used

Use the Agent or LLM for judgment-heavy tasks:

- interpreting natural-language onboarding responses
- updating preferences from one-sentence feedback
- judging public echoes and attribution
- checking claim actor attribution
- selecting candidates that require semantic understanding
- scoring final candidates
- writing `brief_text`
- resolving ambiguous failures and recommending fixes

Do not send every fetched item in full to the Agent. Code should narrow the candidate pool first.

## Recommended Pipeline

```text
onboard
-> resolve user profile
-> resolve source catalog
-> fetch with code
-> code prefilter
-> dedupe and story lifecycle check
-> prepare compact candidate payload
-> Agent/LLM content selection and scoring
-> canonical digest JSON
-> render platform card / HTML
-> deliver
-> save artifacts and logs
```

## Token Control

Code should reduce the problem space before any expensive model call.

Recommended approach:

1. Fetch many items.
2. Code removes obvious duplicates, excluded keywords, old items, empty items, and obvious low-value records.
3. Code builds compact payloads with title, source, URL, excerpt, source metadata, and history metadata.
4. Only send the best 30-50 candidates to the Agent/LLM.
5. Keep full text available for selected items when deeper interpretation is needed.

## Local Scheduling

The first version should be triggered by local tasks, not GitHub Actions.

Reasoning:

- this is a personal information radar
- local credentials and platform tools are easier to access locally
- users may not want to publish configs or secrets to GitHub
- local scheduling fits Agent-based personal workflows

Possible schedulers:

- Windows Task Scheduler
- macOS launchd
- Linux cron or systemd timer

The scheduled job should run a single local entrypoint once it exists, such as:

```bash
python scripts/run_ai_headlines_pipeline.py
```

The exact command may change during implementation.

## Delivery Resolution

Users choose a delivery platform as an intention. The Agent resolves how to send based on available tools.

Do not make onboarding ask for every token or webhook.

Resolution order:

1. Check available local tools, inner skills, MCP servers, or scripts.
2. Use the strongest available platform renderer.
3. Ask the user only for missing credentials or authorization.
4. If native delivery is unavailable, save the digest and provide an HTML or compact fallback.

## Failure Handling

Failures should be diagnosed by stage.

Non-critical failures should not block the whole run:

- image failure: send without image
- one source fails: continue with other sources
- rich card fails: send compact message or HTML fallback
- HTML generation fails: send native card if available
- platform delivery fails: save artifacts and explain what credential or tool is missing

Critical failures:

- no user profile
- no usable source data
- selection/scoring fails completely
- no deliverable output

For critical failures, the Agent should explain the failed stage and propose the next fix.

## When MCP Makes Sense

MCP should be considered after the workflow stabilizes.

Good MCP candidates:

- `ai_headlines_validate_config`
- `ai_headlines_fetch`
- `ai_headlines_select`
- `ai_headlines_score`
- `ai_headlines_render`
- `ai_headlines_send`
- `ai_headlines_update_preferences`
- `ai_headlines_get_last_digest`

MCP is useful when multiple Agents need reliable, reusable tools. It should not replace the Skill. The Skill remains the product behavior layer.

## Final Principle

Skill defines behavior. Scripts execute repeatable work. MCP can expose stable tools later.
