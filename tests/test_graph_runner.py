from pathlib import Path

from frontier_pipeline.graph.loader import load_graph
from frontier_pipeline.graph.runner import GraphRunner
from frontier_pipeline.nodes.registry import NodeContext, NodeRegistry


def _write_sample(tmp_path: Path) -> Path:
    p = tmp_path / "g.yaml"
    p.write_text(
        """
name: sample
nodes:
  - id: a
    uses: echo_a
    outputs: [a.json]
  - id: b
    uses: echo_b
    inputs: [a.json]
    outputs: [b.json]
edges:
  - [a, b]
""",
        encoding="utf-8",
    )
    return p


def test_runner_executes_in_order(tmp_path: Path):
    order: list[str] = []

    def echo_a(ctx: NodeContext) -> None:
        order.append("a")
        (ctx.artifact_dir / "a.json").write_text("{}", encoding="utf-8")

    def echo_b(ctx: NodeContext) -> None:
        order.append("b")
        assert (ctx.artifact_dir / "a.json").exists()
        (ctx.artifact_dir / "b.json").write_text("{}", encoding="utf-8")

    registry = NodeRegistry({"echo_a": echo_a, "echo_b": echo_b})
    runner = GraphRunner(registry=registry, artifacts_root=tmp_path / "artifacts")
    manifest = runner.run(load_graph(_write_sample(tmp_path)), run_id="run1")
    assert order == ["a", "b"]
    assert manifest.nodes[-1].status == "succeeded"
    assert (tmp_path / "artifacts" / "run1" / "manifest.json").exists()


def test_runner_blocks_when_input_missing(tmp_path: Path):
    """Node b fails when a required input artifact is absent.

    Clarification vs plan snippet: after Step 4 (artifact_dir-only output checks),
    a node that declares outputs must write them or it fails. So for this test,
    echo_a MUST write a.json (succeed), and use a graph where b requires an
    input that was never produced (e.g. missing.json) so b fails on missing inputs.
    """
    p = tmp_path / "g.yaml"
    p.write_text(
        """
name: sample
nodes:
  - id: a
    uses: echo_a
    outputs: [a.json]
  - id: b
    uses: echo_b
    inputs: [missing.json]
    outputs: [b.json]
edges:
  - [a, b]
""",
        encoding="utf-8",
    )

    def echo_a(ctx: NodeContext) -> None:
        (ctx.artifact_dir / "a.json").write_text("{}", encoding="utf-8")

    def echo_b(ctx: NodeContext) -> None:
        raise AssertionError("should not run")

    registry = NodeRegistry({"echo_a": echo_a, "echo_b": echo_b})
    runner = GraphRunner(registry=registry, artifacts_root=tmp_path / "artifacts")
    manifest = runner.run(load_graph(p), run_id="run2")
    statuses = {n.node_id: n.status for n in manifest.nodes}
    assert statuses["a"] == "succeeded"
    assert statuses["b"] == "failed"
