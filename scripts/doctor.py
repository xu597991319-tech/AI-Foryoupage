#!/usr/bin/env python3
"""Read-only environment and configuration checks for AI Headlines."""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

REQUIRED_MODULES = {
    "bs4": "beautifulsoup4",
    "aiohttp": "aiohttp",
    "feedparser": "feedparser",
    "requests": "requests",
}

REQUIRED_FILES = [
    "SKILL.md",
    "README.md",
    "requirements.txt",
    "fetcher.py",
    "assets/content_packs.json",
    "assets/user_profile.example.json",
    "assets/push_schedule.example.json",
    "assets/delivery.example.json",
    "assets/sources_catalog.example.json",
    "scripts/run_ai_headlines_pipeline.py",
    "scripts/export_candidates.py",
    "scripts/apply_decisions.py",
    "scripts/update_preferences.py",
    "scripts/finalize_digest.py",
    "scripts/render_lark_digest.py",
]

OPTIONAL_USER_FILES = [
    "assets/user_profile.json",
    "assets/push_schedule.json",
    "assets/delivery.json",
    "assets/sources_catalog.json",
]

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


def check_python() -> Dict[str, Any]:
    version = sys.version_info
    ok = version.major == 3 and version.minor >= 10
    return check(ok, "python_version", f"{version.major}.{version.minor}.{version.micro}")


def check_modules() -> List[Dict[str, Any]]:
    results = []
    for module, package in REQUIRED_MODULES.items():
        exists = importlib.util.find_spec(module) is not None
        hint = "" if exists else f"missing module '{module}', install with: python -m pip install -r requirements.txt"
        results.append(check(exists, f"dependency:{package}", hint))
    return results


def check_files(root: Path) -> List[Dict[str, Any]]:
    results = []
    for rel in REQUIRED_FILES:
        path = root / rel
        results.append(check(path.exists(), f"required_file:{rel}", "missing required project file"))
    for rel in OPTIONAL_USER_FILES:
        path = root / rel
        results.append(
            check(
                path.exists(),
                f"user_file:{rel}",
                "missing; onboarding or first setup may create it",
                severity="warning",
            )
        )
    return results


def validate_content_packs(root: Path) -> List[Dict[str, Any]]:
    path = root / "assets/content_packs.json"
    if not path.exists():
        return [check(False, "content_packs", "assets/content_packs.json missing")]
    try:
        payload = read_json(path)
    except Exception as exc:  # noqa: BLE001
        return [check(False, "content_packs", f"invalid JSON: {exc}")]

    packs = payload.get("packs")
    if not isinstance(packs, list):
        return [check(False, "content_packs", "`packs` must be a list")]

    ids = [str(pack.get("id", "")).strip() for pack in packs if isinstance(pack, dict)]
    duplicate_ids = sorted({pack_id for pack_id in ids if ids.count(pack_id) > 1})
    results = [
        check(bool(ids), "content_packs:not_empty", f"{len(ids)} packs"),
        check(not duplicate_ids, "content_packs:unique_ids", f"duplicates: {duplicate_ids}"),
    ]
    return results


def validate_sources_catalog(root: Path, rel_path: str) -> List[Dict[str, Any]]:
    path = root / rel_path
    if not path.exists():
        return [check(False, f"sources_catalog:{rel_path}", "missing", severity="warning")]
    try:
        payload = read_json(path)
    except Exception as exc:  # noqa: BLE001
        return [check(False, f"sources_catalog:{rel_path}", f"invalid JSON: {exc}")]

    sources = payload.get("sources")
    if not isinstance(sources, list):
        return [check(False, f"sources_catalog:{rel_path}", "`sources` must be a list")]

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
    results.insert(0, check(not duplicate_ids, f"sources_catalog:{rel_path}:unique_ids", f"duplicates: {duplicate_ids}"))
    results.insert(0, check(bool(sources), f"sources_catalog:{rel_path}:not_empty", f"{len(sources)} sources"))
    return results


def check_output_dir(root: Path) -> Dict[str, Any]:
    path = root / "output"
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".doctor_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return check(True, "output_writable", str(path))
    except Exception as exc:  # noqa: BLE001
        return check(False, "output_writable", str(exc))


def run_doctor(root: Path) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    checks.append(check_python())
    checks.extend(check_modules())
    checks.extend(check_files(root))
    checks.extend(validate_content_packs(root))
    checks.extend(validate_sources_catalog(root, "assets/sources_catalog.example.json"))
    if (root / "assets/sources_catalog.json").exists():
        checks.extend(validate_sources_catalog(root, "assets/sources_catalog.json"))
    checks.append(check_output_dir(root))

    errors = [item for item in checks if not item["ok"] and item["severity"] == "error"]
    warnings = [item for item in checks if not item["ok"] and item["severity"] == "warning"]
    return {
        "ok": not errors,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "checks": checks,
    }


def print_human(result: Dict[str, Any]) -> None:
    print("AI Headlines doctor")
    print(f"status: {'OK' if result['ok'] else 'FAILED'}")
    print(f"errors: {result['error_count']}, warnings: {result['warning_count']}")
    for item in result["checks"]:
        if item["ok"]:
            continue
        label = "ERROR" if item["severity"] == "error" else "WARN"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{label}] {item['name']}{detail}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check AI Headlines environment and local config")
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true", help="Print full JSON result")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result = run_doctor(args.root.resolve())
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human(result)
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
