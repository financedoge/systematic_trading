from systematic_trading.research import current_sota_definition, instantiate_overlays, strategy_model_card
from systematic_trading.signals import RegimeGatedRelativeMomentumOverlay


def test_current_sota_definition_instantiates_overlay_and_diagrams() -> None:
    definition = current_sota_definition()
    overlays = instantiate_overlays(definition)
    card = strategy_model_card(definition)

    assert definition.state == "sota"
    assert isinstance(overlays[0], RegimeGatedRelativeMomentumOverlay)
    assert overlays[0].name == "relative-momentum-126-252d-regime"
    assert "Relative momentum overlay" in card["layerDiagram"]
    assert "Basket drawdown" in card["decisionTree"]
