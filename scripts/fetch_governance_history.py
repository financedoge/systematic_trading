"""Freeze public maximum-range Yahoo daily bars and action ledgers for governance.

This is a new source vintage, never a rewrite of earlier research evidence.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import json
from pathlib import Path
import shutil
import time
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from systematic_trading.market_data.analytics_store import digest, encode

BASE = Path('D:/systematic_trading_data/research')
ROOTS = ['underlying-sector-hhi-20260926-v1', 'ivv-constituents-2012-2026-v1']
ETFS = 'SPY DBC EWH EWJ EWY GLD HYG IEF LQD MCHI TLT VGK URTH IVV ITOT XLB XLC XLE XLF XLI XLK XLP XLRE XLU XLV XLY'.split()


def write(path, value):
    path.write_text(encode(value), encoding='utf8')


def inventory():
    symbols = {s: dict(symbol=s, holdings_names=[], roles=['ETF']) for s in ETFS}
    for root in ROOTS:
        for path in sorted((BASE/root/'holdings').glob('*.json')):
            snap = json.loads(path.read_text(encoding='utf8'))
            for r in snap['rows']:
                item = symbols.setdefault(r['yahoo'], dict(symbol=r['yahoo'], holdings_names=[], roles=[]))
                if r['name'] not in item['holdings_names']:
                    item['holdings_names'].append(r['name'])
                if root not in item['roles']:
                    item['roles'].append(root)
        for path in (BASE/root/'bars_metadata').glob('*.json'):
            symbols.setdefault(path.stem, dict(symbol=path.stem, holdings_names=[], roles=[root]))
    archive = BASE/'ivv-public-archive-subset-20260926-v1'/'archive_index.json'
    for r in json.loads(archive.read_text(encoding='utf8')):
        symbols.setdefault(r['symbol'], dict(symbol=r['symbol'], holdings_names=[], roles=['archive']))
    return dict(sorted(symbols.items()))


def fetch(root, symbol):
    meta_path = root/'metadata'/f'{symbol}.json'
    if meta_path.exists():
        return json.loads(meta_path.read_text(encoding='utf8'))
    # Negative period1 includes pre-1970 data. End includes every action known at
    # this retrieval; the governed price cutoff is separately frozen at Sept 24.
    params = dict(period1=-631152000, period2=int(datetime(2026, 9, 27, tzinfo=UTC).timestamp()),
                  interval='1d', events='div,splits,capitalGains')
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/'+quote(symbol, safe='')+'?'+urlencode(params)
    meta = dict(symbol=symbol, url=url, retrieved_at=datetime.now(UTC).isoformat(),
                requested_start='1950-01-01', requested_end='2026-09-27', historical_available_at=None)
    for attempt in range(2):
        try:
            with urlopen(Request(url, headers={'User-Agent':'Mozilla/5.0'}), timeout=25) as response:
                raw = response.read()
            (root/'raw'/f'{symbol}.json').write_bytes(raw)
            result = json.loads(raw)['chart']['result'][0]
            m = result['meta']
            meta.update(raw_sha256=digest(raw), name=m.get('longName', m.get('shortName')),
                        currency=m.get('currency'), instrument_type=m.get('instrumentType'),
                        provider_symbol=m.get('symbol'), observations=len(result.get('timestamp', [])),
                        event_counts={k:len(v) for k,v in result.get('events', {}).items()})
            if m.get('currency') != 'USD' or m.get('instrumentType') not in ('EQUITY', 'ETF'):
                raise ValueError('Unsupported currency or instrument type; retained for identity audit')
            meta['status'] = 'ok' if meta['observations'] else 'empty'
            break
        except Exception as exc:
            meta.update(status='unavailable', error=str(exc))
            if getattr(exc, 'code', None) in (400, 404) or isinstance(exc, ValueError) or attempt:
                break
            time.sleep(15 if getattr(exc, 'code', None) == 429 else 1)
    write(meta_path, meta)
    time.sleep(.15)
    return meta


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--workers',type=int,default=6)
    args=p.parse_args()
    root=args.root
    if (root/'manifest.json').exists():
        for name, expected in json.loads((root/'manifest.json').read_text(encoding='utf8')).items():
            if digest((root/name).read_bytes()) != expected:
                raise ValueError('Frozen input changed: '+name)
        print('Frozen governance source verified',flush=True)
        return
    for sub in ('raw','metadata'):
        (root/sub).mkdir(parents=True,exist_ok=True)
    symbols=inventory()
    write(root/'universe.json',symbols)
    counts={}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures=[pool.submit(fetch,root,s) for s in symbols]
        for i,f in enumerate(as_completed(futures),1):
            row=f.result()
            counts[row['status']]=counts.get(row['status'],0)+1
            if i%100==0:
                print('FETCH',i,'/',len(symbols),counts,flush=True)
    write(root/'summary.json',dict(symbols=len(symbols),counts=counts))
    shutil.copyfile(__file__,root/'fetch_source.py')
    write(root/'manifest.json',{p.relative_to(root).as_posix():digest(p.read_bytes()) for p in root.rglob('*') if p.is_file()})
    print('FROZEN',counts,flush=True)


if __name__=='__main__':
    main()
