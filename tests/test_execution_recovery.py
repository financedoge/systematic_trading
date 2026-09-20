import json
import os
import runpy
import socket
import subprocess
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from systematic_trading.config import AppSettings
from systematic_trading.domain import PnLBaseline
from systematic_trading.domain.enums import BrokerOrderStatus, OrderEnvironment
from systematic_trading.execution.fills import execution_state_token
from systematic_trading.execution.recovery import ExecutionRecoveryRequest, preview_execution_recovery
from systematic_trading.execution.reconciliation import IBPaperReconciliationReport, submission_reconciliation_issues
from systematic_trading.storage.postgres import PostgresConnectionConfig, PostgresStore
from test_execution_history import fill, sync, store as sqlite_store


@pytest.fixture(scope="session")
def isolated_postgres(tmp_path_factory):
    configured = os.environ.get("ST_TEST_POSTGRES_BIN")
    if not configured:
        pytest.skip("Set ST_TEST_POSTGRES_BIN to run against a disposable Postgres cluster.")
    binaries = Path(configured)
    root = tmp_path_factory.mktemp("execution-recovery-postgres")
    password = uuid4().hex
    password_file = root / "password.txt"
    password_file.write_text(password, encoding="ascii")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    suffix = ".exe" if os.name == "nt" else ""
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    def command(program, *args):
        # On Windows the background server inherits pg_ctl's pipe handles;
        # communicate() would wait for EOF until the server exits. Use a file.
        output_path = root / f"{program}.log"
        with output_path.open("w", encoding="utf-8") as output:
            result = subprocess.run([str(binaries / (program + suffix)), *map(str, args)],
                                    stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                    creationflags=flags, timeout=60)
        if result.returncode:
            raise RuntimeError(f"Isolated Postgres {program} failed: {output_path.read_text(encoding='utf-8', errors='replace')}")

    data = root / "data"
    try:
        command("initdb", "-D", data, "-U", "postgres", "--auth=scram-sha-256", "--pwfile", password_file,
                "--no-locale", "--encoding=UTF8")
    finally:
        password_file.unlink(missing_ok=True)
    try:
        command("pg_ctl", "-D", data, "-l", root / "server.log", "-o", f"-h 127.0.0.1 -p {port}", "-w", "start")
        yield dict(host="127.0.0.1", port=port, user="postgres", password=password)
    finally:
        if (data / "postmaster.pid").exists():
            command("pg_ctl", "-D", data, "-m", "fast", "-w", "stop")


@pytest.fixture(params=["sqlite", "postgres"])
def backend_store(request, sqlite_store):
    if request.param == "sqlite":
        return sqlite_store
    kwargs = request.getfixturevalue("isolated_postgres")
    database = "recovery_" + uuid4().hex[:12]
    with psycopg.connect(**kwargs, dbname="postgres", autocommit=True) as connection:
        connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
    with psycopg.connect(**kwargs, dbname=database) as connection:
        connection.execute(Path("deploy/postgres/migrations/001_initial_transactional_store.sql").read_text())
    store = PostgresStore(PostgresConnectionConfig(database=database, **kwargs))
    store.initialize()
    store.save_proposal(sqlite_store.get_proposal("proposal"))
    store.save_broker_order_record(sqlite_store.list_broker_order_records()[0])
    return store


def request_for(*fills):
    return ExecutionRecoveryRequest(local_order_id="local", operator="test-operator", reason="Verified broker export",
                                    account="DU123", fills=list(fills or [fill(cumulative_quantity=4)]))


def preview(store, request):
    return preview_execution_recovery(store.list_broker_order_records()[0], request, store.latest_pnl_baseline())


def test_recovery_is_audited_idempotent_and_survives_stale_updates(backend_store):
    store = backend_store
    sync(store, [fill(cumulative_quantity=4)])
    sync(store, [fill("trade-a.02", price="101", cumulative_quantity=4)])
    stale = store.list_broker_order_records()[0]
    request = request_for(fill("trade-a.02", price="101", cumulative_quantity=4))
    plan = preview(store, request)
    assert store.list_broker_order_records()[0] == stale
    updated = store.recover_broker_executions(request, review_token=plan.review_token)
    assert updated.average_fill_price == Decimal(101)
    assert updated.execution_sync_issue is None
    assert updated.execution_recoveries[0].previous_fills[0].average_price == Decimal(100)
    assert updated.execution_recoveries[0].reason == request.reason
    store.save_broker_order_record(stale)
    assert store.list_broker_order_records()[0].execution_sync_issue is None
    sync(store, [fill(cumulative_quantity=4)])  # old broker revision is still visible in history
    assert store.list_broker_order_records()[0].execution_sync_issue is None
    assert store.list_broker_order_records()[0].average_fill_price == Decimal(101)
    with pytest.raises(ValueError, match="generate a new preview"):
        store.recover_broker_executions(request, review_token=plan.review_token)


