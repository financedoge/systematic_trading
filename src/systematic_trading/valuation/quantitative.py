from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from systematic_trading.domain.market import FundamentalSnapshot, Instrument
from systematic_trading.valuation.framework import (
    BehavioralOverlayScore,
    StockFrameworkScreen,
    StockScoreBreakdown,
    StockValuationReport,
    ValuationScenario,
    rank_stock_reports,
)
from systematic_trading.valuation.screener import MarketFeatureSnapshot


def build_quantitative_framework_screen(
    *,
    instruments: Mapping[str, Instrument],
    features: Mapping[str, MarketFeatureSnapshot],
    fundamentals_by_symbol: Mapping[str, Sequence[FundamentalSnapshot]],
    as_of: date,
    top_n: int | None = None,
    universe_name: str = "US stock replacement universe",
) -> StockFrameworkScreen:
    reports: list[StockValuationReport] = []
    missing: list[str] = []
    for symbol, instrument in sorted(instruments.items()):
        feature = features.get(symbol)
        if feature is None:
            missing.append(f"{symbol}: no price features")
            continue
        snapshot = latest_available_fundamental(
            fundamentals_by_symbol.get(symbol, ()),
            as_of=as_of,
        )
        if snapshot is None:
            missing.append(f"{symbol}: no fundamental snapshot available by {as_of}")
            continue
        reports.append(
            quantitative_stock_report(
                instrument=instrument,
                feature=feature,
                fundamental=snapshot,
                as_of=as_of,
            )
        )

    ranked = rank_stock_reports(reports, top_n=top_n)
    notes = [
        "Point-in-time quantitative screen uses only price features up to the rebalance date and fundamental snapshots whose available_date is on or before the rebalance date.",
        "Scorecard is a deterministic proxy for the probability framework; policy, macro, and qualitative memo layers are intentionally excluded.",
    ]
    if missing:
        notes.append(f"Skipped {len(missing)} symbols without time-gated inputs: " + "; ".join(missing[:8]))
    return StockFrameworkScreen(
        as_of=as_of,
        framework_version="v1.0-quantitative-pit",
        model="point-in-time-quantitative-fundamentals",
        universe=universe_name,
        reports=ranked,
        notes=notes,
    )


def latest_available_fundamental(
    snapshots: Sequence[FundamentalSnapshot],
    *,
    as_of: date,
) -> FundamentalSnapshot | None:
    available = [snapshot for snapshot in snapshots if snapshot.available_date <= as_of]
    if not available:
        return None
    return max(available, key=lambda item: (item.available_date, item.period_end))


