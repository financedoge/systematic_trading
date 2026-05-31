from __future__ import annotations

import math
from datetime import date
from decimal import Decimal
from typing import Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field

from systematic_trading.domain.market import Instrument, PriceBar
from systematic_trading.valuation.framework import (
    BehavioralOverlayScore,
    StockFrameworkScreen,
    StockScoreBreakdown,
    StockValuationReport,
    ValuationScenario,
    rank_stock_reports,
)


class MarketFeatureSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticker: str
    as_of: date
    current_price: float = Field(gt=0)
    return_21d: float | None = None
    return_63d: float | None = None
    return_252d: float | None = None
    drawdown_252d: float | None = None
    realized_volatility_63d: float | None = None
    volume_ratio_21d_126d: float | None = None
    observations: int


def build_market_feature_snapshots(
    bars_by_symbol: Mapping[str, Sequence[PriceBar]],
    *,
    as_of: date | None = None,
) -> dict[str, MarketFeatureSnapshot]:
    snapshots: dict[str, MarketFeatureSnapshot] = {}
    for symbol, raw_bars in bars_by_symbol.items():
        bars = sorted(
            [bar for bar in raw_bars if as_of is None or bar.trade_date <= as_of],
            key=lambda item: item.trade_date,
        )
        if not bars:
            continue
        latest = bars[-1]
        snapshots[symbol.upper()] = MarketFeatureSnapshot(
            ticker=symbol.upper(),
            as_of=latest.trade_date,
            current_price=float(latest.close),
            return_21d=_return_over_bars(bars, 21),
            return_63d=_return_over_bars(bars, 63),
            return_252d=_return_over_bars(bars, 252),
            drawdown_252d=_drawdown_from_high(bars, 252),
            realized_volatility_63d=_realized_volatility(bars[-64:]) if len(bars) >= 64 else None,
            volume_ratio_21d_126d=_volume_ratio(bars, 21, 126),
            observations=len(bars),
        )
    return snapshots


def build_heuristic_framework_screen(
    *,
    instruments: Mapping[str, Instrument],
    features: Mapping[str, MarketFeatureSnapshot],
    as_of: date,
    top_n: int | None = None,
    universe_name: str = "US stock replacement universe",
) -> StockFrameworkScreen:
    reports = [
        heuristic_stock_report(instrument=instrument, feature=features[symbol], as_of=as_of)
        for symbol, instrument in sorted(instruments.items())
        if symbol in features
    ]
    ranked = rank_stock_reports(reports, top_n=top_n)
    return StockFrameworkScreen(
        as_of=as_of,
        framework_version="v1.0",
        model="market-data-heuristic",
        universe=universe_name,
        reports=ranked,
        notes=[
            "Fallback screen uses price, volatility, drawdown, and sector heuristics only; it is not a substitute for the AI/fundamental deep-dive process.",
            "Use this output for plumbing tests when OpenAI scoring or current fundamental data is unavailable.",
        ],
    )


