from __future__ import annotations

import json
from pathlib import Path

from frontier_pipeline.publish import publish_friday_artifacts


def _write_artifacts(artifact_dir: Path, *, hard_pass: bool) -> None:
    artifact_dir.mkdir(parents=True, exist_ok=True)
    (artifact_dir / "report.md").write_text("# Report\n", encoding="utf-8")
    (artifact_dir / "report.json").write_text(
        json.dumps({"title": "t", "report_date": "2026-08-08", "ranked_projects": []}),
        encoding="utf-8",
    )
    (artifact_dir / "report.html").write_text("<html></html>", encoding="utf-8")
    (artifact_dir / "check.json").write_text(
        json.dumps({"hard_pass": hard_pass, "soft_pass": hard_pass, "issues": []}),
        encoding="utf-8",
    )


def test_publish_hard_pass_copies_report_and_html(tmp_path: Path):
    artifact_dir = tmp_path / "artifacts" / "run1"
    repo_root = tmp_path / "repo"
    (repo_root / "wiki" / "reports").mkdir(parents=True)
    _write_artifacts(artifact_dir, hard_pass=True)

    result = publish_friday_artifacts(artifact_dir, repo_root, "2026-08-08")

    assert result is True
    assert (repo_root / "reports" / "2026-08-08.md").read_text(encoding="utf-8") == "# Report\n"
    assert (repo_root / "wiki" / "reports" / "2026-08-08.md").read_text(encoding="utf-8") == "# Report\n"
    assert (repo_root / "reports" / "2026-08-08.html").read_text(encoding="utf-8") == "<html></html>"
    assert not (repo_root / "reports" / "drafts").exists()


def test_publish_hard_fail_copies_drafts(tmp_path: Path):
    artifact_dir = tmp_path / "artifacts" / "run1"
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _write_artifacts(artifact_dir, hard_pass=False)

    result = publish_friday_artifacts(artifact_dir, repo_root, "2026-08-08")

    assert result is False
    draft = repo_root / "reports" / "drafts" / "2026-08-08"
    assert (draft / "report.md").exists()
    assert (draft / "report.json").exists()
    assert (draft / "check.json").exists()
    assert not (repo_root / "reports" / "2026-08-08.md").exists()
    assert not (repo_root / "reports" / "2026-08-08.html").exists()
