from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from frontier_pipeline.schemas import (
    CheckResult,
    InvestmentCard,
    RepoCard,
    ReportDocument,
)


def test_repo_card_roundtrip():
    card = RepoCard(
        id="owner/repo",
        url="https://github.com/owner/repo",
        stars=100,
        topics=["ai-agents"],
        summary="An agent framework",
        fetched_at=datetime(2026, 8, 9, tzinfo=timezone.utc),
    )
    assert card.model_dump()["id"] == "owner/repo"


def test_investment_card_requires_source_url():
    with pytest.raises(ValidationError):
        InvestmentCard(
            headline="AI funding",
            themes=["agents"],
            actors=["Acme"],
            source_url="",
            date=date(2026, 8, 8),
        )


def test_check_result_hard_fail_blocks_share():
    result = CheckResult(
        hard_pass=False,
        soft_pass=True,
        issues=[{"severity": "hard", "code": "ungrounded", "message": "claim lacks citation"}],
    )
    assert result.hard_pass is False
    assert result.allows_render is False


def test_report_claim_accepts_claim_alias():
    from frontier_pipeline.schemas import ReportClaim

    claim = ReportClaim.model_validate(
        {"claim": "Funding rose", "citations": ["https://example.com/a"]}
    )
    assert claim.text == "Funding rose"


def test_report_document_requires_citations_on_claims():
    doc = ReportDocument(
        title="Frontier Report",
        report_date=date(2026, 8, 8),
        ranked_projects=[
            {
                "repo_id": "owner/repo",
                "rank": 1,
                "rationale": "Matches agent infra theme",
                "business_case": "Sell agent ops tooling",
                "citations": ["https://example.com/a", "wiki/projects/owner-repo.md"],
            }
        ],
        claims=[
            {
                "text": "Funding into agent infra rose",
                "citations": ["https://example.com/a"],
            }
        ],
    )
    assert doc.ranked_projects[0].rank == 1
