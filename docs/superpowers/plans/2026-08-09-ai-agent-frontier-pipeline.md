# AI Agent Frontier Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a GitHub Actions–scheduled workflow-graph pipeline that daily curates AI-agent GitHub repos into an Obsidian-style llm-wiki and each Friday produces a checker-gated frontier investment report (Markdown + HTML, best-effort PDF).

**Architecture:** Declarative YAML DAGs executed by a small Python graph runner; nodes exchange JSON/Markdown artifacts; Claude is the default LLM behind a provider interface; Actions commits `wiki/` and `reports/`.

**Tech Stack:** Python 3.12+, pydantic v2, PyYAML, httpx, anthropic SDK, pytest, GitHub Actions, Markdown→HTML (Python `markdown` or `mistune`), optional Chromium print for PDF.

**Spec:** `docs/superpowers/specs/2026-08-09-ai-agent-frontier-pipeline-design.md`

---

## File structure

| Path | Responsibility |
|------|----------------|
| `pyproject.toml` | Package metadata, deps, pytest config |
| `src/frontier_pipeline/__init__.py` | Package version |
| `src/frontier_pipeline/schemas.py` | Pydantic models for all artifacts |
| `src/frontier_pipeline/graph/model.py` | Graph YAML dataclasses/models |
| `src/frontier_pipeline/graph/loader.py` | Load + validate graph YAML |
| `src/frontier_pipeline/graph/runner.py` | Topological execution + manifest |
| `src/frontier_pipeline/llm/base.py` | `LLMProvider` protocol |
| `src/frontier_pipeline/llm/anthropic_provider.py` | Claude implementation |
| `src/frontier_pipeline/llm/fake.py` | Deterministic fake for tests |
| `src/frontier_pipeline/nodes/registry.py` | `uses` name → callable map |
| `src/frontier_pipeline/nodes/github_ingest.py` | GitHub search → `repos.json` |
| `src/frontier_pipeline/nodes/wiki_curate.py` | Upsert wiki Markdown |
| `src/frontier_pipeline/nodes/pipeline_check.py` | Soft daily integrity check |
| `src/frontier_pipeline/nodes/invest_scan.py` | Public web investment cards |
| `src/frontier_pipeline/nodes/frontier_report.py` | Ranked report draft |
| `src/frontier_pipeline/nodes/checker.py` | Hard/soft verification |
| `src/frontier_pipeline/nodes/render_share.py` | HTML (+ optional PDF) |
| `src/frontier_pipeline/wiki_bootstrap.py` | Seed wiki tree + style guide |
| `src/frontier_pipeline/cli.py` | `frontier-pipeline run --graph ...` |
| `graphs/daily_ingest.yaml` | Daily DAG |
| `graphs/friday_report.yaml` | Friday DAG |
| `wiki/**` | Obsidian-style llm-wiki |
| `reports/.gitkeep` | Published outputs root |
| `.github/workflows/ci.yml` | PR tests |
| `.github/workflows/daily.yml` | Daily cron |
| `.github/workflows/friday.yml` | Friday cron |
| `.gitignore` | `artifacts/`, `.venv/`, etc. |
| `tests/**` | Unit + fixture integration |

---

### Task 1: Project skeleton

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/frontier_pipeline/__init__.py`
- Create: `reports/.gitkeep`
- Create: `artifacts/.gitkeep` (file tracked only as reminder; directory contents ignored)
- Test: `tests/test_package_imports.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_package_imports.py
def test_package_version():
    import frontier_pipeline

    assert frontier_pipeline.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_package_imports.py -v`  
Expected: FAIL (package/module not found or no `__version__`)

- [ ] **Step 3: Write minimal project files**

```toml
# pyproject.toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "frontier-pipeline"
version = "0.1.0"
description = "Workflow-graph pipeline for AI-agent GitHub curation and Friday frontier reports"
readme = "README.md"
requires-python = ">=3.12"
dependencies = [
  "pydantic>=2.7",
  "pyyaml>=6.0",
  "httpx>=0.27",
  "anthropic>=0.34",
  "markdown>=3.6",
  "python-dateutil>=2.9",
]

[project.optional-dependencies]
dev = ["pytest>=8.2", "pytest-asyncio>=0.23"]

[project.scripts]
frontier-pipeline = "frontier_pipeline.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/frontier_pipeline"]

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

```gitignore
# .gitignore
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
.mypy_cache/
artifacts/*/
!artifacts/.gitkeep
.DS_Store
*.html
!tests/fixtures/**/*.html
```

