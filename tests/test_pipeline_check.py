import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from frontier_pipeline.graph.model import GraphNode
from frontier_pipeline.nodes.pipeline_check import run_pipeline_check
from frontier_pipeline.nodes.registry import NodeContext


def _write_repos(artifact_dir: Path) -> None:
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


def _ctx(tmp_path: Path, inputs: list[str] | None = None) -> NodeContext:
    return NodeContext(
        node=GraphNode(
            id="pipeline_check",
            uses="pipeline_check",
            inputs=inputs or ["repos.json", "wiki_done.json"],
            outputs=["pipeline_check.json"],
        ),
        artifact_dir=tmp_path,
        repo_root=tmp_path,
        llm=None,
    )


def test_pipeline_check_soft_pass_when_inputs_valid(tmp_path: Path):
    _write_repos(tmp_path)
    (tmp_path / "wiki_done.json").write_text(
        json.dumps({"updated": ["acme/agentkit"]}), encoding="utf-8"
    )
    run_pipeline_check(_ctx(tmp_path))
    out = json.loads((tmp_path / "pipeline_check.json").read_text(encoding="utf-8"))
    assert out["soft_pass"] is True
    assert out["warnings"] == []


def test_pipeline_check_soft_fail_empty_wiki_updated_without_raise(tmp_path: Path):
    _write_repos(tmp_path)
    (tmp_path / "wiki_done.json").write_text(json.dumps({"updated": []}), encoding="utf-8")
    run_pipeline_check(_ctx(tmp_path))
    out = json.loads((tmp_path / "pipeline_check.json").read_text(encoding="utf-8"))
    assert out["soft_pass"] is False
    assert len(out["warnings"]) >= 1
    assert any("updated" in w.lower() for w in out["warnings"])


def test_pipeline_check_warns_on_manifest_failures(tmp_path: Path):
    _write_repos(tmp_path)
    (tmp_path / "wiki_done.json").write_text(
        json.dumps({"updated": ["acme/agentkit"]}), encoding="utf-8"
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "nodes": [
                    {"node_id": "github_ingest", "status": "succeeded"},
                    {"node_id": "wiki_curate", "status": "failed", "error": "boom"},
                ]
            }
        ),
        encoding="utf-8",
    )
    run_pipeline_check(_ctx(tmp_path))
    out = json.loads((tmp_path / "pipeline_check.json").read_text(encoding="utf-8"))
    assert out["soft_pass"] is False
    assert any("manifest" in w.lower() or "failed" in w.lower() for w in out["warnings"])
