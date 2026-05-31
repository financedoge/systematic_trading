from datetime import UTC, date, datetime
from decimal import Decimal

from fastapi.testclient import TestClient

from systematic_trading.app import create_app
from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import BrokerOrderStatus, Currency, OrderEnvironment, OrderSide, OrderType
from systematic_trading.domain.execution import BrokerExecutionFill, BrokerOrderRecord, OrderRequest, ProposalReasoning, TradeProposal
from systematic_trading.execution.broker import _local_order_id
from systematic_trading.live import AccountSummaryRow, IbPositionRow
from systematic_trading.research import current_sota_definition


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


def test_submit_approved_proposal_to_ib_paper_persists_broker_records(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "ib_submit.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        queue_response = client.post(
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
                        "country": "US",
                    },
                    {
                        "symbol": "TLT",
                        "name": "iShares 20+ Year Treasury Bond ETF",
                        "asset_class": "etf",
                        "exchange": "NYSE",
                        "quote_currency": "USD",
                        "country": "US",
                    },
                ],
                "prices": [
                    {"symbol": "SPY", "price": "500"},
                    {"symbol": "TLT", "price": "90"},
                ],
                "volatilities": [
                    {"symbol": "SPY", "realized_volatility": "0.20"},
                    {"symbol": "TLT", "realized_volatility": "0.12"},
                ],
                "fx_rates": [
                    {"currency": "USD", "rate_to_cnh": "7.20"},
                ],
            },
        )
        assert queue_response.status_code == 200
        proposal_id = queue_response.json()["proposal"]["proposal_id"]
        decision = client.post(
            f"/api/v1/proposals/{proposal_id}/decisions",
            json={"status": "approved", "comment": "Route to paper."},
        )
        assert decision.status_code == 200

        dry_run = client.post(
            f"/api/v1/execution/interactive-brokers/proposals/{proposal_id}/submit",
            json={"environment": "paper", "confirm_submit": False},
        )
        assert dry_run.status_code == 200
        assert dry_run.json()["records"] == []
        assert "confirm_submit is required" in dry_run.json()["validation_issues"][-1]

        fake_ib = _FakeIBClient(first_order_id=500)
        client.app.state.ib_order_client = fake_ib
        submit = client.post(
            f"/api/v1/execution/interactive-brokers/proposals/{proposal_id}/submit",
            json={"environment": "paper", "confirm_submit": True, "route_order_type": "twap"},
        )

        assert submit.status_code == 200
        payload = submit.json()
        assert payload["validation_issues"] == []
        assert [record["status"] for record in payload["records"]] == ["submitted", "submitted"]
        assert [item[0] for item in fake_ib.placed_orders] == [500, 501]
        assert {record["order"]["order_type"] for record in payload["records"]} == {"twap"}
        assert fake_ib.placed_orders[0][2].algo_strategy == "Twap"
        assert fake_ib.placed_orders[0][2].algo_params["endTime"].endswith("10:00:00 US/Eastern")
        records = client.get("/api/v1/execution/interactive-brokers/orders", params={"proposal_id": proposal_id})
        assert records.status_code == 200
        assert [record["broker_order_id"] for record in records.json()] == [500, 501]


