#!/usr/bin/env python3
"""对 Todayradar 的精选结果进行排序、封顶并输出扁平 Top 10。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse

MAX_SELECTED_ITEMS = 10
DEFAULT_HISTORY_FILE = "assets/history_seen_urls.json"
DEFAULT_TRUST_FILE = "assets/sources_trust.json"
HISTORY_FILE_VERSION = 1
TRUST_FILE_VERSION = 1

TRUST_MULTIPLIER_MIN = 0.5
TRUST_MULTIPLIER_MAX = 1.5
TRUST_WIN_DELTA = 0.05
TRUST_LOSS_DELTA = 0.01

# 与新 Prompt 的 0-100 量表对齐：70 分以下视为“底分淘汰”候选，用于负反馈更新。
LOW_SCORE_THRESHOLD = 70.0
SECTION_PRIORITY = {
    "AI方向": 0,
    "量化与美股方向": 1,
    "工具与开源方向": 2,
}
TAG_FALLBACK_BY_CATEGORY = {
    "ai-lab": "AI模型",
    "ai-tools": "AI产品",
    "quant-research": "量化研究",
    "us-stocks": "美股市场",
    "developer-news": "开发工具",
}
T0_TOPICS = {
    "量化交易（Quant）",
    "美股市场（US Stocks）",
    "交易策略与市场信号",
    "量化投资（Quant）",
    "美股交易（US Stocks）",
}
T1_TOPICS = {
    "AI 产品落地",
    "AI 行业实践",
    "AI 工作流应用",
    "AI技术",
}


def as_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def parse_score(value) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def parse_adjustment(item: Dict) -> float:
    direct = item.get("score_adjustment_hint")
    if direct is not None:
        return parse_score(direct)
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    return parse_score(extra.get("score_adjustment_hint", 0))


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def normalize_link(value: str) -> str:
    return (value or "").strip().lower()


def title_hash(title: str) -> str:
    normalized = re.sub(r"\s+", " ", (title or "")).strip().lower()
    return sha256_text(normalized) if normalized else ""


def dedupe_key(title: str, link: str) -> str:
    normalized_link = normalize_link(link)
    if normalized_link:
        return f"url:{normalized_link}"
    return f"title:{title_hash(title)}"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_trust_payload() -> Dict:
    return {
        "version": TRUST_FILE_VERSION,
        "updated_at": iso_now(),
        "sources": {},
        "domains": {},
    }


def ensure_sources_trust_file(trust_path: Path) -> None:
    trust_path.parent.mkdir(parents=True, exist_ok=True)
    if trust_path.exists():
        return
    trust_path.write_text(json.dumps(empty_trust_payload(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_sources_trust(trust_path: Path) -> Dict:
    ensure_sources_trust_file(trust_path)
    try:
        payload = json.loads(trust_path.read_text(encoding="utf-8"))
    except Exception:
        payload = empty_trust_payload()
        trust_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    if not isinstance(payload, dict):
        payload = empty_trust_payload()

    payload["version"] = int(payload.get("version") or TRUST_FILE_VERSION)
    payload["updated_at"] = str(payload.get("updated_at", "")).strip() or iso_now()
    payload["sources"] = payload.get("sources") if isinstance(payload.get("sources"), dict) else {}
    payload["domains"] = payload.get("domains") if isinstance(payload.get("domains"), dict) else {}
    return payload


def extract_domain(item: Dict) -> str:
    explicit = str(item.get("domain", "")).strip().lower()
    if explicit:
        return explicit
    link = str(item.get("link", "")).strip()
    if not link:
        return ""
    try:
        parsed = urlparse(link)
    except Exception:
        return ""
    return (parsed.netloc or "").lower()


def _ensure_trust_entry(container: Dict, key: str) -> Dict:
    if not key:
        return {}
    entry = container.get(key)
    if not isinstance(entry, dict):
        entry = {}
    entry.setdefault("multiplier", 1.0)
    entry.setdefault("wins", 0)
    entry.setdefault("losses", 0)
    entry.setdefault("last_seen_at", "")
    container[key] = entry
    return entry


def resolve_multiplier(item: Dict, trust_payload: Dict) -> Tuple[float, str]:
    """优先按 source 命中，其次按 domain 回退。返回 (multiplier, key_used)。"""

    source_name = str(item.get("source", "")).strip()
    domain = extract_domain(item)
    sources = trust_payload.get("sources") if isinstance(trust_payload.get("sources"), dict) else {}
    domains = trust_payload.get("domains") if isinstance(trust_payload.get("domains"), dict) else {}

    if source_name and isinstance(sources.get(source_name), dict):
        entry = sources[source_name]
        return float(entry.get("multiplier", 1.0) or 1.0), f"source:{source_name}"

    if domain and isinstance(domains.get(domain), dict):
        entry = domains[domain]
        return float(entry.get("multiplier", 1.0) or 1.0), f"domain:{domain}"

    return 1.0, ""


def parse_ai_raw_score(item: Dict) -> float:
    direct = item.get("ai_raw_score")
    if direct is not None:
        return parse_score(direct)
    fallback = item.get("score")
    score = parse_score(fallback)
    # 兼容旧版 5-10 评分；新体系 score=ai_raw_score(0-100)。
    if 0 < score <= 10:
        return score * 10
    return score


def compute_final_score(ai_raw_score: float, adjustment_hint: float, multiplier: float) -> float:
    base = ai_raw_score
    adjusted = base + adjustment_hint
    return adjusted * multiplier


def update_trust_after_finalize(
    *,
    trust_payload: Dict,
    winners: List[Dict],
    losers: List[Dict],
) -> Dict:
    sources = trust_payload.get("sources") if isinstance(trust_payload.get("sources"), dict) else {}
    domains = trust_payload.get("domains") if isinstance(trust_payload.get("domains"), dict) else {}
    now = iso_now()

    def apply_delta(item: Dict, *, delta: float, win: bool) -> None:
        source_name = str(item.get("source", "")).strip()
        domain = extract_domain(item)
        if source_name:
            entry = _ensure_trust_entry(sources, source_name)
            if entry:
                entry["multiplier"] = clamp(float(entry.get("multiplier", 1.0) or 1.0) + delta, TRUST_MULTIPLIER_MIN, TRUST_MULTIPLIER_MAX)
                entry["wins"] = int(entry.get("wins", 0) or 0) + (1 if win else 0)
                entry["losses"] = int(entry.get("losses", 0) or 0) + (0 if win else 1)
                entry["last_seen_at"] = now

        if domain:
            entry = _ensure_trust_entry(domains, domain)
            if entry:
                entry["multiplier"] = clamp(float(entry.get("multiplier", 1.0) or 1.0) + delta, TRUST_MULTIPLIER_MIN, TRUST_MULTIPLIER_MAX)
                entry["wins"] = int(entry.get("wins", 0) or 0) + (1 if win else 0)
                entry["losses"] = int(entry.get("losses", 0) or 0) + (0 if win else 1)
                entry["last_seen_at"] = now

    for item in winners:
        apply_delta(item, delta=TRUST_WIN_DELTA, win=True)
    for item in losers:
        apply_delta(item, delta=-TRUST_LOSS_DELTA, win=False)

    trust_payload["version"] = TRUST_FILE_VERSION
    trust_payload["updated_at"] = now
    trust_payload["sources"] = sources
    trust_payload["domains"] = domains
    return trust_payload


def empty_history_payload() -> Dict:
    return {
        "version": HISTORY_FILE_VERSION,
        "updated_at": iso_now(),
        "items": [],
    }


def ensure_history_file(history_path: Path) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    if history_path.exists():
        return
    history_path.write_text(
        json.dumps(empty_history_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_history(history_path: Path) -> Dict:
    ensure_history_file(history_path)
    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception:
        payload = empty_history_payload()
        history_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    if not isinstance(payload, dict):
        payload = empty_history_payload()

    items = payload.get("items")
    if not isinstance(items, list):
        items = []

    normalized_items: List[Dict] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item_title = re.sub(r"\s+", " ", str(raw.get("title", ""))).strip()
        item_original_title = re.sub(r"\s+", " ", str(raw.get("original_title", ""))).strip()
        title_basis = item_original_title or item_title
        item_link = str(raw.get("link", "")).strip()
        normalized_items.append(
            {
                "dedupe_key": str(raw.get("dedupe_key", "")).strip() or dedupe_key(title_basis, item_link),
                "title_hash": str(raw.get("title_hash", "")).strip() or title_hash(title_basis),
                "link": item_link,
                "title": item_title,
                "original_title": item_original_title,
                "source": str(raw.get("source", "")).strip(),
                "category": str(raw.get("category", "")).strip(),
                "last_seen_at": str(raw.get("last_seen_at", "")).strip(),
                "report_date": str(raw.get("report_date", "")).strip(),
            }
        )

    payload["version"] = payload.get("version") or HISTORY_FILE_VERSION
    payload["updated_at"] = str(payload.get("updated_at", "")).strip() or iso_now()
    payload["items"] = normalized_items
    return payload


def build_history_entry(item: Dict, report_date: str) -> Dict:
    title = re.sub(r"\s+", " ", str(item.get("title", ""))).strip()
    original_title = re.sub(r"\s+", " ", str(item.get("original_title", ""))).strip()
    title_basis = original_title or title
    link = str(item.get("link", "")).strip()
    return {
        "dedupe_key": dedupe_key(title_basis, link),
        "title_hash": title_hash(title_basis),
        "link": link,
        "title": title,
        "original_title": original_title,
        "source": str(item.get("source", "")).strip(),
        "category": str(item.get("category", "")).strip(),
        "last_seen_at": iso_now(),
        "report_date": report_date,
    }


def upsert_history_items(history_path: Path, items: List[Dict], report_date: str) -> Dict:
    payload = load_history(history_path)
    history_items = list(payload.get("items", []))
    dedupe_index = {}
    title_hash_index = {}

    for index, entry in enumerate(history_items):
        if entry.get("dedupe_key"):
            dedupe_index[entry["dedupe_key"]] = index
        if entry.get("title_hash"):
            title_hash_index[entry["title_hash"]] = index

    added_count = 0
    updated_count = 0

    for item in items:
        history_entry = build_history_entry(item, report_date)
        matched_index = dedupe_index.get(history_entry["dedupe_key"])
        if matched_index is None and history_entry.get("title_hash"):
            matched_index = title_hash_index.get(history_entry["title_hash"])

        if matched_index is None:
            history_items.append(history_entry)
            matched_index = len(history_items) - 1
            added_count += 1
        else:
            history_items[matched_index].update(history_entry)
            updated_count += 1

        dedupe_index[history_entry["dedupe_key"]] = matched_index
        if history_entry.get("title_hash"):
            title_hash_index[history_entry["title_hash"]] = matched_index

    payload["version"] = HISTORY_FILE_VERSION
    payload["updated_at"] = iso_now()
    payload["items"] = history_items
    history_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "added_count": added_count,
        "updated_count": updated_count,
        "written_count": len(items),
        "total_count": len(history_items),
    }


def classify_section(item: Dict) -> str:
    topics = set(as_list(item.get("topics")))
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    topics.update(as_list(extra.get("priority_topics")))
    category = str(item.get("category", "")).strip().lower()

    if topics & T0_TOPICS or category in {"quant-research", "us-stocks"}:
        return "量化与美股方向"
    if topics & T1_TOPICS or category in {"ai-lab", "ai-tools"}:
        return "AI方向"
    return "工具与开源方向"


def normalize_digest(item: Dict) -> str:
    for key in ("digest", "summary_text", "ai_summary", "brief"):
        text = " ".join(str(item.get(key, "")).split()).strip()
        if text:
            return text
    return ""


def infer_tag(item: Dict) -> str:
    explicit = str(item.get("tag", "")).strip()
    if explicit:
        return explicit

    category = str(item.get("category", "")).strip().lower()
    if category in TAG_FALLBACK_BY_CATEGORY:
        return TAG_FALLBACK_BY_CATEGORY[category]

    topics = set(as_list(item.get("topics")))
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    topics.update(as_list(extra.get("priority_topics")))
    if "交易策略与市场信号" in topics:
        return "交易信号"
    if topics & {"美股市场（US Stocks）", "美股交易（US Stocks）"}:
        return "美股市场"
    if topics & {"量化交易（Quant）", "量化投资（Quant）"}:
        return "量化研究"
    if topics & {"AI 产品落地", "AI 行业实践", "AI 工作流应用", "AI技术"}:
        return "AI产品"
    return "行业动态"


def normalize_item(item: Dict, original_index: int, trust_payload: Dict) -> Dict:
    """保留函数名以便局部复用（本质为带 trust 的规范化）。"""
    return normalize_item_with_trust(item, original_index, trust_payload)


def normalize_item_with_trust(item: Dict, original_index: int, trust_payload: Dict) -> Dict:
    normalized = dict(item)
    normalized["topics"] = as_list(item.get("topics"))

    ai_raw_score = parse_ai_raw_score(item)
    normalized["ai_raw_score"] = ai_raw_score
    # 兼容字段：下游若仍读 score，则直接等于 ai_raw_score。
    normalized["score"] = ai_raw_score

    normalized["domain"] = extract_domain(normalized)
    multiplier, _ = resolve_multiplier(normalized, trust_payload)
    normalized["source_trust_multiplier"] = float(multiplier)
    normalized["digest"] = normalize_digest(normalized)
    normalized["tag"] = infer_tag(normalized)
    normalized["section_title"] = str(item.get("section_title", "")).strip() or classify_section(normalized)

    adjustment_hint = parse_adjustment(item)
    normalized["_score_adjustment_hint"] = adjustment_hint
    normalized["final_score"] = compute_final_score(ai_raw_score, adjustment_hint, float(multiplier))
    normalized["_ranking_score"] = normalized["final_score"]
    normalized["_is_low_score_rejected"] = ai_raw_score < LOW_SCORE_THRESHOLD
    normalized["_original_index"] = original_index
    return normalized


def flatten_items(payload: Dict, trust_payload: Dict) -> List[Dict]:
    if isinstance(payload.get("items"), list):
        return [normalize_item_with_trust(item, index, trust_payload) for index, item in enumerate(payload.get("items", []))]

    items: List[Dict] = []
    original_index = 0
    for section in payload.get("sections", []):
        section_title = str(section.get("title", "")).strip()
        for item in section.get("items", []):
            normalized = normalize_item_with_trust(item, original_index, trust_payload)
            if section_title:
                normalized["section_title"] = section_title
            items.append(normalized)
            original_index += 1
    return items


def finalize_payload(payload: Dict, trust_payload: Dict, max_items: int = MAX_SELECTED_ITEMS) -> Tuple[Dict, Dict, Dict]:
    all_items = flatten_items(payload, trust_payload)
    all_items.sort(
        key=lambda item: (
            -item["final_score"],
            -item["ai_raw_score"],
            SECTION_PRIORITY.get(item["section_title"], 99),
            item["_original_index"],
        ),
    )
    selected_items = all_items[:max_items]

    selected_uids = {str(item.get("link", "")).strip().lower() or str(item.get("_original_index")) for item in selected_items}
    rejected_low_score = [
        item
        for item in all_items
        if (str(item.get("link", "")).strip().lower() or str(item.get("_original_index"))) not in selected_uids
        and bool(item.get("_is_low_score_rejected"))
    ]

    finalized_items: List[Dict] = []
    for rank, item in enumerate(selected_items, start=1):
        cleaned = {key: value for key, value in item.items() if not key.startswith("_")}
        cleaned["rank"] = rank
        finalized_items.append(cleaned)

    trust_updated = update_trust_after_finalize(
        trust_payload=trust_payload,
        winners=[{key: value for key, value in item.items() if not key.startswith("_")} for item in selected_items],
        losers=[{key: value for key, value in item.items() if not key.startswith("_")} for item in rejected_low_score],
    )

    finalized_payload = {
        "report_date": payload.get("report_date", ""),
        "scan_scope": payload.get("scan_scope", "AI、Quant、US Stocks、开发工具、开源仓库"),
        "meta": {
            "max_selected_items": max_items,
            "selected_item_count": len(finalized_items),
            "input_item_count": len(all_items),
            "trust_selected_win_count": len(selected_items),
            "trust_rejected_low_score_count": len(rejected_low_score),
        },
        "items": finalized_items,
    }

    trust_stats = {
        "selected_top_count": len(selected_items),
        "rejected_low_score_count": len(rejected_low_score),
    }

    return finalized_payload, trust_updated, trust_stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="对 Todayradar 精选结果执行排序封顶并输出扁平 JSON")
    parser.add_argument("--input", required=True, help="输入 JSON 文件路径")
    parser.add_argument("--output", required=True, help="输出 JSON 文件路径")
    parser.add_argument("--max-items", type=int, default=MAX_SELECTED_ITEMS, help="最终最多保留多少条，默认 10")
    parser.add_argument(
        "--history-file",
        default=DEFAULT_HISTORY_FILE,
        help="跨频次历史去重文件，默认 assets/history_seen_urls.json",
    )
    parser.add_argument(
        "--trust-file",
        default=DEFAULT_TRUST_FILE,
        help="信源信任度状态文件，默认 assets/sources_trust.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    history_path = Path(args.history_file)
    trust_path = Path(args.trust_file)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    trust_payload = load_sources_trust(trust_path)
    finalized, trust_updated, trust_stats = finalize_payload(
        payload,
        trust_payload,
        max_items=max(1, args.max_items),
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(finalized, ensure_ascii=False, indent=2), encoding="utf-8")

    trust_path.write_text(json.dumps(trust_updated, ensure_ascii=False, indent=2), encoding="utf-8")

    history_stats = upsert_history_items(
        history_path,
        finalized.get("items", []),
        report_date=str(finalized.get("report_date", "")).strip(),
    )
    print(
        f"已生成 {output_path}，输入 {finalized['meta']['input_item_count']} 条，最终保留 {finalized['meta']['selected_item_count']} 条；"
        f"历史写回 {history_stats['written_count']} 条（新增 {history_stats['added_count']}，更新 {history_stats['updated_count']}），"
        f"历史总量 {history_stats['total_count']} 条；"
        f"trust +{trust_stats['selected_top_count']}（Top） -{trust_stats['rejected_low_score_count']}（低分）。"
    )


if __name__ == "__main__":
    main()
