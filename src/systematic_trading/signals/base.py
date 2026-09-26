from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Protocol, Sequence

from systematic_trading.domain.market import Instrument, PriceBar
from systematic_trading.domain.portfolio import AllocationTarget


@dataclass(frozen=True)
class SignalContext:
    as_of: date
    instruments: Mapping[str, Instrument]
    bars_by_symbol: Mapping[str, Sequence[PriceBar]]
    trade_dates: Sequence[date]


    def __post_init__(self) -> None:
        # A signal cannot see the execution-day close, or any future bars.
        object.__setattr__(self, "bars_by_symbol", {
            symbol: tuple(bar for bar in bars if bar.trade_date < self.as_of)
            for symbol, bars in self.bars_by_symbol.items()
        })
        object.__setattr__(self, "trade_dates", tuple(day for day in self.trade_dates if day < self.as_of))


class TargetOverlay(Protocol):
    name: str

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        """Return adjusted allocation targets for one rebalance date."""
