"""Shared source catalog validation helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

VALID_SOURCE_TYPES = {"rss", "github_repo"}
VALID_SOURCE_ROLES = {"anchor", "expert", "discovery", "candidate"}
VALID_FEED_MODES = {"core", "discovery"}


def check(ok: bool, name: str, detail: str = "", severity: str = "error") -> Dict[str, Any]:
    return {
        "ok": bool(ok),
        "name": name,
        "detail": "" if ok else detail,
        "severity": "ok" if ok else severity,
    }


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate_sources_catalog(path: Path, label: str | None = None) -> List[Dict[str, Any]]:
    label = label or str(path)
    if not path.exists():
        return [check(False, f"sources_catalog:{label}", "missing", severity="warning")]
    try:
        payload = read_json(path)
    except Exception as exc:  # noqa: BLE001
        return [check(False, f"sources_catalog:{label}", f"invalid JSON: {exc}")]

    sources = payload.get("sources")
    if not isinstance(sources, list):
        return [check(False, f"sources_catalog:{label}", "`sources` must be a list")]

    results: List[Dict[str, Any]] = []
    ids = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            results.append(check(False, f"source:{index}", "source must be an object"))
            continue
        source_id = str(source.get("id", "")).strip()
        ids.append(source_id)
        prefix = f"source:{source_id or index}"
        source_type = str(source.get("type", "")).strip()
        source_role = str(source.get("source_role", "")).strip()
        feed_mode = str(source.get("feed_mode", "")).strip()
        packs = source.get("packs")
        results.append(check(bool(source_id), f"{prefix}:id", "missing id"))
        results.append(check(source_type in VALID_SOURCE_TYPES, f"{prefix}:type", f"type={source_type}"))
        results.append(check(source_role in VALID_SOURCE_ROLES, f"{prefix}:source_role", f"role={source_role}", severity="warning"))
        results.append(check(feed_mode in VALID_FEED_MODES, f"{prefix}:feed_mode", f"mode={feed_mode}", severity="warning"))
        results.append(check(isinstance(packs, list) and bool(packs), f"{prefix}:packs", "packs should be a non-empty list", severity="warning"))
        if source_type == "rss":
            results.append(check(bool(str(source.get("url", "")).strip()), f"{prefix}:url", "missing rss url"))
        elif source_type == "github_repo":
            owner = str(source.get("owner", "")).strip()
            repo = str(source.get("repo", "")).strip()
            results.append(check(bool(owner and repo), f"{prefix}:repo", "github_repo needs owner and repo"))

    duplicate_ids = sorted({source_id for source_id in ids if source_id and ids.count(source_id) > 1})
    results.insert(0, check(not duplicate_ids, f"sources_catalog:{label}:unique_ids", f"duplicates: {duplicate_ids}"))
    results.insert(0, check(bool(sources), f"sources_catalog:{label}:not_empty", f"{len(sources)} sources"))
    return results


def summarize(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    errors = [item for item in results if not item["ok"] and item["severity"] == "error"]
    warnings = [item for item in results if not item["ok"] and item["severity"] == "warning"]
    return {
        "ok": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "checks": results,
    }