def quantitative_stock_report(
    *,
    instrument: Instrument,
    feature: MarketFeatureSnapshot,
    fundamental: FundamentalSnapshot,
    as_of: date,
) -> StockValuationReport:
    valuation = _valuation_score(fundamental, feature)
    recovery = _recovery_score(fundamental, feature)
    quality = _quality_score(fundamental)
    balance = _balance_sheet_score(fundamental)
    revision = _revision_score(fundamental)
    macro = _macro_score(instrument.sector, fundamental)
    regime = _regime_optionality(instrument.sector, instrument.symbol)
    volatility = feature.realized_volatility_63d or 0.25

    penalties = 0.0
    snapshot_age_days = (as_of - fundamental.available_date).days
    if snapshot_age_days > 550:
        penalties -= 6
    elif snapshot_age_days > 370:
        penalties -= 3
    if volatility > 0.55:
        penalties -= 6
    elif volatility > 0.40:
        penalties -= 3

    breakdown = StockScoreBreakdown(
        valuation_dislocation=valuation,
        recovery_potential=recovery,
        business_quality=quality,
        balance_sheet=balance,
        earnings_revision=revision,
        macro_scenario_skew=macro,
        regime_change_optionality=regime,
        penalties=penalties,
    )
    total_score = breakdown.total_score()
    drawdown = feature.drawdown_252d or 0
    expected_upside = _clip(
        (total_score - 52) / 100
        + valuation / 250
        + abs(min(drawdown, 0)) * 0.15
        - max(volatility - 0.35, 0) * 0.20,
        -0.35,
        1.00,
    )
    current_price = feature.current_price
    fair_value = current_price * (1 + expected_upside)
    bear_downside = -_clip(
        0.10
        + volatility * 0.55
        + max(-float(feature.return_252d or 0), 0) * 0.20
        + max(8 - balance, 0) * 0.015,
        0.10,
        0.75,
    )
    bucket = _bucket(instrument.sector, valuation, recovery, quality, regime, drawdown)
    quality_score = _clip((quality / 15) * 100, 0, 100)

    return StockValuationReport(
        ticker=instrument.symbol,
        company=instrument.name,
        market=instrument.country,
        sector=instrument.sector or "Unknown",
        as_of=as_of,
        opportunity_bucket=bucket,
        total_score=round(total_score, 2),
        score_breakdown=breakdown,
        behavioral_overlay_score=BehavioralOverlayScore(
            sector_thematic_beta=_clip(1 + regime, 0, 5),
            narrative_strength=_clip(1.5 + regime * 0.5 + max(feature.return_63d or 0, 0) * 4, 0, 5),
            retail_sentiment=_clip(2 + max(feature.return_21d or 0, 0) * 6, 0, 5),
            options_technical_momentum=_clip(1 + max(feature.return_63d or 0, 0) * 4, 0, 3),
            positioning_asymmetry=_clip(0.5 + valuation / 25 + abs(min(drawdown, 0)), 0, 2),
        ),
        current_price=current_price,
        probability_weighted_fair_value=round(fair_value, 4),
        expected_upside=round(expected_upside, 4),
        bear_case_downside=round(bear_downside, 4),
        quality_score=round(quality_score, 2),
        positive_thesis_probability=_clip(0.35 + total_score / 220 + max(revision - 4, 0) / 100, 0, 0.88),
        final_rating=_rating(total_score),
        key_thesis=(
            f"Point-in-time fundamentals available {fundamental.available_date} support a "
            f"{bucket.replace('_', ' ')} score with valuation {valuation:.1f}/25 and quality {quality:.1f}/15."
        ),
        main_risk=(
            "Quantitative proxy excludes contemporaneous news, management guidance, accounting restatements, "
            "and policy narrative not present in the stored snapshot."
        ),
        deep_dive_priority="high" if total_score >= 70 else "medium" if total_score >= 55 else "low",
        scenarios=_scenarios(current_price, fair_value, bear_downside),
        source_urls=[],
        review_notes=[
            f"Fundamental period_end={fundamental.period_end}, available_date={fundamental.available_date}.",
            f"Price feature as_of={feature.as_of}; no future fundamentals were used.",
        ],
    )


def _valuation_score(snapshot: FundamentalSnapshot, feature: MarketFeatureSnapshot) -> float:
    score = 0.0
    score += _score_high(snapshot.free_cash_flow_yield, low=0.00, high=0.12, points=8)
    score += _score_high(snapshot.earnings_yield, low=0.00, high=0.10, points=6)
    score += _score_low(snapshot.pe_ratio, good=8, bad=35, points=4)
    score += _score_low(snapshot.ev_to_ebitda, good=7, bad=22, points=3)
    score += _score_high(snapshot.dividend_yield, low=0.00, high=0.05, points=2)
    score += _score_low(snapshot.pb_ratio, good=1.0, bad=6.0, points=2)
    score += _clip(abs(min(feature.drawdown_252d or 0, 0)) / 0.50 * 3, 0, 3)
    return _clip(score, 0, 25)


def _recovery_score(snapshot: FundamentalSnapshot, feature: MarketFeatureSnapshot) -> float:
    drawdown = abs(min(feature.drawdown_252d or 0, 0))
    rebound = max(feature.return_63d or 0, 0)
    score = 0.0
    score += _score_high(snapshot.revenue_growth_yoy, low=-0.15, high=0.20, points=5)
    score += _score_high(snapshot.eps_growth_yoy, low=-0.30, high=0.30, points=5)
    score += _clip(drawdown / 0.55 * 5, 0, 5)
    score += _clip(rebound / 0.25 * 3, 0, 3)
    score += _score_high(snapshot.operating_margin, low=-0.05, high=0.20, points=2)
    return _clip(score, 0, 20)


def _quality_score(snapshot: FundamentalSnapshot) -> float:
    score = 0.0
    score += _score_high(snapshot.return_on_invested_capital, low=0.00, high=0.25, points=5)
    score += _score_high(snapshot.return_on_equity, low=0.00, high=0.30, points=3)
    score += _score_high(snapshot.gross_margin, low=0.20, high=0.70, points=3)
    score += _score_high(snapshot.operating_margin, low=0.00, high=0.25, points=2)
    score += _score_high(snapshot.free_cash_flow_margin, low=0.00, high=0.25, points=2)
    return _clip(score, 0, 15)


