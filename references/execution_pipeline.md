# AI Headlines Execution Pipeline

This file preserves the current AI Headlines execution details. `SKILL.md` should stay focused on product behavior and high-level rules.

## 输入与产物

- 输入：默认使用 onboarding 生成的 `assets/user_profile.json` 与 `assets/push_schedule.json`；如需扩展范围，可继续编辑 `fetcher.py` 中的 RSS 源与 GitHub 仓库列表。
- 原始抓取产物：JSON 文件，例如 `output/raw_news_today.json`。
- AI 处理草稿：结构化精选 JSON，例如 `output/selected_news_draft.json`。
- 封顶后结果：`output/selected_news.json`。
- 补图后结果：`output/selected_news_with_assets.json`。
- 飞书卡片草稿：交互式卡片 JSON，例如 `output/ai_headlines_digest.card.json`。
- 消息发送配置：`assets/lark_message_config.json`。
- 跨频次历史去重文件：`assets/history_seen_urls.json`（运行时自动初始化，默认已被 `.gitignore` 忽略）。
- 主要字段：`title`、`original_title`、`link`、`summary`、`content`、`published_at`、`source`、`source_type`、`category`、`tag`、`digest`、`cover_image_url`、`image_prompt`、`image_path`、`extra.priority_tier`、`extra.priority_topics`、`extra.priority_score_floor`、`extra.score_adjustment_hint`、`extra.suggested_score_ceiling`。
- 去重规则：先做单次抓取内去重（优先按 URL，其次按标题哈希），再读取 `assets/history_seen_urls.json` 做跨频次历史去重；如果 URL 或标题哈希已出现，则在进入 AI 评估前直接丢弃。

## 执行流程

1. 安装依赖。

   ```bash
   python3 -m pip install -r requirements.txt
   cp assets/sources_catalog.example.json assets/sources_catalog.json
   ```

2. 使用两段式入口准备候选。

   ```bash
   python3 scripts/run_ai_headlines_pipeline.py prepare --dry-run
   ```

   这一步会执行抓取和候选导出，生成：

   - `output/raw_news_today.json`
   - `output/candidates.json`
   - `output/run_status.json`

3. Agent/LLM 读取 `output/candidates.json`，写出 `output/decisions.json`。

4. 使用两段式入口完成后续处理。

   ```bash
   python3 scripts/run_ai_headlines_pipeline.py finish --dry-run --skip-send
   ```

   这一步会应用决策、封顶、补图、生成 `digest.json`、生成 `digest.html`、渲染平台卡片，并在非 dry-run 模式下发送。

下面保留子步骤命令，便于调试。

## 子步骤命令

1. 抓取并标准化新闻。

   ```bash
   python3 fetcher.py --output output/raw_news_today.json --limit-per-source 8 --history-file assets/history_seen_urls.json --sources-catalog assets/sources_catalog.json
   ```

   `fetcher.py` 会补充以下信息，供后续 AI 判断：

   - 对 RSS 与 GitHub 条目尽量回源抓取原文摘要与正文片段。
   - 优先提取原文的 `og:image` / `twitter:image` / 首图，并写入 `extra.cover_image_url`。
   - 按新的 tier 体系写入 `extra.priority_tier`、`extra.priority_topics`、`extra.priority_score_floor`。
   - 对 GitHub 条目与 `developer-news` 条目默认写入明显的 `extra.score_adjustment_hint` 与 `extra.suggested_score_ceiling`，提醒后续 AI **按 T2 处理**。
   - `stats.history_filtered_count` 会统计跨频次历史去重丢弃的条目数量。
   - 如果 `assets/sources_catalog.json` 不存在，fetcher 会回退读取 `assets/sources_catalog.example.json`。

2. 导出压缩候选快照，交给 Agent/LLM 判断。

   ```bash
   python3 scripts/export_candidates.py --input output/raw_news_today.json --output output/candidates.json --max-items 50
   ```

   `output/candidates.json` 只保留 Agent 判断需要的 compact payload，例如标题、来源、链接、摘要片段、正文片段、优先级元数据和图片线索。

