#!/usr/bin/env python3
"""Export a compact candidate snapshot for Agent/LLM decisions."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_INPUT = "output/raw_news_today.json"
DEFAULT_OUTPUT = "output/candidates.json"
DEFAULT_MAX_ITEMS = 50
DEFAULT_EXCERPT_CHARS = 900


def compact_text(value: Any, limit: int) -> str:
    text = " ".join(str(value or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def build_candidate(
    item: Dict[str, Any],
    *,
    index: int,
    excerpt_chars: int,
) -> Dict[str, Any]:
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    summary = compact_text(item.get("summary", ""), excerpt_chars // 2)
    content = compact_text(item.get("content", ""), excerpt_chars)
    excerpt_parts = [part for part in [summary, content] if part]
    excerpt = "\n\n".join(excerpt_parts)

    return {
        "candidate_id": f"c{index:04d}",
        "raw_index": index - 1,
        "title": str(item.get("title", "")).strip(),
        "original_title": str(item.get("original_title") or item.get("title", "")).strip(),
        "source": str(item.get("source", "")).strip(),
        "category": str(item.get("category", "")).strip(),
        "link": str(item.get("link", "")).strip(),
        "published_at": str(item.get("published_at", "")).strip(),
        "source_type": str(item.get("source_type") or extra.get("source_type", "")).strip(),
        "priority_tier": str(extra.get("priority_tier", "")).strip(),
        "priority_topics": as_list(extra.get("priority_topics")),
        "priority_score_floor": extra.get("priority_score_floor"),
        "score_adjustment_hint": extra.get("score_adjustment_hint"),
        "suggested_score_ceiling": extra.get("suggested_score_ceiling"),
        "coarse_score": extra.get("coarse_score"),
        "coarse_reason": as_list(extra.get("coarse_reason")),
        "cover_image_url": str(extra.get("cover_image_url", "")).strip(),
        "excerpt": excerpt,
    }


def export_candidates(
    payload: Dict[str, Any],
    *,
    max_items: int,
    excerpt_chars: int,
) -> Dict[str, Any]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raw_items = []

    items = [
        build_candidate(item, index=index, excerpt_chars=excerpt_chars)
        for index, item in enumerate(raw_items[:max_items], start=1)
        if isinstance(item, dict)
    ]

    stats = dict(payload.get("stats", {})) if isinstance(payload.get("stats"), dict) else {}
    stats["exported_candidate_count"] = len(items)
    stats["candidate_export_limit"] = max_items

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_generated_at": payload.get("generated_at", ""),
        "report_date": payload.get("report_date", datetime.now(timezone.utc).strftime("%Y-%m-%d")),
        "scan_scope": payload.get("scan_scope", "AI、Quant、US Stocks、开发工具、开源仓库"),
        "stats": stats,
        "decision_instructions": {
            "output_file": "output/decisions.json",
            "selected_items_key": "items",
            "required_per_item": ["candidate_id", "tag", "brief_text", "final_score"],
            "optional_per_item": [
                "topics",
                "title",
                "image_prompt",
                "daily_priority",
                "information_gain",
                "portfolio_value",
                "attention_return",
                "ranking_reasons",
                "ranking_penalties",
            ],
        },
        "items": items,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export compact candidates for Agent decisions")
    parser.add_argument("--input", default=DEFAULT_INPUT, help=f"Input raw news JSON, default {DEFAULT_INPUT}")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Output candidates JSON, default {DEFAULT_OUTPUT}")
    parser.add_argument("--max-items", type=int, default=DEFAULT_MAX_ITEMS, help="Maximum candidates to export")
    parser.add_argument("--excerpt-chars", type=int, default=DEFAULT_EXCERPT_CHARS, help="Maximum content excerpt length")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    candidates = export_candidates(
        payload,
        max_items=max(1, args.max_items),
        excerpt_chars=max(200, args.excerpt_chars),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(candidates, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {output_path} ({len(candidates['items'])} candidates)")


if __name__ == "__main__":
    main()
