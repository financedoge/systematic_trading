from __future__ import annotations

from dataclasses import dataclass
import math
from decimal import Decimal
from typing import Mapping, Sequence

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals.base import SignalContext
from systematic_trading.signals.trend import (
    _add_category,
    _clip,
    _component_summary,
    _fmt_decimal_pct,
    _momentum,
    _rank_metric,
    _signed_volume_pressure,
    _up_volume_share,
)


@dataclass(frozen=True)
class BalancedSelectionScore:
    total: Decimal
    components: Mapping[str, Decimal]
    long_momentum: Decimal | None


class BalancedAssetGroupOverlay:
    def __init__(
        self,
        *,
        sleeve_by_symbol: Mapping[str, str],
        sleeve_budgets: Mapping[str, Decimal | str | int | float],
        top_n_per_sleeve: int = 1,
        min_selected_per_sleeve: int = 1,
        short_momentum_bars: int = 21,
        medium_momentum_bars: int = 63,
        long_momentum_bars: int = 252,
        volume_bars: int = 21,
        slow_volume_bars: int = 126,
        trend_weight: Decimal = Decimal("0.80"),
        volume_weight: Decimal = Decimal("0.20"),
        require_positive_long_momentum: bool = True,
        min_long_momentum: Decimal = Decimal("0"),
        fallback_to_top_ranked: bool = True,
        name: str | None = None,
    ) -> None:
        lookbacks = [
            short_momentum_bars,
            medium_momentum_bars,
            long_momentum_bars,
            volume_bars,
            slow_volume_bars,
        ]
        if any(item < 2 for item in lookbacks):
            raise ValueError("All balanced overlay lookbacks must be at least 2.")
        if top_n_per_sleeve < 1:
            raise ValueError("top_n_per_sleeve must be at least 1.")
        if min_selected_per_sleeve < 1:
            raise ValueError("min_selected_per_sleeve must be at least 1.")
        if Decimal(trend_weight) < Decimal("0") or Decimal(volume_weight) < Decimal("0"):
            raise ValueError("Balanced overlay weights must be non-negative.")
        if Decimal(trend_weight) + Decimal(volume_weight) <= Decimal("0"):
            raise ValueError("At least one balanced overlay weight must be positive.")

        self.sleeve_by_symbol = {symbol.upper(): sleeve for symbol, sleeve in sleeve_by_symbol.items()}
        self.sleeve_budgets = {sleeve: Decimal(str(weight)) for sleeve, weight in sleeve_budgets.items()}
        self.top_n_per_sleeve = top_n_per_sleeve
        self.min_selected_per_sleeve = min_selected_per_sleeve
        self.short_momentum_bars = short_momentum_bars
        self.medium_momentum_bars = medium_momentum_bars
        self.long_momentum_bars = long_momentum_bars
        self.volume_bars = volume_bars
        self.slow_volume_bars = slow_volume_bars
        self.trend_weight = Decimal(trend_weight)
        self.volume_weight = Decimal(volume_weight)
        self.require_positive_long_momentum = require_positive_long_momentum
        self.min_long_momentum = Decimal(min_long_momentum)
        self.fallback_to_top_ranked = fallback_to_top_ranked
        self.lookback_bars = max(lookbacks)
        self.threshold = self.min_long_momentum
        self.name = name or (
            f"balanced-group-filter-top{top_n_per_sleeve}-"
            f"{short_momentum_bars}-{medium_momentum_bars}-{long_momentum_bars}d"
        )

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        target_list = list(targets)
        if not target_list:
            return []

        original_weight = sum((target.target_weight for target in target_list), Decimal("0"))
        budget_total = sum(self.sleeve_budgets.values(), Decimal("0"))
        if original_weight <= Decimal("0") or budget_total <= Decimal("0"):
            return target_list

        targets_by_sleeve: dict[str, list[AllocationTarget]] = {}
        for target in target_list:
            sleeve = self.sleeve_by_symbol.get(target.symbol)
            if sleeve is None:
                continue
            targets_by_sleeve.setdefault(sleeve, []).append(target)

        adjusted_weight_by_symbol = {target.symbol: Decimal("0") for target in target_list}
        rationale_by_symbol = {
            target.symbol: f"{target.rationale} Balanced group overlay removed the asset because it is outside configured sleeves."
            for target in target_list
        }

        for sleeve, sleeve_targets in targets_by_sleeve.items():
            sleeve_budget = self.sleeve_budgets.get(sleeve, Decimal("0"))
            if sleeve_budget <= Decimal("0"):
                continue
            sleeve_weight = original_weight * sleeve_budget / budget_total
            selected, scores, reason = self._select_sleeve(sleeve_targets, context)
            if not selected:
                continue
            base_weight = sum((target.target_weight for target in selected), Decimal("0"))
            equal_weight = sleeve_weight / Decimal(len(selected))
            for target in sleeve_targets:
                score = scores.get(target.symbol)
                if target in selected:
                    target_weight = (
                        sleeve_weight * target.target_weight / base_weight
                        if base_weight > Decimal("0")
                        else equal_weight
                    )
                    adjusted_weight_by_symbol[target.symbol] = target_weight
                    rationale_by_symbol[target.symbol] = (
                        f"{target.rationale} Balanced group overlay selected {target.symbol} in {sleeve}; "
                        f"sleeve budget={sleeve_budget:.2%}, score={_fmt_score(score)}, "
                        f"long={_fmt_decimal_pct(score.long_momentum if score else None)}, {reason}."
                    )
                    continue
                rationale_by_symbol[target.symbol] = (
                    f"{target.rationale} Balanced group overlay filtered out {target.symbol} in {sleeve}; "
                    f"score={_fmt_score(score)}, long={_fmt_decimal_pct(score.long_momentum if score else None)}."
                )

        return [
            target.model_copy(
                update={
                    "target_weight": adjusted_weight_by_symbol[target.symbol],
                    "rationale": rationale_by_symbol[target.symbol],
                }
            )
            for target in target_list
        ]

    def _select_sleeve(
        self,
        targets: Sequence[AllocationTarget],
        context: SignalContext,
    ) -> tuple[list[AllocationTarget], dict[str, BalancedSelectionScore], str]:
        target_list = list(targets)
        scores = self._scores(target_list, context)
        if not scores:
            return target_list, {}, "selected all sleeve assets because ranking history was incomplete"

        eligible = [
            target
            for target in target_list
            if (
                target.symbol in scores
                and (
                    not self.require_positive_long_momentum
                    or (
                        scores[target.symbol].long_momentum is not None
                        and scores[target.symbol].long_momentum > self.min_long_momentum
                    )
                )
            )
        ]
        ranked_targets = sorted(
            [target for target in target_list if target.symbol in scores],
            key=lambda target: (-scores[target.symbol].total, target.symbol),
        )
        if len(eligible) < self.min_selected_per_sleeve and self.fallback_to_top_ranked:
            selected = ranked_targets[: min(len(ranked_targets), self.min_selected_per_sleeve)]
            return selected, scores, "fallback selected top-ranked assets because the positive-momentum gate was too narrow"

        ranked_eligible = sorted(eligible, key=lambda target: (-scores[target.symbol].total, target.symbol))
        selected = ranked_eligible[: self.top_n_per_sleeve]
        return selected, scores, f"{_component_summary(scores[selected[0].symbol].components) if selected else 'components=n/a'}"

    def _scores(
        self,
        targets: Sequence[AllocationTarget],
        context: SignalContext,
    ) -> dict[str, BalancedSelectionScore] | None:
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

        scores: dict[str, BalancedSelectionScore] = {}
        for symbol in symbols:
            weighted_score = Decimal("0")
            weight_sum = Decimal("0")
            components: dict[str, Decimal] = {}
            for category, weight in {"trend": self.trend_weight, "volume": self.volume_weight}.items():
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
            scores[symbol] = BalancedSelectionScore(
                total=_clip(weighted_score / weight_sum, Decimal("-1"), Decimal("1")),
                components=components,
                long_momentum=long_momentum.get(symbol),
            )
        return scores if scores else None


