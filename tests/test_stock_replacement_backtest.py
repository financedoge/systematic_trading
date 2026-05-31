from datetime import date, timedelta
from decimal import Decimal

from systematic_trading.backtest.stock_replacement import (
    StockReplacementBacktestConfig,
    run_spy_replacement_backtest,
)
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate, FundamentalSnapshot, PriceBar
from systematic_trading.research import GLOBAL_ETF_UNIVERSE
from systematic_trading.research.stock_universe import US_STOCK_REPLACEMENT_UNIVERSE
from systematic_trading.storage.sqlite import SQLiteStore
from systematic_trading.valuation.framework import (
    BehavioralOverlayScore,
    StockScoreBreakdown,
    StockValuationReport,
    ValuationScenario,
)
from scripts.run_stock_replacement_backtest import _fetch_market_bars, _range_is_covered


def test_spy_replacement_backtest_expands_spy_target_into_selected_stocks(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "market.db")
    store.initialize()
    start = date(2023, 1, 2)
    trade_dates = _business_dates(start, 90)

    for instrument in GLOBAL_ETF_UNIVERSE.values():
        store.upsert_instrument(instrument)
        _insert_bars(store, instrument.symbol, trade_dates, base=100, drift=Decimal("0.001"))
    for symbol in ["AAPL", "MSFT"]:
        store.upsert_instrument(US_STOCK_REPLACEMENT_UNIVERSE[symbol])
        _insert_bars(store, symbol, trade_dates, base=50, drift=Decimal("0.002"))
    for trade_date in trade_dates:
        store.upsert_fx_rate(
            FXRate(
                rate_date=trade_date,
                base_currency=Currency.USD,
                quote_currency=Currency.CNH,
                rate=Decimal("7.20"),
            )
        )

    result = run_spy_replacement_backtest(
        store=store,
        stock_instruments=US_STOCK_REPLACEMENT_UNIVERSE,
        selected_symbols=["AAPL", "MSFT"],
        stock_reports=[_report("AAPL", 80, 0.30), _report("MSFT", 70, 0.20)],
        config=StockReplacementBacktestConfig(
            start_date=trade_dates[0],
            end_date=trade_dates[-1],
            initial_cash_cnh=Decimal("1000000"),
            lookback_bars=3,
            stock_weighting="framework",
        ),
    )

    assert result.proposals
    first_targets = {target.symbol: target.target_weight for target in result.proposals[0].targets}
    assert "SPY" not in first_targets
    assert first_targets["AAPL"] > 0
    assert first_targets["MSFT"] > 0
    assert all(position.symbol != "SPY" for position in result.final_snapshot.positions)


def test_point_in_time_stock_replacement_reranks_at_rebalance_dates(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "dynamic_market.db")
    store.initialize()
    start = date(2023, 1, 2)
    trade_dates = _business_dates(start, 130)

    for instrument in GLOBAL_ETF_UNIVERSE.values():
        store.upsert_instrument(instrument)
        _insert_bars(store, instrument.symbol, trade_dates, base=100, drift=Decimal("0.001"))
    for symbol in ["AAPL", "MSFT"]:
        store.upsert_instrument(US_STOCK_REPLACEMENT_UNIVERSE[symbol])
        _insert_bars(store, symbol, trade_dates, base=50, drift=Decimal("0.002"))
    for trade_date in trade_dates:
        store.upsert_fx_rate(
            FXRate(
                rate_date=trade_date,
                base_currency=Currency.USD,
                quote_currency=Currency.CNH,
                rate=Decimal("7.20"),
            )
        )

    fundamentals = {
        "AAPL": [
            _fundamental("AAPL", date(2023, 1, 15), fcf_yield="0.12", roic="0.25"),
            _fundamental("AAPL", date(2023, 3, 15), fcf_yield="0.01", roic="0.04"),
        ],
        "MSFT": [
            _fundamental("MSFT", date(2023, 1, 15), fcf_yield="0.01", roic="0.04"),
            _fundamental("MSFT", date(2023, 3, 15), fcf_yield="0.12", roic="0.25"),
        ],
    }

    result = run_spy_replacement_backtest(
        store=store,
        stock_instruments=US_STOCK_REPLACEMENT_UNIVERSE,
        selected_symbols=["AAPL", "MSFT"],
        fundamentals_by_symbol=fundamentals,
        config=StockReplacementBacktestConfig(
            start_date=trade_dates[0],
            end_date=trade_dates[-1],
            initial_cash_cnh=Decimal("1000000"),
            lookback_bars=3,
            stock_weighting="framework",
            stock_selection_mode="quantitative_point_in_time",
            dynamic_top_n=1,
        ),
    )

    stock_targets_by_date = {
        proposal.as_of: {target.symbol for target in proposal.targets if target.symbol in {"AAPL", "MSFT"}}
        for proposal in result.proposals
    }
    first_rebalance = min(stock_targets_by_date)
    last_rebalance = max(stock_targets_by_date)
    assert stock_targets_by_date[first_rebalance] == {"AAPL"}
    assert stock_targets_by_date[last_rebalance] == {"MSFT"}


