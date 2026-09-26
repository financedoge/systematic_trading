"""Publish extracted public CSV histories and exact source files to ClickHouse."""
from __future__ import annotations
import argparse
import csv
import io
from pathlib import Path

from import_sector_research_clickhouse import ResearchBatchAnalytics
from prepare_long_constituent_features import read_json, numeric
from run_constituent_research import verify_manifest
from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.analytics_projection import observation

# The bar transformation is unchanged from this version. A later source-document
# newline fix must not create new versions of millions of identical numeric rows.
BAR_EXTRACTOR_VERSION='3829bacf5b0b236c07cce82313087e389d12d4c447fc79ba802fe6437c15e6df'


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args()
    root=args.root
    verify_manifest(root,'archive_manifest.json')
    store=ResearchBatchAnalytics.from_settings(AppSettings())
    store.client.timeout_seconds=120
    prefix='sector-research/'+root.name+'/'
    current=store.publication_index(prefix)
    count=0
    for i,item in enumerate(read_json(root/'archive_index.json')):
        source=prefix+'bars/'+item['provider']+'/'+item['symbol']
        version=digest(encode(dict(item=item,extractor=BAR_EXTRACTOR_VERSION)))
        raw=(root/item['path']).read_bytes().decode('utf8')
        rows=[]
        for r in csv.DictReader(io.StringIO(raw)):
            payload=dict(symbol=item['symbol'],date=r['Date'],provider=item['provider'],source_raw_sha256=item['raw_sha256'],
                historical_available_at=None,quality_flags=['historical_vintage_uncertified',item['price_convention'],item['identity_method']])
            for field in ('open','high','low','close','volume'):
                value=numeric(r[field.title()])
                payload[field]=value if value==value else None
            value=numeric(r.get('Adj Close',r['Close']))
            payload['adjusted_close']=value if value==value else None
            rows.append(observation(r['Date'],'research_equity_daily_bar',item['symbol'],payload,r['Date']))
        if len({r['point_key'] for r in rows})!=len(rows):
            raise ValueError('Duplicate archive dates: '+source)
        if current.get(source,{}).get('version')!=version:
            store.publish_batch([(source,version,rows,item)])
        document_version=digest(encode(dict(raw_sha256=item['raw_sha256'],exact_utf8=True))) if '\r' in raw else item['raw_sha256']
        store.publish(source+'/raw',document_version,[],[dict(point_key=item['path'],media_type='text/csv',payload=raw)],provenance=item)
        count+=len(rows)
        if i%100==0:
            print('ARCHIVE',i,'rows',count,flush=True)
    docs=[dict(point_key=n,media_type='application/json',payload=(root/n).read_text(encoding='utf8')) for n in ('archive_index.json','archive_manifest.json')]
    version=sha256(root/'archive_manifest.json')
    store.publish(prefix+'dataset',version,[],docs,provenance=dict(research_only=True,root=str(root)))
    write_json(root/'clickhouse_receipt.json',dict(source_id=prefix+'dataset',version=version,observations=count,
        verification='Exact row and source-document payload SHA256 readback before publication',research_only=True))
    print('PUBLISHED',count,flush=True)


if __name__=='__main__':
    main()