def _fmt_score(score: BalancedSelectionScore | None) -> str:
    return "n/a" if score is None else f"{score.total:.2f}"


class SleeveCappedMomentumOverlay:
    def __init__(
        self,
        *,
        sleeve_by_symbol: Mapping[str, str],
        asset_class_by_symbol: Mapping[str, str],
        region_by_symbol: Mapping[str, str],
        top_n: int = 3,
        max_per_sleeve: int = 1,
        max_per_asset_class: Mapping[str, int] | None = None,
        min_per_asset_class: Mapping[str, int] | None = None,
        max_per_region: Mapping[str, int] | None = None,
        short_momentum_bars: int = 21,
        medium_momentum_bars: int = 63,
        long_momentum_bars: int = 252,
        volume_bars: int = 21,
        slow_volume_bars: int = 126,
        trend_weight: Decimal = Decimal("0.80"),
        volume_weight: Decimal = Decimal("0.20"),
        require_positive_long_momentum: bool = True,
        min_long_momentum: Decimal = Decimal("0"),
        reallocate_selected: bool = True,
        name: str | None = None,
    ) -> None:
        lookbacks = [
            short_momentum_bars,
            medium_momentum_bars,
            long_momentum_bars,
            volume_bars,
            slow_volume_bars,
        ]
        if any(item < 2 for item in lookbacks):
            raise ValueError("All sleeve-capped overlay lookbacks must be at least 2.")
        if top_n < 1:
            raise ValueError("top_n must be at least 1.")
        if max_per_sleeve < 1:
            raise ValueError("max_per_sleeve must be at least 1.")
        if Decimal(trend_weight) < Decimal("0") or Decimal(volume_weight) < Decimal("0"):
            raise ValueError("Sleeve-capped overlay weights must be non-negative.")
        if Decimal(trend_weight) + Decimal(volume_weight) <= Decimal("0"):
            raise ValueError("At least one sleeve-capped overlay weight must be positive.")

        self.sleeve_by_symbol = {symbol.upper(): group for symbol, group in sleeve_by_symbol.items()}
        self.asset_class_by_symbol = {symbol.upper(): group for symbol, group in asset_class_by_symbol.items()}
        self.region_by_symbol = {symbol.upper(): group for symbol, group in region_by_symbol.items()}
        self.top_n = top_n
        self.max_per_sleeve = max_per_sleeve
        self.max_per_asset_class = dict(max_per_asset_class or {})
        self.min_per_asset_class = dict(min_per_asset_class or {})
        self.max_per_region = dict(max_per_region or {})
        self.short_momentum_bars = short_momentum_bars
        self.medium_momentum_bars = medium_momentum_bars
        self.long_momentum_bars = long_momentum_bars
        self.volume_bars = volume_bars
        self.slow_volume_bars = slow_volume_bars
        self.trend_weight = Decimal(trend_weight)
        self.volume_weight = Decimal(volume_weight)
        self.require_positive_long_momentum = require_positive_long_momentum
        self.min_long_momentum = Decimal(min_long_momentum)
        self.reallocate_selected = reallocate_selected
        self.lookback_bars = max(lookbacks)
        self.threshold = self.min_long_momentum
        self.name = name or (
            f"sleeve-capped-momentum-top{top_n}-"
            f"{short_momentum_bars}-{medium_momentum_bars}-{long_momentum_bars}d"
        )

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        target_list = list(targets)
        if len(target_list) < 2:
            return target_list

        scores = self._scores(target_list, context)
        if not scores:
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Sleeve-capped momentum overlay was neutral because "
                            "ranking history was incomplete."
                        )
                    }
                )
                for target in target_list
            ]

        ranked_targets = sorted(
            [target for target in target_list if target.symbol in scores],
            key=lambda target: (-scores[target.symbol].total, target.symbol),
        )
        selected: list[AllocationTarget] = []
        sleeve_counts: dict[str, int] = {}
        asset_class_counts: dict[str, int] = {}
        region_counts: dict[str, int] = {}
        for target in ranked_targets:
            score = scores[target.symbol]
            if (
                self.require_positive_long_momentum
                and (score.long_momentum is None or score.long_momentum <= self.min_long_momentum)
            ):
                continue
            sleeve = self.sleeve_by_symbol.get(target.symbol, "unmapped")
            asset_class = self.asset_class_by_symbol.get(target.symbol, "unmapped")
            region = self.region_by_symbol.get(target.symbol, "unmapped")
            if sleeve_counts.get(sleeve, 0) >= self.max_per_sleeve:
                continue
            if asset_class_counts.get(asset_class, 0) >= self.max_per_asset_class.get(asset_class, self.top_n):
                continue
            if region_counts.get(region, 0) >= self.max_per_region.get(region, self.top_n):
                continue
            selected.append(target)
            sleeve_counts[sleeve] = sleeve_counts.get(sleeve, 0) + 1
            asset_class_counts[asset_class] = asset_class_counts.get(asset_class, 0) + 1
            region_counts[region] = region_counts.get(region, 0) + 1
            if len(selected) >= self.top_n:
                break

        if not selected:
            selected = ranked_targets[: self.top_n]
            sleeve_counts = {}
            asset_class_counts = {}
            region_counts = {}
            for target in selected:
                self._increment_counts(target, sleeve_counts, asset_class_counts, region_counts)
        if selected and self.min_per_asset_class:
            selected, sleeve_counts, asset_class_counts, region_counts = self._enforce_min_asset_classes(
                selected=selected,
                ranked_targets=ranked_targets,
                scores=scores,
                sleeve_counts=sleeve_counts,
                asset_class_counts=asset_class_counts,
                region_counts=region_counts,
            )

        selected_symbols = {target.symbol for target in selected}
        original_weight = sum((target.target_weight for target in target_list), Decimal("0"))
        selected_weight = sum((target.target_weight for target in selected), Decimal("0"))
        scale = original_weight / selected_weight if self.reallocate_selected and selected_weight > Decimal("0") else Decimal("1")

        return [
            self._adjust_target(target, scores.get(target.symbol), selected_symbols, scale)
            for target in target_list
        ]

    def _enforce_min_asset_classes(
        self,
        *,
        selected: list[AllocationTarget],
        ranked_targets: Sequence[AllocationTarget],
        scores: Mapping[str, BalancedSelectionScore],
        sleeve_counts: dict[str, int],
        asset_class_counts: dict[str, int],
        region_counts: dict[str, int],
    ) -> tuple[list[AllocationTarget], dict[str, int], dict[str, int], dict[str, int]]:
        selected_symbols = {target.symbol for target in selected}
        for required_class, minimum in self.min_per_asset_class.items():
            while asset_class_counts.get(required_class, 0) < minimum:
                removable = None
                candidate_sleeve_counts = dict(sleeve_counts)
                candidate_asset_class_counts = dict(asset_class_counts)
                candidate_region_counts = dict(region_counts)
                if len(selected) >= self.top_n:
                    removable = self._weakest_removable(selected, required_class, asset_class_counts, scores)
                    if removable is None:
                        break
                    self._decrement_counts(
                        removable,
                        candidate_sleeve_counts,
                        candidate_asset_class_counts,
                        candidate_region_counts,
                    )
                candidate = self._best_minimum_candidate(
                    required_class=required_class,
                    ranked_targets=ranked_targets,
                    selected_symbols=selected_symbols,
                    sleeve_counts=candidate_sleeve_counts,
                    asset_class_counts=candidate_asset_class_counts,
                    region_counts=candidate_region_counts,
                    require_positive=True,
                    scores=scores,
                )
                if candidate is None:
                    candidate = self._best_minimum_candidate(
                        required_class=required_class,
                        ranked_targets=ranked_targets,
                        selected_symbols=selected_symbols,
                        sleeve_counts=candidate_sleeve_counts,
                        asset_class_counts=candidate_asset_class_counts,
                        region_counts=candidate_region_counts,
                        require_positive=False,
                        scores=scores,
                    )
                if candidate is None:
                    break
                if removable is not None:
                    selected.remove(removable)
                    selected_symbols.remove(removable.symbol)
                    sleeve_counts = candidate_sleeve_counts
                    asset_class_counts = candidate_asset_class_counts
                    region_counts = candidate_region_counts
                selected.append(candidate)
                selected_symbols.add(candidate.symbol)
                self._increment_counts(candidate, sleeve_counts, asset_class_counts, region_counts)
        return selected, sleeve_counts, asset_class_counts, region_counts

    def _best_minimum_candidate(
        self,
        *,
        required_class: str,
        ranked_targets: Sequence[AllocationTarget],
        selected_symbols: set[str],
        sleeve_counts: Mapping[str, int],
        asset_class_counts: Mapping[str, int],
        region_counts: Mapping[str, int],
        require_positive: bool,
        scores: Mapping[str, BalancedSelectionScore],
    ) -> AllocationTarget | None:
        for target in ranked_targets:
            if target.symbol in selected_symbols:
                continue
            if self.asset_class_by_symbol.get(target.symbol, "unmapped") != required_class:
                continue
            score = scores[target.symbol]
            if (
                require_positive
                and self.require_positive_long_momentum
                and (score.long_momentum is None or score.long_momentum <= self.min_long_momentum)
            ):
                continue
            if not self._within_caps(target, sleeve_counts, asset_class_counts, region_counts):
                continue
            return target
        return None

    def _weakest_removable(
        self,
        selected: Sequence[AllocationTarget],
        required_class: str,
        asset_class_counts: Mapping[str, int],
        scores: Mapping[str, BalancedSelectionScore],
    ) -> AllocationTarget | None:
        candidates = []
        for target in selected:
            asset_class = self.asset_class_by_symbol.get(target.symbol, "unmapped")
            minimum = self.min_per_asset_class.get(asset_class, 0)
            if asset_class == required_class:
                continue
            if asset_class_counts.get(asset_class, 0) <= minimum:
                continue
            candidates.append(target)
        if not candidates:
            return None
        return min(candidates, key=lambda target: (scores[target.symbol].total, target.symbol))

    def _within_caps(
        self,
        target: AllocationTarget,
        sleeve_counts: Mapping[str, int],
        asset_class_counts: Mapping[str, int],
        region_counts: Mapping[str, int],
    ) -> bool:
        sleeve = self.sleeve_by_symbol.get(target.symbol, "unmapped")
        asset_class = self.asset_class_by_symbol.get(target.symbol, "unmapped")
        region = self.region_by_symbol.get(target.symbol, "unmapped")
        return (
            sleeve_counts.get(sleeve, 0) < self.max_per_sleeve
            and asset_class_counts.get(asset_class, 0) < self.max_per_asset_class.get(asset_class, self.top_n)
            and region_counts.get(region, 0) < self.max_per_region.get(region, self.top_n)
        )

    def _increment_counts(
        self,
        target: AllocationTarget,
        sleeve_counts: dict[str, int],
        asset_class_counts: dict[str, int],
        region_counts: dict[str, int],
    ) -> None:
        sleeve = self.sleeve_by_symbol.get(target.symbol, "unmapped")
        asset_class = self.asset_class_by_symbol.get(target.symbol, "unmapped")
        region = self.region_by_symbol.get(target.symbol, "unmapped")
        sleeve_counts[sleeve] = sleeve_counts.get(sleeve, 0) + 1
        asset_class_counts[asset_class] = asset_class_counts.get(asset_class, 0) + 1
        region_counts[region] = region_counts.get(region, 0) + 1

    def _decrement_counts(
        self,
        target: AllocationTarget,
        sleeve_counts: dict[str, int],
        asset_class_counts: dict[str, int],
        region_counts: dict[str, int],
    ) -> None:
        sleeve = self.sleeve_by_symbol.get(target.symbol, "unmapped")
        asset_class = self.asset_class_by_symbol.get(target.symbol, "unmapped")
        region = self.region_by_symbol.get(target.symbol, "unmapped")
        sleeve_counts[sleeve] = max(0, sleeve_counts.get(sleeve, 0) - 1)
        asset_class_counts[asset_class] = max(0, asset_class_counts.get(asset_class, 0) - 1)
        region_counts[region] = max(0, region_counts.get(region, 0) - 1)

    def _adjust_target(
        self,
        target: AllocationTarget,
        score: BalancedSelectionScore | None,
        selected_symbols: set[str],
        scale: Decimal,
    ) -> AllocationTarget:
        if target.symbol in selected_symbols:
            return target.model_copy(
                update={
                    "target_weight": target.target_weight * scale,
                    "rationale": (
                        f"{target.rationale} Sleeve-capped momentum selected {target.symbol}; "
                        f"score={_fmt_score(score)}, long={_fmt_decimal_pct(score.long_momentum if score else None)}, "
                        f"sleeve={self.sleeve_by_symbol.get(target.symbol, 'unmapped')}."
                    ),
                }
            )
        return target.model_copy(
            update={
                "target_weight": Decimal("0"),
                "rationale": (
                    f"{target.rationale} Sleeve-capped momentum removed {target.symbol}; "
                    f"score={_fmt_score(score)}, long={_fmt_decimal_pct(score.long_momentum if score else None)}, "
                    f"sleeve={self.sleeve_by_symbol.get(target.symbol, 'unmapped')}."
                ),
            }
        )

    def _scores(
        self,
        targets: Sequence[AllocationTarget],
        context: SignalContext,
    ) -> dict[str, BalancedSelectionScore] | None:
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

        scores: dict[str, BalancedSelectionScore] = {}
        for symbol in symbols:
            weighted_score = Decimal("0")
            weight_sum = Decimal("0")
            components: dict[str, Decimal] = {}
            for category, weight in {"trend": self.trend_weight, "volume": self.volume_weight}.items():
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
            scores[symbol] = BalancedSelectionScore(
                total=_clip(weighted_score / weight_sum, Decimal("-1"), Decimal("1")),
                components=components,
                long_momentum=long_momentum.get(symbol),
            )
        return scores if scores else None


