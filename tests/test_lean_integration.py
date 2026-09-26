import copy
import json
from datetime import date, timedelta
from pathlib import Path

import pytest

from systematic_trading.lean.contracts import BacktestRunSpec, verify_bundle, write_json, sha256
from systematic_trading.lean.runner import compare_outputs, docker_command, lean_config
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.live.trading_calendar import is_us_trading_day
from systematic_trading.research import current_sota_definition, instruments_for_definition
from test_execution_recovery import isolated_postgres


def spec(**updates):
    return BacktestRunSpec(start_date='2025-01-02', end_date='2025-12-31', warmup_start='2023-01-01',
                          strategy_hash='fixture', source_hash='fixture', repository_commit='fixture', **updates)


def output():
    return dict(complete=True, decisions={'2025-01-02': dict(signal_session='2025-01-02', known_through='2024-12-31',
                targets=[dict(symbol='SPY', target_weight='0.9')])},
                fills=[dict(date='2025-01-02', symbol='SPY', quantity=2, price='100', fee='1')],
                nav=[dict(date='2025-01-02', nav='1000', cash='799')], final_positions={'SPY': 2})


@pytest.mark.parametrize('kind', ['date', 'quantity', 'weight', 'cash', 'fee', 'partial'])
def test_parity_rejects_every_unexplained_difference(kind):
    a, b = output(), output()
    if kind == 'date': b['nav'][0]['date'] = '2025-01-03'
    if kind == 'quantity': b['fills'][0]['quantity'] = 1
    if kind == 'weight': b['decisions']['2025-01-02']['targets'][0]['target_weight'] = '0.91'
    if kind == 'cash': b['nav'][0]['cash'] = '798'
    if kind == 'fee': b['fills'][0]['fee'] = '2'
    if kind == 'partial':
        b['complete'] = False
        with pytest.raises(ValueError, match='Incomplete'): compare_outputs(a, b, spec())
        return
    assert not compare_outputs(a, b, spec())['passed']


def test_offline_container_has_no_secrets_and_requires_digest(tmp_path):
    with pytest.raises(ValueError, match='pinned'):
        docker_command(image='quantconnect/lean:latest', bundle=tmp_path, output=tmp_path, name='test')
    command = docker_command(image='quantconnect/lean@sha256:'+'a'*64, bundle=tmp_path, output=tmp_path, name='test')
    assert command[command.index('--network') + 1] == 'none'
    assert '--read-only' in command and '--memory' in command and '--cpus' in command
    assert not any('.env' in value or '7497' in value or 'password' in value for value in command)
    assert lean_config()['live-mode'] is False


def test_frozen_inputs_reject_corruption_and_extra_files(tmp_path):
    write_json(tmp_path / 'spec.json', spec().model_dump())
    write_json(tmp_path / 'manifest.json', {'schema_version':1, 'files':{'spec.json':sha256(tmp_path / 'spec.json')}})
    verify_bundle(tmp_path)
    (tmp_path / 'extra.py').write_text('tampered')
    with pytest.raises(ValueError, match='inventory'): verify_bundle(tmp_path)
    (tmp_path / 'spec.json').write_text('{}')
    with pytest.raises(ValueError, match='hash mismatch'): verify_bundle(tmp_path)


def test_shared_sota_targets_are_invariant_to_future_prices():
    histories = {s: [] for s in instruments_for_definition(current_sota_definition())}
    start = date(2023, 1, 3)
    for i in range(620):
        day = start + timedelta(days=i)
        if not is_us_trading_day(day): continue
        for index, rows in enumerate(histories.values()):
            price = str(100 + i * (index + 1) / 100 + (i % 9) / 10)
            rows.append(dict(trade_date=day.isoformat(), open=price, high=price, low=price, close=price, volume=100000+i))
    decision = date(2024, 5, 1)
    original = targets_for_day(histories, decision)
    changed = copy.deepcopy(histories)
    for rows in changed.values():
        for row in rows:
            if row['trade_date'] >= str(decision):
                row.update(open='99999', high='99999', low='99999', close='99999', volume=99999999)
    assert targets_for_day(changed, decision) == original
    with pytest.raises(ValueError, match='warmup'):
        targets_for_day(histories, date(2023, 2, 1))


@pytest.mark.parametrize('failure', ['nonzero', 'timeout', 'missing-output', 'parity'])
def test_runner_marks_engine_failure_and_retains_logs(tmp_path, monkeypatch, failure):
    import subprocess
    from types import SimpleNamespace
    from systematic_trading.lean import runner
    bundle, target = tmp_path / 'bundle', tmp_path / 'run'
    bundle.mkdir()
    write_json(bundle / 'spec.json', spec().model_dump())
    write_json(bundle / 'manifest.json', {'schema_version':1, 'files':{'spec.json':sha256(bundle / 'spec.json')}})
    def failing(args, **kwargs):
        if args[0] == 'docker' and args[1] == 'rm': return None
        if args[0] != 'docker':
            write_json(target / 'reference.json', output())
            return None
        if args[1] == 'image':
            return SimpleNamespace(stdout=json.dumps([{'Id': 'fixture'}]))
        if failure == 'nonzero': raise subprocess.CalledProcessError(1, args)
        if failure == 'timeout': raise subprocess.TimeoutExpired(args, 1)
        if failure == 'parity':
            actual = output()
            actual['nav'][0]['cash'] = '1'
            write_json(target / 'economic.json', actual)
    monkeypatch.setattr(runner.subprocess, 'run', failing)
    with pytest.raises((subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, ValueError)):
        runner.run_bundle(bundle=bundle, output=target, image='quantconnect/lean@sha256:'+'a'*64)
    assert json.loads((target / 'run.json').read_text())['status'] == 'failed'
    assert (target / 'reference.log').exists()
    assert (target / 'lean.log').exists()
    if failure == 'parity':
        assert not json.loads((target / 'parity.json').read_text())['passed']