def test_approve_and_submit_routes_twap_paper_orders_in_one_call(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "approve_submit.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        queue_response = client.post(
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
                        "country": "US",
                    },
                    {
                        "symbol": "TLT",
                        "name": "iShares 20+ Year Treasury Bond ETF",
                        "asset_class": "etf",
                        "exchange": "NYSE",
                        "quote_currency": "USD",
                        "country": "US",
                    },
                ],
                "prices": [
                    {"symbol": "SPY", "price": "500"},
                    {"symbol": "TLT", "price": "90"},
                ],
                "volatilities": [
                    {"symbol": "SPY", "realized_volatility": "0.20"},
                    {"symbol": "TLT", "realized_volatility": "0.12"},
                ],
                "fx_rates": [{"currency": "USD", "rate_to_cnh": "7.20"}],
            },
        )
        assert queue_response.status_code == 200
        proposal_id = queue_response.json()["proposal"]["proposal_id"]
        fake_ib = _FakeIBClient(first_order_id=800)
        client.app.state.ib_order_client = fake_ib

        response = client.post(
            f"/api/v1/proposals/{proposal_id}/approve-and-submit",
            json={"comment": "Approve and route."},
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["proposal"]["status"] == "approved"
        assert payload["broker_submission"]["validation_issues"] == []
        assert [record["broker_order_id"] for record in payload["broker_submission"]["records"]] == [800, 801]
        assert {record["order"]["order_type"] for record in payload["broker_submission"]["records"]} == {"twap"}
        assert {
            record["order"]["intended_trade_date"]
            for record in payload["broker_submission"]["records"]
        } == {"2026-04-20"}
        assert [item[0] for item in fake_ib.placed_orders] == [800, 801]
        assert fake_ib.placed_orders[0][2].algo_params["startTime"] == "20260420 09:30:00 US/Eastern"
        assert fake_ib.placed_orders[0][2].algo_params["endTime"] == "20260420 10:00:00 US/Eastern"


def test_failed_only_submit_resubmits_rejected_and_missing_records(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "ib_resubmit.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        queue_response = client.post(
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
                        "country": "US",
                    },
                    {
                        "symbol": "TLT",
                        "name": "iShares 20+ Year Treasury Bond ETF",
                        "asset_class": "etf",
                        "exchange": "NYSE",
                        "quote_currency": "USD",
                        "country": "US",
                    },
                ],
                "prices": [
                    {"symbol": "SPY", "price": "500"},
                    {"symbol": "TLT", "price": "90"},
                ],
                "volatilities": [
                    {"symbol": "SPY", "realized_volatility": "0.20"},
                    {"symbol": "TLT", "realized_volatility": "0.12"},
                ],
                "fx_rates": [{"currency": "USD", "rate_to_cnh": "7.20"}],
            },
        )
        assert queue_response.status_code == 200
        proposal = TradeProposal.model_validate(queue_response.json()["proposal"])
        decision = client.post(
            f"/api/v1/proposals/{proposal.proposal_id}/decisions",
            json={"status": "approved", "comment": "Route to paper."},
        )
        assert decision.status_code == 200
        client.app.state.store.save_broker_order_record(
            BrokerOrderRecord(
                local_order_id=_local_order_id(proposal.proposal_id, 1, proposal.orders[1]),
                proposal_id=proposal.proposal_id,
                environment=OrderEnvironment.PAPER,
                order_index=1,
                order=proposal.orders[1],
                order_ref=f"st-{proposal.proposal_id}-01",
                status=BrokerOrderStatus.REJECTED,
                message="IB rejected previous attempt.",
            )
        )
        fake_ib = _FakeIBClient(first_order_id=700)
        client.app.state.ib_order_client = fake_ib

        submit = client.post(
            f"/api/v1/execution/interactive-brokers/proposals/{proposal.proposal_id}/submit",
            json={"environment": "paper", "confirm_submit": True, "failed_only": True, "route_order_type": "twap"},
        )

        assert submit.status_code == 200
        payload = submit.json()
        assert [record["order_index"] for record in payload["records"]] == [0, 1]
        assert {record["order"]["order_type"] for record in payload["records"]} == {"twap"}
        assert [item[0] for item in fake_ib.placed_orders] == [700, 701]
        records = client.get("/api/v1/execution/interactive-brokers/orders", params={"proposal_id": proposal.proposal_id})
        assert records.status_code == 200
        submitted_records = [record for record in records.json() if record["order_index"] in {0, 1}]
        assert [record["status"] for record in submitted_records] == ["submitted", "submitted"]
        assert [record["broker_order_id"] for record in submitted_records] == [700, 701]


