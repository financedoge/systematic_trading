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
