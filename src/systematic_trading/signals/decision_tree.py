from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Mapping, Sequence

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals.base import SignalContext
from systematic_trading.signals.library import (
    compute_signal_features,
    max_signal_lookback_bars,
    signal_feature_ids,
)


@dataclass(frozen=True)
class DecisionTreeSample:
    features: Mapping[str, float | None]
    target: float


@dataclass(frozen=True)
class DecisionTreeNode:
    value: float
    samples: int
    mse: float
    feature: str | None = None
    threshold: float | None = None
    left: "DecisionTreeNode | None" = None
    right: "DecisionTreeNode | None" = None

    def predict(self, features: Mapping[str, float | None]) -> float:
        if self.feature is None or self.threshold is None or self.left is None or self.right is None:
            return self.value
        value = features.get(self.feature)
        if value is None or not math.isfinite(value):
            return self.value
        return self.left.predict(features) if value <= self.threshold else self.right.predict(features)

    def to_dict(self) -> dict[str, Any]:
        return {
            "value": self.value,
            "samples": self.samples,
            "mse": self.mse,
            "feature": self.feature,
            "threshold": self.threshold,
            "left": self.left.to_dict() if self.left is not None else None,
            "right": self.right.to_dict() if self.right is not None else None,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DecisionTreeNode":
        left = payload.get("left")
        right = payload.get("right")
        return cls(
            value=float(payload["value"]),
            samples=int(payload["samples"]),
            mse=float(payload["mse"]),
            feature=str(payload["feature"]) if payload.get("feature") is not None else None,
            threshold=float(payload["threshold"]) if payload.get("threshold") is not None else None,
            left=cls.from_dict(left) if left is not None else None,
            right=cls.from_dict(right) if right is not None else None,
        )


@dataclass(frozen=True)
class SimpleDecisionTreeModel:
    feature_names: tuple[str, ...]
    root: DecisionTreeNode
    max_depth: int
    min_samples_leaf: int
    training_summary: Mapping[str, Any]

    def predict(self, features: Mapping[str, float | None]) -> float:
        return self.root.predict(features)

    def to_dict(self) -> dict[str, Any]:
        return {
            "featureNames": list(self.feature_names),
            "maxDepth": self.max_depth,
            "minSamplesLeaf": self.min_samples_leaf,
            "trainingSummary": dict(self.training_summary),
            "root": self.root.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "SimpleDecisionTreeModel":
        return cls(
            feature_names=tuple(str(item) for item in payload["featureNames"]),
            root=DecisionTreeNode.from_dict(payload["root"]),
            max_depth=int(payload["maxDepth"]),
            min_samples_leaf=int(payload["minSamplesLeaf"]),
            training_summary=dict(payload.get("trainingSummary", {})),
        )

    def depth(self) -> int:
        return _node_depth(self.root)


class DecisionTreeSignalOverlay:
    def __init__(
        self,
        *,
        model: SimpleDecisionTreeModel,
        tilt: Decimal = Decimal("0.12"),
        max_active_weight: Decimal = Decimal("0.06"),
        valuation_scores: Mapping[str, Decimal | str | int | float] | None = None,
        macro_scores: Mapping[str, Decimal | str | int | float] | None = None,
    ) -> None:
        if Decimal(tilt) < Decimal("0"):
            raise ValueError("tilt must be non-negative.")
        if Decimal(max_active_weight) < Decimal("0"):
            raise ValueError("max_active_weight must be non-negative.")
        self.model = model
        self.tilt = Decimal(tilt)
        self.max_active_weight = Decimal(max_active_weight)
        self.valuation_scores = _score_map(valuation_scores)
        self.macro_scores = _score_map(macro_scores)
        self.lookback_bars = max_signal_lookback_bars()
        self.threshold = Decimal("0")
        self.name = f"decision-tree-signal-d{model.max_depth}-tilt-{_threshold_label(self.tilt)}"

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        target_list = list(targets)
        if len(target_list) < 2:
            return target_list

        forecasts = {
            target.symbol: self.model.predict(
                compute_signal_features(
                    symbol=target.symbol,
                    context=context,
                    valuation_scores=self.valuation_scores,
                    macro_scores=self.macro_scores,
                )
            )
            for target in target_list
        }
        if not any(math.isfinite(value) for value in forecasts.values()):
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Decision-tree overlay was neutral because no valid "
                            "factor forecasts were available."
                        )
                    }
                )
                for target in target_list
            ]

        rank_scores = _rank_scores(forecasts)
        adjusted_weights: dict[str, Decimal] = {}
        for target in target_list:
            base_weight = target.target_weight
            proposed_weight = base_weight * (Decimal("1") + self.tilt * rank_scores[target.symbol])
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

        return [
            target.model_copy(
                update={
                    "target_weight": adjusted_weights[target.symbol],
                    "rationale": (
                        f"{target.rationale} Decision-tree overlay applied a {self.tilt:.0%} tilt; "
                        f"forecast={forecasts[target.symbol]:.2%}, rank={rank_scores[target.symbol]:.2f}."
                    ),
                }
            )
            for target in target_list
        ]


