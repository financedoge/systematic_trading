from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from systematic_trading.signals import (
    AdaptiveTrendOverlay,
    CountryCompositeFactorOverlay,
    DecisionTreeSignalOverlay,
    RegimeGatedRelativeMomentumOverlay,
    SimpleDecisionTreeModel,
    TimeSeriesMomentumOverlay,
)
from systematic_trading.signals.base import TargetOverlay


@dataclass(frozen=True)
class OverlaySpec:
    kind: str
    parameters: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "parameters": dict(self.parameters)}


@dataclass(frozen=True)
class StrategyDefinition:
    key: str
    name: str
    sleeve_name: str
    state: str
    description: str
    promoted_on: str | None = None
    overlays: tuple[OverlaySpec, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "name": self.name,
            "sleeveName": self.sleeve_name,
            "state": self.state,
            "description": self.description,
            "promotedOn": self.promoted_on,
            "overlays": [overlay.to_dict() for overlay in self.overlays],
        }


def risk_parity_definition() -> StrategyDefinition:
    return StrategyDefinition(
        key="risk_parity",
        name="Baseline risk parity",
        sleeve_name="baseline-risk-parity",
        state="baseline",
        description="Monthly inverse-volatility ETF allocation with a max weight cap and cash reserve.",
    )


def current_sota_definition() -> StrategyDefinition:
    return StrategyDefinition(
        key="sota_relative_momentum_20_60d_tilt20_regime",
        name="SOTA: risk parity + relative momentum 20/60d 20% tilt",
        sleeve_name="sota-relative-momentum-20-60d-tilt20-regime",
        state="sota",
        promoted_on="2026-05-05",
        description=(
            "Monthly risk parity with a shorter-horizon regime-gated cross-sectional relative momentum tilt. "
            "This is the current research hurdle for new candidate strategies."
        ),
        overlays=(
            OverlaySpec(
                kind="relative_momentum",
                parameters={
                    "mediumLookbackBars": "20",
                    "longLookbackBars": "60",
                    "fastVolatilityBars": "21",
                    "slowVolatilityBars": "252",
                    "drawdownLookbackBars": "252",
                    "calmTilt": "0.20",
                    "riskTilt": "0.20",
                    "drawdownTrigger": "-0.08",
                    "volatilityRatioTrigger": "1.35",
                    "maxActiveWeight": "0.07",
                },
            ),
        ),
    )


