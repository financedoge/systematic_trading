"""Restartable, bounded export of retained ClickHouse publications to native storage.

The source remains intact. Only independently read-back Parquet fragments become
visible through one PostgreSQL publication transaction. No downloaded prices.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import sys
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.market_data.golden import _sql_string as literal
from systematic_trading.market_data.native_analytics import NativeAnalyticsStore
from systematic_trading.market_data.native_market import NativeMarketDataClient
from systematic_trading.storage.artifact_retention import retirement_for_path


def stream(settings, sql):
    with httpx.stream('POST',settings.clickhouse_http_url,content=sql+' FORMAT JSONEachRow',
            headers={'X-ClickHouse-User':settings.clickhouse_user,'X-ClickHouse-Key':settings.clickhouse_password},
            params={'max_threads':2,'max_memory_usage':2147483648,'max_block_size':2048,
                    'max_bytes_before_external_sort':268435456,'max_bytes_before_external_group_by':268435456},
            timeout=600,trust_env=False) as response:
        if response.status_code != 200:
            raise RuntimeError(f'ClickHouse export failed (HTTP {response.status_code}): '+response.read().decode(errors='replace')[:1500])
        for line in response.iter_lines():
            if line:
                yield json.loads(line)


def select_plan(settings, destination):
    source=AnalyticsStore.from_settings(settings.model_copy(update={'market_data_store_backend':'clickhouse'}))
    workspace=literal(source.workspace)
    # Keep current and rollback catalogs, every active study pin, and the data
    # batches referenced by protected calculation/operational evidence.
    batches={r['version'] for r in source.publications('governance/catalog')[:2]}
    # Broker/execution evidence may pin older calculations and audited catalogs
    # beyond the latest monitored/rollback pair. Preserve their published data.
    from retire_research_artifacts import operational_references, protection
    guard,_=protection(settings)
    known_catalogs={r['version'] for r in source.publications('governance/catalog')}
    batches.update(operational_references(settings,r'([a-f0-9]{64})','batch') & known_catalogs)
    for path in (ROOT/'config').glob('*.json'):
        batches.update(set(re.findall(r'[a-f0-9]{64}',path.read_text(encoding='utf8'))) & known_catalogs)
    for revision in guard['protected_revisions']:
        publication=source.publication('tracked-strategies/calculations',revision)
        if publication:
            batches.update(set(re.findall(r'[a-f0-9]{64}',encode(publication))) & known_catalogs)
    for name in ('cash-relative-momentum-20261017-v1','class-volatility-screen-20261016-v1','etf-expansion-20261014-v1'):
        for path in (ROOT/'research'/name).glob('*.json'):
            body=json.loads(path.read_text(encoding='utf8'))
            def pins(value):
                if isinstance(value,dict):
                    if value.get('lifecycle')=='archived': return
                    for key,item in value.items():
                        if 'batch' in key and isinstance(item,str) and re.fullmatch('[0-9a-f]{64}',item): batches.add(item)
                        pins(item)
                elif isinstance(value,list):
                    for item in value: pins(item)
            pins(body)
    selected={}
    governed_publications={}
    dropped=Counter()
    for row in stream(settings,'SELECT * FROM analytics.publications FINAL WHERE workspace='+workspace+
            ' AND (source_id,version) IN (SELECT source_id,argMax(version,published_at) FROM analytics.publications '
            'WHERE workspace='+workspace+' GROUP BY source_id) ORDER BY source_id,version'):
        source_id=row['source_id']
        if source_id.startswith('governance-batch/'):
            governed_publications[source_id,row['version']]=row
            continue
        if source_id=='governance/catalog':
            continue
        provenance=json.loads(row['provenance'])
        if source_id.startswith('lean-run/') and retirement_for_path(settings.data_dir,provenance.get('artifact_path','')):
            dropped['retired_lean_publications']+=1
            continue
        selected[source_id,row['version']]=row
    for source_id in ('tracked-strategies/calculations','strategy-serving'):
        for row in source.publications(source_id)[:2]:
            selected[source_id,row['version']]=row
            for record in source.pinned_rows('documents',source_id,row['version']):
                if record.get('media_type') != 'application/json': continue
                body=json.loads(record['payload'])
                if isinstance(body,dict) and body.get('lifecycle')=='archived': continue
                pins(body)
    # Operational and retained rollback artifacts also need their original
    # publication records, even when older than the two newest revisions.
    for revision in guard['protected_revisions']:
        publication=source.publication('tracked-strategies/calculations',revision)
        if publication:
            selected['tracked-strategies/calculations',revision]=publication
    physical=set()
    external_pins=[]
    for batch in sorted(batches):
        publication=source.publication('governance/catalog',batch)
        if publication is None:
            # Model/FX/economic receipts also use a "batch" key. Their pinned
            # files remain protected; they are not governed price catalogs.
            external_pins.append(batch)
            continue
        selected['governance/catalog',batch]=publication
        for row in source.pinned_rows('observations','governance/catalog',batch,family='governed_series_catalog'):
            record=json.loads(row['payload'])
            physical.add((record.get('storage_batch',batch),record['symbol']))
    for batch,symbol in sorted(physical):
        source_id='governance-batch/'+batch+'/'+symbol
        publication=governed_publications.get((source_id,batch))
        if publication is None: raise ValueError('Protected symbol storage is not published: '+source_id)
        selected[source_id,batch]=publication
    plan=dict(format=1,workspace=source.workspace,created_at=datetime.now(UTC).isoformat(),
        catalogs=sorted(batches-set(external_pins)),external_batch_pins=external_pins,
        governed_pairs=sorted(physical),publications=list(selected.values()),retired=dict(dropped))
    plan['sha256']=digest(encode(plan))
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(encode(plan),encoding='utf8')
    print(encode(dict(plan=str(destination),publications=len(selected),catalogs=len(batches),governed_pairs=len(physical),retired=dropped)),flush=True)


def governed_fingerprint(rows):
    return digest(''.join(sorted(digest('\0'.join([r['symbol'],r.get('source_id',''),r['trade_date'],r['payload_hash']])) for r in rows)))


def export_governed(settings,target,plan):
    from itertools import groupby
    workspace=literal(target.workspace)
    for table in ('governed_daily','governance_comparisons'):
        pending=[tuple(p) for p in plan['governed_pairs']]
        for offset in range(0,len(pending),64):
            pairs=pending[offset:offset+64]
            where='workspace='+workspace+' AND (batch,symbol) IN ('+','.join('('+literal(b)+','+literal(s)+')' for b,s in pairs)+')'
            source_column='source_id' if table=='governance_comparisons' else "''"
            signature="lower(hex(SHA256(concat(symbol,char(0),"+source_column+",char(0),toString(trade_date),char(0),payload_hash))))"
            counts={(r['batch'],r['symbol']):r for r in stream(settings,
                'SELECT batch,symbol,count() n,countIf(lower(hex(SHA256(payload)))!=payload_hash) invalid,'
                'lower(hex(SHA256(arrayStringConcat(arraySort(groupArray('+signature+")),'')))) fingerprint "
                'FROM market_data.'+table+' FINAL WHERE '+where+' GROUP BY batch,symbol')}
            reusable={}; needed=[]
            for batch,symbol in pairs:
                proof=counts.get((batch,symbol),dict(n=0,invalid=0,fingerprint=digest('')))
                if int(proof['invalid']):raise ValueError('Governed source contains invalid payload hashes')
                key='governed/'+table+'/'+batch+'/'+symbol
                cache='migration/fingerprint/'+table+'/'+symbol+'/'+proof['fingerprint']
                previous=target.lake.manifest(key)
                cached=target.lake.manifest(cache,proof['fingerprint'])
                if previous:
                    if not cached:
                        rows=target.lake.select([previous])
                        if len(rows)!=int(proof['n']) or governed_fingerprint(rows)!=proof['fingerprint']:
                            raise ValueError('Resumed governed data differs from source')
                        with target.catalog.writer(cache) as c:
                            target.catalog.commit(c,cache,proof['fingerprint'],previous,advance=False)
                elif cached:
                    if cached['row_count']!=int(proof['n']):raise ValueError('Governed reuse count differs')
                    for fragment in cached['fragments']:target.lake.verify_file(fragment)
                    with target.catalog.writer(key) as c:target.catalog.commit(c,key,cached['logical_sha256'],cached)
                    reusable[batch,symbol]=True
                else:needed.append((batch,symbol))
            if not needed:
                print(encode(dict(governed_table=table,committed=min(offset+64,len(pending)),pending=len(pending),reused=len(reusable))),flush=True)
                continue
            where='workspace='+workspace+' AND (batch,symbol) IN ('+','.join('('+literal(b)+','+literal(s)+')' for b,s in needed)+')'
            order='batch,symbol,'+('source_id,trade_date' if table=='governance_comparisons' else 'trade_date')
            source=stream(settings,'SELECT * FROM market_data.'+table+' FINAL WHERE '+where+' ORDER BY '+order)
            seen=set()
            try:
                for (batch,symbol),records in groupby(source,key=lambda r:(r['batch'],r['symbol'])):
                    if (batch,symbol) not in needed:raise ValueError('Unexpected governed identity')
                    signatures=[]
                    def checked_rows():
                        for row in records:
                            if digest(row['payload'])!=row['payload_hash']:raise ValueError('Governed source payload hash mismatch')
                            signatures.append(dict(symbol=row['symbol'],source_id=row.get('source_id',''),trade_date=row['trade_date'],payload_hash=row['payload_hash']))
                            yield target.governed_record(table,row)
                    key='governed/'+table+'/'+batch+'/'+symbol
                    with target.catalog.writer(key) as c:
                        manifest=target.lake.prepare(checked_rows())
                        proof=counts[batch,symbol]
                        if manifest['row_count']!=int(proof['n']) or governed_fingerprint(signatures)!=proof['fingerprint']:
                            raise ValueError('Governed export count or fingerprint mismatch')
                        target.catalog.commit(c,key,manifest['logical_sha256'],manifest)
                        target.catalog.commit(c,'migration/fingerprint/'+table+'/'+symbol+'/'+proof['fingerprint'],
                            proof['fingerprint'],manifest,advance=False)
                    seen.add((batch,symbol))
                for batch,symbol in set(needed)-seen:
                    if counts.get((batch,symbol),{}).get('n',0):raise ValueError('Missing governed rows')
                    key='governed/'+table+'/'+batch+'/'+symbol
                    with target.catalog.writer(key) as c:
                        manifest=target.lake.prepare([])
                        target.catalog.commit(c,key,manifest['logical_sha256'],manifest)
            finally:source.close()
            print(encode(dict(governed_table=table,committed=min(offset+64,len(pending)),pending=len(pending))),flush=True)


def apply(settings,path):
    plan=json.loads(path.read_text(encoding='utf8'))
    if plan['sha256']!=digest(encode({k:v for k,v in plan.items() if k!='sha256'})):
        raise ValueError('Export plan changed')
    target=NativeAnalyticsStore.from_settings(settings)
    if target.workspace!=plan['workspace']: raise ValueError('Workspace mismatch')
    target.initialize()
    with target.catalog.connect() as c:
        done={(r['source_id'],r['version']) for r in c.execute('SELECT source_id,version FROM native_analytics.publications WHERE workspace=%s',(target.workspace,))}
    pending=sorted((p for p in plan['publications'] if (p['source_id'],p['version']) not in done),key=lambda p:(p['source_id'],p['version']))
    workspace=literal(target.workspace)
    count=0
    for start in range(0,len(pending),128):
        batch=pending[start:start+128]
        identities=','.join('('+literal(p['source_id'])+','+literal(p['version'])+')' for p in batch)
        where='workspace='+workspace+' AND (source_id,version) IN ('+identities+')'
        generators=[]
        try:
            for table in ('observations','documents'):
                generators.append(stream(settings,'SELECT * FROM analytics.'+table+' FINAL WHERE '+where+
                    ' ORDER BY source_id,version,point_key'))
            target.publish_migration_batch(batch,*generators)
            count+=len(batch)
            print(encode(dict(publications_committed=count,total_pending=len(pending),last=batch[-1]['source_id'])),flush=True)
        finally:
            # Generator context managers close their HTTP streams when consumed.
            for generator in generators: generator.close()
    export_governed(settings,target,plan)
    market=NativeMarketDataClient(target.lake)
    for symbol in stream(settings,'SELECT DISTINCT symbol FROM market_data.daily_bars ORDER BY symbol'):
        market.insert_daily_bar_rows(list(stream(settings,'SELECT * FROM market_data.daily_bars FINAL WHERE symbol='+literal(symbol['symbol'])+' ORDER BY trade_date')))
    for pair in stream(settings,'SELECT DISTINCT base_currency,quote_currency FROM market_data.fx_rates'):
        market.insert_fx_rate_rows(list(stream(settings,'SELECT * FROM market_data.fx_rates FINAL WHERE base_currency='+literal(pair['base_currency'])+
            ' AND quote_currency='+literal(pair['quote_currency'])+' ORDER BY rate_date')))
    receipt=dict(plan_sha256=plan['sha256'],completed_at=datetime.now(UTC).isoformat(),publications=len(plan['publications']),
        governed_pairs=len(plan['governed_pairs']),verified='Every canonical source row independently read back from immutable Parquet before publication; committed source counts matched')
    path.with_suffix('.completed.json').write_text(encode(receipt),encoding='utf8')
    print(encode(receipt),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['plan','apply'])
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--transport-attempts',type=int,default=3,
        help='Bounded retries of restartable apply after interrupted HTTP transport')
    args=parser.parse_args()
    if not 1 <= args.transport_attempts <= 5:
        parser.error('--transport-attempts must be between 1 and 5')
    for attempt in range(args.transport_attempts):
        try:
            (select_plan if args.action=='plan' else apply)(AppSettings(),args.manifest)
            break
        except httpx.TransportError as exc:
            if args.action!='apply' or attempt+1==args.transport_attempts:
                raise
            print(encode(dict(transport_interrupted=type(exc).__name__,
                retry=attempt+1,action='Resume from verified committed publications')),flush=True)
            time.sleep(10)
