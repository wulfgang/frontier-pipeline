import json
from pathlib import Path

import httpx
import pytest

from frontier_pipeline.graph.loader import load_graph
from frontier_pipeline.graph.runner import GraphRunner
from frontier_pipeline.llm.fake import FakeLLMProvider
from frontier_pipeline.nodes.registry import build_default_registry
from frontier_pipeline.wiki_bootstrap import bootstrap_wiki


FIXTURES = Path(__file__).parent / "fixtures" / "daily"
GRAPH_PATH = Path(__file__).resolve().parents[1] / "graphs" / "daily_ingest.yaml"


@pytest.fixture
def mock_github_client(monkeypatch):
    payload = json.loads((FIXTURES / "github_search_response.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    def fake_default_client() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(
        "frontier_pipeline.nodes.github_ingest.default_client",
        fake_default_client,
    )


def test_daily_ingest_graph_end_to_end(tmp_path: Path, mock_github_client):
    wiki = tmp_path / "wiki"
    bootstrap_wiki(wiki)
    artifacts = tmp_path / "artifacts"

    runner = GraphRunner(
        registry=build_default_registry(),
        artifacts_root=artifacts,
        repo_root=tmp_path,
        llm=FakeLLMProvider(),
    )
    manifest = runner.run(load_graph(GRAPH_PATH), run_id="daily1")

    run_dir = artifacts / "daily1"
    assert (run_dir / "repos.json").exists()
    assert (run_dir / "wiki_done.json").exists()
    assert (run_dir / "pipeline_check.json").exists()
    assert (run_dir / "manifest.json").exists()

    check = json.loads((run_dir / "pipeline_check.json").read_text(encoding="utf-8"))
    assert check["soft_pass"] is True

    page = wiki / "projects" / "acme-agentkit.md"
    assert page.exists()
    assert "acme/agentkit" in page.read_text(encoding="utf-8")

    statuses = {n.node_id: n.status for n in manifest.nodes}
    assert statuses["github_ingest"] == "succeeded"
    assert statuses["wiki_curate"] == "succeeded"
    assert statuses["pipeline_check"] == "succeeded"
