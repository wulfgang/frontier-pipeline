import json
from datetime import datetime, timezone
from pathlib import Path

from frontier_pipeline.graph.model import GraphNode
from frontier_pipeline.nodes.registry import NodeContext
from frontier_pipeline.nodes.wiki_curate import run_wiki_curate
from frontier_pipeline.wiki_bootstrap import bootstrap_wiki


def test_wiki_curate_upserts_project_page(tmp_path: Path):
    wiki = tmp_path / "wiki"
    bootstrap_wiki(wiki)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    repos = [
        {
            "id": "acme/agentkit",
            "url": "https://github.com/acme/agentkit",
            "stars": 1200,
            "topics": ["ai-agents"],
            "summary": "LLM agents toolkit",
            "fetched_at": datetime(2026, 8, 9, tzinfo=timezone.utc).isoformat(),
            "recent_activity_score": 1.0,
        }
    ]
    (artifact_dir / "repos.json").write_text(json.dumps(repos), encoding="utf-8")
    ctx = NodeContext(
        node=GraphNode(
            id="wiki_curate",
            uses="wiki_curate",
            inputs=["repos.json"],
            outputs=["wiki_done.json"],
        ),
        artifact_dir=artifact_dir,
        repo_root=tmp_path,
        llm=None,
    )
    run_wiki_curate(ctx)
    page = wiki / "projects" / "acme-agentkit.md"
    assert page.exists()
    text = page.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    assert "\n---\n" in text
    assert "acme/agentkit" in text
    assert "[[themes/ai-agents]]" in text or "ai-agents" in text
    assert (wiki / "themes" / "ai-agents.md").exists()
    assert (artifact_dir / "wiki_done.json").exists()
    assert "acme-agentkit" in (wiki / "index.md").read_text(encoding="utf-8")
