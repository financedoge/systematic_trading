from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Sequence

from pydantic import BaseModel, Field

from systematic_trading.backtest.risk import inverse_volatility_weights
from systematic_trading.domain.market import Instrument
from systematic_trading.domain.portfolio import AllocationTarget

PERCENT_STEP = Decimal("0.01")


class BetaInstrumentState(BaseModel):
    instrument: Instrument
    realized_volatility: Decimal = Field(gt=0)


class RiskParityBetaSleeve:
    def __init__(self, *, name: str = "beta-risk-parity", max_weight: Decimal = Decimal("0.35")) -> None:
        self.name = name
        self.max_weight = Decimal(max_weight)

    def generate_targets(self, states: Sequence[BetaInstrumentState]) -> list[AllocationTarget]:
        volatility_map = {state.instrument.symbol: state.realized_volatility for state in states}
        weights = inverse_volatility_weights(volatility_map, max_weight=self.max_weight)

        targets: list[AllocationTarget] = []
        state_by_symbol = {state.instrument.symbol: state for state in states}
        for symbol, weight in sorted(weights.items(), key=lambda item: item[1], reverse=True):
            state = state_by_symbol[symbol]
            vol_pct = (state.realized_volatility * Decimal("100")).quantize(PERCENT_STEP, rounding=ROUND_HALF_UP)
            targets.append(
                AllocationTarget(
                    symbol=symbol,
                    target_weight=weight,
                    sleeve=self.name,
                    rationale=(
                        f"Inverse-volatility beta allocation. {symbol} receives a {weight:.2%} target because "
                        f"its realized volatility is {vol_pct}% and diversification is preferred over concentrated risk."
                    ),
                    hold_horizon_months=12,
                )
            )
        return targets
