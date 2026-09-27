"""Regressions for the cross-application connection audit (C01-C17)."""
import gzip
import json
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain import FXRate, PriceBar, PnLBaseline
from systematic_trading.domain.enums import Currency, BrokerOrderStatus, OrderEnvironment
from systematic_trading.domain.events import CashEventPayload, CashEventRecordedEvent, EventSource
from systematic_trading.live.pnl import build_dashboard_pnl_snapshot, build_reference_pnl_snapshot, build_pnl_baseline
from systematic_trading.portfolio.context import portfolio_context, session_end
from systematic_trading.portfolio.economic import economic_bridge, record_cash_event
from systematic_trading.portfolio.revision import accounting_revision
from systematic_trading.live.sota import LiveAccountSnapshotInput
from systematic_trading.web.api import dashboard_execution_quality
from systematic_trading.web.shell import with_app_shell
from systematic_trading.lean.contracts import sha256
from test_execution_history import store, fill, sync


def marks(store, day=date(2026,8,3), price="120", fx="7"):
    store.upsert_price_bar("SPY", PriceBar(trade_date=day, open=price, high=price, low=price, close=price, volume=100))
    if fx:
        store.upsert_fx_rate(FXRate(base_currency=Currency.USD, rate_date=day, rate=fx))


def test_compaction_keeps_both_ledgers_and_episode(store):
    marks(store)
    sync(store, [fill(quantity=10, price="101")])
    before = build_dashboard_pnl_snapshot(store, as_of=date(2026,8,3))
    ref = build_reference_pnl_snapshot(store, as_of=date(2026,8,3))
    assert before.total_pnl_cnh - ref.total_pnl_cnh == -70
    store.save_pnl_baseline(build_pnl_baseline(store, cutoff_date=date(2026,8,3)))
    after = build_dashboard_pnl_snapshot(store, as_of=date(2026,8,3))
    reference_after = build_reference_pnl_snapshot(store, as_of=date(2026,8,3))
    assert after.total_pnl_cnh == before.total_pnl_cnh
    assert reference_after.total_pnl_cnh == ref.total_pnl_cnh
    assert after.portfolio_context == before.portfolio_context


def test_historical_query_chooses_earlier_checkpoint_and_rejects_previous_episode(store):
    marks(store)
    sync(store, [fill(quantity=10, price="101")])
    store.save_pnl_baseline(build_pnl_baseline(store, cutoff_date=date(2026,8,4)))
    assert build_dashboard_pnl_snapshot(store, as_of=date(2026,8,3)).total_pnl_cnh == 1330
    # A reset is a new episode; old dates cannot borrow its opening positions.
    base=PnLBaseline(cutoff_at=session_end(date(2026,8,5)), account_reset_at=session_end(date(2026,8,5)))
    store.save_pnl_baseline(base)
    with pytest.raises(ValueError, match="precedes"):
        build_dashboard_pnl_snapshot(store, as_of=date(2026,8,3))


def test_missing_fill_fx_and_stale_marks_are_incomplete(store):
    marks(store, fx=None)
    sync(store, [fill(quantity=10)])
    assert not build_dashboard_pnl_snapshot(store, as_of=date(2026,8,3)).valuation_complete
    marks(store)
    assert not build_dashboard_pnl_snapshot(store, as_of=date(2026,8,4)).valuation_complete
    assert build_dashboard_pnl_snapshot(store, as_of=date(2026,8,3)).valuation_complete


def test_ny_session_scope_splits_executions_and_misses(store):
    cutoff=session_end(date(2026,8,3))
    store.save_pnl_baseline(PnLBaseline(cutoff_at=cutoff, account_reset_at=cutoff))
    marks(store, date(2026,8,4))
    # First slice is August 3 in New York even though its UTC date is August 4.
    sync(store, [fill(quantity=4, filled_at=cutoff-timedelta(minutes=1)),
                 fill("b.01",quantity=6,filled_at=cutoff+timedelta(hours=10))])
    old=store.list_broker_order_records()[0]
    for suffix,day in (("before",date(2026,8,3)),("after",date(2026,8,4))):
        store.save_broker_order_record(old.model_copy(update=dict(local_order_id=suffix, order_index=1 if suffix=="before" else 2,
            status=BrokerOrderStatus.MISSED, filled_quantity=0, execution_fills=[],
            order=old.order.model_copy(update={"intended_trade_date":day}),
            updated_at=cutoff+timedelta(hours=20))))
    req=SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(store=store)))
    result=dashboard_execution_quality(req, as_of=date(2026,8,4), history_limit=10)
    assert result.filled_trade_count == result.filled_order_count == 1
    assert result.rows[0].filled_quantity == 6
    assert result.missed_order_count == 1
    assert result.execution_rows_gain_cnh + result.execution_reconciliation_difference_cnh == result.execution_gain_cnh
    assert result.portfolio_context["start_date"] == "2026-08-04"