def test_recovery_rejects_stale_order_evidence_and_baseline(backend_store):
    store = backend_store
    request = request_for()
    plan = preview(store, request)
    changed = request.model_copy(update={"reason": "different reason"})
    with pytest.raises(ValueError, match="changed"):
        store.recover_broker_executions(changed, review_token=plan.review_token)
    sync(store, [fill(cumulative_quantity=4)])
    with pytest.raises(ValueError, match="changed"):
        store.recover_broker_executions(request, review_token=plan.review_token)
    plan = preview(store, request)
    store.save_pnl_baseline(PnLBaseline(cutoff_at=datetime(2026, 8, 1, tzinfo=UTC)))
    with pytest.raises(ValueError, match="changed"):
        store.recover_broker_executions(request, review_token=plan.review_token)


@pytest.mark.parametrize("bad, message", [
    (request_for(fill(cumulative_quantity=None)), "cumulative"),
    (request_for(fill(account="DU999", cumulative_quantity=4)), "expected account"),
    (request_for(fill(quantity=11, cumulative_quantity=11)), "exceeds"),
    (request_for(fill(quantity=4, cumulative_quantity=6)), "gap or overlap"),
    (request_for(fill(filled_at=datetime(2099, 1, 1, tzinfo=UTC), cumulative_quantity=4)), "non-future"),
])
def test_invalid_recovery_evidence_never_writes(backend_store, bad, message):
    before = backend_store.list_broker_order_records()[0]
    with pytest.raises(ValueError, match=message):
        preview(backend_store, bad)
    assert backend_store.list_broker_order_records()[0] == before


def test_existing_baseline_and_live_orders_cannot_be_recovered(backend_store):
    store = backend_store
    store.save_pnl_baseline(PnLBaseline(cutoff_at=datetime(2026, 8, 4, tzinfo=UTC)))
    with pytest.raises(ValueError, match="historical rebuild"):
        preview(store, request_for())
    record = store.list_broker_order_records()[0].model_copy(update={"environment": OrderEnvironment.LIVE})
    with pytest.raises(ValueError, match="paper orders"):
        preview_execution_recovery(record, request_for(), None)


def test_recovery_cannot_drop_history_rewrite_ids_or_change_accounts(backend_store):
    store = backend_store
    sync(store, [fill(cumulative_quantity=4)])
    with pytest.raises(ValueError, match="omits"):
        preview(store, request_for(fill("other.01", cumulative_quantity=4)))
    with pytest.raises(ValueError, match="cannot be rewritten"):
        preview(store, request_for(fill(price="102", cumulative_quantity=4)))
    with pytest.raises(ValueError, match="cannot change"):
        preview(store, request_for().model_copy(update={"account": "DU999"}))


def test_stale_pnl_calculation_cannot_commit_after_recovery(backend_store):
    store = backend_store
    baseline = PnLBaseline(cutoff_at=datetime(2026, 8, 4, tzinfo=UTC),
                           execution_state_token=execution_state_token(store.list_broker_order_records()))
    request = request_for()
    store.recover_broker_executions(request, review_token=preview(store, request).review_token)
    with pytest.raises(ValueError, match="rebuild the baseline"):
        store.save_pnl_baseline(baseline)
    assert store.latest_pnl_baseline() is None


def test_concurrent_recoveries_only_commit_once(backend_store):
    store = backend_store
    request = request_for()
    token = preview(store, request).review_token
    barrier = Barrier(2)

    def apply():
        barrier.wait(timeout=5)
        try:
            store.recover_broker_executions(request, review_token=token)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(apply) for _ in range(2)]
        assert sorted(f.result(timeout=15) for f in futures) == [False, True]
    assert len(store.list_broker_order_records()[0].execution_recoveries) == 1


