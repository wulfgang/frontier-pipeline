import json
from datetime import date
from pathlib import Path

import pytest
from pydantic import ValidationError

from frontier_pipeline.graph.model import GraphNode
from frontier_pipeline.llm.fake import FakeLLMProvider
from frontier_pipeline.nodes.frontier_report import run_frontier_report
from frontier_pipeline.nodes.registry import NodeContext, build_default_registry
from frontier_pipeline.schemas import ReportDocument
from frontier_pipeline.wiki_bootstrap import bootstrap_wiki

INVESTMENT_URL = "https://techcrunch.com/2026/08/08/acme-raises-50m/"
WIKI_PATH = "wiki/projects/acme-agentkit.md"


def _valid_report_payload() -> dict:
    return {
        "title": "AI Agent Frontier Report",
        "report_date": "2026-08-09",
        "ranked_projects": [
            {
                "repo_id": "acme/agentkit",
                "rank": 1,
                "rationale": "Strong agent infra fit with recent funding themes",
                "business_case": "Enterprise agent ops tooling aligned with Acme Series B",
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


def _setup(tmp_path: Path) -> tuple[Path, Path]:
    wiki = tmp_path / "wiki"
    bootstrap_wiki(wiki)
    project = wiki / "projects" / "acme-agentkit.md"
    project.write_text(
        "---\nrepo_id: acme/agentkit\nurl: https://github.com/acme/agentkit\nstars: 1200\n"
        "topics:\n- ai-agents\nupdated: 2026-08-09\n---\n\n"
        "LLM agents toolkit for enterprise workflows.\n",
        encoding="utf-8",
    )
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    investments = [
        {
            "headline": "Acme raises $50M Series B for AI agent platform",
            "themes": ["AI", "agents", "funding"],
            "actors": ["Acme"],
            "source_url": INVESTMENT_URL,
            "date": "2026-08-08",
        }
    ]
    (artifact_dir / "investments.json").write_text(
        json.dumps(investments), encoding="utf-8"
    )
    return artifact_dir, tmp_path


def _ctx(artifact_dir: Path, repo_root: Path, llm: FakeLLMProvider) -> NodeContext:
    return NodeContext(
        node=GraphNode(
            id="frontier_report",
            uses="frontier_report",
            inputs=["investments.json"],
            outputs=["report.md", "report.json"],
        ),
        artifact_dir=artifact_dir,
        repo_root=repo_root,
        llm=llm,
    )


def test_frontier_report_writes_validated_report_and_markdown(tmp_path: Path):
    artifact_dir, repo_root = _setup(tmp_path)
    llm = FakeLLMProvider(json_responses=[_valid_report_payload()])
    run_frontier_report(_ctx(artifact_dir, repo_root, llm))

    report_json = json.loads((artifact_dir / "report.json").read_text(encoding="utf-8"))
    doc = ReportDocument.model_validate(report_json)
    assert doc.ranked_projects[0].repo_id == "acme/agentkit"
    assert doc.ranked_projects[0].rank == 1
    assert INVESTMENT_URL in doc.ranked_projects[0].citations
    assert WIKI_PATH in doc.ranked_projects[0].citations

    md = (artifact_dir / "report.md").read_text(encoding="utf-8")
    assert "rank" in md.lower() or "#1" in md or "1." in md
    assert "acme/agentkit" in md
    assert INVESTMENT_URL in md
    assert WIKI_PATH in md
    assert not (repo_root / "reports" / "drafts").exists() or not any(
        (repo_root / "reports" / "drafts").iterdir()
    )


def test_frontier_report_repairs_invalid_json_once(tmp_path: Path):
    artifact_dir, repo_root = _setup(tmp_path)
    invalid = {"title": "bad", "ranked_projects": []}  # missing report_date / invalid shape
    llm = FakeLLMProvider(json_responses=[invalid, _valid_report_payload()])
    run_frontier_report(_ctx(artifact_dir, repo_root, llm))
    doc = ReportDocument.model_validate(
        json.loads((artifact_dir / "report.json").read_text(encoding="utf-8"))
    )
    assert doc.report_date == date(2026, 8, 9)
    assert len(doc.ranked_projects) == 1


def test_frontier_report_fails_after_failed_repair(tmp_path: Path):
    artifact_dir, repo_root = _setup(tmp_path)
    invalid = {"title": "bad"}
    still_invalid = {"title": "still-bad", "ranked_projects": "nope"}
    llm = FakeLLMProvider(json_responses=[invalid, still_invalid])
    with pytest.raises((ValidationError, ValueError)):
        run_frontier_report(_ctx(artifact_dir, repo_root, llm))


def test_frontier_report_registered_in_default_registry():
    registry = build_default_registry()
    assert registry.get("frontier_report") is not None
