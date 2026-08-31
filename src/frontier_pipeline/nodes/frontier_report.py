from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from frontier_pipeline.nodes.registry import NodeContext
from frontier_pipeline.schemas import InvestmentCard, ReportDocument

SYSTEM_PROMPT = (
    "You rank AI-agent frontier projects and draft business cases. "
    "Return JSON matching ReportDocument: title, report_date, ranked_projects "
    "(repo_id, rank, rationale, business_case, citations), and optional claims "
    "as objects with fields text and citations. Do not use a claim key; use text. "
    "Every citation MUST be one of the provided investment source_urls or wiki paths."
)


def _load_investments(artifact_dir: Path, input_name: str) -> list[InvestmentCard]:
    path = artifact_dir / input_name
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [InvestmentCard.model_validate(item) for item in raw]


def _gather_wiki_projects(repo_root: Path) -> list[dict[str, str]]:
    projects_dir = repo_root / "wiki" / "projects"
    pages: list[dict[str, str]] = []
    if not projects_dir.is_dir():
        return pages
    for path in sorted(projects_dir.glob("*.md")):
        rel = f"wiki/projects/{path.name}"
        pages.append({"path": rel, "content": path.read_text(encoding="utf-8")})
    return pages


def _allowed_citations(investments: list[InvestmentCard], wiki_pages: list[dict[str, str]]) -> list[str]:
    urls = [card.source_url for card in investments]
    paths = [page["path"] for page in wiki_pages]
    return urls + paths


def _build_prompt(
    investments: list[InvestmentCard],
    wiki_pages: list[dict[str, str]],
    *,
    repair_error: str | None = None,
) -> str:
    allowed = _allowed_citations(investments, wiki_pages)
    payload = {
        "report_date": datetime.now(timezone.utc).date().isoformat(),
        "investments": [card.model_dump(mode="json") for card in investments],
        "wiki_projects": wiki_pages,
        "allowed_citations": allowed,
    }
    prompt = (
        "Produce a frontier ranking report as JSON (ReportDocument).\n"
        "Use only allowed_citations for every citations list.\n"
        f"Context:\n{json.dumps(payload, indent=2)}"
    )
    if repair_error:
        prompt = (
            "Your previous JSON failed schema validation. "
            f"Error: {repair_error}\n"
            "Return corrected ReportDocument JSON only.\n\n"
            + prompt
        )
    return prompt


def _validate_report(data: dict[str, Any]) -> ReportDocument:
    return ReportDocument.model_validate(data)


def _render_markdown(doc: ReportDocument) -> str:
    lines = [
        f"# {doc.title}",
        "",
        f"Date: {doc.report_date.isoformat()}",
        "",
        "## Rankings",
        "",
    ]
    for project in sorted(doc.ranked_projects, key=lambda p: p.rank):
        lines.append(f"### {project.rank}. {project.repo_id}")
        lines.append("")
        lines.append(f"**Rationale:** {project.rationale}")
        lines.append("")
        lines.append(f"**Business case:** {project.business_case}")
        lines.append("")
        lines.append("**Citations:**")
        for cite in project.citations:
            lines.append(f"- {cite}")
        lines.append("")
    if doc.claims:
        lines.append("## Claims")
        lines.append("")
        for claim in doc.claims:
            lines.append(f"- {claim.text}")
            for cite in claim.citations:
                lines.append(f"  - {cite}")
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _require_llm(ctx: NodeContext) -> Any:
    if ctx.llm is None:
        raise ValueError("frontier_report requires ctx.llm")
    return ctx.llm


def run_frontier_report(ctx: NodeContext) -> None:
    llm = _require_llm(ctx)
    input_name = ctx.node.inputs[0] if ctx.node.inputs else "investments.json"
    investments = _load_investments(ctx.artifact_dir, input_name)
    wiki_pages = _gather_wiki_projects(ctx.repo_root)

    raw = llm.complete_json(_build_prompt(investments, wiki_pages), system=SYSTEM_PROMPT)
    try:
        doc = _validate_report(raw)
    except ValidationError as exc:
        repaired = llm.complete_json(
            _build_prompt(investments, wiki_pages, repair_error=str(exc)),
            system=SYSTEM_PROMPT,
        )
        try:
            doc = _validate_report(repaired)
        except ValidationError as repair_exc:
            raise ValueError(
                f"frontier_report LLM output invalid after repair: {repair_exc}"
            ) from repair_exc

    outputs = list(ctx.node.outputs) if ctx.node.outputs else ["report.md", "report.json"]
    md_name = next((o for o in outputs if o.endswith(".md")), "report.md")
    json_name = next((o for o in outputs if o.endswith(".json")), "report.json")

    (ctx.artifact_dir / json_name).write_text(
        json.dumps(doc.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    (ctx.artifact_dir / md_name).write_text(_render_markdown(doc), encoding="utf-8")


def frontier_report_node(ctx: NodeContext) -> None:
    run_frontier_report(ctx)
