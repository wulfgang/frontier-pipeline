import json
from pathlib import Path

import httpx

from frontier_pipeline.graph.model import GraphNode
from frontier_pipeline.nodes.github_ingest import run_github_ingest
from frontier_pipeline.nodes.registry import NodeContext


def test_github_ingest_writes_repo_cards(tmp_path: Path):
    payload = {
        "items": [
            {
                "full_name": "acme/agentkit",
                "html_url": "https://github.com/acme/agentkit",
                "stargazers_count": 1200,
                "description": "LLM agents toolkit",
                "topics": ["ai-agents"],
                "pushed_at": "2026-08-08T00:00:00Z",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    ctx = NodeContext(
        node=GraphNode(id="github_ingest", uses="github_ingest", outputs=["repos.json"]),
        artifact_dir=tmp_path,
        repo_root=tmp_path,
        llm=None,
    )
    run_github_ingest(ctx, client=client, per_page=10)
    data = json.loads((tmp_path / "repos.json").read_text(encoding="utf-8"))
    assert data[0]["id"] == "acme/agentkit"
    assert data[0]["stars"] == 1200
