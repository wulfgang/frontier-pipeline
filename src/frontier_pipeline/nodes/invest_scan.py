from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from frontier_pipeline.http_util import request_with_retries
from frontier_pipeline.llm.fake import FakeLLMProvider
from frontier_pipeline.nodes.registry import NodeContext
from frontier_pipeline.schemas import InvestmentCard

# Public RSS proxies for Bloomberg Tech / funding / AI coverage (tests mock HTTP).
FEED_URLS: list[str] = [
    "https://feeds.bloomberg.com/technology/news.rss",
    "https://techcrunch.com/category/fundraising/feed/",
    "https://venturebeat.com/category/ai/feed/",
]

_THEME_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("ai", "AI"),
    ("artificial intelligence", "AI"),
    ("agent", "agents"),
    ("funding", "funding"),
    ("raises", "funding"),
    ("series", "funding"),
    ("venture", "funding"),
    ("chip", "semiconductors"),
    ("enterprise", "enterprise"),
)


def _parse_entry_date(entry: dict[str, Any]) -> date:
    published = entry.get("published") or entry.get("updated") or ""
    if published:
        try:
            return parsedate_to_datetime(published).date()
        except (TypeError, ValueError, IndexError, OverflowError):
            pass
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return date(*parsed[:3])
        except (TypeError, ValueError):
            pass
    return datetime.now(timezone.utc).date()


def _entry_link(entry: dict[str, Any]) -> str:
    link = (entry.get("link") or "").strip()
    if link:
        return link
    for key in ("id", "guid"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip().startswith("http"):
            return value.strip()
    return ""


def _heuristic_themes(text: str) -> list[str]:
    lower = text.lower()
    themes: list[str] = []
    seen: set[str] = set()
    for needle, theme in _THEME_KEYWORDS:
        if needle in lower and theme not in seen:
            themes.append(theme)
            seen.add(theme)
    if not themes:
        themes.append("technology")
    return themes


def _heuristic_actors(title: str) -> list[str]:
    # Grab leading Proper-Case tokens before common verbs as a light actor guess.
    match = re.match(
        r"^([A-Z][\w&.-]*(?:\s+[A-Z][\w&.-]*){0,2})\s+(?:raises|closes|announces|sees)\b",
        title.strip(),
    )
    if match:
        return [match.group(1)]
    return []


def _extract_with_llm(llm: Any, title: str, summary: str) -> tuple[list[str], list[str]]:
    if llm is None or isinstance(llm, FakeLLMProvider):
        blob = f"{title}\n{summary}"
        return _heuristic_themes(blob), _heuristic_actors(title)

    result = llm.complete_json(
        f"Extract investment themes and actors from this headline and summary.\n"
        f"Title: {title}\nSummary: {summary}\n"
        f'Return JSON: {{"themes": ["..."], "actors": ["..."]}}',
        system="You extract structured investment metadata. Themes and actors must be short strings.",
    )
    themes = [str(t).strip() for t in (result.get("themes") or []) if str(t).strip()]
    actors = [str(a).strip() for a in (result.get("actors") or []) if str(a).strip()]
    if not themes:
        themes = _heuristic_themes(f"{title}\n{summary}")
    return themes, actors


def default_client() -> httpx.Client:
    return httpx.Client(timeout=30.0, follow_redirects=True)


def _fetch_feed(client: httpx.Client, url: str) -> list[dict[str, Any]]:
    response = request_with_retries(
        client,
        "GET",
        url,
        follow_redirects=True,
        timeout=30.0,
    )
    response.raise_for_status()
    parsed = feedparser.parse(response.text)
    return list(parsed.entries or [])


def _top_n_limit(default: int | None = None) -> int | None:
    raw = os.environ.get("TOP_N")
    if raw is None or raw.strip() == "":
        return default
    return max(0, int(raw))


def run_invest_scan(
    ctx: NodeContext,
    client: httpx.Client | None = None,
    feed_urls: list[str] | None = None,
) -> None:
    owns_client = client is None
    if owns_client:
        client = default_client()

    urls = feed_urls if feed_urls is not None else list(FEED_URLS)
    cards: list[InvestmentCard] = []
    seen_urls: set[str] = set()
    limit = _top_n_limit()

    try:
        for feed_url in urls:
            try:
                entries = _fetch_feed(client, feed_url)
            except httpx.HTTPError:
                continue
            for entry in entries:
                source_url = _entry_link(entry)
                if not source_url or source_url in seen_urls:
                    continue
                title = (entry.get("title") or "").strip()
                if not title:
                    continue
                summary = (entry.get("summary") or entry.get("description") or "").strip()
                themes, actors = _extract_with_llm(ctx.llm, title, summary)
                card = InvestmentCard(
                    headline=title,
                    themes=themes,
                    actors=actors,
                    source_url=source_url,
                    date=_parse_entry_date(entry),
                )
                cards.append(card)
                seen_urls.add(source_url)
                if limit is not None and len(cards) >= limit:
                    break
            if limit is not None and len(cards) >= limit:
                break
    finally:
        if owns_client:
            client.close()

    output_name = ctx.node.outputs[0] if ctx.node.outputs else "investments.json"
    payload = [card.model_dump(mode="json") for card in cards]
    out_path = ctx.artifact_dir / output_name
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def invest_scan_node(ctx: NodeContext) -> None:
    run_invest_scan(ctx)