3. Agent/LLM 读取 `output/candidates.json` 和 `references/ai_digest_prompt.md`，写出结构化决策文件。

   ```text
   output/decisions.json
   ```

   决策文件建议结构：

   ```json
   {
     "report_date": "2026-05-10",
     "items": [
       {
         "candidate_id": "c0001",
         "tag": "AI设计",
         "brief_text": "用用户偏好语言写成的一段解释。",
         "final_score": 82,
         "topics": ["AI 产品落地"],
         "daily_priority": 86,
         "information_gain": 78,
         "portfolio_value": 82,
         "attention_return": 75,
         "ranking_reasons": ["represents_today_key_change"],
         "ranking_penalties": []
       }
     ]
   }
   ```

4. 将 Agent 决策应用回现有 draft 格式。

   ```bash
   python3 scripts/apply_decisions.py --candidates output/candidates.json --decisions output/decisions.json --output output/selected_news_draft.json
   ```

5. 对候选结果执行**全局排序 + 数量封顶**，只保留得分最高的前 **10 条** 精选资讯。

   ```bash
   python3 scripts/finalize_digest.py --input output/selected_news_draft.json --output output/selected_news.json --max-items 10 --history-file assets/history_seen_urls.json
   ```

   这个步骤是强制步骤：

   - 必须按分数从高到低做**全局排序**，而不是每个分组各留几条。
   - 最终保留并输出的精选资讯**绝对不能超过 10 条**。
   - `scripts/finalize_digest.py` 会把 `extra.score_adjustment_hint` 作为排序修正项，进一步压低 GitHub / Developer Tools 在 Top 10 里的占位概率。
   - 最终保留下来的 Top 10 会写回 `assets/history_seen_urls.json`，确保只有成功保留的精选才进入跨频次历史。
   - 输出结果使用 **扁平 `items` 数组**，保留最终排序，不再重新分组。

## Agent 决策要求

Agent 在写 `output/decisions.json` 时必须满足：

- 只从 `output/candidates.json` 中选择内容，不凭空新增候选。
- 每个入选项必须带 `candidate_id`。
- 使用 `brief_text` 作为唯一正文层，不拆标题/副标题/摘要。
- `brief_text` 使用用户偏好语言；中文目标 120-220 字，上限 260 字，英文目标 70-130 words，上限 160 words。
- 必须保留一个轻量 `tag`。
- 必须给出 `final_score`，并可选给出 `daily_priority`、`information_gain`、`portfolio_value`、`attention_return`。
- 必须核对动作主体归因，不能把个人观点、员工文章、第三方分析或社区解读写成公司官方动作。
- 重复 story 只有在有新证据、新用例、新限制、实现细节、生态影响或专家分析时才入选。
- 不输出后台 source role、selection reason、score 解释到最终卡片。
- 可为无图但高价值的内容生成 `image_prompt`；优先透传候选里的 `cover_image_url`。

6. 为最终保留的条目补齐本地配图。

   ```bash
   python3 scripts/resolve_article_images.py --input output/selected_news.json --output output/selected_news_with_assets.json --assets-dir output/images
   ```

   **注意：** 这个脚本在缺少封面图时会调用 `inner_skills/image-generate` 生成图片，必须通过 `bash` 直接执行，并设置 `include_secrets=true`。

7. 生成平台无关 digest。

   ```bash
   python3 scripts/build_digest.py --input output/selected_news_with_assets.json --output output/digest.json
   ```

8. 生成 HTML fallback / archive。

   ```bash
   python3 scripts/render_html_digest.py --input output/digest.json --output output/digest.html
   ```

9. 将补图后的结果渲染成飞书交互式卡片草稿。

   ```bash
   python3 scripts/render_lark_digest.py --input output/selected_news_with_assets.json --output output/ai_headlines_digest.card.json
   ```

   渲染结果必须遵守：

   - 不写“一句话结论”。
   - 不写“精选条数”。
   - 不写“其他值得跟进”。
   - 不写“共性趋势判断”。
   - 不写任何二级分类标题。
   - 只保留：**卡片头部日期标题 → 扁平 Top 10 条目正文 → 紧跟正文的配图**。
   - 每条正文格式为：`{序号}. 【{类别标签}】{brief_text}`。
   - 当前兼容脚本会把 `brief_text` 映射到旧字段 `digest`，后续渲染层应直接使用 `brief_text`。