def strategy_definition_from_overlay(overlay: TargetOverlay) -> StrategyDefinition:
    if isinstance(overlay, DecisionTreeSignalOverlay):
        summary = dict(overlay.model.training_summary)
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description=(
                "Research candidate using an in-sample-trained regression decision tree over the signal library."
            ),
            overlays=(
                OverlaySpec(
                    kind="decision_tree",
                    parameters={
                        "maxDepth": str(overlay.model.max_depth),
                        "minSamplesLeaf": str(overlay.model.min_samples_leaf),
                        "trainingSamples": str(summary.get("samples", "0")),
                        "tilt": str(overlay.tilt),
                        "maxActiveWeight": str(overlay.max_active_weight),
                        "valuationScores": _score_map_param(overlay.valuation_scores),
                        "macroScores": _score_map_param(overlay.macro_scores),
                        "model": json.dumps(overlay.model.to_dict(), separators=(",", ":")),
                    },
                ),
            ),
        )
    if isinstance(overlay, CountryCompositeFactorOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description=(
                "Research candidate using country ETF trend, volume, mean-reversion, valuation, "
                "and macro-growth factor tilts."
            ),
            overlays=(
                OverlaySpec(
                    kind="country_factor",
                    parameters={
                        "shortMomentumBars": str(overlay.short_momentum_bars),
                        "mediumMomentumBars": str(overlay.medium_momentum_bars),
                        "longMomentumBars": str(overlay.long_momentum_bars),
                        "reversalBars": str(overlay.reversal_bars),
                        "meanReversionBars": str(overlay.mean_reversion_bars),
                        "volumeBars": str(overlay.volume_bars),
                        "slowVolumeBars": str(overlay.slow_volume_bars),
                        "trendWeight": str(overlay.trend_weight),
                        "volumeWeight": str(overlay.volume_weight),
                        "meanReversionWeight": str(overlay.mean_reversion_weight),
                        "valuationWeight": str(overlay.valuation_weight),
                        "macroWeight": str(overlay.macro_weight),
                        "tilt": str(overlay.tilt),
                        "maxActiveWeight": str(overlay.max_active_weight),
                        "valuationScores": _score_map_param(overlay.valuation_scores),
                        "macroScores": _score_map_param(overlay.macro_scores),
                    },
                ),
            ),
        )
    if isinstance(overlay, RegimeGatedRelativeMomentumOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description="Research candidate using a regime-gated cross-sectional relative momentum overlay.",
            overlays=(
                OverlaySpec(
                    kind="relative_momentum",
                    parameters={
                        "mediumLookbackBars": str(overlay.medium_lookback_bars),
                        "longLookbackBars": str(overlay.long_lookback_bars),
                        "fastVolatilityBars": str(overlay.fast_volatility_bars),
                        "slowVolatilityBars": str(overlay.slow_volatility_bars),
                        "drawdownLookbackBars": str(overlay.drawdown_lookback_bars),
                        "calmTilt": str(overlay.calm_tilt),
                        "riskTilt": str(overlay.risk_tilt),
                        "drawdownTrigger": str(overlay.drawdown_trigger),
                        "volatilityRatioTrigger": str(overlay.volatility_ratio_trigger),
                        "maxActiveWeight": str(overlay.max_active_weight),
                    },
                ),
            ),
        )
    if isinstance(overlay, AdaptiveTrendOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description="Research candidate using adaptive trend exposure scaling.",
            overlays=(
                OverlaySpec(
                    kind="adaptive_trend",
                    parameters={
                        "shortLookbackBars": str(overlay.short_lookback_bars),
                        "mediumLookbackBars": str(overlay.medium_lookback_bars),
                        "longLookbackBars": str(overlay.long_lookback_bars),
                        "reboundLookbackBars": str(overlay.rebound_lookback_bars),
                        "volumeLookbackBars": str(overlay.volume_lookback_bars),
                        "fastVolatilityBars": str(overlay.fast_volatility_bars),
                        "slowVolatilityBars": str(overlay.slow_volatility_bars),
                        "shortThreshold": str(overlay.short_threshold),
                        "mediumThreshold": str(overlay.medium_threshold),
                        "longThreshold": str(overlay.long_threshold),
                        "weakScale": str(overlay.weak_scale),
                        "neutralScale": str(overlay.neutral_scale),
                        "defensiveScale": str(overlay.defensive_scale),
                        "reboundScale": str(overlay.rebound_scale),
                        "reallocateResidual": str(overlay.reallocate_residual).lower(),
                    },
                ),
            ),
        )
    if isinstance(overlay, TimeSeriesMomentumOverlay):
        return StrategyDefinition(
            key=overlay.name.replace("-", "_"),
            name=f"Research: risk parity + {overlay.name}",
            sleeve_name=f"research-risk-parity-{overlay.name}",
            state="research",
            description="Research candidate using absolute time-series momentum gating.",
            overlays=(
                OverlaySpec(
                    kind="time_series_momentum",
                    parameters={
                        "lookbackBars": str(overlay.lookback_bars),
                        "threshold": str(overlay.threshold),
                        "reallocateSurvivors": str(overlay.reallocate_survivors).lower(),
                    },
                ),
            ),
        )
    raise TypeError(f"Unsupported overlay type: {type(overlay).__name__}")


