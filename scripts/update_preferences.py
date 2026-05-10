#!/usr/bin/env python3
"""Safely apply Agent-interpreted preference updates."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_PATCH = "output/preference_patch.json"
DEFAULT_PROFILE = "assets/user_profile.json"
DEFAULT_PROFILE_EXAMPLE = "assets/user_profile.example.json"
DEFAULT_SCHEDULE = "assets/push_schedule.json"
DEFAULT_SCHEDULE_EXAMPLE = "assets/push_schedule.example.json"
DEFAULT_DELIVERY = "assets/delivery.json"
DEFAULT_DELIVERY_EXAMPLE = "assets/delivery.example.json"
DEFAULT_SOURCES = "assets/sources_catalog.json"
DEFAULT_SOURCES_EXAMPLE = "assets/sources_catalog.example.json"

TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def unique_extend(existing: Any, additions: Any) -> List[str]:
    result = as_list(existing)
    seen = {item.lower(): item for item in result}
    for item in as_list(additions):
        key = item.lower()
        if key not in seen:
            result.append(item)
            seen[key] = item
    return result


def remove_items(existing: Any, removals: Any) -> List[str]:
    remove_set = {item.lower() for item in as_list(removals)}
    return [item for item in as_list(existing) if item.lower() not in remove_set]


def read_json_or_example(path: Path, example_path: Path) -> Dict[str, Any]:
    source = path if path.exists() else example_path
    if not source.exists():
        return {"version": 1}
    return json.loads(source.read_text(encoding="utf-8-sig"))


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at"] = iso_now()
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_local_sources(path: Path, example_path: Path) -> Dict[str, Any]:
    payload = read_json_or_example(path, example_path)
    if not path.exists() and example_path.exists():
        write_json(path, payload)
    return payload


def update_profile(profile: Dict[str, Any], patch: Dict[str, Any], changes: List[str]) -> Dict[str, Any]:
    if "selected_packs_add" in patch:
        profile["selected_packs"] = unique_extend(profile.get("selected_packs"), patch["selected_packs_add"])
        changes.append(f"added packs: {', '.join(as_list(patch['selected_packs_add']))}")
    if "selected_packs_remove" in patch:
        profile["selected_packs"] = remove_items(profile.get("selected_packs"), patch["selected_packs_remove"])
        changes.append(f"removed packs: {', '.join(as_list(patch['selected_packs_remove']))}")
    if "include_keywords_add" in patch or "include_keywords" in patch:
        additions = patch.get("include_keywords_add", patch.get("include_keywords"))
        profile["include_keywords"] = unique_extend(profile.get("include_keywords"), additions)
        changes.append(f"added include keywords: {', '.join(as_list(additions))}")
    if "include_keywords_remove" in patch:
        profile["include_keywords"] = remove_items(profile.get("include_keywords"), patch["include_keywords_remove"])
        changes.append(f"removed include keywords: {', '.join(as_list(patch['include_keywords_remove']))}")
    if "exclude_keywords_add" in patch or "exclude_keywords" in patch:
        additions = patch.get("exclude_keywords_add", patch.get("exclude_keywords"))
        profile["exclude_keywords"] = unique_extend(profile.get("exclude_keywords"), additions)
        changes.append(f"added exclude keywords: {', '.join(as_list(additions))}")
    if "exclude_keywords_remove" in patch:
        profile["exclude_keywords"] = remove_items(profile.get("exclude_keywords"), patch["exclude_keywords_remove"])
        changes.append(f"removed exclude keywords: {', '.join(as_list(patch['exclude_keywords_remove']))}")
    if "language" in patch:
        language = str(patch["language"]).strip()
        if language:
            profile["language"] = language
            changes.append(f"set language: {language}")
    if "max_items" in patch:
        max_items = int(patch["max_items"])
        profile["max_items"] = max(1, min(20, max_items))
        changes.append(f"set max_items: {profile['max_items']}")
    profile["onboarding_completed"] = bool(profile.get("onboarding_completed", True))
    profile.setdefault("version", 1)
    return profile


def update_schedule(schedule: Dict[str, Any], patch: Dict[str, Any], changes: List[str]) -> Dict[str, Any]:
    push_time = str(patch.get("push_time", "")).strip()
    if push_time:
        if not TIME_RE.match(push_time):
            raise ValueError(f"Invalid push_time '{push_time}', expected HH:mm")
        schedule["time"] = push_time
        schedule["mode"] = "single_time"
        schedule["enabled"] = True
        changes.append(f"set push time: {push_time}")
    if "timezone" in patch:
        timezone_value = str(patch["timezone"]).strip()
        if timezone_value:
            schedule["timezone"] = timezone_value
            schedule["timezone_source"] = "user_requested"
            changes.append(f"set timezone: {timezone_value}")
    if "schedule_enabled" in patch:
        schedule["enabled"] = bool(patch["schedule_enabled"])
        changes.append(f"set schedule enabled: {schedule['enabled']}")
    schedule.setdefault("version", 1)
    schedule.setdefault("mode", "single_time")
    return schedule


def update_delivery(delivery: Dict[str, Any], patch: Dict[str, Any], changes: List[str]) -> Dict[str, Any]:
    if "delivery_platforms" in patch or "preferred_platforms" in patch:
        platforms = as_list(patch.get("delivery_platforms", patch.get("preferred_platforms")))
        if platforms:
            delivery["preferred_platforms"] = platforms
            delivery["setup_status"] = "pending_agent_resolution"
            changes.append(f"set delivery platforms: {', '.join(platforms)}")
    if "fallback_platforms" in patch:
        fallbacks = as_list(patch["fallback_platforms"])
        delivery["fallback_platforms"] = fallbacks
        changes.append(f"set fallback platforms: {', '.join(fallbacks)}")
    delivery.setdefault("version", 1)
    delivery.setdefault("resolved_channels", [])
    return delivery


def update_sources(sources: Dict[str, Any], patch: Dict[str, Any], changes: List[str]) -> Dict[str, Any]:
    raw_sources = sources.get("sources")
    if not isinstance(raw_sources, list):
        return sources

    enable_ids = set(as_list(patch.get("enable_sources")))
    disable_ids = set(as_list(patch.get("disable_sources")))
    boost_ids = set(as_list(patch.get("boost_sources")))
    downrank_ids = set(as_list(patch.get("downrank_sources")))

    for source in raw_sources:
        if not isinstance(source, dict):
            continue
        source_id = str(source.get("id", "")).strip()
        if not source_id:
            continue
        if source_id in enable_ids:
            source["enabled"] = True
        if source_id in disable_ids:
            source["enabled"] = False
        if source_id in boost_ids:
            source["user_preference"] = "boost"
        if source_id in downrank_ids:
            source["user_preference"] = "downrank"

    if enable_ids:
        changes.append(f"enabled sources: {', '.join(sorted(enable_ids))}")
    if disable_ids:
        changes.append(f"disabled sources: {', '.join(sorted(disable_ids))}")
    if boost_ids:
        changes.append(f"boosted sources: {', '.join(sorted(boost_ids))}")
    if downrank_ids:
        changes.append(f"downranked sources: {', '.join(sorted(downrank_ids))}")

    sources.setdefault("version", 1)
    return sources


def apply_patch(args: argparse.Namespace) -> Dict[str, Any]:
    patch_path = Path(args.patch)
    patch = json.loads(patch_path.read_text(encoding="utf-8-sig"))
    changes: List[str] = []

    profile_path = Path(args.profile)
    schedule_path = Path(args.schedule)
    delivery_path = Path(args.delivery)
    sources_path = Path(args.sources)

    profile = read_json_or_example(profile_path, Path(args.profile_example))
    schedule = read_json_or_example(schedule_path, Path(args.schedule_example))
    delivery = read_json_or_example(delivery_path, Path(args.delivery_example))
    sources = ensure_local_sources(sources_path, Path(args.sources_example))

    profile = update_profile(profile, patch, changes)
    schedule = update_schedule(schedule, patch, changes)
    delivery = update_delivery(delivery, patch, changes)
    sources = update_sources(sources, patch, changes)

    if not args.dry_run:
        write_json(profile_path, profile)
        write_json(schedule_path, schedule)
        write_json(delivery_path, delivery)
        write_json(sources_path, sources)

    return {
        "ok": True,
        "dry_run": bool(args.dry_run),
        "patch_file": str(patch_path),
        "changes": changes,
        "files": {
            "profile": str(profile_path),
            "schedule": str(schedule_path),
            "delivery": str(delivery_path),
            "sources": str(sources_path),
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely update AI Headlines user preferences from an Agent patch")
    parser.add_argument("--patch", default=DEFAULT_PATCH, help=f"Patch JSON file, default {DEFAULT_PATCH}")
    parser.add_argument("--profile", default=DEFAULT_PROFILE)
    parser.add_argument("--profile-example", default=DEFAULT_PROFILE_EXAMPLE)
    parser.add_argument("--schedule", default=DEFAULT_SCHEDULE)
    parser.add_argument("--schedule-example", default=DEFAULT_SCHEDULE_EXAMPLE)
    parser.add_argument("--delivery", default=DEFAULT_DELIVERY)
    parser.add_argument("--delivery-example", default=DEFAULT_DELIVERY_EXAMPLE)
    parser.add_argument("--sources", default=DEFAULT_SOURCES)
    parser.add_argument("--sources-example", default=DEFAULT_SOURCES_EXAMPLE)
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = apply_patch(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
