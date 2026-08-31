from __future__ import annotations

from pathlib import Path

import yaml

from frontier_pipeline.graph.model import GraphNode, WorkflowGraph


class GraphValidationError(ValueError):
    pass


def load_graph(path: Path) -> WorkflowGraph:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise GraphValidationError("graph root must be a mapping")

    nodes = [GraphNode.model_validate(n) for n in raw.get("nodes", [])]
    edges_raw = raw.get("edges", [])
    edges: list[tuple[str, str]] = []
    for e in edges_raw:
        if not (isinstance(e, (list, tuple)) and len(e) == 2):
            raise GraphValidationError(f"invalid edge: {e!r}")
        edges.append((str(e[0]), str(e[1])))

    graph = WorkflowGraph(name=str(raw.get("name", "")), nodes=nodes, edges=edges)
    _validate(graph)
    return graph


def _validate(graph: WorkflowGraph) -> None:
    if not graph.name:
        raise GraphValidationError("graph name is required")
    ids = [n.id for n in graph.nodes]
    if len(ids) != len(set(ids)):
        raise GraphValidationError("duplicate node ids")
    id_set = set(ids)
    for a, b in graph.edges:
        if a not in id_set or b not in id_set:
            raise GraphValidationError(f"unknown edge endpoint in {[a, b]}")
    # Kahn cycle detection
    incoming = {i: 0 for i in ids}
    adj: dict[str, list[str]] = {i: [] for i in ids}
    for a, b in graph.edges:
        adj[a].append(b)
        incoming[b] += 1
    queue = [i for i, c in incoming.items() if c == 0]
    seen = 0
    while queue:
        n = queue.pop()
        seen += 1
        for m in adj[n]:
            incoming[m] -= 1
            if incoming[m] == 0:
                queue.append(m)
    if seen != len(ids):
        raise GraphValidationError("cycle detected in graph")
