from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
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


def apply_target_overlays(targets, overlays, context):
    """Preserve an explicit fallback's membership and released cash downstream.

    Legacy chains are unchanged. A cash fallback sets a maximum gross budget;
    later reductions tighten it and later tilts may redistribute only inside it.
    """
    targets = list(targets)
    allowed = None
    budget = None
    for overlay in overlays:
        before = {t.symbol for t in targets}
        targets = overlay.apply(targets, context)
        if getattr(overlay, "cash_budget_active", False):
            allowed = {t.symbol for t in targets if t.target_weight > 0}
            budget = sum((t.target_weight for t in targets), Decimal(0))
        if allowed is not None:
            if (len(targets) != len(before) or {t.symbol for t in targets} != before
                    or any(not t.target_weight.is_finite() or t.target_weight < 0 for t in targets)):
                raise ValueError("Invalid downstream targets after cash fallback")
            targets = [t.model_copy(update={"target_weight": Decimal(0)})
                       if t.symbol not in allowed else t for t in targets]
            gross = sum((t.target_weight for t in targets), Decimal(0))
            if gross > budget:
                scale = budget / gross
                targets = [t.model_copy(update={"target_weight": t.target_weight * scale,
                    "rationale": t.rationale + " Protected fallback cash budget."}) for t in targets]
            budget = min(budget, sum((t.target_weight for t in targets), Decimal(0)))
    return targets
