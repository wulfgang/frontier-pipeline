from __future__ import annotations

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    id: str
    uses: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    on_hard_fail: str | None = None  # "stop"
    requires_check: str | None = None  # "hard_pass"


class WorkflowGraph(BaseModel):
    name: str
    nodes: list[GraphNode]
    edges: list[tuple[str, str]] = Field(default_factory=list)