```python
# src/frontier_pipeline/__init__.py
__version__ = "0.1.0"
```

Create empty `reports/.gitkeep` and `artifacts/.gitkeep`. Add a short `README.md` stating the product purpose and pointing at the design spec.

- [ ] **Step 4: Install and run test**

Run:
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/test_package_imports.py -v
```
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore README.md src/frontier_pipeline/__init__.py reports/.gitkeep artifacts/.gitkeep tests/test_package_imports.py
git commit -m "chore: scaffold frontier-pipeline Python package"
```

---

### Task 2: Artifact schemas

**Files:**
- Create: `src/frontier_pipeline/schemas.py`
- Test: `tests/test_schemas.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_schemas.py
from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from frontier_pipeline.schemas import (
    CheckResult,
    InvestmentCard,
    RepoCard,
    ReportDocument,
)


def test_repo_card_roundtrip():
    card = RepoCard(
        id="owner/repo",
        url="https://github.com/owner/repo",
        stars=100,
        topics=["ai-agents"],
        summary="An agent framework",
        fetched_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
    )
    assert card.model_dump()["id"] == "owner/repo"


def test_investment_card_requires_source_url():
    with pytest.raises(ValidationError):
        InvestmentCard(
            headline="AI funding",
            themes=["agents"],
            actors=["Acme"],
            source_url="",
            date=date(2026, 8, 8),
        )


def test_check_result_hard_fail_blocks_share():
    result = CheckResult(
        hard_pass=False,
        soft_pass=True,
        issues=[{"severity": "hard", "code": "ungrounded", "message": "claim lacks citation"}],
    )
    assert result.hard_pass is False
    assert result.allows_render is False


def test_report_document_requires_citations_on_claims():
    doc = ReportDocument(
        title="Frontier Report",
        report_date=date(2026, 8, 8),
        ranked_projects=[
            {
                "repo_id": "owner/repo",
                "rank": 1,
                "rationale": "Matches agent infra theme",
                "business_case": "Sell agent ops tooling",
                "citations": ["https://example.com/a", "wiki/projects/owner-repo.md"],
            }
        ],
        claims=[
            {
                "text": "Funding into agent infra rose",
                "citations": ["https://example.com/a"],
            }
        ],
    )
    assert doc.ranked_projects[0].rank == 1
```

- [ ] **Step 2: Run tests — expect FAIL (import error)**

Run: `pytest tests/test_schemas.py -v`  
Expected: FAIL module not found

- [ ] **Step 3: Implement schemas**

```python
# src/frontier_pipeline/schemas.py
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator


class RepoCard(BaseModel):
    id: str
    url: str
    stars: int = Field(ge=0)
    topics: list[str] = Field(default_factory=list)
    summary: str = ""
    fetched_at: datetime
    recent_activity_score: float = 0.0


class InvestmentCard(BaseModel):
    headline: str
    themes: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    source_url: str
    date: date

    @field_validator("source_url")
    @classmethod
    def non_empty_url(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source_url is required")
        return v


class ReportClaim(BaseModel):
    text: str
    citations: list[str] = Field(min_length=1)


class RankedProject(BaseModel):
    repo_id: str
    rank: int = Field(ge=1)
    rationale: str
    business_case: str
    citations: list[str] = Field(min_length=1)


class ReportDocument(BaseModel):
    title: str
    report_date: date
    ranked_projects: list[RankedProject]
    claims: list[ReportClaim] = Field(default_factory=list)


class CheckIssue(BaseModel):
    severity: Literal["hard", "soft"]
    code: str
    message: str


class CheckResult(BaseModel):
    hard_pass: bool
    soft_pass: bool
    issues: list[CheckIssue] = Field(default_factory=list)

    @property
    def allows_render(self) -> bool:
        return self.hard_pass


class NodeStatus(BaseModel):
    node_id: str
    status: Literal["pending", "running", "succeeded", "failed", "skipped"]
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class RunManifest(BaseModel):
    run_id: str
    graph_name: str
    started_at: datetime
    finished_at: datetime | None = None
    nodes: list[NodeStatus] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_schemas.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/frontier_pipeline/schemas.py tests/test_schemas.py
git commit -m "feat: add pydantic artifact schemas"
```

---

### Task 3: Graph loader and validation

**Files:**
- Create: `src/frontier_pipeline/graph/__init__.py`
- Create: `src/frontier_pipeline/graph/model.py`
- Create: `src/frontier_pipeline/graph/loader.py`
- Test: `tests/test_graph_loader.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_graph_loader.py
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
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_graph_loader.py -v`

