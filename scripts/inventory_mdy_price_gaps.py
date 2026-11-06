"""Inventory the 329 remaining MDY price reviews against the frozen pilot window."""
import gzip
import json
import math
from collections import Counter, defaultdict
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

from acquire_p421_quarter import OUT as PILOT, PINS, ROOT, TARGET, digest, read, save
from diagnose_mdy_price_audits import OUT as FIRST_FIVE
from qualify_p421_quarter import CUTOFF, FIELDS, window_days
from systematic_trading.lean.contracts import sha256
from systematic_trading.research.governed_inputs import GovernedInputs

OUT = ROOT / 'research/p421-mdy-inventory-20261105-v1'
ADJUSTED = [f'adjusted_{k}' for k in ('open','high','low','close')]
ALIAS_EVIDENCE = {
    'TPX': dict(symbol='SGI', effective='2025-02-18', evidence_date='2025-02-05',
                url='https://www.sec.gov/Archives/edgar/data/1206264/000120626425000023/a20250205pressreleasemattr.htm'),
    'ZI': dict(symbol='GTM', effective='2025-05-13', evidence_date='2025-05-12',
               url='https://infomemo.theocc.com/infomemos?number=56532', cusip='98980F104'),
    'LANC': dict(symbol='MZTI', effective='2025-07-01', evidence_date='2025-06-30',
                url='https://infomemo.theocc.com/infomemos?number=56786', cusip='513847103'),
    'ASGN': dict(symbol='EFOR', effective='2026-04-24', evidence_date='2026-04-08',
                url='https://investors.everforth.com/news/news-details/2026/ASGN-Incorporated-to-Change-Corporate-Name-and-NYSE-Ticker-to-Everforth/default.aspx'),
}


def valid(row, fields):
    return all(row.get(k) is not None and math.isfinite(row[k]) and row[k] > 0 for k in fields)


def priority_group(full, adjusted, comparison_full, available):
    if full:
        return 'complete_published_window'
    if adjusted:
        return 'adjusted_window_raw_or_volume_missing'
    if comparison_full:
        return 'complete_comparison_candidate'
    if available:
        return 'partial_window_records'
    return 'no_window_records'


def summarize(records, total):
    values = sum(Decimal(r['value_usd']) for r in records)
    return dict(count=len(records), value_usd=str(values), equity_pct=float(100*values/total))


