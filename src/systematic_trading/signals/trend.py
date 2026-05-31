from __future__ import annotations

import math
from dataclasses import dataclass
from decimal import Decimal
from typing import Mapping, Sequence

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals.base import SignalContext


@dataclass(frozen=True)
class CompositeFactorScore:
    total: Decimal
    components: Mapping[str, Decimal]


@dataclass(frozen=True)
class AssetPoolSelectionScore:
    total: Decimal
    components: Mapping[str, Decimal]
    raw_metrics: Mapping[str, Decimal]


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


class AssetPoolFilterOverlay:
    def __init__(
        self,
        *,
        short_momentum_bars: int = 63,
        medium_momentum_bars: int = 126,
        long_momentum_bars: int = 252,
        volume_bars: int = 21,
        slow_volume_bars: int = 126,
        trend_weight: Decimal = Decimal("0.75"),
        volume_weight: Decimal = Decimal("0.25"),
        top_n: int = 6,
        min_selected: int = 2,
        require_positive_long_momentum: bool = True,
        min_long_momentum: Decimal = Decimal("0"),
        reallocate_selected: bool = True,
    ) -> None:
        lookbacks = [
            short_momentum_bars,
            medium_momentum_bars,
            long_momentum_bars,
            volume_bars,
            slow_volume_bars,
        ]
        if any(item < 2 for item in lookbacks):
            raise ValueError("All asset-pool filter lookbacks must be at least 2.")
        if top_n < 1:
            raise ValueError("top_n must be at least 1.")
        if min_selected < 1:
            raise ValueError("min_selected must be at least 1.")
        if Decimal(trend_weight) < Decimal("0") or Decimal(volume_weight) < Decimal("0"):
            raise ValueError("Asset-pool filter weights must be non-negative.")
        if Decimal(trend_weight) + Decimal(volume_weight) <= Decimal("0"):
            raise ValueError("At least one asset-pool filter weight must be positive.")

        self.short_momentum_bars = short_momentum_bars
        self.medium_momentum_bars = medium_momentum_bars
        self.long_momentum_bars = long_momentum_bars
        self.volume_bars = volume_bars
        self.slow_volume_bars = slow_volume_bars
        self.trend_weight = Decimal(trend_weight)
        self.volume_weight = Decimal(volume_weight)
        self.top_n = top_n
        self.min_selected = min_selected
        self.require_positive_long_momentum = require_positive_long_momentum
        self.min_long_momentum = Decimal(min_long_momentum)
        self.reallocate_selected = reallocate_selected
        self.lookback_bars = max(lookbacks)
        self.threshold = self.min_long_momentum
        mode = "reallocate" if reallocate_selected else "cash"
        momentum_gate = "pos" if require_positive_long_momentum else "rank"
        self.name = (
            f"asset-pool-filter-top{top_n}-{short_momentum_bars}-{medium_momentum_bars}-"
            f"{long_momentum_bars}d-{momentum_gate}-{mode}"
        )

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        target_list = list(targets)
        if len(target_list) < 2:
            return target_list

        scores = self._selection_scores(target_list, context)
        if scores is None:
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Asset-pool filter was neutral because not enough "
                            "price/volume history was available."
                        )
                    }
                )
                for target in target_list
            ]

        eligible_symbols = [
            symbol
            for symbol, score in scores.items()
            if (
                not self.require_positive_long_momentum
                or score.raw_metrics.get("longMomentum", Decimal("-1")) > self.min_long_momentum
            )
        ]
        ranked_symbols = sorted(
            eligible_symbols,
            key=lambda symbol: (-scores[symbol].total, symbol),
        )
        if len(ranked_symbols) < self.min_selected:
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Asset-pool filter was neutral because only "
                            f"{len(ranked_symbols)} assets passed the momentum gate; minimum is {self.min_selected}."
                        )
                    }
                )
                for target in target_list
            ]

        selected = set(ranked_symbols[: self.top_n])
        rank_by_symbol = {symbol: index + 1 for index, symbol in enumerate(ranked_symbols)}
        original_weight = sum((target.target_weight for target in target_list), Decimal("0"))
        selected_weight = sum((target.target_weight for target in target_list if target.symbol in selected), Decimal("0"))
        scale = original_weight / selected_weight if self.reallocate_selected and selected_weight > Decimal("0") else Decimal("1")

        adjusted: list[AllocationTarget] = []
        for target in target_list:
            score = scores.get(target.symbol)
            if target.symbol in selected:
                if score is None:
                    continue
                adjusted.append(
                    target.model_copy(
                        update={
                            "target_weight": target.target_weight * scale,
                            "rationale": (
                                f"{target.rationale} Asset-pool filter selected {target.symbol} "
                                f"rank {rank_by_symbol[target.symbol]}/{len(ranked_symbols)}; "
                                f"score={score.total:.2f}, long={_fmt_decimal_pct(score.raw_metrics.get('longMomentum'))}, "
                                f"{_component_summary(score.components)}."
                            ),
                        }
                    )
                )
                continue

            rank_text = str(rank_by_symbol[target.symbol]) if target.symbol in rank_by_symbol else "not eligible"
            score_text = "n/a" if score is None else f"{score.total:.2f}"
            long_text = "n/a" if score is None else _fmt_decimal_pct(score.raw_metrics.get("longMomentum"))
            adjusted.append(
                target.model_copy(
                    update={
                        "target_weight": Decimal("0"),
                        "rationale": (
                            f"{target.rationale} Asset-pool filter removed {target.symbol}; "
                            f"rank={rank_text}, score={score_text}, long={long_text}."
                        ),
                    }
                )
            )
        return adjusted

    def _selection_scores(
        self,
        targets: Sequence[AllocationTarget],
        context: SignalContext,
    ) -> dict[str, AssetPoolSelectionScore] | None:
        symbols = [target.symbol for target in targets]
        short_momentum = {symbol: _momentum(symbol, context, self.short_momentum_bars) for symbol in symbols}
        medium_momentum = {symbol: _momentum(symbol, context, self.medium_momentum_bars) for symbol in symbols}
        long_momentum = {symbol: _momentum(symbol, context, self.long_momentum_bars) for symbol in symbols}
        up_volume = {symbol: _up_volume_share(symbol, context, self.volume_bars) for symbol in symbols}
        signed_volume = {
            symbol: _signed_volume_pressure(symbol, context, self.volume_bars, self.slow_volume_bars)
            for symbol in symbols
        }

        category_values: dict[str, dict[str, Decimal]] = {}
        _add_category(
            category_values,
            "trend",
            [
                (Decimal("0.20"), _rank_metric(short_momentum)),
                (Decimal("0.35"), _rank_metric(medium_momentum)),
                (Decimal("0.45"), _rank_metric(long_momentum)),
            ],
        )
        _add_category(
            category_values,
            "volume",
            [
                (Decimal("0.65"), _rank_metric(up_volume)),
                (Decimal("0.35"), _rank_metric(signed_volume)),
            ],
        )
        if not category_values:
            return None

        category_weights = {
            "trend": self.trend_weight,
            "volume": self.volume_weight,
        }
        scores: dict[str, AssetPoolSelectionScore] = {}
        for symbol in symbols:
            weighted_score = Decimal("0")
            weight_sum = Decimal("0")
            components: dict[str, Decimal] = {}
            for category, weight in category_weights.items():
                if weight <= Decimal("0"):
                    continue
                value = category_values.get(category, {}).get(symbol)
                if value is None:
                    continue
                clipped = _clip(value, Decimal("-1"), Decimal("1"))
                components[category] = clipped
                weighted_score += weight * clipped
                weight_sum += weight
            if weight_sum <= Decimal("0"):
                continue
            raw_metrics = {
                key: value
                for key, value in {
                    "shortMomentum": short_momentum.get(symbol),
                    "mediumMomentum": medium_momentum.get(symbol),
                    "longMomentum": long_momentum.get(symbol),
                    "upVolumeShare": up_volume.get(symbol),
                    "signedVolumePressure": signed_volume.get(symbol),
                }.items()
                if value is not None
            }
            scores[symbol] = AssetPoolSelectionScore(
                total=_clip(weighted_score / weight_sum, Decimal("-1"), Decimal("1")),
                components=components,
                raw_metrics=raw_metrics,
            )
        return scores if len(scores) >= self.min_selected else None


