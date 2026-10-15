from decimal import Decimal
from random import Random

import pytest
from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.backtest.risk import inverse_volatility_weights


def preview_payload():
    return {
        "as_of": "2026-10-09",
        "instruments": [dict(symbol=s, name=s, asset_class="etf", exchange="NYSE",
                             quote_currency="USD", country="US") for s in ("SPY", "TLT", "GLD")],
        "prices": [dict(symbol=s, price="100") for s in ("SPY", "TLT", "GLD")],
        "volatilities": [dict(symbol=s, realized_volatility="0.2") for s in ("SPY", "TLT", "GLD")],
        "fx_rates": [dict(currency="USD", rate_to_cnh="7")],
        "cash": [dict(currency="CNH", amount="10000")],
    }


@pytest.mark.parametrize("field", ["instruments", "prices", "volatilities"])
@pytest.mark.parametrize("endpoint", ["risk-parity-preview", "risk-parity-queue"])
def test_empty_preview_inputs_are_validation_errors(field, endpoint):
    payload = preview_payload()
    payload[field] = []
    with TestClient(create_app()) as client:
        assert client.post(f"/api/v1/proposals/{endpoint}", json=payload).status_code == 422
        assert client.get("/api/v1/proposals").json() == []


@pytest.mark.parametrize("field", ["instruments", "prices", "volatilities", "fx_rates", "positions"])
def test_duplicate_preview_inputs_cannot_overwrite_each_other(field):
    payload = preview_payload()
    if field == "positions":
        payload[field] = [dict(symbol="SPY", quantity=1, average_cost="90")]
    payload[field].append(payload[field][0].copy())
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/proposals/risk-parity-preview", json=payload)
    assert response.status_code == 422
    assert "Duplicate" in response.text


def test_preview_missing_fx_is_actionable_and_does_not_queue():
    payload = preview_payload()
    payload["fx_rates"] = []
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/proposals/risk-parity-queue", json=payload)
        assert response.status_code == 400
        assert "Missing FX rates for: USD" in response.text
        assert client.get("/api/v1/proposals").json() == []


def test_preview_rejects_nonidentity_base_currency():
    payload = preview_payload()
    payload["fx_rates"].append(dict(currency="CNH", rate_to_cnh="2"))
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/proposals/risk-parity-preview", json=payload)
    assert response.status_code == 422
    assert "CNH rate_to_cnh must equal 1" in response.text


def test_cap_error_recommends_feasible_rounded_minimum():
    payload = preview_payload()
    payload["max_weight"] = "0.3333"
    with TestClient(create_app()) as client:
        response = client.post("/api/v1/proposals/risk-parity-preview", json=payload)
        assert response.status_code == 400
        assert "0.3334" in response.text
        payload["max_weight"] = "0.3334"
        assert client.post("/api/v1/proposals/risk-parity-preview", json=payload).status_code == 200


def test_rounding_does_not_exceed_concentration_cap():
    volatilities = dict(zip("ABCDEF", map(Decimal, [".35", "1.17", "1.97", ".62", "1.13", "1.58"]), strict=True))
    weights = inverse_volatility_weights(volatilities)
    assert weights["A"] == Decimal(".35")
    assert sum(weights.values()) == 1
    assert all(0 <= weight <= Decimal(".35") for weight in weights.values())


def test_rounding_properties_and_input_order_independence():
    random = Random(17)
    for size in (3, 6, 14, 100):
        for _ in range(30):
            values = {str(i): Decimal(random.randrange(1, 2000)) / 100 for i in range(size)}
            cap = Decimal(".35005")
            weights = inverse_volatility_weights(values, max_weight=cap)
            assert sum(weights.values()) == 1
            assert all(0 <= weight <= cap for weight in weights.values())
            assert weights == inverse_volatility_weights(dict(reversed(list(values.items()))), max_weight=cap)


@pytest.mark.parametrize("value", ["0", "-1", "NaN", "Infinity"])
def test_invalid_volatility_is_rejected(value):
    with pytest.raises(ValueError, match="finite and positive"):
        inverse_volatility_weights(dict(A=Decimal(value), B=Decimal(1), C=Decimal(1)))


def test_unrepresentable_cap_is_rejected():
    with pytest.raises(ValueError, match="precision"):
        inverse_volatility_weights(dict(A=Decimal(1), B=Decimal(1), C=Decimal(1)), max_weight=Decimal(".3333334"))