def test_failed_only_submit_resubmits_all_missing_records_after_approved_send_failure(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "ib_resubmit_missing.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        queue_response = client.post(
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
                        "country": "US",
                    },
                    {
                        "symbol": "TLT",
                        "name": "iShares 20+ Year Treasury Bond ETF",
                        "asset_class": "etf",
                        "exchange": "NYSE",
                        "quote_currency": "USD",
                        "country": "US",
                    },
                ],
                "prices": [
                    {"symbol": "SPY", "price": "500"},
                    {"symbol": "TLT", "price": "90"},
                ],
                "volatilities": [
                    {"symbol": "SPY", "realized_volatility": "0.20"},
                    {"symbol": "TLT", "realized_volatility": "0.12"},
                ],
                "fx_rates": [{"currency": "USD", "rate_to_cnh": "7.20"}],
            },
        )
        assert queue_response.status_code == 200
        proposal_id = queue_response.json()["proposal"]["proposal_id"]
        decision = client.post(
            f"/api/v1/proposals/{proposal_id}/decisions",
            json={"status": "approved", "comment": "Approved but first send failed before persistence."},
        )
        assert decision.status_code == 200
        fake_ib = _FakeIBClient(first_order_id=900)
        client.app.state.ib_order_client = fake_ib

        submit = client.post(
            f"/api/v1/execution/interactive-brokers/proposals/{proposal_id}/submit",
            json={"environment": "paper", "confirm_submit": True, "failed_only": True, "route_order_type": "twap"},
        )

        assert submit.status_code == 200
        payload = submit.json()
        assert [record["order_index"] for record in payload["records"]] == [0, 1]
        assert [record["broker_order_id"] for record in payload["records"]] == [900, 901]


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


