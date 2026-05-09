#!/usr/bin/env python3
"""兼容入口：转发到 Todayradar 飞书消息发送脚本。"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="兼容旧入口：改为发送飞书消息，不再追加飞书文档")
    parser.add_argument("--content-file", required=True, help="现改为接收 Post 草稿 JSON 文件路径")
    parser.add_argument("--receiver-id", default="", help="接收者标识")
    parser.add_argument("--id-type", default="", help="接收者类型")
    parser.add_argument("--reply-message-id", default="", help="若传入 message_id，则回复到对应话题")
    parser.add_argument("--config", default="", help="发送配置文件路径")
    parser.add_argument("--resolved-output", default="", help="最终 Post JSON 输出路径")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    send_script = script_dir / "send_lark_message.py"

    command = [
        sys.executable,
        str(send_script),
        "--draft-file",
        str(Path(args.content_file).resolve()),
    ]
    if args.receiver_id:
        command.extend(["--receiver-id", args.receiver_id])
    if args.id_type:
        command.extend(["--id-type", args.id_type])
    if args.reply_message_id:
        command.extend(["--reply-message-id", args.reply_message_id])
    if args.config:
        command.extend(["--config", args.config])
    if args.resolved_output:
        command.extend(["--resolved-output", args.resolved_output])

    completed = subprocess.run(command, check=False)
    raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
