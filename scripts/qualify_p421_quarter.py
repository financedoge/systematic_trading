"""Qualify one dated holdings cohort. This runner computes coverage, never returns."""
import csv
import gzip
import io
import json
import math
import zipfile
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from functools import lru_cache
from xml.etree import ElementTree as ET

from acquire_p421_quarter import CACHE, OUT, PINS, QUARTERS, TARGET, digest, read, save
from systematic_trading.live.trading_calendar import previous_us_trading_day
from systematic_trading.research.governed_inputs import GovernedInputs
from pathlib import Path

DECISION = date(2025, 3, 3)
CUTOFF = previous_us_trading_day(DECISION)
FTD = 'https://www.sec.gov/files/data/fails-deliver-data/cnsfails202412b.zip'
FIELDS = [f'{base}_{key}' for base in ('raw','adjusted') for key in ('open','high','low','close')] + ['raw_volume']


def window_days(cutoff):
    days = [cutoff]
    while len(days) < 253:
        days.append(previous_us_trading_day(days[-1]))
    return [d.isoformat() for d in reversed(days)]


def complete_window(rows, days):
    return ([r['trade_date'] for r in rows] == days and
            all(all(r.get(k) is not None and math.isfinite(r[k]) and r[k] > 0 for k in FIELDS) for r in rows))


def eligible(filings, cutoff):
    """Day-granular public evidence. Each filing first qualifies after that day's close."""
    latest = {}
    for r in sorted(filings, key=lambda x: (x['filed'], x['accepted_new_york'])):
        if r['as_of'] != TARGET or r['filed'] >= cutoff.isoformat():
            continue
        if r['symbol'] in latest and r['filing'] != 'NPORT-P/A':
            raise ValueError('Conflicting original filings')
        latest[r['symbol']] = r
    return latest


def cached(key, meta):
    raw = gzip.decompress((CACHE / (key+'.gz')).read_bytes())
    if digest(raw) != meta['sha256']:
        raise ValueError('Changed SEC input ' + key)
    return raw


def child_text(el, key):
    return el.findtext('{*}' + key)


def portfolio(f, fund):
    a = f['accession']
    raw = cached(a + '-xml', f['xml'])
    root = ET.fromstring(raw)
    gen = root.find('.//{*}genInfo')
    info = root.find('.//{*}fundInfo')
    classes = [el.text for el in root.findall('.//{*}seriesClassInfo/{*}classId')]
    if (child_text(gen, 'repPdDate') != TARGET or int(child_text(gen, 'regCik')) != fund['cik']
            or child_text(gen, 'seriesId') != fund['series'] or child_text(gen, 'regFileNumber') != fund['file']
            or (fund['share_class'] and fund['share_class'] not in classes)
            or root.findtext('.//{*}headerData/{*}submissionType') != f['filing']):
        raise ValueError('Fund/period mismatch in original XML ' + a)
    dest = OUT / 'filings' / (a + '.xml.gz')
    dest.write_bytes(gzip.compress(raw, mtime=0))
    assets, liabilities, nav, cash = [Decimal(child_text(info, key)) for key in
                                    ('totAssets', 'totLiabs', 'netAssets', 'cshNotRptdInCorD')]
    if nav != Decimal(f['nav']) or abs(assets-liabilities-nav) > Decimal('.02') or nav <= 0:
        raise ValueError('Fund balance sheet mismatch ' + a)
    positions = []
    for i, el in enumerate(root.findall('.//{*}invstOrSec'), 1):
        row = {k: child_text(el, k) for k in ('name','title','cusip','assetCat','invCountry','curCd','valUSD','pctVal')}
        ids = el.findall('{*}identifiers/*')
        row['identifiers'] = [{**e.attrib, 'type': e.tag.split('}')[-1]} for e in ids]
        if row['assetCat'] is None:
            row['assetCat'] = el.find('{*}assetConditional').get('assetCat')
        row['line'] = i
        positions.append(row)
    value = sum(Decimal(p['valUSD']) for p in positions)
    filed_pct = sum(Decimal(p['pctVal']) for p in positions)
    if abs(filed_pct - 100*value/nav) > Decimal('.02'):
        raise ValueError('Sum of filed position weights disagrees with line values ' + a)
    return positions, dict(nav_usd=str(nav), total_assets_usd=str(assets), liabilities_usd=str(liabilities),
                           positions_usd=str(value), filed_positions_pct_nav=float(filed_pct), cash_outside_positions_usd=str(cash),
                           other_net_assets_usd=str(nav-value-cash), categories=dict(Counter(p['assetCat'] for p in positions)))


def security_keys(p):
    keys = {('isin', i['value']) for i in p['identifiers']
            if i['type'] == 'isin' and len(i['value']) == 12 and i['value'].isalnum()}
    cusip = p['cusip'] or ''
    if len(cusip) == 9 and cusip not in ('000000000','999999999') and cusip.isalnum():
        keys.add(('cusip', cusip))
    return sorted(keys)


def observe(links, reverse, key, symbol, evidence):
    if symbol:
        links[key][symbol].add(evidence)
        reverse[key[0], symbol].add(key[1])


def unique_symbol(keys, links, reverse):
    candidates = defaultdict(set)
    for key in keys:
        for symbol, evidence in links.get(key, {}).items():
            if len(reverse[key[0], symbol]) != 1:
                return None
            candidates[symbol].update(evidence)
    if len(candidates) == 1:
        symbol, evidence = next(iter(candidates.items()))
        return symbol, sorted(evidence)
    return None


