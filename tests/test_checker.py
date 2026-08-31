# tests/test_checker.py
import json
from datetime import date
from pathlib import Path

from frontier_pipeline.graph.model import GraphNode
from frontier_pipeline.nodes.checker import run_checker
from frontier_pipeline.nodes.registry import NodeContext
from frontier_pipeline.schemas import CheckResult, InvestmentCard, ReportDocument


def _ctx(tmp_path: Path) -> NodeContext:
    return NodeContext(
        node=GraphNode(
            id="checker",
            uses="checker",
            inputs=["report.md", "report.json", "investments.json"],
            outputs=["check.json"],
            on_hard_fail="stop",
        ),
        artifact_dir=tmp_path,
        repo_root=tmp_path,
        llm=None,
    )


def test_hard_fail_on_ungrounded_claim(tmp_path: Path):
    report = ReportDocument(
        title="t",
        report_date=date(2026, 8, 8),
        ranked_projects=[
            {
                "repo_id": "acme/agentkit",
                "rank": 1,
                "rationale": "fits",
                "business_case": "sell tools",
                "citations": ["https://example.com/ok"],
            }
        ],
        claims=[{"text": "Secret claim", "citations": ["https://not-in-sources.example"]}],
    )
    investments = [
        InvestmentCard(
            headline="Agents funded",
            themes=["agents"],
            actors=["Fund"],
            source_url="https://example.com/ok",
            date=date(2026, 8, 7),
        ).model_dump(mode="json")
    ]
    (tmp_path / "report.json").write_text(report.model_dump_json(), encoding="utf-8")
    (tmp_path / "report.md").write_text("# t\n", encoding="utf-8")
    (tmp_path / "investments.json").write_text(json.dumps(investments), encoding="utf-8")
    run_checker(_ctx(tmp_path))
    result = CheckResult.model_validate_json((tmp_path / "check.json").read_text(encoding="utf-8"))
    assert result.hard_pass is False
    assert any(i.code == "ungrounded" for i in result.issues)


def test_hard_fail_when_business_case_ignores_themes(tmp_path: Path):
    report = ReportDocument(
        title="t",
        report_date=date(2026, 8, 8),
        ranked_projects=[
            {
                "repo_id": "acme/agentkit",
                "rank": 1,
                "rationale": "popular",
                "business_case": "Build a coffee shop franchise",
                "citations": ["https://example.com/ok", "wiki/projects/acme-agentkit.md"],
            }
        ],
        claims=[
            {
                "text": "Investors funded agent infra",
                "citations": ["https://example.com/ok"],
            }
        ],
    )
    investments = [
        InvestmentCard(
            headline="Chip design round",
            themes=["chip design", "semiconductors"],
            actors=["Fund"],
            source_url="https://example.com/ok",
            date=date(2026, 8, 7),
        ).model_dump(mode="json")
    ]
    (tmp_path / "report.json").write_text(report.model_dump_json(), encoding="utf-8")
    (tmp_path / "report.md").write_text("# t\n", encoding="utf-8")
    (tmp_path / "investments.json").write_text(json.dumps(investments), encoding="utf-8")
    (tmp_path / "wiki" / "projects").mkdir(parents=True)
    (tmp_path / "wiki" / "projects" / "acme-agentkit.md").write_text(
        "topics: [ai-agents]\n", encoding="utf-8"
    )
    run_checker(_ctx(tmp_path))
    result = CheckResult.model_validate_json((tmp_path / "check.json").read_text(encoding="utf-8"))
    assert result.hard_pass is False
    assert any(i.code == "investment_logic" for i in result.issues)


def test_soft_fail_on_missing_manifest_nodes(tmp_path: Path):
    report = ReportDocument(
        title="t",
        report_date=date(2026, 8, 8),
        ranked_projects=[
            {
                "repo_id": "acme/agentkit",
                "rank": 1,
                "rationale": "agent infra aligns",
                "business_case": "Agent ops platform for enterprises",
                "citations": ["https://example.com/ok", "wiki/projects/acme-agentkit.md"],
            }
        ],
        claims=[
            {
                "text": "Investors funded agent infra",
                "citations": ["https://example.com/ok"],
            }
        ],
    )
    investments = [
        InvestmentCard(
            headline="Agent infra round",
            themes=["agent infra", "agents"],
            actors=["Fund"],
            source_url="https://example.com/ok",
            date=date(2026, 8, 7),
        ).model_dump(mode="json")
    ]
    (tmp_path / "report.json").write_text(report.model_dump_json(), encoding="utf-8")
    (tmp_path / "report.md").write_text("# t\n", encoding="utf-8")
    (tmp_path / "investments.json").write_text(json.dumps(investments), encoding="utf-8")
    (tmp_path / "wiki" / "projects").mkdir(parents=True)
    (tmp_path / "wiki" / "projects" / "acme-agentkit.md").write_text(
        "topics: [ai-agents]\n", encoding="utf-8"
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps(
            {
                "run_id": "x",
                "graph_name": "friday_report",
                "started_at": "2026-08-08T00:00:00+00:00",
                "nodes": [],
            }
        ),
        encoding="utf-8",
    )
    run_checker(_ctx(tmp_path))
    result = CheckResult.model_validate_json((tmp_path / "check.json").read_text(encoding="utf-8"))
    assert result.hard_pass is True
    assert result.soft_pass is False
