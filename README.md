# AI Headlines

**A personal AI information radar for Agents.**

AI Headlines helps an Agent turn noisy feeds into a personalized high-signal briefing. It learns what the user cares about, builds a source strategy, exports compact candidates, lets the Agent make structured decisions, and delivers concise briefings through rich cards or HTML fallback.

> AI Headlines is not a hosted news app. It is an Agent Skill plus local scripts that teach an Agent how to operate a personal information radar.

---

## 中文简介

AI Headlines 是一个面向 Agent 的个人高信号信息雷达。

它不是传统 RSS 工具，也不是一个托管新闻 App。用户只需要告诉 Agent：

- 想看什么
- 在哪里收到
- 什么时候收到

然后 Agent 根据 Skill 规则和本地脚本完成信息源抓取、候选筛选、每日编排、内容生成和平台推送。

它的目标不是追热点，而是在信息噪音越来越高的环境里，帮助用户持续看到真正值得理解的内容。

---

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

---

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

The current prototype uses a two-stage local runner.

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

You can also run:

```bash
python scripts/run_ai_headlines_pipeline.py all --dry-run --skip-send
```

If `output/decisions.json` does not exist, `all` stops after generating `output/candidates.json`.

The finish stage also produces:

- `output/digest.json`: canonical platform-neutral digest
- `output/digest.html`: HTML fallback/archive
- `output/ai_headlines_digest.card.json`: Feishu/Lark card draft

### Agent decision shape

The Agent should write `output/decisions.json` like this:

```json
{
  "report_date": "2026-05-10",
  "items": [
    {
      "candidate_id": "c0001",
      "tag": "AI设计",
      "brief_text": "Google 在 Sheets 中加入 Gemini Canvas，表格数据可以直接生成看板、仪表盘或交互页面；办公软件中的 AI 正在从问答辅助扩展到信息呈现和业务界面生成。",
      "final_score": 82,
      "topics": ["AI 产品落地"],
      "daily_priority": 86,
      "information_gain": 78,
      "portfolio_value": 82,
      "attention_return": 75
    }
  ]
}
```

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

## Examples and Smoke Test

Minimal example artifacts live in `examples/`:

- `examples/raw_news.example.json`
- `examples/decisions.example.json`

Run the local artifact pipeline without network access:

```bash
python tests/smoke_pipeline.py
```

This verifies:

```text
raw_news -> candidates -> decisions -> selected_news -> digest.json -> digest.html
```

## Updating Preferences

Agents should translate natural-language feedback into a small patch file, then apply it safely:

```bash
python scripts/update_preferences.py --patch output/preference_patch.json --dry-run
python scripts/update_preferences.py --patch output/preference_patch.json
```

This updates local profile, schedule, delivery intent, or source preferences without hand-editing JSON.

Example patch:

```json
{
  "include_keywords_add": ["Figma", "design system"],
  "exclude_keywords_add": ["crypto"],
  "push_time": "18:00",
  "delivery_platforms": ["feishu"]
}
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

## Roadmap

- Complete onboarding automation.
- Add stronger source catalog editing and source learning workflows.
- Add more source types, especially podcasts and video metadata.
- Improve HTML digest design.
- Add platform-specific renderers beyond Feishu/Lark.
- Add optional MCP tools after the workflow stabilizes.

## License

MIT
