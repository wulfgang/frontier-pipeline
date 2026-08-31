from pathlib import Path

from frontier_pipeline.graph.model import GraphNode
from frontier_pipeline.nodes.registry import NodeContext, build_default_registry
from frontier_pipeline.nodes.render_share import run_render_share


def test_render_share_writes_html_with_html_tag(tmp_path: Path):
    report_md = tmp_path / "report.md"
    report_md.write_text(
        "# Frontier Report\n\n## Rankings\n\n- **acme/agentkit** leads agents.\n",
        encoding="utf-8",
    )
    (tmp_path / "check.json").write_text(
        '{"hard_pass": true, "soft_pass": true, "issues": []}',
        encoding="utf-8",
    )

    ctx = NodeContext(
        node=GraphNode(
            id="render_share",
            uses="render_share",
            inputs=["report.md", "check.json"],
            outputs=["report.html"],
            requires_check="hard_pass",
        ),
        artifact_dir=tmp_path,
        repo_root=tmp_path,
        llm=None,
        check_hard_pass=True,
    )
    run_render_share(ctx)

    html_path = tmp_path / "report.html"
    assert html_path.exists()
    html = html_path.read_text(encoding="utf-8")
    assert "<html" in html
    assert "Frontier Report" in html
    assert "acme/agentkit" in html


def test_render_share_registered_in_default_registry():
    registry = build_default_registry()
    assert registry.get("render_share") is not None
