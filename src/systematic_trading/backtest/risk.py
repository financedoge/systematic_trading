from __future__ import annotations

import math
from decimal import Decimal, ROUND_HALF_UP
from typing import Mapping, Sequence

WEIGHT_STEP = Decimal("0.0001")


def realized_volatility(returns: Sequence[Decimal | float], periods_per_year: int = 252) -> Decimal:
    clean = [float(item) for item in returns]
    if len(clean) < 2:
        return Decimal("0.0000")

    mean = sum(clean) / len(clean)
    variance = sum((item - mean) ** 2 for item in clean) / (len(clean) - 1)
    annualized = math.sqrt(variance * periods_per_year)
    return Decimal(str(annualized)).quantize(WEIGHT_STEP, rounding=ROUND_HALF_UP)


def inverse_volatility_weights(
    volatility_by_symbol: Mapping[str, Decimal],
    *,
    max_weight: Decimal = Decimal("0.35"),
) -> dict[str, Decimal]:
    if not volatility_by_symbol:
        raise ValueError("At least one volatility observation is required.")
    if Decimal(max_weight) <= 0:
        raise ValueError("max_weight must be positive.")
    if Decimal(max_weight) * len(volatility_by_symbol) < Decimal("1"):
        raise ValueError("max_weight is too low to allocate the full portfolio.")

    inverse = {symbol: Decimal("1") / Decimal(volatility) for symbol, volatility in volatility_by_symbol.items()}
    capped: dict[str, Decimal] = {}
    remaining = dict(inverse)
    remaining_budget = Decimal("1")

    while remaining:
        total_inverse = sum(remaining.values())
        provisional = {symbol: remaining_budget * (value / total_inverse) for symbol, value in remaining.items()}
        breaches = {symbol for symbol, weight in provisional.items() if weight > Decimal(max_weight)}

        if not breaches:
            capped.update(provisional)
            break

        for symbol in breaches:
            capped[symbol] = Decimal(max_weight)
            remaining_budget -= Decimal(max_weight)
            remaining.pop(symbol)

    rounded = {
        symbol: Decimal(weight).quantize(WEIGHT_STEP, rounding=ROUND_HALF_UP)
        for symbol, weight in capped.items()
    }
    residual = Decimal("1.0000") - sum(rounded.values())
    if residual != Decimal("0.0000"):
        largest = max(rounded, key=rounded.get)
        rounded[largest] = (rounded[largest] + residual).quantize(WEIGHT_STEP, rounding=ROUND_HALF_UP)
    return dict(sorted(rounded.items()))