def test_registry_rejects_failed_or_tampered_evidence(tmp_path):
    from systematic_trading.lean.registry import register_run
    write_json(tmp_path / 'run.json', {'status': 'failed', 'promotion_eligible': False})
    with pytest.raises(ValueError, match='completed'):
        register_run(None, tmp_path)


def test_same_day_filing_not_visible_to_opening_selection(monkeypatch):
    from systematic_trading.backtest import stock_replacement as module
    from types import SimpleNamespace
    captured = {}
    def screen(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(reports=[])
    monkeypatch.setattr(module, 'build_quantitative_framework_screen', screen)
    monkeypatch.setattr(module, 'build_market_feature_snapshots', lambda *args, **kwargs: {})
    module._effective_stock_selection(selected_symbols=[], stock_instruments={}, stock_bars_by_symbol={},
        trade_date=date(2026, 9, 25), trade_dates=[date(2026, 9, 24), date(2026, 9, 25)],
        config=SimpleNamespace(stock_selection_mode='quantitative_point_in_time', dynamic_top_n=1),
        static_reports_by_symbol={}, fundamentals_by_symbol={})
    assert captured['as_of'] == date(2026, 9, 24)


@pytest.mark.parametrize('mutation', ['missing-session', 'duplicate-session', 'zero-volume', 'fx-gap', 'bad-ohlc'])
def test_export_refuses_common_missing_sessions_and_bad_economics(tmp_path, monkeypatch, mutation):
    from systematic_trading.lean import fixtures
    from systematic_trading.lean.bundle import freeze_bundle
    def altered(**kwargs):
        if mutation == 'missing-session':
            for rows in kwargs['bars'].values(): rows.pop(10)
        if mutation == 'duplicate-session':
            for rows in kwargs['bars'].values(): rows.insert(10, rows[10])
        if mutation == 'zero-volume': kwargs['bars']['SPY'][10]['volume'] = 0
        if mutation == 'bad-ohlc': kwargs['bars']['SPY'][10]['high'] = '1'
        if mutation == 'fx-gap': kwargs['fx'].pop(next(iter(kwargs['fx'])))
        return freeze_bundle(**kwargs)
    monkeypatch.setattr(fixtures, 'freeze_bundle', altered)
    with pytest.raises(ValueError, match='sessions|OHLC|FX'):
        fixtures.make_fixture_bundle(tmp_path / 'invalid')
    assert not (tmp_path / 'invalid').exists()


def test_research_registry_is_append_only_and_cannot_promote(isolated_postgres):
    import psycopg
    from psycopg import sql
    from uuid import uuid4
    name = 'lean_' + uuid4().hex[:12]
    with psycopg.connect(**isolated_postgres, dbname='postgres', autocommit=True) as db:
        db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    with psycopg.connect(**isolated_postgres, dbname=name, autocommit=True) as db:
        db.execute('CREATE SCHEMA ops')
        for migration in ('003_lean_research_runs.sql', '004_lean_append_only.sql'):
            db.execute((Path('deploy/postgres/migrations') / migration).read_text(encoding='utf-8'))
        db.execute("INSERT INTO ops.lean_research_runs VALUES ('fixture',now(),'m','r','p',false,'{}')")
        for query in ("UPDATE ops.lean_research_runs SET receipt_sha256='tampered'",
                      'DELETE FROM ops.lean_research_runs', 'TRUNCATE ops.lean_research_runs'):
            with pytest.raises(psycopg.errors.RaiseException, match='append-only'):
                db.execute(query)
        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute("INSERT INTO ops.lean_research_runs VALUES ('promoted',now(),'m','r','p',true,'{}')")
        assert db.execute('SELECT count(*) FROM ops.lean_research_runs').fetchone()[0] == 1


@pytest.mark.parametrize('mutation', ['source', 'output', 'inventory', 'parity'])
def test_registry_detects_evidence_changes_before_database_access(tmp_path, mutation):
    from systematic_trading.lean.registry import register_run
    bundle, result = tmp_path / 'bundle', tmp_path / 'result'
    bundle.mkdir()
    result.mkdir()
    write_json(bundle / 'spec.json', spec().model_dump())
    write_json(bundle / 'manifest.json', {'schema_version': 1, 'files': {'spec.json': sha256(bundle / 'spec.json')}})
    for name in ('reference.json', 'economic.json', 'config.json', 'lean.log', 'resources.json'):
        write_json(result / name, {})
    write_json(result / 'parity.json', {'passed': mutation != 'parity'})
    receipt = dict(status='succeeded', promotion_eligible=False, bundle=str(bundle),
                   manifest_sha256=sha256(bundle / 'manifest.json'),
                   artifacts={p.name: sha256(p) for p in result.iterdir()})
    write_json(result / 'run.json', receipt)
    if mutation == 'source': write_json(bundle / 'spec.json', {})
    if mutation == 'output': write_json(result / 'economic.json', {'modified': True})
    if mutation == 'inventory': write_json(result / 'extra.json', {})
    with pytest.raises(ValueError, match='hash mismatch|artifact|Parity'):
        register_run(None, result)


def test_shared_analytics_does_not_import_database_or_broker_adapters():
    import subprocess
    import sys
    script = '''
import importlib.abc
import sys
class BlockAdapters(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'psycopg', 'ibapi'}:
            raise AssertionError('Offline analytics tried to import ' + fullname)
sys.meta_path.insert(0, BlockAdapters())
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.lean.reference import run_reference
assert not any(name.startswith('systematic_trading.execution') for name in sys.modules)
'''
    subprocess.run([sys.executable, '-c', script], check=True, capture_output=True, timeout=30)