def heuristic_stock_report(
    *,
    instrument: Instrument,
    feature: MarketFeatureSnapshot,
    as_of: date,
) -> StockValuationReport:
    drawdown = feature.drawdown_252d if feature.drawdown_252d is not None else 0
    return_63d = feature.return_63d if feature.return_63d is not None else 0
    return_252d = feature.return_252d if feature.return_252d is not None else 0
    volatility = feature.realized_volatility_63d if feature.realized_volatility_63d is not None else 0.25

    deep_drawdown = min(abs(min(drawdown, 0)) / 0.60, 1)
    rebound = max(return_63d, 0)
    revision_proxy = _clip(5 + return_63d * 20, 0, 10)
    quality = _sector_quality_prior(instrument.sector)
    balance = _sector_balance_prior(instrument.sector)
    macro = _sector_macro_prior(instrument.sector) + _clip(return_252d * 4, -2, 2)
    regime = _sector_regime_prior(instrument.sector, instrument.symbol)

    valuation_score = _clip(8 + deep_drawdown * 13 + max(-return_252d, 0) * 8, 0, 25)
    recovery_score = _clip(5 + deep_drawdown * 8 + rebound * 20, 0, 20)
    breakdown = StockScoreBreakdown(
        valuation_dislocation=valuation_score,
        recovery_potential=recovery_score,
        business_quality=quality,
        balance_sheet=balance,
        earnings_revision=revision_proxy,
        macro_scenario_skew=_clip(macro, 0, 10),
        regime_change_optionality=regime,
        penalties=_heuristic_penalty(volatility, return_252d),
    )
    total_score = breakdown.total_score()
    expected_upside = _clip((total_score - 55) / 100 + deep_drawdown * 0.25, -0.20, 0.80)
    fair_value = feature.current_price * (1 + expected_upside)
    bear_downside = -_clip(0.12 + volatility * 0.7 + max(-return_252d, 0) * 0.25, 0.12, 0.65)
    bucket = _heuristic_bucket(instrument.sector, drawdown, regime, recovery_score)
    scenarios = _heuristic_scenarios(feature.current_price, fair_value, bear_downside)

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
            sector_thematic_beta=min(5, 1 + regime),
            narrative_strength=_clip(2 + deep_drawdown * 2 + regime * 0.3, 0, 5),
            retail_sentiment=_clip(2 + max(return_63d, 0) * 8, 0, 5),
            options_technical_momentum=_clip(1 + max(return_63d, 0) * 5, 0, 3),
            positioning_asymmetry=_clip(0.5 + deep_drawdown, 0, 2),
        ),
        current_price=feature.current_price,
        probability_weighted_fair_value=round(fair_value, 4),
        expected_upside=round(expected_upside, 4),
        bear_case_downside=round(bear_downside, 4),
        quality_score=round((quality / 15) * 100, 2),
        positive_thesis_probability=_clip(0.35 + total_score / 250, 0, 0.85),
        final_rating=_rating(total_score),
        key_thesis=(
            f"Market-data proxy screen ranks {instrument.symbol} as a {bucket.replace('_', ' ')} candidate "
            f"with {return_63d:.1%} 63-day return and {drawdown:.1%} trailing drawdown."
        ),
        main_risk="Heuristic score lacks point-in-time fundamentals, earnings revisions, leverage, and peer valuation data.",
        deep_dive_priority="high" if total_score >= 70 else "medium" if total_score >= 55 else "low",
        scenarios=scenarios,
        source_urls=[],
        review_notes=["Generated by deterministic fallback heuristic, not by the full AI/fundamental scoring pass."],
    )


