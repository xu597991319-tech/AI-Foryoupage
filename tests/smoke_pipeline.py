#!/usr/bin/env python3
"""Smoke test the local AI Headlines artifact pipeline without network access."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run(args: list[str]) -> None:
    completed = subprocess.run(args, cwd=ROOT, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(args)}")


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        raw = tmpdir / "raw_news.json"
        candidates = tmpdir / "candidates.json"
        decisions = tmpdir / "decisions.json"
        draft = tmpdir / "selected_news_draft.json"
        selected = tmpdir / "selected_news.json"
        digest = tmpdir / "digest.json"
        html = tmpdir / "digest.html"
        history = tmpdir / "history.json"
        trust = tmpdir / "trust.json"

        raw.write_text((ROOT / "examples/raw_news.example.json").read_text(encoding="utf-8"), encoding="utf-8")
        decisions.write_text((ROOT / "examples/decisions.example.json").read_text(encoding="utf-8"), encoding="utf-8")

        run([sys.executable, "scripts/export_candidates.py", "--input", str(raw), "--output", str(candidates)])
        run([sys.executable, "scripts/apply_decisions.py", "--candidates", str(candidates), "--decisions", str(decisions), "--output", str(draft)])
        run([sys.executable, "scripts/finalize_digest.py", "--input", str(draft), "--output", str(selected), "--history-file", str(history), "--trust-file", str(trust)])
        run([sys.executable, "scripts/build_digest.py", "--input", str(selected), "--output", str(digest)])
        run([sys.executable, "scripts/render_html_digest.py", "--input", str(digest), "--output", str(html)])

        digest_payload = json.loads(digest.read_text(encoding="utf-8"))
        assert digest_payload["items"], "digest should contain items"
        assert html.exists() and html.stat().st_size > 0, "HTML digest should be written"
        print(f"smoke ok: {len(digest_payload['items'])} items")


if __name__ == "__main__":
    main()