class TechnicalDecisionTreeAllocatorOverlay:
    def __init__(
        self,
        *,
        model: SimpleDecisionTreeModel,
        top_n: int = 8,
        min_selected: int = 5,
        tree_weight: Decimal = Decimal("0.45"),
        momentum_weight: Decimal = Decimal("0.35"),
        technical_weight: Decimal = Decimal("0.20"),
        allocation_tilt: Decimal = Decimal("0.35"),
        min_long_momentum: Decimal = Decimal("0"),
        require_positive_timeseries: bool = True,
        reallocate_selected: bool = True,
        valuation_scores: Mapping[str, Decimal | str | int | float] | None = None,
        macro_scores: Mapping[str, Decimal | str | int | float] | None = None,
    ) -> None:
        if top_n < 1:
            raise ValueError("top_n must be at least 1.")
        if min_selected < 1:
            raise ValueError("min_selected must be at least 1.")
        weights = [tree_weight, momentum_weight, technical_weight]
        if any(Decimal(weight) < Decimal("0") for weight in weights):
            raise ValueError("Technical tree allocator weights must be non-negative.")
        if sum((Decimal(weight) for weight in weights), Decimal("0")) <= Decimal("0"):
            raise ValueError("At least one technical tree allocator weight must be positive.")
        if Decimal(allocation_tilt) < Decimal("0"):
            raise ValueError("allocation_tilt must be non-negative.")

        self.model = model
        self.top_n = top_n
        self.min_selected = min_selected
        self.tree_weight = Decimal(tree_weight)
        self.momentum_weight = Decimal(momentum_weight)
        self.technical_weight = Decimal(technical_weight)
        self.allocation_tilt = Decimal(allocation_tilt)
        self.min_long_momentum = Decimal(min_long_momentum)
        self.require_positive_timeseries = require_positive_timeseries
        self.reallocate_selected = reallocate_selected
        self.valuation_scores = _score_map(valuation_scores)
        self.macro_scores = _score_map(macro_scores)
        self.lookback_bars = max_signal_lookback_bars()
        self.threshold = self.min_long_momentum
        self.name = f"technical-tree-allocator-top{top_n}-d{model.max_depth}"

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        target_list = list(targets)
        if len(target_list) < 2:
            return target_list

        features_by_symbol = {
            target.symbol: compute_signal_features(
                symbol=target.symbol,
                context=context,
                valuation_scores=self.valuation_scores,
                macro_scores=self.macro_scores,
            )
            for target in target_list
        }
        forecast_values: dict[str, float] = {}
        for symbol, features in features_by_symbol.items():
            forecast = self.model.predict(features)
            if _finite(forecast):
                forecast_values[symbol] = forecast
        momentum_values = {
            symbol: value
            for symbol, features in features_by_symbol.items()
            if _finite(value := _first_feature(features, "relative_momentum_20_60", "mom_63", "mom_126"))
        }
        technical_values = {
            symbol: value
            for symbol, features in features_by_symbol.items()
            if _finite(value := _technical_health(features))
        }
        if not forecast_values and not momentum_values and not technical_values:
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Technical decision-tree allocator was neutral because no valid "
                            "tree, momentum, or technical scores were available."
                        )
                    }
                )
                for target in target_list
            ]

        rank_components = {
            "tree": _rank_scores(forecast_values) if len(forecast_values) >= 2 else {},
            "momentum": _rank_scores(momentum_values) if len(momentum_values) >= 2 else {},
            "technical": _rank_scores(technical_values) if len(technical_values) >= 2 else {},
        }
        composite_scores = self._composite_scores(target_list, rank_components)
        ranked_targets = sorted(
            [target for target in target_list if target.symbol in composite_scores],
            key=lambda target: (-composite_scores[target.symbol], target.symbol),
        )
        if not ranked_targets:
            return target_list

        eligible = [
            target
            for target in ranked_targets
            if not self.require_positive_timeseries or self._passes_timeseries_gate(features_by_symbol[target.symbol])
        ]
        selected = eligible[: self.top_n]
        if len(selected) < self.min_selected:
            selected = ranked_targets[: min(len(ranked_targets), max(self.min_selected, self.top_n))]
        selected = selected[: self.top_n]

        selected_symbols = {target.symbol for target in selected}
        rank_by_symbol = {target.symbol: index + 1 for index, target in enumerate(ranked_targets)}
        adjusted_weights = self._allocated_weights(target_list, selected_symbols, composite_scores)
        return [
            target.model_copy(
                update={
                    "target_weight": adjusted_weights.get(target.symbol, Decimal("0")),
                    "rationale": self._rationale(
                        target=target,
                        selected=target.symbol in selected_symbols,
                        rank=rank_by_symbol.get(target.symbol),
                        total=len(ranked_targets),
                        features=features_by_symbol[target.symbol],
                        composite_score=composite_scores.get(target.symbol),
                        forecast=forecast_values.get(target.symbol),
                        momentum=momentum_values.get(target.symbol),
                        technical=technical_values.get(target.symbol),
                    ),
                }
            )
            for target in target_list
        ]

    def _composite_scores(
        self,
        targets: Sequence[AllocationTarget],
        rank_components: Mapping[str, Mapping[str, Decimal]],
    ) -> dict[str, Decimal]:
        weights = {
            "tree": self.tree_weight,
            "momentum": self.momentum_weight,
            "technical": self.technical_weight,
        }
        scores: dict[str, Decimal] = {}
        for target in targets:
            weighted = Decimal("0")
            weight_sum = Decimal("0")
            for name, weight in weights.items():
                value = rank_components.get(name, {}).get(target.symbol)
                if value is None or weight <= Decimal("0"):
                    continue
                weighted += weight * value
                weight_sum += weight
            if weight_sum > Decimal("0"):
                scores[target.symbol] = weighted / weight_sum
        return scores

    def _passes_timeseries_gate(self, features: Mapping[str, float | None]) -> bool:
        long_momentum = features.get("mom_252")
        above_ma = features.get("above_ma_252")
        if not _finite(long_momentum) or float(long_momentum) <= float(self.min_long_momentum):
            return False
        return _finite(above_ma) and float(above_ma) > 0

    def _allocated_weights(
        self,
        targets: Sequence[AllocationTarget],
        selected_symbols: set[str],
        composite_scores: Mapping[str, Decimal],
    ) -> dict[str, Decimal]:
        original_weight = sum((target.target_weight for target in targets), Decimal("0"))
        if original_weight <= Decimal("0"):
            return {target.symbol: target.target_weight for target in targets}

        raw_weights: dict[str, Decimal] = {}
        for target in targets:
            if target.symbol not in selected_symbols:
                raw_weights[target.symbol] = Decimal("0")
                continue
            multiplier = Decimal("1") + self.allocation_tilt * composite_scores.get(target.symbol, Decimal("0"))
            raw_weights[target.symbol] = target.target_weight * max(Decimal("0.05"), multiplier)

        raw_total = sum(raw_weights.values(), Decimal("0"))
        if raw_total <= Decimal("0"):
            equal = original_weight / Decimal(len(selected_symbols)) if selected_symbols else Decimal("0")
            return {target.symbol: equal if target.symbol in selected_symbols else Decimal("0") for target in targets}
        scale = original_weight / raw_total if self.reallocate_selected else Decimal("1")
        return {symbol: weight * scale for symbol, weight in raw_weights.items()}

    def _rationale(
        self,
        *,
        target: AllocationTarget,
        selected: bool,
        rank: int | None,
        total: int,
        features: Mapping[str, float | None],
        composite_score: Decimal | None,
        forecast: float | None,
        momentum: float | None,
        technical: float | None,
    ) -> str:
        action = "selected" if selected else "removed"
        rank_text = "n/a" if rank is None else f"{rank}/{total}"
        return (
            f"{target.rationale} Technical decision-tree allocator {action} {target.symbol}; "
            f"rank={rank_text}, composite={_fmt_decimal(composite_score)}, forecast={_fmt_float_pct(forecast)}, "
            f"momentum={_fmt_float_pct(momentum)}, technical={_fmt_float(technical)}, "
            f"mom252={_fmt_float_pct(features.get('mom_252'))}, "
            f"macdHist={_fmt_float(features.get('macd_hist_12_26_9'))}, "
            f"bbZ={_fmt_float(features.get('bollinger_z_20'))}."
        )


