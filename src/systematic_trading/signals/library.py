from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from systematic_trading.signals.base import SignalContext


@dataclass(frozen=True)
class SignalFeatureSpec:
    feature_id: str
    family: str
    name: str
    description: str
    lookback_bars: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "featureId": self.feature_id,
            "family": self.family,
            "name": self.name,
            "description": self.description,
            "lookbackBars": self.lookback_bars,
        }


SIGNAL_LIBRARY: tuple[SignalFeatureSpec, ...] = (
    SignalFeatureSpec("mom_20", "price_trend", "20-bar momentum", "Promoted SOTA short-horizon price return.", 20),
    SignalFeatureSpec("mom_21", "price_trend", "21-bar momentum", "Short-term price return.", 21),
    SignalFeatureSpec("mom_40", "price_trend", "40-bar momentum", "Two-month price return tested in short-horizon momentum research.", 40),
    SignalFeatureSpec("mom_60", "price_trend", "60-bar momentum", "Promoted SOTA medium-horizon price return.", 60),
    SignalFeatureSpec("mom_63", "price_trend", "63-bar momentum", "Quarterly price return.", 63),
    SignalFeatureSpec("mom_126", "price_trend", "126-bar momentum", "Medium-term price return.", 126),
    SignalFeatureSpec("mom_252", "price_trend", "252-bar momentum", "Long-term price return.", 252),
    SignalFeatureSpec("mom_378", "price_trend", "378-bar momentum", "Extended trend return.", 378),
    SignalFeatureSpec(
        "relative_momentum_20_60",
        "price_trend",
        "20/60 relative momentum",
        "Promoted SOTA blend: 45% 20-bar return plus 55% 60-bar return.",
        60,
    ),
    SignalFeatureSpec(
        "relative_momentum_126_252",
        "price_trend",
        "126/252 relative momentum",
        "Prior SOTA blend: 45% 126-bar return plus 55% 252-bar return.",
        252,
    ),
    SignalFeatureSpec("above_ma_63", "price_trend", "Above 63-bar MA", "1 when close is above its 63-bar average.", 63),
    SignalFeatureSpec("above_ma_252", "price_trend", "Above 252-bar MA", "1 when close is above its 252-bar average.", 252),
    SignalFeatureSpec("reversal_21", "mean_reversion", "21-bar reversal", "Negative of 21-bar momentum.", 21),
    SignalFeatureSpec(
        "mean_reversion_ma_63",
        "mean_reversion",
        "63-bar MA reversion",
        "Negative of price deviation from the 63-bar moving average.",
        63,
    ),
    SignalFeatureSpec(
        "up_volume_share_21",
        "volume",
        "21-bar up-volume share",
        "Share of recent volume traded on up-close days.",
        21,
    ),
    SignalFeatureSpec(
        "signed_volume_pressure_21_126",
        "volume",
        "Signed volume pressure",
        "21-bar volume acceleration, positive when short momentum is positive and negative when it is weak.",
        126,
    ),
    SignalFeatureSpec(
        "vol_ratio_21_252",
        "risk_regime",
        "21/252 volatility ratio",
        "Fast realized volatility divided by slow realized volatility.",
        252,
    ),
    SignalFeatureSpec("drawdown_252", "risk_regime", "252-bar drawdown", "Drawdown from the trailing 252-bar high.", 252),
    SignalFeatureSpec(
        "valuation_score",
        "valuation",
        "Valuation score",
        "External score map. Positive means cheaper or more attractive.",
    ),
    SignalFeatureSpec(
        "macro_growth_score",
        "macro",
        "Macro growth score",
        "External country score map. Positive means stronger growth or policy backdrop.",
    ),
)


def signal_library_rows() -> list[dict[str, Any]]:
    return [spec.to_dict() for spec in SIGNAL_LIBRARY]


def signal_feature_ids() -> list[str]:
    return [spec.feature_id for spec in SIGNAL_LIBRARY]


def max_signal_lookback_bars() -> int:
    return max((spec.lookback_bars or 0 for spec in SIGNAL_LIBRARY), default=0)


def compute_signal_features(
    *,
    symbol: str,
    context: SignalContext,
    valuation_scores: Mapping[str, Decimal | str | int | float] | None = None,
    macro_scores: Mapping[str, Decimal | str | int | float] | None = None,
) -> dict[str, float | None]:
    valuation = _score_map(valuation_scores)
    macro = _score_map(macro_scores)
    mom_20 = _momentum(symbol, context, 20)
    mom_21 = _momentum(symbol, context, 21)
    mom_40 = _momentum(symbol, context, 40)
    mom_60 = _momentum(symbol, context, 60)
    mom_63 = _momentum(symbol, context, 63)
    mom_126 = _momentum(symbol, context, 126)
    mom_252 = _momentum(symbol, context, 252)
    mom_378 = _momentum(symbol, context, 378)
    ma_dev_63 = _moving_average_deviation(symbol, context, 63)
    return {
        "mom_20": _float(mom_20),
        "mom_21": _float(mom_21),
        "mom_40": _float(mom_40),
        "mom_60": _float(mom_60),
        "mom_63": _float(mom_63),
        "mom_126": _float(mom_126),
        "mom_252": _float(mom_252),
        "mom_378": _float(mom_378),
        "relative_momentum_20_60": _float(
            mom_20 * Decimal("0.45") + mom_60 * Decimal("0.55")
            if mom_20 is not None and mom_60 is not None
            else None
        ),
        "relative_momentum_126_252": _float(
            mom_126 * Decimal("0.45") + mom_252 * Decimal("0.55")
            if mom_126 is not None and mom_252 is not None
            else None
        ),
        "above_ma_63": _above_moving_average(symbol, context, 63),
        "above_ma_252": _above_moving_average(symbol, context, 252),
        "reversal_21": _float(-mom_21 if mom_21 is not None else None),
        "mean_reversion_ma_63": _float(-ma_dev_63 if ma_dev_63 is not None else None),
        "up_volume_share_21": _float(_up_volume_share(symbol, context, 21)),
        "signed_volume_pressure_21_126": _float(_signed_volume_pressure(symbol, context, 21, 126)),
        "vol_ratio_21_252": _float(_volatility_ratio(symbol, context, 21, 252)),
        "drawdown_252": _float(_drawdown_from_high(symbol, context, 252)),
        "valuation_score": _float(valuation.get(symbol.upper(), Decimal("0"))),
        "macro_growth_score": _float(macro.get(symbol.upper(), Decimal("0"))),
    }


