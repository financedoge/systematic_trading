"""Read-only P4.21 diagnosis of the five largest MDY holdings in price review."""
import gzip
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

import numpy as np

from acquire_p421_quarter import OUT as PILOT, PINS, ROOT, TARGET, digest, read, save
from qualify_p421_quarter import CUTOFF, complete_window, window_days
from systematic_trading.lean.contracts import sha256
from systematic_trading.research.governed_inputs import GovernedInputs

OUT = ROOT / 'research/p421-mdy-audit-20261104-v1'
PILOT_MANIFEST = 'artifact-manifest.json'
ALIAS_PROBE = 'P'
CHECK_FIELDS = ('raw_open','raw_high','raw_low','raw_close','raw_volume')


def comparison(new, old):
    """Compare on common sessions, preserving absolute raw and normalized adjusted bases."""
    left = {r['trade_date']: r for r in new}
    right = {r['trade_date']: r for r in old}
    days = sorted(left.keys() & right.keys())
    if not days:
        return dict(sessions=0)
    result = dict(sessions=len(days), first=days[0], last=days[-1])
    for field in CHECK_FIELDS:
        valid = [d for d in days if left[d][field] is not None and right[d][field] is not None]
        result[field] = dict(comparable=len(valid), identical=sum(left[d][field] == right[d][field] for d in valid))
    ratio = np.array([left[d]['adjusted_close']/right[d]['adjusted_close'] for d in days])
    result['adjusted_close_median_ratio'] = float(np.median(ratio))
    result['max_adjacent_adjusted_log_return_difference_bp'] = float(np.max(np.abs(np.diff(np.log(ratio))))*10000) if len(ratio)>1 else None
    return result


def source_diagnosis(g, s, days):
    current = g.audit(s)
    parent = g.parent
    base = parent.audit(s)
    prior_link = current.get('previous_audit')
    if prior_link and (prior_link['batch'] != parent.batch or prior_link['status'] != base['status']
                       or any(prior_link[k] != base[k] for k in ('volume_conflict_pairs','conflict_dates'))):
        raise ValueError('Unresolved previous audit link ' + s)
    rows = g.rows(s, days[0], days[-1])
    original = parent.rows(s, days[0], days[-1])
    keys = {r['source_id']: r['provider'] for r in base['sources']}
    overlaps = []
    window_conflicts = set()
    for pair in base['overlaps']:
        conflicts = pair.get('conflicting_dates', [])
        volume_error = pair.get('volume_p99_scale_error')
        if conflicts or (volume_error is not None and volume_error > .05):
            window_conflicts.update(set(conflicts).intersection(days))
            overlaps.append(dict(anchor=pair['anchor'], candidate=pair['candidate'],
                      families=[keys[pair['anchor']],keys[pair['candidate']]], first=pair['first'],last=pair['last'],
                      price_conflict_count=len(conflicts), first_conflict=min(conflicts,default=None),
                      last_conflict=max(conflicts,default=None), volume_p99_scale_error=volume_error))
    counters = Counter()
    with gzip.open(parent.checked(f'comparisons/{s}.jsonl.gz'),'rt',encoding='utf8') as stream:
        for line in stream:
            r = json.loads(line)
            if days[0] <= r['trade_date'] <= days[-1]:
                counters[r['source_id']] += 1
    actions = []
    with gzip.open(g.checked(f'actions/{s}.jsonl.gz'),'rt',encoding='utf8') as stream:
        for line in stream:
            r = json.loads(line)
            if r['kind']=='splits' and r['source_id']==current['primary_source'] and r['date']>=days[0]:
                actions.append(dict(date=r['date'],reported_kind=r['kind'],factor=r['ratio']))
    filed_day = next((r for r in rows if r['trade_date']==TARGET),None)
    return dict(first=current['first'], last=current['last'], status=current['status'], sessions=len(rows),
                complete=complete_window(rows,days), prior_link=prior_link, identity_status=current['identity_status'],
                full_listing_history_certified=current['full_listing_history_certified'],
                historical_available_at=current['historical_available_at'], pre_listing_original=base['pre_listing_source_observations'],
                unresolved_historical_names=base['unresolved_historical_names'], price_conflict_dates=base['conflict_dates'],
                volume_conflict_pairs=base['volume_conflict_pairs'], window_price_conflict_dates=sorted(window_conflicts),
                source_window_counts=dict(counters), window_source_families=sorted({keys[k] for k in counters}),
                earlier_problem_pairs=overlaps, anchor_factor_failures=next(r['factor_failures'] for r in current['sources'] if r['source_id']==current['primary_source']),
                reported_split_actions=actions, window_factors=dict(Counter(str(r['split_multiplier']) for r in rows)),
                cross_vintage=comparison(rows, original), raw_at_filing_date=filed_day['raw_close'] if filed_day else None)


def illumina_before_event(g):
    # A separate vintage already in the published comparison store predates the 2024 event.
    dates = ('2019-01-01','2020-04-01')
    with gzip.open(g.parent.checked('comparisons/ILMN.jsonl.gz'),'rt',encoding='utf8') as stream:
        old = {r['trade_date']:r for line in stream if (r:=json.loads(line))['source_id'].endswith('/yahoo2020/ILMN')
               and dates[0]<=r['trade_date']<=dates[1]}
    rows = g.rows('ILMN', *dates)
    common = [r for r in rows if r['trade_date'] in old]
    if not common:
        raise ValueError('Missing before-event comparison')
    metrics = dict(sessions=len(common),first=common[0]['trade_date'],last=common[-1]['trade_date'])
    for field, prior in [('source_volume','source_volume'),('raw_volume','source_volume'),('raw_close','source_close')]:
        ratios = [r[field]/old[r['trade_date']][prior] for r in common]
        metrics[field] = dict(median_ratio=float(np.median(ratios)),max_relative_error=max(abs(x-1) for x in ratios))
    return metrics


