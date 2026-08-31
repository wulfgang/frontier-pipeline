from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from frontier_pipeline.graph.model import WorkflowGraph
from frontier_pipeline.llm.base import LLMProvider
from frontier_pipeline.nodes.registry import NodeContext, NodeRegistry
from frontier_pipeline.schemas import NodeStatus, RunManifest


class GraphRunner:
    def __init__(
        self,
        registry: NodeRegistry,
        artifacts_root: Path,
        repo_root: Path | None = None,
        llm: LLMProvider | None = None,
    ) -> None:
        self.registry = registry
        self.artifacts_root = artifacts_root
        self.repo_root = repo_root or Path.cwd()
        self.llm = llm

    def run(self, graph: WorkflowGraph, run_id: str) -> RunManifest:
        artifact_dir = self.artifacts_root / run_id
        artifact_dir.mkdir(parents=True, exist_ok=True)
        started = datetime.now(timezone.utc)
        manifest = RunManifest(
            run_id=run_id,
            graph_name=graph.name,
            started_at=started,
            nodes=[],
        )
        order = self._topo(graph)
        node_by_id = {n.id: n for n in graph.nodes}
        check_hard_pass: bool | None = None

        for node_id in order:
            node = node_by_id[node_id]
            status = NodeStatus(
                node_id=node.id,
                status="running",
                inputs=list(node.inputs),
                outputs=list(node.outputs),
            )
            try:
                missing = [i for i in node.inputs if not (artifact_dir / i).exists()]
                if missing:
                    raise FileNotFoundError(f"missing inputs: {missing}")
                if node.requires_check == "hard_pass" and check_hard_pass is not True:
                    status.status = "skipped"
                    status.warnings.append("requires hard_pass check")
                    manifest.nodes.append(status)
                    self._write_manifest(artifact_dir, manifest)
                    continue
                fn = self.registry.get(node.uses)
                fn(
                    NodeContext(
                        node=node,
                        artifact_dir=artifact_dir,
                        repo_root=self.repo_root,
                        llm=self.llm,
                        check_hard_pass=check_hard_pass,
                    )
                )
                for out in node.outputs:
                    if not (artifact_dir / out).exists():
                        raise FileNotFoundError(f"missing output: {out}")
                status.status = "succeeded"
                if node.uses == "checker":
                    check_path = artifact_dir / "check.json"
                    data = json.loads(check_path.read_text(encoding="utf-8"))
                    check_hard_pass = bool(data.get("hard_pass"))
                    if node.on_hard_fail == "stop" and not check_hard_pass:
                        manifest.nodes.append(status)
                        manifest.finished_at = datetime.now(timezone.utc)
                        self._write_manifest(artifact_dir, manifest)
                        continue
            except Exception as exc:  # noqa: BLE001 - recorded in manifest
                status.status = "failed"
                status.error = str(exc)
                manifest.nodes.append(status)
                manifest.finished_at = datetime.now(timezone.utc)
                self._write_manifest(artifact_dir, manifest)
                return manifest
            manifest.nodes.append(status)
            self._write_manifest(artifact_dir, manifest)

        manifest.finished_at = datetime.now(timezone.utc)
        self._write_manifest(artifact_dir, manifest)
        return manifest

    def _write_manifest(self, artifact_dir: Path, manifest: RunManifest) -> None:
        path = artifact_dir / "manifest.json"
        path.write_text(manifest.model_dump_json(indent=2), encoding="utf-8")

    def _topo(self, graph: WorkflowGraph) -> list[str]:
        ids = [n.id for n in graph.nodes]
        incoming = {i: 0 for i in ids}
        adj: dict[str, list[str]] = {i: [] for i in ids}
        for a, b in graph.edges:
            adj[a].append(b)
            incoming[b] += 1
        queue = sorted(i for i, c in incoming.items() if c == 0)
        order: list[str] = []
        while queue:
            n = queue.pop(0)
            order.append(n)
            for m in sorted(adj[n]):
                incoming[m] -= 1
                if incoming[m] == 0:
                    queue.append(m)
        return order
