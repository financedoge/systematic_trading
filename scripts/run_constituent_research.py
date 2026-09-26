"""Freeze stock proxy features, archive them in ClickHouse, and run bounded LEAN trials."""
from __future__ import annotations

import argparse
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from systematic_trading.config import AppSettings
from systematic_trading.lean.bundle import freeze_bundle
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.lean.runner import run_bundle
from systematic_trading.live.trading_calendar import is_us_trading_day
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.market_data.golden import _sql_string
from systematic_trading.research.analytics_projection import observation
from systematic_trading.research.constituent_signals import ConstituentOverlaySpec, WINDOW, cohort_features, threshold
from analyze_underlying_sectors import compatible_name


def verify_manifest(root, name):
    for relative, expected in json.loads((root/name).read_text()).items():
        if sha256(root/relative) != expected:
            raise ValueError('Source changed: '+str(root/relative))


def build_features(protocol, output):
    source = Path(protocol['stock_root'])
    verify_manifest(source, 'data_manifest.json')
    snapshots = [json.loads(p.read_text()) for p in sorted((source/'holdings').glob('*.json'))]
    aliases = json.loads((source/'symbol_aliases.json').read_text())['aliases']
    for snap in snapshots:
        for row in snap['rows']:
            row['yahoo'] = aliases.get(row['ticker'], row['yahoo'])
    symbols = sorted({r['yahoo'] for s in snapshots for r in s['rows']})
    lookup = {s: i for i, s in enumerate(symbols)}
    first = date.fromisoformat(protocol.get('feature_history_start', '2018-10-01'))
    last = date.fromisoformat(protocol['end'])
    dates = [(first+timedelta(days=i)).isoformat() for i in range((last-first).days+1)
             if is_us_trading_day(first+timedelta(days=i))]
    day_index = {d: i for i, d in enumerate(dates)}
    c, v, a = [np.full((len(dates), len(symbols)), np.nan) for _ in range(3)]
    metadata = {}
    for symbol, col in lookup.items():
        meta = json.loads((source/'bars_metadata'/f'{symbol}.json').read_text())
        metadata[symbol] = meta
        if meta['status'] != 'ok':
            continue
        raw = json.loads((source/'bars_raw'/f'{symbol}.json').read_text())['chart']['result'][0]
        quote = raw['indicators']['quote'][0]
        adj = raw['indicators'].get('adjclose', [{}])[0].get('adjclose', [])
        seen = set()
        for i, stamp in enumerate(raw.get('timestamp', [])):
            day = datetime.fromtimestamp(stamp, UTC).date().isoformat()
            if day not in day_index:
                continue
            if day in seen:
                raise ValueError('Duplicate stock date')
            seen.add(day)
            j = day_index[day]
            c[j, col], v[j, col] = quote['close'][i], quote['volume'][i]
            a[j, col] = adj[i] if i < len(adj) else np.nan
    sectors = json.loads((source/'protocol.json').read_text())['sectors']
    features, exclusions = {}, []
    for lag in (45, 60):
        features[str(lag)] = {}
        activations = [(date.fromisoformat(s['as_of'])+timedelta(days=lag)).isoformat() for s in snapshots]
        for ix, snap in enumerate(snapshots):
            active = [j for j, d in enumerate(dates) if j >= WINDOW-1 and activations[ix] <= d
                      < (activations[ix+1] if ix+1 < len(snapshots) else '9999-12-31')
                      and (date.fromisoformat(d)-date.fromisoformat(snap['as_of'])).days <= protocol.get('max_snapshot_age_days', 100000)]
            if not active:
                continue
            merged = {}
            for ri, row in enumerate(snap['rows']):
                key = (row['yahoo'], row['sector']) if row['yahoo'] != '-' else ('unknown', ri)
                if key in merged:
                    merged[key]['market_value'] += row['market_value']
                else:
                    merged[key] = dict(row)
            rows = list(merged.values())
            ids = [lookup[r['yahoo']] for r in rows]
            weights = np.array([r['market_value'] for r in rows])
            sec = np.array([sectors.index(r['sector']) for r in rows])
            counts = {s: sum(r['yahoo'] == s for r in rows) for s in {r['yahoo'] for r in rows}}
            accepted = np.array([metadata[r['yahoo']]['status'] == 'ok'
                and compatible_name(r['name'], metadata[r['yahoo']].get('name'), r['ticker'])
                and counts[r['yahoo']] == 1 for r in rows])
            if lag == 45:
                exclusions += [dict(snapshot=snap['as_of'], ticker=r['ticker'], resolved=r['yahoo'])
                               for r, valid in zip(rows, accepted) if not valid]
            for j in active:
                ix_window = np.ix_(np.arange(j-WINDOW+1, j+1), ids)
                values = cohort_features(c[ix_window], v[ix_window], a[ix_window], sec, weights, accepted)
                features[str(lag)][dates[j]] = dict(known_through=dates[j], snapshot=snap['as_of'],
                    assumed_available=activations[ix], historical_available_at=None, **values)
        print(f'FEATURES lag{lag}: {len(features[str(lag)])} sessions', flush=True)
    etf = json.loads((Path(protocol['etf_snapshot'])/'bars.json').read_text())['SPY']
    for j in range(63, len(etf)):
        day = etf[j]['trade_date']
        for rows in features.values():
            if day in rows and rows[day]['scores'] is not None:
                rows[day]['scores']['price_control'] = threshold(float(etf[j]['close'])/float(etf[j-63]['close'])-1, .02)
    write_json(output/'features.json', features)
    write_json(output/'identity_exclusions.json', exclusions)
    audit = {lag: dict(sessions=len(rows), qualified95=sum(r['value_coverage'] >= .95 and r['name_coverage'] >= .7 for r in rows.values()),
             qualified90=sum(r['value_coverage'] >= .9 and r['name_coverage'] >= .7 for r in rows.values()),
             median_value_coverage=float(np.median([r['value_coverage'] for r in rows.values()])),
             median_name_coverage=float(np.median([r['name_coverage'] for r in rows.values()]))) for lag, rows in features.items()}
    write_json(output/'coverage.json', audit)
    print(json.dumps(audit), flush=True)
    return features