def instantiate_overlays(definition: StrategyDefinition) -> list[TargetOverlay]:
    overlays: list[TargetOverlay] = []
    for spec in definition.overlays:
        params = spec.parameters
        if spec.kind == "relative_momentum":
            overlays.append(
                RegimeGatedRelativeMomentumOverlay(
                    medium_lookback_bars=int(params["mediumLookbackBars"]),
                    long_lookback_bars=int(params["longLookbackBars"]),
                    fast_volatility_bars=int(params["fastVolatilityBars"]),
                    slow_volatility_bars=int(params["slowVolatilityBars"]),
                    drawdown_lookback_bars=int(params["drawdownLookbackBars"]),
                    calm_tilt=Decimal(params["calmTilt"]),
                    risk_tilt=Decimal(params["riskTilt"]),
                    drawdown_trigger=Decimal(params["drawdownTrigger"]),
                    volatility_ratio_trigger=Decimal(params["volatilityRatioTrigger"]),
                    max_active_weight=Decimal(params["maxActiveWeight"]),
                )
            )
        elif spec.kind == "decision_tree":
            overlays.append(
                DecisionTreeSignalOverlay(
                    model=SimpleDecisionTreeModel.from_dict(json.loads(params["model"])),
                    tilt=Decimal(params["tilt"]),
                    max_active_weight=Decimal(params["maxActiveWeight"]),
                    valuation_scores=_parse_score_map(params.get("valuationScores", "")),
                    macro_scores=_parse_score_map(params.get("macroScores", "")),
                )
            )
        elif spec.kind == "country_factor":
            overlays.append(
                CountryCompositeFactorOverlay(
                    short_momentum_bars=int(params["shortMomentumBars"]),
                    medium_momentum_bars=int(params["mediumMomentumBars"]),
                    long_momentum_bars=int(params["longMomentumBars"]),
                    reversal_bars=int(params["reversalBars"]),
                    mean_reversion_bars=int(params["meanReversionBars"]),
                    volume_bars=int(params["volumeBars"]),
                    slow_volume_bars=int(params["slowVolumeBars"]),
                    trend_weight=Decimal(params["trendWeight"]),
                    volume_weight=Decimal(params["volumeWeight"]),
                    mean_reversion_weight=Decimal(params["meanReversionWeight"]),
                    valuation_weight=Decimal(params["valuationWeight"]),
                    macro_weight=Decimal(params["macroWeight"]),
                    tilt=Decimal(params["tilt"]),
                    max_active_weight=Decimal(params["maxActiveWeight"]),
                    valuation_scores=_parse_score_map(params.get("valuationScores", "")),
                    macro_scores=_parse_score_map(params.get("macroScores", "")),
                )
            )
        elif spec.kind == "adaptive_trend":
            overlays.append(
                AdaptiveTrendOverlay(
                    short_lookback_bars=int(params["shortLookbackBars"]),
                    medium_lookback_bars=int(params["mediumLookbackBars"]),
                    long_lookback_bars=int(params["longLookbackBars"]),
                    rebound_lookback_bars=int(params["reboundLookbackBars"]),
                    volume_lookback_bars=int(params["volumeLookbackBars"]),
                    fast_volatility_bars=int(params["fastVolatilityBars"]),
                    slow_volatility_bars=int(params["slowVolatilityBars"]),
                    short_threshold=Decimal(params["shortThreshold"]),
                    medium_threshold=Decimal(params["mediumThreshold"]),
                    long_threshold=Decimal(params["longThreshold"]),
                    weak_scale=Decimal(params["weakScale"]),
                    neutral_scale=Decimal(params["neutralScale"]),
                    defensive_scale=Decimal(params["defensiveScale"]),
                    rebound_scale=Decimal(params["reboundScale"]),
                    reallocate_residual=_bool(params["reallocateResidual"]),
                )
            )
        elif spec.kind == "time_series_momentum":
            overlays.append(
                TimeSeriesMomentumOverlay(
                    lookback_bars=int(params["lookbackBars"]),
                    threshold=Decimal(params["threshold"]),
                    reallocate_survivors=_bool(params["reallocateSurvivors"]),
                )
            )
        else:
            raise ValueError(f"Unsupported overlay spec: {spec.kind}")
    return overlays


def build_model_structure_comparison(
    *,
    baseline: StrategyDefinition,
    candidate: StrategyDefinition,
) -> dict[str, Any]:
    return {
        "baseline": strategy_model_card(baseline),
        "candidate": strategy_model_card(candidate),
    }


def strategy_model_card(definition: StrategyDefinition) -> dict[str, Any]:
    layers = _model_layers(definition)
    return {
        "definition": definition.to_dict(),
        "layers": layers,
        "layerDiagram": _layer_mermaid(layers),
        "decisionTree": _decision_tree_mermaid(definition),
    }


def _model_layers(definition: StrategyDefinition) -> list[dict[str, str]]:
    layers = [
        {
            "id": "data",
            "title": "Market data",
            "detail": "Adjusted ETF closes, volumes, and USD/CNH FX for SPY, VGK, EWJ, EWH, EWY.",
        },
        {
            "id": "schedule",
            "title": "Monthly rebalance",
            "detail": "Recompute targets on the first available trading day of each month.",
        },
        {
            "id": "risk_parity",
            "title": "Risk parity beta",
            "detail": "63-bar realized volatility, inverse-vol weights, 45% max weight, 2% cash reserve.",
        },
    ]
    for index, overlay in enumerate(definition.overlays, start=1):
        layers.append(_overlay_layer(overlay, index))
    layers.append(
        {
            "id": "targets",
            "title": "Final target weights",
            "detail": "Normalize portfolio weights and feed the daily backtest execution engine.",
        }
    )
    return layers


