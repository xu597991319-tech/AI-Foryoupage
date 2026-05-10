#!/usr/bin/env python3
"""Apply Agent decisions to candidates and produce selected_news_draft.json."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_CANDIDATES = "output/candidates.json"
DEFAULT_DECISIONS = "output/decisions.json"
DEFAULT_OUTPUT = "output/selected_news_draft.json"


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def parse_score(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def selected_items(decisions: Dict[str, Any]) -> List[Dict[str, Any]]:
    for key in ("items", "selected_items", "decisions"):
        value = decisions.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def resolve_decision_score(decision: Dict[str, Any]) -> float:
    for key in ("final_score", "ai_raw_score", "score"):
        if key in decision:
            return parse_score(decision.get(key))
    weighted_keys = {
        "daily_priority": 0.35,
        "information_gain": 0.25,
        "portfolio_value": 0.25,
        "attention_return": 0.15,
    }
    if any(key in decision for key in weighted_keys):
        return sum(parse_score(decision.get(key)) * weight for key, weight in weighted_keys.items())
    return 0.0


def pick_text(decision: Dict[str, Any], candidate: Dict[str, Any], *keys: str) -> str:
    for key in keys:
        if key in decision and str(decision.get(key, "")).strip():
            return str(decision[key]).strip()
    for key in keys:
        if key in candidate and str(candidate.get(key, "")).strip():
            return str(candidate[key]).strip()
    return ""


def build_item(
    decision: Dict[str, Any],
    candidate: Dict[str, Any],
    *,
    rank: int,
) -> Dict[str, Any]:
    score = resolve_decision_score(decision)
    brief_text = pick_text(decision, candidate, "brief_text", "digest", "summary_zh", "summary")
    tag = pick_text(decision, candidate, "tag") or "行业动态"
    title = pick_text(decision, candidate, "title", "title_zh") or brief_text[:40]
    image_prompt = pick_text(decision, candidate, "image_prompt")
    cover_image_url = pick_text(decision, candidate, "cover_image_url")

    extra = {
        "candidate_id": candidate.get("candidate_id"),
        "source_type": candidate.get("source_type", ""),
        "published_at": candidate.get("published_at", ""),
        "priority_tier": candidate.get("priority_tier", ""),
        "priority_topics": candidate.get("priority_topics", []),
        "priority_score_floor": candidate.get("priority_score_floor"),
        "score_adjustment_hint": candidate.get("score_adjustment_hint"),
        "suggested_score_ceiling": candidate.get("suggested_score_ceiling"),
        "daily_priority": decision.get("daily_priority"),
        "information_gain": decision.get("information_gain"),
        "portfolio_value": decision.get("portfolio_value"),
        "attention_return": decision.get("attention_return"),
        "ranking_reasons": decision.get("ranking_reasons", []),
        "ranking_penalties": decision.get("ranking_penalties", []),
        "final_gate": decision.get("pass_final_gate", True),
        "final_reject_reason": decision.get("final_reject_reason", ""),
    }
    extra = {key: value for key, value in extra.items() if value not in (None, "", [])}

    item = {
        "rank": int(decision.get("rank") or rank),
        "title": title,
        "original_title": candidate.get("original_title") or candidate.get("title", ""),
        "score": score,
        "ai_raw_score": score,
        "source": candidate.get("source", ""),
        "category": candidate.get("category", ""),
        "link": candidate.get("link", ""),
        "topics": as_list(decision.get("topics")) or as_list(candidate.get("priority_topics")),
        "tag": tag,
        "digest": brief_text,
        "brief_text": brief_text,
        "cover_image_url": cover_image_url,
        "image_prompt": image_prompt,
        "extra": extra,
    }
    return {key: value for key, value in item.items() if value not in (None, "", [])}


def apply_decisions(candidates: Dict[str, Any], decisions: Dict[str, Any]) -> Dict[str, Any]:
    candidate_items = candidates.get("items") if isinstance(candidates.get("items"), list) else []
    by_id = {
        str(item.get("candidate_id", "")).strip(): item
        for item in candidate_items
        if isinstance(item, dict) and str(item.get("candidate_id", "")).strip()
    }

    output_items: List[Dict[str, Any]] = []
    missing_ids: List[str] = []

    for rank, decision in enumerate(selected_items(decisions), start=1):
        if decision.get("pass_final_gate") is False:
            continue
        candidate_id = str(decision.get("candidate_id") or decision.get("id") or "").strip()
        candidate = by_id.get(candidate_id)
        if not candidate:
            missing_ids.append(candidate_id or f"<missing:{rank}>")
            continue
        output_items.append(build_item(decision, candidate, rank=rank))

    return {
        "report_date": decisions.get("report_date") or candidates.get("report_date", ""),
        "scan_scope": decisions.get("scan_scope") or candidates.get("scan_scope", ""),
        "meta": {
            "candidate_count": len(candidate_items),
            "decision_count": len(selected_items(decisions)),
            "selected_item_count": len(output_items),
            "missing_candidate_ids": missing_ids,
        },
        "items": output_items,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply Agent decisions to exported candidates")
    parser.add_argument("--candidates", default=DEFAULT_CANDIDATES, help=f"Candidates JSON, default {DEFAULT_CANDIDATES}")
    parser.add_argument("--decisions", default=DEFAULT_DECISIONS, help=f"Decisions JSON, default {DEFAULT_DECISIONS}")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"Output draft JSON, default {DEFAULT_OUTPUT}")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    candidates_path = Path(args.candidates)
    decisions_path = Path(args.decisions)
    output_path = Path(args.output)

    candidates = json.loads(candidates_path.read_text(encoding="utf-8-sig"))
    decisions = json.loads(decisions_path.read_text(encoding="utf-8-sig"))
    draft = apply_decisions(candidates, decisions)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(draft, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    missing = draft["meta"]["missing_candidate_ids"]
    suffix = f"; missing candidates: {', '.join(missing)}" if missing else ""
    print(f"wrote {output_path} ({draft['meta']['selected_item_count']} selected{suffix})")


if __name__ == "__main__":
    main()
