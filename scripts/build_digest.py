#!/usr/bin/env python3
"""Build platform-neutral digest.json from selected AI Headlines items."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_INPUT = "output/selected_news_with_assets.json"
DEFAULT_OUTPUT = "output/digest.json"


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def image_payload(item: Dict[str, Any]) -> Dict[str, Any]:
    if clean_text(item.get("image_path")):
        return {
            "path": clean_text(item.get("image_path")),
            "source": "local_asset",
            "visual_role": "entry_image",
        }
    if clean_text(item.get("cover_image_url")):
        return {
            "url": clean_text(item.get("cover_image_url")),
            "source": "original_cover",
            "visual_role": "entry_image",
        }
    return {}


def normalize_item(item: Dict[str, Any], fallback_rank: int) -> Dict[str, Any]:
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    brief_text = (
        clean_text(item.get("brief_text"))
        or clean_text(item.get("digest"))
        or clean_text(item.get("summary"))
        or clean_text(item.get("title"))
    )
    normalized = {
        "rank": int(item.get("rank") or fallback_rank),
        "tag": clean_text(item.get("tag")) or "行业动态",
        "brief_text": brief_text,
        "brief_language": clean_text(item.get("brief_language")) or "zh-CN",
        "source_language": clean_text(item.get("source_language")),
        "source": clean_text(item.get("source")),
        "source_url": clean_text(item.get("link") or item.get("source_url")),
        "content_type": clean_text(item.get("content_type") or extra.get("source_type")),
        "topics": as_list(item.get("topics")),
        "score": item.get("final_score") or item.get("score"),
        "image": image_payload(item),
    }
    return {
        key: value
        for key, value in normalized.items()
        if value not in ("", None, [], {})
    }


def build_digest(payload: Dict[str, Any]) -> Dict[str, Any]:
    raw_items = payload.get("items")
    if not isinstance(raw_items, list):
        raw_items = []
    items = [
        normalize_item(item, fallback_rank=index)
        for index, item in enumerate(raw_items, start=1)
        if isinstance(item, dict)
    ]
    items.sort(key=lambda item: int(item.get("rank", 9999)))

    return {
        "version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": clean_text(payload.get("report_date")) or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "title": "AI Headlines",
        "scan_scope": clean_text(payload.get("scan_scope")),
        "meta": dict(payload.get("meta", {})) if isinstance(payload.get("meta"), dict) else {},
        "items": items,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build platform-neutral AI Headlines digest JSON")
    parser.add_argument("--input", default=DEFAULT_INPUT, help=f"Input selected JSON, default {DEFAULT_INPUT}")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Output digest JSON, default {DEFAULT_OUTPUT}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    payload = json.loads(input_path.read_text(encoding="utf-8-sig"))
    digest = build_digest(payload)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(digest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {output_path} ({len(digest['items'])} items)")


if __name__ == "__main__":
    main()
