"""Validate official snapshots, verify analytical readback, then publish a batch."""
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
import re

from bs4 import BeautifulSoup

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.analytics_store import AnalyticsStore, encode, timestamp
from systematic_trading.research.usd_index_governance import audit_snapshot


def current_history(source):
    soup=BeautifulSoup(source.read_text(encoding='utf8'),'html.parser')
    rows=[]
    for tr in soup.find_all('tr'):
        cells=[c.get_text(' ',strip=True) for c in tr.find_all(['td','th'])]
        if len(cells)==2 and re.fullmatch(r'\d{1,2}-[A-Z]{3}-\d{2}',cells[0]):
            day=datetime.strptime(cells[0],'%d-%b-%y').date()
            value=None if cells[1] in ('ND','NA','') else float(cells[1])
            rows.append(dict(observation_date=str(day),value=value))
    if not rows or len(rows)<4000:raise ValueError('Incomplete current Fed history')
    return rows


def publish(source,root):
    if root.exists():raise FileExistsError('Immutable USD batch already exists')
    manifest=json.loads((source/'download-manifest.json').read_text(encoding='utf8'))
    accepted=[];excluded=[];files={}
    for record in manifest['records']:
        if record['status']!='downloaded_for_audit':excluded.append(record);continue
        path=Path(record['path'])
        if sha256(path)!=record['sha256']:raise ValueError('Changed USD archive')
        files[str(path.resolve())]=record['sha256']
        try:
            row=audit_snapshot(path.read_text(encoding='utf-8-sig'),record)
            row.update(source_url=record['url'],source_sha256=record['sha256'],retrieved_at=record['retrieved_at'])
            accepted.append(row)
        except ValueError as exc:
            excluded.append(dict(record,audit_error=str(exc)))
    if not accepted:raise ValueError('No admissible USD snapshots')
    root.mkdir(parents=True)
    write_json(root/'snapshots.json',accepted)
    current=source/'source-inspection/broad-current.html'
    history=current_history(current)
    write_json(source/'broad-dollar-latest-history.json',dict(series='DTWEXBGS',source_url='https://www.federalreserve.gov/releases/h10/summary/jrxwtfb_nb.htm',
        source_sha256=sha256(current),basis='latest revised historical snapshot; source inspection only, not a historical point-in-time signal',observations=history))
    import csv
    with (source/'broad-dollar-latest-history.csv').open('w',encoding='utf8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=['observation_date','value']);writer.writeheader();writer.writerows(history)
    audit=dict(series='DTWEXBGS',accepted=len(accepted),excluded=excluded,source_files=files,
        policy='Post-February-2019 identity, prior-day ALFRED vintages, complete ordered snapshot, finite positive levels, 64 valid observations, <=14-day staleness, <=105-day span, <=5% adjacent level change; no filling, source splicing or current-vintage substitution.',
        historical_availability='Daily ALFRED vintage evidence with conservative end-of-day availability; intraday timestamps not independently certified',
        cross_source='Latest Fed full history retained separately. Revision differences are expected; not forced to agree across vintages.',
        code_sha256=sha256(Path('src/systematic_trading/research/usd_index_governance.py')),published_at=datetime.now(UTC).isoformat())
    write_json(root/'audit.json',audit)
    write_json(root/'manifest.json',{p.name:sha256(p) for p in root.iterdir()})
    batch=sha256(root/'manifest.json')
    analytics=AnalyticsStore.from_settings(AppSettings())
    observations=[dict(point_key=r['vintage_date'],family='usd_index_vintage',entity='DTWEXBGS',
        observed_at=timestamp(r['observation_date']),available_at=timestamp(r['available_at']),payload=encode(r)) for r in accepted]
    analytics.publish('governance/usd-broad-index',batch,observations,
        [dict(point_key='audit',media_type='application/json',payload=encode(audit))],
        provenance=dict(root=str(root.resolve()),batch=batch,series='DTWEXBGS',basis='same-vintage nominal broad dollar index',audit=audit))
    pub=analytics.latest('governance/usd-broad-index')
    if pub['version']!=batch:raise ValueError('USD publication not committed')
    write_json(source/'published-batch.json',pub)
    print(json.dumps(dict(batch=batch,accepted=len(accepted),excluded=len(excluded),history_rows=len(history),root=str(root.resolve()))))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source',type=Path,default=Path('research/usd-data'));p.add_argument('--root',type=Path,required=True)
    args=p.parse_args();publish(args.source,args.root)