10. 直接把草稿推送到飞书聊天或指定话题。

   ```bash
   python3 scripts/send_lark_message.py --draft-file output/ai_headlines_digest.card.json
   ```

   发送阶段必须遵守：

   - 默认读取 `assets/lark_message_config.json`；未显式指定接收者时，默认发送到当前用户的飞书聊天。
   - 如需回复到已有话题，传入 `--reply-message-id <message_id>`，脚本会通过飞书话题回复发送。
   - 脚本会先上传每张配图，再创建卡片实体，最后以 **Interactive Card** 发送。
   - 卡片头部使用 `AI Headlines 每日精选 | {日期}`，默认蓝色 Header。
   - 相邻资讯之间必须插入 `hr` 分隔，避免正文与图片挤在一起。
   - **注意：** 这个脚本内部会调用 `inner_skills/feishu-im-send` 的发送脚本，必须通过 `bash` 直接执行，并设置 `include_secrets=true`。

## AI 打分规则（三档 tier）

对每条新闻先判断 tier，再在对应分段内给分。**必须严格按 tier 评分**，不要把 T0 / T1 / T2 混打。

### T0（9-10 分，最高优先级）

以下方向默认按 T0 审视：

- **量化交易（Quant）**：因子、策略、回测、组合优化、风险模型、研究框架、执行与微观结构。
- **美股市场（US Stocks）**：美股市场结构、行情数据、券商与交易基础设施、选股/研究工具、ETF / Options / Earnings 等核心市场信号。
- **交易策略与市场信号**：策略研究、alpha 信号、波动率、事件驱动、趋势跟踪、跨市场联动等。

### T1（7-8 分，高优先级）

以下方向默认按 T1 审视：

- **AI 产品落地**：AI 产品发布、可直接使用的新功能、企业级落地能力。
- **AI 行业实践**：团队/企业如何把 AI 用进业务流程，是否有明确可迁移的方法论。
- **AI 工作流应用**：Agent 编排、工具调用、自动化流程、工作台与工作流产品化。

### T2（5-6 分，中低优先级）

以下方向默认按 T2 审视：

- **GitHub 热门项目**：包括热门 repo、版本发布、commit 动态。
- **底层开发工具**：IDE、编辑器、工程工具、泛开发效率工具、普通 infra 更新。
- **普通 developer-news**：除非它明确带来重大技术突破，或直接改变 Quant / US Stocks / AI 工作流，否则默认保持在 T2。

### 严格评分约束

- 先定 tier，再打分。
- 允许小数，但分数必须落在对应区间：
  - T0：`9.0 - 10.0`
  - T1：`7.0 - 8.9`
  - T2：`5.0 - 6.9`
- **T2 默认会因低于 7 分而被过滤**；只有当条目存在明确重大突破、显著改变工作流、或具备强可迁移的方法论价值时，才允许上调到 T1 甚至 T0。
- 不要因为仓库是 Quant / US Stocks 相关 GitHub repo，就自动给高分 floor。

### 打分时优先拉高

- `extra.priority_tier=T0` 且命中 `extra.priority_topics` 的 RSS 条目。
- 能直接改变研究工作流、交易工作流或市场判断方式的内容。
- 有清晰方法论、清晰信号、清晰“为什么现在重要”的内容。
- AI 产品落地案例里，具备明确业务场景、流程变化与迁移价值的内容。

### 打分时优先降低

- `category=developer-news` 的条目。
- `source_type=github_release` / `github_commit` 的条目。
- 带有 `extra.score_adjustment_hint < 0` 或 `extra.suggested_score_ceiling < 7` 的条目。
- 纯品牌宣传、常规版本迭代、泛工程效率工具、与主线弱相关的资讯。
- 只有个人表态、采访引述或第三方评论，且无法确认是官方动作的内容。

## 过滤规则