def train_simple_regression_tree(
    samples: Sequence[DecisionTreeSample],
    *,
    feature_names: Sequence[str] | None = None,
    max_depth: int = 3,
    min_samples_leaf: int = 25,
    min_impurity_decrease: float = 0.000001,
) -> SimpleDecisionTreeModel:
    if max_depth < 1:
        raise ValueError("max_depth must be at least 1.")
    if min_samples_leaf < 1:
        raise ValueError("min_samples_leaf must be at least 1.")
    sample_list = list(samples)
    if len(sample_list) < min_samples_leaf:
        raise ValueError("Not enough training samples for the requested min_samples_leaf.")
    features = tuple(feature_names or signal_feature_ids())
    root = _fit_node(
        sample_list,
        feature_names=features,
        depth=0,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        min_impurity_decrease=min_impurity_decrease,
    )
    return SimpleDecisionTreeModel(
        feature_names=features,
        root=root,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        training_summary={
            "samples": len(sample_list),
            "features": len(features),
            "target": "next_rebalance_forward_return_minus_cross_section_mean",
            "leaves": _leaf_count(root),
            "depth": _node_depth(root),
        },
    )


def build_forward_return_samples(
    *,
    symbols: Sequence[str],
    bars_by_symbol: Mapping[str, Sequence[object]],
    trade_dates: Sequence[date],
    rebalance_dates: Sequence[date],
    split_date: date,
    valuation_scores: Mapping[str, Decimal | str | int | float] | None = None,
    macro_scores: Mapping[str, Decimal | str | int | float] | None = None,
) -> list[DecisionTreeSample]:
    bar_by_symbol_date = {
        symbol: {bar.trade_date: bar for bar in bars}
        for symbol, bars in bars_by_symbol.items()
    }
    samples: list[DecisionTreeSample] = []
    starts = sorted(set(rebalance_dates))
    for index, start in enumerate(starts[:-1]):
        end = starts[index + 1]
        if start >= split_date or end > split_date:
            continue
        returns: dict[str, float] = {}
        for symbol in symbols:
            start_bar = bar_by_symbol_date.get(symbol, {}).get(start)
            end_bar = bar_by_symbol_date.get(symbol, {}).get(end)
            if start_bar is None or end_bar is None or start_bar.close <= Decimal("0"):
                continue
            returns[symbol] = float((end_bar.close / start_bar.close) - Decimal("1"))
        if len(returns) < 2:
            continue
        mean_return = sum(returns.values()) / len(returns)
        context = SignalContext(
            as_of=start,
            instruments={},
            bars_by_symbol=bars_by_symbol,
            trade_dates=trade_dates,
        )
        for symbol, forward_return in returns.items():
            features = compute_signal_features(
                symbol=symbol,
                context=context,
                valuation_scores=valuation_scores,
                macro_scores=macro_scores,
            )
            if any(value is not None and math.isfinite(value) for value in features.values()):
                samples.append(DecisionTreeSample(features=features, target=forward_return - mean_return))
    return samples