- [ ] **Step 3: Implement model + loader**

```python
# src/frontier_pipeline/graph/model.py
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
```

```python
# src/frontier_pipeline/graph/loader.py
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
```

```python
# src/frontier_pipeline/graph/__init__.py
from frontier_pipeline.graph.loader import GraphValidationError, load_graph
from frontier_pipeline.graph.model import GraphNode, WorkflowGraph

__all__ = ["GraphValidationError", "load_graph", "GraphNode", "WorkflowGraph"]
```

- [ ] **Step 4: Run tests — expect PASS**

Run: `pytest tests/test_graph_loader.py -v`

- [ ] **Step 5: Commit**

```bash
git add src/frontier_pipeline/graph tests/test_graph_loader.py
git commit -m "feat: add workflow graph loader and validation"
```

---

### Task 4: Graph runner + manifest

**Files:**
- Create: `src/frontier_pipeline/graph/runner.py`
- Create: `src/frontier_pipeline/nodes/registry.py`
- Test: `tests/test_graph_runner.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_graph_runner.py
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
    def echo_a(ctx: NodeContext) -> None:
        # deliberately do not write a.json
        return

    def echo_b(ctx: NodeContext) -> None:
        raise AssertionError("should not run")

    registry = NodeRegistry({"echo_a": echo_a, "echo_b": echo_b})
    runner = GraphRunner(registry=registry, artifacts_root=tmp_path / "artifacts")
    manifest = runner.run(load_graph(_write_sample(tmp_path)), run_id="run2")
    statuses = {n.node_id: n.status for n in manifest.nodes}
    assert statuses["a"] == "succeeded"
    assert statuses["b"] == "failed"
```

- [ ] **Step 2: Run tests — expect FAIL**

Run: `pytest tests/test_graph_runner.py -v`

- [ ] **Step 3: Implement registry + runner**

```python
# src/frontier_pipeline/nodes/registry.py
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

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
```

```python
# src/frontier_pipeline/graph/runner.py
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from frontier_pipeline.graph.model import WorkflowGraph
from frontier_pipeline.nodes.registry import NodeContext, NodeRegistry
from frontier_pipeline.schemas import NodeStatus, RunManifest
from frontier_pipeline.llm.base import LLMProvider


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
                    if out.endswith(".json") or out.endswith(".md") or out.endswith(".html"):
                        if not (artifact_dir / out).exists() and not (
                            self.repo_root / out
                        ).exists():
                            # outputs may be written under artifact_dir by convention
                            if not (artifact_dir / out).exists():
                                raise FileNotFoundError(f"missing output: {out}")
                status.status = "succeeded"
                if node.uses == "checker":
                    check_path = artifact_dir / "check.json"
                    data = json.loads(check_path.read_text(encoding="utf-8"))
                    check_hard_pass = bool(data.get("hard_pass"))
                    if node.on_hard_fail == "stop" and not check_hard_pass:
                        manifest.nodes.append(status)
                        # mark remaining as skipped after break
                        manifest.finished_at = datetime.now(timezone.utc)
                        self._write_manifest(artifact_dir, manifest)
                        # continue loop will skip render via requires_check
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
```

Also add a minimal `src/frontier_pipeline/llm/base.py` so imports resolve:

```python
# src/frontier_pipeline/llm/base.py
from __future__ import annotations

from typing import Any, Protocol


class LLMProvider(Protocol):
    def complete(self, prompt: str, *, system: str | None = None) -> str: ...

    def complete_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]: ...
```

```python
# src/frontier_pipeline/llm/__init__.py
```

- [ ] **Step 4: Fix output-existence check to artifact_dir only**

In the runner, require each declared `outputs` filename to exist under `artifact_dir` after the node runs (nodes that write into `wiki/` should still emit a small sentinel JSON under `artifact_dir`, e.g. `wiki_done.json`). Update the test helpers accordingly if needed. Re-run until PASS.

- [ ] **Step 5: Commit**

```bash
git add src/frontier_pipeline/graph/runner.py src/frontier_pipeline/nodes/registry.py src/frontier_pipeline/llm tests/test_graph_runner.py
git commit -m "feat: add graph runner with run manifests"
```

---

### Task 5: LLM provider interface + fake + Anthropic

