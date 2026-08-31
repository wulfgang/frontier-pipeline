from __future__ import annotations

import os
from pathlib import Path

import markdown

from frontier_pipeline.nodes.registry import NodeContext

_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>{title}</title>
<style>
body {{ font-family: Georgia, "Times New Roman", serif; max-width: 42rem;
  margin: 2rem auto; padding: 0 1rem; line-height: 1.5; color: #1a1a1a; }}
h1, h2, h3 {{ font-family: system-ui, sans-serif; }}
a {{ color: #0b57d0; }}
code {{ font-family: ui-monospace, monospace; font-size: 0.9em; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def _extract_title(md_text: str) -> str:
    for line in md_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip() or "Frontier Report"
    return "Frontier Report"


def _maybe_write_pdf(html_path: Path, pdf_path: Path) -> None:
    if os.environ.get("FRONTIER_PDF") != "1":
        return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            try:
                page = browser.new_page()
                page.goto(html_path.resolve().as_uri())
                page.pdf(path=str(pdf_path))
            finally:
                browser.close()
    except Exception:  # noqa: BLE001 - PDF is best-effort
        return


def run_render_share(ctx: NodeContext) -> None:
    inputs = ctx.node.inputs or ["report.md", "check.json"]
    md_name = inputs[0] if inputs else "report.md"
    # Optionally read check.json when declared (presence already enforced by runner).
    if len(inputs) > 1:
        check_name = inputs[1]
        check_path = ctx.artifact_dir / check_name
        if check_path.exists():
            check_path.read_text(encoding="utf-8")

    outputs = list(ctx.node.outputs) if ctx.node.outputs else ["report.html"]
    html_name = next((o for o in outputs if o.endswith(".html")), "report.html")

    md_text = (ctx.artifact_dir / md_name).read_text(encoding="utf-8")
    body = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    title = _extract_title(md_text)
    html = _HTML_TEMPLATE.format(title=title, body=body)

    html_path = ctx.artifact_dir / html_name
    html_path.write_text(html, encoding="utf-8")

    pdf_name = html_name.rsplit(".", 1)[0] + ".pdf"
    _maybe_write_pdf(html_path, ctx.artifact_dir / pdf_name)


def render_share_node(ctx: NodeContext) -> None:
    run_render_share(ctx)