def test_dashboard_performance_and_holdings_use_strategy_and_account_artifacts(tmp_path) -> None:
    strategy_path = tmp_path / "backtests" / "sota_current" / f"{current_sota_definition().key}.json"
    strategy_path.parent.mkdir(parents=True)
    strategy_path.write_text(
        """
        {
          "nav_series": [
            {"trade_date": "2026-04-17", "nav_cnh": "1000000"},
            {"trade_date": "2026-04-18", "nav_cnh": "1100000"}
          ],
          "proposals": []
        }
        """,
        encoding="utf-8",
    )
    snapshot_dir = tmp_path / "live" / "account_snapshots"
    snapshot_dir.mkdir(parents=True)
    (snapshot_dir / "ib_paper_account_snapshot_20260417_010000.json").write_text(
        """
        {
          "as_of": "2026-04-17",
          "cash": [{"currency": "CNH", "amount": "100000"}],
          "positions": []
        }
        """,
        encoding="utf-8",
    )
    (snapshot_dir / "ib_paper_account_snapshot_20260418_010000.json").write_text(
        """
        {
          "as_of": "2026-04-18",
          "cash": [{"currency": "CNH", "amount": "120000"}],
          "positions": [{"symbol": "SPY", "quantity": 30, "average_cost": "470"}]
        }
        """,
        encoding="utf-8",
    )
    settings = AppSettings(database_path=tmp_path / "dashboard.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        for trade_date, close in [("2026-04-17", "490"), ("2026-04-18", "500")]:
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
        fx_response = client.put(
            "/api/v1/market-data/fx-rates",
            json={
                "rate_date": "2026-04-18",
                "base_currency": "USD",
                "quote_currency": "CNH",
                "rate": "7.20",
            },
        )
        assert fx_response.status_code == 200
        queue_response = client.post(
            "/api/v1/proposals/risk-parity-queue",
            json={
                "as_of": "2026-04-18",
                "cash": [{"currency": "CNH", "amount": "228000"}],
                "instruments": [
                    {
                        "symbol": "SPY",
                        "name": "SPDR S&P 500 ETF Trust",
                        "asset_class": "etf",
                        "exchange": "NYSE",
                        "quote_currency": "USD",
                        "country": "US",
                    },
                    {
                        "symbol": "TLT",
                        "name": "iShares 20+ Year Treasury Bond ETF",
                        "asset_class": "etf",
                        "exchange": "NYSE",
                        "quote_currency": "USD",
                        "country": "US",
                    },
                ],
                "prices": [
                    {"symbol": "SPY", "price": "500"},
                    {"symbol": "TLT", "price": "90"},
                ],
                "volatilities": [
                    {"symbol": "SPY", "realized_volatility": "0.20"},
                    {"symbol": "TLT", "realized_volatility": "0.12"},
                ],
                "fx_rates": [{"currency": "USD", "rate_to_cnh": "7.20"}],
            },
        )
        assert queue_response.status_code == 200

        performance = client.get("/api/v1/dashboard/performance")
        holdings = client.get("/api/v1/dashboard/holdings")

        assert performance.status_code == 200
        performance_payload = performance.json()
        assert performance_payload["latest_strategy_nav_cnh"] == "1100000.00"
        assert performance_payload["latest_account_nav_cnh"] == "228000.00"
        assert performance_payload["latest_strategy_data_date"] == "2026-04-18"
        assert performance_payload["latest_market_data_date"] == "2026-04-18"
        assert performance_payload["strategy_extension_count"] == 0
        assert len(performance_payload["strategy"]) == 2
        assert len(performance_payload["account"]) == 2
        assert holdings.status_code == 200
        holdings_payload = holdings.json()
        assert holdings_payload["account_nav_cnh"] == "228000.00"
        assert holdings_payload["strategy_proposal_id"] == queue_response.json()["proposal"]["proposal_id"]
        symbols = {row["symbol"] for row in holdings_payload["rows"]}
        assert {"SPY", "TLT", "CASH"}.issubset(symbols)


def test_dashboard_performance_extends_strategy_snapshot_with_new_market_bars(tmp_path) -> None:
    strategy_path = tmp_path / "backtests" / "sota_current" / f"{current_sota_definition().key}.json"
    strategy_path.parent.mkdir(parents=True)
    strategy_path.write_text(
        """
        {
          "nav_series": [
            {"trade_date": "2026-04-18", "nav_cnh": "7200"}
          ],
          "final_snapshot": {
            "as_of": "2026-04-18",
            "base_currency": "CNH",
            "cash": [],
            "positions": [
              {
                "symbol": "SPY",
                "quantity": 10,
                "average_cost": "100",
                "market_price": "100",
                "currency": "USD",
                "country": "US"
              }
            ],
            "nav_cnh": "7200",
            "gross_exposure_cnh": "7200",
            "country_exposure_cnh": {"US": "7200"},
            "currency_exposure_cnh": {"USD": "7200"}
          }
        }
        """,
        encoding="utf-8",
    )
    settings = AppSettings(database_path=tmp_path / "dashboard_extend.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        for trade_date, close in [("2026-04-18", "100"), ("2026-04-19", "110")]:
            bar_response = client.put(
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
            assert bar_response.status_code == 200
            fx_response = client.put(
                "/api/v1/market-data/fx-rates",
                json={
                    "rate_date": trade_date,
                    "base_currency": "USD",
                    "quote_currency": "CNH",
                    "rate": "7.20",
                },
            )
            assert fx_response.status_code == 200

        performance = client.get("/api/v1/dashboard/performance")

        assert performance.status_code == 200
        payload = performance.json()
        assert payload["latest_strategy_data_date"] == "2026-04-18"
        assert payload["latest_market_data_date"] == "2026-04-19"
        assert payload["strategy_extension_count"] == 1
        assert payload["latest_strategy_nav_cnh"] == "7920.00"
        assert payload["strategy"][-1]["trade_date"] == "2026-04-19"


def test_dashboard_can_refresh_ib_account_snapshot(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "dashboard_refresh.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        client.app.state.ib_account_snapshot_client = _FakeAccountSnapshotClient()

        response = client.post("/api/v1/dashboard/account-snapshot/refresh")

        assert response.status_code == 200
        payload = response.json()
        assert payload["cash_count"] == 1
        assert payload["position_count"] == 1
        assert payload["managed_accounts"] == ["DU123"]
        snapshot_path = tmp_path / "live" / "account_snapshots"
        snapshots = list(snapshot_path.glob("ib_paper_account_snapshot_*.json"))
        assert len(snapshots) == 1
        assert '"symbol": "SPY"' in snapshots[0].read_text(encoding="utf-8")


def test_dashboard_pnl_uses_filled_broker_history_and_persists_snapshots(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "dashboard_pnl.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        for trade_date_text, close in [("2026-04-17", "100"), ("2026-04-18", "120")]:
            response = client.put(
                "/api/v1/market-data/bars/SPY",
                json={
                    "trade_date": trade_date_text,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1000,
                },
            )
            assert response.status_code == 200
            fx_response = client.put(
                "/api/v1/market-data/fx-rates",
                json={
                    "rate_date": trade_date_text,
                    "base_currency": "USD",
                    "quote_currency": "CNH",
                    "rate": "7.20",
                },
            )
            assert fx_response.status_code == 200

        buy_order = OrderRequest(
            symbol="SPY",
            side=OrderSide.BUY,
            order_type=OrderType.TWAP,
            quantity=10,
            reference_price=Decimal("100"),
            currency=Currency.USD,
            environment=OrderEnvironment.PAPER,
            notional_cnh=Decimal("7200"),
            rationale="Open test lot.",
        )
        sell_order = OrderRequest(
            symbol="SPY",
            side=OrderSide.SELL,
            order_type=OrderType.TWAP,
            quantity=4,
            reference_price=Decimal("110"),
            currency=Currency.USD,
            environment=OrderEnvironment.PAPER,
            notional_cnh=Decimal("3168"),
            rationale="Trim test lot.",
        )
        proposal = TradeProposal(
            proposal_id="pnl-test",
            as_of=date(2026, 4, 18),
            sleeve="test",
            summary="PnL test proposal.",
            orders=[buy_order, sell_order],
            reasoning=ProposalReasoning(summary="test"),
        )
        client.app.state.store.save_proposal(proposal)
        client.app.state.store.save_broker_order_record(
            BrokerOrderRecord(
                local_order_id="buy-fill",
                proposal_id=proposal.proposal_id,
                environment=OrderEnvironment.PAPER,
                order_index=0,
                order=buy_order,
                order_ref="pnl-test-00",
                status=BrokerOrderStatus.FILLED,
                submitted_at=datetime(2026, 4, 17, 14, 30, tzinfo=UTC),
                filled_quantity=10,
                average_fill_price=Decimal("100"),
            )
        )
        client.app.state.store.save_broker_order_record(
            BrokerOrderRecord(
                local_order_id="sell-fill",
                proposal_id=proposal.proposal_id,
                environment=OrderEnvironment.PAPER,
                order_index=1,
                order=sell_order,
                order_ref="pnl-test-01",
                status=BrokerOrderStatus.FILLED,
                submitted_at=datetime(2026, 4, 18, 14, 30, tzinfo=UTC),
                filled_quantity=4,
                average_fill_price=Decimal("110"),
            )
        )

        pnl = client.get("/api/v1/dashboard/pnl", params={"as_of": "2026-04-18"})

        assert pnl.status_code == 200
        payload = pnl.json()
        assert payload["realized_pnl_cnh"] == "288.00"
        assert payload["unrealized_pnl_cnh"] == "864.00"
        assert payload["total_pnl_cnh"] == "1152.00"
        assert payload["open_market_value_cnh"] == "5184.00"
        assert payload["filled_trade_count"] == 2
        spy = [row for row in payload["symbols"] if row["symbol"] == "SPY"][0]
        assert spy["quantity"] == 6
        assert spy["cost_basis_cnh"] == "4320.00"

        saved = client.post("/api/v1/dashboard/pnl/snapshots", params={"as_of": "2026-04-18"})
        assert saved.status_code == 200
        history = client.get("/api/v1/dashboard/pnl/snapshots")
        assert history.status_code == 200
        assert history.json()[0]["total_pnl_cnh"] == "1152.00"

        baseline = client.post("/api/v1/dashboard/pnl/collapse", json={"cutoff_date": "2026-04-17"})
        assert baseline.status_code == 200
        assert baseline.json()["filled_trade_count"] == 1
        after_collapse = client.get("/api/v1/dashboard/pnl", params={"as_of": "2026-04-18"})
        assert after_collapse.status_code == 200
        after_payload = after_collapse.json()
        assert after_payload["baseline_cutoff_at"].startswith("2026-04-17")
        assert after_payload["total_pnl_cnh"] == "1152.00"
        assert after_payload["filled_trade_count"] == 2


def test_dashboard_execution_quality_compares_reference_and_actual_fills(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "execution_quality.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        for trade_date_text, close in [("2026-04-17", "100"), ("2026-04-18", "120")]:
            response = client.put(
                "/api/v1/market-data/bars/SPY",
                json={
                    "trade_date": trade_date_text,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1000,
                },
            )
            assert response.status_code == 200
            fx_response = client.put(
                "/api/v1/market-data/fx-rates",
                json={
                    "rate_date": trade_date_text,
                    "base_currency": "USD",
                    "quote_currency": "CNH",
                    "rate": "7.20",
                },
            )
            assert fx_response.status_code == 200

        order = OrderRequest(
            symbol="SPY",
            side=OrderSide.BUY,
            order_type=OrderType.TWAP,
            quantity=10,
            reference_price=Decimal("100"),
            currency=Currency.USD,
            environment=OrderEnvironment.PAPER,
            notional_cnh=Decimal("7200"),
            rationale="Open test lot.",
        )
        proposal = TradeProposal(
            proposal_id="execution-quality",
            as_of=date(2026, 4, 17),
            sleeve="test",
            summary="Execution quality test.",
            orders=[order],
            reasoning=ProposalReasoning(summary="test"),
        )
        client.app.state.store.save_proposal(proposal)
        client.app.state.store.save_broker_order_record(
            BrokerOrderRecord(
                local_order_id="worse-buy-fill",
                proposal_id=proposal.proposal_id,
                environment=OrderEnvironment.PAPER,
                order_index=0,
                order=order,
                order_ref="execution-quality-00",
                status=BrokerOrderStatus.FILLED,
                submitted_at=datetime(2026, 4, 17, 14, 30, tzinfo=UTC),
                filled_quantity=10,
                average_fill_price=Decimal("101"),
            )
        )
        saved = client.post("/api/v1/dashboard/pnl/snapshots", params={"as_of": "2026-04-18"})
        assert saved.status_code == 200

        response = client.get("/api/v1/dashboard/execution-quality", params={"as_of": "2026-04-18"})

        assert response.status_code == 200
        payload = response.json()
        assert payload["actual_pnl_cnh"] == "1368.00"
        assert payload["theoretical_pnl_cnh"] == "1440.00"
        assert payload["execution_gain_cnh"] == "-72.00"
        assert payload["execution_gain_bps"] == "-100.00"
        assert payload["filled_notional_cnh"] == "7200.00"
        assert payload["history"][0]["execution_gain_cnh"] == "-72.00"
        assert payload["slippage"] == [
            {
                "trade_date": "2026-04-17",
                "daily_slippage_cnh": "-72.00",
                "cumulative_slippage_cnh": "-72.00",
                "daily_slippage_bps": "-100.00",
            }
        ]
        row = payload["rows"][0]
        assert row["symbol"] == "SPY"
        assert row["execution_gain_cnh"] == "-72.00"
        assert row["execution_gain_bps"] == "-100.00"


def test_dashboard_can_sync_ib_fills_into_local_broker_records(tmp_path) -> None:
    settings = AppSettings(database_path=tmp_path / "dashboard_fill_sync.db", data_dir=tmp_path)
    with TestClient(create_app(settings)) as client:
        for trade_date_text, close in [("2026-04-17", "100"), ("2026-04-18", "108")]:
            bar_response = client.put(
                "/api/v1/market-data/bars/SPY",
                json={
                    "trade_date": trade_date_text,
                    "open": close,
                    "high": close,
                    "low": close,
                    "close": close,
                    "volume": 1000,
                },
            )
            assert bar_response.status_code == 200
            fx_response = client.put(
                "/api/v1/market-data/fx-rates",
                json={
                    "rate_date": trade_date_text,
                    "base_currency": "USD",
                    "quote_currency": "CNH",
                    "rate": "7.20",
                },
            )
            assert fx_response.status_code == 200
        order = OrderRequest(
            symbol="SPY",
            side=OrderSide.BUY,
            order_type=OrderType.TWAP,
            quantity=10,
            reference_price=Decimal("100"),
            currency=Currency.USD,
            environment=OrderEnvironment.PAPER,
            notional_cnh=Decimal("7200"),
            rationale="Open test lot.",
        )
        proposal = TradeProposal(
            proposal_id="fill-sync",
            as_of=date(2026, 4, 17),
            sleeve="test",
            summary="Fill sync test.",
            orders=[order],
            reasoning=ProposalReasoning(summary="test"),
        )
        client.app.state.store.save_proposal(proposal)
        client.app.state.store.save_broker_order_record(
            BrokerOrderRecord(
                local_order_id="sync-fill-record",
                proposal_id=proposal.proposal_id,
                environment=OrderEnvironment.PAPER,
                order_index=0,
                order=order,
                order_ref="st-fill-sync-00",
                broker_order_id=900,
                status=BrokerOrderStatus.SUBMITTED,
                submitted_at=datetime(2026, 4, 17, 14, 30, tzinfo=UTC),
                remaining_quantity=10,
            )
        )
        client.app.state.ib_execution_sync_client = _FakeExecutionSyncClient(
            [
                BrokerExecutionFill(
                    broker_order_id=900,
                    order_ref="st-fill-sync-00",
                    symbol="SPY",
                    side=OrderSide.BUY,
                    quantity=10,
                    average_price=Decimal("100"),
                    filled_at=datetime(2026, 4, 17, 15, 0, tzinfo=UTC),
                    currency=Currency.USD,
                )
            ]
        )

        sync = client.post("/api/v1/dashboard/fills/refresh")

        assert sync.status_code == 200
        assert sync.json()["fills_seen"] == 1
        assert sync.json()["records_updated"] == 1
        records = client.get("/api/v1/execution/interactive-brokers/orders", params={"proposal_id": proposal.proposal_id})
        assert records.status_code == 200
        stored = records.json()[0]
        assert stored["status"] == "filled"
        assert stored["filled_quantity"] == 10
        assert stored["remaining_quantity"] == 0
        assert stored["average_fill_price"] == "100.0000"
        pnl = client.get("/api/v1/dashboard/pnl", params={"as_of": "2026-04-18"})
        assert pnl.status_code == 200
        assert pnl.json()["unrealized_pnl_cnh"] == "576.00"


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


class _FakeIBClient:
    def __init__(self, *, first_order_id: int) -> None:
        self.first_order_id = first_order_id
        self.placed_orders = []

    def connect(self, profile):
        self.profile = profile
        return self.first_order_id

    def place_order(self, order_id, contract, order) -> None:
        self.placed_orders.append((order_id, contract, order))

    def disconnect(self) -> None:
        self.disconnected = True


class _FakeAccountSnapshotClient:
    def fetch(self, profile):
        return (
            [AccountSummaryRow(account="DU123", tag="TotalCashValue", value="1000", currency="USD")],
            [
                IbPositionRow(
                    account="DU123",
                    symbol="SPY",
                    security_type="STK",
                    currency="USD",
                    quantity=Decimal("3"),
                    average_cost=Decimal("500.25"),
                )
            ],
            ["DU123"],
        )


class _FakeExecutionSyncClient:
    def __init__(self, fills) -> None:
        self.fills = fills

    def fetch_fills(self, profile):
        self.profile = profile
        return self.fills
