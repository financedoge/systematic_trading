"""Verify complete governed exports and source documents in ClickHouse, then commit."""
from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import gzip
import http.client
import json
from pathlib import Path
import time
from urllib.error import URLError
from urllib.parse import urlencode, urlsplit

from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.market_data.governance_store import GovernanceStore
from systematic_trading.market_data.golden import _sql_string
from systematic_trading.research.analytics_projection import observation


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def rows(path):
    with gzip.open(path,'rt',encoding='utf8') as f:
        return [json.loads(line) for line in f]


def connected_store():
    analytics=AnalyticsStore.from_settings(AppSettings())
    # Local to this idempotent, hash-verified research import. No trading calls.
    client=analytics.client
    url=urlsplit(client.base_url)
    connection_type=http.client.HTTPSConnection if url.scheme=='https' else http.client.HTTPConnection
    connection=connection_type(url.hostname,url.port,timeout=30)
    request_path=(url.path.rstrip('/') or '')+'/?'+urlencode(dict(database=client.database,user=client.user,password=client.password))
    def execute(sql):
        for attempt in range(4):
            try:
                connection.request('POST',request_path,body=sql.encode('utf8'))
                response=connection.getresponse()
                body=response.read().decode('utf8')
                if response.status!=200:
                    raise RuntimeError(f'ClickHouse import HTTP {response.status}: {body}')
                return body
            except (URLError,TimeoutError,ConnectionError,http.client.HTTPException):
                connection.close()
                if attempt==3:
                    raise
                time.sleep(attempt+1)
    analytics.client.execute=execute
    return analytics


_worker = None


def initialize_worker(root,fresh,batch,indexed,current):
    global _worker
    analytics=connected_store()
    _worker=(root,fresh,batch,indexed,current,analytics,GovernanceStore(analytics))


def publish_symbol(item):
    root,fresh,batch,indexed,current,analytics,store=_worker
    symbol=item['symbol']
    source_id='governance-batch/'+batch+'/'+symbol
    bars=rows(root/'bars'/(symbol+'.jsonl.gz'))
    comparisons=rows(root/'comparisons'/(symbol+'.jsonl.gz'))
    actions=rows(root/'actions'/(symbol+'.jsonl.gz'))
    docs=[dict(point_key='audit',media_type='application/json',payload=(root/'audits'/(symbol+'.json')).read_bytes().decode('utf8'))]
    # Newly acquired histories, action ledgers and extracted files are saved
    # as exact source documents, even when identity gates reject their bars.
    for source in indexed.get(symbol,[]):
        if not source['already_archived']:
            raw=Path(source['path']).read_bytes()
            if digest(raw)!=source['raw_sha256']:
                raise ValueError('Source hash mismatch')
            docs.append(dict(point_key=source['source_id'],media_type='text/plain',payload=raw.decode('utf8')))
    meta=fresh/'metadata'/(symbol+'.json')
    supplement=fresh.parent/'governance-etfs-20260926-v1'
    if not meta.exists():
        meta=supplement/'metadata'/(symbol+'.json')
    if meta.exists():
        docs.append(dict(point_key='download_metadata',media_type='application/json',payload=meta.read_bytes().decode('utf8')))
        m=read(meta)
        rejected=meta.parent.parent/'raw'/(symbol+'.json')
        if m.get('status')!='ok' and rejected.exists():
            docs.append(dict(point_key='rejected_download',media_type='application/json',payload=rejected.read_bytes().decode('utf8')))
    if source_id not in current:
        store.insert_verified('governed_daily',batch,symbol,bars)
        store.insert_verified('governance_comparisons',batch,symbol,comparisons)
        observations=[observation(str(j),'governed_corporate_action',symbol,r,r['date']) for j,r in enumerate(actions)]
        analytics.publish(source_id,batch,observations,docs,provenance=dict(symbol=symbol,manifest_sha256=batch,rows=len(bars),comparisons=len(comparisons),research_only=True))
    return dict(bars=len(bars),comparisons=len(comparisons),actions=len(actions),source_documents=len(docs),symbols=1)