def archive(protocol, features, root):
    store = AnalyticsStore.from_settings(AppSettings())
    store.client.timeout_seconds = 120
    source_id = 'sector-research/'+Path(protocol['stock_root']).name+'/'
    original = store.latest(source_id+'dataset')
    if original is None:
        raise ValueError('Stock source dataset must already be published in ClickHouse')
    counts = store.query("SELECT family,count() AS n FROM analytics.current_observations WHERE workspace="
        +_sql_string(store.workspace)+" AND startsWith(source_id,"+_sql_string(source_id)
        +") GROUP BY family ORDER BY family")
    rows = [observation(lag+'/'+day, 'research_constituent_signal', 'SPY', dict(holdings_lag_days=int(lag), **row), day)
            for lag, series in features.items() for day, row in series.items()]
    version = digest(encode(dict(features=sha256(root/'features.json'), protocol=sha256(root/'protocol.json'),
        source_manifest=sha256(Path(protocol['stock_root'])/'data_manifest.json'),
        code=sha256(root/'feature_source.py'))))
    documents = [dict(point_key=name, media_type='application/json', payload=(root/name).read_text())
                 for name in ('protocol.json', 'coverage.json')]
    destination = 'constituent-research/'+root.name+'/features'
    changed = store.publish(destination, version, rows, documents, provenance=dict(research_only=True,
        original_dataset=original['version'], root=str(root), historical_available_at=None))
    receipt = dict(source_id=destination, version=version, changed=changed, observations=len(rows), documents=len(documents),
        source_counts=counts, original_dataset_version=original['version'],
        verification='Exact payload SHA256 readback before publication', workspace=store.workspace)
    write_json(root/'clickhouse_receipt.json', receipt)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=Path('config/constituent-research-v1.json'))
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--features-only', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    if not args.resume:
        root.mkdir(parents=True, exist_ok=False)
        shutil.copyfile(args.protocol, root/'protocol.json')
        shutil.copyfile(__file__, root/'study_runner.py')
        shutil.copyfile(Path(__file__).resolve().parents[1]/'src/systematic_trading/research/constituent_signals.py', root/'feature_source.py')
        shutil.copyfile(Path(__file__).with_name('analyze_underlying_sectors.py'), root/'identity_source.py')
        protocol = json.loads((root/'protocol.json').read_text())
        features = build_features(protocol, root)
        archive(protocol, features, root)
        write_json(root/'input_manifest.json', {p.name: sha256(p) for p in root.iterdir() if p.is_file()})
    else:
        verify_manifest(root, 'input_manifest.json')
        protocol = json.loads((root/'protocol.json').read_text())
        features = json.loads((root/'features.json').read_text())
    if args.features_only:
        return
    snapshot = Path(protocol['etf_snapshot'])
    verify_manifest(snapshot, 'manifest.json')
    bars, fx, provenance = [json.loads((snapshot/f'{name}.json').read_text()) for name in ('bars', 'fx', 'provenance')]
    bars = {s: [r for r in rows if protocol['warmup_start'] <= r['trade_date'] <= protocol['end']] for s, rows in bars.items()}
    provenance = dict(etf_snapshot=str(snapshot), etf_manifest=sha256(snapshot/'manifest.json'),
        constituents_manifest=sha256(root/'input_manifest.json'), constituents_archive=json.loads((root/'clickhouse_receipt.json').read_text()),
        limitations=protocol.get('interpretation',
            'Historical vintages uncertified; ITOT proxy only for SPY; missing delisted histories; modeled45/60day publication lag.'))
    trials = [(name, spec, {}) for name, spec in protocol['trials'].items()]
    base_tree_models = json.loads((root/'base_tree_models.json').read_text()) if protocol.get('base_tree_model_schedule') else None
    for label, stress in protocol['stresses'].items():
        trials += [(name+'__'+label, protocol['trials'][name], stress) for name in protocol.get('stress_trials', ('sota', protocol['primary']))]
    passed = {}
    for name, cfg, stress in trials:
        trial_features = features
        feature_file = protocol.get('feature_sets', {}).get(name.split('__')[0])
        if feature_file:
            trial_features = json.loads((root/feature_file).read_text())
        bundle, output = root/'datasets'/name, root/'runs'/name
        if (output/'run.json').exists():
            receipt = json.loads((output/'run.json').read_text())
            if receipt['status'] != 'succeeded':
                raise ValueError('Investigate failed immutable run: '+name)
        else:
            if not bundle.exists():
                spec = dict(start_date=protocol['start'], end_date=protocol['end'], warmup_start=protocol['warmup_start'],
                    strategy='sota_constituents' if cfg is not None else 'sota', mode='shared' if name in protocol.get('shared_trials', ('sota', protocol['primary'])) else 'targets',
                    fx_policy='legacy_carry_max7', **stress)
                if base_tree_models is not None:
                    spec['base_tree_model_schedule'] = True
                    spec['limitations'] = [protocol['interpretation'], protocol['coverage'],
                        'CNH adjusted units; prior-open FX; modeled costs/fills; uncertified historical data vintages.']
                if cfg is not None:
                    spec['constituent_overlay'] = ConstituentOverlaySpec(**cfg).model_dump()
                print('FREEZE '+name, flush=True)
                freeze_bundle(root=bundle, bars=bars, fx=fx, provenance=provenance, spec_values=spec,
                              constituent_features=trial_features if cfg is not None else None, base_tree_models=base_tree_models)
            print('LEAN '+name, flush=True)
            receipt = run_bundle(bundle=bundle, output=output, image=protocol['image'])
            print(f'PASS {name} {receipt["elapsed_seconds"]:.1f}s', flush=True)
        passed[name] = receipt['economic_sha256']
        write_json(root/'progress.json', dict(complete=False, passed=passed))
    write_json(root/'progress.json', dict(complete=True, passed=passed))


if __name__ == '__main__':
    main()
