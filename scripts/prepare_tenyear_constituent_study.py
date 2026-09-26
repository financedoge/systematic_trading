"""Freeze dated expanding base trees, residual trees, public features and provenance."""
from __future__ import annotations
import argparse
from datetime import date
from pathlib import Path
import shutil

from prepare_long_constituent_features import read_json
from prepare_constituent_integration import fit_models
from run_constituent_research import verify_manifest
from systematic_trading.config import AppSettings
from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research import current_sota_definition, instantiate_overlays
from systematic_trading.research.analytics_projection import observation
from systematic_trading.research.chronological_tree import select_base_tree
from systematic_trading.research.constituent_integration import residual_inputs
from systematic_trading.signals.base import SignalContext
from systematic_trading.signals.library import compute_signal_features
from systematic_trading.signals.decision_tree import DecisionTreeSample, train_simple_regression_tree


def fit_base_models(records, template, years):
    models={}
    for year in years:
        cutoff=f'{year}-01-01'
        completed=[r for r in records if r['label_end']<cutoff and r['known_through']<cutoff]
        if len(completed)<100:
            continue
        model=train_simple_regression_tree([DecisionTreeSample(features=r['inputs'],target=r['relative_return']) for r in completed],
            feature_names=template.feature_names,max_depth=template.max_depth,min_samples_leaf=template.min_samples_leaf)
        models[cutoff]=dict(fit_as_of=cutoff,max_label_end=max(r['label_end'] for r in completed),
            max_feature_date=max(r['known_through'] for r in completed),training_samples=len(completed),model=model.to_dict())
        print('FIT BASE',cutoff,len(completed),flush=True)
    return models


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--features',type=Path,required=True)
    p.add_argument('--yahoo-features',type=Path,required=True)
    args=p.parse_args()
    root=args.root
    root.mkdir(parents=True,exist_ok=False)
    protocol=read_json(args.protocol)
    shutil.copyfile(args.protocol,root/'protocol.json')
    features=read_json(args.features/'features.json')
    shutil.copyfile(args.features/'coverage.json',root/'coverage.json')
    shutil.copyfile(args.yahoo_features/'features.json',root/'features_yahoo_only.json')
    shutil.copyfile(args.yahoo_features/'coverage.json',root/'coverage_yahoo_only.json')
    snapshot=Path(protocol['etf_snapshot'])
    verify_manifest(snapshot,'manifest.json')
    bars={s:[PriceBar.model_validate(r) for r in rows] for s,rows in read_json(snapshot/'bars.json').items()}
    days=[str(r.trade_date) for r in bars['SPY']]
    starts=[d for i,d in enumerate(days) if i>=253 and d[:7]!=days[i-1][:7]]
    prices={s:{str(r.trade_date):float(r.close) for r in rows} for s,rows in bars.items()}
    records=[]
    for start,end in zip(starts,starts[1:]):
        known,label_end=days[days.index(start)-1],days[days.index(end)-1]
        context=SignalContext(as_of=date.fromisoformat(start),instruments={},bars_by_symbol=bars,trade_dates=[])
        returns={s:prices[s][label_end]/prices[s][known]-1 for s in bars}
        mean=sum(returns.values())/len(returns)
        for symbol in bars:
            records.append(dict(symbol=symbol,signal_session=start,known_through=known,label_end=label_end,
                inputs=compute_signal_features(symbol=symbol,context=context),relative_return=returns[symbol]-mean))
    template=instantiate_overlays(current_sota_definition())[1].model
    base_models=fit_base_models(records,template,range(2014,2027))
    residuals=[]
    for r in records:
        if r['symbol']!='SPY' or r['known_through']<min(base_models):
            continue
        row=features['45'].get(r['known_through'])
        if not row or row['scores'] is None or row['value_coverage']<.95 or row['name_coverage']<.70:
            continue
        forecast=select_base_tree(base_models,r['known_through']).predict(r['inputs'])
        residuals.append(dict(known_through=r['known_through'],label_end=r['label_end'],
            inputs=residual_inputs(r['inputs'],forecast,row),relative_return=r['relative_return'],
            residual=r['relative_return']-forecast,label_role='training_only_never_runtime_feature'))
    models=fit_models(residuals,range(2015,2027))
    features['integration_models']=models
    write_json(root/'features.json',features)
    write_json(root/'base_tree_models.json',base_models)
    write_json(root/'models.json',models)
    write_json(root/'base_training_records.json',records)
    write_json(root/'training_records.json',residuals)
    for name in ('prepare_tenyear_constituent_study.py','prepare_long_constituent_features.py','run_constituent_research.py'):
        shutil.copyfile(Path(__file__).with_name(name),root/name)
    store=AnalyticsStore.from_settings(AppSettings())
    store.client.timeout_seconds=120
    source=store.latest('sector-research/'+Path(protocol['stock_root']).name+'/dataset')
    if source is None:
        raise ValueError('Issuer dataset must be in ClickHouse')
    rows=[]
    for kind,series in [('mixed',features),('yahoo_only',read_json(root/'features_yahoo_only.json'))]:
        rows += [observation(kind+'/'+lag+'/'+d,'research_constituent_signal','SPY',dict(feature_set=kind,holdings_lag_days=int(lag),**r),d)
                 for lag in ('45','60') for d,r in series[lag].items()]
    rows += [observation('base/'+d,'research_constituent_tree_model','BASE',r,d) for d,r in base_models.items()]
    rows += [observation(kind+'/'+d,'research_constituent_tree_model','SPY',r,d) for kind,series in models.items() for d,r in series.items()]
    rows += [observation('base_label/'+r['symbol']+'/'+r['known_through'],'research_constituent_training_label',r['symbol'],r,r['label_end']) for r in records]
    rows += [observation('residual_label/'+r['known_through'],'research_constituent_training_label','SPY',r,r['label_end']) for r in residuals]
    files={p.name:sha256(p) for p in root.iterdir() if p.is_file()}
    version=digest(encode(files))
    docs=[dict(point_key=n,media_type='application/json',payload=(root/n).read_text(encoding='utf8')) for n in ('protocol.json','coverage.json','coverage_yahoo_only.json','base_tree_models.json','models.json')]
    source_id='constituent-research/'+root.name+'/features'
    store.publish(source_id,version,rows,docs,provenance=dict(research_only=True,files=files,source_version=source['version'],archive_manifest=sha256(Path(protocol['archive_root'])/'archive_manifest.json')))
    write_json(root/'clickhouse_receipt.json',dict(source_id=source_id,version=version,observations=len(rows),documents=len(docs),verification='Exact payload SHA256 readback'))
    write_json(root/'input_manifest.json',{p.name:sha256(p) for p in root.iterdir() if p.is_file()})
    print('READY',root,'base labels',len(records),'residual labels',len(residuals),flush=True)


if __name__=='__main__':
    main()