def emcor_distribution(g):
    days = ('2012-12-13','2012-12-14')
    vintages = {}
    with gzip.open(g.parent.checked('comparisons/EME.jsonl.gz'),'rt',encoding='utf8') as stream:
        for line in stream:
            r = json.loads(line)
            if r['trade_date'] in days and r['price_basis']=='split_adjusted':
                vintages.setdefault(r['source_id'],{})[r['trade_date']] = r
    implied = {}
    for source, rows in vintages.items():
        before, after = (rows[d] for d in days)
        factor_before = before['source_adjusted_close']/before['source_close']
        factor_after = after['source_adjusted_close']/after['source_close']
        implied[source] = before['source_close']*(1-factor_before/factor_after)
    with gzip.open(g.checked('actions/EME.jsonl.gz'),'rt',encoding='utf8') as stream:
        stated = [r['amount'] for line in stream if (r:=json.loads(line))['date']==days[1] and r['kind']=='dividends']
    return dict(dates=days, implied_cash_per_share=implied, published_dividends=stated)


def run():
    manifest = read(PILOT/PILOT_MANIFEST)
    used = {}
    def checked(name):
        path = PILOT/name
        used[name] = sha256(path)
        if used[name] != manifest[name]:
            raise ValueError('Changed pilot artifact ' + name)
        return path

    pilot = read(checked('qualification.json'))
    if sha256(PINS) != read(checked('sources.json'))['prior_pins_sha256']:
        raise ValueError('Changed price pin')
    pin = read(PINS)['price']
    if pin['batch'] != pilot['price_batch']:
        raise ValueError('Pilot price batch mismatch')
    g = GovernedInputs(Path(pin['root']), pin['batch'])
    cat = {r['symbol']:r for r in read(g.checked('catalog.json'))}
    with gzip.open(checked('positions.jsonl.gz'),'rt',encoding='utf8') as f:
        equities = [r for line in f if (r:=json.loads(line))['symbol']=='MDY' and r['assetCat'] in ('EC','EP')]
    total = sum(abs(Decimal(r['valUSD'])) for r in equities)
    if total != Decimal(pilot['funds']['MDY']['equity_abs_usd']):
        raise ValueError('MDY denominator mismatch')
    selected = sorted((r for r in equities if r['price_status']=='review'),key=lambda r:-abs(Decimal(r['valUSD'])))[:5]
    accession = pilot['funds']['MDY']['accession']
    receipt = read(checked(f'filings/{accession}.json'))
    raw = gzip.decompress(checked(f'filings/{accession}.xml.gz').read_bytes())
    if digest(raw) != receipt['xml']['sha256']:
        raise ValueError('Filing hash mismatch')
    positions = ElementTree.fromstring(raw).findall('.//{*}invstOrSec')
    days = window_days(CUTOFF)
    cases = {}
    for r in selected:
        s = r['candidate_symbol']
        xml = positions[r['line']-1]
        if (xml.findtext('{*}cusip') != r['cusip'] or xml.find('{*}identifiers/{*}ticker').get('value') != s
                or xml.findtext('{*}units')!='NS' or xml.findtext('{*}curCd')!='USD'
                or Decimal(xml.findtext('{*}valUSD'))!=Decimal(r['valUSD']) or cat[s]['status']!='review'):
            raise ValueError('Filing or catalog mismatch ' + s)
        cases[s] = dict(cusip=r['cusip'], equity_value_pct=100*float(abs(Decimal(r['valUSD']))/total),
                        filing_value_per_share=float(Decimal(r['valUSD'])/Decimal(xml.findtext('{*}balance'))),
                        **source_diagnosis(g,s,days))
    alias = source_diagnosis(g,ALIAS_PROBE,days)
    overlap = comparison(g.rows(ALIAS_PROBE,cases['PSTG']['first'],cases['PSTG']['last']),
                         g.rows('PSTG',cases['PSTG']['first'],cases['PSTG']['last']))
    result = dict(holdings_as_of=TARGET, decision=pilot['first_monthly_decision'], dates=[days[0],days[-1]],
        sessions=len(days), ranking=list(cases), equity_denominator_usd=str(total), cases=cases, later_symbol_probe=alias,
        pstg_p_older_overlap=overlap, illumina_older_comparison=illumina_before_event(g),
        emcor_2012_distribution=emcor_distribution(g),
        baseline_complete_pct=pilot['funds']['MDY']['price_window_value_pct'],
        selected_equity_pct=sum(r['equity_value_pct'] for r in cases.values()),
        pilot_manifest_sha256=sha256(PILOT/PILOT_MANIFEST), pilot_inputs=used, pins_sha256=sha256(PINS),
        governed_batch=g.batch, prior_batch=g.parent.batch, used=g.used, prior_used=g.parent.used)
    save(OUT/'diagnosis.json',result)


if __name__ == '__main__':
    run()
