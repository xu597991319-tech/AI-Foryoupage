# AI Headlines

**A personal AI information radar for Agents.**

AI Headlines helps an Agent turn noisy feeds into a personalized high-signal briefing. It learns what the user cares about, builds a source strategy, exports compact candidates, lets the Agent make structured decisions, and delivers concise briefings through rich cards or HTML fallback.

> AI Headlines is not a hosted news app. It is an Agent Skill plus local scripts that teach an Agent how to operate a personal information radar.

## What It Does

- **Agent-native onboarding**  
  Ask users what they care about, where to receive updates, and when to receive them.

- **High-signal source strategy**  
  Use source roles, source learning, and source renewal to avoid low-quality feeds.

- **Content selection before scoring**  
  Decide whether an item deserves candidate status before ranking it.

- **Structured Agent decisions**  
  Code exports `candidates.json`; the Agent writes `decisions.json`; code applies decisions.

- **Daily ranking, not generic scoring**  
  Rank candidates into the best daily composition instead of just scoring isolated items.

- **User-language brief text**  
  Generate concise `brief_text` in the user's preferred language, not necessarily the source language.

- **Rich delivery with fallback**  
  Use native rich cards when a platform supports them; generate HTML fallback when it does not.

- **Natural-language preference updates**  
  Users can say "more like this", "less of this", "stop showing this source", or "send it at 6pm".

## Why It Is Different

Most AI digest projects follow:

```text
configure feeds -> fetch -> summarize -> publish
```

AI Headlines is designed around an Agent workflow:

```text
onboard user -> build source strategy -> fetch -> export candidates
-> Agent writes decisions -> rank and render -> deliver
-> user adjusts by conversation
```

The main difference is that AI Headlines treats the Agent as the product interface, not just as a summarization backend.

## Prototype Pipeline

```bash
# Install dependencies first
python -m pip install -r requirements.txt

# Check local environment and configuration
python scripts/doctor.py
python scripts/validate_sources.py

# Optional: create a local editable source catalog
cp assets/sources_catalog.example.json assets/sources_catalog.json

# 1. Fetch and export compact candidates
python scripts/run_ai_headlines_pipeline.py prepare --dry-run

# 2. Let your Agent read output/candidates.json and write output/decisions.json

# 3. Apply decisions, finalize, render, and optionally send
python scripts/run_ai_headlines_pipeline.py finish --dry-run --skip-send
```

The finish stage produces:

- `output/digest.json`: canonical platform-neutral digest
- `output/digest.html`: HTML fallback/archive
- `output/ai_headlines_digest.card.json`: Feishu/Lark card draft

## Repository Structure

```text
SKILL.md                    # Main Skill instructions
references/                 # Detailed product and execution rules
assets/                     # Content packs, source catalog, and config examples
examples/                   # Minimal sample artifacts for Agent decisions
scripts/                    # Existing execution helpers
tests/                      # Smoke tests
fetcher.py                  # Existing fetcher prototype
requirements.txt            # Python dependencies
```

## Examples and Smoke Test

```bash
python tests/smoke_pipeline.py
```

This verifies:

```text
raw_news -> candidates -> decisions -> selected_news -> digest.json -> digest.html
```

## Install as a Cursor Skill

Place this folder in a Cursor project under:

```text
.cursor/skills/ai-headlines/
```

or use it as a personal Skill under your Cursor skills directory.

## Current Status

AI Headlines is currently a Skill-led prototype:

- Product rules are documented in `SKILL.md` and `references/`.
- Local scripts can export candidates, apply Agent decisions, build canonical digest JSON, render HTML, and render Feishu/Lark card drafts.
- Source catalog, doctor checks, and preference patching are available.
- Full onboarding automation, mature multi-platform delivery, and MCP tooling are future work.

## License

MIT
