"""Archive the companion matched comparison against the unchanged frozen tree."""
import argparse
from pathlib import Path
import shutil
import numpy as np

from prepare_long_constituent_features import read_json
from run_constituent_research import verify_manifest
from analyze_constituent_research import information_ratio
from analyze_flow_concentration_research import metrics,return_vector,block_audit
from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256,write_json,verify_bundle
from systematic_trading.lean.registry import register_run
from systematic_trading.market_data.analytics_store import AnalyticsStore,digest,encode
from systematic_trading.research.analytics_projection import observation
from systematic_trading.storage.postgres import PostgresStore


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True)
    root=p.parse_args().root;verify_manifest(root,'input_manifest.json')
    progress,protocol=read_json(root/'progress.json'),read_json(root/'protocol.json')
    if not progress['complete']:
        raise ValueError('Finish all four matched native trials first')
    economics={}
    for n,h in progress['passed'].items():
        verify_bundle(root/'datasets'/n);r=read_json(root/'runs'/n/'run.json')
        if r['status']!='succeeded' or r['economic_sha256']!=h or not read_json(root/'runs'/n/'parity.json')['passed']:
            raise ValueError('Native comparison failed: '+n)
        for name,expected in r['artifacts'].items():
            if sha256(root/'runs'/n/name)!=expected:
                raise ValueError('Changed run artifact')
        economics[n]=read_json(root/'runs'/n/'economic.json')
    days=[r['date'] for r in economics['sota']['nav']]
    if any([r['date'] for r in e['nav']]!=days for e in economics.values()):
        raise ValueError('Unaligned comparison')
    vectors={n:return_vector(e['nav']) for n,e in economics.items()}
    base=metrics(economics['sota'],protocol['start'],protocol['end']);summary={}
    for n,e in economics.items():
        m=metrics(e,protocol['start'],protocol['end'])
        summary[n]=dict(**m,**information_ratio(vectors[n]-vectors['sota']),cagr_delta=m['cagr']-base['cagr'],sharpe_delta=m['sharpe']-base['sharpe'])
    names=[n for n in economics if n!='sota']
    uncertainty=block_audit(np.column_stack([vectors[n]-vectors['sota'] for n in names]),names)
    pairs={n:information_ratio(vectors[n]-vectors['early_price']) for n in ('early_signed','early_breadth')}
    for n,data in [('summary',summary),('uncertainty',uncertainty),('vs_price',pairs)]:write_json(root/(n+'.json'),data)
    shutil.copyfile(__file__,root/'analysis_source.py')
    write_json(root/'analysis_manifest.json',{n:sha256(root/n) for n in ('summary.json','uncertainty.json','vs_price.json','analysis_source.py')})
    store=AnalyticsStore.from_settings(AppSettings());version=digest(encode(read_json(root/'analysis_manifest.json')))
    store.publish('constituent-research/'+root.name+'/results',version,
        [observation(n+'/post2023','research_constituent_backtest',n,dict(period='post2023',**r)) for n,r in summary.items()],
        [dict(point_key=n,media_type='application/json',payload=(root/n).read_text(encoding='utf8')) for n in ('summary.json','uncertainty.json','vs_price.json')],provenance=dict(research_only=True,unchanged_production_tree=True))
    write_json(root/'results_clickhouse_receipt.json',dict(version=version,observations=len(summary),documents=3))
    registry=PostgresStore.from_settings(AppSettings());write_json(root/'registry_receipt.json',{n:register_run(registry,root/'runs'/n) for n in economics})
    for n,m in summary.items():print(n,m['cagr'],m['sharpe'],m['information_ratio'],flush=True)


if __name__=='__main__':main()
