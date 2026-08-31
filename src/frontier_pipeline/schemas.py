from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import AliasChoices, BaseModel, Field, field_validator


class RepoCard(BaseModel):
    id: str
    url: str
    stars: int = Field(ge=0)
    topics: list[str] = Field(default_factory=list)
    summary: str = ""
    fetched_at: datetime
    recent_activity_score: float = 0.0


class InvestmentCard(BaseModel):
    headline: str
    themes: list[str] = Field(default_factory=list)
    actors: list[str] = Field(default_factory=list)
    source_url: str
    date: date

    @field_validator("source_url")
    @classmethod
    def non_empty_url(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("source_url is required")
        return v


class ReportClaim(BaseModel):
    model_config = {"populate_by_name": True}

    text: str = Field(validation_alias=AliasChoices("text", "claim"))
    citations: list[str] = Field(min_length=1)


class RankedProject(BaseModel):
    repo_id: str
    rank: int = Field(ge=1)
    rationale: str
    business_case: str
    citations: list[str] = Field(min_length=1)


class ReportDocument(BaseModel):
    title: str
    report_date: date
    ranked_projects: list[RankedProject]
    claims: list[ReportClaim] = Field(default_factory=list)


class CheckIssue(BaseModel):
    severity: Literal["hard", "soft"]
    code: str
    message: str


class CheckResult(BaseModel):
    hard_pass: bool
    soft_pass: bool
    issues: list[CheckIssue] = Field(default_factory=list)

    @property
    def allows_render(self) -> bool:
        return self.hard_pass


class NodeStatus(BaseModel):
    node_id: str
    status: Literal["pending", "running", "succeeded", "failed", "skipped"]
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    error: str | None = None
    warnings: list[str] = Field(default_factory=list)


class RunManifest(BaseModel):
    run_id: str
    graph_name: str
    started_at: datetime
    finished_at: datetime | None = None
    nodes: list[NodeStatus] = Field(default_factory=list)