def train_decision_tree_overlay(
    *,
    symbols: Sequence[str],
    bars_by_symbol: Mapping[str, Sequence[object]],
    trade_dates: Sequence[date],
    rebalance_dates: Sequence[date],
    split_date: date,
    max_depth: int,
    min_samples_leaf: int,
    tilt: Decimal,
    max_active_weight: Decimal,
    valuation_scores: Mapping[str, Decimal | str | int | float] | None = None,
    macro_scores: Mapping[str, Decimal | str | int | float] | None = None,
) -> DecisionTreeSignalOverlay:
    samples = build_forward_return_samples(
        symbols=symbols,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        rebalance_dates=rebalance_dates,
        split_date=split_date,
        valuation_scores=valuation_scores,
        macro_scores=macro_scores,
    )
    model = train_simple_regression_tree(
        samples,
        feature_names=signal_feature_ids(),
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
    )
    return DecisionTreeSignalOverlay(
        model=model,
        tilt=tilt,
        max_active_weight=max_active_weight,
        valuation_scores=valuation_scores,
        macro_scores=macro_scores,
    )


def train_technical_tree_allocator_overlay(
    *,
    symbols: Sequence[str],
    bars_by_symbol: Mapping[str, Sequence[object]],
    trade_dates: Sequence[date],
    rebalance_dates: Sequence[date],
    split_date: date,
    max_depth: int,
    min_samples_leaf: int,
    top_n: int,
    min_selected: int,
    tree_weight: Decimal = Decimal("0.45"),
    momentum_weight: Decimal = Decimal("0.35"),
    technical_weight: Decimal = Decimal("0.20"),
    allocation_tilt: Decimal = Decimal("0.35"),
    min_long_momentum: Decimal = Decimal("0"),
    require_positive_timeseries: bool = True,
    reallocate_selected: bool = True,
    valuation_scores: Mapping[str, Decimal | str | int | float] | None = None,
    macro_scores: Mapping[str, Decimal | str | int | float] | None = None,
) -> TechnicalDecisionTreeAllocatorOverlay:
    samples = build_forward_return_samples(
        symbols=symbols,
        bars_by_symbol=bars_by_symbol,
        trade_dates=trade_dates,
        rebalance_dates=rebalance_dates,
        split_date=split_date,
        valuation_scores=valuation_scores,
        macro_scores=macro_scores,
    )
    model = train_simple_regression_tree(
        samples,
        feature_names=signal_feature_ids(),
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
    )
    return TechnicalDecisionTreeAllocatorOverlay(
        model=model,
        top_n=top_n,
        min_selected=min_selected,
        tree_weight=tree_weight,
        momentum_weight=momentum_weight,
        technical_weight=technical_weight,
        allocation_tilt=allocation_tilt,
        min_long_momentum=min_long_momentum,
        require_positive_timeseries=require_positive_timeseries,
        reallocate_selected=reallocate_selected,
        valuation_scores=valuation_scores,
        macro_scores=macro_scores,
    )


