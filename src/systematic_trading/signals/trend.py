from __future__ import annotations

import math
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
        threshold_suffix = "" if self.threshold == Decimal("0") else f"-thr-{_threshold_label(self.threshold)}"
        self.name = f"ts-momentum-{lookback_bars}d-{mode}{threshold_suffix}"

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


class AdaptiveTrendOverlay:
    def __init__(
        self,
        *,
        short_lookback_bars: int = 63,
        medium_lookback_bars: int = 126,
        long_lookback_bars: int = 252,
        rebound_lookback_bars: int = 21,
        volume_lookback_bars: int = 21,
        fast_volatility_bars: int = 21,
        slow_volatility_bars: int = 252,
        short_threshold: Decimal = Decimal("0"),
        medium_threshold: Decimal = Decimal("-0.03"),
        long_threshold: Decimal = Decimal("-0.05"),
        rebound_threshold: Decimal = Decimal("0.03"),
        up_volume_threshold: Decimal = Decimal("0.58"),
        volatility_shock_threshold: Decimal = Decimal("1.20"),
        weak_scale: Decimal = Decimal("0.35"),
        neutral_scale: Decimal = Decimal("0.75"),
        defensive_scale: Decimal = Decimal("0.35"),
        rebound_scale: Decimal = Decimal("1.00"),
        reallocate_residual: bool = True,
    ) -> None:
        lookbacks = [
            short_lookback_bars,
            medium_lookback_bars,
            long_lookback_bars,
            rebound_lookback_bars,
            volume_lookback_bars,
            fast_volatility_bars,
            slow_volatility_bars,
        ]
        if any(item < 2 for item in lookbacks):
            raise ValueError("All adaptive trend lookbacks must be at least 2.")
        self.short_lookback_bars = short_lookback_bars
        self.medium_lookback_bars = medium_lookback_bars
        self.long_lookback_bars = long_lookback_bars
        self.rebound_lookback_bars = rebound_lookback_bars
        self.volume_lookback_bars = volume_lookback_bars
        self.fast_volatility_bars = fast_volatility_bars
        self.slow_volatility_bars = slow_volatility_bars
        self.short_threshold = Decimal(short_threshold)
        self.medium_threshold = Decimal(medium_threshold)
        self.long_threshold = Decimal(long_threshold)
        self.rebound_threshold = Decimal(rebound_threshold)
        self.up_volume_threshold = Decimal(up_volume_threshold)
        self.volatility_shock_threshold = Decimal(volatility_shock_threshold)
        self.weak_scale = Decimal(weak_scale)
        self.neutral_scale = Decimal(neutral_scale)
        self.defensive_scale = Decimal(defensive_scale)
        self.rebound_scale = Decimal(rebound_scale)
        self.reallocate_residual = reallocate_residual
        self.lookback_bars = long_lookback_bars
        self.threshold = self.long_threshold
        mode = "reallocate" if reallocate_residual else "cash"
        self.name = (
            f"adaptive-trend-{short_lookback_bars}-{medium_lookback_bars}-{long_lookback_bars}d-"
            f"{mode}-thr-{_threshold_label(self.long_threshold)}"
        )

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        adjusted: list[AllocationTarget] = []
        scale_by_symbol: dict[str, Decimal] = {}

        for target in targets:
            scale, rationale = self._scale(target.symbol, context)
            scale_by_symbol[target.symbol] = scale
            adjusted.append(
                target.model_copy(
                    update={
                        "target_weight": target.target_weight * scale,
                        "rationale": f"{target.rationale} {rationale}",
                    }
                )
            )

        if not self.reallocate_residual:
            return adjusted

        original_weight = sum((target.target_weight for target in targets), Decimal("0"))
        active_weight = sum((target.target_weight for target in adjusted), Decimal("0"))
        residual = original_weight - active_weight
        if residual <= Decimal("0"):
            return adjusted

        recipients = [target for target in adjusted if scale_by_symbol.get(target.symbol, Decimal("0")) >= self.neutral_scale]
        recipient_weight = sum((target.target_weight for target in recipients), Decimal("0"))
        if recipient_weight <= Decimal("0"):
            return adjusted

        return [
            target.model_copy(update={"target_weight": target.target_weight + residual * (target.target_weight / recipient_weight)})
            if target in recipients
            else target
            for target in adjusted
        ]

    def _scale(self, symbol: str, context: SignalContext) -> tuple[Decimal, str]:
        short = _momentum(symbol, context, self.short_lookback_bars)
        medium = _momentum(symbol, context, self.medium_lookback_bars)
        long = _momentum(symbol, context, self.long_lookback_bars)
        rebound = _momentum(symbol, context, self.rebound_lookback_bars)
        up_volume_share = _up_volume_share(symbol, context, self.volume_lookback_bars)
        volatility_ratio = _volatility_ratio(
            symbol,
            context,
            self.fast_volatility_bars,
            self.slow_volatility_bars,
        )

        score = self._trend_score(short, medium, long)
        if score is None:
            return Decimal("1"), "Adaptive trend overlay was neutral because not enough history was available."

        if score >= Decimal("0.67"):
            scale = Decimal("1")
            label = "full"
        elif score >= Decimal("0.34"):
            scale = self.neutral_scale
            label = "partial"
        else:
            scale = self.weak_scale
            label = "weak"

        if self._is_volatility_shock(short, medium, long, volatility_ratio):
            scale = min(scale, self.defensive_scale)
            label = "defensive"

        rebound_confirmed = (
            rebound is not None
            and rebound > self.rebound_threshold
            and _above_moving_average(symbol, context, self.short_lookback_bars)
        )
        volume_confirmed = (
            short is not None
            and short > self.short_threshold
            and up_volume_share is not None
            and up_volume_share >= self.up_volume_threshold
        )
        if rebound_confirmed:
            scale = max(scale, self.rebound_scale)
            label = "rebound"
        elif volume_confirmed:
            scale = max(scale, self.neutral_scale)
            label = "volume-confirmed"

        return (
            scale,
            (
                f"Adaptive trend overlay used {label} exposure at {scale:.0%}; "
                f"score={score:.2f}, short={_fmt_decimal_pct(short)}, medium={_fmt_decimal_pct(medium)}, "
                f"long={_fmt_decimal_pct(long)}, rebound={_fmt_decimal_pct(rebound)}, "
                f"up-volume={_fmt_decimal_pct(up_volume_share)}, vol-ratio={_fmt_decimal(volatility_ratio)}."
            ),
        )

    def _trend_score(
        self,
        short: Decimal | None,
        medium: Decimal | None,
        long: Decimal | None,
    ) -> Decimal | None:
        weighted_score = Decimal("0")
        weight_sum = Decimal("0")
        for value, threshold, weight in [
            (short, self.short_threshold, Decimal("0.35")),
            (medium, self.medium_threshold, Decimal("0.35")),
            (long, self.long_threshold, Decimal("0.30")),
        ]:
            if value is None:
                continue
            weight_sum += weight
            if value > threshold:
                weighted_score += weight
        if weight_sum <= Decimal("0"):
            return None
        return weighted_score / weight_sum

    def _is_volatility_shock(
        self,
        short: Decimal | None,
        medium: Decimal | None,
        long: Decimal | None,
        volatility_ratio: Decimal | None,
    ) -> bool:
        return (
            short is not None
            and medium is not None
            and long is not None
            and volatility_ratio is not None
            and short < self.short_threshold
            and medium < Decimal("-0.08")
            and long < Decimal("-0.10")
            and volatility_ratio > self.volatility_shock_threshold
        )


