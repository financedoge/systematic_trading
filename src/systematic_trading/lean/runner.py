from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from systematic_trading.lean.contracts import verify_bundle, sha256, write_json


def compare_outputs(reference: dict, actual: dict, spec) -> dict:
    differences = []
    for item in (reference, actual):
        if not item.get('complete'):
            raise ValueError('Incomplete engine output')
    left, right = reference['decisions'], actual['decisions']
    if left.keys() != right.keys():
        differences.append('Decision dates differ')
    for day in sorted(left.keys() & right.keys()):
        a, b = left[day], right[day]
        for field in ('signal_session', 'known_through'):
            if a[field] != b[field]:
                differences.append(f'{day}: {field} differs')
        aw = {t['symbol']: Decimal(t['target_weight']) for t in a['targets']}
        bw = {t['symbol']: Decimal(t['target_weight']) for t in b['targets']}
        if aw.keys() != bw.keys() or any(abs(aw[s] - bw[s]) > Decimal(spec.target_tolerance) for s in aw.keys() & bw.keys()):
            differences.append(f'{day}: target weights differ')
    def fill_key(row):
        return row['date'], row['symbol'], row['quantity']
    a, b = sorted(reference['fills'], key=fill_key), sorted(actual['fills'], key=fill_key)
    if [fill_key(x) for x in a] != [fill_key(x) for x in b]:
        differences.append('Fill dates/symbols/integer quantities differ')
    else:
        for x, y in zip(a, b):
            for field in ('price', 'fee'):
                if abs(Decimal(x[field]) - Decimal(y[field])) > Decimal(spec.money_tolerance_cnh):
                    differences.append(f'{fill_key(x)}: {field} differs')
    if [r['date'] for r in reference['nav']] != [r['date'] for r in actual['nav']]:
        differences.append('Valuation sessions differ')
    else:
        for x, y in zip(reference['nav'], actual['nav']):
            for field in ('nav', 'cash'):
                if abs(Decimal(x[field]) - Decimal(y[field])) > Decimal(spec.money_tolerance_cnh):
                    differences.append(f"{x['date']}: {field} differs by {Decimal(y[field]) - Decimal(x[field])} CNH")
    if reference['final_positions'] != actual['final_positions']:
        differences.append('Final positions differ')
    normalized = {key: actual[key] for key in ['decisions', 'nav', 'final_positions']}
    normalized['fills'] = b
    digest = hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()
    return {'passed': not differences, 'differences': differences, 'economic_sha256': digest,
            'nav_count': len(actual['nav']), 'fill_count': len(b), 'decision_count': len(right),
            'promotion_eligible': False, 'limitations': spec.limitations}


def docker_command(*, image: str, bundle: Path, output: Path, name: str, memory='4g', cpus='2') -> list[str]:
    if not re.fullmatch(r'quantconnect/lean@sha256:[0-9a-f]{64}', image):
        raise ValueError('A pinned quantconnect/lean image digest is required')
    for path in (bundle, output):
        if ',' in str(path):
            raise ValueError('Docker mount paths cannot contain commas')
    return ['docker', 'run', '--rm', '--name', name, '--network', 'none', '--read-only',
            '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--pids-limit', '512',
            '--memory', memory, '--cpus', cpus, '--tmpfs', '/tmp:rw,size=512m',
            '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'DOTNET_CLI_HOME=/tmp',
            '--mount', f'type=bind,src={bundle.resolve()},dst=/input,readonly',
            '--mount', f'type=bind,src={output.resolve()},dst=/output',
            image, '--config', '/output/config.json']


