from decimal import Decimal

from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.config import AppSettings


def test_risk_parity_preview_endpoint_returns_cnh_proposal() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/v1/proposals/risk-parity-preview",
            json={
                "as_of": "2026-04-18",
                "cash": [{"currency": "CNH", "amount": "200000"}],
                "instruments": [
                    {
                        "symbol": "SPY",
                        "name": "SPDR S&P 500 ETF Trust",
                        "asset_class": "etf",
                        "exchange": "NYSE",
                        "quote_currency": "USD",
                        "country": "US"
                    },
                    {
                        "symbol": "VGK",
                        "name": "Vanguard FTSE Europe ETF",
                        "asset_class": "etf",
                        "exchange": "NYSE",
                        "quote_currency": "USD",
                        "country": "Europe"
                    },
                    {
                        "symbol": "2800.HK",
                        "name": "Tracker Fund of Hong Kong",
                        "asset_class": "etf",
                        "exchange": "HKEX",
                        "quote_currency": "HKD",
                        "country": "HK"
                    }
                ],
                "prices": [
                    {"symbol": "SPY", "price": "510"},
                    {"symbol": "VGK", "price": "70"},
                    {"symbol": "2800.HK", "price": "20"}
                ],
                "volatilities": [
                    {"symbol": "SPY", "realized_volatility": "0.18"},
                    {"symbol": "VGK", "realized_volatility": "0.14"},
                    {"symbol": "2800.HK", "realized_volatility": "0.24"}
                ],
                "fx_rates": [
                    {"currency": "USD", "rate_to_cnh": "7.20"},
                    {"currency": "HKD", "rate_to_cnh": "0.92"}
                ],
                "positions": [
                    {"symbol": "SPY", "quantity": 30, "average_cost": "470"}
                ],
                "max_weight": "0.50"
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["proposal"]["base_currency"] == "CNH"
        assert payload["snapshot"]["base_currency"] == "CNH"
        assert payload["proposal"]["orders"]
        target_weights = {item["symbol"]: Decimal(item["target_weight"]) for item in payload["proposal"]["targets"]}
        assert target_weights["VGK"] > target_weights["SPY"] > target_weights["2800.HK"]


def test_watchlist_endpoints_persist_instrument_and_thesis(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "test.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        instrument_response = client.put(
            "/api/v1/watchlist/instruments/NVDA",
            json={
                "symbol": "NVDA",
                "name": "NVIDIA Corporation",
                "asset_class": "stock",
                "exchange": "NASDAQ",
                "quote_currency": "USD",
                "country": "US",
                "sector": "Semiconductors"
            },
        )
        assert instrument_response.status_code == 200

        thesis_response = client.put(
            "/api/v1/watchlist/theses/NVDA",
            json={
                "symbol": "NVDA",
                "status": "active",
                "summary": "High-conviction long-horizon AI infrastructure thesis.",
                "valuation_case": "Monitor whether earnings growth continues to outrun premium valuation.",
                "catalyst_window": "12-24 months",
                "hold_horizon_months": 18,
                "key_risks": ["AI capex slows materially"],
                "invalidation_rules": ["Data-center revenue growth breaks the thesis for two consecutive quarters"],
                "sources": []
            },
        )
        assert thesis_response.status_code == 200

        watchlist_response = client.get("/api/v1/watchlist")
        assert watchlist_response.status_code == 200
        payload = watchlist_response.json()
        assert len(payload) == 1
        assert payload[0]["instrument"]["symbol"] == "NVDA"
        assert payload[0]["thesis"]["hold_horizon_months"] == 18


def test_queue_and_approve_proposal_persists_status(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "queue.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.post(
            "/api/v1/proposals/risk-parity-queue",
            json={
                "as_of": "2026-04-18",
                "cash": [{"currency": "CNH", "amount": "120000"}],
                "instruments": [
                    {
                        "symbol": "SPY",
                        "name": "SPDR S&P 500 ETF Trust",
                        "asset_class": "etf",
                        "exchange": "NYSE",
                        "quote_currency": "USD",
                        "country": "US"
                    },
                    {
                        "symbol": "VGK",
                        "name": "Vanguard FTSE Europe ETF",
                        "asset_class": "etf",
                        "exchange": "NYSE",
                        "quote_currency": "USD",
                        "country": "Europe"
                    }
                ],
                "prices": [
                    {"symbol": "SPY", "price": "500"},
                    {"symbol": "VGK", "price": "70"}
                ],
                "volatilities": [
                    {"symbol": "SPY", "realized_volatility": "0.20"},
                    {"symbol": "VGK", "realized_volatility": "0.15"}
                ],
                "fx_rates": [
                    {"currency": "USD", "rate_to_cnh": "7.20"}
                ]
            },
        )
        assert response.status_code == 200
        proposal_id = response.json()["proposal"]["proposal_id"]

        pending = client.get("/api/v1/proposals", params={"status": "pending"})
        assert pending.status_code == 200
        assert pending.json()[0]["proposal_id"] == proposal_id

        decision = client.post(
            f"/api/v1/proposals/{proposal_id}/decisions",
            json={"status": "approved", "comment": "Paper trade is acceptable."},
        )
        assert decision.status_code == 200
        assert decision.json()["status"] == "approved"

        approved = client.get("/api/v1/proposals", params={"status": "approved"})
        assert approved.status_code == 200
        assert approved.json()[0]["proposal_id"] == proposal_id


def test_market_data_endpoints_persist_price_bars_and_fx_rates(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "market_data.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        bar_response = client.put(
            "/api/v1/market-data/bars/SPY",
            json={
                "trade_date": "2026-04-17",
                "open": "510",
                "high": "515",
                "low": "508",
                "close": "512",
                "volume": 65000000,
            },
        )
        assert bar_response.status_code == 200

        fx_response = client.put(
            "/api/v1/market-data/fx-rates",
            json={
                "rate_date": "2026-04-17",
                "base_currency": "USD",
                "quote_currency": "CNH",
                "rate": "7.20",
            },
        )
        assert fx_response.status_code == 200

        bars = client.get(
            "/api/v1/market-data/bars/SPY",
            params={"start_date": "2026-04-01", "end_date": "2026-04-30"},
        )
        assert bars.status_code == 200
        assert bars.json()[0]["trade_date"] == "2026-04-17"
        assert bars.json()[0]["close"] == "512"

        fx_rates = client.get(
            "/api/v1/market-data/fx-rates",
            params={"base_currency": "USD", "start_date": "2026-04-01", "end_date": "2026-04-30"},
        )
        assert fx_rates.status_code == 200
        assert fx_rates.json()[0]["base_currency"] == "USD"
        assert fx_rates.json()[0]["rate"] == "7.20"


def test_market_data_volatility_endpoint_uses_stored_bars(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "volatility.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        for trade_date, close in [
            ("2026-04-13", "100"),
            ("2026-04-14", "110"),
            ("2026-04-15", "105"),
            ("2026-04-16", "108"),
        ]:
            response = client.put(
                "/api/v1/market-data/bars/SPY",
                json={
                    "trade_date": trade_date,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1000,
                },
            )
            assert response.status_code == 200

        estimate = client.get("/api/v1/market-data/volatility/SPY")

        assert estimate.status_code == 200
        payload = estimate.json()
        assert payload["symbol"] == "SPY"
        assert payload["observation_count"] == 3
        assert payload["realized_volatility"] == "1.1546"


def test_market_data_volatility_endpoint_rejects_short_history(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "short_history.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/market-data/volatility/SPY")

        assert response.status_code == 400
