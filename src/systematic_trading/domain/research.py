from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from systematic_trading.domain.enums import ThesisStatus


class ResearchArtifact(BaseModel):
    title: str
    source_type: str
    source_url: str
    published_at: date | None = None
    summary: str


class ThesisMemo(BaseModel):
    symbol: str
    status: ThesisStatus = ThesisStatus.ACTIVE
    summary: str
    valuation_case: str
    catalyst_window: str
    hold_horizon_months: int = Field(ge=1)
    key_risks: list[str] = Field(default_factory=list)
    invalidation_rules: list[str] = Field(default_factory=list)
    sources: list[ResearchArtifact] = Field(default_factory=list)
    analyst_notes: str | None = None
