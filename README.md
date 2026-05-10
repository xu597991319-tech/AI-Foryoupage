# AI Headlines

**中文** · [English](./README.en.md)

#### 一个给 Agent 用的个人专属今日头条

[![License](https://img.shields.io/badge/License-MIT-3B82F6?style=for-the-badge)](./LICENSE)
[![Skill](https://img.shields.io/badge/Agent_Skill-ai--headlines-8B5CF6?style=for-the-badge)](./SKILL.md)
[![Status](https://img.shields.io/badge/Status-Prototype-F59E0B?style=for-the-badge)](#-当前状态)

AI Headlines 想解决的是一个很普通但越来越明显的问题：信息越来越多，低质量内容越来越便宜，真正值得看的东西反而越来越难找。

它不是一个新闻 App，也不是一个 RSS 阅读器。它是一个 **Agent Skill**：装上之后，你的 Agent 会学会怎么给你搭一个个人信息雷达。

你只需要告诉它三件事：

- 你想看什么
- 你想在哪收到
- 你想什么时候收到

剩下的事情交给 Agent：找源、抓取、过滤、判断、排序、生成卡片、推送。

---

## 它和普通 AI 摘要有什么不同？

大多数 digest 项目是：

```text
配置 RSS -> 抓取 -> 总结 -> 发布
```

AI Headlines 更像：

```text
用户表达兴趣 -> Agent 建立雷达 -> 抓取候选 -> Agent 结构化判断
-> 每日编排 -> 生成卡片 / HTML -> 用户继续用对话调教
```

几个核心区别：

- **不是让用户配源**：用户说想看什么，Agent 决定去哪找。
- **不是所有内容都总结**：先判断内容有没有资格进入候选池。
- **不是简单打分排序**：先做最终守门，再做每日 10 条组合。
- **不是黑箱推荐**：用户可以直接说“多发这个”“少发这个”“不要这个来源”。
- **不是只支持纯文本**：播客、视频、字幕、show notes、公开讨论都可以成为候选，只要能转成可靠文本。

---

## 现在能做什么？

- 首次 onboarding：问用户看什么、在哪收、什么时候收。
- 根据内容包和 source catalog 抓取 RSS / GitHub 内容。
- 导出 `candidates.json`，让 Agent 只判断压缩后的候选，减少 token 浪费。
- Agent 写 `decisions.json`，代码再合并回下游流程。
- 生成：
  - `digest.json`
  - `digest.html`
  - 飞书 / Lark 卡片草稿
- 支持自然语言偏好更新，例如：
  - “少发金融”
  - “多发 Figma 和设计系统”
  - “不要加密货币”
  - “改成晚上 6 点发”

---

## 快速体验

当前还是原型版本，推荐先用 dry-run 跑本地流程。

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

也可以直接运行：

```bash
python scripts/run_ai_headlines_pipeline.py all --dry-run --skip-send
```

如果 `output/decisions.json` 不存在，`all` 会在生成 `output/candidates.json` 后停下来，等待 Agent 写决策文件。

`finish` 阶段会生成：

- `output/digest.json`: canonical platform-neutral digest
- `output/digest.html`: HTML fallback/archive
- `output/ai_headlines_digest.card.json`: Feishu/Lark card draft

### Agent 决策文件长什么样？

Agent 应该写出类似这样的 `output/decisions.json`：

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

---

## 目录结构

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

## 关键文档

- `references/onboarding.md`: onboarding flow and saved profile schema
- `references/source_strategy.md`: high-signal source library and source learning
- `references/content_selection.md`: candidate selection rules
- `references/scoring.md`: final gate and daily ranking
- `references/presentation.md`: output model and platform rendering
- `references/architecture.md`: Skill + local scripts now, optional MCP later
- `references/execution_pipeline.md`: existing pipeline commands and legacy details

## 为什么要有 candidates / decisions？

AI Headlines 把确定性工作和 Agent 判断分开：

- 代码导出 `output/candidates.json`
- Agent 写 `output/decisions.json`
- 代码把决策应用回 `output/selected_news_draft.json`

这样有三个好处：

- 可恢复：Agent 判断失败时不用重新抓取。
- 可调试：能看到候选和决策。
- 省 token：Agent 不需要读所有原始内容。

## 示例和 Smoke Test

最小示例在 `examples/`：

- `examples/raw_news.example.json`
- `examples/decisions.example.json`

不依赖网络跑一遍本地 artifact 流程：

```bash
python tests/smoke_pipeline.py
```

它会验证：

```text
raw_news -> candidates -> decisions -> selected_news -> digest.json -> digest.html
```

## 用一句话调整偏好

Agent 会把自然语言反馈转成 patch，再由脚本安全更新配置：

```bash
python scripts/update_preferences.py --patch output/preference_patch.json --dry-run
python scripts/update_preferences.py --patch output/preference_patch.json
```

示例：

用户说：

```text
以后少发金融，多发 Figma 和设计系统，晚上 6 点推给我。
```

Agent 可以生成：

```json
{
  "include_keywords_add": ["Figma", "design system"],
  "exclude_keywords_add": ["crypto"],
  "push_time": "18:00",
  "delivery_platforms": ["feishu"]
}
```

## 安装成 Cursor Skill

把这个目录放到你的项目里：

```text
.cursor/skills/ai-headlines/
```

也可以作为个人 Skill 使用。

## 当前状态

AI Headlines 目前还是 **Skill-led prototype**：

- 产品规则已经写在 `SKILL.md` 和 `references/`。
- 本地脚本可以导出候选、应用 Agent 决策、生成 `digest.json`、生成 HTML、渲染飞书卡片草稿。
- Source catalog、doctor 检查、偏好 patch 更新已经可用。
- 完整 onboarding 自动化、多平台成熟投递、MCP 工具化还在 roadmap 中。

## Roadmap

- 完成 onboarding 自动化。
- 强化 source catalog 编辑和 source learning。
- 增加更多源类型，尤其是 podcast / video metadata。
- 改进 HTML digest 设计。
- 增加飞书以外的平台 renderer。
- 工作流稳定后再 MCP 化。

## License

MIT
