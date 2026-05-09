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
-> content selection
-> scoring and daily ranking
-> canonical digest
-> platform rendering
-> delivery
```

## Repository Structure

```text
SKILL.md                    # Main Skill instructions
references/                 # Detailed product and execution rules
assets/                     # Content packs and config examples
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

## Install as a Cursor Skill

Place this folder in a Cursor project under:

```text
.cursor/skills/ai-headlines/
```

or use it as a personal Skill under your Cursor skills directory.

## License

MIT
