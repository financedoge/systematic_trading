from datetime import date, timedelta, datetime, UTC
from decimal import Decimal
import json
import pytest

from systematic_trading.config import AppSettings
from systematic_trading.data.ib_fx import IbFxDailyBarProvider
from systematic_trading.domain import Currency, PriceBar
from systematic_trading.execution.ib_compat import compatible_ib_errors, cancel_ib_order
from systematic_trading.live.fx import refresh_required_fx
from systematic_trading.live.market_data import _next_missing_price_date
from systematic_trading.live.management_service import TradingManagementService
from systematic_trading.storage.sqlite import SQLiteStore
from test_initial_allocation import setup, history_db, NOW, DECISION, Orders


def bar(day, close):
    return PriceBar(trade_date=day, open=close, high=close, low=close, close=close, volume=0)


class FXClient:
    def __init__(self, legs):
        self.legs = legs
        self.calls = []

    def fetch_daily_bars(self, profile, symbol, start_date, end_date, *, forex_currency):
        self.calls.append((profile, symbol, forex_currency))
        return self.legs.get((symbol, forex_currency), [])


def test_cross_rates_use_only_matching_observed_dates_and_preserve_evidence(tmp_path):
    day = date(2026, 9, 24)
    client = FXClient({("USD", "CNH"): [bar(day, "7"), bar(day-timedelta(days=1), "6.9"), bar(day+timedelta(days=1), "7.1")],
        ("USD", "HKD"): [bar(day, "8"), bar(day+timedelta(days=1), "8")]})
    provider = IbFxDailyBarProvider(AppSettings(data_dir=tmp_path), client=client)
    rates = provider.fetch_daily_bars("HKD/CNH", day-timedelta(days=1), day)
    assert [(b.trade_date, b.close) for b in rates] == [(day, Decimal("0.875"))]
    assert all(c[0].environment.value == "paper" and c[0].client_id == 181 for c in client.calls)
    evidence = json.loads(next((tmp_path / "market_data" / "fx_observations").glob("*.json")).read_text())
    assert evidence["formula"] == "USD/CNH / USD/HKD"
    assert set(evidence["legs"]) == {"USD/CNH", "USD/HKD"}
    assert evidence["rates"][0]["trade_date"] == str(day)


def test_usd_rate_is_offshore_cnh_and_unsupported_mapping_fails(tmp_path):
    day = date(2026, 9, 24)
    client = FXClient({("USD", "CNH"): [bar(day, "7")]})
    provider = IbFxDailyBarProvider(AppSettings(data_dir=tmp_path), client=client)
    assert provider.fetch_daily_bars("USD/CNH", day, day)[0].close == 7
    assert client.calls[0][1:] == ("USD", "CNH")
    with pytest.raises(ValueError, match="verified IB FX mapping"):
        provider.fetch_daily_bars("KRW/CNH", day, day)
    future = datetime.now(UTC).date() + timedelta(days=1)
    with pytest.raises(ValueError, match="not complete"):
        provider.fetch_daily_bars("USD/CNH", future, future)


def test_fx_readiness_does_not_accept_missing_date_or_future_rate(tmp_path):
    store = SQLiteStore(tmp_path / "fx.db");store.initialize()
    day = date(2026, 9, 24)
    class Provider:
        def fetch_daily_bars(self, symbol, start, end):
            return [bar(day + timedelta(days=1), "7")]
    result = refresh_required_fx(store=store,target_date=day,currencies=[Currency.USD,Currency.HKD],provider=Provider())
    assert result.rates_upserted == 0
    assert len(result.warnings) == 2
    assert result.latest_dates == {"HKD": None, "USD": None}


def test_automatic_cash_currency_refresh_unblocks_initial_proposal(setup):
    settings, store, _ = setup
    with store._connect() as connection:
        connection.execute("DELETE FROM fx_rates WHERE base_currency='HKD'")
    class Provider:
        def __init__(self): self.requests = []
        def fetch_daily_bars(self, symbol, start, end):
            self.requests.append(symbol)
            return [bar(end, "0.92")]
    provider = Provider()
    service = TradingManagementService(settings=settings, store=store, fx_market_data_provider=provider, order_management_client=Orders())
    service._stage_portfolio_alignment(NOW)
    assert provider.requests == ["HKD/CNH"]
    assert service.status().portfolio_alignment_status == "queued"
    assert not store.list_broker_order_records()
    service._stage_portfolio_alignment(NOW + timedelta(seconds=30))
    assert provider.requests == ["HKD/CNH"]
    assert len(store.list_proposals()) == 1


def test_operational_refresh_leaves_old_history_to_explicit_repair(tmp_path):
    store = SQLiteStore(tmp_path / "bars.db");store.initialize()
    old, today = date(2012, 1, 4), date(2026, 9, 24)
    store.upsert_price_bar("SPY", bar(old, "100"))
    store.upsert_price_bar("SPY", bar(today, "500").model_copy(update={"volume": 1000}))
    assert _next_missing_price_date(store,"SPY",today,repair_history=False) is None
    assert _next_missing_price_date(store,"SPY",today) == old
    store.upsert_price_bar("SPY", bar(today, "500"))
    assert _next_missing_price_date(store,"SPY",today,repair_history=False) == today


def test_error_callbacks_accept_both_sdk_versions():
    class Client:
        @compatible_ib_errors
        def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
            return reqId, errorCode, errorString, advancedOrderRejectJson
    c = Client()
    assert c.error(1, 200, "missing") == c.error(1, 1760000000000, 200, "missing") == (1,200,"missing","")
    assert c.error(1, 1760000000000, 201, "rejected", '{"reason":"risk"}') == (1,201,"rejected",'{"reason":"risk"}')


def test_cancellation_uses_current_sdk_order_cancel_contract():
    class Modern:
        def cancelOrder(self, orderId, orderCancel): self.sent = (orderId, orderCancel)
    class Legacy:
        def cancelOrder(self, orderId): self.sent = orderId
    current, old = Modern(), Legacy()
    cancel_ib_order(current, 123);cancel_ib_order(old, 123)
    assert current.sent[0] == old.sent == 123
    assert type(current.sent[1]).__name__ == "OrderCancel"


def test_current_sdk_serializes_twap_without_contacting_broker():
    from ibapi.client_utils import createOrderProto
    from systematic_trading.execution.broker import IBOrderSpec, _to_ib_order
    order = _to_ib_order(IBOrderSpec(action="BUY", order_type="LMT", quantity=10,
        limit_price=Decimal("100"), order_ref="st-test", algo_strategy="Twap",
        algo_params={"startTime": "20260925 09:30:00 US/Eastern", "endTime": "20260925 10:00:00 US/Eastern", "allowPastEndTime": "0"}))
    encoded = createOrderProto(order)
    assert encoded.totalQuantity == "10"
    assert encoded.algoStrategy == "Twap"
    assert encoded.SerializeToString()
