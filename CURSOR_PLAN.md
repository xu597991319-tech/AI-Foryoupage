# AI Headlines v2.0 重构指令

目标：把当前单线串行 + 固定权重流程，重构为 **双漏斗并发架构 + 四维动态打分 + 信源优胜劣汰机制**。

输出要求：
- 保持现有 CLI 用法尽量不破坏。
- 优先小步重构，不要一次性推翻全部流程。
- 代码要可读、可测试、可回退。

---

## 先理解当前结构

当前关键链路：
1. `fetcher.py`：抓 RSS / GitHub，做标准化、去重、预打标签。
2. `references/ai_digest_prompt.md`：定义 LLM 打分与输出 JSON。
3. `scripts/finalize_digest.py`：按分数排序、截断 Top 10、写回历史。

本次只重点改这 3 个位置，并新增 1 个本地状态文件：
- `fetcher.py`
- `references/ai_digest_prompt.md`
- `scripts/finalize_digest.py`
- `assets/sources_trust.json`

不要先改卡片渲染层。

---

## 任务 1：性能改造

### 1.1 改造目标

当前问题：全量抓取后串行送 LLM，整体耗时可到 40 分钟。

目标改为：
- RSS 抓取并发化。
- 粗筛前置。
- 只有粗筛通过的 Top 30 才进入 LLM 精筛。
- LLM 调用也并发化。

### 1.2 修改文件

修改：`fetcher.py`

### 1.3 代码结构要求

把 `fetcher.py` 从“同步大循环”改成下面这种职责拆分：

- `async fetch_rss_source(session, source, limit_per_source) -> list[dict]`
- `async fetch_all_rss(sources, limit_per_source) -> list[dict]`
- `coarse_filter_item(item) -> bool`
- `coarse_score_item(item) -> float`
- `run_funnel_one(items) -> list[dict]`
- `select_top_for_llm(items, top_n=30) -> list[dict]`

如果 GitHub 抓取暂时不改异步，可以先保留同步；但 RSS 必须改成 `asyncio + aiohttp`。

### 1.4 双漏斗机制

#### 漏斗一：粗筛

目标：在本地先过滤掉约 70% 明显无关内容。

实现要求：
- 不依赖 LLM。
- 用关键词正则 + 轻量规则判断。
- 结合以下字段：
  - `title`
  - `summary`
  - `content`
  - `category`
  - `source`
  - `source_type`
  - `extra.priority_tier`
- 明显弱相关内容直接淘汰。
- 粗筛后给每条保留项一个 `coarse_score`，用于进入漏斗二前排序。

建议规则：
- T0/T1 主题词命中：加分。
- `developer-news`、普通 GitHub release/commit：降分。
- 文本过短、信息密度过低、纯标题党、明显转载摘要：降分。
- `extra.priority_score_floor` 可作为粗筛加权信号，但不是最终分。

#### 漏斗二：精筛

目标：只把粗筛通过的 Top 30 送入 LLM。

实现要求：
- `run_funnel_one()` 先输出候选池。
- 按 `coarse_score` 降序取前 30。
- 对这 30 条并发调用 LLM API。
- LLM 返回新的四维评分 JSON。

### 1.5 数据结构新增

在 `fetcher.py` 输出的 item 上新增以下临时字段：

```json
{
  "coarse_pass": true,
  "coarse_score": 0.82,
  "coarse_reason": ["hit_quant_keyword", "priority_tier_T0"]
}
```

说明：
- `coarse_score` 建议归一化到 `0-1`。
- `coarse_reason` 用短 token，不写长句，便于调试。
- 这些字段可以保留在 `extra` 里，也可以挂在 item 根部；但全项目要统一。

建议：放进 `extra`，避免污染顶层字段。

即：

```json
"extra": {
  "coarse_pass": true,
  "coarse_score": 0.82,
  "coarse_reason": ["hit_quant_keyword", "priority_tier_T0"]
}
```

### 1.6 依赖

更新 `requirements.txt`：
- 新增 `aiohttp`

`asyncio` 用标准库，不需要额外安装。

---

## 任务 2：四维动态打分模型

### 2.1 修改文件

修改：`references/ai_digest_prompt.md`

### 2.2 改造目标

废弃旧版“只看 T0/T1/T2 段位分”的主评分逻辑。

新的 LLM 输出必须包含 4 个维度：
1. `score_new`：时效爆发力，权重 35%
2. `score_deep`：逻辑深度与事实密度，权重 30%
3. `score_target`：赛道核心度，权重 20%
4. `score_action`：实操启发性，权重 15%

并输出最终：
- `ai_raw_score`
- 每个维度的 `reason`

### 2.3 Prompt 设计要求