class RegimeGatedRelativeMomentumOverlay:
    def __init__(
        self,
        *,
        medium_lookback_bars: int = 126,
        long_lookback_bars: int = 252,
        fast_volatility_bars: int = 21,
        slow_volatility_bars: int = 252,
        drawdown_lookback_bars: int = 252,
        calm_tilt: Decimal = Decimal("0.12"),
        risk_tilt: Decimal = Decimal("0.12"),
        drawdown_trigger: Decimal = Decimal("-0.08"),
        volatility_ratio_trigger: Decimal = Decimal("1.35"),
        max_active_weight: Decimal = Decimal("0.07"),
    ) -> None:
        lookbacks = [
            medium_lookback_bars,
            long_lookback_bars,
            fast_volatility_bars,
            slow_volatility_bars,
            drawdown_lookback_bars,
        ]
        if any(item < 2 for item in lookbacks):
            raise ValueError("All relative momentum lookbacks must be at least 2.")
        self.medium_lookback_bars = medium_lookback_bars
        self.long_lookback_bars = long_lookback_bars
        self.fast_volatility_bars = fast_volatility_bars
        self.slow_volatility_bars = slow_volatility_bars
        self.drawdown_lookback_bars = drawdown_lookback_bars
        self.calm_tilt = Decimal(calm_tilt)
        self.risk_tilt = Decimal(risk_tilt)
        self.drawdown_trigger = Decimal(drawdown_trigger)
        self.volatility_ratio_trigger = Decimal(volatility_ratio_trigger)
        self.max_active_weight = Decimal(max_active_weight)
        self.lookback_bars = long_lookback_bars
        self.threshold = Decimal("0")
        self.name = f"relative-momentum-{medium_lookback_bars}-{long_lookback_bars}d-regime"

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        target_list = list(targets)
        if len(target_list) < 2:
            return list(target_list)

        scores = self._scores(target_list, context)
        if scores is None:
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Relative momentum overlay was neutral because enough "
                            "medium/long history was not available for the basket."
                        )
                    }
                )
                for target in target_list
            ]

        regime = self._regime([target.symbol for target in target_list], context)
        is_risk_regime = regime["drawdown"] <= self.drawdown_trigger or regime["volatilityRatio"] >= self.volatility_ratio_trigger
        tilt = self.risk_tilt if is_risk_regime else self.calm_tilt
        rank_scores = _rank_scores(scores)

        adjusted_weights: dict[str, Decimal] = {}
        for target in target_list:
            base_weight = target.target_weight
            multiplier = Decimal("1") + tilt * rank_scores[target.symbol]
            proposed_weight = max(Decimal("0"), base_weight * multiplier)
            delta = proposed_weight - base_weight
            if delta > self.max_active_weight:
                proposed_weight = base_weight + self.max_active_weight
            elif delta < -self.max_active_weight:
                proposed_weight = max(Decimal("0"), base_weight - self.max_active_weight)
            adjusted_weights[target.symbol] = proposed_weight

        original_weight = sum((target.target_weight for target in target_list), Decimal("0"))
        adjusted_weight = sum(adjusted_weights.values(), Decimal("0"))
        if adjusted_weight > Decimal("0") and original_weight > Decimal("0"):
            scale = original_weight / adjusted_weight
            adjusted_weights = {symbol: weight * scale for symbol, weight in adjusted_weights.items()}

        regime_label = "risk" if is_risk_regime else "calm"
        return [
            target.model_copy(
                update={
                    "target_weight": adjusted_weights[target.symbol],
                    "rationale": (
                        f"{target.rationale} Relative momentum overlay applied a {tilt:.0%} {regime_label}-regime "
                        f"tilt; score={_fmt_decimal_pct(scores[target.symbol])}, "
                        f"rank={rank_scores[target.symbol]:.2f}, basket drawdown={_fmt_decimal_pct(regime['drawdown'])}, "
                        f"basket vol-ratio={_fmt_decimal(regime['volatilityRatio'])}."
                    ),
                }
            )
            for target in target_list
        ]

    def _scores(
        self,
        targets: Sequence[AllocationTarget],
        context: SignalContext,
    ) -> dict[str, Decimal] | None:
        scores: dict[str, Decimal] = {}
        for target in targets:
            medium = _momentum(target.symbol, context, self.medium_lookback_bars)
            long = _momentum(target.symbol, context, self.long_lookback_bars)
            if medium is None or long is None:
                return None
            scores[target.symbol] = medium * Decimal("0.45") + long * Decimal("0.55")
        return scores

    def _regime(self, symbols: Sequence[str], context: SignalContext) -> dict[str, Decimal]:
        drawdowns = [
            item
            for symbol in symbols
            if (item := _drawdown_from_high(symbol, context, self.drawdown_lookback_bars)) is not None
        ]
        volatility_ratios = [
            item
            for symbol in symbols
            if (item := _volatility_ratio(symbol, context, self.fast_volatility_bars, self.slow_volatility_bars)) is not None
        ]
        return {
            "drawdown": sum(drawdowns, Decimal("0")) / Decimal(len(drawdowns)) if drawdowns else Decimal("0"),
            "volatilityRatio": (
                sum(volatility_ratios, Decimal("0")) / Decimal(len(volatility_ratios))
                if volatility_ratios
                else Decimal("1")
            ),
        }


