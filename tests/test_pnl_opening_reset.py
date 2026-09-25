import json
from datetime import UTC, date, datetime, timedelta

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain import PnLBaseline, PnLSnapshot
from systematic_trading.domain.enums import BrokerOrderStatus
from systematic_trading.execution.reconciliation import IBPaperReconciliationReport, latest_reconciliation_report_path
from systematic_trading.live.pnl_reset import reset_paper_pnl_before_session
from systematic_trading.live.sota import AccountPositionInput
from systematic_trading.web.api import _active_pnl_snapshots
from test_execution_history import store, fill, sync


@pytest.fixture
def opening(tmp_path, store):
    settings = AppSettings(data_dir=tmp_path)
    stamp = datetime(2026,8,3,12,tzinfo=UTC)
    source = tmp_path/'opening.json'
    source.write_text(json.dumps(dict(as_of='2026-08-03',captured_at=stamp.isoformat(),cash=[dict(currency='USD',amount='10000')],positions=[])))
    report = IBPaperReconciliationReport(checked_at=stamp,managed_accounts=['DU123'],account_snapshot_path=str(source),
        broker_cash=[dict(currency='USD',amount='10000')],ib_position_count=0,ib_fill_count=0,
        local_order_history_count=0,local_order_count=0,local_filled_order_count=0)
    path = tmp_path/'opening-report.json'; path.write_text(report.model_dump_json())
    sync(store,[fill(cumulative_quantity=4)])
    current = report.model_copy(update={'checked_at':datetime.now(UTC),'ib_position_count':1,
        'broker_positions':[AccountPositionInput(symbol='SPY',quantity=4)]})
    # Validate through the model, just as a real reconciliation file is read.
    current = IBPaperReconciliationReport.model_validate(current.model_dump())
    latest=latest_reconciliation_report_path(settings);latest.parent.mkdir(parents=True)
    latest.write_text(current.model_dump_json())
    return settings,path,source,store


def reset(opening):
    settings,path,_,store=opening
    return reset_paper_pnl_before_session(settings=settings,store=store,trade_date=date(2026,8,3),
        opening_report_path=path,operator='Test',reason='Paper account reset confirmed')


def test_reset_retains_execution_ledger_and_audits_observed_opening_cash(opening):
    settings,path,source,store=opening
    before=[r.model_dump() for r in store.list_broker_order_records()]
    baseline=reset(opening)
    assert baseline.cutoff_at == datetime(2026,8,3,3,59,59,999999,tzinfo=UTC)
    assert baseline.filled_trade_count == 0 and baseline.open_lots == []
    assert [r.model_dump() for r in store.list_broker_order_records()] == before
    evidence=json.loads(__import__('pathlib').Path(baseline.account_snapshot_path).read_text())
    assert evidence['as_of']=='2026-07-31'
    assert evidence['captured_at']=='2026-08-03T12:00:00Z'
    assert evidence['observed_snapshot_path']==str(source)
    audit=json.loads((settings.data_dir/'live'/f'pnl_opening_reset_{baseline.baseline_id}.json').read_text())
    assert audit['status']=='applied' and audit['retained_execution_count']==1
    with pytest.raises(ValueError,match='already covers'): reset(opening)


@pytest.mark.parametrize('invalid',['late','positions','ledger_issue','wrong_holdings'])
def test_invalid_opening_or_ledger_cannot_reset(opening,invalid):
    settings,path,source,store=opening
    if invalid in {'late','positions'}:
        data=json.loads(source.read_text())
        data.update({'captured_at':'2026-08-03T23:00:00Z'} if invalid=='late' else {'positions':[dict(symbol='SPY',quantity=1)]})
        source.write_text(json.dumps(data))
    elif invalid=='ledger_issue':
        record=store.list_broker_order_records()[0]
        store.save_broker_order_record(record.model_copy(update={'execution_sync_issue':'Conflict'}))
    else:
        latest=latest_reconciliation_report_path(settings)
        data=json.loads(latest.read_text());data['broker_positions'][0]['quantity']=5;latest.write_text(json.dumps(data))
    with pytest.raises(ValueError):reset(opening)
    assert store.latest_pnl_baseline() is None


def test_active_history_excludes_experiments_without_deleting_them(store):
    cutoff=datetime(2026,8,3,4,tzinfo=UTC)
    store.save_pnl_baseline(PnLBaseline(cutoff_at=cutoff,account_reset_at=cutoff))
    old=PnLSnapshot(as_of=cutoff+timedelta(hours=12),total_pnl_cnh='999')
    active=PnLSnapshot(as_of=cutoff+timedelta(hours=12),baseline_cutoff_at=cutoff,total_pnl_cnh='10')
    store.save_pnl_snapshot(old);store.save_pnl_snapshot(active)
    assert [s.snapshot_id for s in _active_pnl_snapshots(store,100)] == [active.snapshot_id]
    assert len(store.list_pnl_snapshots())==2