**Files:**
- Create: `src/frontier_pipeline/llm/fake.py`
- Create: `src/frontier_pipeline/llm/anthropic_provider.py`
- Create: `src/frontier_pipeline/llm/factory.py`
- Test: `tests/test_llm_providers.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_llm_providers.py
import json

from frontier_pipeline.llm.fake import FakeLLMProvider
from frontier_pipeline.llm.factory import get_provider


def test_fake_complete_json():
    fake = FakeLLMProvider(json_responses=[{"ok": True}])
    assert fake.complete_json("hi") == {"ok": True}


def test_factory_defaults_to_fake_without_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("FRONTIER_LLM_PROVIDER", "fake")
    provider = get_provider()
    assert provider.complete("x") == "fake-response"
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement**

```python
# src/frontier_pipeline/llm/fake.py
from __future__ import annotations

import json
from typing import Any


class FakeLLMProvider:
    def __init__(
        self,
        text_responses: list[str] | None = None,
        json_responses: list[dict[str, Any]] | None = None,
    ) -> None:
        self._text = list(text_responses or ["fake-response"])
        self._json = list(json_responses or [{"ok": True}])

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        return self._text.pop(0) if len(self._text) > 1 else self._text[0]

    def complete_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        data = self._json.pop(0) if len(self._json) > 1 else self._json[0]
        return dict(data)
```

```python
# src/frontier_pipeline/llm/anthropic_provider.py
from __future__ import annotations

import json
import re
from typing import Any

from anthropic import Anthropic


class AnthropicProvider:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514") -> None:
        self.client = Anthropic(api_key=api_key)
        self.model = model

    def complete(self, prompt: str, *, system: str | None = None) -> str:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            kwargs["system"] = system
        msg = self.client.messages.create(**kwargs)
        return "".join(b.text for b in msg.content if hasattr(b, "text"))

    def complete_json(self, prompt: str, *, system: str | None = None) -> dict[str, Any]:
        text = self.complete(
            prompt + "\n\nRespond with a single JSON object only.",
            system=system,
        )
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise ValueError("no JSON object in model response")
        return json.loads(match.group(0))
```

```python
# src/frontier_pipeline/llm/factory.py
from __future__ import annotations

import os
from typing import Any

from frontier_pipeline.llm.anthropic_provider import AnthropicProvider
from frontier_pipeline.llm.fake import FakeLLMProvider


def get_provider(name: str | None = None) -> Any:
    chosen = (name or os.getenv("FRONTIER_LLM_PROVIDER") or "anthropic").lower()
    if chosen == "fake":
        return FakeLLMProvider()
    if chosen == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for anthropic provider")
        return AnthropicProvider(api_key=key)
    raise RuntimeError(f"unknown provider: {chosen}")
```

- [ ] **Step 4: Run tests — PASS**

- [ ] **Step 5: Commit**

```bash
git add src/frontier_pipeline/llm tests/test_llm_providers.py
git commit -m "feat: add provider-agnostic LLM interface with Claude default"
```

---

### Task 6: Wiki bootstrap

**Files:**
- Create: `src/frontier_pipeline/wiki_bootstrap.py`
- Create: `wiki/index.md`, `wiki/STYLE.md`, and directory placeholders via bootstrap
- Test: `tests/test_wiki_bootstrap.py`
- Create: `src/frontier_pipeline/cli.py` (bootstrap + run commands)

- [ ] **Step 1: Write failing test**

```python
# tests/test_wiki_bootstrap.py
from pathlib import Path

from frontier_pipeline.wiki_bootstrap import bootstrap_wiki


def test_bootstrap_creates_structure(tmp_path: Path):
    wiki = tmp_path / "wiki"
    bootstrap_wiki(wiki)
    assert (wiki / "index.md").exists()
    assert (wiki / "STYLE.md").exists()
    for d in ("projects", "themes", "investments", "reports"):
        assert (wiki / d).is_dir()
        assert (wiki / d / ".gitkeep").exists()
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement bootstrap + CLI entry**

```python
# src/frontier_pipeline/wiki_bootstrap.py
from __future__ import annotations

from pathlib import Path

INDEX = """# LLM Wiki

Home for AI-agent project curation and Friday frontier reports.

## Sections
- [[projects/]] — GitHub projects
- [[themes/]] — recurring themes
- [[investments/]] — investment cards (summaries)
- [[reports/]] — published Friday reports
"""

STYLE = """# Wiki style guide

## Project pages (`projects/<owner>-<repo>.md`)
Front matter:
```yaml
---
repo_id: owner/repo
url: https://github.com/owner/repo
stars: 0
topics: []
updated: YYYY-MM-DD
---
```
Body: short summary, why it matters for agents, links to themes.

## Linking
Use Obsidian wikilinks between projects and themes.
"""


def bootstrap_wiki(wiki_root: Path) -> None:
    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "index.md").write_text(INDEX, encoding="utf-8")
    (wiki_root / "STYLE.md").write_text(STYLE, encoding="utf-8")
    for name in ("projects", "themes", "investments", "reports"):
        d = wiki_root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch()
```

