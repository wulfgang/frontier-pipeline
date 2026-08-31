from __future__ import annotations

import json

import yaml

from frontier_pipeline.nodes.registry import NodeContext
from frontier_pipeline.schemas import RepoCard


def repo_slug(repo_id: str) -> str:
    return repo_id.replace("/", "-")


def _load_repos(artifact_dir, input_name: str) -> list[RepoCard]:
    path = artifact_dir / input_name
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [RepoCard.model_validate(item) for item in raw]


def _render_project_page(card: RepoCard) -> str:
    front_matter = {
        "repo_id": card.id,
        "url": card.url,
        "stars": card.stars,
        "topics": card.topics,
        "updated": card.fetched_at.date().isoformat(),
    }
    fm = yaml.dump(front_matter, default_flow_style=False, sort_keys=False).strip()
    body = card.summary
    if card.topics:
        links = " ".join(f"[[themes/{topic}]]" for topic in card.topics)
        body = f"{body}\n\n{links}"
    return f"---\n{fm}\n---\n\n{body}\n"


def _ensure_theme_stub(wiki_root, topic: str, project_slug: str) -> None:
    theme_path = wiki_root / "themes" / f"{topic}.md"
    link = f"[[projects/{project_slug}]]"
    if theme_path.exists():
        text = theme_path.read_text(encoding="utf-8")
        if link in text:
            return
        if "## Projects" in text:
            text = text.rstrip() + f"\n- {link}\n"
        else:
            text = text.rstrip() + f"\n\n## Projects\n\n- {link}\n"
        theme_path.write_text(text, encoding="utf-8")
        return
    theme_path.write_text(f"# {topic}\n\n## Projects\n\n- {link}\n", encoding="utf-8")


def _update_index(wiki_root, project_slug: str) -> None:
    index_path = wiki_root / "index.md"
    text = index_path.read_text(encoding="utf-8")
    link_line = f"- [[projects/{project_slug}]]"
    if f"projects/{project_slug}" in text:
        return
    marker = "## Projects"
    if marker not in text:
        text = text.rstrip() + f"\n\n{marker}\n{link_line}\n"
    else:
        before, after = text.split(marker, 1)
        lines = after.splitlines()
        insert_at = len(lines)
        for i, line in enumerate(lines[1:], start=1):
            if line.startswith("## "):
                insert_at = i
                break
        lines.insert(insert_at, link_line)
        after = "\n".join(lines)
        if not after.endswith("\n"):
            after += "\n"
        text = before + marker + after
    index_path.write_text(text, encoding="utf-8")


def run_wiki_curate(ctx: NodeContext) -> None:
    input_name = ctx.node.inputs[0] if ctx.node.inputs else "repos.json"
    output_name = ctx.node.outputs[0] if ctx.node.outputs else "wiki_done.json"
    wiki_root = ctx.repo_root / "wiki"
    cards = _load_repos(ctx.artifact_dir, input_name)
    updated_ids: list[str] = []
    for card in cards:
        slug = repo_slug(card.id)
        page_path = wiki_root / "projects" / f"{slug}.md"
        page_path.write_text(_render_project_page(card), encoding="utf-8")
        for topic in card.topics:
            _ensure_theme_stub(wiki_root, topic, slug)
        _update_index(wiki_root, slug)
        updated_ids.append(card.id)
    out_path = ctx.artifact_dir / output_name
    out_path.write_text(json.dumps({"updated": updated_ids}, indent=2), encoding="utf-8")


def wiki_curate_node(ctx: NodeContext) -> None:
    run_wiki_curate(ctx)
