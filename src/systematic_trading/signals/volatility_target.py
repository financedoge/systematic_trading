"""P4.18 fixed, monthly, no-leverage volatility scaling for research targets.

This shared app calculation changes exposure only. Registration, scheduling,
promotion and broker authority remain separate contracts.
"""
from dataclasses import dataclass
from decimal import Decimal

import numpy as np

from systematic_trading.signals.base import SignalContext


@dataclass
class VolatilityTargetOverlay:
    name: str = 'volatility-target-10pct-63-v1'
    target: float = .10
    lookback: int = 63

    def scale(self, targets, context: SignalContext):
        if self.target <= 0 or not np.isfinite(self.target) or self.lookback < 2:
            raise ValueError('Invalid volatility target or lookback')
        if any(not t.target_weight.is_finite() or t.target_weight < 0 for t in targets):
            raise ValueError('Expected finite long-only target weights')
        active = [t for t in targets if t.target_weight > 0]
        if not active:
            return 1.0, 0.0
        sessions = list(context.trade_dates[-(self.lookback + 1):])
        if len(sessions) != self.lookback + 1 or sessions != sorted(set(sessions)):
            raise ValueError('Volatility scaling requires the full prior session calendar')
        portfolio = np.zeros(self.lookback)
        for target in active:
            rows = context.bars_by_symbol.get(target.symbol, ())
            prices = {r.trade_date: float(r.close) for r in rows}
            if len(prices) != len(rows) or any(d not in prices for d in sessions):
                raise ValueError('Missing or duplicate volatility observation: ' + target.symbol)
            values = np.array([prices[d] for d in sessions])
            if not np.all(np.isfinite(values)) or np.any(values <= 0):
                raise ValueError('Invalid volatility price: ' + target.symbol)
            portfolio += float(target.target_weight) * (values[1:] / values[:-1] - 1)
        volatility = float(np.std(portfolio, ddof=1) * np.sqrt(252))
        return min(1.0, self.target / volatility) if volatility else 1.0, volatility

    def apply(self, targets, context: SignalContext):
        scale, volatility = self.scale(targets, context)
        return [t.model_copy(update={
            'target_weight': t.target_weight * Decimal(str(scale)),
            'rationale': t.rationale + f' P4.18 prior volatility {volatility:.4%}; exposure scale {scale:.6f}.',
        }) for t in targets]
