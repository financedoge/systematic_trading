"""Freeze public historical ITOT holdings and underlying equity bars for research."""
from __future__ import annotations

import argparse
import calendar
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
from datetime import UTC, date, datetime, timedelta
import io
import json
from pathlib import Path
import re
import shutil
import sys
import time
from urllib.parse import urlencode, quote
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.live.trading_calendar import is_us_trading_day

BASE = 'https://www.blackrock.com/ae/intermediaries/products/239724/ishares-core-sp-total-us-stock-market-etf/1492884494502.ajax'
SECTORS = ['Communication', 'Consumer Discretionary', 'Consumer Staples', 'Energy',
           'Financials', 'Health Care', 'Industrials', 'Information Technology',
           'Materials', 'Real Estate', 'Utilities']
ALIASES = {'FB': 'META', 'ANTM': 'ELV', 'BRKB': 'BRK-B', 'BFB': 'BF-B'}


def download(url):
    for attempt in range(2):
        try:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0'}), timeout=20) as r:
                return r.read()
        except Exception as error:
            if getattr(error, 'code', None) in (400, 404) or attempt:
                raise
            time.sleep(10 if getattr(error, 'code', None) == 429 else 1)


def parse_holdings(raw, expected):
    content = raw.decode('utf-8-sig')
    lines = content.splitlines()
    supplied = list(csv.reader([lines[1]]))[0][1]
    actual = None
    for fmt in ('%d-%b-%Y', '%b %d, %Y'):
        try:
            actual = datetime.strptime(supplied, fmt).date().isoformat()
            break
        except ValueError:
            pass
    if actual != expected:
        raise ValueError(f'Holdings date mismatch: {actual} != {expected}')
    head = next(i for i, line in enumerate(lines) if line.startswith('Ticker,Name,Sector,'))
    rows, excluded = [], []
    for row in csv.DictReader(io.StringIO('\n'.join(lines[head:]))):
        if row.get('Asset Class') != 'Equity':
            continue
        try:
            value = float(row['Market Value'].replace(',', ''))
            weight = float(row['Weight (%)'].replace(',', ''))
        except (ValueError, KeyError, AttributeError):
            excluded.append(row)
            continue
        ticker = row['Ticker'].strip()
        sector = row['Sector'].replace('Communication Services', 'Communication')
        if sector not in SECTORS or row.get('Currency') != 'USD' or not re.fullmatch(r'[A-Z0-9.\-/]+', ticker) or value <= 0:
            excluded.append(row)
            continue
        yahoo = ALIASES.get(ticker, ticker.replace('.', '-').replace('/', '-'))
        rows.append(dict(ticker=ticker, yahoo=yahoo, name=row['Name'], sector=sector,
                         market_value=value, weight_pct=weight, exchange=row.get('Exchange')))
    if len(rows) < 1000 or len({r['sector'] for r in rows}) != 11:
        raise ValueError(f'Incomplete holdings: {expected}: {len(rows)}')
    return rows, excluded


def snapshot(root, day):
    name = day.isoformat()
    raw_path, parsed = root/'holdings_raw'/f'{name}.csv', root/'holdings'/f'{name}.json'
    if parsed.exists():
        return json.loads(parsed.read_text())
    url = BASE+'?'+urlencode(dict(fileType='csv', fileName='ITOT_holdings', dataType='fund', asOfDate=day.strftime('%Y%m%d')))
    raw = download(url)
    raw_path.write_bytes(raw)
    rows, excluded = parse_holdings(raw, name)
    result = dict(as_of=name, assumed_available=(day+timedelta(days=45)).isoformat(),
                  availability_status='45-calendar-day assumption; publication vintage not certified',
                  url=url, retrieved_at=datetime.now(UTC).isoformat(), rows=rows,
                  excluded=excluded, raw_sha256=sha256(raw_path))
    write_json(parsed, result)
    return result