- 只保留 **7 分及以上** 的条目。
- T0 与 T1 是主要候选池；T2 默认过滤。
- 对命中 **量化交易（Quant）/ 美股市场（US Stocks）/ 交易策略与市场信号** 的 RSS 条目，只要原文存在实质信息，默认优先进入候选池。
- 对 GitHub 热门项目、普通底层开发工具、developer-news，默认不进入候选池；只有出现明确重大突破时才保留。
- 若只能确认到个人观点、采访引述或第三方评论，且无法证明确为官方动作，默认降分；信息不足时直接过滤。
- 同主题多条内容同时出现时，只保留信息最完整、最原始、最能说明变化的一条。
- 如果条目虽然热度高，但没有说明“它是什么、为什么现在重要、会带来什么影响”，视为信息不足，可以过滤。
- 候选池生成后，必须按最终分数做**全局降序排序**，只保留得分最高的前 **10 条**。
- 最终飞书卡片里的精选资讯条目总数**必须 <= 10**。

## 极简总结规则

对保留下来的每条信息，**必须基于原文的 `summary` / `content` 提炼极简 digest**。

### 单条输出字段

- `tag`：2-6 个字的小标签，例如 `AI模型`、`AI产品`、`量化研究`、`美股市场`、`交易信号`。
- `digest`：一段两句。
  - 第一句：现象（Fact）——只写**已核实**的主体与动作。
  - 第二句：洞察（Insight）——只写保守影响、用途或启发，不把猜测写成事实。

### 事实核查与反标题党

- 写 `digest` 前，必须回看原文 `summary` / `content` / 正文片段，确认标题有没有夸张、偷换主体或把评论写成事实。
- 只有原文能明确证明是公司 / 机构官方正式发布，才能写“某公司发布 / 宣布 / 上线”。
- 若只是员工、研究员、团队成员、作者个人博客 / 采访 / 发言，必须写成“某团队成员提到 / 主张 / 复盘……”，绝不可夸大为公司官方动作。
- 遇到“弃用 / 官宣 / 颠覆 / 全面支持 / 正式发布”等刺激性表述，必须回看正文核实；正文证据不足时，改写为保守说法，或直接过滤。
- 如果无法确认主体与动作，优先写“原文仅提到……”或“作者认为……”。

### 硬性字数上限

- `digest` 两句合计 **绝对不能超过 120 个非空白字符**。
- 超过上限时，继续删字，直到只剩最关键的动作与影响。
- 原文信息不足时，直接说“原文信息有限”或“原文仅提到……”。仍然必须控制在 120 字内。

### 结果整理与飞书卡片结构

最终飞书卡片只保留以下层级：

1. 卡片标题：`AI Headlines 每日精选 | 日期`
2. `1. 【类别标签】两句正文`
3. `查看原文`
4. 配图
5. `hr` 分隔线

不要再输出以下板块：

- 一句话结论
- 精选条数
- 其他值得跟进
- 共性趋势判断
- 分类二级标题
- 三级文章标题

## 飞书发送目标

- 默认发送配置记录在 `assets/lark_message_config.json`。
- 未显式指定接收者时，优先发送到当前用户的飞书聊天。
- 如需发到已有聊天话题，传入 `--reply-message-id` 并通过 `scripts/send_lark_message.py` 发送。
- 不再沉淀到固定飞书文档，也不要重复创建日报文档。

## 失败排查

- 如果抓取失败条目较多，先查看 JSON 里的 `errors` 字段，再重试执行 `python3 fetcher.py`。
- 如果原始抓取条目显著偏少，先看 `stats.history_filtered_count` 是否过高，以及 `assets/history_seen_urls.json` 是否需要人工清理。
- 如果 AI 处理结果里缺少 `cover_image_url` 和 `image_prompt`，先重新按 `references/ai_digest_prompt.md` 产出草稿。
- 如果 `render_lark_digest.py` 报 digest 超长，说明 AI 输出没有压够或没有按 120 字上限收缩，必须先重做 AI 草稿，再继续发送。
- 如果图片补齐失败，先确认 `scripts/resolve_article_images.py` 是通过 `bash` 直接执行，且设置了 `include_secrets=true`。
- 如果飞书消息发送失败，先确认 `scripts/send_lark_message.py` 是通过 `bash` 直接执行，且设置了 `include_secrets=true`；再检查 `assets/lark_message_config.json`、接收者参数与图片上传结果。
- 如果高优先级主题被错误过滤，先检查条目的 `extra.priority_tier`、`extra.priority_topics`、`extra.priority_score_floor` 与 `extra.score_adjustment_hint`。