def _momentum(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
    if len(history) < lookback_bars + 1:
        return None
    latest = history[-1]
    reference = history[-(lookback_bars + 1)]
    if reference.close == Decimal("0"):
        return None
    return (latest.close / reference.close) - Decimal("1")


def _above_moving_average(symbol: str, context: SignalContext, lookback_bars: int) -> bool:
    history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
    if len(history) < lookback_bars:
        return False
    lookback = history[-lookback_bars:]
    average = sum((bar.close for bar in lookback), Decimal("0")) / Decimal(len(lookback))
    return history[-1].close > average


def _up_volume_share(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
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


def _volatility_ratio(
    symbol: str,
    context: SignalContext,
    fast_bars: int,
    slow_bars: int,
) -> Decimal | None:
    history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
    if len(history) < slow_bars + 1:
        return None
    fast = _realized_volatility(history[-(fast_bars + 1) :])
    slow = _realized_volatility(history[-(slow_bars + 1) :])
    if fast is None or slow is None or slow == 0:
        return None
    return Decimal(str(fast / slow))


def _drawdown_from_high(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
    if len(history) < 2:
        return None
    lookback = history[-min(len(history), lookback_bars + 1) :]
    peak = max((bar.close for bar in lookback), default=Decimal("0"))
    if peak <= Decimal("0"):
        return None
    return (lookback[-1].close / peak) - Decimal("1")


def _rank_scores(scores: dict[str, Decimal]) -> dict[str, Decimal]:
    ranked = sorted(scores, key=lambda symbol: (scores[symbol], symbol))
    if len(ranked) == 1:
        return {ranked[0]: Decimal("0")}
    denominator = Decimal(len(ranked) - 1)
    return {
        symbol: (Decimal(index) / denominator) * Decimal("2") - Decimal("1")
        for index, symbol in enumerate(ranked)
    }


def _realized_volatility(bars: Sequence[object]) -> float | None:
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


def _fmt_decimal_pct(value: Decimal | None) -> str:
    return "n/a" if value is None else f"{value:.2%}"


def _fmt_decimal(value: Decimal | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _threshold_label(value: Decimal) -> str:
    return str(value.normalize()).replace("-", "m").replace(".", "p")
