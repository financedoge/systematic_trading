"""Freeze a post-selection follow-up and strictly chronological residual trees."""
from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from systematic_trading.config import AppSettings
from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.contracts import sha256, write_json, verify_bundle
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research import current_sota_definition, instantiate_overlays
from systematic_trading.research.analytics_projection import observation
from systematic_trading.research.constituent_integration import residual_inputs
from systematic_trading.signals.base import SignalContext
from systematic_trading.signals.decision_tree import DecisionTreeSample, train_simple_regression_tree
from systematic_trading.signals.library import compute_signal_features
from run_constituent_research import verify_manifest


def fit_models(records, years):
    models = {'joint': {}, 'price': {}}
    for year in years:
        cutoff = f'{year}-01-01'
        completed = [r for r in records if r['label_end'] < cutoff and r['known_through'] < cutoff]
        if len(completed) < 18:
            continue
        for kind in models:
            names = ('mom_63', 'mom_126', 'base_forecast') + (('breadth', 'signed_activity') if kind == 'joint' else ())
            model = train_simple_regression_tree([DecisionTreeSample(features=r['inputs'], target=r['residual']) for r in completed],
                feature_names=names, max_depth=2, min_samples_leaf=6)
            models[kind][cutoff] = dict(fit_as_of=cutoff, max_label_end=max(r['label_end'] for r in completed),
                max_feature_date=max(r['known_through'] for r in completed), training_samples=len(completed),
                training_dates=[r['known_through'] for r in completed], model=model.to_dict())
    return models


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--protocol', type=Path, default=Path('config/constituent-integration-v1.json'))
    args = parser.parse_args()
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(args.protocol, root/'protocol.json')
    protocol = json.loads((root/'protocol.json').read_text())
    # Freeze definitions before fitting; candidate backtest outcomes are not read.
    shutil.copyfile(__file__, root/'prepare_source.py')
    shutil.copyfile(Path(__file__).with_name('run_constituent_research.py'), root/'study_runner.py')
    repo = Path(__file__).resolve().parents[1]
    for name in ('constituent_integration', 'constituent_signals'):
        shutil.copyfile(repo/f'src/systematic_trading/research/{name}.py', root/f'{name}_source.py')
    origin = Path(protocol['feature_origin'])
    verify_manifest(origin, 'input_manifest.json')
    verify_bundle(origin/'datasets'/'sota')
    snapshot = Path(protocol['etf_snapshot'])
    verify_manifest(snapshot, 'manifest.json')
    features = json.loads((origin/'features.json').read_text())
    bars = {s: [PriceBar.model_validate(r) for r in rows] for s, rows in json.loads((snapshot/'bars.json').read_text()).items()}
    prices = {s: {str(r.trade_date): float(r.close) for r in rows} for s, rows in bars.items()}
    decisions = list(json.loads((origin/'datasets'/'sota'/'decisions.json').read_text()).values())
    base_tree = instantiate_overlays(current_sota_definition())[1].model
    records = []
    for i, decision in enumerate(decisions[:-1]):
        known, end = decision['known_through'], decisions[i+1]['known_through']
        row = features['45'].get(known)
        if row is None or row['scores'] is None or row['value_coverage'] < .95 or row['name_coverage'] < .70:
            continue
        context = SignalContext(as_of=date.fromisoformat(decision['signal_session']), instruments={}, bars_by_symbol=bars, trade_dates=[])
        price_features = compute_signal_features(symbol='SPY', context=context)
        forecast = base_tree.predict(price_features)
        inputs = residual_inputs(price_features, forecast, row)
        returns = {s: p[end]/p[known]-1 for s, p in prices.items()}
        target = returns['SPY']-sum(returns.values())/len(returns)
        records.append(dict(known_through=known, label_end=end, inputs=inputs, relative_return=target,
                            residual=target-forecast, label_role='training_only_never_runtime_feature'))
    models = fit_models(records, range(2020, 2027))
    features['integration_models'] = models
    write_json(root/'features.json', features)
    write_json(root/'training_records.json', records)
    write_json(root/'models.json', models)
    shutil.copyfile(origin/'coverage.json', root/'coverage.json')
    store = AnalyticsStore.from_settings(AppSettings())
    original = store.latest('constituent-research/'+origin.name+'/features')
    if original is None:
        raise ValueError('Original constituent signals must be archived first')
    rows = [observation(lag+'/'+d, 'research_constituent_signal', 'SPY', dict(holdings_lag_days=int(lag), **r), d)
            for lag in ('45', '60') for d, r in features[lag].items()]
    rows += [observation('model/'+kind+'/'+d, 'research_constituent_tree_model', 'SPY', r, d)
             for kind, series in models.items() for d, r in series.items()]
    rows += [observation('training/'+r['known_through'], 'research_constituent_training_label', 'SPY', r, r['label_end']) for r in records]
    source_id = 'constituent-research/'+root.name+'/features'
    version = digest(encode(dict(features=sha256(root/'features.json'), protocol=sha256(root/'protocol.json'),
        labels=sha256(root/'training_records.json'), source=sha256(root/'prepare_source.py'))))
    docs = [dict(point_key=n, media_type='application/json', payload=(root/n).read_text()) for n in ('protocol.json', 'models.json', 'coverage.json')]
    changed = store.publish(source_id, version, rows, docs, provenance=dict(research_only=True,
        selected_after_prior_results=True, original_features_version=original['version'], modeled_availability=True))
    write_json(root/'clickhouse_receipt.json', dict(source_id=source_id, version=version, changed=changed,
        observations=len(rows), documents=len(docs), original_features_version=original['version'],
        verification='Exact payload SHA256 readback before publication'))
    write_json(root/'input_manifest.json', {p.name: sha256(p) for p in root.iterdir() if p.is_file()})
    print(json.dumps(dict(training_records=len(records), models={k:{d:r['training_samples'] for d,r in v.items()} for k,v in models.items()},
                         clickhouse_rows=len(rows)), indent=2))


if __name__ == '__main__':
    main()