class TrendQualityFilterOverlay:
    def __init__(
        self,
        *,
        short_momentum_bars: int = 63,
        medium_momentum_bars: int = 126,
        long_momentum_bars: int = 252,
        volatility_bars: int = 126,
        consistency_bars: int = 126,
        drawdown_lookback_bars: int = 252,
        momentum_weight: Decimal = Decimal("0.50"),
        risk_adjusted_weight: Decimal = Decimal("0.30"),
        consistency_weight: Decimal = Decimal("0.10"),
        drawdown_weight: Decimal = Decimal("0.10"),
        low_volatility_weight: Decimal = Decimal("0"),
        top_n: int = 6,
        min_selected: int = 3,
        require_positive_long_momentum: bool = True,
        min_long_momentum: Decimal = Decimal("0"),
        fallback_to_top_ranked: bool = True,
        reallocate_selected: bool = True,
    ) -> None:
        lookbacks = [
            short_momentum_bars,
            medium_momentum_bars,
            long_momentum_bars,
            volatility_bars,
            consistency_bars,
            drawdown_lookback_bars,
        ]
        if any(item < 2 for item in lookbacks):
            raise ValueError("All trend-quality lookbacks must be at least 2.")
        if top_n < 1:
            raise ValueError("top_n must be at least 1.")
        if min_selected < 1:
            raise ValueError("min_selected must be at least 1.")
        weights = [
            momentum_weight,
            risk_adjusted_weight,
            consistency_weight,
            drawdown_weight,
            low_volatility_weight,
        ]
        if any(Decimal(item) < Decimal("0") for item in weights):
            raise ValueError("Trend-quality weights must be non-negative.")
        if sum((Decimal(item) for item in weights), Decimal("0")) <= Decimal("0"):
            raise ValueError("At least one trend-quality weight must be positive.")

        self.short_momentum_bars = short_momentum_bars
        self.medium_momentum_bars = medium_momentum_bars
        self.long_momentum_bars = long_momentum_bars
        self.volatility_bars = volatility_bars
        self.consistency_bars = consistency_bars
        self.drawdown_lookback_bars = drawdown_lookback_bars
        self.momentum_weight = Decimal(momentum_weight)
        self.risk_adjusted_weight = Decimal(risk_adjusted_weight)
        self.consistency_weight = Decimal(consistency_weight)
        self.drawdown_weight = Decimal(drawdown_weight)
        self.low_volatility_weight = Decimal(low_volatility_weight)
        self.top_n = top_n
        self.min_selected = min_selected
        self.require_positive_long_momentum = require_positive_long_momentum
        self.min_long_momentum = Decimal(min_long_momentum)
        self.fallback_to_top_ranked = fallback_to_top_ranked
        self.reallocate_selected = reallocate_selected
        self.lookback_bars = max(lookbacks)
        self.threshold = self.min_long_momentum
        mode = "reallocate" if reallocate_selected else "cash"
        momentum_gate = "pos" if require_positive_long_momentum else "rank"
        self.name = (
            f"trend-quality-filter-top{top_n}-{short_momentum_bars}-{medium_momentum_bars}-"
            f"{long_momentum_bars}d-{momentum_gate}-{mode}"
        )

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        target_list = list(targets)
        if len(target_list) < 2:
            return target_list

        scores = self._selection_scores(target_list, context)
        if scores is None:
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Trend-quality filter was neutral because not enough "
                            "price history was available."
                        )
                    }
                )
                for target in target_list
            ]

        ranked_symbols = sorted(scores, key=lambda symbol: (-scores[symbol].total, symbol))
        eligible_symbols = [
            symbol
            for symbol in ranked_symbols
            if (
                not self.require_positive_long_momentum
                or scores[symbol].raw_metrics.get("longMomentum", Decimal("-1")) > self.min_long_momentum
            )
        ]
        if len(eligible_symbols) >= self.min_selected:
            selected = set(eligible_symbols[: self.top_n])
            gate_reason = "positive-momentum gate"
        elif self.fallback_to_top_ranked and ranked_symbols:
            selected = set(ranked_symbols[: min(self.min_selected, len(ranked_symbols))])
            gate_reason = "fallback top-ranked gate"
        else:
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Trend-quality filter was neutral because only "
                            f"{len(eligible_symbols)} assets passed the momentum gate; minimum is {self.min_selected}."
                        )
                    }
                )
                for target in target_list
            ]

        rank_by_symbol = {symbol: index + 1 for index, symbol in enumerate(ranked_symbols)}
        original_weight = sum((target.target_weight for target in target_list), Decimal("0"))
        selected_weight = sum((target.target_weight for target in target_list if target.symbol in selected), Decimal("0"))
        scale = original_weight / selected_weight if self.reallocate_selected and selected_weight > Decimal("0") else Decimal("1")

        adjusted: list[AllocationTarget] = []
        for target in target_list:
            score = scores.get(target.symbol)
            if target.symbol in selected and score is not None:
                adjusted.append(
                    target.model_copy(
                        update={
                            "target_weight": target.target_weight * scale,
                            "rationale": (
                                f"{target.rationale} Trend-quality filter selected {target.symbol} via {gate_reason}; "
                                f"rank {rank_by_symbol[target.symbol]}/{len(ranked_symbols)}, score={score.total:.2f}, "
                                f"long={_fmt_decimal_pct(score.raw_metrics.get('longMomentum'))}, "
                                f"vol={_fmt_decimal(score.raw_metrics.get('volatility'))}, "
                                f"{_component_summary(score.components)}."
                            ),
                        }
                    )
                )
                continue

            rank_text = str(rank_by_symbol[target.symbol]) if target.symbol in rank_by_symbol else "not ranked"
            score_text = "n/a" if score is None else f"{score.total:.2f}"
            adjusted.append(
                target.model_copy(
                    update={
                        "target_weight": Decimal("0"),
                        "rationale": (
                            f"{target.rationale} Trend-quality filter removed {target.symbol}; "
                            f"rank={rank_text}, score={score_text}."
                        ),
                    }
                )
            )
        return adjusted

    def _selection_scores(
        self,
        targets: Sequence[AllocationTarget],
        context: SignalContext,
    ) -> dict[str, AssetPoolSelectionScore] | None:
        symbols = [target.symbol for target in targets]
        short_momentum = {symbol: _momentum(symbol, context, self.short_momentum_bars) for symbol in symbols}
        medium_momentum = {symbol: _momentum(symbol, context, self.medium_momentum_bars) for symbol in symbols}
        long_momentum = {symbol: _momentum(symbol, context, self.long_momentum_bars) for symbol in symbols}
        volatility = {symbol: _realized_volatility_metric(symbol, context, self.volatility_bars) for symbol in symbols}
        consistency = {symbol: _positive_return_share(symbol, context, self.consistency_bars) for symbol in symbols}
        drawdown = {symbol: _drawdown_from_high(symbol, context, self.drawdown_lookback_bars) for symbol in symbols}
        medium_risk_adjusted = {
            symbol: _safe_divide(medium_momentum[symbol], volatility[symbol]) for symbol in symbols
        }
        long_risk_adjusted = {
            symbol: _safe_divide(long_momentum[symbol], volatility[symbol]) for symbol in symbols
        }
        low_volatility = {symbol: _negated(volatility[symbol]) for symbol in symbols}

        category_values: dict[str, dict[str, Decimal]] = {}
        _add_category(
            category_values,
            "momentum",
            [
                (Decimal("0.20"), _rank_metric(short_momentum)),
                (Decimal("0.35"), _rank_metric(medium_momentum)),
                (Decimal("0.45"), _rank_metric(long_momentum)),
            ],
        )
        _add_category(
            category_values,
            "risk-adjusted",
            [
                (Decimal("0.45"), _rank_metric(medium_risk_adjusted)),
                (Decimal("0.55"), _rank_metric(long_risk_adjusted)),
            ],
        )
        _add_category(category_values, "consistency", [(Decimal("1"), _rank_metric(consistency))])
        _add_category(category_values, "drawdown", [(Decimal("1"), _rank_metric(drawdown))])
        _add_category(category_values, "low-volatility", [(Decimal("1"), _rank_metric(low_volatility))])

        category_weights = {
            "momentum": self.momentum_weight,
            "risk-adjusted": self.risk_adjusted_weight,
            "consistency": self.consistency_weight,
            "drawdown": self.drawdown_weight,
            "low-volatility": self.low_volatility_weight,
        }
        scores: dict[str, AssetPoolSelectionScore] = {}
        for symbol in symbols:
            weighted_score = Decimal("0")
            weight_sum = Decimal("0")
            components: dict[str, Decimal] = {}
            for category, weight in category_weights.items():
                if weight <= Decimal("0"):
                    continue
                value = category_values.get(category, {}).get(symbol)
                if value is None:
                    continue
                clipped = _clip(value, Decimal("-1"), Decimal("1"))
                components[category] = clipped
                weighted_score += weight * clipped
                weight_sum += weight
            if weight_sum <= Decimal("0"):
                continue
            raw_metrics = {
                key: value
                for key, value in {
                    "shortMomentum": short_momentum.get(symbol),
                    "mediumMomentum": medium_momentum.get(symbol),
                    "longMomentum": long_momentum.get(symbol),
                    "volatility": volatility.get(symbol),
                    "consistency": consistency.get(symbol),
                    "drawdown": drawdown.get(symbol),
                }.items()
                if value is not None
            }
            scores[symbol] = AssetPoolSelectionScore(
                total=_clip(weighted_score / weight_sum, Decimal("-1"), Decimal("1")),
                components=components,
                raw_metrics=raw_metrics,
            )
        return scores if len(scores) >= self.min_selected else None


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
        tilt_suffix = _relative_tilt_suffix(self.calm_tilt, self.risk_tilt)
        self.name = f"relative-momentum-{medium_lookback_bars}-{long_lookback_bars}d-regime{tilt_suffix}"

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


