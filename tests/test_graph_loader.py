from pathlib import Path

import pytest

from frontier_pipeline.graph.loader import GraphValidationError, load_graph


def test_load_valid_linear_graph(tmp_path: Path):
    p = tmp_path / "g.yaml"
    p.write_text(
        """
name: sample
nodes:
  - id: a
    uses: github_ingest
    outputs: [repos.json]
  - id: b
    uses: wiki_curate
    inputs: [repos.json]
    outputs: [wiki_done.json]
edges:
  - [a, b]
""",
        encoding="utf-8",
    )
    g = load_graph(p)
    assert g.name == "sample"
    assert [n.id for n in g.nodes] == ["a", "b"]


def test_reject_cycle(tmp_path: Path):
    p = tmp_path / "cycle.yaml"
    p.write_text(
        """
name: cycle
nodes:
  - id: a
    uses: github_ingest
    outputs: [a.json]
  - id: b
    uses: wiki_curate
    inputs: [a.json]
    outputs: [b.json]
edges:
  - [a, b]
  - [b, a]
""",
        encoding="utf-8",
    )
    with pytest.raises(GraphValidationError, match="cycle"):
        load_graph(p)


def test_reject_unknown_edge_endpoint(tmp_path: Path):
    p = tmp_path / "bad.yaml"
    p.write_text(
        """
name: bad
nodes:
  - id: a
    uses: github_ingest
    outputs: [a.json]
edges:
  - [a, missing]
""",
        encoding="utf-8",
    )
    with pytest.raises(GraphValidationError, match="unknown"):
        load_graph(p)
