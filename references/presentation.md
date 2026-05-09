# DeepLearning Presentation

Presentation turns ranked content into something users can read quickly, understand clearly, and open for deeper reading when they choose.

It is not a place for clickbait, marketing hooks, scoring details, or backend reasoning.

## Core Principle

The output should help users understand and digest high-quality content quickly.

Do not optimize for clicks. A good item gives value before the user opens the original source. The original link is for deeper reading, not for completing the basic meaning.

## Canonical Item Model

Use a platform-neutral item model before rendering to Feishu, Slack, Email, Telegram, HTML, or any other platform.

Recommended fields:

```json
{
  "rank": 1,
  "tag": "AI设计",
  "brief_text": "Google 在 Sheets 中加入 Gemini Canvas，表格数据可以直接生成看板、仪表盘或交互页面；办公软件中的 AI 正在从问答辅助扩展到信息呈现和业务界面生成。",
  "brief_language": "zh-CN",
  "source_language": "en",
  "source": "Google Workspace Blog",
  "source_url": "https://...",
  "content_type": "article",
  "image": {
    "url": "https://...",
    "source": "original_cover",
    "visual_role": "entry_image"
  }
}
```

Do not expose scoring fields, source roles, selection reasons, or internal metadata in the final card.

## brief_text

Each item should use one `brief_text`.

Do not split one item into title, subtitle, and summary. Avoid duplicated layers.

`brief_text` should:

- use the user's preferred language
- be one concise paragraph
- explain what the content is about
- preserve a meaningful information point
- accurately attribute who made the claim or action
- avoid clickbait, emotional framing, marketing tone, and forced "why this matters" phrasing
- preserve necessary proper nouns, product names, model names, repo names, and company names
- be understandable across roles when possible

Length:

- Chinese target: 120-220 characters
- Chinese hard max: 260 characters
- English target: 70-130 words
- English hard max: 160 words

Do not bind the product to Chinese. Use Chinese only when the user's preferred language is Chinese.

## Tone

Use calm information statements.

Avoid:

- "这篇文章讲的是..."
- "值得关注的是..."
- "对你来说..."
- presenting employee opinions as company decisions
- presenting secondary analysis as original reporting
- "没人告诉你的真相..."
- "已死..."
- "彻底改变..."
- direct clickbait translation
- emotional or sensational language
- technical jargon when it can be explained more clearly

Prefer:

- concrete subject
- concrete action
- concrete change
- relevant scenario or implication

Example:

```text
【AI设计】Google 在 Sheets 中加入 Gemini Canvas，表格数据可以直接生成看板、仪表盘或交互页面；办公软件中的 AI 正在从问答辅助扩展到信息呈现和业务界面生成。
```

## Tags

Keep one lightweight tag per item.

Rules:

- one tag only
- short and scannable
- no tag pile
- do not use tags as section headings

Examples:

- `AI设计`
- `AI商业`
- `量化研究`
- `开源工具`
- `产品案例`
- `市场结构`

## Source and Link

Always keep source attribution and an original link when available.

Render as:

```text
Source Name · 查看原文
```

Do not show backend source roles like `anchor`, `expert`, or `discovery`.

For public echoes or secondary analysis, preserve accurate attribution. Do not present a secondary interpretation as the original source.

## Claim Actor Attribution

Before writing `brief_text`, verify the actor of the main claim.

Do not write:

```text
Anthropic 建议废弃 Markdown。
```

if the actual source is a personal article from a Claude Code team member.

Write:

```text
Claude Code 团队成员 Thariq Shihipar 在个人文章中建议，复杂 AI 输出可以更多使用 HTML artifact，而不是默认写成长篇 Markdown。
```

Keep the distinction clear between:

- official company announcement
- official team or product blog
- employee personal opinion
- third-party analysis
- public echo or interpretation

If the actor cannot be confirmed, use conservative attribution or reject the item before rendering.

## Images

Images are visual entry points, not proof.

Priority:

1. original cover image
2. original inline image
3. video thumbnail
4. podcast cover
5. repo or product preview
6. restrained editorial illustration
7. no image

Use AI-generated images only when:

- no reliable original visual exists
- the item is important enough to benefit from a visual
- the generated image can stay restrained and editorial

Avoid:

- self-media style thumbnails
- exaggerated finance visuals
- fake UI with misleading details
- marketing-poster style graphics
- images with large generated text

## Platform Rendering

Use the strongest native message format available for the selected platform.

- Strong platforms: render native rich cards when possible.
- Weak platforms: send a compact notification with a link or attachment to the HTML digest.
- Email: HTML is acceptable as the primary rendering format.

Content model comes first. Platform rendering is only adaptation.

Recommended platform behavior:

- Feishu/Lark: rich interactive card
- Slack: Blocks if available, otherwise compact message plus HTML
- Telegram: compact message plus HTML
- Discord: embed if available, otherwise compact message plus HTML
- Email: HTML digest
- Unknown platform: compact message plus HTML fallback

## HTML Digest

HTML is a fallback and archive format, not necessarily the first product experience.

Generate HTML when useful for:

- weaker platforms
- email
- archive
- sharing
- future web page support

Do not let HTML requirements make the first version heavy.

## Ordering

Keep the final order from scoring and daily ranking.

Use numbered items:

```text
1. 【Tag】brief_text
2. 【Tag】brief_text
```

Do not create complex grouping unless a platform-specific renderer later needs it.

## Feedback Prompt

Do not add recurring feedback prompts at the bottom of every card.

Users interact with the Agent directly. They can say:

- "多发这个"
- "少发这个"
- "不要这个来源"
- "改成晚上发"

The onboarding flow can mention this once. The daily card should stay clean.