def _overlay_layer(overlay: OverlaySpec, index: int) -> dict[str, str]:
    params = overlay.parameters
    if overlay.kind == "relative_momentum":
        detail = (
            f"Score = 45% {params['mediumLookbackBars']}d momentum + 55% {params['longLookbackBars']}d momentum; "
            f"regime drawdown trigger {params['drawdownTrigger']}, vol-ratio trigger {params['volatilityRatioTrigger']}; "
            f"tilt {params['calmTilt']} calm / {params['riskTilt']} risk; cap active weight {params['maxActiveWeight']}."
        )
        title = "Relative momentum overlay"
    elif overlay.kind == "decision_tree":
        detail = (
            f"Train a max-depth {params['maxDepth']} regression tree on {params['trainingSamples']} "
            f"in-sample asset-month observations from the signal library; tilt {params['tilt']}, "
            f"cap active weight {params['maxActiveWeight']}."
        )
        title = "Decision-tree signal overlay"
    elif overlay.kind == "country_factor":
        detail = (
            f"Blend {params['shortMomentumBars']}/{params['mediumMomentumBars']}/{params['longMomentumBars']}d trend, "
            f"{params['volumeBars']}d volume pressure, {params['reversalBars']}/{params['meanReversionBars']}d "
            f"mean reversion, valuation priors, and macro-growth priors; tilt {params['tilt']}, "
            f"cap active weight {params['maxActiveWeight']}."
        )
        title = "Country factor overlay"
    elif overlay.kind == "adaptive_trend":
        detail = (
            f"Blend {params['shortLookbackBars']}/{params['mediumLookbackBars']}/{params['longLookbackBars']}d trend, "
            f"volume, rebound, and volatility shock gates; scales {params['weakScale']}, "
            f"{params['neutralScale']}, {params['defensiveScale']}, {params['reboundScale']}."
        )
        title = "Adaptive trend overlay"
    elif overlay.kind == "time_series_momentum":
        mode = "reallocate survivors" if _bool(params["reallocateSurvivors"]) else "hold residual cash"
        detail = (
            f"Keep assets above {params['lookbackBars']}d return threshold {params['threshold']}; otherwise reduce to zero and {mode}."
        )
        title = "Time-series momentum overlay"
    else:
        title = overlay.kind.replace("_", " ").title()
        detail = "Custom overlay."
    return {"id": f"overlay_{index}", "title": title, "detail": detail}


def _layer_mermaid(layers: list[dict[str, str]]) -> str:
    lines = ["flowchart LR"]
    for index, layer in enumerate(layers):
        node_id = f"L{index + 1}"
        lines.append(f'  {node_id}["{_mermaid_label(layer["title"], layer["detail"])}"]')
        if index:
            lines.append(f"  L{index} --> {node_id}")
    return "\n".join(lines)


def _decision_tree_mermaid(definition: StrategyDefinition) -> str:
    if not definition.overlays:
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Monthly rebalance date"]) --> B{"Enough 63-bar history for every ETF?"}',
                '  B -- "No" --> C["Skip rebalance until history is available"]',
                '  B -- "Yes" --> D["Compute realized volatility by ETF"]',
                '  D --> E{"All volatilities positive?"}',
                '  E -- "No" --> C',
                '  E -- "Yes" --> F["Allocate inverse to volatility"]',
                '  F --> G["Apply 45% max weight and 2% cash reserve"]',
                '  G --> H(["Final risk-parity targets"])',
            ]
        )
    trees = [_overlay_decision_tree(overlay) for overlay in definition.overlays]
    if len(trees) == 1:
        return trees[0]
    return "\n\n".join(trees)


