from decimal import Decimal

from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument
from systematic_trading.portfolio.beta import BetaInstrumentState, RiskParityBetaSleeve


def test_risk_parity_targets_reward_lower_realized_volatility() -> None:
    instruments = [
        Instrument(
            symbol="SPY",
            name="SPDR S&P 500 ETF Trust",
            asset_class=AssetClass.ETF,
            exchange=Exchange.NYSE,
            quote_currency=Currency.USD,
            country="US",
        ),
        Instrument(
            symbol="VGK",
            name="Vanguard FTSE Europe ETF",
            asset_class=AssetClass.ETF,
            exchange=Exchange.NYSE,
            quote_currency=Currency.USD,
            country="Europe",
        ),
        Instrument(
            symbol="2800.HK",
            name="Tracker Fund of Hong Kong",
            asset_class=AssetClass.ETF,
            exchange=Exchange.HKEX,
            quote_currency=Currency.HKD,
            country="HK",
        ),
    ]
    states = [
        BetaInstrumentState(instrument=instruments[0], realized_volatility=Decimal("0.18")),
        BetaInstrumentState(instrument=instruments[1], realized_volatility=Decimal("0.14")),
        BetaInstrumentState(instrument=instruments[2], realized_volatility=Decimal("0.24")),
    ]

    targets = RiskParityBetaSleeve(max_weight=Decimal("0.50")).generate_targets(states)
    weights = {target.symbol: target.target_weight for target in targets}

    assert sum(weights.values()) == Decimal("1.0000")
    assert weights["VGK"] > weights["SPY"] > weights["2800.HK"]
    assert max(weights.values()) <= Decimal("0.5000")
