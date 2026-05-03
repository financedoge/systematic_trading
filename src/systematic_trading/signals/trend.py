from __future__ import annotations

from decimal import Decimal
from typing import Sequence

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals.base import SignalContext


class TimeSeriesMomentumOverlay:
    def __init__(
        self,
        *,
        lookback_bars: int = 252,
        threshold: Decimal = Decimal("0"),
        reallocate_survivors: bool = False,
    ) -> None:
        if lookback_bars < 2:
            raise ValueError("lookback_bars must be at least 2.")
        self.lookback_bars = lookback_bars
        self.threshold = Decimal(threshold)
        self.reallocate_survivors = reallocate_survivors
        mode = "reallocate" if reallocate_survivors else "cash"
        self.name = f"ts-momentum-{lookback_bars}d-{mode}"

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        adjusted: list[AllocationTarget] = []
        active_weight = Decimal("0")
        original_weight = sum((target.target_weight for target in targets), Decimal("0"))

        for target in targets:
            momentum = self._momentum(target.symbol, context)
            if momentum is None:
                adjusted.append(
                    target.model_copy(
                        update={
                            "rationale": (
                                f"{target.rationale} Time-series momentum overlay was neutral because "
                                f"{self.lookback_bars} prior bars were not available."
                            )
                        }
                    )
                )
                active_weight += target.target_weight
                continue

            if momentum > self.threshold:
                adjusted.append(
                    target.model_copy(
                        update={
                            "rationale": (
                                f"{target.rationale} Time-series momentum overlay kept the allocation because "
                                f"{target.symbol}'s {self.lookback_bars}-bar return was {momentum:.2%}."
                            )
                        }
                    )
                )
                active_weight += target.target_weight
                continue

            adjusted.append(
                target.model_copy(
                    update={
                        "target_weight": Decimal("0"),
                        "rationale": (
                            f"{target.rationale} Time-series momentum overlay set the allocation to cash because "
                            f"{target.symbol}'s {self.lookback_bars}-bar return was {momentum:.2%}."
                        ),
                    }
                )
            )

        if not self.reallocate_survivors or active_weight <= Decimal("0"):
            return adjusted

        scale = original_weight / active_weight
        return [
            target.model_copy(update={"target_weight": target.target_weight * scale})
            if target.target_weight > Decimal("0")
            else target
            for target in adjusted
        ]

    def _momentum(self, symbol: str, context: SignalContext) -> Decimal | None:
        history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
        if len(history) < self.lookback_bars + 1:
            return None

        latest = history[-1]
        reference = history[-(self.lookback_bars + 1)]
        return (latest.close / reference.close) - Decimal("1")