def write_signal_library_markdown(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Signal Library",
        "",
        "This is the code-backed feature library used by research overlays and the decision-tree trainer.",
        "",
        "| Feature ID | Family | Name | Lookback | Description |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for spec in SIGNAL_LIBRARY:
        lookback = str(spec.lookback_bars) if spec.lookback_bars is not None else "n/a"
        lines.append(
            f"| `{spec.feature_id}` | {spec.family} | {spec.name} | {lookback} | {spec.description} |"
        )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _momentum(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = _history(symbol, context)
    if len(history) < lookback_bars + 1:
        return None
    latest = history[-1]
    reference = history[-(lookback_bars + 1)]
    if reference.close <= Decimal("0"):
        return None
    return (latest.close / reference.close) - Decimal("1")


def _above_moving_average(symbol: str, context: SignalContext, lookback_bars: int) -> float | None:
    deviation = _moving_average_deviation(symbol, context, lookback_bars)
    return None if deviation is None else float(deviation > Decimal("0"))


def _moving_average_deviation(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = _history(symbol, context)
    if len(history) < lookback_bars:
        return None
    lookback = history[-lookback_bars:]
    average = sum((bar.close for bar in lookback), Decimal("0")) / Decimal(len(lookback))
    if average <= Decimal("0"):
        return None
    return (history[-1].close / average) - Decimal("1")


def _up_volume_share(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = _history(symbol, context)
    if len(history) < lookback_bars + 1:
        return None
    lookback = history[-(lookback_bars + 1) :]
    up_volume = Decimal("0")
    total_volume = Decimal("0")
    for index in range(1, len(lookback)):
        volume = Decimal(lookback[index].volume)
        total_volume += volume
        if lookback[index].close > lookback[index - 1].close:
            up_volume += volume
    if total_volume <= Decimal("0"):
        return None
    return up_volume / total_volume


def _signed_volume_pressure(symbol: str, context: SignalContext, fast_bars: int, slow_bars: int) -> Decimal | None:
    fast_average = _average_volume(symbol, context, fast_bars)
    slow_average = _average_volume(symbol, context, slow_bars)
    short_momentum = _momentum(symbol, context, fast_bars)
    if fast_average is None or slow_average is None or slow_average <= Decimal("0") or short_momentum is None:
        return None
    pressure = (fast_average / slow_average) - Decimal("1")
    return pressure if short_momentum >= Decimal("0") else -pressure


def _average_volume(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = _history(symbol, context)
    if len(history) < lookback_bars:
        return None
    volumes = [Decimal(bar.volume) for bar in history[-lookback_bars:]]
    return sum(volumes, Decimal("0")) / Decimal(len(volumes))


def _volatility_ratio(symbol: str, context: SignalContext, fast_bars: int, slow_bars: int) -> Decimal | None:
    history = _history(symbol, context)
    if len(history) < slow_bars + 1:
        return None
    fast = _realized_volatility(history[-(fast_bars + 1) :])
    slow = _realized_volatility(history[-(slow_bars + 1) :])
    if fast is None or slow is None or slow == 0:
        return None
    return Decimal(str(fast / slow))


def _drawdown_from_high(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = _history(symbol, context)
    if len(history) < 2:
        return None
    lookback = history[-min(len(history), lookback_bars + 1) :]
    peak = max((bar.close for bar in lookback), default=Decimal("0"))
    if peak <= Decimal("0"):
        return None
    return (lookback[-1].close / peak) - Decimal("1")


def _realized_volatility(bars: list[object]) -> float | None:
    returns: list[float] = []
    for index in range(1, len(bars)):
        previous = Decimal(bars[index - 1].close)
        current = Decimal(bars[index].close)
        if previous <= Decimal("0"):
            continue
        returns.append(float((current / previous) - Decimal("1")))
    if len(returns) < 2:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((item - mean) ** 2 for item in returns) / (len(returns) - 1)
    return math.sqrt(variance)


def _history(symbol: str, context: SignalContext) -> list[object]:
    return [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]


def _score_map(values: Mapping[str, Decimal | str | int | float] | None) -> dict[str, Decimal]:
    if values is None:
        return {}
    return {symbol.upper(): _clip(Decimal(str(value))) for symbol, value in values.items()}


def _clip(value: Decimal) -> Decimal:
    return max(Decimal("-1"), min(Decimal("1"), value))


def _float(value: Decimal | float | None) -> float | None:
    return None if value is None else float(value)
