"""Freeze audited prices, backward stock features, separate labels and causal trees."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, timedelta
import json
from pathlib import Path
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from analyze_underlying_sectors import compatible_name
from prepare_tenyear_constituent_study import fit_base_models
from prepare_constituent_integration import fit_models
from run_constituent_research import verify_manifest
from systematic_trading.config import AppSettings
from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.market_data.golden import _sql_string
from systematic_trading.research import current_sota_definition, instantiate_overlays
from systematic_trading.research.analytics_projection import observation
from systematic_trading.research.chronological_tree import select_base_tree
from systematic_trading.research.constituent_integration import residual_inputs
from systematic_trading.research.constituent_signals import WINDOW, threshold
from systematic_trading.research.governed_inputs import GovernedInputs, diagnostic_features, etf_bar, fixed_cohort_return
from systematic_trading.signals.base import SignalContext
from systematic_trading.signals.library import compute_signal_features


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def fit_all(bars, features):
    bars = {s: [PriceBar.model_validate(r) for r in rows] for s, rows in bars.items()}
    days = [str(r.trade_date) for r in bars['SPY']]
    starts = [d for i, d in enumerate(days) if i >= 253 and d[:7] != days[i-1][:7]]
    prices = {s: {str(r.trade_date): float(r.close) for r in rows} for s, rows in bars.items()}
    records = []
    for start, end in zip(starts, starts[1:]):
        known, label_end = days[days.index(start)-1], days[days.index(end)-1]
        context = SignalContext(as_of=date.fromisoformat(start), instruments={}, bars_by_symbol=bars, trade_dates=[])
        returns = {s: prices[s][label_end]/prices[s][known]-1 for s in bars}
        mean = sum(returns.values())/len(returns)
        for symbol in bars:
            records.append(dict(symbol=symbol, signal_session=start, known_through=known, label_end=label_end,
                inputs=compute_signal_features(symbol=symbol, context=context), relative_return=returns[symbol]-mean))
    template = instantiate_overlays(current_sota_definition())[1].model
    base = fit_base_models(records, template, range(2014, 2027))
    residuals = []
    for r in records:
        if r['symbol'] != 'SPY' or r['known_through'] < min(base):
            continue
        row = features['45'].get(r['known_through'])
        if not row or row['scores'] is None or row['value_coverage'] < .95 or row['name_coverage'] < .70:
            continue
        forecast = select_base_tree(base, r['known_through']).predict(r['inputs'])
        residuals.append(dict(known_through=r['known_through'], label_end=r['label_end'],
            inputs=residual_inputs(r['inputs'], forecast, row), relative_return=r['relative_return'],
            residual=r['relative_return']-forecast, label_role='training_only_never_runtime_feature'))
    return base, fit_models(residuals, range(2015, 2027)), records, residuals


def prepare(protocol_path):
    protocol = read(protocol_path)
    root, source = Path(protocol['root']), Path(protocol['stock_root'])
    root.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(protocol_path, root/'protocol.json')
    # Definitions are frozen before any features or candidate results are computed.
    for name in ('prepare_audited_research.py', 'run_audited_research.py'):
        shutil.copyfile(Path(__file__).with_name(name), root/name)
    shutil.copytree(Path(__file__).resolve().parents[1]/'src/systematic_trading', root/'preparation_source', ignore=shutil.ignore_patterns('__pycache__'))
    governed = GovernedInputs(Path(protocol['governed_root']), protocol['batch'])
    store = AnalyticsStore.from_settings(AppSettings()); store.client.timeout_seconds = 120
    committed = store.query('SELECT version FROM analytics.publications FINAL WHERE workspace='+_sql_string(store.workspace)
        +" AND source_id='governance/catalog' AND version="+_sql_string(protocol['batch']))
    if not committed:
        raise ValueError('Governed batch is not published')
    verify_manifest(source, 'data_manifest.json')
    prior = Path(protocol['prior_root']); verify_manifest(prior, 'input_manifest.json')
    old_snapshot = Path(protocol['old_snapshot']); verify_manifest(old_snapshot, 'manifest.json')
    old_bars = read(old_snapshot/'bars.json')
    calendar = read(governed.checked('calendar.json'))['sessions']
    days = [d for d in calendar if '2011-01-03' <= d <= protocol['end']]
    day_index = {d: i for i, d in enumerate(days)}
    trade_days = [d for d in days if d >= protocol['warmup_start']]
    etfs = {}
    for symbol in old_bars:
        rows = governed.rows(symbol, protocol['warmup_start'], protocol['end'])
        if [r['trade_date'] for r in rows] != trade_days:
            raise ValueError('ETF calendar incomplete: ' + symbol)
        etfs[symbol] = [etf_bar(r) for r in rows]
    write_json(root/'bars.json', etfs)
    shutil.copyfile(old_snapshot/'fx.json', root/'fx.json')
    if any(d not in read(root/'fx.json') for d in trade_days):
        raise ValueError('The unchanged FX scenario has missing sessions')
    snapshots = [read(p) for p in sorted((source/'holdings').glob('*.json'))]
    aliases = read(source/'symbol_aliases.json')['aliases']
    for snap in snapshots:
        for row in snap['rows']:
            row['yahoo'] = aliases.get(row['ticker'], row['yahoo'])
    symbols = sorted({r['yahoo'] for s in snapshots for r in s['rows']})
    symbol_index = {s: i for i, s in enumerate(symbols)}
    c, v, a = [np.full((len(days), len(symbols)), np.nan) for _ in range(3)]
    audits, coverage = {}, []
    for col, symbol in enumerate(symbols):
        audits[symbol] = governed.audit(symbol)
        rows = governed.rows(symbol, days[0], days[-1])
        for row in rows:
            if row['trade_date'] in day_index:
                j = day_index[row['trade_date']]
                c[j, col], v[j, col], a[j, col] = [float(row[k]) if row[k] is not None else np.nan for k in ('raw_close','raw_volume','adjusted_close')]
        coverage.append(dict(symbol=symbol, governed_rows=len(rows), raw_complete_rows=int((np.isfinite(c[:, col]) & np.isfinite(v[:, col])).sum()),
            identity_boundary=audits[symbol].get('listing_boundary'), name=audits[symbol].get('name')))
        if col % 100 == 0:
            print('READ GOVERNED',col,len(symbols),flush=True)
    # Source rows were previously fully hash verified in CH; compare current per-symbol counts too.
    counts = store.query('SELECT symbol,count() n FROM market_data.governed_daily FINAL WHERE workspace='+_sql_string(store.workspace)
        +' AND batch='+_sql_string(protocol['batch'])+" AND trade_date>='"+days[0]+"' AND trade_date<='"+days[-1]+"' GROUP BY symbol")
    counts = {r['symbol']: r['n'] for r in counts}
    if any(counts.get(r['symbol'],0) != r['governed_rows'] for r in coverage):
        raise ValueError('Local governed series and ClickHouse row counts differ')
    write_json(root/'stock_coverage.json', coverage)
    sectors = read(source/'protocol.json')['sectors']
    features, labels, exclusions = {}, {}, []
    for lag in (45, 60):
        out = features[str(lag)] = {}
        activations = [(date.fromisoformat(s['as_of'])+timedelta(days=lag)).isoformat() for s in snapshots]
        for ix, snap in enumerate(snapshots):
            rows = snap['rows']; counts = Counter(r['yahoo'] for r in rows)
            ids = [symbol_index[r['yahoo']] for r in rows]
            weights = np.array([r['market_value'] for r in rows]); sec = np.array([sectors.index(r['sector']) for r in rows])
            accepted = np.array([counts[r['yahoo']] == 1 and compatible_name(r['name'], audits[r['yahoo']].get('name'), r['ticker']) for r in rows])
            if lag == 45:
                exclusions += [dict(snapshot=snap['as_of'],ticker=r['ticker'],provider_name=audits[r['yahoo']].get('name')) for r,valid in zip(rows,accepted) if not valid]
            for j, day in enumerate(days):
                if j < WINDOW-1 or not activations[ix] <= day < (activations[ix+1] if ix+1 < len(snapshots) else '9999'):
                    continue
                if (date.fromisoformat(day)-date.fromisoformat(snap['as_of'])).days > 140:
                    continue
                select = np.ix_(np.arange(j-WINDOW+1,j+1), ids)
                values, valid = diagnostic_features(c[select], v[select], a[select], sec, weights, accepted)
                out[day] = dict(known_through=day,snapshot=snap['as_of'],assumed_available=activations[ix],historical_available_at=None,**values)
                if lag == 45 and values['scores'] is not None and values['value_coverage'] >= .95 and values['name_coverage'] >= .70:
                    forward = {}
                    for horizon in (20,60,120):
                        if j+horizon < len(days):
                            forward[str(horizon)] = dict(label_end=days[j+horizon],
                                basket=fixed_cohort_return(a[j,ids],a[j+horizon,ids],weights,valid),
                                sectors={sector:fixed_cohort_return(a[j,ids],a[j+horizon,ids],weights,valid & (sec == k)) for k,sector in enumerate(sectors)})
                    labels[day] = forward
        print('FEATURES',lag,len(out),flush=True)
    spy = etfs['SPY']
    for i in range(63,len(spy)):
        for series in features.values():
            row = series.get(spy[i]['trade_date'])
            if row and row['scores'] is not None:
                row['scores']['price_control'] = threshold(float(spy[i]['close'])/float(spy[i-63]['close'])-1,.02)
    base, models, training, residuals = fit_all(etfs, features)
    features['integration_models'] = models
    for name, value in [('features',features),('labels',labels),('identity_exclusions',exclusions),('base_tree_models',base),
                        ('models',models),('base_training_records',training),('training_records',residuals),('used_governed_files',governed.used)]:
        write_json(root/(name+'.json'),value)
    shutil.copyfile(prior/'features.json',root/'old_features.json')
    yearly = {lag:{str(y):dict(sessions=len(part),qualified95=sum(r['scores'] is not None and r['value_coverage']>=.95 and r['name_coverage']>=.7 for r in part),
        mean_value=float(np.mean([r['value_coverage'] for r in part]))) for y in range(2012,2027) if (part:=[r for d,r in features[lag].items() if d.startswith(str(y))])} for lag in ('45','60')}
    write_json(root/'coverage.json',yearly)
    provenance = dict(batch=protocol['batch'],governed_manifest=sha256(governed.root/'manifest.json'),
        used_governed_files=governed.used,holdings_manifest=sha256(source/'data_manifest.json'),
        old_snapshot_manifest=sha256(old_snapshot/'manifest.json'),old_snapshot_provenance=read(old_snapshot/'provenance.json'),
        etf_basis=protocol['etf_basis'],constituent_basis=protocol['constituent_basis'],limitations=protocol['limitations'])
    write_json(root/'provenance.json',provenance)
    observations = [observation(lag+'/'+d,'research_constituent_signal','SPY',dict(holdings_lag_days=int(lag),**r),d) for lag in ('45','60') for d,r in features[lag].items()]
    observations += [observation('base/'+d,'research_constituent_tree_model','BASE',r,d) for d,r in base.items()]
    observations += [observation(kind+'/'+d,'research_constituent_tree_model','SPY',r,d) for kind,series in models.items() for d,r in series.items()]
    observations += [observation('base_label/'+r['symbol']+'/'+r['known_through'],'research_constituent_training_label',r['symbol'],r,r['label_end']) for r in training]
    observations += [observation('residual_label/'+r['known_through'],'research_constituent_training_label','SPY',r,r['label_end']) for r in residuals]
    observations += [observation(d+'/'+h,'research_governed_forward_label','IVV_cohort',dict(signal_date=d,horizon=int(h),**r),r['label_end']) for d,hs in labels.items() for h,r in hs.items()]
    names = ['protocol.json','provenance.json','coverage.json','stock_coverage.json','identity_exclusions.json','models.json','base_tree_models.json']
    files = {p.relative_to(root).as_posix():sha256(p) for p in root.rglob('*') if p.is_file()}
    version = digest(encode(files)); source_id = 'constituent-research/'+root.name+'/features'
    store.publish(source_id,version,observations,[dict(point_key=n,media_type='application/json',payload=(root/n).read_text(encoding='utf8')) for n in names],
        provenance=dict(research_only=True,governed_batch=protocol['batch'],historical_available_at=None,files=files))
    write_json(root/'clickhouse_receipt.json',dict(source_id=source_id,version=version,observations=len(observations),documents=len(names),verification='Exact SHA256 readback before publication'))
    write_json(root/'input_manifest.json',{p.relative_to(root).as_posix():sha256(p) for p in root.rglob('*') if p.is_file()})
    print('READY',root,json.dumps(yearly['45']),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol',type=Path,default=Path('config/audited-research-rerun-v1.json'))
    prepare(parser.parse_args().protocol)
