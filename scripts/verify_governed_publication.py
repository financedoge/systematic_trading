"""Independent database/API acceptance checks for a committed governed batch."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.market_data.golden import _sql_string


def verify(root: Path, output: Path, base_url: str):
    receipt=json.loads((root/'clickhouse_receipt.json').read_text(encoding='utf8'))
    batch=receipt['batch']
    assert digest((root/'manifest.json').read_bytes())==batch
    store=AnalyticsStore.from_settings(AppSettings())
    scope='workspace='+_sql_string(store.workspace)
    checks={}
    for table,key in [('governed_daily','bars'),('governance_comparisons','comparisons')]:
        checks[table]=store.query(f'SELECT count() n,uniqExact(symbol) symbols FROM market_data.{table} FINAL WHERE '
                                  +scope+' AND batch='+_sql_string(batch))[0]
        assert checks[table]['n']==receipt[key]
    prefix='governance-batch/'+batch+'/'
    publication=store.latest('governance/catalog')
    assert publication['version']==batch and publication['observation_count']==receipt['symbols']
    for table,key in [('observations','actions'),('documents','source_documents'),('publications','symbols')]:
        n=store.query(f'SELECT count() n FROM analytics.{table} FINAL WHERE '+scope
                      +' AND startsWith(source_id,'+_sql_string(prefix)+') AND version='+_sql_string(batch))[0]['n']
        assert n==receipt[key],(table,n,receipt[key])
        checks[table]=n
    manifest=store.document('governance/catalog','manifest.json')
    assert digest(manifest[0]['payload'])==batch

    def get(path,**params):
        params['batch']=batch
        with urlopen(base_url.rstrip('/')+'/api/v1/market-data/governed/'+path+'?'+urlencode(params),timeout=120) as response:
            return json.load(response)

    catalog=get('catalog')
    assert catalog['batch']==batch and len(catalog['series'])==receipt['symbols']
    records={r['symbol']:r for r in catalog['series']}
    assert sum(r.get('rows',0) for r in records.values())==receipt['bars']
    assert 'TEST' not in records
    for record in records.values():
        boundary=record.get('listing_boundary',{}).get('date')
        if boundary and record.get('rows'):
            assert record['first']>=boundary,(record['symbol'],record['first'],boundary)
    etfs='SPY DBC EWH EWJ EWY GLD HYG IEF LQD MCHI TLT VGK'.split()
    for symbol in etfs:
        r=records[symbol]
        assert r['rows']==r['raw_rows']==r['raw_volume_rows']>0
        assert r['internal_gaps']==0 and r['last']=='2026-09-25'
    aapl=get('series',symbol='AAPL',start_date='2020-08-28',end_date='2020-08-31')
    assert len(aapl['rows'])==2 and aapl['next_after'] is None
    for row in aapl['rows']:
        assert digest(encode({k:v for k,v in row.items() if k!='payload_sha256'}))==row['payload_sha256']
    assert abs(aapl['rows'][0]['raw_close']-499.23)<0.001
    assert abs(aapl['rows'][1]['raw_close']-129.04)<0.001
    first=get('series',symbol='AAPL',start_date='2020-08-28',end_date='2020-08-31',limit=1)
    second=get('series',symbol='AAPL',after=first['next_after'],end_date='2020-08-31',limit=1)
    assert second['rows']==aapl['rows'][1:]
    ge=get('series',symbol='GE',start_date='1962-07-02',end_date='1962-07-06')
    assert len(ge['rows'])==4 and all(r['raw_close'] is None for r in ge['rows'])
    assert all(r['trade_date']!='1962-07-04' for r in ge['rows'])
    unavailable=next(r['symbol'] for r in records.values() if not r.get('rows'))
    assert get('audit',symbol=unavailable)['audit']['status']=='unavailable'
    assert get('series',symbol=unavailable)['rows']==[]
    audit=get('audit',symbol='AAPL')['audit']
    primary=next(s for s in audit['sources'] if s['source_id']==audit['primary_source'])
    original=get('source',symbol='AAPL',source_id=primary['source_id'])
    assert digest(original['document']['payload'])==primary['raw_sha256']
    compared=get('series',symbol='AAPL',start_date='2020-01-02',end_date='2020-01-10',comparison_source=primary['source_id'])
    assert len(compared['rows'])==len(compared['comparisons'])>0
    assert get('actions',symbol='AAPL')['actions']
    for symbol,start in [('NET','2019-09-13'),('WMS','2014-07-25'),('DAL','2007-05-03')]:
        record=get('audit',symbol=symbol)['audit']
        assert record['first']==start and record['pre_listing_source_observations']>0
        assert not get('series',symbol=symbol,end_date='2000-01-01')['rows']
    net=get('audit',symbol='NET')['audit']
    archived=next(s for s in net['sources'] if s.get('pre_listing_observations',0)>0)
    before=get('series',symbol='NET',comparison_source=archived['source_id'],end_date='2000-01-01')
    assert before['comparisons'] and all(not r['accepted'] and r['rebased_adjusted_close'] is None for r in before['comparisons'])
    checks.update(batch=batch,workspace=store.workspace,api_catalog_symbols=len(records),strategy_etfs=etfs,
                  price_split_check=aapl['rows'],pre1970_calendar_dates=[r['trade_date'] for r in ge['rows']],
                  unavailable_symbol_checked=unavailable,source_document_sha256=primary['raw_sha256'],
                  result='passed')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(encode(checks),encoding='utf8')
    print(encode({k:v for k,v in checks.items() if k!='price_split_check'}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--base-url',default='http://127.0.0.1:8000')
    args=parser.parse_args()
    verify(args.root,args.output,args.base_url)