```python
# src/frontier_pipeline/cli.py
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from frontier_pipeline.graph.loader import load_graph
from frontier_pipeline.graph.runner import GraphRunner
from frontier_pipeline.llm.factory import get_provider
from frontier_pipeline.nodes.registry import build_default_registry
from frontier_pipeline.wiki_bootstrap import bootstrap_wiki


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="frontier-pipeline")
    sub = parser.add_subparsers(dest="cmd", required=True)

    boot = sub.add_parser("bootstrap-wiki")
    boot.add_argument("--wiki", type=Path, default=Path("wiki"))

    run = sub.add_parser("run")
    run.add_argument("--graph", type=Path, required=True)
    run.add_argument("--repo-root", type=Path, default=Path.cwd())
    run.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    run.add_argument("--run-id", type=str, default="")
    run.add_argument(
        "--llm",
        type=str,
        default=None,
        help="Provider name: anthropic|fake (default: FRONTIER_LLM_PROVIDER or anthropic)",
    )

    args = parser.parse_args(argv)
    if args.cmd == "bootstrap-wiki":
        bootstrap_wiki(args.wiki)
        return
    if args.cmd == "run":
        run_id = args.run_id or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        provider = get_provider(args.llm)
        runner = GraphRunner(
            registry=build_default_registry(),
            artifacts_root=args.artifacts,
            repo_root=args.repo_root,
            llm=provider,
        )
        manifest = runner.run(load_graph(args.graph), run_id=run_id)
        failed = [n for n in manifest.nodes if n.status == "failed"]
        if failed:
            raise SystemExit(1)
        return
    raise SystemExit(2)


if __name__ == "__main__":
    main()
```

Also add to `registry.py` in this task:

```python
def build_default_registry() -> NodeRegistry:
    return NodeRegistry({})
```

Extend `build_default_registry` in later tasks as each node lands. For local/CI without keys, run with `--llm fake`.

- [ ] **Step 4: Run bootstrap into repo + test**

```bash
pytest tests/test_wiki_bootstrap.py -v
frontier-pipeline bootstrap-wiki --wiki wiki
```

- [ ] **Step 5: Commit**

```bash
git add src/frontier_pipeline/wiki_bootstrap.py src/frontier_pipeline/cli.py wiki tests/test_wiki_bootstrap.py
git commit -m "feat: bootstrap Obsidian-style llm-wiki"
```

---

### Task 7: `github_ingest` node

**Files:**
- Create: `src/frontier_pipeline/nodes/github_ingest.py`
- Create: `src/frontier_pipeline/github_client.py`
- Modify: `src/frontier_pipeline/nodes/registry.py` (`build_default_registry`)
- Test: `tests/test_github_ingest.py`

- [ ] **Step 1: Write failing tests with httpx mock transport**

```python
# tests/test_github_ingest.py
import json
from pathlib import Path

import httpx

from frontier_pipeline.graph.model import GraphNode
from frontier_pipeline.nodes.github_ingest import run_github_ingest
from frontier_pipeline.nodes.registry import NodeContext


def test_github_ingest_writes_repo_cards(tmp_path: Path):
    payload = {
        "items": [
            {
                "full_name": "acme/agentkit",
                "html_url": "https://github.com/acme/agentkit",
                "stargazers_count": 1200,
                "description": "LLM agents toolkit",
                "topics": ["ai-agents"],
                "pushed_at": "2026-08-08T00:00:00Z",
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    ctx = NodeContext(
        node=GraphNode(id="github_ingest", uses="github_ingest", outputs=["repos.json"]),
        artifact_dir=tmp_path,
        repo_root=tmp_path,
        llm=None,
    )
    run_github_ingest(ctx, client=client, per_page=10)
    data = json.loads((tmp_path / "repos.json").read_text(encoding="utf-8"))
    assert data[0]["id"] == "acme/agentkit"
    assert data[0]["stars"] == 1200
```

- [ ] **Step 2: Run — FAIL**

- [ ] **Step 3: Implement**

Query GitHub search: topics `ai-agents`, `llm-agents`, `autonomous-agents`, `agentic` (union via multiple queries or topic OR query), sort by stars, merge/dedupe by `full_name`, compute a simple `recent_activity_score` from `pushed_at`, take top N (default 25). Use `GITHUB_TOKEN` header when present. Write `repos.json` as a JSON list of `RepoCard` dumps.

