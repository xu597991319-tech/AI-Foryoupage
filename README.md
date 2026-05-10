# AI Headlines

An Agent Skill that turns noisy feeds into personalized high-signal headlines, with onboarding, source learning, content selection, daily ranking, and rich card delivery.

AI Headlines is not a hosted news app. It is a Skill that teaches an Agent how to build and operate a personal information radar.

## What It Does

- Onboards users by asking what they care about, where they want to receive updates, and when they want them.
- Builds a high-signal source strategy behind the scenes.
- Selects useful content instead of chasing every new item.
- Ranks candidates into a daily briefing.
- Writes concise `brief_text` in the user's preferred language.
- Delivers through rich native cards when possible, with HTML fallback when needed.
- Lets users update preferences with natural language.

## How It Works

```text
onboarding
-> source strategy
-> fetch and prefilter
-> candidates.json
-> decisions.json
-> content selection
-> scoring and daily ranking
-> canonical digest
-> platform rendering
-> delivery
```

## Prototype Pipeline

The current prototype uses a two-stage local runner:

```bash
# Install dependencies first
python -m pip install -r requirements.txt

# Optional: create a local editable source catalog
cp assets/sources_catalog.example.json assets/sources_catalog.json

# 1. Fetch and export compact candidates
python scripts/run_ai_headlines_pipeline.py prepare --dry-run

# 2. Let your Agent read output/candidates.json and write output/decisions.json

# 3. Apply decisions, finalize, render, and optionally send
python scripts/run_ai_headlines_pipeline.py finish --dry-run --skip-send
```

You can also run:

```bash
python scripts/run_ai_headlines_pipeline.py all --dry-run --skip-send
```

If `output/decisions.json` does not exist, `all` stops after generating `output/candidates.json`.

## Repository Structure

```text
SKILL.md                    # Main Skill instructions
references/                 # Detailed product and execution rules
assets/                     # Content packs, source catalog, and config examples
scripts/                    # Existing execution helpers
fetcher.py                  # Existing fetcher prototype
requirements.txt            # Python dependencies
```

## Key References

- `references/onboarding.md`: onboarding flow and saved profile schema
- `references/source_strategy.md`: high-signal source library and source learning
- `references/content_selection.md`: candidate selection rules
- `references/scoring.md`: final gate and daily ranking
- `references/presentation.md`: output model and platform rendering
- `references/architecture.md`: Skill + local scripts now, optional MCP later
- `references/execution_pipeline.md`: existing pipeline commands and legacy details

## Agent Decision Artifacts

AI Headlines separates deterministic code from Agent judgment:

- Code exports `output/candidates.json`
- The Agent writes `output/decisions.json`
- Code applies decisions into `output/selected_news_draft.json`

This keeps runs resumable, easier to debug, and cheaper in tokens because the Agent only reads compact candidates instead of every raw item.

## Install as a Cursor Skill

Place this folder in a Cursor project under:

```text
.cursor/skills/ai-headlines/
```

or use it as a personal Skill under your Cursor skills directory.

## License

MIT