def main(root,fresh,workers=1):
    if read(root/'policy.json').get('version',0)<2:
        raise ValueError('Quarantined pre-listing policy: rebuild with listing-boundary controls before publication')
    manifest=read(root/'manifest.json')
    for name,expected in manifest.items():
        if digest((root/name).read_bytes())!=expected:
            raise ValueError('Frozen governed artifact changed: '+name)
    batch=digest((root/'manifest.json').read_bytes())
    analytics=connected_store()
    store=GovernanceStore(analytics)
    store.initialize()
    current=analytics.publication_index('governance-batch/'+batch+'/')
    catalog=read(root/'catalog.json')
    index=read(root/'source_index.json')
    indexed={}
    for source in index:
        indexed.setdefault(source['symbol'],[]).append(source)
    counts=dict(bars=0,comparisons=0,actions=0,symbols=0,source_documents=0)
    if len({item['symbol'] for item in catalog})!=len(catalog):
        raise ValueError('Duplicate catalog symbol')
    # Each worker owns disjoint symbol keys and its own persistent connection.
    # Workers commit only per-symbol evidence; the parent commits the catalog
    # after every worker and the whole-batch count checks succeed.
    with ProcessPoolExecutor(max_workers=workers,initializer=initialize_worker,
            initargs=(root,fresh,batch,indexed,current)) as pool:
        for i,result in enumerate(pool.map(publish_symbol,catalog,chunksize=4),1):
            for key,value in result.items():
                counts[key]+=value
            if i%100==0:
                print('PUBLISH',i,counts,flush=True)
    docs=[dict(point_key=name,media_type='application/json',payload=(root/name).read_bytes().decode('utf8')) for name in
          ('manifest.json','input_manifest.json','identity_inputs_manifest.json','universe.json','source_index.json','calendar.json','policy.json','summary.json')]
    for name in ('build_source.py','price_governance.py'):
        docs.append(dict(point_key=name,media_type='text/x-python',payload=(root/name).read_bytes().decode('utf8')))
    for name in ('coverage.csv','unresolved.csv'):
        docs.append(dict(point_key=name,media_type='text/csv',payload=(root/name).read_bytes().decode('utf8')))
    for name in ('input_inventory_parent.json','runtime_versions.json'):
        if (root/name).exists():
            docs.append(dict(point_key=name,media_type='application/json',payload=(root/name).read_bytes().decode('utf8')))
    docs.append(dict(point_key='fresh_source_manifest',media_type='application/json',payload=(fresh/'manifest.json').read_bytes().decode('utf8')))
    docs.append(dict(point_key='etf_source_manifest',media_type='application/json',payload=(fresh.parent/'governance-etfs-20260926-v1'/'manifest.json').read_bytes().decode('utf8')))
    docs.append(dict(point_key='publisher_source.py',media_type='text/x-python',payload=Path(__file__).read_bytes().decode('utf8')))
    for table,key in [('governed_daily','bars'),('governance_comparisons','comparisons')]:
        actual=analytics.query(f'SELECT count() AS n FROM market_data.{table} FINAL WHERE workspace='
            +_sql_string(analytics.workspace)+' AND batch='+_sql_string(batch))[0]['n']
        if actual!=counts[key]:
            raise ValueError('Whole-batch row count mismatch: '+table)
    # The catalog pointer moves only after all per-symbol rows and documents have
    # passed exact SHA256 readback. APIs never expose a half-ingested batch.
    observations=[observation(r['symbol'],'governed_series_catalog',r['symbol'],r) for r in catalog]
    analytics.publish('governance/catalog',batch,observations,docs,provenance=dict(root=str(root),counts=counts,policy=read(root/'policy.json')))
    (root/'clickhouse_receipt.json').write_text(encode(dict(batch=batch,**counts,verification='Every row and exact source-document payload SHA256 read back before batch publication')),encoding='utf8')
    print('COMMITTED',batch,counts,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--fresh',type=Path,required=True)
    p.add_argument('--workers',type=int,choices=range(1,9),default=1)
    a=p.parse_args()
    main(a.root,a.fresh,a.workers)