def test_concurrent_order_reservations_have_one_winner(backend_store):
    store = backend_store
    store.save_proposal(store.get_proposal("proposal").model_copy(update={"proposal_id": "new-proposal"}))
    template = store.list_broker_order_records()[0]
    barrier = Barrier(2)

    def reserve(index):
        candidate = template.model_copy(update={
            "local_order_id": f"claim-{index}", "proposal_id": "new-proposal", "order_ref": "st-new-proposal-00",
            "broker_order_id": 20 + index, "status": BrokerOrderStatus.PENDING_SUBMIT,
        })
        barrier.wait(timeout=5)
        return store.reserve_broker_order_record(candidate)

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(reserve, [0, 1])) == [False, True]
    assert len(store.list_broker_order_records("new-proposal")) == 1


def test_concurrent_fill_writers_accumulate_on_each_backend(backend_store):
    barrier = Barrier(2)

    def accumulate(execution):
        barrier.wait(timeout=5)
        return backend_store.apply_broker_execution_fills("local", [execution])

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(accumulate, [fill(), fill("trade-b.01", 6, "110", 4)]))
    record = backend_store.list_broker_order_records()[0]
    assert record.filled_quantity == 10
    assert record.average_fill_price == Decimal(106)


def test_recovery_rolls_back_with_outbox_failure(backend_store, monkeypatch):
    store = backend_store
    request = request_for()
    token = preview(store, request).review_token
    original = store.list_broker_order_records()[0]

    def fail(*args, **kwargs):
        raise RuntimeError("outbox failure")

    monkeypatch.setattr(type(store).__module__ + "._insert_platform_event", fail)
    with pytest.raises(RuntimeError, match="outbox failure"):
        store.recover_broker_executions(request, review_token=token)
    assert store.list_broker_order_records()[0] == original


def test_new_successful_reconciliation_required_after_recovery(backend_store, tmp_path):
    checked_at = datetime.now(UTC)
    request = request_for()
    recovered = backend_store.recover_broker_executions(request, review_token=preview(backend_store, request).review_token)
    settings = AppSettings(data_dir=tmp_path)
    report = IBPaperReconciliationReport(checked_at=checked_at, local_order_history_count=1, local_order_count=1,
                                        local_filled_order_count=1, ib_fill_count=1, ib_position_count=1)
    path = tmp_path / "reconciliation" / "ib_paper_reconciliation_latest.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(report.model_dump_json())
    required_after = recovered.execution_recoveries[-1].recovered_at
    assert "after execution recovery" in submission_reconciliation_issues(settings, required_after=required_after)[0]
    report.checked_at = datetime.now(UTC)
    path.write_text(report.model_dump_json())
    assert submission_reconciliation_issues(settings, required_after=required_after) == []


def test_cli_previews_without_mutation_and_requires_review_token(sqlite_store, tmp_path, capsys):
    main = runpy.run_path("scripts/recover_ib_paper_executions.py")["main"]
    evidence = tmp_path / "evidence.json"
    evidence.write_text(request_for().model_dump_json())
    args = ["--database", str(sqlite_store.database_path), "--evidence", str(evidence)]
    before = sqlite_store.database_path.read_bytes()
    main(args)
    token = json.loads(capsys.readouterr().out)["review_token"]
    assert sqlite_store.database_path.read_bytes() == before
    with pytest.raises(SystemExit):
        main([*args, "--apply"])
    main([*args, "--apply", "--review-token", token])
    assert sqlite_store.list_broker_order_records()[0].execution_recoveries


def test_cli_refuses_ignored_sqlite_path_before_connecting_to_postgres(tmp_path, monkeypatch, capsys):
    main = runpy.run_path("scripts/recover_ib_paper_executions.py")["main"]
    evidence = tmp_path / "evidence.json"
    evidence.write_text(request_for().model_dump_json())
    monkeypatch.setenv("ST_TRANSACTIONAL_STORE_BACKEND", "postgres")

    def forbidden(*args, **kwargs):
        raise AssertionError("must refuse an ambiguous database before connecting")

    monkeypatch.setitem(main.__globals__, "create_transactional_store", forbidden)
    with pytest.raises(SystemExit) as error:
        main(["--database", str(tmp_path / "intended.db"), "--evidence", str(evidence)])
    assert error.value.code == 2
    assert "cannot redirect Postgres" in capsys.readouterr().err