class CommodityRiskGuardOverlay:
    def __init__(
        self,
        *,
        asset_class_by_symbol: Mapping[str, str],
        guarded_asset_class: str = "commodity",
        max_asset_class_weight: Decimal = Decimal("0.55"),
        triggered_scale: Decimal = Decimal("0.50"),
        short_momentum_bars: int = 10,
        slow_momentum_bars: int = 21,
        short_momentum_threshold: Decimal = Decimal("-0.05"),
        fast_volatility_bars: int = 10,
        slow_volatility_bars: int = 63,
        volatility_spike_multiple: Decimal = Decimal("1.50"),
        reallocate_residual: bool = True,
        name: str | None = None,
    ) -> None:
        lookbacks = [short_momentum_bars, slow_momentum_bars, fast_volatility_bars, slow_volatility_bars]
        if any(item < 2 for item in lookbacks):
            raise ValueError("All commodity guard lookbacks must be at least 2.")
        if Decimal(max_asset_class_weight) <= Decimal("0"):
            raise ValueError("max_asset_class_weight must be positive.")
        if Decimal(triggered_scale) < Decimal("0") or Decimal(triggered_scale) > Decimal("1"):
            raise ValueError("triggered_scale must be between 0 and 1.")
        if Decimal(volatility_spike_multiple) <= Decimal("0"):
            raise ValueError("volatility_spike_multiple must be positive.")

        self.asset_class_by_symbol = {symbol.upper(): asset_class for symbol, asset_class in asset_class_by_symbol.items()}
        self.guarded_asset_class = guarded_asset_class
        self.max_asset_class_weight = Decimal(max_asset_class_weight)
        self.triggered_scale = Decimal(triggered_scale)
        self.short_momentum_bars = short_momentum_bars
        self.slow_momentum_bars = slow_momentum_bars
        self.short_momentum_threshold = Decimal(short_momentum_threshold)
        self.fast_volatility_bars = fast_volatility_bars
        self.slow_volatility_bars = slow_volatility_bars
        self.volatility_spike_multiple = Decimal(volatility_spike_multiple)
        self.reallocate_residual = reallocate_residual
        self.lookback_bars = max(lookbacks)
        self.threshold = self.short_momentum_threshold
        self.name = name or f"{guarded_asset_class}-risk-guard"

    def apply(self, targets: Sequence[AllocationTarget], context: SignalContext) -> list[AllocationTarget]:
        target_list = list(targets)
        if not target_list:
            return []

        guarded = [
            target
            for target in target_list
            if target.target_weight > Decimal("0")
            and self.asset_class_by_symbol.get(target.symbol) == self.guarded_asset_class
        ]
        guarded_weight = sum((target.target_weight for target in guarded), Decimal("0"))
        if guarded_weight <= Decimal("0"):
            return target_list

        basket = self._basket_state(guarded, context)
        cap_scale = min(Decimal("1"), self.max_asset_class_weight / guarded_weight)
        crash_triggered = (
            basket["short_momentum"] is not None
            and basket["short_momentum"] <= self.short_momentum_threshold
        )
        vol_triggered = (
            basket["fast_volatility"] is not None
            and basket["slow_volatility"] is not None
            and basket["slow_volatility"] > Decimal("0")
            and basket["fast_volatility"] >= basket["slow_volatility"] * self.volatility_spike_multiple
        )
        trigger_scale = self.triggered_scale if crash_triggered or vol_triggered else Decimal("1")
        scale = min(cap_scale, trigger_scale)
        if scale >= Decimal("1"):
            return [
                target.model_copy(
                    update={
                        "rationale": (
                            f"{target.rationale} Commodity risk guard left weights unchanged; "
                            f"{self.guarded_asset_class} weight={guarded_weight:.2%}, "
                            f"short={_fmt_decimal_pct(basket['short_momentum'])}, "
                            f"fast/slow vol={_fmt_decimal_pct(basket['fast_volatility'])}/"
                            f"{_fmt_decimal_pct(basket['slow_volatility'])}."
                        )
                    }
                )
                if target in guarded
                else target
                for target in target_list
            ]

        adjusted_weights = {target.symbol: target.target_weight for target in target_list}
        residual = Decimal("0")
        for target in guarded:
            new_weight = target.target_weight * scale
            residual += target.target_weight - new_weight
            adjusted_weights[target.symbol] = new_weight

        recipients = [
            target
            for target in target_list
            if target.target_weight > Decimal("0")
            and self.asset_class_by_symbol.get(target.symbol) != self.guarded_asset_class
        ]
        recipient_weight = sum((target.target_weight for target in recipients), Decimal("0"))
        if self.reallocate_residual and residual > Decimal("0") and recipient_weight > Decimal("0"):
            for target in recipients:
                adjusted_weights[target.symbol] += residual * target.target_weight / recipient_weight

        reasons = []
        if cap_scale < Decimal("1"):
            reasons.append(f"capped {self.guarded_asset_class} gross weight at {self.max_asset_class_weight:.0%}")
        if crash_triggered:
            reasons.append(f"short momentum breached {_fmt_decimal_pct(self.short_momentum_threshold)}")
        if vol_triggered:
            reasons.append(f"fast volatility exceeded {self.volatility_spike_multiple}x slow volatility")
        reason = ", ".join(reasons) if reasons else "risk scale applied"

        return [
            target.model_copy(
                update={
                    "target_weight": adjusted_weights[target.symbol],
                    "rationale": (
                        f"{target.rationale} Commodity risk guard {reason}; "
                        f"scale={scale:.2f}, short={_fmt_decimal_pct(basket['short_momentum'])}, "
                        f"slow={_fmt_decimal_pct(basket['slow_momentum'])}, "
                        f"fast/slow vol={_fmt_decimal_pct(basket['fast_volatility'])}/"
                        f"{_fmt_decimal_pct(basket['slow_volatility'])}."
                    ),
                }
            )
            for target in target_list
        ]

    def _basket_state(
        self,
        targets: Sequence[AllocationTarget],
        context: SignalContext,
    ) -> dict[str, Decimal | None]:
        weight_by_symbol = {target.symbol: target.target_weight for target in targets}
        total_weight = sum(weight_by_symbol.values(), Decimal("0"))
        if total_weight <= Decimal("0"):
            return {
                "short_momentum": None,
                "slow_momentum": None,
                "fast_volatility": None,
                "slow_volatility": None,
            }
        short_values = {
            symbol: _momentum(symbol, context, self.short_momentum_bars)
            for symbol in weight_by_symbol
        }
        slow_values = {
            symbol: _momentum(symbol, context, self.slow_momentum_bars)
            for symbol in weight_by_symbol
        }
        fast_vols = {
            symbol: _realized_volatility(symbol, context, self.fast_volatility_bars)
            for symbol in weight_by_symbol
        }
        slow_vols = {
            symbol: _realized_volatility(symbol, context, self.slow_volatility_bars)
            for symbol in weight_by_symbol
        }
        return {
            "short_momentum": _weighted_average(short_values, weight_by_symbol),
            "slow_momentum": _weighted_average(slow_values, weight_by_symbol),
            "fast_volatility": _weighted_average(fast_vols, weight_by_symbol),
            "slow_volatility": _weighted_average(slow_vols, weight_by_symbol),
        }


