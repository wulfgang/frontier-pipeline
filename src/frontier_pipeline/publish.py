from __future__ import annotations

import json
import shutil
from pathlib import Path


def publish_friday_artifacts(
    artifact_dir: Path,
    repo_root: Path,
    report_date: str,
) -> bool:
    """Copy Friday run artifacts into reports/ (and wiki) based on check.json.

    On hard_pass: publish report.md and report.html under dated paths.
    Otherwise: copy draft artifacts into reports/drafts/YYYY-MM-DD/.

    Returns whether check.json reported hard_pass.
    """
    check_path = artifact_dir / "check.json"
    hard_pass = False
    if check_path.exists():
        data = json.loads(check_path.read_text(encoding="utf-8"))
        hard_pass = bool(data.get("hard_pass"))

    if hard_pass:
        reports_dir = repo_root / "reports"
        wiki_reports = repo_root / "wiki" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        wiki_reports.mkdir(parents=True, exist_ok=True)

        md_src = artifact_dir / "report.md"
        html_src = artifact_dir / "report.html"
        if md_src.exists():
            shutil.copy2(md_src, reports_dir / f"{report_date}.md")
            shutil.copy2(md_src, wiki_reports / f"{report_date}.md")
        if html_src.exists():
            shutil.copy2(html_src, reports_dir / f"{report_date}.html")
        return True

    draft_dir = repo_root / "reports" / "drafts" / report_date
    draft_dir.mkdir(parents=True, exist_ok=True)
    for name in ("report.md", "report.json", "check.json"):
        src = artifact_dir / name
        if src.exists():
            shutil.copy2(src, draft_dir / name)
    return False
