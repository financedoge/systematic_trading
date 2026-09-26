"""Freeze public archive subsets and build coherent-window constituent features.

Archive OHLC conventions are retained, never silently called unadjusted turnover.
One provider supplies an entire stock's backward window; no price-scale splicing.
"""
from __future__ import annotations

import argparse
import csv
from datetime import UTC, date, datetime, timedelta
import io
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np

from analyze_underlying_sectors import compatible_name
from run_constituent_research import verify_manifest
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.live.trading_calendar import is_us_trading_day
from systematic_trading.research.constituent_signals import WINDOW, cohort_features, threshold


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def extract(source, archives, output):
    """Extract only observed-universe files; preserve exact CSV and source metadata."""
    if (output/'archive_manifest.json').exists():
        verify_manifest(output,'archive_manifest.json')
        print('Frozen archive subset verified; use a new root for another vintage.',flush=True)
        return
    snapshots = [read_json(p) for p in sorted((source/'holdings').glob('*.json'))]
    symbols = {r['yahoo'] for s in snapshots for r in s['rows']}
    symbols |= set(read_json(source/'symbol_aliases.json')['aliases'].values())
    records = []
    for provider in ('yahoo2020', 'stooq2017'):
        folder = output/provider
        folder.mkdir(parents=True, exist_ok=True)
        archive = archives/(provider+'.zip')
        meta = read_json(archives/(provider+'.metadata.json'))
        with zipfile.ZipFile(archive) as z:
            names = set(z.namelist())
            identities = {r['Symbol']: r for r in csv.DictReader(io.StringIO(z.read('symbols_valid_meta.csv').decode()))} if provider == 'yahoo2020' else {}
            for symbol in sorted(symbols):
                name = f'stocks/{symbol}.csv' if provider == 'yahoo2020' else f'Data/Stocks/{symbol.lower()}.us.txt'
                if name not in names:
                    continue
                identity = identities.get(symbol)
                if provider == 'yahoo2020' and (not identity or identity['ETF'] != 'N'):
                    continue
                raw = z.read(name)
                rows = list(csv.DictReader(io.StringIO(raw.decode())))
                if not rows:
                    continue
                last = rows[-1]['Date']
                if provider == 'stooq2017':
                    # No security-name field: require contemporaneous issuer holdings.
                    candidates = [(s['as_of'], r['name']) for s in snapshots if s['as_of'] <= last
                                  and (date.fromisoformat(last)-date.fromisoformat(s['as_of'])).days < 150
                                  for r in s['rows'] if r['yahoo'] == symbol]
                    if not candidates:
                        continue
                    identity_name = max(candidates)[1]
                else:
                    identity_name = identity['Security Name']
                path = folder/(symbol+'.csv')
                path.write_bytes(raw)
                records.append(dict(provider=provider, symbol=symbol, name=identity_name,
                    path=path.relative_to(output).as_posix(), raw_sha256=sha256(path),
                    archive_member=name, archive_sha256=sha256(archive) if not records or records[-1]['provider'] != provider else records[-1]['archive_sha256'],
                    archive_metadata=meta, first_date=rows[0]['Date'], last_date=last,
                    identity_method='publisher security-name metadata' if identity else 'ticker matched to dated issuer holdings near archive end; not security-ID certified',
                    price_convention='Yahoo Close plus Adj Close' if identity else 'dividend/split-adjusted OHLC; dollar activity is an adjusted proxy',
                    historical_available_at=None))
        print('EXTRACT', provider, sum(r['provider'] == provider for r in records), flush=True)
    write_json(output/'archive_index.json', records)
    shutil.copyfile(__file__, output/'prepare_source.py')
    write_json(output/'archive_manifest.json', {p.relative_to(output).as_posix(): sha256(p) for p in output.rglob('*') if p.is_file()})


