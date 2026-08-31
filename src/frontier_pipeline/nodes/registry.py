from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from frontier_pipeline.graph.model import GraphNode
from frontier_pipeline.llm.base import LLMProvider


@dataclass
class NodeContext:
    node: GraphNode
    artifact_dir: Path
    repo_root: Path
    llm: LLMProvider | None
    check_hard_pass: bool | None = None


NodeFn = Callable[[NodeContext], None]


class NodeRegistry:
    def __init__(self, mapping: dict[str, NodeFn] | None = None) -> None:
        self._mapping = dict(mapping or {})

    def register(self, name: str, fn: NodeFn) -> None:
        self._mapping[name] = fn

    def get(self, name: str) -> NodeFn:
        if name not in self._mapping:
            raise KeyError(f"unknown node uses={name!r}")
        return self._mapping[name]


def build_default_registry() -> NodeRegistry:
    from frontier_pipeline.nodes.checker import checker_node
    from frontier_pipeline.nodes.frontier_report import frontier_report_node
    from frontier_pipeline.nodes.github_ingest import github_ingest_node
    from frontier_pipeline.nodes.invest_scan import invest_scan_node
    from frontier_pipeline.nodes.pipeline_check import pipeline_check_node
    from frontier_pipeline.nodes.render_share import render_share_node
    from frontier_pipeline.nodes.wiki_curate import wiki_curate_node

    return NodeRegistry(
        {
            "github_ingest": github_ingest_node,
            "invest_scan": invest_scan_node,
            "wiki_curate": wiki_curate_node,
            "frontier_report": frontier_report_node,
            "pipeline_check": pipeline_check_node,
            "checker": checker_node,
            "render_share": render_share_node,
        }
    )