def _balance_sheet_score(snapshot: FundamentalSnapshot) -> float:
    score = 0.0
    score += _score_low(snapshot.net_debt_to_ebitda, good=0.0, bad=4.0, points=5)
    score += _score_low(snapshot.debt_to_equity, good=0.25, bad=2.0, points=3)
    score += _score_high(snapshot.interest_coverage, low=2.0, high=12.0, points=4)
    score += _score_high(snapshot.current_ratio, low=0.8, high=2.0, points=3)
    return _clip(score, 0, 15)


def _revision_score(snapshot: FundamentalSnapshot) -> float:
    score = 0.0
    score += _score_high(snapshot.analyst_eps_revision_90d, low=-0.15, high=0.15, points=7)
    score += _score_high(snapshot.eps_growth_yoy, low=-0.20, high=0.25, points=3)
    return _clip(score, 0, 10)


def _macro_score(sector: str | None, snapshot: FundamentalSnapshot) -> float:
    priors = {
        "Information Technology": 6.0,
        "Health Care": 5.5,
        "Consumer Staples": 5.0,
        "Industrials": 5.5,
        "Communication Services": 5.0,
        "Financials": 4.5,
        "Consumer Discretionary": 4.5,
        "Energy": 5.0,
    }
    score = priors.get(sector or "", 5.0)
    score += _score_high(snapshot.revenue_growth_yoy, low=-0.10, high=0.20, points=2) - 1
    score += _score_high(snapshot.free_cash_flow_yield, low=0.00, high=0.10, points=2) - 1
    return _clip(score, 0, 10)


def _regime_optionality(sector: str | None, symbol: str) -> float:
    if symbol in {"NVDA", "AVGO", "AMD", "MU", "MSFT", "TSLA"}:
        return 4.0
    if symbol in {"LMT", "NOC", "RTX", "GE"}:
        return 3.5
    if sector in {"Information Technology", "Energy"}:
        return 2.5
    return 1.0


def _bucket(
    sector: str | None,
    valuation: float,
    recovery: float,
    quality: float,
    regime: float,
    drawdown: float,
) -> str:
    if regime >= 3.5 and quality >= 7:
        return "major_regime_change"
    if drawdown <= -0.30 and valuation >= 13 and recovery >= 10:
        return "fallen_angel"
    if valuation >= 15 and drawdown <= -0.20:
        return "deep_value_recovery"
    if sector in {"Energy", "Industrials", "Financials"}:
        return "cyclical_macro"
    if sector in {"Consumer Staples", "Health Care"}:
        return "defensive_compounder"
    return "quality_first_value"


def _scenarios(current_price: float, fair_value: float, bear_downside: float) -> list[ValuationScenario]:
    bull = max(fair_value * 1.30, current_price * 1.12)
    base = fair_value
    bear = current_price * (1 + bear_downside)
    stress_downside = max(min(bear_downside * 1.4, -0.20), -0.95)
    stress = current_price * (1 + stress_downside)
    return [
        ValuationScenario(name="Bull", probability=0.20, fair_value=round(bull, 4), implied_upside=(bull / current_price) - 1, key_assumption="Quantitative valuation and quality factors expand."),
        ValuationScenario(name="Base", probability=0.45, fair_value=round(base, 4), implied_upside=(base / current_price) - 1, key_assumption="Point-in-time score translates into normalized expected upside."),
        ValuationScenario(name="Bear", probability=0.25, fair_value=round(bear, 4), implied_upside=(bear / current_price) - 1, key_assumption="Revision or balance-sheet factors deteriorate."),
        ValuationScenario(name="Stress", probability=0.10, fair_value=round(stress, 4), implied_upside=(stress / current_price) - 1, key_assumption="Macro and company-specific assumptions both fail."),
    ]


def _rating(score: float) -> str:
    if score >= 78:
        return "A"
    if score >= 65:
        return "B"
    if score >= 55:
        return "C"
    if score >= 45:
        return "D"
    return "E"


def _score_high(value: Decimal | float | int | None, *, low: float, high: float, points: float) -> float:
    if value is None:
        return 0
    normalized = _ratio(value)
    if high <= low:
        return 0
    return _clip((normalized - low) / (high - low), 0, 1) * points


def _score_low(value: Decimal | float | int | None, *, good: float, bad: float, points: float) -> float:
    if value is None:
        return 0
    normalized = float(value)
    if bad <= good:
        return 0
    return _clip((bad - normalized) / (bad - good), 0, 1) * points


def _ratio(value: Decimal | float | int) -> float:
    parsed = float(value)
    if abs(parsed) > 2:
        return parsed / 100
    return parsed


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