class BasketRiskControlOverlay:
    def __init__(
        self,
        *,
        short_momentum_bars: int = 63,
        long_momentum_bars: int = 252,
        moving_average_bars: int = 252,
        drawdown_lookback_bars: int = 252,
        fast_volatility_bars: int = 21,
        slow_volatility_bars: int = 252,
        weak_breadth_threshold: Decimal = Decimal("0.40"),
        healthy_breadth_threshold: Decimal = Decimal("0.55"),
        short_momentum_threshold: Decimal = Decimal("-0.02"),
        long_momentum_threshold: Decimal = Decimal("0"),
        drawdown_trigger: Decimal = Decimal("-0.08"),
        severe_drawdown_trigger: Decimal = Decimal("-0.14"),
        volatility_ratio_trigger: Decimal = Decimal("1.35"),
        severe_volatility_ratio_trigger: Decimal = Decimal("1.70"),
        neutral_scale: Decimal = Decimal("0.85"),
        defensive_scale: Decimal = Decimal("0.60"),
        severe_scale: Decimal = Decimal("0.35"),
    ) -> None:
        lookbacks = [
            short_momentum_bars,
            long_momentum_bars,
            moving_average_bars,
            drawdown_lookback_bars,
            fast_volatility_bars,
            slow_volatility_bars,
        ]
        if any(item < 2 for item in lookbacks):
            raise ValueError("All basket risk-control lookbacks must be at least 2.")
        for value in [weak_breadth_threshold, healthy_breadth_threshold, neutral_scale, defensive_scale, severe_scale]:
            decimal_value = Decimal(value)
            if decimal_value < Decimal("0") or decimal_value > Decimal("1"):
                raise ValueError("Breadth thresholds and basket risk-control scales must be between 0 and 1.")
        if Decimal(weak_breadth_threshold) > Decimal(healthy_breadth_threshold):
            raise ValueError("weak_breadth_threshold cannot exceed healthy_breadth_threshold.")

        self.short_momentum_bars = short_momentum_bars
        self.long_momentum_bars = long_momentum_bars
        self.moving_average_bars = moving_average_bars
        self.drawdown_lookback_bars = drawdown_lookback_bars
        self.fast_volatility_bars = fast_volatility_bars
        self.slow_volatility_bars = slow_volatility_bars
        self.weak_breadth_threshold = Decimal(weak_breadth_threshold)
        self.healthy_breadth_threshold = Decimal(healthy_breadth_threshold)
        self.short_momentum_threshold = Decimal(short_momentum_threshold)
        self.long_momentum_threshold = Decimal(long_momentum_threshold)
        self.drawdown_trigger = Decimal(drawdown_trigger)
        self.severe_drawdown_trigger = Decimal(severe_drawdown_trigger)
        self.volatility_ratio_trigger = Decimal(volatility_ratio_trigger)
        self.severe_volatility_ratio_trigger = Decimal(severe_volatility_ratio_trigger)
        self.neutral_scale = Decimal(neutral_scale)
        self.defensive_scale = Decimal(defensive_scale)
        self.severe_scale = Decimal(severe_scale)
        self.lookback_bars = max(lookbacks)
        self.threshold = self.long_momentum_threshold
        self.name = (
            f"basket-risk-control-{short_momentum_bars}-{long_momentum_bars}d-"
            f"dd-{_threshold_label(self.drawdown_trigger)}-scale-{_threshold_label(self.defensive_scale)}"
        )

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        target_list = list(targets)
        active_targets = [target for target in target_list if target.target_weight > Decimal("0")]
        if not active_targets:
            return target_list

        state = self._state(active_targets, context)
        if not _basket_state_ready(state):
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Basket risk control was neutral because not enough "
                            "basket history was available."
                        )
                    }
                )
                for target in target_list
            ]

        scale, label = self._scale(state)
        state_summary = self._state_summary(state)
        if scale >= Decimal("1"):
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Basket risk control kept full exposure; {state_summary}."
                        )
                    }
                )
                if target.target_weight > Decimal("0")
                else target
                for target in target_list
            ]

        return [
            target.model_copy(
                update={
                    "target_weight": target.target_weight * scale,
                    "rationale": (
                        f"{target.rationale} Basket risk control used {label} exposure at {scale:.0%}; "
                        f"residual stays in cash; {state_summary}."
                    ),
                }
            )
            if target.target_weight > Decimal("0")
            else target
            for target in target_list
        ]

    def _state(
        self,
        targets: Sequence[AllocationTarget],
        context: SignalContext,
    ) -> dict[str, Decimal | None]:
        weights = {target.symbol: target.target_weight for target in targets}
        symbols = list(weights)
        short_momentum = {symbol: _momentum(symbol, context, self.short_momentum_bars) for symbol in symbols}
        long_momentum = {symbol: _momentum(symbol, context, self.long_momentum_bars) for symbol in symbols}
        moving_average_deviation = {
            symbol: _moving_average_deviation(symbol, context, self.moving_average_bars)
            for symbol in symbols
        }
        drawdowns = {
            symbol: _drawdown_from_high(symbol, context, self.drawdown_lookback_bars)
            for symbol in symbols
        }
        volatility_ratios = {
            symbol: _volatility_ratio(symbol, context, self.fast_volatility_bars, self.slow_volatility_bars)
            for symbol in symbols
        }
        return {
            "shortMomentum": _weighted_average_metric(short_momentum, weights),
            "longMomentum": _weighted_average_metric(long_momentum, weights),
            "longBreadth": _breadth_above(long_momentum, self.long_momentum_threshold),
            "movingAverageBreadth": _breadth_above(moving_average_deviation, Decimal("0")),
            "drawdown": _weighted_average_metric(drawdowns, weights),
            "volatilityRatio": _weighted_average_metric(volatility_ratios, weights),
        }

    def _scale(self, state: Mapping[str, Decimal | None]) -> tuple[Decimal, str]:
        severe = (
            (
                _lte(state["drawdown"], self.severe_drawdown_trigger)
                and _gte(state["volatilityRatio"], self.volatility_ratio_trigger)
            )
            or (
                _lte(state["longMomentum"], Decimal("-0.08"))
                and _lte(state["longBreadth"], self.weak_breadth_threshold)
            )
            or _gte(state["volatilityRatio"], self.severe_volatility_ratio_trigger)
        )
        if severe:
            return self.severe_scale, "severe-defensive"

        defensive = (
            _lte(state["longBreadth"], self.weak_breadth_threshold)
            or _lte(state["movingAverageBreadth"], self.weak_breadth_threshold)
            or (
                _lte(state["longMomentum"], self.long_momentum_threshold)
                and _lte(state["shortMomentum"], self.short_momentum_threshold)
            )
            or _lte(state["drawdown"], self.drawdown_trigger)
            or _gte(state["volatilityRatio"], self.volatility_ratio_trigger)
        )
        if defensive:
            return self.defensive_scale, "defensive"

        neutral = (
            _lt(state["longBreadth"], self.healthy_breadth_threshold)
            or _lt(state["movingAverageBreadth"], self.healthy_breadth_threshold)
            or _lte(state["shortMomentum"], self.short_momentum_threshold)
        )
        if neutral:
            return self.neutral_scale, "neutral"

        return Decimal("1"), "full"

    def _state_summary(self, state: Mapping[str, Decimal | None]) -> str:
        return (
            f"short={_fmt_decimal_pct(state['shortMomentum'])}, long={_fmt_decimal_pct(state['longMomentum'])}, "
            f"long-breadth={_fmt_decimal_pct(state['longBreadth'])}, "
            f"ma-breadth={_fmt_decimal_pct(state['movingAverageBreadth'])}, "
            f"drawdown={_fmt_decimal_pct(state['drawdown'])}, "
            f"vol-ratio={_fmt_decimal(state['volatilityRatio'])}"
        )