Wire `build_default_registry()` to include `"github_ingest": run_github_ingest`.

- [ ] **Step 4: Tests PASS**

- [ ] **Step 5: Commit**

```bash
git commit -am "feat: add github_ingest node for AI-agent repos"
```

---

### Task 8: `wiki_curate` node

**Files:**
- Create: `src/frontier_pipeline/nodes/wiki_curate.py`
- Modify: `src/frontier_pipeline/nodes/registry.py`
- Test: `tests/test_wiki_curate.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_wiki_curate.py
import json
from datetime import datetime, timezone
from pathlib import Path

from frontier_pipeline.graph.model import GraphNode
from frontier_pipeline.nodes.registry import NodeContext
from frontier_pipeline.nodes.wiki_curate import run_wiki_curate
from frontier_pipeline.wiki_bootstrap import bootstrap_wiki


def test_wiki_curate_upserts_project_page(tmp_path: Path):
    wiki = tmp_path / "wiki"
    bootstrap_wiki(wiki)
    artifact_dir = tmp_path / "artifacts"
    artifact_dir.mkdir()
    repos = [
        {
            "id": "acme/agentkit",
            "url": "https://github.com/acme/agentkit",
            "stars": 1200,
            "topics": ["ai-agents"],
            "summary": "LLM agents toolkit",
            "fetched_at": datetime(2026, 8, 9, tzinfo=timezone.utc).isoformat(),
            "recent_activity_score": 1.0,
        }
    ]
    (artifact_dir / "repos.json").write_text(json.dumps(repos), encoding="utf-8")
    ctx = NodeContext(
        node=GraphNode(
            id="wiki_curate",
            uses="wiki_curate",
            inputs=["repos.json"],
            outputs=["wiki_done.json"],
        ),
        artifact_dir=artifact_dir,
        repo_root=tmp_path,
        llm=None,
    )
    run_wiki_curate(ctx)
    page = wiki / "projects" / "acme-agentkit.md"
    assert page.exists()
    text = page.read_text(encoding="utf-8")
    assert "acme/agentkit" in text
    assert "[[themes/ai-agents]]" in text or "ai-agents" in text
    assert (wiki / "themes" / "ai-agents.md").exists()
    assert (artifact_dir / "wiki_done.json").exists()
    assert "acme-agentkit" in (wiki / "index.md").read_text(encoding="utf-8")
```

- [ ] **Step 2: Run — expect FAIL**

Run: `pytest tests/test_wiki_curate.py -v`

- [ ] **Step 3: Implement `run_wiki_curate`**

- Read `repos.json`, validate each item as `RepoCard`.
- Path: `wiki/projects/{owner}-{repo}.md` (slash → dash).
- Write YAML front matter (`repo_id`, `url`, `stars`, `topics`, `updated`) + summary body + theme wikilinks.
- Ensure `wiki/themes/{topic}.md` stub exists with backlink list entry.
- Append/update a bullet in `wiki/index.md` under a `## Projects` section.
- Write `wiki_done.json` as `{"updated": [...repo ids...]}`.
- Register `"wiki_curate": run_wiki_curate` in `build_default_registry`.

- [ ] **Step 4: Tests PASS; commit**

```bash
git add src/frontier_pipeline/nodes/wiki_curate.py src/frontier_pipeline/nodes/registry.py tests/test_wiki_curate.py
git commit -m "feat: curate GitHub repos into llm-wiki markdown"
```
---

### Task 9: Soft `pipeline_check` + daily graph YAML

**Files:**
- Create: `src/frontier_pipeline/nodes/pipeline_check.py`
- Create: `graphs/daily_ingest.yaml`
- Test: `tests/test_pipeline_check.py`
- Test: `tests/test_daily_graph_fixture.py`

- [ ] **Step 1: Tests** — soft warnings when `repos.json` missing from manifest outputs; success path writes `pipeline_check.json` with `soft_pass: true` and does not raise.

- [ ] **Step 2: Create graph**

```yaml
# graphs/daily_ingest.yaml
name: daily_ingest
nodes:
  - id: github_ingest
    uses: github_ingest
    outputs: [repos.json]
  - id: wiki_curate
    uses: wiki_curate
    inputs: [repos.json]
    outputs: [wiki_done.json]
  - id: pipeline_check
    uses: pipeline_check
    inputs: [repos.json, wiki_done.json]
    outputs: [pipeline_check.json]
edges:
  - [github_ingest, wiki_curate]
  - [wiki_curate, pipeline_check]
```

