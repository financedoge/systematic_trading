"""Freeze a predeclared activity-concentration study and execute every trial in LEAN."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.config import AppSettings
from systematic_trading.daily_quality import captured_before_close, valid_ohlc
from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.bundle import freeze_bundle
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.lean.runner import run_bundle
from systematic_trading.live.trading_calendar import is_us_trading_day
from systematic_trading.market_data.store import ClickHouseMarketDataStore
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.research.flow_concentration import FlowConcentrationSpec


def extract_snapshot(protocol: dict, root: Path) -> tuple[dict, dict, dict]:
    store = ClickHouseMarketDataStore.from_settings(AppSettings())
    bars, source_rows, excluded, external = {}, {}, [], {}
    symbols = list(instruments_for_definition(current_sota_definition())) + ['URTH']
    for symbol in symbols:
        rows = store.client.query_daily_bars(symbol=symbol, start_date=protocol['start'] if symbol == 'URTH' else protocol['warmup_start'],
                                            end_date=protocol['end'], limit=50000)
        accepted = []
        source_rows[symbol] = rows
        for row in rows:
            day = date.fromisoformat(row['trade_date'])
            if not is_us_trading_day(day):
                excluded.append(dict(symbol=symbol, date=str(day), reason='not a US trading session',
                                     volume=row['volume'], source=row.get('source_name')))
                continue
            item = PriceBar.model_validate(row)
            if captured_before_close(row) or not valid_ohlc(item) or item.volume <= 0:
                if symbol == 'URTH':
                    excluded.append(dict(symbol=symbol, date=str(day), reason='invalid external benchmark observation; never filled',
                                         volume=row['volume'], source=row.get('source_name')))
                    continue
                raise ValueError(f'Invalid or unfinished true session: {symbol} {day}')
            accepted.append(item.model_dump(mode='json'))
        (external if symbol == 'URTH' else bars)[symbol] = accepted
    fx_rows = store.client.query_fx_rates(base_currency='USD', quote_currency='CNH',
        start_date=protocol['warmup_start'], end_date=protocol['end'])
    fx_by_date = {r['rate_date']: r for r in fx_rows}
    fx, lineage = {}, {}
    for row in next(iter(bars.values())):
        day = row['trade_date']
        prior = max((d for d in fx_by_date if d <= day), default=None)
        if prior is None or (date.fromisoformat(day)-date.fromisoformat(prior)).days > 7:
            raise ValueError('Missing/stale FX: '+day)
        fx[day] = str(fx_by_date[prior]['rate'])
        lineage[day] = dict(observation_date=prior, source=fx_by_date[prior].get('source_name'), carried=prior != day)
    provenance = dict(bars=source_rows, fx=fx_rows, fx_lineage=lineage, excluded_non_sessions=excluded,
        warning='Uncertified legacy adjusted prices/volume, fixed universe, CNH lineage may include CNY proxies; no net-flow/holdings data.',
        license='Local-provider research; no redistribution rights inferred')
    snapshot = root / 'snapshot'
    snapshot.mkdir()
    for name, value in [('bars', bars), ('fx', fx), ('provenance', provenance), ('external', external)]:
        write_json(snapshot / f'{name}.json', value)
    write_json(snapshot / 'manifest.json', {p.name: sha256(p) for p in snapshot.glob('*.json')})
    write_json(root / 'data_audit.json', dict(
        coverage={s: dict(rows=len(v), first=v[0]['trade_date'], last=v[-1]['trade_date']) for s, v in {**bars, **external}.items()},
        excluded_non_sessions=excluded, fx_carried=sum(r['carried'] for r in lineage.values()),
        net_flows_available=False, historical_holdings_available=False, sector_etfs_available=False))
    return bars, fx, provenance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=Path('config/flow-concentration-research-v1.json'))
    parser.add_argument('--resume', action='store_true', help='Use existing frozen protocol/snapshot; never overwrite completed runs')
    args = parser.parse_args()
    root = args.root.resolve()
    if args.resume:
        protocol = json.loads((root/'protocol.json').read_text())
        snapshot = root/'snapshot'
        for name, digest in json.loads((snapshot/'manifest.json').read_text()).items():
            if sha256(snapshot/name) != digest:
                raise ValueError('Snapshot changed: '+name)
        bars, fx, provenance = [json.loads((snapshot/f'{n}.json').read_text()) for n in ('bars', 'fx', 'provenance')]
    else:
        root.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(args.protocol, root/'protocol.json')
        protocol = json.loads((root/'protocol.json').read_text())
        # Freeze the orchestration source before observing any result.
        shutil.copyfile(__file__, root/'study_runner.py')
        bars, fx, provenance = extract_snapshot(protocol, root)
    trials = [(name, cfg, {}) for name, cfg in protocol['trials'].items()]
    for label, stress in protocol['stresses'].items():
        trials += [(f'{name}__{label}', protocol['trials'][name], stress) for name in ('sota', protocol['primary'])]
    progress = {}
    for name, cfg, stress in trials:
        bundle, output = root/'datasets'/name, root/'runs'/name
        if (output/'run.json').exists():
            receipt = json.loads((output/'run.json').read_text())
            if receipt['status'] != 'succeeded':
                raise ValueError(f'Failed immutable run requires investigation and a new study root: {name}')
            progress[name] = receipt['economic_sha256']
            continue
        if not bundle.exists():
            values = dict(start_date=protocol['start'], end_date=protocol['end'], warmup_start=protocol['warmup_start'],
                strategy='benchmark' if name == 'risk_parity' else 'sota_flow' if cfg is not None else 'sota',
                mode='shared' if name in ('sota', protocol['primary']) else 'targets', fx_policy='legacy_carry_max7',
                **stress)
            if cfg is not None:
                values['flow_overlay'] = FlowConcentrationSpec(**cfg).model_dump()
            print('FREEZE '+name, flush=True)
            freeze_bundle(root=bundle, bars=bars, fx=fx, provenance=provenance, spec_values=values)
        print('LEAN '+name, flush=True)
        receipt = run_bundle(bundle=bundle, output=output, image=protocol['image'])
        progress[name] = receipt['economic_sha256']
        write_json(root/'progress.json', dict(complete=False, passed=progress))
        print(f'PASS {name} ({receipt["elapsed_seconds"]:.1f}s)', flush=True)
    write_json(root/'progress.json', dict(complete=True, passed=progress))


if __name__ == '__main__':
    main()