def _overlay_decision_tree(overlay: OverlaySpec) -> str:
    params = overlay.parameters
    if overlay.kind == "relative_momentum":
        return "\n".join(
            [
                "flowchart TD",
                (
                    f'  A(["Risk-parity targets"]) --> B{{"Enough {params["mediumLookbackBars"]}d '
                    f'and {params["longLookbackBars"]}d history for the basket?"}}'
                ),
                '  B -- "No" --> C["Keep risk-parity targets"]',
                (
                    f'  B -- "Yes" --> D["Score each ETF = 45% {params["mediumLookbackBars"]}d '
                    f'momentum + 55% {params["longLookbackBars"]}d momentum"]'
                ),
                (
                    f'  D --> E{{"Basket drawdown <= {params["drawdownTrigger"]} '
                    f'or vol-ratio >= {params["volatilityRatioTrigger"]}?"}}'
                ),
                f'  E -- "Yes" --> F["Use risk tilt {params["riskTilt"]}"]',
                f'  E -- "No" --> G["Use calm tilt {params["calmTilt"]}"]',
                '  F --> H["Rank ETFs by score"]',
                '  G --> H',
                '  H --> I["Multiply base weight by 1 + tilt * rank score"]',
                f'  I --> J["Cap active delta at +/-{params["maxActiveWeight"]} per ETF"]',
                '  J --> K["Rescale to preserve original invested weight"]',
                '  K --> L(["Final SOTA/research targets"])',
            ]
        )
    if overlay.kind == "decision_tree":
        return "\n".join(
            [
                "flowchart TD",
                '  A(["In-sample rebalance rows"]) --> B["Compute signal-library features"]',
                '  B --> C["Target = next-month asset return minus basket mean"]',
                f'  C --> D["Fit regression tree, max depth {params["maxDepth"]}"]',
                '  D --> E(["Freeze tree before OOS starts"])',
                '  E --> F["Score ETFs at each rebalance"]',
                f'  F --> G["Rank forecasts and apply tilt {params["tilt"]}"]',
                f'  G --> H["Cap active delta at +/-{params["maxActiveWeight"]} per ETF"]',
                '  H --> I["Rescale to preserve original invested weight"]',
                '  I --> J(["Final decision-tree targets"])',
            ]
        )
    if overlay.kind == "country_factor":
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Risk-parity targets"]) --> B{"Enough price and volume history?"}',
                '  B -- "No" --> C["Keep risk-parity targets"]',
                '  B -- "Yes" --> D["Rank trend, volume pressure, and mean-reversion factors"]',
                '  D --> E["Add valuation and macro-growth score maps when supplied"]',
                f'  E --> F["Blend factor scores using tilt {params["tilt"]}"]',
                f'  F --> G["Cap active delta at +/-{params["maxActiveWeight"]} per ETF"]',
                '  G --> H["Rescale to preserve original invested weight"]',
                '  H --> I(["Final country factor targets"])',
            ]
        )
    if overlay.kind == "adaptive_trend":
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Risk-parity targets"]) --> B{"Enough short/medium/long trend history?"}',
                '  B -- "No" --> C["Keep risk-parity targets"]',
                '  B -- "Yes" --> D["Score trend across short, medium, and long windows"]',
                '  D --> E{"Volatility shock?"}',
                f'  E -- "Yes" --> F["Use defensive scale {params["defensiveScale"]}"]',
                '  E -- "No" --> G{"Rebound or volume confirmation?"}',
                f'  G -- "Yes" --> H["Use rebound/neutral scale up to {params["reboundScale"]}"]',
                f'  G -- "No" --> I["Use weak/neutral/full trend scale starting at {params["weakScale"]}"]',
                '  F --> J["Optionally reallocate residual to stronger assets"]',
                '  H --> J',
                '  I --> J',
                '  J --> K(["Final adaptive targets"])',
            ]
        )
    if overlay.kind == "time_series_momentum":
        mode = "reallocate survivors" if _bool(params["reallocateSurvivors"]) else "leave residual in cash"
        return "\n".join(
            [
                "flowchart TD",
                '  A(["Risk-parity targets"]) --> B{"Enough lookback history for asset?"}',
                '  B -- "No" --> C["Keep asset weight"]',
                f'  B -- "Yes" --> D{{"{params["lookbackBars"]}d return > {params["threshold"]}?"}}',
                '  D -- "Yes" --> C',
                '  D -- "No" --> E["Set asset weight to zero"]',
                f'  E --> F["{mode}"]',
                '  F --> G(["Final trend targets"])',
            ]
        )
    return "\n".join(["flowchart TD", '  A(["Custom overlay"]) --> B(["Final targets"])'])


def _mermaid_label(title: str, detail: str) -> str:
    return f"{_escape_mermaid(title)}<br/>{_escape_mermaid(detail)}"


def _escape_mermaid(value: str) -> str:
    return value.replace('"', "'")


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y"}


def _score_map_param(values: dict[str, Decimal]) -> str:
    return ",".join(f"{symbol}:{value}" for symbol, value in sorted(values.items()))


def _parse_score_map(value: str) -> dict[str, Decimal]:
    scores: dict[str, Decimal] = {}
    for item in value.split(","):
        if not item.strip():
            continue
        if ":" in item:
            symbol, score = item.split(":", 1)
        else:
            symbol, score = item.split("=", 1)
        scores[symbol.strip().upper()] = Decimal(score.strip())
    return scores
