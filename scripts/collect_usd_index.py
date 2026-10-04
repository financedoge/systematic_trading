"""Acquire official dollar-index snapshots for audit, never direct backtest use."""
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
import io
import json
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.live.trading_calendar import is_us_trading_day

ROOT=Path('research/usd-data')


def fetch(item):
    vintage,known,decision=item
    start=str(date.fromisoformat(vintage)-timedelta(days=180))
    query=urlencode(dict(id='DTWEXBGS',cosd=start,coed=vintage,vintage_date=vintage))
    url='https://alfred.stlouisfed.org/graph/alfredgraph.csv?'+query
    path=ROOT/'archives'/(vintage+'.csv')
    metadata=path.with_suffix('.json')
    if path.exists() and metadata.exists():
        old=json.loads(metadata.read_text(encoding='utf8'))
        if sha256(path)!=old['sha256']:
            raise ValueError('Archived USD snapshot changed')
        return old
    for attempt in range(3):
        try:
            request=Request(url,headers={'User-Agent':'Mozilla/5.0 research data audit'})
            with urlopen(request,timeout=40) as response:
                data=response.read()
            rows=list(csv.DictReader(io.StringIO(data.decode('utf-8-sig'))))
            expected='DTWEXBGS_'+vintage.replace('-','')
            if not rows or expected not in rows[0]:
                raise ValueError('Wrong ALFRED series/vintage header')
            path.write_bytes(data)
            record=dict(vintage_date=vintage,known_through=known,decision_date=decision,url=url,
                path=str(path.resolve()),sha256=sha256(path),retrieved_at=datetime.now(UTC).isoformat(),rows=len(rows),status='downloaded_for_audit')
            write_json(metadata,record)
            return record
        except Exception as exc:
            if attempt==2:
                return dict(vintage_date=vintage,known_through=known,decision_date=decision,url=url,status='failed',error=repr(exc))
            time.sleep(1+attempt)


def collect():
    (ROOT/'archives').mkdir(parents=True,exist_ok=True)
    items=[]
    # DTWEXBGS was introduced February 4, 2019; no pre-launch proxy splice.
    for year in range(2019,2027):
        for month in range(1,13):
            first=date(year,month,1)
            if not date(2019,3,1)<=first<=date(2026,10,1):continue
            decision=first
            while not is_us_trading_day(decision):decision+=timedelta(days=1)
            known=decision-timedelta(days=1)
            while not is_us_trading_day(known):known-=timedelta(days=1)
            vintage=known-timedelta(days=1)  # prior calendar day, conservatively before signal close
            items.append((str(vintage),str(known),str(decision)))
    records=[]
    with ThreadPoolExecutor(4) as pool:
        for f in as_completed([pool.submit(fetch,item) for item in items]):
            records.append(f.result())
            if len(records)%10==0:print('USD snapshots',len(records),'/',len(items),flush=True)
    records.sort(key=lambda r:r['vintage_date'])
    write_json(ROOT/'download-manifest.json',dict(series='DTWEXBGS',source='Federal Reserve / ALFRED',
        methodology_start='2019-02-04',records=records,stage='source inspection; requires audit and publication before research'))
    print('Downloaded',sum(r['status']=='downloaded_for_audit' for r in records),'failed',sum(r['status']=='failed' for r in records),flush=True)


if __name__=='__main__':collect()
