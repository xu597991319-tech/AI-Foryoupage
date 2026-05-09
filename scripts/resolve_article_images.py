#!/usr/bin/env python3
"""为 AI Headlines 的扁平精选结果补齐本地图片资产。"""

from __future__ import annotations

import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple
from urllib.parse import urlparse

import requests

REQUEST_TIMEOUT = 30
USER_AGENT = "AI-Headlines-image-resolver/1.0"
CONTENT_TYPE_EXTENSION = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
    "image/avif": ".avif",
}
SECTION_BY_CATEGORY = {
    "ai-lab": "AI方向",
    "ai-tools": "AI方向",
    "quant-research": "量化与美股方向",
    "us-stocks": "量化与美股方向",
    "developer-news": "工具与开源方向",
}



def as_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []



def iter_items(payload: Dict) -> Iterable[Tuple[int, Dict]]:
    if isinstance(payload.get("items"), list):
        for index, item in enumerate(payload.get("items", []), start=1):
            yield index, item
        return

    index = 0
    for section in payload.get("sections", []):
        section_title = str(section.get("title", "")).strip()
        for item in section.get("items", []):
            index += 1
            normalized = dict(item)
            if section_title and not str(normalized.get("section_title", "")).strip():
                normalized["section_title"] = section_title
            yield index, normalized



def infer_section_title(item: Dict) -> str:
    explicit = str(item.get("section_title", "")).strip()
    if explicit:
        return explicit

    category = str(item.get("category", "")).strip().lower()
    if category in SECTION_BY_CATEGORY:
        return SECTION_BY_CATEGORY[category]

    topics = set(as_list(item.get("topics")))
    if topics & {"量化投资（Quant）", "美股交易（US Stocks）"}:
        return "量化与美股方向"
    if "AI技术" in topics:
        return "AI方向"
    return "工具与开源方向"



def normalize_digest(item: Dict) -> str:
    for key in ("digest", "summary_text", "ai_summary", "brief"):
        text = " ".join(str(item.get(key, "")).split()).strip()
        if text:
            return text
    return ""



def build_file_stem(title: str, index: int) -> str:
    digest = hashlib.sha256(title.encode("utf-8")).hexdigest()[:10]
    return f"item-{index:02d}-{digest}"



def normalize_cover_url(item: Dict) -> str:
    direct_fields = [
        item.get("cover_image_url"),
        item.get("image_url"),
    ]
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    direct_fields.extend(
        [
            extra.get("cover_image_url"),
            extra.get("image_url"),
        ]
    )
    for candidate in direct_fields:
        url = str(candidate or "").strip()
        if url.startswith(("http://", "https://")):
            return url
    return ""



def build_fallback_prompt(item: Dict) -> str:
    title = str(item.get("title", "这则资讯")).strip()
    section_title = infer_section_title(item)
    digest_text = normalize_digest(item)
    if section_title == "量化与美股方向":
        topic_hint = "量化研究、美股市场和数据终端"
    elif section_title == "AI方向":
        topic_hint = "AI 模型、Agent 和工程工作流"
    else:
        topic_hint = "开发工具、开源协作和技术动态"
    detail = digest_text[:80] if digest_text else title
    return f"横版科技插画，极简高级感，突出{topic_hint}，核心主题是：{detail}，无文字，无水印，适合资讯配图。"



def guess_extension_from_url(url: str) -> str:
    parsed = urlparse(url)
    ext = Path(parsed.path).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}:
        return ext
    guessed, _ = mimetypes.guess_type(url)
    if guessed and guessed in CONTENT_TYPE_EXTENSION:
        return CONTENT_TYPE_EXTENSION[guessed]
    return ".png"



def guess_extension_from_content_type(content_type: str, fallback: str = ".png") -> str:
    lowered = (content_type or "").split(";")[0].strip().lower()
    return CONTENT_TYPE_EXTENSION.get(lowered, fallback)



def download_cover_image(session: requests.Session, url: str, destination_without_ext: Path) -> Path:
    response = session.get(url, timeout=REQUEST_TIMEOUT, stream=True)
    response.raise_for_status()
    content_type = response.headers.get("content-type", "")
    if "image" not in content_type.lower():
        raise ValueError(f"封面地址未返回图片内容：{url}")

    ext = guess_extension_from_content_type(content_type, fallback=guess_extension_from_url(url))
    destination = destination_without_ext.with_suffix(ext)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                file.write(chunk)
    return destination



def detect_workspace_root(start: Path) -> Path:
    env_root = os.environ.get("IRIS_WORKSPACE_PATH")
    if env_root:
        return Path(env_root)
    for candidate in [start, *start.parents]:
        if (candidate / "inner_skills").exists():
            return candidate
    raise RuntimeError("未找到 workspace 根目录，无法定位 inner_skills/image-generate")



