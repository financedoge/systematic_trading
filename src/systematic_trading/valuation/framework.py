from __future__ import annotations

from datetime import date
from typing import Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


OpportunityBucket = Literal[
    "major_regime_change",
    "fallen_angel",
    "deep_value_recovery",
    "cyclical_macro",
    "quality_first_value",
    "defensive_compounder",
]
DeepDivePriority = Literal["high", "medium", "low"]
FinalRating = Literal["A", "B", "C", "D", "E"]


class MacroScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    probability: float = Field(ge=0, le=1)
    description: str


class ValuationScenario(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    probability: float = Field(ge=0, le=1)
    fair_value: float = Field(ge=0)
    implied_upside: float
    key_assumption: str


class StockScoreBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valuation_dislocation: float = Field(ge=0, le=25)
    recovery_potential: float = Field(ge=0, le=20)
    business_quality: float = Field(ge=0, le=15)
    balance_sheet: float = Field(ge=0, le=15)
    earnings_revision: float = Field(ge=0, le=10)
    macro_scenario_skew: float = Field(ge=0, le=10)
    regime_change_optionality: float = Field(ge=0, le=5)
    penalties: float = Field(default=0, ge=-50, le=0)

    def gross_score(self) -> float:
        return (
            self.valuation_dislocation
            + self.recovery_potential
            + self.business_quality
            + self.balance_sheet
            + self.earnings_revision
            + self.macro_scenario_skew
            + self.regime_change_optionality
        )

    def total_score(self) -> float:
        return _clip(self.gross_score() + self.penalties, 0, 100)


class BehavioralOverlayScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sector_thematic_beta: float = Field(ge=0, le=5)
    narrative_strength: float = Field(ge=0, le=5)
    retail_sentiment: float = Field(ge=0, le=5)
    options_technical_momentum: float = Field(ge=0, le=3)
    positioning_asymmetry: float = Field(ge=0, le=2)

    def total_score(self) -> float:
        return (
            self.sector_thematic_beta
            + self.narrative_strength
            + self.retail_sentiment
            + self.options_technical_momentum
            + self.positioning_asymmetry
        )


class StockValuationReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    company: str
    market: str = "US"
    sector: str
    as_of: date
    opportunity_bucket: OpportunityBucket
    total_score: float = Field(ge=0, le=100)
    score_breakdown: StockScoreBreakdown
    behavioral_overlay_score: BehavioralOverlayScore
    current_price: float = Field(gt=0)
    probability_weighted_fair_value: float = Field(ge=0)
    expected_upside: float
    bear_case_downside: float
    quality_score: float = Field(ge=0, le=100)
    positive_thesis_probability: float = Field(ge=0, le=1)
    final_rating: FinalRating
    key_thesis: str
    main_risk: str
    deep_dive_priority: DeepDivePriority
    scenarios: list[ValuationScenario]
    source_urls: list[str] = Field(default_factory=list)
    review_notes: list[str] = Field(default_factory=list)

    @field_validator("ticker")
    @classmethod
    def _uppercase_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @model_validator(mode="after")
    def _sync_derived_values(self) -> StockValuationReport:
        derived_total = round(self.score_breakdown.total_score(), 2)
        if abs(self.total_score - derived_total) > 1.0:
            self.review_notes.append(
                f"Total score was {self.total_score:.2f}; scorecard components imply {derived_total:.2f}."
            )
        if self.probability_weighted_fair_value > 0 and self.current_price > 0:
            derived_upside = (self.probability_weighted_fair_value / self.current_price) - 1
            if abs(self.expected_upside - derived_upside) > 0.03:
                self.review_notes.append(
                    f"Expected upside was {self.expected_upside:.2%}; fair-value math implies {derived_upside:.2%}."
                )
        return self

    def normalized_total_score(self) -> float:
        return _clip(self.total_score, 0, 100)

    def behavioral_total_score(self) -> float:
        return self.behavioral_overlay_score.total_score()


class StockFrameworkScreen(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: date
    framework_version: str = "v1.0"
    model: str
    universe: str
    reports: list[StockValuationReport]
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ensure_unique_tickers(self) -> StockFrameworkScreen:
        tickers = [report.ticker for report in self.reports]
        duplicates = sorted({ticker for ticker in tickers if tickers.count(ticker) > 1})
        if duplicates:
            raise ValueError(f"Duplicate stock reports: {', '.join(duplicates)}")
        return self


def rank_stock_reports(
    reports: Sequence[StockValuationReport],
    *,
    top_n: int | None = None,
) -> list[StockValuationReport]:
    ranked = sorted(reports, key=_ranking_key, reverse=True)
    return ranked[:top_n] if top_n is not None else ranked


def framework_allocation_weights(
    reports: Sequence[StockValuationReport],
    *,
    volatility_by_symbol: Mapping[str, float] | None = None,
    min_expected_upside: float = 0.01,
    max_single_name_weight: float | None = None,
) -> dict[str, float]:
    volatility_by_symbol = {symbol.upper(): value for symbol, value in (volatility_by_symbol or {}).items()}
    raw: dict[str, float] = {}
    for report in reports:
        expected_upside = max(report.expected_upside, min_expected_upside)
        conviction = max(report.normalized_total_score() / 100, 0.01)
        volatility = max(volatility_by_symbol.get(report.ticker, 0.25), 0.05)
        downside_penalty = 1.0
        if report.bear_case_downside < -0.30:
            downside_penalty *= 0.75
        if report.positive_thesis_probability < 0.45:
            downside_penalty *= 0.80
        raw[report.ticker] = conviction * expected_upside * downside_penalty / volatility

    if not raw or sum(raw.values()) <= 0:
        return _equal_weights([report.ticker for report in reports])

    weights = _normalize(raw)
    if max_single_name_weight is not None:
        weights = _cap_and_redistribute(weights, cap=max_single_name_weight)
    return weights


def scenario_probability_weighted_value(scenarios: Sequence[ValuationScenario]) -> float:
    total_probability = sum(scenario.probability for scenario in scenarios)
    if total_probability <= 0:
        return 0
    return sum(scenario.probability * scenario.fair_value for scenario in scenarios) / total_probability


def _ranking_key(report: StockValuationReport) -> tuple[float, float, float, float]:
    return (
        report.normalized_total_score(),
        report.expected_upside,
        report.positive_thesis_probability,
        -abs(min(report.bear_case_downside, 0)),
    )


def _equal_weights(symbols: Sequence[str]) -> dict[str, float]:
    if not symbols:
        return {}
    weight = 1 / len(symbols)
    return {symbol.upper(): weight for symbol in symbols}


def _normalize(values: Mapping[str, float]) -> dict[str, float]:
    total = sum(max(0, value) for value in values.values())
    if total <= 0:
        return _equal_weights(list(values))
    return {symbol.upper(): max(0, value) / total for symbol, value in values.items()}


def _cap_and_redistribute(weights: Mapping[str, float], *, cap: float) -> dict[str, float]:
    if cap <= 0:
        return _normalize(weights)

    capped = {symbol: min(weight, cap) for symbol, weight in weights.items()}
    for _ in range(len(capped) + 1):
        residual = 1 - sum(capped.values())
        if residual <= 0.0000001:
            break
        recipients = {symbol: weight for symbol, weight in capped.items() if weight < cap}
        recipient_total = sum(recipients.values())
        if not recipients or recipient_total <= 0:
            break
        for symbol, weight in recipients.items():
            capped[symbol] = min(cap, capped[symbol] + residual * (weight / recipient_total))
    return _normalize(capped)


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