def _fit_node(
    samples: Sequence[DecisionTreeSample],
    *,
    feature_names: Sequence[str],
    depth: int,
    max_depth: int,
    min_samples_leaf: int,
    min_impurity_decrease: float,
) -> DecisionTreeNode:
    targets = [sample.target for sample in samples]
    value = sum(targets) / len(targets)
    mse = _mse(targets)
    if depth >= max_depth or len(samples) < min_samples_leaf * 2:
        return DecisionTreeNode(value=value, samples=len(samples), mse=mse)

    split = _best_split(samples, feature_names, min_samples_leaf)
    if split is None or mse - split["mse"] < min_impurity_decrease:
        return DecisionTreeNode(value=value, samples=len(samples), mse=mse)

    left = _fit_node(
        split["left"],
        feature_names=feature_names,
        depth=depth + 1,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        min_impurity_decrease=min_impurity_decrease,
    )
    right = _fit_node(
        split["right"],
        feature_names=feature_names,
        depth=depth + 1,
        max_depth=max_depth,
        min_samples_leaf=min_samples_leaf,
        min_impurity_decrease=min_impurity_decrease,
    )
    return DecisionTreeNode(
        value=value,
        samples=len(samples),
        mse=mse,
        feature=split["feature"],
        threshold=split["threshold"],
        left=left,
        right=right,
    )


def _best_split(
    samples: Sequence[DecisionTreeSample],
    feature_names: Sequence[str],
    min_samples_leaf: int,
) -> dict[str, Any] | None:
    best: dict[str, Any] | None = None
    for feature in feature_names:
        values = sorted(
            {
                float(value)
                for sample in samples
                if (value := sample.features.get(feature)) is not None and math.isfinite(value)
            }
        )
        if len(values) < 2:
            continue
        thresholds = _candidate_thresholds(values)
        for threshold in thresholds:
            left = [sample for sample in samples if _feature_value(sample, feature) <= threshold]
            right = [sample for sample in samples if _feature_value(sample, feature) > threshold]
            if len(left) < min_samples_leaf or len(right) < min_samples_leaf:
                continue
            split_mse = _weighted_mse(left, right)
            if best is None or split_mse < best["mse"]:
                best = {
                    "feature": feature,
                    "threshold": threshold,
                    "mse": split_mse,
                    "left": left,
                    "right": right,
                }
    return best


