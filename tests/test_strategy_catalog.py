from systematic_trading.research import current_sota_definition, instantiate_overlays, strategy_model_card
from systematic_trading.research.strategy_catalog import strategy_definition_from_overlay
from systematic_trading.signals import (
    AssetPoolFilterOverlay,
    BasketRiskControlOverlay,
    CommodityRiskGuardOverlay,
    CountryCompositeFactorOverlay,
    DecisionTreeSignalOverlay,
    RegimeGatedRelativeMomentumOverlay,
    SleeveCappedMomentumOverlay,
    TechnicalDecisionTreeAllocatorOverlay,
    TrendQualityFilterOverlay,
)
from systematic_trading.signals.decision_tree import DecisionTreeSample, train_simple_regression_tree


def test_current_sota_definition_instantiates_overlay_and_diagrams() -> None:
    definition = current_sota_definition()
    overlays = instantiate_overlays(definition)
    card = strategy_model_card(definition)

    assert definition.state == "sota"
    assert definition.key == "sota_price_volume_technical_tree_relative_adaptive_top6"
    assert definition.universe_key == "multi_asset"
    assert definition.scheduler == "static_monthly"
    assert isinstance(overlays[0], AssetPoolFilterOverlay)
    assert overlays[0].top_n == 6
    assert overlays[0].min_selected == 4
    assert isinstance(overlays[1], DecisionTreeSignalOverlay)
    assert overlays[1].model.training_summary["samples"] == 1572
    assert isinstance(overlays[2], RegimeGatedRelativeMomentumOverlay)
    assert overlays[2].medium_lookback_bars == 20
    assert overlays[2].long_lookback_bars == 60
    assert overlays[2].calm_tilt == overlays[2].risk_tilt
    assert "Asset-pool filter overlay" in card["layerDiagram"]
    assert "Decision-tree signal overlay" in card["layerDiagram"]
    assert "Relative momentum overlay" in card["layerDiagram"]
    assert "Adaptive trend overlay" in card["layerDiagram"]
    assert "Freeze tree before OOS starts" in card["decisionTree"]


def test_sleeve_capped_and_commodity_guard_definitions_round_trip() -> None:
    sleeve = SleeveCappedMomentumOverlay(
        sleeve_by_symbol={"SPY": "equity_us", "IEF": "rates_us"},
        asset_class_by_symbol={"SPY": "equity", "IEF": "rates"},
        region_by_symbol={"SPY": "US", "IEF": "US"},
        top_n=2,
        max_per_sleeve=1,
        max_per_asset_class={"equity": 1, "rates": 1},
        max_per_region={"US": 2},
    )
    guard = CommodityRiskGuardOverlay(asset_class_by_symbol={"GLD": "commodity"}, max_asset_class_weight="0.45")

    sleeve_overlays = instantiate_overlays(strategy_definition_from_overlay(sleeve))
    guard_overlays = instantiate_overlays(strategy_definition_from_overlay(guard))

    assert isinstance(sleeve_overlays[0], SleeveCappedMomentumOverlay)
    assert sleeve_overlays[0].top_n == 2
    assert sleeve_overlays[0].max_per_asset_class["equity"] == 1
    assert isinstance(guard_overlays[0], CommodityRiskGuardOverlay)
    assert str(guard_overlays[0].max_asset_class_weight) == "0.45"


def test_country_factor_definition_round_trips_and_diagrams() -> None:
    overlay = CountryCompositeFactorOverlay(
        valuation_scores={"SPY": "-0.5", "EWY": "0.5"},
        macro_scores={"SPY": "0.5", "EWY": "0.2"},
    )
    definition = strategy_definition_from_overlay(overlay)
    overlays = instantiate_overlays(definition)
    card = strategy_model_card(definition)

    assert isinstance(overlays[0], CountryCompositeFactorOverlay)
    assert overlays[0].valuation_scores["SPY"] == overlay.valuation_scores["SPY"]
    assert overlays[0].macro_scores["EWY"] == overlay.macro_scores["EWY"]
    assert "Country factor overlay" in card["layerDiagram"]
    assert "valuation and macro-growth score maps" in card["decisionTree"]


