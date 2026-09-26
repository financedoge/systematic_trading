"""Matched post-2023 check against the actual frozen production SOTA tree."""
from __future__ import annotations
import argparse
from pathlib import Path
import shutil

from prepare_long_constituent_features import read_json
from run_constituent_research import verify_manifest
from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.analytics_store import AnalyticsStore


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--origin',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True)
    a=p.parse_args();verify_manifest(a.origin,'input_manifest.json')
    a.root.mkdir(parents=True,exist_ok=False)
    protocol=read_json(a.origin/'protocol.json')
    protocol.update(version='constituent-frozen-reference-v1',start='2023-01-03',base_tree_model_schedule=False,
        primary='early_signed',trials={n:protocol['trials'][n] for n in ('sota','early_signed','early_breadth','early_price')},
        stresses={},shared_trials=['sota','early_signed'],stress_trials=[],feature_sets={},
        interpretation='Actual frozen pre2023 production model compared on post2023 dates using the new IVV features. Retrospective public-data research, not an untouched holdout. Companion to causal2016+ reconstruction.')
    write_json(a.root/'protocol.json',protocol)
    for n in ('features.json','coverage.json'):
        shutil.copyfile(a.origin/n,a.root/n)
    shutil.copyfile(__file__,a.root/'prepare_source.py')
    source='constituent-research/'+a.root.name+'/features'
    version=sha256(a.root/'features.json')
    store=AnalyticsStore.from_settings(AppSettings())
    provenance=dict(research_only=True,origin=str(a.origin),origin_input_manifest=sha256(a.origin/'input_manifest.json'),
                    original_feature_source=read_json(a.origin/'clickhouse_receipt.json'))
    store.publish(source,version,[],[dict(point_key='protocol',media_type='application/json',payload=(a.root/'protocol.json').read_text(encoding='utf8'))],provenance=provenance)
    write_json(a.root/'clickhouse_receipt.json',dict(source_id=source,version=version,provenance=provenance))
    write_json(a.root/'input_manifest.json',{p.name:sha256(p) for p in a.root.iterdir() if p.is_file()})
    print('READY',a.root)


if __name__=='__main__':
    main()