- [ ] **Step 3: Fixture integration** — `tests/fixtures/daily/` with mocked GitHub transport via monkeypatch; run full graph with FakeLLM; assert wiki page exists.

- [ ] **Step 4: Commit**

```bash
git commit -am "feat: add daily_ingest graph and soft pipeline_check"
```

---

### Task 10: Daily GitHub Actions workflow

**Files:**
- Create: `.github/workflows/daily.yml`
- Create: `.github/workflows/ci.yml`

- [ ] **Step 1: CI workflow** — on PR/push: setup Python 3.12, `pip install -e ".[dev]"`, `pytest`.

- [ ] **Step 2: Daily workflow**

```yaml
name: daily-ingest
on:
  schedule:
    - cron: "0 6 * * *"  # 06:00 UTC daily
  workflow_dispatch:
concurrency:
  group: daily-ingest
  cancel-in-progress: false
jobs:
  run:
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install -e ".[dev]"
      - env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          FRONTIER_LLM_PROVIDER: anthropic
        run: frontier-pipeline run --graph graphs/daily_ingest.yaml
      - name: Commit wiki
        run: |
          git config user.name "frontier-bot"
          git config user.email "frontier-bot@users.noreply.github.com"
          git add wiki
          git diff --staged --quiet || git commit -m "chore(wiki): daily AI-agent curation"
          git push
```

- [ ] **Step 3: Commit workflows**

```bash
git add .github/workflows
git commit -m "ci: add PR tests and daily ingest workflow"
```

---

### Task 11: `invest_scan` node

**Files:**
- Create: `src/frontier_pipeline/nodes/invest_scan.py`
- Test: `tests/test_invest_scan.py`

- [ ] **Step 1: Failing test with MockTransport** returning HTML/RSS fixtures for Bloomberg tech + TechCrunch funding pages; assert `investments.json` cards have non-empty `source_url` and themes.

- [ ] **Step 2: Implement** — fetch configured feed/list URLs (constants in module), parse titles/links/dates conservatively (BeautifulSoup optional; prefer stdlib `html.parser` + RSS `feedparser` if added to deps — **add `feedparser` to `pyproject.toml`**), map into `InvestmentCard`, optionally use LLM to extract themes/actors via `complete_json` with Fake in tests.

- [ ] **Step 3: Register; PASS; commit**

```bash
git commit -am "feat: add invest_scan public-web investment cards"
```

---

### Task 12: `frontier_report` node

**Files:**
- Create: `src/frontier_pipeline/nodes/frontier_report.py`
- Test: `tests/test_frontier_report.py`

- [ ] **Step 1: Failing test** — fixture `investments.json` + wiki project pages → writes `report.json` validating as `ReportDocument` and `report.md` containing rankings and citation URLs.

- [ ] **Step 2: Implement** — gather wiki project Markdown; prompt LLM for ranking + business cases **requiring** citations from provided investment URLs and wiki paths; validate with Pydantic; on schema failure, one repair prompt then fail. Also write copies toward `reports/drafts/` only in Friday orchestration helper or leave placement to checker/render tasks — **node writes artifact_dir files only**; CLI/Actions copy on success.

- [ ] **Step 3: Commit**

```bash
git commit -am "feat: generate frontier report from wiki and investments"
```

---

### Task 13: `checker` node

**Files:**
- Create: `src/frontier_pipeline/nodes/checker.py`
- Modify: `src/frontier_pipeline/nodes/registry.py`
- Test: `tests/test_checker.py`

- [ ] **Step 1: Write failing tests**

```python
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
```

- [ ] **Step 2: Run — expect FAIL**

- [ ] **Step 3: Implement deterministic checker**

Rules:
1. **Grounding (hard):** every claim and ranked-project citation must appear in the allowed set = investment `source_url`s ∪ existing wiki-relative paths referenced in the report inputs.
2. **Investment logic (hard):** for each ranked project, tokenize investment themes + project rationale/business_case; require non-empty overlap with at least one investment theme token (casefold, length>3), else `investment_logic`.
3. **Pipeline integrity (soft):** if `manifest.json` present, require nodes `invest_scan`, `frontier_report` succeeded; missing/failed → soft issue `pipeline_integrity`.
4. Write `CheckResult` to `check.json`. Do not raise on hard fail (runner reads `hard_pass`).

Register `"checker": run_checker`.

- [ ] **Step 4: Tests PASS; commit**

