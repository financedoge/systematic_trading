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


class TargetOverlay(Protocol):
    name: str

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        """Return adjusted allocation targets for one rebalance date."""
