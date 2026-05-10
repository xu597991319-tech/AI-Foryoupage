#!/usr/bin/env python3
"""抓取 RSS 与 GitHub 仓库动态，并输出标准化原始新闻数据。"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import html
import json
import re
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import aiohttp
import feedparser
import requests
from bs4 import BeautifulSoup

DEFAULT_SOURCE_CATALOG_FILE = "assets/sources_catalog.json"
DEFAULT_SOURCE_CATALOG_EXAMPLE_FILE = "assets/sources_catalog.example.json"

FALLBACK_RSS_SOURCES = [
    {
        "name": "OpenAI Blog",
        "url": "https://openai.com/news/rss.xml",
        "category": "ai-lab",
    },
    {
        "name": "Hugging Face Blog",
        "url": "https://huggingface.co/blog/feed.xml",
        "category": "ai-lab",
    },
    {
        "name": "Simon Willison",
        "url": "https://simonwillison.net/atom/everything/",
        "category": "ai-tools",
    },
    {
        "name": "Hacker News Frontpage",
        "url": "https://hnrss.org/frontpage",
        "category": "developer-news",
    },
    {
        "name": "QuantStart",
        "url": "https://www.quantstart.com/feed/",
        "category": "quant-research",
    },
    {
        "name": "Robot Wealth",
        "url": "https://robotwealth.com/feed/",
        "category": "quant-research",
    },
    {
        "name": "Qoppac",
        "url": "https://qoppac.blogspot.com/feeds/posts/default?alt=rss",
        "category": "quant-research",
    },
    {
        "name": "Jonathan Kinlay",
        "url": "https://jonathankinlay.com/feed/",
        "category": "quant-research",
    },
    {
        "name": "EP Chan Blog",
        "url": "https://epchan.blogspot.com/feeds/posts/default?alt=rss",
        "category": "quant-research",
    },
    {
        "name": "Reddit r/algotrading",
        "url": "https://www.reddit.com/r/algotrading/.rss",
        "category": "quant-research",
    },
    {
        "name": "Reddit r/quant",
        "url": "https://www.reddit.com/r/quant/.rss",
        "category": "quant-research",
    },
    {
        "name": "Seeking Alpha Latest Articles",
        "url": "https://seekingalpha.com/feed.xml",
        "category": "us-stocks",
    },
    {
        "name": "Seeking Alpha All News",
        "url": "https://seekingalpha.com/market_currents.xml",
        "category": "us-stocks",
    },
    {
        "name": "Seeking Alpha Wall Street Breakfast",
        "url": "https://seekingalpha.com/tag/wall-st-breakfast.xml",
        "category": "us-stocks",
    },
    {
        "name": "Seeking Alpha Long Ideas",
        "url": "https://seekingalpha.com/tag/long-ideas.xml",
        "category": "us-stocks",
    },
    {
        "name": "Seeking Alpha Financial",
        "url": "https://seekingalpha.com/sector/financial.xml",
        "category": "us-stocks",
    },
    {
        "name": "CXO Advisory",
        "url": "https://www.cxoadvisory.com/feed/",
        "category": "us-stocks",
    },
    {
        "name": "Nasdaq Markets",
        "url": "https://www.nasdaq.com/feed/rssoutbound?category=Markets",
        "category": "us-stocks",
    },
]

FALLBACK_GITHUB_REPOS = [
    {"owner": "openai", "repo": "openai-python", "branch": "main", "category": "ai-tools"},
    {"owner": "langchain-ai", "repo": "langchain", "branch": "master", "category": "ai-tools"},
    {"owner": "microsoft", "repo": "vscode", "branch": "main", "category": "developer-news"},
    {"owner": "microsoft", "repo": "qlib", "branch": "main", "category": "quant-research"},
    {"owner": "ranaroussi", "repo": "yfinance", "branch": "main", "category": "us-stocks"},
    {"owner": "stefan-jansen", "repo": "zipline-reloaded", "branch": "main", "category": "quant-research"},
    {"owner": "QuantConnect", "repo": "Lean", "branch": "master", "category": "quant-research"},
    {"owner": "polakowo", "repo": "vectorbt", "branch": "master", "category": "quant-research"},
]


def as_list(value) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _source_catalog_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.exists():
        return candidate
    fallback = Path(DEFAULT_SOURCE_CATALOG_EXAMPLE_FILE)
    if fallback.exists():
        return fallback
    return candidate


def load_source_catalog(path: str = DEFAULT_SOURCE_CATALOG_FILE) -> Tuple[List[Dict], List[Dict], Dict]:
    catalog_path = _source_catalog_path(path)
    if not catalog_path.exists():
        return FALLBACK_RSS_SOURCES, FALLBACK_GITHUB_REPOS, {
            "path": str(catalog_path),
            "used_fallback_constants": True,
            "version": 0,
        }

    try:
        payload = json.loads(catalog_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:  # noqa: BLE001
        return FALLBACK_RSS_SOURCES, FALLBACK_GITHUB_REPOS, {
            "path": str(catalog_path),
            "used_fallback_constants": True,
            "error": str(exc),
            "version": 0,
        }

    raw_sources = payload.get("sources") if isinstance(payload.get("sources"), list) else []
    rss_sources: List[Dict] = []
    github_repos: List[Dict] = []

    for raw in raw_sources:
        if not isinstance(raw, dict) or raw.get("enabled") is False:
            continue
        source_type = str(raw.get("type", "")).strip()
        base = {
            "id": str(raw.get("id", "")).strip(),
            "name": str(raw.get("name", "")).strip(),
            "category": str(raw.get("category", "")).strip() or "uncategorized",
            "content_type": str(raw.get("content_type", "")).strip(),
            "source_role": str(raw.get("source_role", "")).strip(),
            "feed_mode": str(raw.get("feed_mode", "")).strip(),
            "packs": as_list(raw.get("packs")),
        }
        if source_type == "rss":
            url = str(raw.get("url", "")).strip()
            if not url:
                continue
            rss_sources.append({**base, "url": url})
        elif source_type == "github_repo":
            owner = str(raw.get("owner", "")).strip()
            repo = str(raw.get("repo", "")).strip()
            if not owner or not repo:
                continue
            github_repos.append(
                {
                    **base,
                    "owner": owner,
                    "repo": repo,
                    "branch": str(raw.get("branch", "")).strip() or "main",
                    "name": base["name"] or f"GitHub/{owner}/{repo}",
                }
            )

    if not rss_sources and not github_repos:
        return FALLBACK_RSS_SOURCES, FALLBACK_GITHUB_REPOS, {
            "path": str(catalog_path),
            "used_fallback_constants": True,
            "version": payload.get("version", 1),
        }

    return rss_sources, github_repos, {
        "path": str(catalog_path),
        "used_fallback_constants": False,
        "version": payload.get("version", 1),
        "source_count": len(raw_sources),
    }

TIER_LABELS = {
    "T0": "T0（最高优先级）",
    "T1": "T1（高优先级）",
    "T2": "T2（中低优先级）",
}
TIER_RANK = {"T0": 3, "T1": 2, "T2": 1}

TIER_RULES = [
    {
        "tier": "T0",
        "label": "量化交易（Quant）",
        "categories": {"quant-research"},
        "source_types": {"rss"},
        "keywords": {
            "quant",
            "quantitative",
            "systematic trading",
            "factor",
            "alpha",
            "backtest",
            "portfolio",
            "portfolio optimization",
            "risk model",
            "signal generation",
            "statistical arbitrage",
            "mean reversion",
            "momentum",
            "execution model",
            "market microstructure",
        },
        "score_floor": 90,
        "reason": "RSS 条目命中量化交易核心方向，应优先审视。",
    },
    {
        "tier": "T0",
        "label": "美股市场（US Stocks）",
        "categories": {"us-stocks"},
        "source_types": {"rss"},
        "keywords": {
            "us stock",
            "us stocks",
            "equity market",
            "equities",
            "nasdaq",
            "nyse",
            "s&p 500",
            "etf",
            "earnings",
            "market data",
            "order flow",
            "options",
            "broker",
            "wall street",
            "financial sector",
        },
        "score_floor": 90,
        "reason": "RSS 条目命中美股市场核心方向，应优先审视。",
    },
    {
        "tier": "T0",
        "label": "交易策略与市场信号",
        "categories": {"quant-research", "us-stocks"},
        "source_types": {"rss"},
        "keywords": {
            "strategy",
            "signal",
            "trading signal",
            "alpha signal",
            "signal research",
            "pairs trade",
            "signal decay",
            "volatility",
            "volatility trading",
            "dispersion",
            "trend following",
            "cross-sectional",
            "intermarket",
            "event-driven",
        },
        "score_floor": 90,
        "reason": "RSS 条目直接涉及交易策略或市场信号，默认属于 T0 候选。",
    },
    {
        "tier": "T1",
        "label": "AI 产品落地",
        "categories": {"ai-tools"},
        "source_types": {"rss"},
        "keywords": {
            "assistant",
            "copilot",
            "workflow",
            "product",
            "launch",
            "deployment",
            "production",
            "enterprise",
            "customer",
            "agent",
            "tool calling",
            "automation",
            "integration",
        },
        "score_floor": 70,
        "reason": "命中 AI 产品落地方向，更适合优先评估。",
    },
    {
        "tier": "T1",
        "label": "AI 行业实践",
        "categories": {"ai-tools", "ai-lab"},
        "source_types": {"rss"},
        "keywords": {
            "case study",
            "real-world",
            "adoption",
            "workflow adoption",
            "business impact",
            "productivity",
            "team workflow",
            "operations",
            "customer support",
            "sales",
            "bank",
            "hospital",
        },
        "score_floor": 70,
        "reason": "命中 AI 行业实践方向，更适合优先评估。",
    },
    {
        "tier": "T1",
        "label": "AI 工作流应用",
        "categories": {"ai-tools", "ai-lab"},
        "source_types": {"rss"},
        "keywords": {
            "agent workflow",
            "multi-agent",
            "orchestration",
            "automation workflow",
            "tool use",
            "tooling",
            "reasoning workflow",
            "ai workflow",
            "ops workflow",
            "pipeline",
        },
        "score_floor": 70,
        "reason": "命中 AI 工作流应用方向，更适合优先评估。",
    },
]

DEVELOPER_TOOLS_T2 = {
    "priority_tier": "T2",
    "priority_topics": ["底层开发工具"],
    "score_adjustment_hint": -1.8,
    "suggested_score_ceiling": 64,
    "reason": "developer-news 默认按 T2 处理；只有出现明确重大突破时才允许上调。",
}

GITHUB_T2 = {
    "priority_tier": "T2",
    "priority_topics": ["GitHub 热门项目"],
    "score_adjustment_hint": -1.6,
    "suggested_score_ceiling": 65,
    "reason": "GitHub 条目默认按 T2 处理，即使仓库属于 Quant 或 US Stocks 方向，也不要仅因 category 命中就自动获得高分。",
}

USER_AGENT = "AI-Headlines-fetcher/4.0"
REQUEST_TIMEOUT = 20
DEFAULT_PER_SOURCE = 8
DEFAULT_HISTORY_FILE = "assets/history_seen_urls.json"
DEFAULT_TRUST_FILE = "assets/sources_trust.json"
HISTORY_FILE_VERSION = 1
MAX_ARTICLE_PARAGRAPHS = 5
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}

TRUST_FILE_VERSION = 1
TRUST_MULTIPLIER_BLOCK_THRESHOLD = 0.5

COARSE_LLM_TOP_N = 30
COARSE_MIN_SCORE = 0.52


def strip_html(text: Optional[str]) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", text)
    cleaned = html.unescape(cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def normalize_link(value: str) -> str:
    return (value or "").strip().lower()


def title_hash(title: str) -> str:
    normalized = re.sub(r"\s+", " ", (title or "")).strip().lower()
    return sha256_text(normalized) if normalized else ""


def dedupe_key(title: str, link: str) -> str:
    normalized_link = normalize_link(link)
    if normalized_link:
        return f"url:{normalized_link}"
    return f"title:{title_hash(title)}"


def iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def empty_trust_payload() -> Dict:
    return {
        "version": TRUST_FILE_VERSION,
        "updated_at": iso_now(),
        "sources": {},
        "domains": {},
    }


def ensure_sources_trust_file(trust_path: Path) -> None:
    trust_path.parent.mkdir(parents=True, exist_ok=True)
    if trust_path.exists():
        return
    trust_path.write_text(json.dumps(empty_trust_payload(), ensure_ascii=False, indent=2), encoding="utf-8")


def load_sources_trust(path: str) -> Dict:
    trust_path = Path(path)
    ensure_sources_trust_file(trust_path)
    try:
        payload = json.loads(trust_path.read_text(encoding="utf-8"))
    except Exception:
        payload = empty_trust_payload()
        trust_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    if not isinstance(payload, dict):
        payload = empty_trust_payload()

    payload["version"] = int(payload.get("version") or TRUST_FILE_VERSION)
    payload["updated_at"] = str(payload.get("updated_at", "")).strip() or iso_now()
    payload["sources"] = payload.get("sources") if isinstance(payload.get("sources"), dict) else {}
    payload["domains"] = payload.get("domains") if isinstance(payload.get("domains"), dict) else {}
    return payload


def extract_domain_from_url(value: str) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    try:
        parsed = urlparse(value)
    except Exception:
        return ""
    return (parsed.netloc or "").lower()


def get_source_multiplier(source_name: str, domain: str, trust_payload: Dict) -> float:
    sources = trust_payload.get("sources") if isinstance(trust_payload.get("sources"), dict) else {}
    domains = trust_payload.get("domains") if isinstance(trust_payload.get("domains"), dict) else {}

    source_name = (source_name or "").strip()
    domain = (domain or "").strip().lower()
    if source_name and isinstance(sources.get(source_name), dict):
        try:
            return float(sources[source_name].get("multiplier", 1.0) or 1.0)
        except Exception:
            return 1.0
    if domain and isinstance(domains.get(domain), dict):
        try:
            return float(domains[domain].get("multiplier", 1.0) or 1.0)
        except Exception:
            return 1.0
    return 1.0


def is_source_blocked(source_name: str, domain: str, trust_payload: Dict) -> bool:
    return get_source_multiplier(source_name, domain, trust_payload) < TRUST_MULTIPLIER_BLOCK_THRESHOLD


def shorten(text: str, limit: int = 400) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def unique_non_empty(values: Iterable[str]) -> List[str]:
    seen = set()
    results: List[str] = []
    for value in values:
        normalized = re.sub(r"\s+", " ", (value or "")).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        results.append(normalized)
    return results


def empty_history_payload() -> Dict:
    return {
        "version": HISTORY_FILE_VERSION,
        "updated_at": iso_now(),
        "items": [],
    }


def ensure_history_file(history_path: Path) -> None:
    history_path.parent.mkdir(parents=True, exist_ok=True)
    if history_path.exists():
        return
    history_path.write_text(
        json.dumps(empty_history_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_history(history_path: Path) -> Dict:
    ensure_history_file(history_path)
    try:
        payload = json.loads(history_path.read_text(encoding="utf-8"))
    except Exception:
        payload = empty_history_payload()
        history_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return payload

    if not isinstance(payload, dict):
        payload = empty_history_payload()

    items = payload.get("items")
    if not isinstance(items, list):
        items = []

    normalized_items: List[Dict] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        item_title = re.sub(r"\s+", " ", str(raw.get("title", ""))).strip()
        item_original_title = re.sub(r"\s+", " ", str(raw.get("original_title", ""))).strip()
        title_basis = item_original_title or item_title
        item_link = str(raw.get("link", "")).strip()
        normalized_items.append(
            {
                "dedupe_key": str(raw.get("dedupe_key", "")).strip() or dedupe_key(title_basis, item_link),
                "title_hash": str(raw.get("title_hash", "")).strip() or title_hash(title_basis),
                "link": item_link,
                "title": item_title,
                "original_title": item_original_title,
                "source": str(raw.get("source", "")).strip(),
                "category": str(raw.get("category", "")).strip(),
                "last_seen_at": str(raw.get("last_seen_at", "")).strip(),
                "report_date": str(raw.get("report_date", "")).strip(),
            }
        )

    payload["version"] = payload.get("version") or HISTORY_FILE_VERSION
    payload["updated_at"] = str(payload.get("updated_at", "")).strip() or iso_now()
    payload["items"] = normalized_items
    return payload


def build_history_indexes(history_payload: Dict) -> Dict[str, set]:
    seen_links = set()
    seen_title_hashes = set()
    seen_dedupe_keys = set()
    for item in history_payload.get("items", []):
        item_link = normalize_link(str(item.get("link", "")))
        item_title_hash = str(item.get("title_hash", "")).strip()
        item_dedupe_key = str(item.get("dedupe_key", "")).strip()
        if item_link:
            seen_links.add(item_link)
        if item_title_hash:
            seen_title_hashes.add(item_title_hash)
        if item_dedupe_key:
            seen_dedupe_keys.add(item_dedupe_key)
    return {
        "links": seen_links,
        "title_hashes": seen_title_hashes,
        "dedupe_keys": seen_dedupe_keys,
    }


def filter_history_seen(items: Iterable[Dict], history_payload: Dict) -> Tuple[List[Dict], int]:
    indexes = build_history_indexes(history_payload)
    filtered_items: List[Dict] = []
    filtered_count = 0

    for item in items:
        link_key = normalize_link(str(item.get("link", "")))
        title_key = title_hash(str(item.get("title", "")))
        item_dedupe_key = str(item.get("dedupe_key", "")).strip()
        if (
            (link_key and link_key in indexes["links"])
            or (title_key and title_key in indexes["title_hashes"])
            or (item_dedupe_key and item_dedupe_key in indexes["dedupe_keys"])
        ):
            filtered_count += 1
            continue
        filtered_items.append(item)

    return filtered_items, filtered_count


def extract_meta_content(soup: BeautifulSoup, selectors: List[Dict[str, str]]) -> str:
    for selector in selectors:
        node = soup.find("meta", attrs=selector)
        if not node:
            continue
        content = strip_html(node.get("content", ""))
        if content:
            return content
    return ""


def normalize_image_url(raw_url: str, page_url: str) -> str:
    candidate = (raw_url or "").strip()
    if not candidate:
        return ""
    if candidate.startswith("data:"):
        return ""
    if candidate.startswith("//"):
        parsed_page = urlparse(page_url)
        candidate = f"{parsed_page.scheme}:{candidate}"
    candidate = urljoin(page_url, candidate)
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"}:
        return ""
    return candidate


def looks_like_content_image(url: str) -> bool:
    if not url:
        return False
    lowered = url.lower()
    if any(flag in lowered for flag in ["sprite", "logo", "avatar", "favicon", "icon", "badge"]):
        return False
    if any(lowered.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return True
    if any(marker in lowered for marker in [".jpg?", ".jpeg?", ".png?", ".webp?", ".gif?", ".avif?"]):
        return True
    return True


def extract_meta_image_url(soup: BeautifulSoup, page_url: str) -> str:
    selectors = [
        {"property": "og:image"},
        {"property": "og:image:url"},
        {"name": "twitter:image"},
        {"name": "twitter:image:src"},
        {"itemprop": "image"},
    ]
    for selector in selectors:
        node = soup.find("meta", attrs=selector)
        if not node:
            continue
        candidate = normalize_image_url(node.get("content", ""), page_url)
        if looks_like_content_image(candidate):
            return candidate

    link_node = soup.find("link", attrs={"rel": re.compile(r"image_src", re.I)})
    if link_node:
        candidate = normalize_image_url(link_node.get("href", ""), page_url)
        if looks_like_content_image(candidate):
            return candidate
    return ""


def extract_first_image_url(soup: BeautifulSoup, page_url: str) -> str:
    search_roots = []
    for tag_name in ["article", "main"]:
        tag = soup.find(tag_name)
        if tag:
            search_roots.append(tag)
    if not search_roots:
        body = soup.find("body")
        if body:
            search_roots.append(body)

    for root in search_roots:
        for image in root.find_all("img"):
            candidate = normalize_image_url(
                image.get("src")
                or image.get("data-src")
                or image.get("data-original")
                or image.get("data-lazy-src")
                or "",
                page_url,
            )
            if looks_like_content_image(candidate):
                return candidate
    return ""


def extract_article_body(soup: BeautifulSoup) -> str:
    paragraphs: List[str] = []

    search_roots = []
    for tag_name in ["article", "main"]:
        tag = soup.find(tag_name)
        if tag:
            search_roots.append(tag)
    if not search_roots:
        body = soup.find("body")
        if body:
            search_roots.append(body)

    for root in search_roots:
        for paragraph in root.find_all("p"):
            text = strip_html(paragraph.get_text(" ", strip=True))
            if len(text) < 40:
                continue
            paragraphs.append(text)
            if len(paragraphs) >= MAX_ARTICLE_PARAGRAPHS:
                break
        if len(paragraphs) >= MAX_ARTICLE_PARAGRAPHS:
            break

    return "\n".join(unique_non_empty(paragraphs))


def prefer_richer_text(existing: str, enriched: str, *, min_existing_length: int) -> str:
    existing = (existing or "").strip()
    enriched = (enriched or "").strip()
    if not existing:
        return enriched
    if enriched and len(existing) < min_existing_length and len(enriched) > len(existing):
        return enriched
    return existing


def enrich_from_link(session: requests.Session, link: str) -> Dict[str, str]:
    if not link.startswith(("http://", "https://")):
        return {}

    response = session.get(link, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()

    content_type = response.headers.get("content-type", "")
    if "html" not in content_type.lower():
        return {}

    soup = BeautifulSoup(response.text, "html.parser")

    title = strip_html(soup.title.get_text(" ", strip=True) if soup.title else "")
    summary = extract_meta_content(
        soup,
        [
            {"name": "description"},
            {"property": "og:description"},
            {"name": "twitter:description"},
        ],
    )
    content = extract_article_body(soup)
    cover_image_url = extract_meta_image_url(soup, link) or extract_first_image_url(soup, link)

    return {
        "title": title,
        "summary": summary,
        "content": content,
        "cover_image_url": cover_image_url,
    }


def build_priority_metadata(*, source: str, source_type: str, category: str, title: str, summary: str, content: str) -> Dict:
    haystack = " ".join([source, category, title, summary, content]).lower()

    if source_type.startswith("github"):
        return {
            "priority_tier": GITHUB_T2["priority_tier"],
            "priority_tier_label": TIER_LABELS[GITHUB_T2["priority_tier"]],
            "priority_topics": GITHUB_T2["priority_topics"],
            "priority_reason": GITHUB_T2["reason"],
            "score_adjustment_hint": GITHUB_T2["score_adjustment_hint"],
            "suggested_score_ceiling": GITHUB_T2["suggested_score_ceiling"],
            "score_adjustment_reason": GITHUB_T2["reason"],
        }

    if category == "developer-news":
        return {
            "priority_tier": DEVELOPER_TOOLS_T2["priority_tier"],
            "priority_tier_label": TIER_LABELS[DEVELOPER_TOOLS_T2["priority_tier"]],
            "priority_topics": DEVELOPER_TOOLS_T2["priority_topics"],
            "priority_reason": DEVELOPER_TOOLS_T2["reason"],
            "score_adjustment_hint": DEVELOPER_TOOLS_T2["score_adjustment_hint"],
            "suggested_score_ceiling": DEVELOPER_TOOLS_T2["suggested_score_ceiling"],
            "score_adjustment_reason": DEVELOPER_TOOLS_T2["reason"],
        }

    topics: List[str] = []
    reasons: List[str] = []
    score_floor = 0
    best_tier = ""

    for rule in TIER_RULES:
        if source_type not in rule["source_types"]:
            continue
        category_hit = category in rule["categories"]
        keyword_hit = any(keyword in haystack for keyword in rule["keywords"])
        if not category_hit and not keyword_hit:
            continue
        topics.append(rule["label"])
        reasons.append(rule["reason"])
        score_floor = max(score_floor, int(rule["score_floor"]))
        if TIER_RANK[rule["tier"]] > TIER_RANK.get(best_tier, 0):
            best_tier = rule["tier"]

    metadata = {
        "priority_topics": unique_non_empty(topics),
        "priority_reason": "；".join(unique_non_empty(reasons)),
    }
    if best_tier:
        metadata["priority_tier"] = best_tier
        metadata["priority_tier_label"] = TIER_LABELS[best_tier]
    if score_floor:
        metadata["priority_score_floor"] = score_floor

    return metadata


def normalize_item(
    *,
    source: str,
    source_type: str,
    category: str,
    title: str,
    link: str,
    summary: str,
    content: str,
    published_at: str,
    extra: Optional[Dict] = None,
) -> Dict:
    extra = extra or {}
    key = dedupe_key(title=title, link=link)
    domain = extract_domain_from_url(link)
    return {
        "id": sha256_text(f"{source}|{source_type}|{key}")[:16],
        "source": source,
        "source_type": source_type,
        "category": category,
        "title": title.strip(),
        "link": link.strip(),
        "domain": domain,
        "summary": shorten(summary.strip()),
        "content": shorten(content.strip(), 1800),
        "published_at": published_at,
        "collected_at": iso_now(),
        "dedupe_key": key,
        "extra": extra,
    }


async def enrich_from_link_async(session: aiohttp.ClientSession, link: str) -> Dict[str, str]:
    if not link.startswith(("http://", "https://")):
        return {}
    try:
        async with session.get(link, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in (content_type or "").lower():
                return {}
            text = await response.text(errors="ignore")
    except Exception:
        return {}

    soup = BeautifulSoup(text, "html.parser")
    title = strip_html(soup.title.get_text(" ", strip=True) if soup.title else "")
    summary = extract_meta_content(
        soup,
        [
            {"name": "description"},
            {"property": "og:description"},
            {"name": "twitter:description"},
        ],
    )
    content = extract_article_body(soup)
    cover_image_url = extract_meta_image_url(soup, link) or extract_first_image_url(soup, link)
    return {
        "title": title,
        "summary": summary,
        "content": content,
        "cover_image_url": cover_image_url,
    }


async def fetch_rss_source(session: aiohttp.ClientSession, source: Dict, limit_per_source: int) -> List[Dict]:
    """并发抓取单个 RSS 源并标准化为 items。"""

    async with session.get(source["url"], timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)) as response:
        response.raise_for_status()
        content = await response.read()

    parsed = feedparser.parse(content)
    items: List[Dict] = []
    for entry in parsed.entries[:limit_per_source]:
        title = strip_html(getattr(entry, "title", "")) or "Untitled"
        link = getattr(entry, "link", "") or ""
        summary = resolve_entry_summary(entry)

        content_chunks: List[str] = []
        if getattr(entry, "content", None):
            for block in entry.content:
                content_chunks.append(strip_html(getattr(block, "value", "")))
        if not content_chunks and summary:
            content_chunks.append(summary)

        extra: Dict = {"feed_url": source["url"]}
        enriched: Dict[str, str] = {}
        should_enrich = bool(link) and (len(summary) < 60 or title == "Untitled")
        if should_enrich:
            enriched = await enrich_from_link_async(session, link)

        summary = prefer_richer_text(summary, enriched.get("summary", ""), min_existing_length=60)
        existing_content = "\n".join(part for part in content_chunks if part)
        preferred_content = prefer_richer_text(existing_content, enriched.get("content", ""), min_existing_length=180)
        content_text = preferred_content
        if title == "Untitled" and enriched.get("title"):
            title = enriched["title"]
        elif enriched.get("title") and len(title) < 12 and len(enriched["title"]) > len(title):
            title = enriched["title"]

        if enriched:
            extra["enriched_from_link"] = True
        if enriched.get("cover_image_url"):
            extra["cover_image_url"] = enriched["cover_image_url"]
            extra["cover_image_source"] = "source-page"

        extra.update(
            build_priority_metadata(
                source=source["name"],
                source_type="rss",
                category=source["category"],
                title=title,
                summary=summary,
                content=content_text,
            )
        )

        published_at = getattr(entry, "published", "") or getattr(entry, "updated", "") or ""
        items.append(
            normalize_item(
                source=source["name"],
                source_type="rss",
                category=source["category"],
                title=title,
                link=link,
                summary=summary,
                content=content_text,
                published_at=published_at,
                extra=extra,
            )
        )
    return items


_LAST_RSS_ERRORS: List[Dict] = []


async def fetch_all_rss(sources: List[Dict], limit_per_source: int) -> List[Dict]:
    """并发抓取所有 RSS 源。错误信息可通过模块变量 `_LAST_RSS_ERRORS` 获取。"""

    global _LAST_RSS_ERRORS  # noqa: PLW0603
    _LAST_RSS_ERRORS = []

    timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
    connector = aiohttp.TCPConnector(limit=20)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml;q=0.9, text/html;q=0.8, */*;q=0.7",
    }
    async with aiohttp.ClientSession(timeout=timeout, headers=headers, connector=connector) as session:
        tasks = [fetch_rss_source(session, source, limit_per_source) for source in sources]
        results = await asyncio.gather(*tasks, return_exceptions=True)

    items: List[Dict] = []
    for source, result in zip(sources, results):
        if isinstance(result, Exception):
            _LAST_RSS_ERRORS.append({"source": source.get("name", ""), "stage": "rss", "error": str(result)})
            continue
        items.extend(result)
    return items


def _coarse_eval(item: Dict) -> Tuple[bool, float, List[str]]:
    extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
    title = str(item.get("title", ""))
    summary = str(item.get("summary", ""))
    content = str(item.get("content", ""))
    category = str(item.get("category", ""))
    source = str(item.get("source", ""))
    source_type = str(item.get("source_type", ""))

    reasons: List[str] = []
    score = 0.5

    tier = str(extra.get("priority_tier", "")).strip().upper()
    if tier == "T0":
        score += 0.22
        reasons.append("priority_tier_T0")
    elif tier == "T1":
        score += 0.12
        reasons.append("priority_tier_T1")
    elif tier == "T2":
        score -= 0.10
        reasons.append("priority_tier_T2")

    if category == "developer-news":
        score -= 0.12
        reasons.append("category_developer_news")
    if source_type.startswith("github"):
        score -= 0.15
        reasons.append("source_type_github")

    haystack = " ".join([source, category, title, summary, content]).lower()
    # 正向：核心扫描词
    positive_keywords = {
        "quant",
        "factor",
        "alpha",
        "backtest",
        "portfolio",
        "risk model",
        "market microstructure",
        "options",
        "earnings",
        "etf",
        "agent",
        "workflow",
        "tool calling",
        "orchestration",
        "realtime",
        "multimodal",
        "inference",
        "rl",
        "ppo",
    }
    if any(keyword in haystack for keyword in positive_keywords):
        score += 0.12
        reasons.append("hit_core_keyword")

    # 负向：低信息密度/常规更新
    negative_patterns = [
        r"\bchangelog\b",
        r"\brelease\b",
        r"\bv\d+(?:\.\d+){1,3}\b",
        r"\bweekly\b",
        r"\bnewsletter\b",
        r"\bpatch\b",
    ]
    if any(re.search(pattern, haystack) for pattern in negative_patterns):
        score -= 0.10
        reasons.append("looks_like_routine_update")

    text_len = len(re.sub(r"\s+", " ", f"{title} {summary} {content}").strip())
    if text_len < 120:
        score -= 0.18
        reasons.append("too_short")
    elif text_len < 220:
        score -= 0.08
        reasons.append("short")

    score = clamp(score, 0.0, 1.0)
    passed = score >= COARSE_MIN_SCORE
    if passed:
        reasons.append("coarse_pass")
    else:
        reasons.append("coarse_reject")
    return passed, score, reasons


def coarse_filter_item(item: Dict) -> bool:
    passed, _, _ = _coarse_eval(item)
    return passed


def coarse_score_item(item: Dict) -> float:
    _, score, _ = _coarse_eval(item)
    return score


def run_funnel_one(items: List[Dict]) -> List[Dict]:
    passed_items: List[Dict] = []
    for item in items:
        passed, score, reasons = _coarse_eval(item)
        extra = item.get("extra") if isinstance(item.get("extra"), dict) else {}
        extra["coarse_pass"] = passed
        extra["coarse_score"] = round(float(score), 4)
        # reasons 保持短 token，便于调试
        extra["coarse_reason"] = reasons[:8]
        item["extra"] = extra
        if passed:
            passed_items.append(item)
    return passed_items


def select_top_for_llm(items: List[Dict], top_n: int = COARSE_LLM_TOP_N) -> List[Dict]:
    ranked = sorted(
        items,
        key=lambda item: float((item.get("extra") or {}).get("coarse_score", 0) or 0),
        reverse=True,
    )
    return ranked[: max(1, int(top_n))]


def resolve_entry_summary(entry) -> str:
    candidates = [
        getattr(entry, "summary", ""),
        getattr(entry, "description", ""),
    ]
    detail = getattr(entry, "summary_detail", None)
    if detail and getattr(detail, "value", None):
        candidates.append(detail.value)
    cleaned = unique_non_empty([strip_html(candidate) for candidate in candidates])
    return cleaned[0] if cleaned else ""


def fetch_feed(session: requests.Session, source: Dict, limit: int) -> List[Dict]:
    response = session.get(source["url"], timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)

    items: List[Dict] = []
    for entry in parsed.entries[:limit]:
        title = strip_html(getattr(entry, "title", "")) or "Untitled"
        link = getattr(entry, "link", "") or ""
        summary = resolve_entry_summary(entry)

        content_chunks: List[str] = []
        if getattr(entry, "content", None):
            for block in entry.content:
                content_chunks.append(strip_html(getattr(block, "value", "")))
        if not content_chunks and summary:
            content_chunks.append(summary)

        extra: Dict = {"feed_url": source["url"]}
        enriched: Dict[str, str] = {}
        if link:
            try:
                enriched = enrich_from_link(session, link)
            except Exception:
                enriched = {}

        summary = prefer_richer_text(summary, enriched.get("summary", ""), min_existing_length=60)
        existing_content = "\n".join(part for part in content_chunks if part)
        preferred_content = prefer_richer_text(existing_content, enriched.get("content", ""), min_existing_length=180)
        content_text = preferred_content
        if title == "Untitled" and enriched.get("title"):
            title = enriched["title"]
        elif enriched.get("title") and len(title) < 12 and len(enriched["title"]) > len(title):
            title = enriched["title"]

        if enriched:
            extra["enriched_from_link"] = True
        if enriched.get("cover_image_url"):
            extra["cover_image_url"] = enriched["cover_image_url"]
            extra["cover_image_source"] = "source-page"

        extra.update(
            build_priority_metadata(
                source=source["name"],
                source_type="rss",
                category=source["category"],
                title=title,
                summary=summary,
                content=content_text,
            )
        )

        published_at = (
            getattr(entry, "published", "")
            or getattr(entry, "updated", "")
            or ""
        )

        items.append(
            normalize_item(
                source=source["name"],
                source_type="rss",
                category=source["category"],
                title=title,
                link=link,
                summary=summary,
                content=content_text,
                published_at=published_at,
                extra=extra,
            )
        )

    return items


def fetch_github_feed(session: requests.Session, repo: Dict, kind: str, limit: int) -> List[Dict]:
    if kind == "release":
        feed_url = f"https://github.com/{repo['owner']}/{repo['repo']}/releases.atom"
        source_type = "github_release"
    else:
        branch = repo["branch"]
        feed_url = f"https://github.com/{repo['owner']}/{repo['repo']}/commits/{branch}.atom"
        source_type = "github_commit"

    response = session.get(feed_url, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    parsed = feedparser.parse(response.content)

    items: List[Dict] = []
    for entry in parsed.entries[:limit]:
        title = strip_html(getattr(entry, "title", "")) or "Untitled"
        link = getattr(entry, "link", "") or ""
        summary = resolve_entry_summary(entry)

        content_chunks: List[str] = []
        if getattr(entry, "content", None):
            for block in entry.content:
                content_chunks.append(strip_html(getattr(block, "value", "")))
        if not content_chunks and summary:
            content_chunks.append(summary)

        enriched: Dict[str, str] = {}
        if link:
            try:
                enriched = enrich_from_link(session, link)
            except Exception:
                enriched = {}

        existing_content = "\n".join(part for part in content_chunks if part)
        summary = prefer_richer_text(summary, enriched.get("summary", ""), min_existing_length=80)
        content_text = prefer_richer_text(existing_content, enriched.get("content", ""), min_existing_length=220)

        extra = {
            "owner": repo["owner"],
            "repo": repo["repo"],
            "branch": repo["branch"],
            "feed_url": feed_url,
        }
        if enriched:
            extra["enriched_from_link"] = True
        if enriched.get("cover_image_url"):
            extra["cover_image_url"] = enriched["cover_image_url"]
            extra["cover_image_source"] = "source-page"

        extra.update(
            build_priority_metadata(
                source=f"GitHub/{repo['owner']}/{repo['repo']}",
                source_type=source_type,
                category=repo.get("category", "github"),
                title=title,
                summary=summary,
                content=content_text,
            )
        )

        items.append(
            normalize_item(
                source=f"GitHub/{repo['owner']}/{repo['repo']}",
                source_type=source_type,
                category=repo.get("category", "github"),
                title=title,
                link=link,
                summary=summary,
                content=content_text,
                published_at=(getattr(entry, "published", "") or getattr(entry, "updated", "") or ""),
                extra=extra,
            )
        )
    return items


def deduplicate(items: Iterable[Dict]) -> List[Dict]:
    seen = set()
    results: List[Dict] = []
    for item in items:
        key = item["dedupe_key"]
        if key in seen:
            continue
        seen.add(key)
        results.append(item)
    return results


def sort_datetime(value: str) -> datetime:
    if not value:
        return datetime.min.replace(tzinfo=timezone.utc)
    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value)
        else:
            parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return datetime.min.replace(tzinfo=timezone.utc)


def collect_news(
    limit_per_source: int,
    history_file: str,
    trust_file: str,
    sources_catalog: str = DEFAULT_SOURCE_CATALOG_FILE,
) -> Dict:
    history_path = Path(history_file)
    history_payload = load_history(history_path)

    trust_payload = load_sources_trust(trust_file)
    rss_sources, github_repos, catalog_meta = load_source_catalog(sources_catalog)

    items: List[Dict] = []
    errors: List[Dict] = []

    # RSS：并发抓取 + 信源黑名单前置
    allowed_rss_sources: List[Dict] = []
    rss_blocked_count = 0
    for source in rss_sources:
        domain = extract_domain_from_url(source.get("url", ""))
        if is_source_blocked(source.get("name", ""), domain, trust_payload):
            rss_blocked_count += 1
            continue
        allowed_rss_sources.append(source)

    try:
        rss_items = asyncio.run(fetch_all_rss(allowed_rss_sources, limit_per_source))
        items.extend(rss_items)
        errors.extend(_LAST_RSS_ERRORS)
    except Exception as exc:  # noqa: BLE001
        errors.append({"source": "*", "stage": "rss_all", "error": str(exc)})

    # GitHub：暂保留同步抓取
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "application/atom+xml, application/rss+xml, application/xml, text/xml;q=0.9, text/html;q=0.8, */*;q=0.7",
        }
    )
    for repo in github_repos:
        for kind in ["release", "commit"]:
            try:
                items.extend(fetch_github_feed(session, repo, kind=kind, limit=max(3, min(limit_per_source, 5))))
            except Exception as exc:  # noqa: BLE001
                errors.append(
                    {
                        "source": f"{repo['owner']}/{repo['repo']}",
                        "stage": f"github_{kind}",
                        "error": str(exc),
                    }
                )

    current_run_deduped = deduplicate(items)
    history_filtered, history_filtered_count = filter_history_seen(current_run_deduped, history_payload)
    history_filtered.sort(
        key=lambda item: sort_datetime(item.get("published_at") or item.get("collected_at")),
        reverse=True,
    )

    # 漏斗一：本地粗筛
    funnel_one_passed = run_funnel_one(history_filtered)
    funnel_one_rejected_count = len(history_filtered) - len(funnel_one_passed)

    # 漏斗二（仅选择 Top 30 进入 LLM）
    llm_candidates = select_top_for_llm(funnel_one_passed, top_n=COARSE_LLM_TOP_N)

    return {
        "generated_at": iso_now(),
        "stats": {
            "rss_source_count": len(rss_sources),
            "rss_blocked_count": rss_blocked_count,
            "github_repo_count": len(github_repos),
            "raw_item_count": len(items),
            "current_run_deduped_item_count": len(current_run_deduped),
            "history_item_count": len(history_payload.get("items", [])),
            "history_filtered_count": history_filtered_count,
            "deduped_item_count": len(history_filtered),
            "coarse_rejected_count": funnel_one_rejected_count,
            "coarse_passed_count": len(funnel_one_passed),
            "llm_candidate_count": len(llm_candidates),
            "error_count": len(errors),
        },
        "sources": {
            "catalog": catalog_meta,
            "rss": rss_sources,
            "github": github_repos,
        },
        "history": {
            "file": str(history_path),
            "mode": "drop_before_ai_if_link_or_title_hash_seen",
            "loaded_item_count": len(history_payload.get("items", [])),
        },
        "scoring_tiers": [
            {"tier": "T0", "description": "量化交易、US Stocks、交易策略与市场信号。"},
            {"tier": "T1", "description": "AI 产品落地、AI 行业实践、AI 工作流应用。"},
            {"tier": "T2", "description": "GitHub 热门项目、底层开发工具、developer-news。"},
        ],
        "priority_topics": unique_non_empty([rule["label"] for rule in TIER_RULES]),
        "weight_adjustments": [
            {
                "target": "developer-news",
                "priority_tier": DEVELOPER_TOOLS_T2["priority_tier"],
                "score_adjustment_hint": DEVELOPER_TOOLS_T2["score_adjustment_hint"],
                "suggested_score_ceiling": DEVELOPER_TOOLS_T2["suggested_score_ceiling"],
                "reason": DEVELOPER_TOOLS_T2["reason"],
            },
            {
                "target": "github_*",
                "priority_tier": GITHUB_T2["priority_tier"],
                "score_adjustment_hint": GITHUB_T2["score_adjustment_hint"],
                "suggested_score_ceiling": GITHUB_T2["suggested_score_ceiling"],
                "reason": GITHUB_T2["reason"],
            },
        ],
        "errors": errors,
        "items": llm_candidates,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取 RSS 和 GitHub 仓库动态")
    parser.add_argument(
        "--output",
        default="raw_news.json",
        help="输出 JSON 文件路径，默认 raw_news.json",
    )
    parser.add_argument(
        "--limit-per-source",
        type=int,
        default=DEFAULT_PER_SOURCE,
        help="每个 RSS 源最多抓取多少条，默认 8",
    )
    parser.add_argument(
        "--history-file",
        default=DEFAULT_HISTORY_FILE,
        help="跨频次历史去重文件，默认 assets/history_seen_urls.json",
    )
    parser.add_argument(
        "--trust-file",
        default=DEFAULT_TRUST_FILE,
        help="信源信任度状态文件，默认 assets/sources_trust.json",
    )
    parser.add_argument(
        "--sources-catalog",
        default=DEFAULT_SOURCE_CATALOG_FILE,
        help=f"信息源目录文件，默认 {DEFAULT_SOURCE_CATALOG_FILE}；不存在时回退到 example",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = collect_news(
        limit_per_source=max(1, args.limit_per_source),
        history_file=args.history_file,
        trust_file=args.trust_file,
        sources_catalog=args.sources_catalog,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"已生成 {output_path}，本轮去重后 {payload['stats']['current_run_deduped_item_count']} 条，"
        f"历史过滤 {payload['stats']['history_filtered_count']} 条，最终保留 {payload['stats']['deduped_item_count']} 条，"
        f"抓取错误 {payload['stats']['error_count']} 条。"
    )


if __name__ == "__main__":
    main()