def test_market_data_coverage_allows_non_trading_start_date() -> None:
    bars = [
        _bar(date(2023, 1, 3), Decimal("100")),
        _bar(date(2023, 1, 4), Decimal("101")),
        _bar(date(2023, 1, 5), Decimal("102")),
    ]

    assert _range_is_covered(bars, start_date=date(2023, 1, 1), end_date=date(2023, 1, 5))


def test_tushare_first_market_data_fetch_falls_back_with_safe_log(capsys) -> None:
    yahoo_bar = _bar(date(2023, 1, 3), Decimal("100"))

    bars = _fetch_market_bars(
        symbol="AAPL",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 1, 5),
        market_data_source="tushare-first",
        tushare_provider=_FailingTushareProvider(),
        yahoo_provider=_StaticYahooProvider([yahoo_bar]),
    )

    assert bars == [yahoo_bar]
    assert "\\u62b1\\u6b49" in capsys.readouterr().out


def _business_dates(start: date, count: int) -> list[date]:
    dates: list[date] = []
    current = start
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return dates


def _bar(trade_date: date, close: Decimal) -> PriceBar:
    return PriceBar(
        trade_date=trade_date,
        open=close,
        high=close,
        low=close,
        close=close,
        volume=1_000_000,
    )


def _insert_bars(
    store: SQLiteStore,
    symbol: str,
    trade_dates: list[date],
    *,
    base: int,
    drift: Decimal,
) -> None:
    price = Decimal(base)
    for index, trade_date in enumerate(trade_dates):
        price = price * (Decimal("1") + drift + Decimal(index % 3) * Decimal("0.0001"))
        store.upsert_price_bar(
            symbol,
            PriceBar(
                trade_date=trade_date,
                open=price,
                high=price * Decimal("1.01"),
                low=price * Decimal("0.99"),
                close=price,
                volume=1_000_000,
            ),
        )


class _FailingTushareProvider:
    def fetch_daily_bars(self, symbols, start_date, end_date):
        raise Exception("\u62b1\u6b49\uff0c\u9891\u7387\u8d85\u9650")


class _StaticYahooProvider:
    def __init__(self, bars: list[PriceBar]) -> None:
        self._bars = bars

    def fetch_daily_bars(self, symbol, start_date, end_date):
        return self._bars


def _fundamental(
    symbol: str,
    available_date: date,
    *,
    fcf_yield: str,
    roic: str,
) -> FundamentalSnapshot:
    return FundamentalSnapshot(
        symbol=symbol,
        period_end=date(available_date.year - 1, 12, 31),
        available_date=available_date,
        revenue_growth_yoy=Decimal("0.08"),
        eps_growth_yoy=Decimal("0.10"),
        gross_margin=Decimal("0.55"),
        operating_margin=Decimal("0.20"),
        net_margin=Decimal("0.15"),
        return_on_equity=Decimal("0.24"),
        return_on_invested_capital=Decimal(roic),
        free_cash_flow_margin=Decimal("0.18"),
        pe_ratio=Decimal("16"),
        pb_ratio=Decimal("3"),
        ev_to_ebitda=Decimal("11"),
        earnings_yield=Decimal("0.06"),
        dividend_yield=Decimal("0.01"),
        free_cash_flow_yield=Decimal(fcf_yield),
        debt_to_equity=Decimal("0.4"),
        net_debt_to_ebitda=Decimal("0.8"),
        interest_coverage=Decimal("10"),
        current_ratio=Decimal("1.5"),
        analyst_eps_revision_90d=Decimal("0.04"),
    )


def _report(symbol: str, score: float, upside: float) -> StockValuationReport:
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
        bear_case_downside=-0.2,
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
