from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import httpx

from frontier_pipeline.github_client import default_client, fetch_agent_repositories
from frontier_pipeline.nodes.registry import NodeContext
from frontier_pipeline.schemas import RepoCard


def _top_n_limit(default: int) -> int:
    raw = os.environ.get("TOP_N")
    if raw is None or raw.strip() == "":
        return default
    return max(1, int(raw))


def recent_activity_score(pushed_at: str | None, now: datetime) -> float:
    if not pushed_at:
        return 0.0
    pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
    days = max(0.0, (now - pushed).total_seconds() / 86400)
    return max(0.0, 1.0 - min(days, 365.0) / 365.0)


def _to_repo_card(item: dict, now: datetime) -> RepoCard:
    activity = recent_activity_score(item.get("pushed_at"), now)
    return RepoCard(
        id=item["full_name"],
        url=item["html_url"],
        stars=int(item.get("stargazers_count") or 0),
        topics=list(item.get("topics") or []),
        summary=item.get("description") or "",
        fetched_at=now,
        recent_activity_score=activity,
    )


def _rank_key(card: RepoCard) -> tuple[float, int]:
    return (card.recent_activity_score, card.stars)


def run_github_ingest(
    ctx: NodeContext,
    client: httpx.Client | None = None,
    per_page: int = 25,
) -> None:
    owns_client = client is None
    if owns_client:
        client = default_client()

    limit = _top_n_limit(per_page)

    try:
        now = datetime.now(timezone.utc)
        raw_items = fetch_agent_repositories(client, per_page=limit)
        cards = [_to_repo_card(item, now) for item in raw_items]
        cards.sort(key=_rank_key, reverse=True)
        top = cards[:limit]

        output_name = ctx.node.outputs[0] if ctx.node.outputs else "repos.json"
        payload = [card.model_dump(mode="json") for card in top]
        out_path = ctx.artifact_dir / output_name
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    finally:
        if owns_client:
            client.close()


def github_ingest_node(ctx: NodeContext) -> None:
    run_github_ingest(ctx)
