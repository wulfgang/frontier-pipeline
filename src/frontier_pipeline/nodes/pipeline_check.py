from __future__ import annotations

import json

from frontier_pipeline.nodes.registry import NodeContext
from frontier_pipeline.schemas import RepoCard


def _load_repos(artifact_dir, name: str) -> list[RepoCard]:
    raw = json.loads((artifact_dir / name).read_text(encoding="utf-8"))
    return [RepoCard.model_validate(item) for item in raw]


def _load_wiki_done(artifact_dir, name: str) -> dict:
    return json.loads((artifact_dir / name).read_text(encoding="utf-8"))


def _check_manifest(artifact_dir) -> list[str]:
    path = artifact_dir / "manifest.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    warnings: list[str] = []
    for node in data.get("nodes", []):
        if node.get("status") == "failed":
            node_id = node.get("node_id", "unknown")
            error = node.get("error") or "unknown error"
            warnings.append(f"manifest: node {node_id!r} failed: {error}")
    return warnings


def run_pipeline_check(ctx: NodeContext) -> None:
    inputs = ctx.node.inputs or ["repos.json", "wiki_done.json"]
    output_name = ctx.node.outputs[0] if ctx.node.outputs else "pipeline_check.json"
    warnings: list[str] = []

    repos_name = inputs[0]
    wiki_done_name = inputs[1] if len(inputs) > 1 else "wiki_done.json"

    repos = _load_repos(ctx.artifact_dir, repos_name)
    if not repos:
        warnings.append("repos.json is empty")

    wiki_done = _load_wiki_done(ctx.artifact_dir, wiki_done_name)
    updated = wiki_done.get("updated")
    if not updated:
        warnings.append("wiki_done.json has empty updated list")

    repo_ids = {card.id for card in repos}
    if updated:
        missing = [repo_id for repo_id in updated if repo_id not in repo_ids]
        if missing:
            warnings.append(f"wiki_done updated repos missing from repos.json: {missing}")

    warnings.extend(_check_manifest(ctx.artifact_dir))

    result = {"soft_pass": len(warnings) == 0, "warnings": warnings}
    out_path = ctx.artifact_dir / output_name
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")


def pipeline_check_node(ctx: NodeContext) -> None:
    run_pipeline_check(ctx)
