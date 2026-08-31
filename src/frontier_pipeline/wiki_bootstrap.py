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

STYLE = '''# Wiki style guide

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
'''


def bootstrap_wiki(wiki_root: Path) -> None:
    wiki_root.mkdir(parents=True, exist_ok=True)
    (wiki_root / "index.md").write_text(INDEX, encoding="utf-8")
    (wiki_root / "STYLE.md").write_text(STYLE, encoding="utf-8")
    for name in ("projects", "themes", "investments", "reports"):
        d = wiki_root / name
        d.mkdir(parents=True, exist_ok=True)
        (d / ".gitkeep").touch()
