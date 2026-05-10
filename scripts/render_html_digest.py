#!/usr/bin/env python3
"""Render a lightweight HTML fallback from digest.json."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any, Dict

DEFAULT_INPUT = "output/digest.json"
DEFAULT_OUTPUT = "output/digest.html"


def esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def render_image(image: Dict[str, Any]) -> str:
    src = image.get("path") or image.get("url")
    if not src:
        return ""
    return f'<img class="item-image" src="{esc(src)}" alt="" loading="lazy" />'


def render_item(item: Dict[str, Any]) -> str:
    rank = esc(item.get("rank", ""))
    tag = esc(item.get("tag", ""))
    brief = esc(item.get("brief_text", ""))
    source = esc(item.get("source", ""))
    source_url = esc(item.get("source_url", ""))
    source_html = (
        f'<a href="{source_url}" target="_blank" rel="noopener noreferrer">{source or "Source"}</a>'
        if source_url
        else source
    )
    image_html = render_image(item.get("image", {}) if isinstance(item.get("image"), dict) else {})
    return f"""
    <article class="digest-item">
      <div class="item-main">
        <p class="item-brief"><span class="rank">{rank}.</span> <span class="tag">【{tag}】</span>{brief}</p>
        <p class="source">{source_html}</p>
      </div>
      {image_html}
    </article>
    """


def render_html(digest: Dict[str, Any]) -> str:
    title = esc(digest.get("title") or "AI Headlines")
    date = esc(digest.get("date", ""))
    items = digest.get("items") if isinstance(digest.get("items"), list) else []
    item_html = "\n".join(render_item(item) for item in items if isinstance(item, dict))
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{title} {date}</title>
  <style>
    :root {{
      color-scheme: light dark;
      --fg: #202124;
      --muted: #5f6368;
      --line: #e5e7eb;
      --bg: #ffffff;
      --card: #ffffff;
      --link: #2563eb;
    }}
    @media (prefers-color-scheme: dark) {{
      :root {{
        --fg: #e5e7eb;
        --muted: #9ca3af;
        --line: #30363d;
        --bg: #0d1117;
        --card: #111827;
        --link: #60a5fa;
      }}
    }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--fg);
      font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.6;
    }}
    main {{
      max-width: 860px;
      margin: 0 auto;
      padding: 32px 18px 56px;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      margin-bottom: 18px;
      padding-bottom: 18px;
    }}
    h1 {{
      font-size: 28px;
      margin: 0 0 4px;
      letter-spacing: -0.02em;
    }}
    .date {{
      color: var(--muted);
      margin: 0;
      font-size: 14px;
    }}
    .digest-item {{
      display: grid;
      grid-template-columns: 1fr 220px;
      gap: 20px;
      border-bottom: 1px solid var(--line);
      padding: 22px 0;
      align-items: start;
    }}
    .item-brief {{
      margin: 0 0 10px;
      font-size: 17px;
    }}
    .rank {{
      color: var(--muted);
      margin-right: 4px;
    }}
    .tag {{
      font-weight: 700;
      margin-right: 4px;
    }}
    .source {{
      margin: 0;
      font-size: 14px;
      color: var(--muted);
    }}
    a {{
      color: var(--link);
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .item-image {{
      width: 220px;
      max-height: 150px;
      object-fit: cover;
      border-radius: 10px;
      background: var(--line);
    }}
    @media (max-width: 720px) {{
      .digest-item {{
        grid-template-columns: 1fr;
      }}
      .item-image {{
        width: 100%;
        max-height: 220px;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{title}</h1>
      <p class="date">{date}</p>
    </header>
    {item_html}
  </main>
</body>
</html>
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render AI Headlines HTML digest")
    parser.add_argument("--input", default=DEFAULT_INPUT, help=f"Input digest JSON, default {DEFAULT_INPUT}")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Output HTML file, default {DEFAULT_OUTPUT}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    digest = json.loads(input_path.read_text(encoding="utf-8-sig"))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_html(digest), encoding="utf-8")
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
