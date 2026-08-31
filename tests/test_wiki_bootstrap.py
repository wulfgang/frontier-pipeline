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
