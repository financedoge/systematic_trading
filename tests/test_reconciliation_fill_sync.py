import pytest

from systematic_trading.config import AppSettings
from systematic_trading.execution.reconciliation import reconcile_ib_paper_account, submission_reconciliation_issues
from test_execution_history import Account, Executions, fill, sync
from test_execution_recovery import backend_store, isolated_postgres, sqlite_store


@pytest.mark.parametrize("already_synced", [False, True])
def test_reconciliation_persists_its_own_new_fill_batch(backend_store, tmp_path, already_synced):
    first = fill(cumulative_quantity=4)
    if already_synced:
        sync(backend_store, [first])
    # Another slice arrived after the periodic synchronization query.
    fresh = [fill("trade-c.01", 4, "110", 4, cumulative_quantity=10), first,
             fill("trade-b.01", 2, "110", 4, cumulative_quantity=6)]
    settings = AppSettings(data_dir=tmp_path)
    arguments = dict(settings=settings, store=backend_store, execution_client=Executions(fresh),
                     account_snapshot_client=Account(10), sync_new_fills=True)

    report = reconcile_ib_paper_account(**arguments)

    assert not report.has_breaks
    assert report.status == "matched"
    assert report.execution_issues == report.execution_sync_pending == []
    assert submission_reconciliation_issues(settings) == []
    record = backend_store.list_broker_order_records()[0]
    assert record.filled_quantity == 10
    assert len(record.execution_fills) == 3
    before = len(backend_store.list_pending_platform_events())
    repeated = reconcile_ib_paper_account(**arguments)
    assert not repeated.has_breaks
    assert len(backend_store.list_pending_platform_events()) == before


@pytest.mark.parametrize("bad_fill", [
    fill("trade-a.02", cumulative_quantity=4),
    fill("trade-b.01", 2, cumulative_quantity=8),
])
def test_synchronizing_reconciliation_keeps_real_conflicts_blocked(backend_store, tmp_path, bad_fill):
    sync(backend_store, [fill(cumulative_quantity=4)])
    settings = AppSettings(data_dir=tmp_path)
    arguments = dict(settings=settings, store=backend_store, execution_client=Executions([bad_fill]),
                     account_snapshot_client=Account(4), sync_new_fills=True)
    report = reconcile_ib_paper_account(**arguments)
    assert report.has_breaks
    assert report.status == "break"
    assert report.execution_issues
    assert not report.execution_sync_pending
    assert submission_reconciliation_issues(settings)
    record = backend_store.list_broker_order_records()[0]
    assert record.execution_sync_issue
    assert record.filled_quantity == 4
    with pytest.raises(ValueError, match="execution-history issues"):
        reconcile_ib_paper_account(**arguments, record_pnl_reset_baseline=True, confirm_paper_reset=True)
    arguments["execution_client"] = Executions([fill(cumulative_quantity=4)])
    assert reconcile_ib_paper_account(**arguments).execution_issues


def test_pending_sync_still_blocks_routing_and_reset(backend_store, tmp_path):
    sync(backend_store, [fill(cumulative_quantity=4)])
    settings = AppSettings(data_dir=tmp_path)
    arguments = dict(settings=settings, store=backend_store,
                     execution_client=Executions([fill("trade-b.01", 6, cumulative_quantity=10)]),
                     account_snapshot_client=Account(10))
    report = reconcile_ib_paper_account(**arguments)
    assert report.has_breaks and report.status == "sync_pending"
    assert not report.requires_operator_confirmation
    assert submission_reconciliation_issues(settings)
    with pytest.raises(ValueError, match="Synchronize pending"):
        reconcile_ib_paper_account(**arguments, record_pnl_reset_baseline=True, confirm_paper_reset=True)
    assert backend_store.latest_pnl_baseline() is None
