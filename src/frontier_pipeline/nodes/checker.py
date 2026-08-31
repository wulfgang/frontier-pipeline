from __future__ import annotations

import json
import re
from pathlib import Path

from frontier_pipeline.nodes.registry import NodeContext
from frontier_pipeline.schemas import (
    CheckIssue,
    CheckResult,
    InvestmentCard,
    ReportDocument,
)

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_REQUIRED_MANIFEST_NODES = ("invest_scan", "frontier_report")


def _tokenize(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.casefold()) if len(t) > 3}


def _load_report(artifact_dir: Path, name: str) -> ReportDocument:
    raw = json.loads((artifact_dir / name).read_text(encoding="utf-8"))
    return ReportDocument.model_validate(raw)


def _load_investments(artifact_dir: Path, name: str) -> list[InvestmentCard]:
    raw = json.loads((artifact_dir / name).read_text(encoding="utf-8"))
    return [InvestmentCard.model_validate(item) for item in raw]


def _wiki_paths_under(repo_root: Path) -> set[str]:
    wiki_root = repo_root / "wiki"
    if not wiki_root.is_dir():
        return set()
    paths: set[str] = set()
    for path in wiki_root.rglob("*"):
        if path.is_file():
            paths.add(path.relative_to(repo_root).as_posix())
    return paths


def _allowed_citations(
    investments: list[InvestmentCard], repo_root: Path
) -> set[str]:
    allowed = {card.source_url for card in investments}
    allowed |= _wiki_paths_under(repo_root)
    return allowed


def _citation_allowed(citation: str, allowed: set[str], repo_root: Path) -> bool:
    if citation in allowed:
        return True
    return (repo_root / citation).is_file()


def _check_grounding(
    report: ReportDocument, allowed: set[str], repo_root: Path
) -> list[CheckIssue]:
    issues: list[CheckIssue] = []
    citations: list[tuple[str, str]] = []
    for claim in report.claims:
        for citation in claim.citations:
            citations.append(("claim", citation))
    for project in report.ranked_projects:
        for citation in project.citations:
            citations.append((f"ranked project {project.repo_id!r}", citation))
    for where, citation in citations:
        if not _citation_allowed(citation, allowed, repo_root):
            issues.append(
                CheckIssue(
                    severity="hard",
                    code="ungrounded",
                    message=f"{where} citation not in allowed sources: {citation}",
                )
            )
    return issues


def _check_investment_logic(
    report: ReportDocument, investments: list[InvestmentCard]
) -> list[CheckIssue]:
    theme_token_sets = [_tokenize(theme) for card in investments for theme in card.themes]
    if not theme_token_sets:
        theme_token_sets = [set()]

    issues: list[CheckIssue] = []
    for project in report.ranked_projects:
        project_tokens = _tokenize(project.rationale) | _tokenize(project.business_case)
        overlaps = any(project_tokens & theme_tokens for theme_tokens in theme_token_sets)
        if not overlaps:
            issues.append(
                CheckIssue(
                    severity="hard",
                    code="investment_logic",
                    message=(
                        f"ranked project {project.repo_id!r} rationale/business_case "
                        "does not overlap any investment theme tokens"
                    ),
                )
            )
    return issues


def _check_pipeline_integrity(artifact_dir: Path) -> list[CheckIssue]:
    path = artifact_dir / "manifest.json"
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    nodes = {n.get("node_id"): n for n in data.get("nodes", []) if isinstance(n, dict)}
    for required in _REQUIRED_MANIFEST_NODES:
        node = nodes.get(required)
        if node is None or node.get("status") != "succeeded":
            return [
                CheckIssue(
                    severity="soft",
                    code="pipeline_integrity",
                    message=(
                        "manifest missing succeeded invest_scan and frontier_report nodes"
                    ),
                )
            ]
    return []


def run_checker(ctx: NodeContext) -> None:
    inputs = ctx.node.inputs or ["report.md", "report.json", "investments.json"]
    output_name = ctx.node.outputs[0] if ctx.node.outputs else "check.json"

    # inputs: report.md, report.json, investments.json
    report_json_name = inputs[1] if len(inputs) > 1 else "report.json"
    investments_name = inputs[2] if len(inputs) > 2 else "investments.json"

    report = _load_report(ctx.artifact_dir, report_json_name)
    investments = _load_investments(ctx.artifact_dir, investments_name)
    allowed = _allowed_citations(investments, ctx.repo_root)

    issues: list[CheckIssue] = []
    issues.extend(_check_grounding(report, allowed, ctx.repo_root))
    issues.extend(_check_investment_logic(report, investments))
    issues.extend(_check_pipeline_integrity(ctx.artifact_dir))

    hard_issues = [i for i in issues if i.severity == "hard"]
    soft_issues = [i for i in issues if i.severity == "soft"]
    result = CheckResult(
        hard_pass=len(hard_issues) == 0,
        soft_pass=len(soft_issues) == 0,
        issues=issues,
    )
    out_path = ctx.artifact_dir / output_name
    out_path.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def checker_node(ctx: NodeContext) -> None:
    run_checker(ctx)