def bars(root, ticker, start, end):
    path, metadata = root/'bars_raw'/f'{ticker}.json', root/'bars_metadata'/f'{ticker}.json'
    if metadata.exists():
        return json.loads(metadata.read_text())
    params = dict(period1=int(datetime.fromisoformat(start).replace(tzinfo=UTC).timestamp()),
                  period2=int((datetime.fromisoformat(end)+timedelta(days=1)).replace(tzinfo=UTC).timestamp()),
                  interval='1d', events='div,splits')
    url = 'https://query1.finance.yahoo.com/v8/finance/chart/'+quote(ticker)+'?'+urlencode(params)
    result = dict(ticker=ticker, url=url, retrieved_at=datetime.now(UTC).isoformat())
    try:
        raw = download(url)
        path.write_bytes(raw)
        data = json.loads(raw)['chart']['result'][0]
        meta = data['meta']
        if meta.get('currency') != 'USD' or meta.get('instrumentType') != 'EQUITY':
            raise ValueError('Expected USD equity: '+str({k: meta.get(k) for k in ('symbol', 'currency', 'instrumentType')}))
        result.update(status='ok', sha256=sha256(path), observations=len(data.get('timestamp', [])),
                      name=meta.get('longName', meta.get('shortName')), symbol=meta.get('symbol'),
                      first_trade=meta.get('firstTradeDate'), exchange=meta.get('exchangeName'))
    except Exception as error:
        result.update(status='unavailable', error=str(error))
    write_json(metadata, result)
    time.sleep(.1)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--stage', choices=['holdings', 'bars', 'all'], default='all')
    parser.add_argument('--workers', type=int, default=6)
    args = parser.parse_args()
    root = args.root
    if (root/'data_manifest.json').exists():
        for name, expected in json.loads((root/'data_manifest.json').read_text()).items():
            if sha256(root/name) != expected:
                raise ValueError('Frozen input changed: '+name)
        print('Frozen dataset verified; use a new root to fetch another vintage.')
        return
    root.mkdir(parents=True, exist_ok=True)
    alias_source = Path(__file__).resolve().parents[1]/'config/underlying-sector-symbol-aliases-v1.json'
    if alias_source.exists() and not (root/'symbol_aliases.json').exists():
        shutil.copyfile(alias_source, root/'symbol_aliases.json')
    for folder in ('holdings', 'holdings_raw', 'bars_raw', 'bars_metadata'):
        (root/folder).mkdir(exist_ok=True)
    protocol = dict(created_at=datetime.now(UTC).isoformat(), universe='Historical monthly ITOT equity holdings; broad US listed-equity proxy',
        first_snapshot='2018-10-31', last_snapshot='2026-08-31', end='2026-09-24', signal_start='2019-01-02',
        publication_lag_days=45, aliases=ALIASES, sectors=SECTORS,
        volume='sum underlying stock shares by dated sector; primary sum(provider close * volume)',
        returns='daily sector return from constituent adjusted-close returns, prior-observation snapshot portfolio-value weights; equal-weight sensitivity',
        coverage_gate='each sector >=95% of lagged snapshot portfolio value and >=70% of names; missing values never treated as zero volume/return',
        member_turnover='on lagged monthly snapshot activation, volume feature differences use same constituent list across backward stencil',
        derivatives='raw backward lag 1 plus causal EMA(10) lag 10; fixed definitions, no outcome tuning',
        horizons=[20,60,120], data_limitations=['Unknown historical publication/revision vintages', 'Missing delisted Yahoo histories',
            'Ticker reuse/identity requires audit', 'Fund is broad-market sample, not full exchange census', 'Volume is activity, not net capital inflow'])
    if not (root/'protocol.json').exists():
        write_json(root/'protocol.json', protocol)
    protocol = json.loads((root/'protocol.json').read_text())
    if args.stage in ('all', 'holdings'):
        dates = []
        for year in range(2018, 2027):
            for month in range(1, 13):
                day = date(year, month, calendar.monthrange(year, month)[1])
                while not is_us_trading_day(day):
                    day -= timedelta(days=1)
                if protocol['first_snapshot'] <= day.isoformat() <= protocol['last_snapshot']:
                    dates.append(day)
        snapshots = []
        with ThreadPoolExecutor(max_workers=3) as pool:
            for i, item in enumerate(pool.map(lambda d: snapshot(root, d), dates), 1):
                snapshots.append(item)
                if i % 12 == 0 or i == len(dates):
                    print('holdings', i, len(dates), item['as_of'], len(item['rows']), flush=True)
        write_json(root/'holdings_manifest.json', {p.relative_to(root).as_posix(): sha256(p) for folder in ('holdings','holdings_raw') for p in (root/folder).glob('*')})
    if args.stage in ('all', 'bars'):
        snapshots = [json.loads(p.read_text()) for p in sorted((root/'holdings').glob('*.json'))]
        alias_path = root/'symbol_aliases.json'
        supplemental = set(json.loads(alias_path.read_text())['aliases'].values()) if alias_path.exists() else set()
        symbols = sorted({r['yahoo'] for s in snapshots for r in s['rows']} | supplemental)
        ok, failed = 0, 0
        with ThreadPoolExecutor(max_workers=min(max(args.workers, 1), 12)) as pool:
            futures = [pool.submit(bars, root, s, '2018-10-01', protocol['end']) for s in symbols]
            for i, future in enumerate(as_completed(futures), 1):
                result = future.result()
                ok += result['status'] == 'ok'
                failed += result['status'] != 'ok'
                if i % 100 == 0 or i == len(symbols):
                    print('bars', i, len(symbols), 'ok', ok, 'unavailable', failed, flush=True)
        write_json(root/'download_summary.json', dict(symbols=len(symbols), ok=ok, unavailable=failed, snapshots=len(snapshots)))
        shutil.copyfile(__file__, root/'fetch_script.py')
        inputs = [p for folder in ('holdings', 'holdings_raw', 'bars_raw', 'bars_metadata') for p in (root/folder).glob('*')]
        inputs += [root/name for name in ('protocol.json', 'symbol_aliases.json', 'download_summary.json', 'fetch_script.py', 'holdings_manifest.json') if (root/name).exists()]
        write_json(root/'data_manifest.json', {p.relative_to(root).as_posix(): sha256(p) for p in inputs})


if __name__ == '__main__':
    main()
