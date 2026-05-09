#!/usr/bin/env python3
"""将 AI Headlines 的扁平精选结果渲染成飞书交互式卡片草稿 JSON。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, List

MAX_SELECTED_ITEMS = 10
MAX_DIGEST_LENGTH = 120
TAG_FALLBACK_BY_CATEGORY = {
    "ai-lab": "AI模型",
    "ai-tools": "AI产品",
    "quant-research": "量化研究",
    "us-stocks": "美股市场",
    "developer-news": "开发工具",
}


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def parse_rank(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def visible_length(text: str) -> int:
    return len(compact_text(text))


def normalize_digest(item: Dict[str, Any]) -> str:
    for key in ("digest", "summary_text", "ai_summary", "brief"):
        text = " ".join(str(item.get(key, "")).split()).strip()
        if text:
            return text
    return ""


def validate_digest(item: Dict[str, Any], digest: str) -> str:
    text = digest.strip()
    if not text:
        raise ValueError(f"条目缺少 digest：{item.get('title', 'unknown')}")
    if visible_length(text) > MAX_DIGEST_LENGTH:
        raise ValueError(
            f"digest 超长（>{MAX_DIGEST_LENGTH}）：{item.get('title', 'unknown')} -> {text}"
        )
    return text


def infer_tag(item: Dict[str, Any]) -> str:
    explicit = str(item.get("tag", "")).strip()
    if explicit:
        return explicit

    category = str(item.get("category", "")).strip().lower()
    if category in TAG_FALLBACK_BY_CATEGORY:
        return TAG_FALLBACK_BY_CATEGORY[category]

    topics = set(as_list(item.get("topics")))
    if "美股交易（US Stocks）" in topics or "美股市场（US Stocks）" in topics:
        return "美股市场"
    if "量化投资（Quant）" in topics or "量化交易（Quant）" in topics:
        return "量化研究"
    if "AI技术" in topics:
        return "AI技术"
    return "行业动态"


def flatten_items(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if isinstance(payload.get("items"), list):
        return [dict(item) for item in payload.get("items", [])]

    flattened: List[Dict[str, Any]] = []
    for section in payload.get("sections", []):
        section_title = str(section.get("title", "")).strip()
        for item in section.get("items", []):
            normalized = dict(item)
            if section_title and not str(normalized.get("section_title", "")).strip():
                normalized["section_title"] = section_title
            flattened.append(normalized)
    return flattened


def normalize_payload(payload: Dict[str, Any], max_items: int = MAX_SELECTED_ITEMS) -> Dict[str, Any]:
    normalized_items: List[Dict[str, Any]] = []
    for original_index, item in enumerate(flatten_items(payload), start=1):
        normalized = dict(item)
        normalized["rank"] = parse_rank(item.get("rank"), default=original_index)
        normalized["tag"] = infer_tag(normalized)
        normalized["digest"] = validate_digest(normalized, normalize_digest(normalized))
        normalized["_original_index"] = original_index
        normalized_items.append(normalized)

    normalized_items.sort(key=lambda item: (item["rank"], item["_original_index"]))
    normalized_items = normalized_items[:max_items]

    normalized_payload = dict(payload)
    normalized_payload.pop("sections", None)
    normalized_payload["items"] = [
        {key: value for key, value in item.items() if not key.startswith("_")}
        for item in normalized_items
    ]
    normalized_payload["meta"] = dict(payload.get("meta", {}))
    normalized_payload["meta"]["max_selected_items"] = max_items
    normalized_payload["meta"]["selected_item_count"] = len(normalized_items)
    normalized_payload["meta"]["max_digest_length"] = MAX_DIGEST_LENGTH
    return normalized_payload


def build_card_draft(payload: Dict[str, Any]) -> Dict[str, Any]:
    payload = normalize_payload(payload, max_items=MAX_SELECTED_ITEMS)
    report_date = str(payload.get("report_date", "")).strip()
    items = payload.get("items", [])

    card_items: List[Dict[str, Any]] = []
    for fallback_rank, item in enumerate(items, start=1):
        rank = parse_rank(item.get("rank"), default=fallback_rank)
        tag = str(item.get("tag", "")).strip() or infer_tag(item)
        digest = validate_digest(item, normalize_digest(item))
        card_items.append(
            {
                "rank": rank,
                "tag": tag,
                "title": str(item.get("title", "")).strip(),
                "digest": digest,
                "link": str(item.get("link", "")).strip(),
                "image_path": str(item.get("image_path", "")).strip(),
                "image_alt": str(item.get("title", "资讯配图")).strip() or "资讯配图",
            }
        )

    return {
        "msg_type": "interactive",
        "report_date": report_date,
        "header_title": f"AI Headlines 每日精选 | {report_date}" if report_date else "AI Headlines 每日精选",
        "header_template": "blue",
        "meta": payload.get("meta", {}),
        "items": card_items,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把 AI Headlines 的结构化 JSON 渲染成飞书交互式卡片草稿")
    parser.add_argument("--input", required=True, help="输入 JSON 文件路径")
    parser.add_argument("--output", required=True, help="输出交互式卡片草稿 JSON 文件路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    draft = build_card_draft(payload)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(draft, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已生成 {output_path}")


if __name__ == "__main__":
    main()