class CountryCompositeFactorOverlay:
    def __init__(
        self,
        *,
        short_momentum_bars: int = 63,
        medium_momentum_bars: int = 126,
        long_momentum_bars: int = 252,
        reversal_bars: int = 21,
        mean_reversion_bars: int = 63,
        volume_bars: int = 21,
        slow_volume_bars: int = 126,
        trend_weight: Decimal = Decimal("0.40"),
        volume_weight: Decimal = Decimal("0.15"),
        mean_reversion_weight: Decimal = Decimal("0.20"),
        valuation_weight: Decimal = Decimal("0.15"),
        macro_weight: Decimal = Decimal("0.10"),
        tilt: Decimal = Decimal("0.12"),
        max_active_weight: Decimal = Decimal("0.06"),
        valuation_scores: Mapping[str, Decimal | str | int | float] | None = None,
        macro_scores: Mapping[str, Decimal | str | int | float] | None = None,
    ) -> None:
        lookbacks = [
            short_momentum_bars,
            medium_momentum_bars,
            long_momentum_bars,
            reversal_bars,
            mean_reversion_bars,
            volume_bars,
            slow_volume_bars,
        ]
        if any(item < 2 for item in lookbacks):
            raise ValueError("All country factor lookbacks must be at least 2.")
        weights = [trend_weight, volume_weight, mean_reversion_weight, valuation_weight, macro_weight]
        if any(Decimal(item) < Decimal("0") for item in weights):
            raise ValueError("Country factor weights must be non-negative.")
        if Decimal(tilt) < Decimal("0"):
            raise ValueError("tilt must be non-negative.")
        if Decimal(max_active_weight) < Decimal("0"):
            raise ValueError("max_active_weight must be non-negative.")

        self.short_momentum_bars = short_momentum_bars
        self.medium_momentum_bars = medium_momentum_bars
        self.long_momentum_bars = long_momentum_bars
        self.reversal_bars = reversal_bars
        self.mean_reversion_bars = mean_reversion_bars
        self.volume_bars = volume_bars
        self.slow_volume_bars = slow_volume_bars
        self.trend_weight = Decimal(trend_weight)
        self.volume_weight = Decimal(volume_weight)
        self.mean_reversion_weight = Decimal(mean_reversion_weight)
        self.valuation_weight = Decimal(valuation_weight)
        self.macro_weight = Decimal(macro_weight)
        self.tilt = Decimal(tilt)
        self.max_active_weight = Decimal(max_active_weight)
        self.valuation_scores = _score_map(valuation_scores)
        self.macro_scores = _score_map(macro_scores)
        self.lookback_bars = max(lookbacks)
        self.threshold = Decimal("0")
        self.name = (
            f"country-factor-{short_momentum_bars}-{medium_momentum_bars}-{long_momentum_bars}d-"
            f"tilt-{_threshold_label(self.tilt)}"
        )

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        target_list = list(targets)
        if len(target_list) < 2:
            return list(target_list)

        factor_scores = self._factor_scores(target_list, context)
        if factor_scores is None:
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Country factor overlay was neutral because not enough "
                            "price/volume history was available."
                        )
                    }
                )
                for target in target_list
            ]

        adjusted_weights: dict[str, Decimal] = {}
        for target in target_list:
            score = factor_scores[target.symbol].total
            proposed_weight = target.target_weight * (Decimal("1") + self.tilt * score)
            delta = proposed_weight - target.target_weight
            if delta > self.max_active_weight:
                proposed_weight = target.target_weight + self.max_active_weight
            elif delta < -self.max_active_weight:
                proposed_weight = max(Decimal("0"), target.target_weight - self.max_active_weight)
            adjusted_weights[target.symbol] = max(Decimal("0"), proposed_weight)

        original_weight = sum((target.target_weight for target in target_list), Decimal("0"))
        adjusted_weight = sum(adjusted_weights.values(), Decimal("0"))
        if adjusted_weight > Decimal("0") and original_weight > Decimal("0"):
            scale = original_weight / adjusted_weight
            adjusted_weights = {symbol: weight * scale for symbol, weight in adjusted_weights.items()}

        return [
            target.model_copy(
                update={
                    "target_weight": adjusted_weights[target.symbol],
                    "rationale": (
                        f"{target.rationale} Country factor overlay applied a {self.tilt:.0%} tilt; "
                        f"score={factor_scores[target.symbol].total:.2f}, "
                        f"{_component_summary(factor_scores[target.symbol].components)}."
                    ),
                }
            )
            for target in target_list
        ]

    def _factor_scores(
        self,
        targets: Sequence[AllocationTarget],
        context: SignalContext,
    ) -> dict[str, CompositeFactorScore] | None:
        symbols = [target.symbol for target in targets]
        category_values: dict[str, dict[str, Decimal]] = {}

        _add_category(
            category_values,
            "trend",
            [
                (
                    Decimal("0.25"),
                    _rank_metric({symbol: _momentum(symbol, context, self.short_momentum_bars) for symbol in symbols}),
                ),
                (
                    Decimal("0.35"),
                    _rank_metric({symbol: _momentum(symbol, context, self.medium_momentum_bars) for symbol in symbols}),
                ),
                (
                    Decimal("0.40"),
                    _rank_metric({symbol: _momentum(symbol, context, self.long_momentum_bars) for symbol in symbols}),
                ),
            ],
        )
        _add_category(
            category_values,
            "volume",
            [
                (
                    Decimal("0.70"),
                    _rank_metric({symbol: _up_volume_share(symbol, context, self.volume_bars) for symbol in symbols}),
                ),
                (
                    Decimal("0.30"),
                    _rank_metric({symbol: _signed_volume_pressure(symbol, context, self.volume_bars, self.slow_volume_bars) for symbol in symbols}),
                ),
            ],
        )
        _add_category(
            category_values,
            "mean-reversion",
            [
                (
                    Decimal("0.60"),
                    _rank_metric({symbol: _negated(_momentum(symbol, context, self.reversal_bars)) for symbol in symbols}),
                ),
                (
                    Decimal("0.40"),
                    _rank_metric({symbol: _negated(_moving_average_deviation(symbol, context, self.mean_reversion_bars)) for symbol in symbols}),
                ),
            ],
        )
        if self.valuation_scores:
            category_values["valuation"] = {
                symbol: self.valuation_scores.get(symbol, Decimal("0")) for symbol in symbols
            }
        if self.macro_scores:
            category_values["macro"] = {symbol: self.macro_scores.get(symbol, Decimal("0")) for symbol in symbols}

        category_weights = {
            "trend": self.trend_weight,
            "volume": self.volume_weight,
            "mean-reversion": self.mean_reversion_weight,
            "valuation": self.valuation_weight,
            "macro": self.macro_weight,
        }
        if not any(category_values.get(category) for category, weight in category_weights.items() if weight > Decimal("0")):
            return None

        scores: dict[str, CompositeFactorScore] = {}
        for symbol in symbols:
            weighted_score = Decimal("0")
            weight_sum = Decimal("0")
            components: dict[str, Decimal] = {}
            for category, weight in category_weights.items():
                if weight <= Decimal("0"):
                    continue
                value = category_values.get(category, {}).get(symbol)
                if value is None:
                    continue
                clipped = _clip(value, Decimal("-1"), Decimal("1"))
                components[category] = clipped
                weighted_score += weight * clipped
                weight_sum += weight
            total = weighted_score / weight_sum if weight_sum > Decimal("0") else Decimal("0")
            scores[symbol] = CompositeFactorScore(total=_clip(total, Decimal("-1"), Decimal("1")), components=components)
        return scores


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