def test_asset_pool_filter_definition_round_trips_and_diagrams() -> None:
    overlay = AssetPoolFilterOverlay(top_n=4, min_selected=2, reallocate_selected=True)
    definition = strategy_definition_from_overlay(overlay)
    overlays = instantiate_overlays(definition)
    card = strategy_model_card(definition)

    assert isinstance(overlays[0], AssetPoolFilterOverlay)
    assert overlays[0].top_n == 4
    assert overlays[0].min_selected == 2
    assert "Asset-pool filter overlay" in card["layerDiagram"]
    assert "Final filtered multi-asset targets" in card["decisionTree"]


def test_basket_risk_control_definition_round_trips_and_diagrams() -> None:
    overlay = BasketRiskControlOverlay(defensive_scale="0.55", severe_scale="0.30")
    definition = strategy_definition_from_overlay(overlay)
    overlays = instantiate_overlays(definition)
    card = strategy_model_card(definition)

    assert isinstance(overlays[0], BasketRiskControlOverlay)
    assert overlays[0].defensive_scale == overlay.defensive_scale
    assert overlays[0].severe_scale == overlay.severe_scale
    assert "Basket risk control" in card["layerDiagram"]
    assert "Final risk-controlled targets" in card["decisionTree"]


def test_trend_quality_filter_definition_round_trips_and_diagrams() -> None:
    overlay = TrendQualityFilterOverlay(top_n=5, min_selected=3, low_volatility_weight="0.10")
    definition = strategy_definition_from_overlay(overlay)
    overlays = instantiate_overlays(definition)
    card = strategy_model_card(definition)

    assert isinstance(overlays[0], TrendQualityFilterOverlay)
    assert overlays[0].top_n == 5
    assert overlays[0].min_selected == 3
    assert overlays[0].low_volatility_weight == overlay.low_volatility_weight
    assert "Trend-quality filter overlay" in card["layerDiagram"]
    assert "Final trend-quality targets" in card["decisionTree"]


def test_decision_tree_definition_round_trips_and_diagrams() -> None:
    model = train_simple_regression_tree(
        [
            DecisionTreeSample(features={"macro_growth_score": -1.0}, target=-0.05),
            DecisionTreeSample(features={"macro_growth_score": 1.0}, target=0.05),
        ],
        feature_names=["macro_growth_score"],
        max_depth=1,
        min_samples_leaf=1,
    )
    overlay = DecisionTreeSignalOverlay(model=model, macro_scores={"SPY": "1", "VGK": "-1"})
    definition = strategy_definition_from_overlay(overlay)
    overlays = instantiate_overlays(definition)
    card = strategy_model_card(definition)

    assert isinstance(overlays[0], DecisionTreeSignalOverlay)
    assert overlays[0].model.feature_names == ("macro_growth_score",)
    assert overlays[0].macro_scores["SPY"] == overlay.macro_scores["SPY"]
    assert "Decision-tree signal overlay" in card["layerDiagram"]
    assert "Freeze tree before OOS starts" in card["decisionTree"]


def test_technical_tree_allocator_definition_round_trips_and_diagrams() -> None:
    model = train_simple_regression_tree(
        [
            DecisionTreeSample(features={"macro_growth_score": -1.0}, target=-0.05),
            DecisionTreeSample(features={"macro_growth_score": 1.0}, target=0.05),
        ],
        feature_names=["macro_growth_score"],
        max_depth=1,
        min_samples_leaf=1,
    )
    overlay = TechnicalDecisionTreeAllocatorOverlay(
        model=model,
        top_n=8,
        min_selected=5,
        macro_scores={"SPY": "1", "VGK": "-1"},
    )
    definition = strategy_definition_from_overlay(overlay)
    overlays = instantiate_overlays(definition)
    card = strategy_model_card(definition)

    assert isinstance(overlays[0], TechnicalDecisionTreeAllocatorOverlay)
    assert overlays[0].top_n == 8
    assert overlays[0].min_selected == 5
    assert overlays[0].macro_scores["SPY"] == overlay.macro_scores["SPY"]
    assert "Technical tree allocator" in card["layerDiagram"]
    assert "MACD and Bollinger bands" in card["decisionTree"]
