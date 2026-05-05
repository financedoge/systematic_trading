from systematic_trading.research import current_sota_definition, instantiate_overlays, strategy_model_card
from systematic_trading.research.strategy_catalog import strategy_definition_from_overlay
from systematic_trading.signals import (
    CountryCompositeFactorOverlay,
    DecisionTreeSignalOverlay,
    RegimeGatedRelativeMomentumOverlay,
)
from systematic_trading.signals.decision_tree import DecisionTreeSample, train_simple_regression_tree


def test_current_sota_definition_instantiates_overlay_and_diagrams() -> None:
    definition = current_sota_definition()
    overlays = instantiate_overlays(definition)
    card = strategy_model_card(definition)

    assert definition.state == "sota"
    assert isinstance(overlays[0], RegimeGatedRelativeMomentumOverlay)
    assert definition.key == "sota_relative_momentum_20_60d_tilt20_regime"
    assert overlays[0].name == "relative-momentum-20-60d-regime-tilt-0p2"
    assert overlays[0].medium_lookback_bars == 20
    assert overlays[0].long_lookback_bars == 60
    assert overlays[0].calm_tilt == overlays[0].risk_tilt
    assert "Relative momentum overlay" in card["layerDiagram"]
    assert "Basket drawdown" in card["decisionTree"]


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
