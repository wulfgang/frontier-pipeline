import json
from pathlib import Path

import httpx
import pytest

from frontier_pipeline.graph.loader import load_graph
from frontier_pipeline.graph.runner import GraphRunner
from frontier_pipeline.llm.fake import FakeLLMProvider
from frontier_pipeline.nodes.registry import build_default_registry
from frontier_pipeline.wiki_bootstrap import bootstrap_wiki

GRAPH_PATH = Path(__file__).resolve().parents[1] / "graphs" / "friday_report.yaml"

INVESTMENT_URL = "https://techcrunch.com/2026/08/08/acme-raises-50m/"
WIKI_PATH = "wiki/projects/acme-agentkit.md"

TECHCRUNCH_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TechCrunch Fundraising</title>
    <item>
      <title>Acme raises $50M Series B for AI agent platform</title>
      <link>https://techcrunch.com/2026/08/08/acme-raises-50m/</link>
      <pubDate>Fri, 08 Aug 2026 12:00:00 GMT</pubDate>
      <description>Acme announced Series B funding to scale its AI agent infrastructure.</description>
    </item>
  </channel>
</rss>
"""


def _grounded_report() -> dict:
    return {
        "title": "AI Agent Frontier Report",
        "report_date": "2026-08-09",
        "ranked_projects": [
            {
                "repo_id": "acme/agentkit",
                "rank": 1,
                "rationale": "Strong agent infra fit with recent funding themes",
                "business_case": "Enterprise agent ops tooling aligned with Acme Series B funding",
                "citations": [INVESTMENT_URL, WIKI_PATH],
            }
        ],
        "claims": [
            {
                "text": "Funding into agent infrastructure continues",
                "citations": [INVESTMENT_URL],
            }
        ],
    }


def _ungrounded_report() -> dict:
    return {
        "title": "AI Agent Frontier Report",
        "report_date": "2026-08-09",
        "ranked_projects": [
            {
                "repo_id": "acme/agentkit",
                "rank": 1,
                "rationale": "Strong agent infra fit with recent funding themes",
                "business_case": "Enterprise agent ops tooling aligned with Acme Series B funding",
                "citations": ["https://not-in-sources.example/secret"],
            }
        ],
        "claims": [
            {
                "text": "Secret claim",
                "citations": ["https://not-in-sources.example/secret"],
            }
        ],
    }


@pytest.fixture
def mock_invest_scan_client(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=TECHCRUNCH_RSS,
            headers={"content-type": "application/rss+xml"},
        )

    def fake_default_client() -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(
        "frontier_pipeline.nodes.invest_scan.default_client",
        fake_default_client,
    )


def _prepare_wiki(tmp_path: Path) -> Path:
    wiki = tmp_path / "wiki"
    bootstrap_wiki(wiki)
    project = wiki / "projects" / "acme-agentkit.md"
    project.write_text(
        "---\nrepo_id: acme/agentkit\nurl: https://github.com/acme/agentkit\nstars: 1200\n"
        "topics:\n- ai-agents\nupdated: 2026-08-09\n---\n\n"
        "LLM agents toolkit for enterprise workflows.\n",
        encoding="utf-8",
    )
    return tmp_path


def test_friday_report_happy_path_writes_html(tmp_path: Path, mock_invest_scan_client):
    repo_root = _prepare_wiki(tmp_path)
    artifacts = tmp_path / "artifacts"
    llm = FakeLLMProvider(json_responses=[_grounded_report()])

    runner = GraphRunner(
        registry=build_default_registry(),
        artifacts_root=artifacts,
        repo_root=repo_root,
        llm=llm,
    )
    manifest = runner.run(load_graph(GRAPH_PATH), run_id="friday1")

    run_dir = artifacts / "friday1"
    assert (run_dir / "investments.json").exists()
    assert (run_dir / "report.md").exists()
    assert (run_dir / "report.json").exists()
    assert (run_dir / "check.json").exists()
    assert (run_dir / "report.html").exists()

    check = json.loads((run_dir / "check.json").read_text(encoding="utf-8"))
    assert check["hard_pass"] is True

    html = (run_dir / "report.html").read_text(encoding="utf-8")
    assert "<html" in html
    assert "acme/agentkit" in html

    statuses = {n.node_id: n.status for n in manifest.nodes}
    assert statuses["invest_scan"] == "succeeded"
    assert statuses["frontier_report"] == "succeeded"
    assert statuses["checker"] == "succeeded"
    assert statuses["render_share"] == "succeeded"


def test_friday_report_hard_fail_skips_render(tmp_path: Path, mock_invest_scan_client):
    repo_root = _prepare_wiki(tmp_path)
    artifacts = tmp_path / "artifacts"
    llm = FakeLLMProvider(json_responses=[_ungrounded_report()])

    runner = GraphRunner(
        registry=build_default_registry(),
        artifacts_root=artifacts,
        repo_root=repo_root,
        llm=llm,
    )
    manifest = runner.run(load_graph(GRAPH_PATH), run_id="friday2")

    run_dir = artifacts / "friday2"
    check = json.loads((run_dir / "check.json").read_text(encoding="utf-8"))
    assert check["hard_pass"] is False

    statuses = {n.node_id: n.status for n in manifest.nodes}
    assert statuses["checker"] == "succeeded"
    assert statuses["render_share"] == "skipped"
    assert not (run_dir / "report.html").exists()