Prompt 里要明确写清：
- 反黑盒：不能只看标题，必须基于 `summary/content`。
- 反套壳：普通包装、转述、媒体二手稿要降分。
- 机构视角：优先高信息密度、可迁移、可决策的内容。
- 主体归因：个人观点、采访、评论，不可写成官方发布。

### 2.4 新输出 JSON 结构

LLM 单条输出改成下面这种结构：

```json
{
  "title": "中文标题",
  "original_title": "Original title",
  "source": "OpenAI Blog",
  "category": "ai-lab",
  "link": "https://...",
  "tag": "AI产品",
  "digest": "第一句事实。第二句洞察。",
  "score_new": 84,
  "score_new_reason": "发布新、传播快、短期影响强。",
  "score_deep": 78,
  "score_deep_reason": "原文给出较完整机制与事实。",
  "score_target": 90,
  "score_target_reason": "强命中核心赛道。",
  "score_action": 72,
  "score_action_reason": "可直接用于产品和工作流判断。",
  "ai_raw_score": 81.6,
  "topics": ["AI 产品落地"],
  "cover_image_url": "https://...",
  "image_prompt": "...",
  "extra": {
    "priority_tier": "T1",
    "priority_topics": ["AI 产品落地"],
    "priority_score_floor": 7
  }
}
```

### 2.5 计算公式

`ai_raw_score` 明确为加权总分：

```text
ai_raw_score = score_new * 0.35 + score_deep * 0.30 + score_target * 0.20 + score_action * 0.15
```

要求：
- 四个维度统一使用 `0-100`。
- `ai_raw_score` 也输出 `0-100`。
- 不再让 LLM直接输出旧版 `score=7.8` 这种 tier 分。

### 2.6 兼容策略

为了减少下游改动：
- 可保留一个兼容字段 `score`。
- 但其值应直接等于 `ai_raw_score`，或由 `finalize_digest.py` 在排序前映射生成。

建议：
- LLM 输出 `ai_raw_score`
- `finalize_digest.py` 统一把 `score = ai_raw_score`

这样更清晰。

---

## 任务 3：信源优胜劣汰机制

### 3.1 新增文件

新增：`assets/sources_trust.json`

### 3.2 最小数据结构

使用简单、稳定、易写回的结构：

```json
{
  "version": 1,
  "updated_at": "2026-05-10T00:00:00+00:00",
  "sources": {
    "OpenAI Blog": {
      "multiplier": 1.0,
      "wins": 0,
      "losses": 0,
      "last_seen_at": ""
    }
  },
  "domains": {
    "openai.com": {
      "multiplier": 1.0,
      "wins": 0,
      "losses": 0,
      "last_seen_at": ""
    }
  }
}
```

说明：
- 同时记录 `sources` 和 `domains`。
- 排序时优先取 `source`，缺失时回退到 `domain`。
- `multiplier` 初始值全部为 `1.0`。

### 3.3 评分公式

在 `scripts/finalize_digest.py` 中实现：

```text
Final_Score = ai_raw_score * multiplier
```

要求新增字段：
- `ai_raw_score`
- `source_trust_multiplier`
- `final_score`

建议在排序前统一补齐：

```json
{
  "ai_raw_score": 81.6,
  "source_trust_multiplier": 1.05,
  "final_score": 85.68
}
```

### 3.4 动态更新规则

在 `scripts/finalize_digest.py` 中写回 `sources_trust.json`：

- 进入最终 Top 10：`multiplier += 0.05`
- 在粗筛阶段淘汰，或 LLM 底分淘汰：`multiplier -= 0.01`
- 下限：`0.5`
- 上限建议：`1.5`，避免无限抬升

注意：
- 低于 `0.5` 的 source/domain，在下一次 `fetcher.py` 拉取时直接忽略。
- 忽略逻辑要尽量前置到抓取前，而不是抓完再丢。

### 3.5 `fetcher.py` 需要配合的事

`fetcher.py` 需要在启动时加载 `assets/sources_trust.json`，并新增：

- `load_sources_trust(path) -> dict`
- `get_source_multiplier(source_name, domain, trust_payload) -> float`
- `is_source_blocked(source_name, domain, trust_payload) -> bool`

如果 `multiplier < 0.5`：
- RSS：跳过该 source。
- GitHub：如果后续也纳入信源机制，同样跳过。

### 3.6 domain 提取

每条 item 最好补一个稳定字段：

```json
{
  "domain": "openai.com"
}
```

来源：从 `link` 解析。

这样 `finalize_digest.py` 不需要重复猜。

---

## `scripts/finalize_digest.py` 的具体改法

### 4.1 现有逻辑保留

保留：
- 扁平化 `items`
- Top N 截断
- 历史写回 `history_seen_urls.json`

### 4.2 需要新增的函数

建议新增：