def numeric(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return float('nan')


def build(protocol, output, *, use_stooq=True):
    source, archive = Path(protocol['stock_root']), Path(protocol['archive_root'])
    verify_manifest(source, 'data_manifest.json')
    verify_manifest(archive, 'archive_manifest.json')
    snaps = [read_json(p) for p in sorted((source/'holdings').glob('*.json'))]
    aliases = read_json(source/'symbol_aliases.json')['aliases']
    for s in snaps:
        for r in s['rows']:
            r['yahoo'] = aliases.get(r['ticker'], r['yahoo'])
    symbols = {r['yahoo'] for s in snaps for r in s['rows']}
    start, end = date(2011, 1, 3), date.fromisoformat(protocol['end'])
    days = [(start+timedelta(days=i)).isoformat() for i in range((end-start).days+1) if is_us_trading_day(start+timedelta(days=i))]
    did = {d:i for i,d in enumerate(days)}
    series = []
    for symbol in sorted(symbols):
        meta = read_json(source/'bars_metadata'/f'{symbol}.json')
        if meta['status'] != 'ok':
            continue
        raw = read_json(source/'bars_raw'/f'{symbol}.json')['chart']['result'][0]
        quote, adj = raw['indicators']['quote'][0], raw['indicators'].get('adjclose', [{}])[0].get('adjclose', [])
        rows = {datetime.fromtimestamp(t, UTC).date().isoformat(): (quote['close'][i], quote['volume'][i], adj[i] if i < len(adj) else None)
                for i,t in enumerate(raw.get('timestamp', []))}
        series.append(dict(symbol=symbol, name=meta.get('name'), provider='yahoo2026', rows=rows))
    for item in read_json(archive/'archive_index.json'):
        if item['symbol'] not in symbols or (item['provider'] == 'stooq2017' and not use_stooq):
            continue
        rows = list(csv.DictReader(io.StringIO((archive/item['path']).read_text(encoding='utf8'))))
        series.append(dict(**{k:item[k] for k in ('symbol','name','provider')},
            rows={r['Date']:(r['Close'], r['Volume'], r.get('Adj Close', r['Close'])) for r in rows}))
    c, v, a = [np.full((len(days), len(series)), np.nan) for _ in range(3)]
    lookup = {}
    for col, item in enumerate(series):
        lookup.setdefault(item['symbol'], []).append(col)
        for day, row in item.pop('rows').items():
            if day in did:
                c[did[day],col], v[did[day],col], a[did[day],col] = map(numeric,row)
    good = np.isfinite(c)&(c>0)&np.isfinite(v)&(v>=0)&np.isfinite(a)&(a>0)
    cumulative = np.vstack([np.zeros((1,len(series)),int), good.cumsum(axis=0)])
    complete = np.zeros_like(good)
    complete[WINDOW-1:] = cumulative[WINDOW:]-cumulative[:-WINDOW] == WINDOW
    sectors = read_json(source/'protocol.json')['sectors']
    features = {}
    for lag in (45,60):
        out = features[str(lag)] = {}
        activations = [(date.fromisoformat(s['as_of'])+timedelta(days=lag)).isoformat() for s in snaps]
        for ix,s in enumerate(snaps):
            rows = s['rows']
            # Duplicate ticker identities are excluded; never count a bar twice.
            candidates = [[i for i in lookup.get(r['yahoo'],[]) if compatible_name(r['name'],series[i]['name'],r['ticker'])]
                          if sum(x['yahoo']==r['yahoo'] for x in rows)==1 else [] for r in rows]
            for j,day in enumerate(days):
                if j < WINDOW-1 or day < activations[ix] or day >= (activations[ix+1] if ix+1<len(snaps) else '9999'):
                    continue
                if (date.fromisoformat(day)-date.fromisoformat(s['as_of'])).days > 140:
                    continue
                ids = [next((i for i in ids if complete[j,i]), -1) for ids in candidates]
                accepted = np.array([i>=0 for i in ids])
                select = np.ix_(np.arange(j-WINDOW+1,j+1), np.maximum(ids,0))
                values = cohort_features(c[select],v[select],a[select],np.array([sectors.index(r['sector']) for r in rows]),
                                         np.array([r['market_value'] for r in rows]),accepted)
                provider_values = {p:sum(r['market_value'] for i,r in zip(ids,rows) if i>=0 and series[i]['provider']==p)/sum(r['market_value'] for r in rows)
                                   for p in ('yahoo2026','yahoo2020','stooq2017')}
                out[day] = dict(known_through=day,snapshot=s['as_of'],assumed_available=activations[ix],historical_available_at=None,
                                provider_value_coverage=provider_values,**values)
        print('FEATURES',lag,len(out),flush=True)
    etf = read_json(Path(protocol['etf_snapshot'])/'bars.json')['SPY']
    for i in range(63,len(etf)):
        for out in features.values():
            row=out.get(etf[i]['trade_date'])
            if row and row['scores']:
                row['scores']['price_control']=threshold(float(etf[i]['close'])/float(etf[i-63]['close'])-1,.02)
    write_json(output/'features.json',features)
    audit = {lag:{str(year):dict(sessions=len(part),qualified95=sum(r['value_coverage']>=.95 and r['name_coverage']>=.7 for r in part),
        qualified90=sum(r['value_coverage']>=.9 and r['name_coverage']>=.7 for r in part),
        mean_value=float(np.mean([r['value_coverage'] for r in part])),
        mean_stooq=float(np.mean([r['provider_value_coverage']['stooq2017'] for r in part])))
        for year in range(2012,2027) if (part:=[r for d,r in out.items() if d.startswith(str(year))])} for lag,out in features.items()}
    write_json(output/'coverage.json',audit)
    print(json.dumps(audit['45'],indent=2),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--extract',action='store_true')
    p.add_argument('--yahoo-only',action='store_true')
    args=p.parse_args()
    protocol=read_json(args.protocol)
    args.root.mkdir(parents=True,exist_ok=True)
    if args.extract:
        extract(Path(protocol['stock_root']),Path(protocol['download_archive_root']),Path(protocol['archive_root']))
    else:
        build(protocol,args.root,use_stooq=not args.yahoo_only)


if __name__=='__main__':
    main()
