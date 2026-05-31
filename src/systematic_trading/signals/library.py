from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

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
        "macd_line_12_26",
        "technical",
        "MACD 12/26 line",
        "12-bar EMA minus 26-bar EMA, divided by latest close.",
        26,
    ),
    SignalFeatureSpec(
        "macd_hist_12_26_9",
        "technical",
        "MACD 12/26/9 histogram",
        "MACD line minus its 9-bar signal EMA, divided by latest close.",
        35,
    ),
    SignalFeatureSpec(
        "bollinger_z_20",
        "technical",
        "20-bar Bollinger z-score",
        "Latest close minus the 20-bar average, divided by the 20-bar close standard deviation.",
        20,
    ),
    SignalFeatureSpec(
        "bollinger_pct_b_20",
        "technical",
        "20-bar Bollinger percent-b",
        "Position of latest close inside 2-standard-deviation Bollinger bands.",
        20,
    ),
    SignalFeatureSpec(
        "bollinger_bandwidth_20",
        "technical",
        "20-bar Bollinger bandwidth",
        "Upper minus lower Bollinger band, divided by the 20-bar average.",
        20,
    ),
    SignalFeatureSpec(
        "rsi_14",
        "technical",
        "14-bar RSI",
        "Relative strength index scaled to -1 to +1, where positive means stronger upside pressure.",
        14,
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
    history = _history(symbol, context)
    mom_20 = _momentum_from_history(history, 20)
    mom_21 = _momentum_from_history(history, 21)
    mom_40 = _momentum_from_history(history, 40)
    mom_60 = _momentum_from_history(history, 60)
    mom_63 = _momentum_from_history(history, 63)
    mom_126 = _momentum_from_history(history, 126)
    mom_252 = _momentum_from_history(history, 252)
    mom_378 = _momentum_from_history(history, 378)
    ma_dev_63 = _moving_average_deviation_from_history(history, 63)
    macd = _macd_from_history(history, 12, 26, 9)
    bollinger = _bollinger_from_history(history, 20, Decimal("2"))
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
        "above_ma_63": _above_moving_average_from_history(history, 63),
        "above_ma_252": _above_moving_average_from_history(history, 252),
        "reversal_21": _float(-mom_21 if mom_21 is not None else None),
        "mean_reversion_ma_63": _float(-ma_dev_63 if ma_dev_63 is not None else None),
        "macd_line_12_26": _float(macd["line"] if macd is not None else None),
        "macd_hist_12_26_9": _float(macd["histogram"] if macd is not None else None),
        "bollinger_z_20": _float(bollinger["z"] if bollinger is not None else None),
        "bollinger_pct_b_20": _float(bollinger["percent_b"] if bollinger is not None else None),
        "bollinger_bandwidth_20": _float(bollinger["bandwidth"] if bollinger is not None else None),
        "rsi_14": _float(_rsi_from_history(history, 14)),
        "up_volume_share_21": _float(_up_volume_share_from_history(history, 21)),
        "signed_volume_pressure_21_126": _float(_signed_volume_pressure_from_history(history, 21, 126)),
        "vol_ratio_21_252": _float(_volatility_ratio_from_history(history, 21, 252)),
        "drawdown_252": _float(_drawdown_from_high_from_history(history, 252)),
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
    return _momentum_from_history(_history(symbol, context), lookback_bars)


def _momentum_from_history(history: Sequence[object], lookback_bars: int) -> Decimal | None:
    if len(history) < lookback_bars + 1:
        return None
    latest = history[-1]
    reference = history[-(lookback_bars + 1)]
    if reference.close <= Decimal("0"):
        return None
    return (latest.close / reference.close) - Decimal("1")


def _above_moving_average(symbol: str, context: SignalContext, lookback_bars: int) -> float | None:
    return _above_moving_average_from_history(_history(symbol, context), lookback_bars)


def _above_moving_average_from_history(history: Sequence[object], lookback_bars: int) -> float | None:
    deviation = _moving_average_deviation_from_history(history, lookback_bars)
    return None if deviation is None else float(deviation > Decimal("0"))


def _moving_average_deviation(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    return _moving_average_deviation_from_history(_history(symbol, context), lookback_bars)


def _moving_average_deviation_from_history(history: Sequence[object], lookback_bars: int) -> Decimal | None:
    if len(history) < lookback_bars:
        return None
    lookback = history[-lookback_bars:]
    average = sum((bar.close for bar in lookback), Decimal("0")) / Decimal(len(lookback))
    if average <= Decimal("0"):
        return None
    return (history[-1].close / average) - Decimal("1")


def _macd(symbol: str, context: SignalContext, fast_bars: int, slow_bars: int, signal_bars: int) -> dict[str, Decimal] | None:
    return _macd_from_history(_history(symbol, context), fast_bars, slow_bars, signal_bars)


def _macd_from_history(history: Sequence[object], fast_bars: int, slow_bars: int, signal_bars: int) -> dict[str, Decimal] | None:
    if len(history) < slow_bars + signal_bars:
        return None
    closes = [Decimal(bar.close) for bar in history]
    if closes[-1] <= Decimal("0"):
        return None
    fast_ema = _ema_series(closes, fast_bars)
    slow_ema = _ema_series(closes, slow_bars)
    offset = len(fast_ema) - len(slow_ema)
    macd_values = [fast_ema[index + offset] - slow_ema[index] for index in range(len(slow_ema))]
    if len(macd_values) < signal_bars:
        return None
    signal = _ema_series(macd_values, signal_bars)[-1]
    line = macd_values[-1]
    return {
        "line": line / closes[-1],
        "histogram": (line - signal) / closes[-1],
    }


def _ema_series(values: list[Decimal], lookback_bars: int) -> list[Decimal]:
    if len(values) < lookback_bars:
        return []
    alpha = Decimal("2") / Decimal(lookback_bars + 1)
    ema = sum(values[:lookback_bars], Decimal("0")) / Decimal(lookback_bars)
    series = [ema]
    for value in values[lookback_bars:]:
        ema = (value - ema) * alpha + ema
        series.append(ema)
    return series


def _bollinger(symbol: str, context: SignalContext, lookback_bars: int, band_width: Decimal) -> dict[str, Decimal] | None:
    return _bollinger_from_history(_history(symbol, context), lookback_bars, band_width)


def _bollinger_from_history(history: Sequence[object], lookback_bars: int, band_width: Decimal) -> dict[str, Decimal] | None:
    if len(history) < lookback_bars:
        return None
    closes = [Decimal(bar.close) for bar in history[-lookback_bars:]]
    average = sum(closes, Decimal("0")) / Decimal(lookback_bars)
    if average <= Decimal("0"):
        return None
    variance = sum((close - average) ** 2 for close in closes) / Decimal(lookback_bars)
    standard_deviation = Decimal(str(math.sqrt(float(variance))))
    if standard_deviation <= Decimal("0"):
        return None
    latest = closes[-1]
    upper = average + band_width * standard_deviation
    lower = average - band_width * standard_deviation
    band_range = upper - lower
    return {
        "z": (latest - average) / standard_deviation,
        "percent_b": (latest - lower) / band_range if band_range > Decimal("0") else Decimal("0.5"),
        "bandwidth": band_range / average,
    }


def _rsi(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    return _rsi_from_history(_history(symbol, context), lookback_bars)


def _rsi_from_history(history: Sequence[object], lookback_bars: int) -> Decimal | None:
    if len(history) < lookback_bars + 1:
        return None
    closes = [Decimal(bar.close) for bar in history[-(lookback_bars + 1) :]]
    gains: list[Decimal] = []
    losses: list[Decimal] = []
    for index in range(1, len(closes)):
        change = closes[index] - closes[index - 1]
        if change >= Decimal("0"):
            gains.append(change)
            losses.append(Decimal("0"))
        else:
            gains.append(Decimal("0"))
            losses.append(abs(change))
    average_gain = sum(gains, Decimal("0")) / Decimal(lookback_bars)
    average_loss = sum(losses, Decimal("0")) / Decimal(lookback_bars)
    if average_loss == Decimal("0"):
        return Decimal("1")
    rs = average_gain / average_loss
    rsi = Decimal("100") - (Decimal("100") / (Decimal("1") + rs))
    return (rsi / Decimal("50")) - Decimal("1")


def _up_volume_share(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    return _up_volume_share_from_history(_history(symbol, context), lookback_bars)


def _up_volume_share_from_history(history: Sequence[object], lookback_bars: int) -> Decimal | None:
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
    return _signed_volume_pressure_from_history(_history(symbol, context), fast_bars, slow_bars)


def _signed_volume_pressure_from_history(history: Sequence[object], fast_bars: int, slow_bars: int) -> Decimal | None:
    fast_average = _average_volume_from_history(history, fast_bars)
    slow_average = _average_volume_from_history(history, slow_bars)
    short_momentum = _momentum_from_history(history, fast_bars)
    if fast_average is None or slow_average is None or slow_average <= Decimal("0") or short_momentum is None:
        return None
    pressure = (fast_average / slow_average) - Decimal("1")
    return pressure if short_momentum >= Decimal("0") else -pressure


def _average_volume(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    return _average_volume_from_history(_history(symbol, context), lookback_bars)


def _average_volume_from_history(history: Sequence[object], lookback_bars: int) -> Decimal | None:
    if len(history) < lookback_bars:
        return None
    volumes = [Decimal(bar.volume) for bar in history[-lookback_bars:]]
    return sum(volumes, Decimal("0")) / Decimal(len(volumes))


def _volatility_ratio(symbol: str, context: SignalContext, fast_bars: int, slow_bars: int) -> Decimal | None:
    return _volatility_ratio_from_history(_history(symbol, context), fast_bars, slow_bars)


def _volatility_ratio_from_history(history: Sequence[object], fast_bars: int, slow_bars: int) -> Decimal | None:
    if len(history) < slow_bars + 1:
        return None
    fast = _realized_volatility(history[-(fast_bars + 1) :])
    slow = _realized_volatility(history[-(slow_bars + 1) :])
    if fast is None or slow is None or slow == 0:
        return None
    return Decimal(str(fast / slow))


def _drawdown_from_high(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    return _drawdown_from_high_from_history(_history(symbol, context), lookback_bars)


def _drawdown_from_high_from_history(history: Sequence[object], lookback_bars: int) -> Decimal | None:
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