```bash
git add src/frontier_pipeline/nodes/checker.py src/frontier_pipeline/nodes/registry.py tests/test_checker.py
git commit -m "feat: add checker agent with hard and soft gates"
```
---

### Task 14: `render_share` + Friday graph

**Files:**
- Create: `src/frontier_pipeline/nodes/render_share.py`
- Create: `graphs/friday_report.yaml`
- Test: `tests/test_render_share.py`
- Test: `tests/test_friday_graph_fixture.py`

- [ ] **Step 1: Render test** — Markdown → HTML file in artifact_dir; assert `<html` present.

- [ ] **Step 2: Friday YAML**

```yaml
name: friday_report
nodes:
  - id: invest_scan
    uses: invest_scan
    outputs: [investments.json]
  - id: frontier_report
    uses: frontier_report
    inputs: [investments.json]
    outputs: [report.md, report.json]
  - id: checker
    uses: checker
    inputs: [report.md, report.json, investments.json]
    outputs: [check.json]
    on_hard_fail: stop
  - id: render_share
    uses: render_share
    inputs: [report.md, check.json]
    outputs: [report.html]
    requires_check: hard_pass
edges:
  - [invest_scan, frontier_report]
  - [frontier_report, checker]
  - [checker, render_share]
```

- [ ] **Step 3: Fixture Friday graph** with fake HTTP + FakeLLM producing grounded report; assert HTML written. Second case: ungrounded report → render skipped, `check.json` hard_pass false.

- [ ] **Step 4: Optional PDF** — if `FRONTIER_PDF=1` and `playwright` available, print PDF; otherwise skip without failing. Document in README.

- [ ] **Step 5: Commit**

```bash
git commit -am "feat: friday_report graph with checker-gated HTML render"
```

---

### Task 15: Friday Actions + publish paths

**Files:**
- Create: `.github/workflows/friday.yml`
- Modify: `src/frontier_pipeline/cli.py` (after run, copy artifacts to `reports/` / `wiki/reports/` / `reports/drafts/` based on check)

- [ ] **Step 1: Post-run publish helper** `src/frontier_pipeline/publish.py`:
  - If `check.json` hard_pass: copy `report.md` → `reports/YYYY-MM-DD.md` and `wiki/reports/YYYY-MM-DD.md`; copy `report.html` → `reports/YYYY-MM-DD.html`
  - Else: copy draft + check → `reports/drafts/YYYY-MM-DD/`

- [ ] **Step 2: Friday workflow** — cron `0 7 * * 5` (Friday 07:00 UTC), concurrency group `friday-report`, run graph, publish, commit `wiki` + `reports`, exit 1 on hard fail after commit of drafts.

- [ ] **Step 3: Manual smoke workflow_dispatch inputs** `live=true` using real keys with `TOP_N=5`.

- [ ] **Step 4: Commit**

```bash
git commit -am "ci: add Friday report workflow and publish helper"
```

---

### Task 16: End-to-end hardening

**Files:**
- Modify: runner retries for httpx (shared `src/frontier_pipeline/http_util.py` with 3-attempt backoff)
- Modify: nodes to use retry helper
- Test: `tests/test_http_retry.py`
- Update: README with secrets, local commands, schedule

- [ ] **Step 1: Retry helper tests** — first two calls 429 with Retry-After, third 200.

- [ ] **Step 2: Wire into GitHub + invest fetch paths.

- [ ] **Step 3: Full offline pytest suite green.

- [ ] **Step 4: Commit**

```bash
git commit -am "fix: add HTTP retry/backoff and finalize README"
```

---

## Self-review (plan vs spec)

| Spec requirement | Task(s) |
|------------------|---------|
| Daily GitHub AI-agent ingest | 7, 9, 10 |
| Markdown/Obsidian llm-wiki + bootstrap prerequisite | 6, 8 |
| Friday public-web investment scan | 11, 14, 15 |
| Frontier report + business cases | 12 |
| Checker hard grounding/logic + soft pipeline | 13, 9 |
| Workflow graph engineering | 3, 4, graphs in 9/14 |
| HTML + best-effort PDF share | 14 |
| GitHub Actions schedules + commits | 10, 15 |
| Provider-agnostic LLM, Claude default | 5 |
| Schemas, errors, retries, CI tests | 2, 4, 16, ci.yml |

No intentional TBD placeholders. Types align on `RepoCard`, `InvestmentCard`, `ReportDocument`, `CheckResult`, `NodeContext`, `RunManifest`.

---

## Execution handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-09-ai-agent-frontier-pipeline.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration  
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints  

Which approach?