def pick_generated_artifact(artifacts_dir: Path, before_snapshot: Dict[Path, float], stdout: str) -> Path:
    candidates = [path for path in artifacts_dir.glob("*") if path.is_file()]
    candidates.sort(key=lambda path: path.stat().st_mtime, reverse=True)
    for path in candidates:
        previous_mtime = before_snapshot.get(path)
        current_mtime = path.stat().st_mtime
        if previous_mtime is None or current_mtime > previous_mtime:
            return path

    for line in stdout.splitlines():
        match = re.search(r"([^\s]+\.(?:png|jpg|jpeg|webp|gif|avif))", line, re.IGNORECASE)
        if not match:
            continue
        candidate = Path(match.group(1))
        if not candidate.is_absolute():
            candidate = artifacts_dir.parent / candidate
        if candidate.exists() and candidate.is_file():
            return candidate

    raise RuntimeError("图片生成成功后未识别到新文件")



def generate_image_from_prompt(prompt: str, destination_without_ext: Path) -> Path:
    workspace_root = detect_workspace_root(Path.cwd())
    image_skill_dir = workspace_root / "inner_skills" / "image-generate"
    artifacts_dir = image_skill_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    before_snapshot = {path: path.stat().st_mtime for path in artifacts_dir.glob("*") if path.is_file()}

    command = [
        sys.executable,
        "script/image_generator.py",
        "--prompt",
        prompt,
        "--aspectratio",
        "16:9",
        "--resolution",
        "1k",
        "--mimetype",
        "image/png",
    ]
    completed = subprocess.run(
        command,
        cwd=image_skill_dir,
        check=True,
        text=True,
        capture_output=True,
    )

    generated_file = pick_generated_artifact(artifacts_dir, before_snapshot, completed.stdout)
    destination = destination_without_ext.with_suffix(generated_file.suffix or ".png")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(generated_file, destination)
    return destination



def resolve_images(payload: Dict, output_path: Path, assets_dir: Path) -> Dict:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    resolved_payload = dict(payload)
    resolved_items: List[Dict] = []
    image_errors: List[Dict] = []
    resolved_count = 0
    downloaded_count = 0
    generated_count = 0

    for item_index, item in iter_items(payload):
        resolved_item = dict(item)
        title = str(item.get("title", f"条目 {item_index}")).strip()
        file_stem = build_file_stem(title, item_index)
        destination_without_ext = assets_dir / file_stem
        cover_url = normalize_cover_url(item)
        image_prompt = str(item.get("image_prompt", "")).strip() or build_fallback_prompt(item)

        resolved_file: Path | None = None
        image_source = ""

        if cover_url:
            try:
                resolved_file = download_cover_image(session, cover_url, destination_without_ext)
                image_source = "fetched_cover"
                downloaded_count += 1
            except Exception as exc:  # noqa: BLE001
                image_errors.append(
                    {
                        "title": title,
                        "stage": "download_cover",
                        "error": str(exc),
                        "cover_image_url": cover_url,
                    }
                )

        if resolved_file is None:
            resolved_file = generate_image_from_prompt(image_prompt, destination_without_ext)
            image_source = "generated"
            generated_count += 1

        relative_image_path = os.path.relpath(resolved_file, output_path.parent)
        resolved_item["image_path"] = relative_image_path
        resolved_item["image_source"] = image_source
        resolved_item["image_prompt"] = image_prompt
        resolved_item["section_title"] = infer_section_title(resolved_item)
        if cover_url:
            resolved_item["cover_image_url"] = cover_url
        resolved_items.append(resolved_item)
        resolved_count += 1

    resolved_payload.pop("sections", None)
    resolved_payload["items"] = resolved_items
    meta = dict(resolved_payload.get("meta", {}))
    meta["image_item_count"] = resolved_count
    meta["downloaded_cover_count"] = downloaded_count
    meta["generated_image_count"] = generated_count
    meta["image_error_count"] = len(image_errors)
    resolved_payload["meta"] = meta
    if image_errors:
        resolved_payload["image_errors"] = image_errors
    return resolved_payload



def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="为 AI Headlines 精选结果补齐图片资产")
    parser.add_argument("--input", required=True, help="输入精选 JSON 文件")
    parser.add_argument("--output", required=True, help="输出带图片路径的 JSON 文件")
    parser.add_argument("--assets-dir", required=True, help="输出图片目录")
    return parser.parse_args()



def main() -> None:
    args = parse_args()
    input_path = Path(args.input)
    output_path = Path(args.output)
    assets_dir = Path(args.assets_dir)

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    resolved = resolve_images(payload, output_path=output_path, assets_dir=assets_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(resolved, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"已生成 {output_path}，图片共 {resolved['meta'].get('image_item_count', 0)} 张，"
        f"下载封面 {resolved['meta'].get('downloaded_cover_count', 0)} 张，"
        f"AI 生成 {resolved['meta'].get('generated_image_count', 0)} 张。"
    )


if __name__ == "__main__":
    main()
