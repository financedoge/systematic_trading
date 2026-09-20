from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain import ProposalReasoning, TradeProposal
from systematic_trading.live.account_snapshot import AccountSummaryRow
from systematic_trading.live.management_service import TradingManagementService, _scheduled_rebalance_due
from systematic_trading.storage.sqlite import SQLiteStore
from systematic_trading.web.api import _proposal_with_route_order_type


@pytest.mark.parametrize("decision, due, execution", [
    (date(2026, 5, 20), False, date(2026, 5, 21)),
    (date(2026, 5, 22), False, date(2026, 5, 26)),
    (date(2026, 5, 29), True, date(2026, 6, 1)),
    (date(2026, 7, 31), True, date(2026, 8, 3)),
    (date(2026, 8, 31), True, date(2026, 9, 1)),
    (date(2026, 12, 31), True, date(2027, 1, 4)),
    (date(2026, 5, 31), False, date(2026, 6, 1)),
])
def test_monthly_cadence_and_route_calendar(decision, due, execution):
    assert _scheduled_rebalance_due(decision) is due
    proposal = TradeProposal(as_of=decision, sleeve="test", summary="test", reasoning=ProposalReasoning(summary="test"))
    assert _proposal_with_route_order_type(proposal, None, AppSettings()).intended_trade_date == execution


def test_unknown_registered_scheduler_is_not_treated_as_daily(monkeypatch):
    monkeypatch.setattr("systematic_trading.live.management_service.current_sota_definition",
                        lambda: SimpleNamespace(scheduler="unknown"))
    with pytest.raises(ValueError, match="does not support"):
        _scheduled_rebalance_due(date(2026, 8, 31))


@pytest.mark.parametrize("reconciled", [True, False])
def test_midmonth_eod_obeys_reconciliation_without_staging(tmp_path, monkeypatch, reconciled):
    store = SQLiteStore(tmp_path / "daily.db")
    store.initialize()
    day = date(2026, 5, 20)

    class Account:
        def fetch(self, profile):
            return [AccountSummaryRow(account="DU123", tag="TotalCashValue", value="1000", currency="USD")], [], ["DU123"]

    service = TradingManagementService(settings=AppSettings(data_dir=tmp_path, automation_queue_rebalance=True),
                                       store=store, account_snapshot_client=Account())
    service._status = service._status.model_copy(update={
        "pending_eod_date": day, "last_reconciliation_status": "matched" if reconciled else "break",
        "last_eod_pnl_date": None if reconciled else day,
    })
    monkeypatch.setattr(service, "_sync_executions", lambda now: None)
    monkeypatch.setattr(service, "_refresh_market_data", lambda day: SimpleNamespace(latest_bar_date=day, latest_fx_date=day))

    def forbidden(**kwargs):
        raise AssertionError("midmonth proposal generation must not run")

    monkeypatch.setattr("systematic_trading.live.management_service.build_sota_live_rebalance_plan", forbidden)
    service._run_eod(datetime(2026, 5, 20, 21, tzinfo=UTC))
    if reconciled:
        assert service._status.last_eod_date == day
        assert service._status.last_eod_pnl_date == day
        assert service._status.pending_eod_date is None
        assert service._status.next_eod_attempt_at is None
    else:
        assert service._status.last_eod_date is None
        assert service._status.pending_eod_date == day
        assert service._status.next_eod_attempt_at is not None
    assert store.list_proposals() == []