def _signed_volume_pressure(
    symbol: str,
    context: SignalContext,
    fast_bars: int,
    slow_bars: int,
) -> Decimal | None:
    fast_average = _average_volume(symbol, context, fast_bars)
    slow_average = _average_volume(symbol, context, slow_bars)
    short_momentum = _momentum(symbol, context, fast_bars)
    if fast_average is None or slow_average is None or slow_average <= Decimal("0") or short_momentum is None:
        return None
    pressure = (fast_average / slow_average) - Decimal("1")
    return pressure if short_momentum >= Decimal("0") else -pressure


def _average_volume(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
    if len(history) < lookback_bars:
        return None
    volumes = [Decimal(bar.volume) for bar in history[-lookback_bars:]]
    return sum(volumes, Decimal("0")) / Decimal(len(volumes))


def _moving_average_deviation(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
    if len(history) < lookback_bars:
        return None
    lookback = history[-lookback_bars:]
    average = sum((bar.close for bar in lookback), Decimal("0")) / Decimal(len(lookback))
    if average <= Decimal("0"):
        return None
    return (history[-1].close / average) - Decimal("1")


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


def _realized_volatility_metric(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
    if len(history) < lookback_bars + 1:
        return None
    volatility = _realized_volatility(history[-(lookback_bars + 1) :])
    return None if volatility is None else Decimal(str(volatility))


def _positive_return_share(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
    if len(history) < lookback_bars + 1:
        return None
    lookback = history[-(lookback_bars + 1) :]
    returns = []
    for index in range(1, len(lookback)):
        previous = Decimal(lookback[index - 1].close)
        current = Decimal(lookback[index].close)
        if previous <= Decimal("0"):
            continue
        returns.append((current / previous) - Decimal("1"))
    if not returns:
        return None
    positive = sum(1 for item in returns if item > Decimal("0"))
    return Decimal(positive) / Decimal(len(returns))


def _drawdown_from_high(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    history = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
    if len(history) < 2:
        return None
    lookback = history[-min(len(history), lookback_bars + 1) :]
    peak = max((bar.close for bar in lookback), default=Decimal("0"))
    if peak <= Decimal("0"):
        return None
    return (lookback[-1].close / peak) - Decimal("1")


def _weighted_average_metric(
    values_by_symbol: Mapping[str, Decimal | None],
    weights_by_symbol: Mapping[str, Decimal],
) -> Decimal | None:
    total = Decimal("0")
    weight_sum = Decimal("0")
    for symbol, value in values_by_symbol.items():
        if value is None:
            continue
        weight = weights_by_symbol.get(symbol, Decimal("0"))
        if weight <= Decimal("0"):
            continue
        total += value * weight
        weight_sum += weight
    if weight_sum <= Decimal("0"):
        return None
    return total / weight_sum


def _breadth_above(values_by_symbol: Mapping[str, Decimal | None], threshold: Decimal) -> Decimal | None:
    present = [value for value in values_by_symbol.values() if value is not None]
    if not present:
        return None
    positive = sum(1 for value in present if value > threshold)
    return Decimal(positive) / Decimal(len(present))


def _basket_state_ready(state: Mapping[str, Decimal | None]) -> bool:
    return any(value is not None for value in state.values())


def _lt(value: Decimal | None, threshold: Decimal) -> bool:
    return value is not None and value < threshold


def _lte(value: Decimal | None, threshold: Decimal) -> bool:
    return value is not None and value <= threshold


def _gte(value: Decimal | None, threshold: Decimal) -> bool:
    return value is not None and value >= threshold


def _rank_scores(scores: dict[str, Decimal]) -> dict[str, Decimal]:
    ranked = sorted(scores, key=lambda symbol: (scores[symbol], symbol))
    if len(ranked) == 1:
        return {ranked[0]: Decimal("0")}
    denominator = Decimal(len(ranked) - 1)
    return {
        symbol: (Decimal(index) / denominator) * Decimal("2") - Decimal("1")
        for index, symbol in enumerate(ranked)
    }


def _rank_metric(values: Mapping[str, Decimal | None]) -> dict[str, Decimal] | None:
    present = {symbol: value for symbol, value in values.items() if value is not None}
    if len(present) < 2:
        return None
    ranked = sorted(present.items(), key=lambda item: (item[1], item[0]))
    if ranked[0][1] == ranked[-1][1]:
        return {symbol: Decimal("0") for symbol in present}

    denominator = Decimal(len(ranked) - 1)
    result: dict[str, Decimal] = {}
    index = 0
    while index < len(ranked):
        value = ranked[index][1]
        end = index
        while end + 1 < len(ranked) and ranked[end + 1][1] == value:
            end += 1
        average_rank = (Decimal(index) + Decimal(end)) / Decimal("2")
        score = (average_rank / denominator) * Decimal("2") - Decimal("1")
        for tied_index in range(index, end + 1):
            result[ranked[tied_index][0]] = score
        index = end + 1
    return result


def _add_category(
    category_values: dict[str, dict[str, Decimal]],
    category: str,
    metrics: Sequence[tuple[Decimal, Mapping[str, Decimal] | None]],
) -> None:
    weighted: dict[str, Decimal] = {}
    weights: dict[str, Decimal] = {}
    for metric_weight, values in metrics:
        if values is None or metric_weight <= Decimal("0"):
            continue
        for symbol, value in values.items():
            weighted[symbol] = weighted.get(symbol, Decimal("0")) + metric_weight * value
            weights[symbol] = weights.get(symbol, Decimal("0")) + metric_weight
    if not weighted:
        return
    category_values[category] = {
        symbol: weighted[symbol] / weights[symbol]
        for symbol in weighted
        if weights[symbol] > Decimal("0")
    }


def _score_map(values: Mapping[str, Decimal | str | int | float] | None) -> dict[str, Decimal]:
    if values is None:
        return {}
    return {
        symbol.upper(): _clip(Decimal(str(value)), Decimal("-1"), Decimal("1"))
        for symbol, value in values.items()
    }


def _negated(value: Decimal | None) -> Decimal | None:
    return None if value is None else -value


def _safe_divide(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator <= Decimal("0"):
        return None
    return numerator / denominator


def _clip(value: Decimal, lower: Decimal, upper: Decimal) -> Decimal:
    return max(lower, min(upper, value))


def _component_summary(components: Mapping[str, Decimal]) -> str:
    if not components:
        return "components=n/a"
    return ", ".join(f"{name}={value:.2f}" for name, value in sorted(components.items()))


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


def _relative_tilt_suffix(calm_tilt: Decimal, risk_tilt: Decimal) -> str:
    default_tilt = Decimal("0.12")
    if calm_tilt == default_tilt and risk_tilt == default_tilt:
        return ""
    if calm_tilt == risk_tilt:
        return f"-tilt-{_threshold_label(calm_tilt)}"
    return f"-tilt-c{_threshold_label(calm_tilt)}-r{_threshold_label(risk_tilt)}"
