#!/usr/bin/env python3
"""Two-stage runner for the AI Headlines pipeline."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_HISTORY_FILE = Path("assets/history_seen_urls.json")
DEFAULT_TRUST_FILE = Path("assets/sources_trust.json")
DEFAULT_LARK_CONFIG = Path("assets/lark_message_config.json")


class PipelineError(RuntimeError):
    def __init__(self, stage: str, message: str):
        self.stage = stage
        super().__init__(message)


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_step(stage: str, args: List[str]) -> None:
    print(f"[{stage}] {' '.join(args)}")
    completed = subprocess.run(args, text=True, check=False)
    if completed.returncode != 0:
        raise PipelineError(stage, f"stage failed with exit code {completed.returncode}")


def read_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_status(path: Path, status: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def default_paths(output_dir: Path) -> Dict[str, Path]:
    return {
        "raw": output_dir / "raw_news_today.json",
        "candidates": output_dir / "candidates.json",
        "decisions": output_dir / "decisions.json",
        "draft": output_dir / "selected_news_draft.json",
        "selected": output_dir / "selected_news.json",
        "with_assets": output_dir / "selected_news_with_assets.json",
        "images_dir": output_dir / "images",
        "card": output_dir / "ai_headlines_digest.card.json",
        "resolved_card": output_dir / "ai_headlines_digest.card.resolved.json",
        "status": output_dir / "run_status.json",
    }


def prepare(args: argparse.Namespace, paths: Dict[str, Path]) -> Dict[str, Any]:
    paths["raw"].parent.mkdir(parents=True, exist_ok=True)
    run_step(
        "fetch",
        [
            sys.executable,
            "fetcher.py",
            "--output",
            str(paths["raw"]),
            "--limit-per-source",
            str(args.limit_per_source),
            "--history-file",
            str(args.history_file),
            "--trust-file",
            str(args.trust_file),
        ],
    )
    run_step(
        "export_candidates",
        [
            sys.executable,
            "scripts/export_candidates.py",
            "--input",
            str(paths["raw"]),
            "--output",
            str(paths["candidates"]),
            "--max-items",
            str(args.max_candidates),
            "--excerpt-chars",
            str(args.excerpt_chars),
        ],
    )

    raw_payload = read_json(paths["raw"])
    candidates_payload = read_json(paths["candidates"])
    return {
        "ok": True,
        "stage": "prepare",
        "raw_file": str(paths["raw"]),
        "candidates_file": str(paths["candidates"]),
        "raw_stats": raw_payload.get("stats", {}),
        "candidate_count": len(candidates_payload.get("items", [])),
        "next_step": "Have the Agent read output/candidates.json and write output/decisions.json, then run finish.",
    }


def finish(args: argparse.Namespace, paths: Dict[str, Path]) -> Dict[str, Any]:
    if not paths["candidates"].exists():
        raise PipelineError(
            "candidates",
            f"{paths['candidates']} not found. Run prepare first to generate candidates.json.",
        )
    if not paths["decisions"].exists():
        raise PipelineError(
            "decisions",
            f"{paths['decisions']} not found. Run prepare first, then have the Agent write decisions.json.",
        )

    run_step(
        "apply_decisions",
        [
            sys.executable,
            "scripts/apply_decisions.py",
            "--candidates",
            str(paths["candidates"]),
            "--decisions",
            str(paths["decisions"]),
            "--output",
            str(paths["draft"]),
        ],
    )
    run_step(
        "finalize",
        [
            sys.executable,
            "scripts/finalize_digest.py",
            "--input",
            str(paths["draft"]),
            "--output",
            str(paths["selected"]),
            "--max-items",
            str(args.max_items),
            "--history-file",
            str(args.history_file),
            "--trust-file",
            str(args.trust_file),
        ],
    )

    if args.skip_images:
        paths["with_assets"].write_text(paths["selected"].read_text(encoding="utf-8"), encoding="utf-8")
        print(f"[images] skipped; copied {paths['selected']} -> {paths['with_assets']}")
    else:
        run_step(
            "resolve_images",
            [
                sys.executable,
                "scripts/resolve_article_images.py",
                "--input",
                str(paths["selected"]),
                "--output",
                str(paths["with_assets"]),
                "--assets-dir",
                str(paths["images_dir"]),
            ],
        )

    run_step(
        "render_lark",
        [
            sys.executable,
            "scripts/render_lark_digest.py",
            "--input",
            str(paths["with_assets"]),
            "--output",
            str(paths["card"]),
        ],
    )

    send_result: Dict[str, Any] = {"skipped": True}
    if not args.skip_send and not args.dry_run:
        send_args = [
            sys.executable,
            "scripts/send_lark_message.py",
            "--draft-file",
            str(paths["card"]),
            "--config",
            str(args.lark_config),
            "--resolved-output",
            str(paths["resolved_card"]),
        ]
        if args.receiver_id:
            send_args.extend(["--receiver-id", args.receiver_id])
        if args.id_type:
            send_args.extend(["--id-type", args.id_type])
        if args.reply_message_id:
            send_args.extend(["--reply-message-id", args.reply_message_id])
        run_step("send_lark", send_args)
        send_result = {"skipped": False, "platform": "feishu"}

    selected_payload = read_json(paths["selected"])
    return {
        "ok": True,
        "stage": "finish",
        "draft_file": str(paths["draft"]),
        "selected_file": str(paths["selected"]),
        "with_assets_file": str(paths["with_assets"]),
        "card_file": str(paths["card"]),
        "selected_count": selected_payload.get("meta", {}).get("selected_item_count", len(selected_payload.get("items", []))),
        "send": send_result,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AI Headlines pipeline in prepare/finish stages")
    parser.add_argument(
        "command",
        choices=["prepare", "finish", "all"],
        help="prepare exports candidates; finish applies decisions and renders/sends; all runs prepare then finish if decisions exists",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--history-file", type=Path, default=DEFAULT_HISTORY_FILE)
    parser.add_argument("--trust-file", type=Path, default=DEFAULT_TRUST_FILE)
    parser.add_argument("--lark-config", type=Path, default=DEFAULT_LARK_CONFIG)
    parser.add_argument("--limit-per-source", type=int, default=8)
    parser.add_argument("--max-candidates", type=int, default=50)
    parser.add_argument("--excerpt-chars", type=int, default=900)
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true", help="Run without sending messages")
    parser.add_argument("--skip-send", action="store_true", help="Render output but do not send")
    parser.add_argument("--skip-images", action="store_true", help="Skip image resolution and reuse selected JSON")
    parser.add_argument("--receiver-id", default="")
    parser.add_argument("--id-type", default="")
    parser.add_argument("--reply-message-id", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    paths = default_paths(args.output_dir)
    status: Dict[str, Any] = {
        "ok": False,
        "command": args.command,
        "started_at": iso_now(),
    }

    try:
        if args.command == "prepare":
            status.update(prepare(args, paths))
        elif args.command == "finish":
            status.update(finish(args, paths))
        else:
            status["prepare"] = prepare(args, paths)
            if not paths["decisions"].exists():
                status.update(
                    {
                        "ok": False,
                        "stage": "awaiting_decisions",
                        "candidates_file": str(paths["candidates"]),
                        "decisions_file": str(paths["decisions"]),
                        "next_step": "Have the Agent write output/decisions.json, then run finish.",
                    }
                )
                return
            status["finish"] = finish(args, paths)
            status["ok"] = True
            status["stage"] = "all"
    except PipelineError as exc:
        status.update({"ok": False, "stage": exc.stage, "error": str(exc)})
        raise SystemExit(1)
    finally:
        status["finished_at"] = iso_now()
        write_status(paths["status"], status)
        print(json.dumps(status, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