def run():
    evidence = {}
    def checked(folder, relative):
        manifest = read(folder/'artifact-manifest.json')
        p = folder/relative
        h = sha256(p)
        if h != manifest[relative]:
            raise ValueError('Changed prior evidence ' + str(p))
        evidence[str(p.relative_to(ROOT))] = h
        return p

    prior = read(checked(FIRST_FIVE,'diagnosis.json'))
    pilot = read(checked(PILOT,'qualification.json'))
    if sha256(PINS) != prior['pins_sha256']:
        raise ValueError('Changed cohort pin')
    pins = read(PINS)['price']
    g = GovernedInputs(Path(pins['root']), pins['batch'])
    if (g.batch,g.parent.batch) != (prior['governed_batch'],prior['prior_batch']):
        raise ValueError('Changed governance chain')
    catalog = read(g.checked('catalog.json'))
    cat = {r['symbol']:r for r in catalog}
    with gzip.open(checked(PILOT,'positions.jsonl.gz'),'rt',encoding='utf8') as f:
        mdy = [r for line in f if (r:=json.loads(line))['symbol']=='MDY' and r['assetCat'] in ('EC','EP')]
    total = sum(abs(Decimal(r['valUSD'])) for r in mdy)
    if total != Decimal(pilot['funds']['MDY']['equity_abs_usd']):
        raise ValueError('Changed equity denominator')
    selected = sorted([r for r in mdy if r['candidate_symbol'] not in prior['ranking']
                       and r['price_status'] in ('review','unavailable')],key=lambda r:-abs(Decimal(r['valUSD'])))
    if Counter(r['price_status'] for r in selected) != dict(review=320,unavailable=9):
        raise ValueError('Unexpected assessment population')
    acc = pilot['funds']['MDY']['accession']
    raw = gzip.decompress(checked(PILOT,f'filings/{acc}.xml.gz').read_bytes())
    if digest(raw) != read(checked(PILOT,f'filings/{acc}.json'))['xml']['sha256']:
        raise ValueError('Changed original filing')
    filed = ElementTree.fromstring(raw).findall('.//{*}invstOrSec')
    days = window_days(CUTOFF)
    dayset = set(days)
    records = []

    def window(s):
        return g.rows(s,days[0],days[-1])

    for i, holding in enumerate(selected):
        symbol = holding['candidate_symbol']
        xml = filed[holding['line']-1]
        if (xml.find('{*}identifiers/{*}ticker').get('value') != symbol or
                xml.findtext('{*}cusip') != holding['cusip'] or
                Decimal(xml.findtext('{*}valUSD')) != Decimal(holding['valUSD'])):
            raise ValueError('Filed identity mismatch ' + symbol)
        current = g.audit(symbol)
        base = g.parent.audit(symbol)
        if current['status'] != cat[symbol]['status']:
            raise ValueError('Catalog status mismatch ' + symbol)
        inherited = current.get('previous_audit')
        if inherited and (inherited['batch'] != g.parent.batch or inherited['status'] != base['status']):
            raise ValueError('Unresolved earlier audit ' + symbol)
        rows = window(symbol)
        full_days = {r['trade_date'] for r in rows if valid(r,FIELDS)}
        adjusted_days = {r['trade_date'] for r in rows if valid(r,ADJUSTED)}
        counters = Counter(flag for r in rows for flag in r['quality_flags'])
        source_by_id = {r['source_id']:r for r in base['sources']}
        comparisons = defaultdict(set)
        comparison_bad = Counter()
        with gzip.open(g.parent.checked(f'comparisons/{symbol}.jsonl.gz'),'rt',encoding='utf8') as f:
            for line in f:
                r = json.loads(line)
                if r['trade_date'] in dayset:
                    if valid(r,('source_close','source_adjusted_close','source_volume')):
                        comparisons[r['source_id']].add(r['trade_date'])
                    else:
                        comparison_bad[r['source_id']] += 1
        source_windows = [dict(source_id=sid,provider=source_by_id[sid]['provider'] if 'provider' in source_by_id[sid] else 'see_source_id',
                    name=source_by_id[sid].get('name'),accepted=source_by_id[sid]['accepted'],
                    usable_close_volume_sessions=len(d),bad_rows=comparison_bad[sid]) for sid,d in comparisons.items()]
        comparison_full = any(d == dayset for d in comparisons.values())
        price_conflicts = set()
        volume_pairs = []
        for pair in base['overlaps']:
            price_conflicts.update(pair.get('conflicting_dates',[]))
            error = pair.get('volume_p99_scale_error')
            if error is not None and error > .05:
                volume_pairs.append(dict(anchor=pair['anchor'],candidate=pair['candidate'],first=pair['first'],last=pair['last'],
                    interval_intersects_window=pair['first'] <= days[-1] and pair['last'] >= days[0],p99_error=error))
        factor_failures = [dict(source_id=s['source_id'],**failure) for s in current['sources']
                           for failure in s.get('factor_failures',[])]
        action_events = []
        with gzip.open(g.checked(f'actions/{symbol}.jsonl.gz'),'rt',encoding='utf8') as f:
            for line in f:
                r = json.loads(line)
                if r['kind']=='splits' and r['date']>=days[0] and r['source_id']==current.get('primary_source'):
                    action_events.append(dict(date=r['date'],reported_factor=r['ratio']))
        record = dict(symbol=symbol,name=holding['name'],cusip=holding['cusip'],isin=[x['value'] for x in holding['identifiers'] if x['type']=='isin'],
            value_usd=str(abs(Decimal(holding['valUSD']))),equity_pct=float(100*abs(Decimal(holding['valUSD']))/total),
            published_status=current['status'],published_first=current.get('first'),published_last=current.get('last'),
            rows=len(rows),complete_sessions=len(full_days),adjusted_sessions=len(adjusted_days),
            absent_dates=sorted(dayset-{r['trade_date'] for r in rows}),unsupported_field_dates=sorted({r['trade_date'] for r in rows}-full_days),
            group=priority_group(full_days==dayset,adjusted_days==dayset,comparison_full,bool(rows or comparisons or comparison_bad)),
            source_windows=source_windows,price_conflict_dates_in_window=sorted(price_conflicts&dayset),
            earlier_price_conflicts=len(price_conflicts-dayset),volume_pairs=volume_pairs,
            quality_flags=dict(counters),factor_failures=factor_failures,reported_split_events=action_events,
            identity_exclusions=base.get('identity_exclusions',[]),unresolved_names=base.get('unresolved_historical_names',[]),
            pre_listing_observations=base.get('pre_listing_source_observations',0),
            identity_status=current.get('identity_status'),historical_available_at=current.get('historical_available_at'),
            invalid_comparison_rows=dict(comparison_bad),source_names=[s.get('name') for s in current['sources']],
            inherited_review=bool(inherited),candidate_aliases=[])
        if symbol in ALIAS_EVIDENCE:
            alias = ALIAS_EVIDENCE[symbol]
            if record['group'] != 'no_window_records' or alias.get('cusip',record['cusip']) != record['cusip']:
                raise ValueError('Unexpected alias or CUSIP ' + symbol)
            candidate = window(alias['symbol'])
            candidate_audit = g.audit(alias['symbol'])
            candidate_days = {r['trade_date'] for r in candidate if valid(r,FIELDS)}
            filed_price = float(Decimal(xml.findtext('{*}valUSD'))/Decimal(xml.findtext('{*}balance')))
            closing_price = next(r['raw_close'] for r in candidate if r['trade_date']==TARGET)
            record['candidate_aliases'] = [dict(**alias, complete_sessions=len(candidate_days),
                status=candidate_audit['status'],name=candidate_audit.get('name'),
                full_window=candidate_days==dayset, filing_value_per_share=filed_price,
                candidate_raw_close=closing_price, valuation_difference=closing_price-filed_price)]
            if candidate_days==dayset:
                record['group'] = 'complete_later_ticker_candidate'
        records.append(record)
        if i%50 == 0:
            print(f'Inspected {i+1}/{len(selected)}',flush=True)

    tags = {
        'earlier_price_conflicts': lambda r:r['earlier_price_conflicts']>0,
        'volume_conflict_pairs': lambda r:bool(r['volume_pairs']),
        'volume_comparison_interval_touches_window': lambda r:any(p['interval_intersects_window'] for p in r['volume_pairs']),
        'window_price_conflicts': lambda r:bool(r['price_conflict_dates_in_window']),
        'factor_failures': lambda r:bool(r['factor_failures']),
        'unresolved_names': lambda r:bool(r['unresolved_names']),
        'excluded_source_identities': lambda r:bool(r['identity_exclusions']),
        'pre_listing_observations': lambda r:r['pre_listing_observations']>0,
        'reported_split_events_affecting_window': lambda r:bool(r['reported_split_events']),
    }
    full = [r for r in records if r['group']=='complete_published_window']
    result = dict(holdings_date=TARGET,decision=pilot['first_monthly_decision'],window=[days[0],days[-1]],sessions=len(days),
        denominator_usd=str(total),scope=summarize(records,total),groups={k:summarize([r for r in records if r['group']==k],total) for k in sorted({r['group'] for r in records})},
        status={k:summarize([r for r in records if r['published_status']==k],total) for k in ('review','unavailable')},
        baseline=dict(count=67,equity_pct=pilot['funds']['MDY']['price_window_value_pct']),previous_five=dict(count=5,equity_pct=prior['selected_equity_pct']),
        complete_window_tags={key:summarize([r for r in full if fn(r)],total) for key,fn in tags.items()},
        holdings=records,pilot_inputs=evidence,pins_sha256=sha256(PINS),batch=g.batch,parent_batch=g.parent.batch,
        used=g.used,parent_used=g.parent.used,runner_sha256=sha256(Path(__file__)))
    save(OUT/'inventory.json',result)
    print(json.dumps(result['groups'],indent=2))


if __name__=='__main__':
    run()