def lean_config() -> dict:
    return {
        'environment': 'backtesting', 'live-mode': False, 'algorithm-type-name': 'FrozenPortfolioAlgorithm',
        'algorithm-language': 'Python', 'algorithm-location': '/input/source/systematic_trading/lean/algorithm.py',
        'data-folder': '/Lean/Data', 'results-destination-folder': '/output', 'object-store-root': '/output/storage',
        'log-handler': 'QuantConnect.Logging.ConsoleLogHandler', 'messaging-handler': 'QuantConnect.Messaging.Messaging',
        'job-queue-handler': 'QuantConnect.Queues.JobQueue', 'api-handler': 'QuantConnect.Api.Api',
        'map-file-provider': 'QuantConnect.Data.Auxiliary.LocalDiskMapFileProvider',
        'factor-file-provider': 'QuantConnect.Data.Auxiliary.LocalDiskFactorFileProvider',
        'data-provider': 'QuantConnect.Lean.Engine.DataFeeds.DefaultDataProvider',
        'object-store': 'QuantConnect.Lean.Engine.Storage.LocalObjectStore',
        'data-aggregator': 'QuantConnect.Lean.Engine.DataFeeds.AggregationManager',
        'setup-handler': 'QuantConnect.Lean.Engine.Setup.BacktestingSetupHandler',
        'result-handler': 'QuantConnect.Lean.Engine.Results.BacktestingResultHandler',
        'data-feed-handler': 'QuantConnect.Lean.Engine.DataFeeds.FileSystemDataFeed',
        'real-time-handler': 'QuantConnect.Lean.Engine.RealTime.BacktestingRealTimeHandler',
        'history-provider': ['QuantConnect.Lean.Engine.HistoricalData.SubscriptionDataReaderHistoryProvider'],
        'transaction-handler': 'QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler',
        'close-automatically': True, 'debugging': False, 'maximum-data-points-per-chart-series': 10000,
    }


def run_bundle(*, bundle: Path, output: Path, image: str, timeout_seconds=900) -> dict:
    verified = verify_bundle(bundle)
    if output.exists():
        raise FileExistsError(f'Run artifacts are immutable: {output}')
    output.mkdir(parents=True)
    name = 'st-lean-' + uuid4().hex[:12]
    receipt = {'run_id': name, 'status': 'running', 'image': image, 'bundle': str(bundle.resolve()),
               'manifest_sha256': sha256(bundle / 'manifest.json'), 'promotion_eligible': False}
    write_json(output / 'run.json', receipt)
    write_json(output / 'config.json', lean_config())
    started = time.perf_counter()
    try:
        command = docker_command(image=image, bundle=bundle, output=output, name=name)
        # The oracle needs the interpreter/runtime, not inherited app credentials.
        runtime_keys = {'PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'SYSTEMDRIVE', 'COMSPEC',
                        'TEMP', 'TMP', 'LANG', 'LC_ALL'}
        environment = {key: value for key, value in os.environ.items() if key.upper() in runtime_keys}
        environment['PYTHONPATH'] = str(bundle.resolve() / 'source')
        environment['PYTHONDONTWRITEBYTECODE'] = '1'
        environment['PYTHONUTF8'] = '1'
        with (output / 'reference.log').open('w', encoding='utf-8') as log:
            subprocess.run([sys.executable, '-B', '-m', 'systematic_trading.lean.reference', str(bundle.resolve()),
                            str(output.resolve() / 'reference.json')], cwd=output, env=environment,
                           stdout=log, stderr=subprocess.STDOUT, timeout=timeout_seconds, check=True)
        receipt['reference_wall_seconds'] = time.perf_counter() - started
        inspected = subprocess.run(['docker', 'image', 'inspect', image], capture_output=True,
                                   text=True, timeout=30, check=True)
        metadata = json.loads(inspected.stdout)[0]
        receipt['engine'] = {'image_id': metadata['Id'], 'repo_digests': metadata.get('RepoDigests'),
                             'labels': metadata.get('Config', {}).get('Labels', {})}
        lean_started = time.perf_counter()
        with (output / 'lean.log').open('w', encoding='utf-8') as log:
            subprocess.run(command,
                           stdout=log, stderr=subprocess.STDOUT, timeout=timeout_seconds, check=True)
        receipt['lean_wall_seconds'] = time.perf_counter() - lean_started
        actual = json.loads((output / 'economic.json').read_text(encoding='utf-8'))
        reference = json.loads((output / 'reference.json').read_text(encoding='utf-8'))
        parity = compare_outputs(reference, actual, verified['spec'])
        write_json(output / 'parity.json', parity)
        if not parity['passed']:
            raise ValueError(f"LEAN parity failed: {len(parity['differences'])} discrepancies")
        verify_bundle(bundle)
        receipt.update(status='succeeded', economic_sha256=parity['economic_sha256'])
    except BaseException as exc:
        receipt.update(status='failed', error=f'{type(exc).__name__}: {exc}')
        try:
            subprocess.run(['docker', 'rm', '-f', name], capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as cleanup_error:
            receipt['cleanup_error'] = str(cleanup_error)
        raise
    finally:
        receipt['elapsed_seconds'] = time.perf_counter() - started
        receipt['artifacts'] = {p.relative_to(output).as_posix(): sha256(p) for p in output.rglob('*')
                                if p.is_file() and p != output / 'run.json'}
        write_json(output / 'run.json', receipt)
    return receipt
