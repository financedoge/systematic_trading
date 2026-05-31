from datetime import date
from decimal import Decimal

from systematic_trading.domain.market import FundamentalSnapshot
from systematic_trading.research.stock_universe import US_STOCK_REPLACEMENT_UNIVERSE
from systematic_trading.storage.sqlite import SQLiteStore
from systematic_trading.valuation.quantitative import (
    build_quantitative_framework_screen,
    latest_available_fundamental,
    quantitative_stock_report,
)
from systematic_trading.valuation.screener import MarketFeatureSnapshot


def test_sqlite_store_returns_latest_fundamentals_available_at_date(tmp_path) -> None:
    store = SQLiteStore(tmp_path / "fundamentals.db")
    store.initialize()
    store.upsert_fundamental_snapshot(_fundamental("AAPL", date(2020, 2, 15), fcf_yield="0.03"))
    store.upsert_fundamental_snapshot(_fundamental("AAPL", date(2020, 8, 15), fcf_yield="0.10"))

    snapshot = store.latest_fundamental_snapshot("AAPL", as_of=date(2020, 6, 1))

    assert snapshot is not None
    assert snapshot.available_date == date(2020, 2, 15)
    assert snapshot.free_cash_flow_yield == Decimal("0.03")


def test_latest_available_fundamental_ignores_future_snapshot() -> None:
    snapshots = [
        _fundamental("MSFT", date(2020, 2, 15), fcf_yield="0.02"),
        _fundamental("MSFT", date(2020, 8, 15), fcf_yield="0.12"),
    ]

    selected = latest_available_fundamental(snapshots, as_of=date(2020, 6, 1))

    assert selected is not None
    assert selected.available_date == date(2020, 2, 15)


def test_quantitative_screen_reranks_from_time_gated_fundamentals() -> None:
    instruments = {
        "AAPL": US_STOCK_REPLACEMENT_UNIVERSE["AAPL"],
        "MSFT": US_STOCK_REPLACEMENT_UNIVERSE["MSFT"],
    }
    features = {
        "AAPL": _feature("AAPL"),
        "MSFT": _feature("MSFT"),
    }
    fundamentals = {
        "AAPL": [
            _fundamental("AAPL", date(2020, 2, 15), fcf_yield="0.10", roic="0.24"),
            _fundamental("AAPL", date(2020, 8, 15), fcf_yield="0.02", roic="0.05"),
        ],
        "MSFT": [
            _fundamental("MSFT", date(2020, 2, 15), fcf_yield="0.02", roic="0.05"),
            _fundamental("MSFT", date(2020, 8, 15), fcf_yield="0.11", roic="0.25"),
        ],
    }

    early = build_quantitative_framework_screen(
        instruments=instruments,
        features=features,
        fundamentals_by_symbol=fundamentals,
        as_of=date(2020, 6, 1),
    )
    late = build_quantitative_framework_screen(
        instruments=instruments,
        features=features,
        fundamentals_by_symbol=fundamentals,
        as_of=date(2020, 9, 1),
    )

    assert early.reports[0].ticker == "AAPL"
    assert late.reports[0].ticker == "MSFT"


def test_quantitative_report_caps_stress_scenario_above_zero() -> None:
    report = quantitative_stock_report(
        instrument=US_STOCK_REPLACEMENT_UNIVERSE["AAPL"],
        feature=_feature("AAPL").model_copy(update={"realized_volatility_63d": 1.2}),
        fundamental=_fundamental("AAPL", date(2020, 2, 15), fcf_yield="0.10", roic="0.24"),
        as_of=date(2020, 6, 1),
    )

    assert min(scenario.fair_value for scenario in report.scenarios) > 0


def _fundamental(
    symbol: str,
    available_date: date,
    *,
    fcf_yield: str,
    roic: str = "0.18",
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


def _feature(symbol: str) -> MarketFeatureSnapshot:
    return MarketFeatureSnapshot(
        ticker=symbol,
        as_of=date(2020, 5, 29),
        current_price=100,
        return_21d=0.02,
        return_63d=0.05,
        return_252d=0.08,
        drawdown_252d=-0.10,
        realized_volatility_63d=0.25,
        volume_ratio_21d_126d=0.05,
        observations=300,
    )