def collect_links(portfolios, filings):
    # SEC settlement-date identifier observations only. No external price or activity input.
    receipt = read(CACHE/'ftd-dec.json')
    if receipt['url'] != FTD:
        raise ValueError('Unexpected FTD source')
    raw = cached('ftd-dec', receipt)
    links = defaultdict(lambda: defaultdict(set))
    reverse = defaultdict(set)
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        with z.open('cnsfails202412b') as f:
            for r in csv.DictReader(io.TextIOWrapper(f, encoding='latin1'), delimiter='|'):
                if r['SETTLEMENT DATE'] == TARGET.replace('-', ''):
                    for key in security_keys(dict(cusip=r['CUSIP'].strip(), identifiers=[])):
                        observe(links, reverse, key, r['SYMBOL'].strip(), 'SEC settlement-date table')
    for s, (positions, _) in portfolios.items():
        for p in positions:
            for i in p['identifiers']:
                if i['type'] == 'ticker':
                    for key in security_keys(p):
                        observe(links, reverse, key, i['value'], filings[s]['accession'])
    return links, reverse, receipt


def audit():
    funds = read(OUT/'funds.json')
    pins = read(PINS)
    if digest(PINS.read_bytes()) != read(OUT/'sources.json')['prior_pins_sha256']:
        raise ValueError('Changed cohort or price pin')
    g = GovernedInputs(Path(pins['price']['root']), pins['price']['batch'])
    catalog = {r['symbol']: r for r in read(g.checked('catalog.json'))}
    reports = [read(f) for f in (OUT/'filings').glob('*.json')]
    ordered = eligible(reports, CUTOFF)
    ports = {s: portfolio(f, funds[s]) for s,f in ordered.items()}
    links, reverse, ftd = collect_links(ports, ordered)
    dates = window_days(CUTOFF)

    @lru_cache(maxsize=None)
    def price_status(symbol):
        entry = catalog.get(symbol, {})
        if entry.get('status') != 'audited_with_limitations':
            return entry.get('status','absent')
        audit_record = g.audit(symbol)
        if audit_record['status'] != entry['status']:
            raise ValueError('Audit/catalog disagreement ' + symbol)
        # A future security-master schema requires a new, separately pinned identity join.
        if audit_record.get('identity_status') != 'provider_identity_not_security_master_certified':
            raise ValueError('Review the price-side identity contract for ' + symbol)
        rows = g.rows(symbol, dates[0], dates[-1])
        return 'complete_window' if complete_window(rows, dates) else 'incomplete_window'

    details = []
    results = {}
    for s, (positions, totals) in sorted(ports.items()):
        equity = [p for p in positions if p['assetCat'] in ('EC','EP')]
        values = Counter()
        counts = Counter()
        for p in positions:
            if p['assetCat'] in ('EC','EP'):
                match = unique_symbol(security_keys(p), links, reverse)
                ticker, evidence = match if match else (None, [])
                state = price_status(ticker) if ticker else 'no_unique_dated_link'
                p.update(candidate_symbol=ticker, symbol_evidence=evidence, price_status=state,
                         certified_security_window=False)
                values[state] += abs(Decimal(p['valUSD']))
                counts[state] += 1
            details.append(dict(symbol=s, accession=ordered[s]['accession'], **p))
        denominator = sum(values.values())
        def pct(d):
            return 100*float(d/denominator)
        linked = len(equity) - counts['no_unique_dated_link']
        results[s] = dict(**totals, accession=ordered[s]['accession'], filed=ordered[s]['filed'],
                          rows=len(positions), equity_rows=len(equity), equity_abs_usd=str(denominator),
                          dated_link_rows=linked, dated_link_pct=pct(denominator-values['no_unique_dated_link']),
                          price_window_rows=counts['complete_window'], price_window_value_pct=pct(values['complete_window']),
                          certified_rows=0, certified_value_pct=0., states=dict(counts),
                          state_values_usd={k:str(v) for k,v in values.items()})
    (OUT/'positions.jsonl.gz').write_bytes(gzip.compress(('\n'.join(json.dumps(p, sort_keys=True) for p in details)+'\n').encode(), mtime=0))
    quarterly = [read(OUT / f'index-{q}.json') for q in QUARTERS]
    index_records = {r['accession'] for q in quarterly for r in q.get('records',[]) if r['as_of'] == TARGET}
    if index_records != {r['accession'] for r in reports}:
        raise ValueError('Incomplete filing capture')
    missing = {r['symbol']:r['as_of'] for r in read(OUT/'index-2025q1.json')['records'] if r['symbol'] not in ordered}
    if set(ordered) | set(missing) != set(funds):
        raise ValueError('Incomplete fund dispositions')
    monthly = {}
    for decision in [date(2025, 1, 2), date(2025, 2, 3), DECISION]:
        cutoff = previous_us_trading_day(decision)
        monthly[str(decision)] = dict(prior_close=str(cutoff), public_december_funds=sorted(eligible(reports, cutoff)))
    save(OUT/'qualification.json', dict(month=TARGET, first_monthly_decision=str(DECISION), monthly=monthly,
            prior_close_date=str(CUTOFF), window_start=dates[0], sessions=len(dates), funds=results,
            missing_december_at_cutoff=missing, checked_quarters=[q['quarter'] for q in quarterly if 'source' in q],
            unavailable_quarters=[q['quarter'] for q in quarterly if 'source' not in q],
            amendment_accessions=[r['accession'] for r in reports if r['filing']=='NPORT-P/A'],
            ftd=ftd, price_batch=pins['price']['batch'], price_files=g.used, distinct_candidate_tickers=price_status.cache_info().currsize))
    print({s:(r['equity_rows'],round(r['dated_link_pct'],2),round(r['price_window_value_pct'],2)) for s,r in results.items()})


if __name__ == '__main__':
    audit()