def _weighted_average(
    values_by_symbol: Mapping[str, Decimal | None],
    weight_by_symbol: Mapping[str, Decimal],
) -> Decimal | None:
    total = Decimal("0")
    weight_sum = Decimal("0")
    for symbol, value in values_by_symbol.items():
        if value is None:
            continue
        weight = weight_by_symbol.get(symbol, Decimal("0"))
        total += weight * value
        weight_sum += weight
    if weight_sum <= Decimal("0"):
        return None
    return total / weight_sum


def _realized_volatility(symbol: str, context: SignalContext, lookback_bars: int) -> Decimal | None:
    bars = [bar for bar in context.bars_by_symbol.get(symbol, []) if bar.trade_date < context.as_of]
    if len(bars) < lookback_bars + 1:
        return None
    closes = [Decimal(bar.close) for bar in bars[-(lookback_bars + 1) :]]
    returns = [
        (closes[index] / closes[index - 1]) - Decimal("1")
        for index in range(1, len(closes))
        if closes[index - 1] > Decimal("0")
    ]
    if len(returns) < 2:
        return None
    clean = [float(item) for item in returns]
    mean = sum(clean) / len(clean)
    variance = sum((item - mean) ** 2 for item in clean) / (len(clean) - 1)
    return Decimal(str(math.sqrt(variance * 252)))