def ai_screen_input_rows(
    *,
    instruments: Mapping[str, Instrument],
    features: Mapping[str, MarketFeatureSnapshot],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for symbol, instrument in sorted(instruments.items()):
        feature = features.get(symbol)
        if feature is None:
            continue
        rows.append(
            {
                "ticker": symbol,
                "company": instrument.name,
                "sector": instrument.sector,
                "market": instrument.country,
                "current_price": feature.current_price,
                "return_21d": feature.return_21d,
                "return_63d": feature.return_63d,
                "return_252d": feature.return_252d,
                "drawdown_252d": feature.drawdown_252d,
                "realized_volatility_63d": feature.realized_volatility_63d,
                "volume_ratio_21d_126d": feature.volume_ratio_21d_126d,
                "observations": feature.observations,
            }
        )
    return rows


def _return_over_bars(bars: Sequence[PriceBar], lookback_bars: int) -> float | None:
    if len(bars) < lookback_bars + 1:
        return None
    latest = bars[-1].close
    reference = bars[-(lookback_bars + 1)].close
    if reference <= Decimal("0"):
        return None
    return float((latest / reference) - Decimal("1"))


def _drawdown_from_high(bars: Sequence[PriceBar], lookback_bars: int) -> float | None:
    if len(bars) < 2:
        return None
    lookback = bars[-min(len(bars), lookback_bars + 1) :]
    peak = max(bar.close for bar in lookback)
    if peak <= Decimal("0"):
        return None
    return float((lookback[-1].close / peak) - Decimal("1"))


def _realized_volatility(bars: Sequence[PriceBar]) -> float | None:
    returns = []
    for previous, current in zip(bars, bars[1:]):
        if previous.close > Decimal("0"):
            returns.append(float((current.close / previous.close) - Decimal("1")))
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    return math.sqrt(variance) * math.sqrt(252)


def _volume_ratio(bars: Sequence[PriceBar], fast_bars: int, slow_bars: int) -> float | None:
    if len(bars) < slow_bars:
        return None
    fast = sum(bar.volume for bar in bars[-fast_bars:]) / fast_bars
    slow = sum(bar.volume for bar in bars[-slow_bars:]) / slow_bars
    if slow <= 0:
        return None
    return (fast / slow) - 1


def _sector_quality_prior(sector: str | None) -> float:
    priors = {
        "Information Technology": 11.5,
        "Health Care": 10.5,
        "Consumer Staples": 10.0,
        "Industrials": 9.0,
        "Communication Services": 8.5,
        "Financials": 8.0,
        "Consumer Discretionary": 8.0,
        "Energy": 7.5,
    }
    return priors.get(sector or "", 8.0)


def _sector_balance_prior(sector: str | None) -> float:
    priors = {
        "Information Technology": 11.0,
        "Health Care": 10.0,
        "Consumer Staples": 9.5,
        "Industrials": 8.0,
        "Communication Services": 8.5,
        "Financials": 8.5,
        "Consumer Discretionary": 7.5,
        "Energy": 8.0,
    }
    return priors.get(sector or "", 8.0)


def _sector_macro_prior(sector: str | None) -> float:
    priors = {
        "Information Technology": 6.5,
        "Health Care": 5.5,
        "Consumer Staples": 5.0,
        "Industrials": 6.0,
        "Communication Services": 5.5,
        "Financials": 5.0,
        "Consumer Discretionary": 4.5,
        "Energy": 5.5,
    }
    return priors.get(sector or "", 5.0)


def _sector_regime_prior(sector: str | None, symbol: str) -> float:
    if symbol in {"NVDA", "AVGO", "AMD", "MU", "MSFT", "TSLA"}:
        return 4.0
    if symbol in {"LMT", "NOC", "RTX", "GE"}:
        return 3.5
    if sector == "Energy":
        return 2.5
    if sector == "Information Technology":
        return 2.5
    return 1.0


def _heuristic_penalty(volatility: float, return_252d: float) -> float:
    penalty = 0.0
    if volatility > 0.55:
        penalty -= 8
    elif volatility > 0.40:
        penalty -= 4
    if return_252d < -0.35:
        penalty -= 5
    return penalty


def _heuristic_bucket(sector: str | None, drawdown: float, regime: float, recovery_score: float) -> str:
    if regime >= 3.5:
        return "major_regime_change"
    if drawdown <= -0.30 and recovery_score >= 11:
        return "fallen_angel"
    if drawdown <= -0.25:
        return "deep_value_recovery"
    if sector in {"Energy", "Industrials", "Financials"}:
        return "cyclical_macro"
    if sector in {"Consumer Staples", "Health Care"}:
        return "defensive_compounder"
    return "quality_first_value"


def _heuristic_scenarios(current_price: float, fair_value: float, bear_downside: float) -> list[ValuationScenario]:
    bull = max(fair_value * 1.35, current_price * 1.15)
    base = fair_value
    bear = current_price * (1 + bear_downside)
    stress = current_price * (1 + min(bear_downside * 1.5, -0.20))
    return [
        ValuationScenario(name="Bull", probability=0.20, fair_value=round(bull, 4), implied_upside=(bull / current_price) - 1, key_assumption="Multiple recovery and stronger operating momentum."),
        ValuationScenario(name="Base", probability=0.45, fair_value=round(base, 4), implied_upside=(base / current_price) - 1, key_assumption="Framework score converts into normalized expected upside."),
        ValuationScenario(name="Bear", probability=0.25, fair_value=round(bear, 4), implied_upside=(bear / current_price) - 1, key_assumption="Weak revisions and risk premium pressure."),
        ValuationScenario(name="Stress", probability=0.10, fair_value=round(stress, 4), implied_upside=(stress / current_price) - 1, key_assumption="Adverse macro and thesis deterioration."),
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


def _clip(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))