def _candidate_thresholds(values: Sequence[float], max_candidates: int = 24) -> list[float]:
    unique = sorted(set(values))
    if len(unique) <= max_candidates:
        return [(unique[index - 1] + unique[index]) / 2 for index in range(1, len(unique))]
    step = max(1, len(unique) // max_candidates)
    indexes = list(range(step, len(unique), step))
    return [(unique[index - 1] + unique[index]) / 2 for index in indexes if index < len(unique)]


def _feature_value(sample: DecisionTreeSample, feature: str) -> float:
    value = sample.features.get(feature)
    return float("-inf") if value is None or not math.isfinite(value) else float(value)


def _weighted_mse(left: Sequence[DecisionTreeSample], right: Sequence[DecisionTreeSample]) -> float:
    total = len(left) + len(right)
    return (len(left) / total) * _mse([sample.target for sample in left]) + (
        len(right) / total
    ) * _mse([sample.target for sample in right])


def _mse(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    return sum((value - mean) ** 2 for value in values) / len(values)


def _first_feature(features: Mapping[str, float | None], *names: str) -> float | None:
    for name in names:
        value = features.get(name)
        if _finite(value):
            return float(value)
    return None


def _technical_health(features: Mapping[str, float | None]) -> float | None:
    components: list[tuple[float, float]] = []
    if _finite(features.get("macd_hist_12_26_9")):
        components.append((0.35, _clip_float(float(features["macd_hist_12_26_9"]) * 50, -1.0, 1.0)))
    if _finite(features.get("macd_line_12_26")):
        components.append((0.20, _clip_float(float(features["macd_line_12_26"]) * 25, -1.0, 1.0)))
    if _finite(features.get("bollinger_z_20")):
        components.append((0.20, _clip_float(float(features["bollinger_z_20"]) / 3.0, -1.0, 1.0)))
    if _finite(features.get("rsi_14")):
        components.append((0.15, _clip_float(float(features["rsi_14"]), -1.0, 1.0)))
    if _finite(features.get("above_ma_63")):
        components.append((0.10, 1.0 if float(features["above_ma_63"]) > 0 else -1.0))
    if not components:
        return None
    weight_sum = sum(weight for weight, _value in components)
    return sum(weight * value for weight, value in components) / weight_sum


def _finite(value: object) -> bool:
    return isinstance(value, int | float) and math.isfinite(float(value))


def _clip_float(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _fmt_decimal(value: Decimal | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def _fmt_float(value: float | None) -> str:
    return "n/a" if not _finite(value) else f"{float(value):.2f}"


def _fmt_float_pct(value: float | None) -> str:
    return "n/a" if not _finite(value) else f"{float(value):.2%}"


def _rank_scores(scores: Mapping[str, float]) -> dict[str, Decimal]:
    ranked = sorted(scores, key=lambda symbol: (scores[symbol], symbol))
    if len(ranked) == 1:
        return {ranked[0]: Decimal("0")}
    denominator = Decimal(len(ranked) - 1)
    result: dict[str, Decimal] = {}
    index = 0
    while index < len(ranked):
        value = scores[ranked[index]]
        end = index
        while end + 1 < len(ranked) and scores[ranked[end + 1]] == value:
            end += 1
        average_rank = (Decimal(index) + Decimal(end)) / Decimal("2")
        score = (average_rank / denominator) * Decimal("2") - Decimal("1")
        for tied_index in range(index, end + 1):
            result[ranked[tied_index]] = score
        index = end + 1
    return result


def _leaf_count(node: DecisionTreeNode) -> int:
    if node.left is None and node.right is None:
        return 1
    return (0 if node.left is None else _leaf_count(node.left)) + (0 if node.right is None else _leaf_count(node.right))


def _node_depth(node: DecisionTreeNode) -> int:
    if node.left is None and node.right is None:
        return 0
    return 1 + max(0 if node.left is None else _node_depth(node.left), 0 if node.right is None else _node_depth(node.right))


def _score_map(values: Mapping[str, Decimal | str | int | float] | None) -> dict[str, Decimal]:
    if values is None:
        return {}
    return {
        symbol.upper(): max(Decimal("-1"), min(Decimal("1"), Decimal(str(value))))
        for symbol, value in values.items()
    }


def _threshold_label(value: Decimal) -> str:
    return str(value.normalize()).replace("-", "m").replace(".", "p")