- `load_sources_trust(trust_path: Path) -> dict`
- `ensure_sources_trust_file(trust_path: Path) -> None`
- `extract_domain(item: dict) -> str`
- `resolve_multiplier(item: dict, trust_payload: dict) -> float`
- `compute_final_score(item: dict, multiplier: float) -> float`
- `update_trust_after_finalize(...) -> dict`
- `apply_trust_result(...) -> None`

### 4.3 排序逻辑改造

当前 `_ranking_score = score + score_adjustment_hint` 需要升级。

建议新逻辑：

```text
base_score = ai_raw_score
adjusted_score = base_score + score_adjustment_hint
final_score = adjusted_score * source_trust_multiplier
```

最终排序按：
1. `final_score` 降序
2. `ai_raw_score` 降序
3. 现有 section 优先级
4. 原始顺序

### 4.4 淘汰回写规则

`finalize_digest.py` 不只处理 Top 10，还要知道哪些 item 被淘汰，用于回写 trust。

至少分 3 类：
- `selected_top10`
- `rejected_low_score`
- `rejected_after_rank_cutoff`

动态更新只要求处理两类负反馈：
- 粗筛淘汰
- 底分淘汰

因此建议：
- 粗筛淘汰在 `fetcher.py` 记录并可选写入一个 debug JSON。
- LLM 底分淘汰在 LLM 结果整理阶段可识别。
- `rank_cutoff` 不降权，避免惩罚高质量但没进前 10 的来源。

---

## 文件级改动说明

### A. `fetcher.py`

必须完成：
- RSS 抓取改 `aiohttp` 并发。
- 加载 `sources_trust.json`。
- 对黑名单 source/domain 直接跳过。
- 新增漏斗一粗筛。
- 只输出粗筛通过项进入后续 LLM 阶段。
- 给 item 补 `domain`、`coarse_score`、`coarse_pass` 等字段。

### B. `references/ai_digest_prompt.md`

必须完成：
- 删除旧版以 T0/T1/T2 为主的最终打分口径。
- T0/T1/T2 只保留为辅助分类语义，不再作为主分数区间。
- 改成四维评分 + 理由 + `ai_raw_score`。
- 明确要求输出合法 JSON。

### C. `scripts/finalize_digest.py`

必须完成：
- 读取 `sources_trust.json`
- 从 `ai_raw_score` 计算最终排序分
- 写回 `source_trust_multiplier`
- 更新 `sources_trust.json`
- 保留现有 history 写回逻辑

### D. `assets/sources_trust.json`

必须完成：
- 若不存在则自动初始化。
- 结构稳定。
- 支持 source/domain 两级存储。

---

## 推荐实现顺序

按这个顺序改，避免混乱：

1. 先定义 `assets/sources_trust.json` 结构与读写函数。
2. 再改 `scripts/finalize_digest.py`，先让新分数字段跑通。
3. 再改 `references/ai_digest_prompt.md`，让 LLM 输出四维评分。
4. 最后改 `fetcher.py` 的异步抓取 + 漏斗一。
5. 最后补 `requirements.txt`。

原因：先把评分和状态落盘机制稳定，再动最重的抓取层。

---

## 验收标准

### 性能

- RSS 抓取明显快于旧版串行。
- LLM 输入条数被稳定压到 `<= 30`。
- 整体耗时明显下降。

### 数据结构

最终候选 item 至少应包含：

```json
{
  "title": "...",
  "original_title": "...",
  "link": "...",
  "source": "...",
  "domain": "...",
  "category": "...",
  "tag": "...",
  "digest": "...",
  "score_new": 0,
  "score_deep": 0,
  "score_target": 0,
  "score_action": 0,
  "ai_raw_score": 0,
  "source_trust_multiplier": 1.0,
  "final_score": 0,
  "extra": {}
}
```

### 业务逻辑

- 粗筛能过滤大部分弱相关资讯。
- 最终排序不再是一刀切固定权重。
- 强信源会逐步抬升，弱信源会逐步边缘化。
- 低于 `0.5` 的 source/domain 下次会被跳过。

---

## 边界提醒

- 不要把 trust 逻辑写死在 prompt 里，trust 应该留在本地代码层。
- 不要把粗筛和精筛混在一起；漏斗一必须本地完成。
- 不要让 `finalize_digest.py` 依赖过多抓取细节；它只做排序、封顶、状态写回。
- 不要为了兼容旧字段把新字段设计得模糊。字段名要直接、稳定。

---

## 最终目标态

完成后，流程应变成：

1. `fetcher.py` 并发抓取 RSS
2. 跳过低信任 source/domain
3. 本地粗筛，过滤 70% 噪音
4. 取 Top 30 进入 LLM
5. LLM 输出四维评分 JSON
6. `scripts/finalize_digest.py` 计算 `final_score`
7. 全局排序，截断 Top 10
8. 写回 `assets/sources_trust.json`
9. 保持后续渲染层基本不动

按这个目标直接实施。