def test_financial_revision_changes_for_fill_and_mark_not_poll(store):
    marks(store)
    before=accounting_revision(store,date(2026,8,3))
    record=store.list_broker_order_records()[0]
    store.save_broker_order_record(record.model_copy(update={"updated_at":datetime.now(UTC), "message":"Polled"}))
    assert accounting_revision(store,date(2026,8,3)) == before
    sync(store,[fill(quantity=10)])
    filled=accounting_revision(store,date(2026,8,3))
    assert filled != before
    marks(store,price="121")
    assert accounting_revision(store,date(2026,8,3)) != filled


def test_historical_snapshot_selection_rejects_backdated_capture(tmp_path):
    from systematic_trading.live.management_service import _latest_stored_account_snapshot
    folder=tmp_path/"live/account_snapshots";folder.mkdir(parents=True)
    (folder/"bad.json").write_text(json.dumps(dict(as_of="2026-08-03",captured_at="2026-08-04T18:00:00Z", cash=[], positions=[])))
    assert _latest_stored_account_snapshot(AppSettings(data_dir=tmp_path),date(2026,8,3)) is None
    (folder/"good.json").write_text(json.dumps(dict(as_of="2026-08-03",captured_at="2026-08-03T20:00:00Z", cash=[], positions=[])))
    assert _latest_stored_account_snapshot(AppSettings(data_dir=tmp_path),date(2026,8,3))[0].endswith("good.json")


def test_account_chart_preserves_opening_anchor_and_rejects_backdating(store, tmp_path, monkeypatch):
    from systematic_trading.web import api
    cutoff=session_end(date(2026,8,3))
    store.save_pnl_baseline(PnLBaseline(cutoff_at=cutoff,account_reset_at=cutoff,account_snapshot_path="opening.json"))
    opening=LiveAccountSnapshotInput(as_of=date(2026,8,3),captured_at=cutoff+timedelta(hours=6),
        cash=[dict(currency="CNH",amount=1000)],observation_kind="opening_reference")
    backdated=opening.model_copy(update={"cash":[opening.cash[0].model_copy(update={"amount":Decimal(9000)})],
        "observation_kind":"broker_live", "captured_at":cutoff+timedelta(days=1)})
    bad_day=backdated.model_copy(update={"as_of":date(2026,8,4),"captured_at":cutoff+timedelta(days=2)})
    monkeypatch.setattr(api,"_account_snapshots",lambda *a:[(tmp_path/"opening.json",opening),
        (tmp_path/"bad-opening.json",backdated),(tmp_path/"bad-day.json",bad_day)])
    points,_,start=api._account_nav_points(AppSettings(),store,[])
    assert points==[(date(2026,8,3),Decimal(1000))] and start==date(2026,8,4)


