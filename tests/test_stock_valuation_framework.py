from datetime import date

import pytest

from systematic_trading.valuation.framework import (
    BehavioralOverlayScore,
    StockScoreBreakdown,
    StockValuationReport,
    ValuationScenario,
    framework_allocation_weights,
    rank_stock_reports,
)


def _report(symbol: str, score: float, upside: float, downside: float = -0.2) -> StockValuationReport:
    breakdown = StockScoreBreakdown(
        valuation_dislocation=min(25, score * 0.25),
        recovery_potential=min(20, score * 0.20),
        business_quality=min(15, score * 0.15),
        balance_sheet=min(15, score * 0.15),
        earnings_revision=min(10, score * 0.10),
        macro_scenario_skew=min(10, score * 0.10),
        regime_change_optionality=min(5, score * 0.05),
        penalties=0,
    )
    return StockValuationReport(
        ticker=symbol,
        company=f"{symbol} Corp",
        market="US",
        sector="Information Technology",
        as_of=date(2026, 4, 29),
        opportunity_bucket="quality_first_value",
        total_score=score,
        score_breakdown=breakdown,
        behavioral_overlay_score=BehavioralOverlayScore(
            sector_thematic_beta=3,
            narrative_strength=3,
            retail_sentiment=2,
            options_technical_momentum=1,
            positioning_asymmetry=1,
        ),
        current_price=100,
        probability_weighted_fair_value=100 * (1 + upside),
        expected_upside=upside,
        bear_case_downside=downside,
        quality_score=75,
        positive_thesis_probability=0.6,
        final_rating="B",
        key_thesis="Test thesis.",
        main_risk="Test risk.",
        deep_dive_priority="high",
        scenarios=[
            ValuationScenario(name="Bull", probability=0.2, fair_value=140, implied_upside=0.4, key_assumption="Bull."),
            ValuationScenario(name="Base", probability=0.45, fair_value=120, implied_upside=0.2, key_assumption="Base."),
            ValuationScenario(name="Bear", probability=0.25, fair_value=80, implied_upside=-0.2, key_assumption="Bear."),
            ValuationScenario(name="Stress", probability=0.1, fair_value=60, implied_upside=-0.4, key_assumption="Stress."),
        ],
        source_urls=[],
        review_notes=[],
    )


def test_rank_stock_reports_uses_framework_score_then_upside() -> None:
    reports = [_report("AAA", 70, 0.25), _report("BBB", 80, 0.05), _report("CCC", 70, 0.40)]

    ranked = rank_stock_reports(reports)

    assert [report.ticker for report in ranked] == ["BBB", "CCC", "AAA"]


def test_framework_allocation_weights_reflect_score_upside_and_volatility() -> None:
    reports = [_report("AAA", 80, 0.30), _report("BBB", 70, 0.10), _report("CCC", 65, 0.40, downside=-0.45)]

    weights = framework_allocation_weights(
        reports,
        volatility_by_symbol={"AAA": 0.20, "BBB": 0.20, "CCC": 0.60},
        max_single_name_weight=0.6,
    )

    assert sum(weights.values()) == pytest.approx(1)
    assert weights["AAA"] > weights["BBB"]
    assert weights["AAA"] > weights["CCC"]
    assert max(weights.values()) <= 0.6000001
