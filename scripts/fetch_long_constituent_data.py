"""Freeze dated IVV holdings and public stock histories, preserving missing requests."""
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
from urllib.parse import urlencode

from fetch_underlying_sector_data import download, bars, ALIASES, SECTORS
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.live.trading_calendar import is_us_trading_day

BASE = 'https://www.blackrock.com/ae/intermediaries/products/239726/ishares-core-sp-500-etf/1492884494502.ajax'


def parse_snapshot(raw, expected):
    lines = raw.decode('utf-8-sig').splitlines()
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
    head = next(i for i, x in enumerate(lines) if x.startswith('Ticker,Name,Sector,'))
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
        sector = row['Sector'].replace('Communication Services', 'Communication').replace('Telecommunications', 'Communication')
        if sector not in SECTORS or row.get('Currency') != 'USD' or not re.fullmatch(r'[A-Z0-9.\-/]+', ticker) or value <= 0:
            excluded.append(row)
            continue
        rows.append(dict(ticker=ticker, yahoo=ALIASES.get(ticker, ticker.replace('.', '-').replace('/', '-')),
            name=row['Name'], sector=sector, sector_original=row['Sector'], market_value=value,
            weight_pct=weight, exchange=row.get('Exchange')))
    if not 450 <= len(rows) <= 550 or len({r['sector'] for r in rows}) < 9:
        raise ValueError(f'Incomplete IVV holdings: {expected}: {len(rows)}')
    return rows, excluded


def snapshot(root, day):
    name = day.isoformat()
    parsed, raw_path = root/'holdings'/f'{name}.json', root/'holdings_raw'/f'{name}.csv'
    if parsed.exists():
        return json.loads(parsed.read_text())
    url = BASE+'?'+urlencode(dict(fileType='csv', fileName='IVV_holdings', dataType='fund', asOfDate=day.strftime('%Y%m%d')))
    raw = download(url)
    raw_path.write_bytes(raw)
    if 'Fund Holdings as of,"-"' in raw.decode('utf-8-sig'):
        result = dict(as_of=name, status='unavailable', url=url, retrieved_at=datetime.now(UTC).isoformat(), raw_sha256=sha256(raw_path))
        write_json(root/'holdings_metadata'/f'{name}.json', result)
        return dict(**result, rows=[])
    rows, excluded = parse_snapshot(raw, name)
    result = dict(fund='IVV', as_of=name, assumed_available=(day+timedelta(days=45)).isoformat(),
        availability_status='45-calendar-day assumption; publication vintage not certified', url=url,
        retrieved_at=datetime.now(UTC).isoformat(), rows=rows, excluded=excluded, raw_sha256=sha256(raw_path))
    write_json(parsed, result)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--stage', choices=('all', 'holdings', 'bars'), default='all')
    args = p.parse_args()
    root = args.root.resolve()
    if (root/'data_manifest.json').exists():
        for n, h in json.loads((root/'data_manifest.json').read_text()).items():
            if sha256(root/n) != h:
                raise ValueError('Frozen data changed: '+n)
        print('Frozen source verified. Use a new root for a new vintage.')
        return
    root.mkdir(parents=True, exist_ok=True)
    for folder in ('holdings', 'holdings_raw', 'holdings_metadata', 'bars_raw', 'bars_metadata'):
        (root/folder).mkdir(exist_ok=True)
    if not (root/'protocol.json').exists():
        write_json(root/'protocol.json', dict(created_at=datetime.now(UTC).isoformat(),
            universe='Historical monthly IVV holdings; same-index proxy for SPY, not exact SPY membership',
            first_snapshot='2012-01-31', last_snapshot='2026-08-31', bars_start='2011-01-03', end='2026-09-24',
            sectors=SECTORS, publication_lag_days=45, research_only=True,
            limitations=['Historical publication/revision dates unknown', 'Public provider may omit delisted securities',
                'Telecommunications mapped to Communication label; original dated sector preserved',
                'Real Estate before GICS separation remains in original Financials classification',
                'No missing price/volume is imputed; coverage uses all dated holdings']))
        shutil.copyfile(Path(__file__).resolve().parents[1]/'config/underlying-sector-symbol-aliases-v1.json', root/'symbol_aliases.json')
    protocol = json.loads((root/'protocol.json').read_text())
    if args.stage in ('all', 'holdings'):
        dates = []
        for year in range(2012, 2027):
            for month in range(1, 13):
                day = date(year, month, calendar.monthrange(year, month)[1])
                while not is_us_trading_day(day):
                    day -= timedelta(days=1)
                if protocol['first_snapshot'] <= day.isoformat() <= protocol['last_snapshot']:
                    dates.append(day)
        with ThreadPoolExecutor(3) as pool:
            for i, s in enumerate(pool.map(lambda d: snapshot(root, d), dates), 1):
                if i % 12 == 0 or i == len(dates):
                    print('holdings', i, len(dates), s['as_of'], len(s['rows']), flush=True)
        write_json(root/'holdings_manifest.json', {p.relative_to(root).as_posix():sha256(p)
            for f in ('holdings','holdings_raw','holdings_metadata') for p in (root/f).glob('*')})
    if args.stage in ('all', 'bars'):
        snapshots = [json.loads(p.read_text()) for p in sorted((root/'holdings').glob('*.json'))]
        symbols = sorted({r['yahoo'] for s in snapshots for r in s['rows']} |
            set(json.loads((root/'symbol_aliases.json').read_text())['aliases'].values()))
        ok = 0
        with ThreadPoolExecutor(6) as pool:
            futures = [pool.submit(bars, root, s, protocol['bars_start'], protocol['end']) for s in symbols]
            for i, f in enumerate(as_completed(futures), 1):
                ok += f.result()['status'] == 'ok'
                if i % 100 == 0 or i == len(symbols):
                    print('bars', i, len(symbols), 'ok', ok, 'unavailable', i-ok, flush=True)
        write_json(root/'download_summary.json', dict(symbols=len(symbols), ok=ok, unavailable=len(symbols)-ok, snapshots=len(snapshots)))
        shutil.copyfile(__file__, root/'fetch_script.py')
        shutil.copyfile(Path(__file__).with_name('fetch_underlying_sector_data.py'), root/'fetch_helpers.py')
        files = [p for f in ('holdings','holdings_raw','holdings_metadata','bars_raw','bars_metadata') for p in (root/f).glob('*')]
        files += [root/n for n in ('protocol.json','symbol_aliases.json','download_summary.json','fetch_script.py','fetch_helpers.py','holdings_manifest.json')]
        write_json(root/'data_manifest.json', {p.relative_to(root).as_posix():sha256(p) for p in files})


if __name__ == '__main__':
    main()
