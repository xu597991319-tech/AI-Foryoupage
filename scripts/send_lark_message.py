#!/usr/bin/env python3
"""将 Todayradar 卡片草稿发送到飞书聊天或话题。"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

CONFIG_RELATIVE_PATH = Path("assets/lark_message_config.json")
DEFAULT_HEADER_TEMPLATE = "blue"
MAX_DIGEST_LENGTH = 120


def detect_workspace_root(start: Path) -> Path:
    env_root = os.environ.get("IRIS_WORKSPACE_PATH")
    if env_root:
        return Path(env_root)
    for candidate in [start, *start.parents]:
        if (candidate / "inner_skills" / "feishu-im-send").exists():
            return candidate
    raise RuntimeError("未找到 workspace 根目录，无法定位 inner_skills/feishu-im-send")


def compact_text(text: str) -> str:
    return re.sub(r"\s+", "", text or "")


def visible_length(text: str) -> int:
    return len(compact_text(text))


def load_config(script_dir: Path, config_path_arg: str) -> Dict[str, Any]:
    if config_path_arg:
        config_path = Path(config_path_arg)
        if not config_path.is_absolute():
            config_path = (Path.cwd() / config_path).resolve()
    else:
        config_path = script_dir.parent / CONFIG_RELATIVE_PATH

    if not config_path.exists():
        return {}
    return json.loads(config_path.read_text(encoding="utf-8"))


def run_command(args: List[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        args,
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            "命令执行失败：{}\nstdout:\n{}\nstderr:\n{}".format(
                " ".join(args),
                completed.stdout,
                completed.stderr,
            )
        )
    return completed


def parse_json_from_stdout(stdout: str) -> Optional[Any]:
    text = (stdout or "").strip()
    if not text:
        return None
    candidates = [text, *reversed(text.splitlines())]
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate:
            continue
        if candidate.startswith("[RESULT]"):
            candidate = candidate.split("[RESULT]", 1)[1].strip()
        try:
            return json.loads(candidate)
        except Exception:
            continue
    return None


def parse_result_field(stdout: str, field_name: str) -> str:
    parsed = parse_json_from_stdout(stdout)
    candidate_fields = [field_name]
    if field_name in {"image_key", "file_key"}:
        candidate_fields.append("resource_key")

    if isinstance(parsed, dict):
        for candidate in candidate_fields:
            value = str(parsed.get(candidate, "")).strip()
            if value:
                return value

    patterns = []
    for candidate in candidate_fields:
        patterns.extend(
            [
                rf'"{re.escape(candidate)}"\s*:\s*"([^"]+)"',
                rf"'{re.escape(candidate)}'\s*:\s*'([^']+)'",
                rf"{re.escape(candidate)}\s*[:=]\s*([A-Za-z0-9_\-]+)",
            ]
        )
    for pattern in patterns:
        match = re.search(pattern, stdout)
        if match:
            return match.group(1).strip()
    raise RuntimeError(f"未能从输出中解析 {field_name}：{stdout}")


def upload_image(im_send_script: Path, image_path: Path) -> str:
    if not image_path.exists():
        raise FileNotFoundError(f"图片不存在：{image_path}")
    completed = run_command([
        sys.executable,
        str(im_send_script),
        "upload",
        str(image_path),
        "image",
    ])
    return parse_result_field(completed.stdout, "image_key")


def create_card(im_send_script: Path, card_payload_path: Path) -> str:
    completed = run_command([
        sys.executable,
        str(im_send_script),
        "create_card",
        str(card_payload_path),
    ])
    return parse_result_field(completed.stdout, "card_id")


def resolve_image_path(draft_file: Path, image_path: str) -> Path:
    candidate = Path(image_path)
    if candidate.is_absolute():
        return candidate
    return (draft_file.parent / candidate).resolve()


def determine_receiver(args: argparse.Namespace, config: Dict[str, Any]) -> Tuple[str, str]:
    receiver_id_type = (args.id_type or config.get("receiver_id_type") or "email").strip()
    receiver_id = (args.receiver_id or config.get("receiver_id") or "").strip()

    if not receiver_id and receiver_id_type == "email":
        receiver_id = os.environ.get("AIME_CURRENT_USER_EMAIL", "").strip()

    if not receiver_id:
        raise RuntimeError("未提供接收者；请通过参数、配置文件或当前用户邮箱补齐")
    return receiver_id, receiver_id_type


def normalize_draft(draft: Dict[str, Any]) -> Dict[str, Any]:
    msg_type = str(draft.get("msg_type", "")).strip().lower()
    if msg_type != "interactive":
        raise RuntimeError("当前脚本仅支持发送 interactive 卡片草稿，请先重新运行 render_lark_digest.py")

    items = draft.get("items")
    if not isinstance(items, list) or not items:
        raise RuntimeError("卡片草稿缺少 items，无法构建卡片")

    normalized_items: List[Dict[str, Any]] = []
    for index, item in enumerate(items, start=1):
        digest = " ".join(str(item.get("digest", "")).split()).strip()
        if not digest:
            raise RuntimeError(f"第 {index} 条资讯缺少 digest")
        if visible_length(digest) > MAX_DIGEST_LENGTH:
            raise RuntimeError(f"第 {index} 条资讯 digest 超过 {MAX_DIGEST_LENGTH} 个非空白字符：{digest}")
        normalized_items.append(
            {
                "rank": int(item.get("rank") or index),
                "tag": str(item.get("tag", "")).strip() or "行业动态",
                "digest": digest,
                "link": str(item.get("link", "")).strip(),
                "image_path": str(item.get("image_path", "")).strip(),
                "image_alt": str(item.get("image_alt", item.get("title", "资讯配图"))).strip() or "资讯配图",
            }
        )

    normalized_items.sort(key=lambda item: item["rank"])
    return {
        "report_date": str(draft.get("report_date", "")).strip(),
        "header_title": str(draft.get("header_title", "")).strip(),
        "header_template": str(draft.get("header_template", "")).strip() or DEFAULT_HEADER_TEMPLATE,
        "meta": dict(draft.get("meta", {})),
        "items": normalized_items,
    }


def upload_images_for_items(draft_file: Path, items: List[Dict[str, Any]], im_send_script: Path) -> List[Dict[str, Any]]:
    resolved_items: List[Dict[str, Any]] = []
    for item in items:
        normalized = dict(item)
        image_path = str(item.get("image_path", "")).strip()
        if image_path:
            normalized["image_key"] = upload_image(im_send_script, resolve_image_path(draft_file, image_path))
        resolved_items.append(normalized)
    return resolved_items


def build_card_dsl(report_date: str, header_title: str, header_template: str, items: List[Dict[str, Any]]) -> Dict[str, Any]:
    title = header_title or (f"Todayradar 每日精选 | {report_date}" if report_date else "Todayradar 每日精选")
    elements: List[Dict[str, Any]] = []

    for index, item in enumerate(items):
        summary = f"{item['rank']}. 【{item['tag']}】{item['digest']}"
        elements.append(
            {
                "tag": "div",
                "text": {
                    "tag": "plain_text",
                    "content": summary,
                },
            }
        )
        if item.get("link"):
            elements.append(
                {
                    "tag": "markdown",
                    "content": f"[查看原文]({item['link']})",
                }
            )
        if item.get("image_key"):
            elements.append(
                {
                    "tag": "img",
                    "img_key": item["image_key"],
                    "mode": "fit_horizontal",
                }
            )
        if index < len(items) - 1:
            elements.append({"tag": "hr"})

    return {
        "name": "TodayradarDigestCard",
        "dsl": {
            "schema": "2.0",
            "header": {
                "title": {
                    "tag": "plain_text",
                    "content": title,
                },
                "template": header_template or DEFAULT_HEADER_TEMPLATE,
            },
            "body": {
                "elements": elements,
            },
        },
    }


def send_card_message(
    im_send_script: Path,
    im_manage_script: Path,
    receiver_id: str,
    receiver_id_type: str,
    reply_message_id: str,
    card_id: str,
) -> Dict[str, Any]:
    if reply_message_id:
        payload = {
            "message_id": reply_message_id,
            "msg_type": "interactive",
            "content": card_id,
            "reply_in_thread": True,
        }
        completed = run_command([
            sys.executable,
            str(im_manage_script),
            "reply_message",
            json.dumps(payload, ensure_ascii=False),
        ])
        parsed = parse_json_from_stdout(completed.stdout)
        return parsed if isinstance(parsed, dict) else {"stdout": completed.stdout.strip()}

    args = [
        sys.executable,
        str(im_send_script),
        "send",
        receiver_id,
        "interactive",
        card_id,
    ]
    if receiver_id_type:
        args.append(f"--id-type={receiver_id_type}")
    completed = run_command(args)
    parsed = parse_json_from_stdout(completed.stdout)
    return parsed if isinstance(parsed, dict) else {"stdout": completed.stdout.strip()}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="把 Todayradar 卡片草稿发送到飞书聊天或话题")
    parser.add_argument("--draft-file", required=True, help="render_lark_digest.py 生成的交互式卡片草稿 JSON 路径")
    parser.add_argument("--receiver-id", default="", help="接收者标识；默认读取配置或当前用户邮箱")
    parser.add_argument("--id-type", default="", help="接收者类型，默认 email")
    parser.add_argument("--reply-message-id", default="", help="若传入 message_id，则回复到对应飞书话题")
    parser.add_argument("--config", default="", help="发送配置文件路径；默认读取 assets/lark_message_config.json")
    parser.add_argument("--resolved-output", default="", help="上传图片并组装完成后的 card JSON 输出路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    workspace_root = detect_workspace_root(script_dir)
    feishu_skill_dir = workspace_root / "inner_skills" / "feishu-im-send"
    im_send_script = feishu_skill_dir / "scripts" / "im_send.py"
    im_manage_script = feishu_skill_dir / "scripts" / "im_manage.py"

    draft_file = Path(args.draft_file).resolve()
    draft = json.loads(draft_file.read_text(encoding="utf-8"))
    normalized_draft = normalize_draft(draft)

    config = load_config(script_dir, args.config)
    receiver_id, receiver_id_type = determine_receiver(args, config)
    reply_message_id = (args.reply_message_id or config.get("reply_message_id") or "").strip()

    resolved_output = args.resolved_output.strip()
    if resolved_output:
        resolved_output_path = Path(resolved_output)
        if not resolved_output_path.is_absolute():
            resolved_output_path = (Path.cwd() / resolved_output_path).resolve()
    else:
        resolved_output_path = draft_file.with_name(f"{draft_file.stem}.resolved.card.json")

    resolved_items = upload_images_for_items(draft_file, normalized_draft["items"], im_send_script)
    card_payload = build_card_dsl(
        report_date=normalized_draft["report_date"],
        header_title=normalized_draft["header_title"],
        header_template=normalized_draft["header_template"],
        items=resolved_items,
    )

    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(
        json.dumps(card_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    card_id = create_card(im_send_script, resolved_output_path)
    send_result = send_card_message(
        im_send_script=im_send_script,
        im_manage_script=im_manage_script,
        receiver_id=receiver_id,
        receiver_id_type=receiver_id_type,
        reply_message_id=reply_message_id,
        card_id=card_id,
    )

    result = {
        "receiver_id": receiver_id,
        "receiver_id_type": receiver_id_type,
        "reply_message_id": reply_message_id,
        "card_id": card_id,
        "card_payload_path": str(resolved_output_path),
        "send_result": send_result,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
