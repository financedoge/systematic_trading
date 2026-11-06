"""Acquire dated SEC source evidence for the P4.21 December 2024 pilot."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import struct
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path

import requests

from systematic_trading.config import AppSettings

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'research/p421-quarter-20261104-v1'
CACHE = ROOT / 'var/research/p421-quarter-20261104-v1'
PINS = ROOT / 'research/p421-coverage-20261104-v1/pins.json'
SEC = 'https://www.sec.gov'
REGISTRY = SEC + '/files/investment/data/other/investment-company-series-and-class-information/investment-company-series-class-2024.csv'
TARGET = '2024-12-31'
TRUSTS = {
    'SPY': (884394, '811-06125', 'SPDR S&P 500 ETF TRUST', '000119312524017688/d315180d497.htm'),
    'MDY': (936958, '811-08972', 'SPDR S&P MIDCAP 400 ETF TRUST', '000119312524017907/d657320d497.htm'),
}
TABLES = ('SUBMISSION.tsv', 'REGISTRANT.tsv', 'FUND_REPORTED_INFO.tsv')
QUARTERS = ('2024q4','2025q1','2025q2','2025q3','2025q4','2026q1','2026q2','2026q3')


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n', encoding='utf8')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source(key, url, prefix=None):
    """Cache exact decoded response bytes and verify every read against the receipt."""
    path = CACHE / (key + '.gz')
    receipt = CACHE / (key + '.json')
    if path.exists() and receipt.exists():
        meta = read(receipt)
        raw = gzip.decompress(path.read_bytes())
        if meta['url'] != url or digest(raw) != meta['sha256'] or meta['prefix'] != prefix:
            raise ValueError('Source cache mismatch ' + key)
        return raw, meta
    headers = {'User-Agent': AppSettings().sec_user_agent}
    if prefix:
        headers.update(Range=f'bytes=0-{prefix-1}', **{'Accept-Encoding': 'identity'})
    for attempt in range(4):
        try:
            with requests.get(url, headers=headers, timeout=(15, 75), stream=True) as r:
                r.raise_for_status()
                if prefix and (r.status_code != 206 or not re.fullmatch(
                        rf'bytes 0-{prefix-1}/[0-9]+', r.headers.get('Content-Range', ''))):
                    raise ValueError('Unexpected ZIP range ' + str(r.headers.get('Content-Range')))
                raw = r.content
                if prefix and len(raw) != prefix:
                    raise ValueError('Truncated ZIP range')
                meta = dict(url=url, prefix=prefix, sha256=digest(raw), bytes=len(raw),
                            content_range=r.headers.get('Content-Range'), retrieved_at=datetime.now(timezone.utc).isoformat())
            break
        except requests.RequestException as exc:
            if attempt == 3 or getattr(exc.response, 'status_code', None) in (403, 404):
                raise
            time.sleep(1 + attempt)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(gzip.compress(raw, mtime=0))
    save(receipt, meta)
    return raw, meta


def members(raw):
    offset = 0
    found = {}
    while len(found) < len(TABLES) and offset + 30 <= len(raw):
        sig, _, flags, method, _, _, crc, size, full, nl, el = struct.unpack_from('<4s5H3I2H', raw, offset)
        if sig != b'PK\x03\x04' or flags & 8 or method != 8:
            raise ValueError('Unsupported ZIP header')
        name = raw[offset+30:offset+30+nl].decode()
        start = offset + 30 + nl + el
        offset = start + size
        if offset > len(raw):
            break
        if name in TABLES:
            data = zlib.decompress(raw[start:offset], -15)
            if len(data) != full or zlib.crc32(data) != crc:
                raise ValueError('Damaged member ' + name)
            found[name] = data
    return found


def inventory():
    pins = read(PINS)
    symbols = {s for s, group in pins['funds'].items() if group.startswith('equity_')}
    raw, reg = source('registry', REGISTRY)
    funds = {}
    for r in csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))):
        s = r['Class Ticker'].strip()
        if s in symbols:
            if s in funds:
                raise ValueError('Ambiguous registry ticker ' + s)
            funds[s] = dict(cik=int(r['CIK Number']), series=r['Series ID'], share_class=r['Class ID'],
                            name=r['Series Name'], file=r['Reporting File Number'], source=REGISTRY)
    for s, (cik, file, name, doc) in TRUSTS.items():
        funds[s] = dict(cik=cik, file=file, name=name, series=None, share_class=None,
                        source=f'{SEC}/Archives/edgar/data/{cik}/{doc}')
    if set(funds) != symbols:
        raise ValueError('Incomplete fund inventory')
    save(OUT / 'funds.json', funds)
    return funds, reg


def quarter(q, funds):
    url = f'{SEC}/files/dera/data/form-n-port-data-sets/{q}_nport.zip'
    for size in (2300001, 4500000, 8000000):
        raw, receipt = source(f'zip-{q}-{size}', url, size)
        files = members(raw)
        if len(files) == len(TABLES):
            break
    if len(files) != len(TABLES):
        raise ValueError('Metadata beyond prefix ' + q)
    parsed = {k: {r['ACCESSION_NUMBER']: r for r in csv.DictReader(io.StringIO(v.decode('utf-8-sig')), delimiter='\t')}
              for k, v in files.items()}
    lookup = {(r['cik'], r['series']): s for s, r in funds.items()}
    matched = []
    for a, portfolio in parsed[TABLES[2]].items():
        issuer = parsed[TABLES[1]][a]
        s = lookup.get((int(issuer['CIK']), portfolio['SERIES_ID'] or None))
        if not s:
            continue
        sub = parsed[TABLES[0]][a]
        as_of = datetime.strptime(sub['REPORT_DATE'], '%d-%b-%Y').date().isoformat()
        if as_of != TARGET and q != '2025q1':
            continue
        if s in TRUSTS and (issuer['FILE_NUM'] != funds[s]['file'] or issuer['REGISTRANT_NAME'].upper() != funds[s]['name'].upper()):
            raise ValueError('Trust mismatch ' + s)
        matched.append(dict(symbol=s, accession=a, as_of=as_of, cik=int(issuer['CIK']),
                            series=portfolio['SERIES_ID'] or None, filing=sub['SUB_TYPE'], nav=portfolio['NET_ASSETS'],
                            filed=datetime.strptime(sub['FILING_DATE'], '%d-%b-%Y').date().isoformat()))
    return dict(quarter=q, source=receipt, member_sha256={k: digest(v) for k,v in files.items()}, records=matched)


def capture(record):
    acc = record['accession']
    cik = record['cik']
    base = f'{SEC}/Archives/edgar/data/{cik}/{acc.replace("-", "")}/'
    xml, xml_meta = source(acc + '-xml', base + 'primary_doc.xml')
    # Date-stamped daily EDGAR dissemination feed proves public presence by end of day.
    day = record['filed']
    q = (int(day[5:7]) - 1) // 3 + 1
    daily, daily_meta = source('daily-' + day, f'{SEC}/Archives/edgar/daily-index/{day[:4]}/QTR{q}/master.{day.replace("-", "")}.idx')
    line = [v for v in daily.decode('latin1').splitlines() if v.endswith('/' + acc + '.txt')]
    if len(line) != 1 or line[0].split('|')[0:1] != [str(cik)] or line[0].split('|')[2:4] != [record['filing'],day.replace('-', '')]:
        raise ValueError('Accession missing or mismatched in public dissemination feed ' + acc)
    index, index_meta = source(acc + '-index', base + acc + '-index.htm')
    match = re.search(rb'Accepted\s*</div>\s*<div[^>]*>\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', index)
    if not match:
        raise ValueError('Missing EDGAR acceptance ' + acc)
    return dict(**record, xml=xml_meta, index=index_meta, dissemination=daily_meta,
                dissemination_row=line[0], accepted_new_york=match[1].decode())


def run(stage):
    funds, reg = inventory()
    source('ftd-dec', SEC + '/files/data/fails-deliver-data/cnsfails202412b.zip')
    quarters = QUARTERS
    if stage == 'primary':
        quarters = ['2025q1']
    for q in quarters:
        try:
            item = quarter(q, funds)
        except requests.HTTPError as exc:
            if q == '2025q1' or exc.response.status_code not in (403, 404):
                raise
            item = dict(quarter=q, unavailable_http=exc.response.status_code)
        save(OUT / ('index-' + q + '.json'), item)
        print(q, len(item.get('records', [])), flush=True)
        for r in item.get('records', []):
            if r['as_of'] == TARGET:
                result = capture(r)
                save(OUT / 'filings' / (r['accession'] + '.json'), result)
                print(r['symbol'], r['accession'], flush=True)
    save(OUT / 'sources.json', dict(registry=reg, prior_pins_sha256=digest(PINS.read_bytes())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['primary','scan'])
    run(parser.parse_args().stage)
