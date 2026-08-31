from __future__ import annotations

import os
from typing import Any

import httpx

from frontier_pipeline.http_util import request_with_retries

GITHUB_API = "https://api.github.com"
AGENT_TOPICS = ("ai-agents", "llm-agents", "autonomous-agents", "agentic")


def default_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def default_client() -> httpx.Client:
    return httpx.Client(headers=default_headers(), timeout=30.0)


def search_repositories(
    client: httpx.Client,
    topic: str,
    *,
    per_page: int = 100,
) -> list[dict[str, Any]]:
    response = request_with_retries(
        client,
        "GET",
        f"{GITHUB_API}/search/repositories",
        params={
            "q": f"topic:{topic}",
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
        },
    )
    response.raise_for_status()
    return response.json().get("items", [])


def fetch_agent_repositories(
    client: httpx.Client,
    *,
    per_page: int = 100,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for topic in AGENT_TOPICS:
        for item in search_repositories(client, topic, per_page=per_page):
            full_name = item.get("full_name")
            if not full_name or full_name in seen:
                continue
            seen.add(full_name)
            merged.append(item)
    return merged