def test_cash_events_are_idempotent_scoped_and_bridge_explains_flow(store):
    cutoff=session_end(date(2026,7,31))
    store.save_pnl_baseline(PnLBaseline(cutoff_at=cutoff,account_reset_at=cutoff,account_id="DU123"))
    context=portfolio_context(store)
    event=CashEventRecordedEvent(occurred_at=datetime(2026,8,3,15,tzinfo=UTC),
        source=EventSource(service="statement-import",environment=OrderEnvironment.PAPER),
        payload=CashEventPayload(portfolio_episode_id=context.episode_id,account_id="DU123",external_id="deposit1",
            kind="external_flow",currency=Currency.CNH,amount=100,source_ref="statement",source_sha256="a"*64))
    assert record_cash_event(store,event).event_id == record_cash_event(store,event).event_id
    with pytest.raises(ValueError,match="Conflicting"):
        record_cash_event(store,event.model_copy(update={"payload":event.payload.model_copy(update={"amount":Decimal(101)})}))
    opening=LiveAccountSnapshotInput(as_of=date(2026,7,31),cash=[dict(currency="CNH",amount=1000)])
    result=economic_bridge(store,opening,Decimal(1000),Decimal(1100),Decimal(0),date(2026,8,3))
    assert result["reconciled"] and result["net_economic_pnl_cnh"] == 0
    assert result["flow_adjusted_return"] == 0
    result=economic_bridge(store,opening,Decimal(1000),Decimal(1090),Decimal(0),date(2026,8,3))
    assert not result["reconciled"] and result["unexplained_cnh"] == -10


def test_handoff_prerequisites_fail_before_restore_on_missing_files(tmp_path):
    from systematic_trading.storage.dependencies import verify_dependencies
    with pytest.raises(ValueError,match="prerequisite"):
        verify_dependencies(AppSettings(),dict(files={str(tmp_path/"absent"):"a"*64}))


def test_all_workspaces_share_idempotent_shell():
    for page in ("trading","strategies","system","market"):
        body=with_app_shell('<html><head></head><body><header>old</header><main>data</main></body></html>',page)
        assert 'aria-label="Application"' in body and 'id="application-shell-style"' in body
        assert body.count('aria-current="page"') == 1
        assert with_app_shell(body,page) == body


def test_operations_health_exposes_stale_completion():
    from systematic_trading.research.analytics_service import AnalyticsService
    service=AnalyticsService(AppSettings(analytics_refresh_seconds=60),None,None)
    service._thread=service._account_thread=SimpleNamespace(is_alive=lambda:True)
    assert service.status()["operations_stale"]
    service._status["operations_completed_at"]=(datetime.now(UTC)-timedelta(seconds=301)).isoformat()
    assert service.status()["operations_stale"]
    service._status["operations_completed_at"]=datetime.now(UTC).isoformat()
    assert not service.status()["operations_stale"]


def test_governed_parent_pins_unchanged_symbols_and_rejects_tampering(tmp_path):
    from systematic_trading.research.governed_inputs import GovernedInputs
    parent=tmp_path/"parent"; (parent/"bars").mkdir(parents=True)
    source=parent/"bars/X.jsonl.gz"
    with gzip.open(source,'wt') as out: out.write(json.dumps(dict(trade_date="2026-08-03"))+"\n")
    (parent/"manifest.json").write_text(json.dumps({"bars/X.jsonl.gz":sha256(source)}))
    child=tmp_path/"child";child.mkdir()
    (child/"parent.json").write_text(json.dumps(dict(root=str(parent),batch=sha256(parent/"manifest.json"))))
    (child/"manifest.json").write_text(json.dumps({"parent.json":sha256(child/"parent.json")}))
    reader=GovernedInputs(child,sha256(child/"manifest.json"))
    assert len(reader.rows("X","2026-01-01","2026-12-31"))==1
    source.write_bytes(b"changed")
    with pytest.raises(ValueError,match="Changed"):
        reader.rows("X","2026-01-01","2026-12-31")


def test_governed_refresh_rejects_revisions_and_truncation():
    from systematic_trading.research.governed_refresh import validate_revision
    rows=[dict(trade_date=str(date(2026,1,1)+timedelta(days=i)),adjusted_close=100+i) for i in range(65)]
    audit=dict(status="audited_with_limitations", name="Example ETF", internal_gaps=0)
    validate_revision("X", rows, [dict(r,adjusted_close=r["adjusted_close"]*.9) for r in rows], audit,audit,rows[-1]["trade_date"])
    with pytest.raises(ValueError,match="truncate"):
        validate_revision("X",rows,rows[1:],audit,audit,rows[-1]["trade_date"])
    changed=[dict(r) for r in rows];changed[10]["adjusted_close"]*=2
    with pytest.raises(ValueError,match="revision"):
        validate_revision("X",rows,changed,audit,audit,rows[-1]["trade_date"])
