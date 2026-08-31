import json
from pathlib import Path

import httpx

from frontier_pipeline.graph.model import GraphNode
from frontier_pipeline.nodes.invest_scan import FEED_URLS, run_invest_scan
from frontier_pipeline.nodes.registry import NodeContext, build_default_registry
from frontier_pipeline.schemas import InvestmentCard

TECHCRUNCH_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TechCrunch Fundraising</title>
    <item>
      <title>Acme raises $50M Series B for AI agent platform</title>
      <link>https://techcrunch.com/2026/08/08/acme-raises-50m/</link>
      <pubDate>Fri, 08 Aug 2026 12:00:00 GMT</pubDate>
      <description>Acme announced Series B funding to scale its AI agent infrastructure.</description>
    </item>
  </channel>
</rss>
"""

VENTUREBEAT_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>VentureBeat AI</title>
    <item>
      <title>Startup closes funding round for enterprise agents</title>
      <link>https://venturebeat.com/ai/startup-funding-agents/</link>
      <pubDate>Thu, 07 Aug 2026 09:30:00 GMT</pubDate>
      <description>A new funding round backs enterprise agent tooling.</description>
    </item>
  </channel>
</rss>
"""

BLOOMBERG_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Bloomberg Technology</title>
    <item>
      <title>Chipmakers see AI boom lift demand</title>
      <link>https://www.bloomberg.com/news/articles/2026-08-08/chipmakers-ai</link>
      <pubDate>Fri, 08 Aug 2026 15:00:00 GMT</pubDate>
      <description>Technology markets react to AI infrastructure spending.</description>
    </item>
  </channel>
</rss>
"""


def _rss_for_url(url: str) -> str:
    if "techcrunch" in url:
        return TECHCRUNCH_RSS
    if "venturebeat" in url:
        return VENTUREBEAT_RSS
    if "bloomberg" in url:
        return BLOOMBERG_RSS
    return "<rss version='2.0'><channel></channel></rss>"


def test_invest_scan_writes_investment_cards(tmp_path: Path):
    assert len(FEED_URLS) >= 2

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text=_rss_for_url(str(request.url)),
            headers={"content-type": "application/rss+xml"},
        )

    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport)

    ctx = NodeContext(
        node=GraphNode(id="invest_scan", uses="invest_scan", outputs=["investments.json"]),
        artifact_dir=tmp_path,
        repo_root=tmp_path,
        llm=None,
    )
    run_invest_scan(ctx, client=client)

    data = json.loads((tmp_path / "investments.json").read_text(encoding="utf-8"))
    assert len(data) >= 2
    for item in data:
        card = InvestmentCard.model_validate(item)
        assert card.source_url.strip()
        assert card.themes
        assert card.headline.strip()


def test_invest_scan_registered_in_default_registry():
    registry = build_default_registry()
    assert registry.get("invest_scan") is not None
