#!/usr/bin/env python3
"""Validate AI Headlines source catalog files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from source_validation import summarize, validate_sources_catalog

DEFAULT_SOURCES = "assets/sources_catalog.json"
DEFAULT_EXAMPLE = "assets/sources_catalog.example.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AI Headlines source catalog")
    parser.add_argument("--sources", type=Path, default=Path(DEFAULT_SOURCES))
    parser.add_argument("--example", type=Path, default=Path(DEFAULT_EXAMPLE))
    parser.add_argument("--json", action="store_true")
    return parser.parse_args()


def print_human(result: dict) -> None:
    print("AI Headlines source validation")
    print(f"status: {'OK' if result['ok'] else 'FAILED'}")
    print(f"errors: {result['error_count']}, warnings: {result['warning_count']}")
    for item in result["checks"]:
        if item["ok"]:
            continue
        label = "ERROR" if item["severity"] == "error" else "WARN"
        detail = f" — {item['detail']}" if item.get("detail") else ""
        print(f"[{label}] {item['name']}{detail}")


def main() -> None:
    args = parse_args()
    checks = []
    checks.extend(validate_sources_catalog(args.example, str(args.example)))
    if args.sources.exists():
        checks.extend(validate_sources_catalog(args.sources, str(args.sources)))
    result = summarize(checks)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human(result)
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
