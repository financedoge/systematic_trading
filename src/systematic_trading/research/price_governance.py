"""Auditable price-basis conversion and conservative joins of immutable sources.

Reconstructed raw prices are estimates from the provider's split ledger, not
exchange-certified tape. A split-only Close is never relabelled as raw.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
import math
import re
from zoneinfo import ZoneInfo

import numpy as np


POLICY = dict(version=2, min_overlap=60, median_scale_error=.001,
              p99_scale_error=.005, p99_return_error=.01,
              minimum_informative_returns=20, raw_basis_price_tolerance=.005, raw_basis_volume_tolerance=.05,
              conflict_tolerance=.005, dividend_factor_tolerance=.001,
              basis='Yahoo split/dividend back-adjusted prices; not a reinvestment total-return index',
              raw='Reconstructed from source Close and strictly subsequent split ratios; never tape-certified',
              historical_availability='unknown; retrieval time is not historical availability',
              listing_boundary='Quarantine every source observation before the preferred provider firstTradeDate; when absent, use the first valid preferred observation as an identity floor. Earlier issuer continuity requires independent dated evidence')
COMPLEX_IDENTITIES = {'ACT','BBT','DOW','GE','HPQ','LB','PCLN','STI','UTX','RTX'}
FIELDS = ('open','high','low','close')


def governed_sessions(start,end):
    """XNYS sessions with an explicit holiday range (pandas defaults to 1970).

    CustomBusinessDay asks regular_holidays.holidays() without date bounds,
    which omits pre-1970 holidays in this dependency combination. Subtract the
    same authoritative rules evaluated across the actual requested range.
    Ad-hoc closures already present in exchange_calendars remain excluded.
    """
    import exchange_calendars as xc
    calendar=xc.get_calendar('XNYS',start=start,end=end)
    nominal={str(d.date()) for d in calendar.sessions}
    holidays={str(d.date()) for d in calendar.regular_holidays.holidays(start,end)}
    return nominal-holidays,dict(name='XNYS',library='exchange_calendars',version=xc.__version__,
        explicit_holiday_range=[start,end],removed_default_range_artifacts=sorted(nominal&holidays))


def finite(value):
    try:
        value=float(value)
        return value if math.isfinite(value) else None
    except (ValueError,TypeError):
        return None


@dataclass
class PriceSource:
    key: str
    symbol: str
    name: str
    provider: str
    raw_hash: str
    vintage: str
    rows: dict
    actions: list = field(default_factory=list)
    action_start: str | None = None
    action_end: str | None = None
    basis: str = 'split_adjusted'
    priority: int = 0
    metadata: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)


def yahoo_source(raw, *, key, symbol, raw_hash, vintage, priority, action_start):
    result=raw['chart']['result'][0]
    meta=result['meta']
    tz=ZoneInfo(meta.get('exchangeTimezoneName','America/New_York'))
    # Windows CRT fromtimestamp rejects some pre-1970 Unix timestamps.
    epoch=datetime(1970,1,1,tzinfo=UTC)
    day=lambda t:(epoch+timedelta(seconds=t)).astimezone(tz).date().isoformat()
    if finite(meta.get('firstTradeDate')) is not None:
        meta['listing_boundary_date']=day(meta['firstTradeDate'])
    q=result['indicators']['quote'][0]
    adj=result['indicators'].get('adjclose',[{}])[0].get('adjclose',[])
    rows,issues={},[]
    for i,t in enumerate(result.get('timestamp',[])):
        d=day(t)
        row={f:finite(q.get(f,[])[i]) if i<len(q.get(f,[])) else None for f in (*FIELDS,'volume')}
        row.update(adjusted_close=finite(adj[i]) if i<len(adj) else None,source_point_key=str(t))
        if d in rows:
            issues.append(dict(date=d,issue='duplicate_local_session'))
            rows[d]=None
        else:
            rows[d]=row
    actions=[]
    for kind,events in result.get('events',{}).items():
        for event_key,event in events.items():
            action=dict(kind=kind,date=day(event['date']),source_point_key=event_key,original=event)
            if kind=='splits':
                num,den=finite(event.get('numerator')),finite(event.get('denominator'))
                action['ratio']=num/den if num and den and num>0 and den>0 else None
            else:
                action['amount']=finite(event.get('amount'))
            actions.append(action)
    return PriceSource(key,symbol,meta.get('longName',meta.get('shortName','')), 'yahoo',raw_hash,vintage,
                       {d:r for d,r in rows.items() if r is not None},sorted(actions,key=lambda x:(x['date'],x['kind'])),
                       action_start,vintage[:10],priority=priority,metadata=meta,issues=issues)


def valid_bar(row):
    p=[row.get(f) for f in FIELDS]
    if any(x is None or not math.isfinite(x) or x<=0 for x in p):
        return False
    a,v=row.get('adjusted_close'),row.get('volume')
    if a is None or not math.isfinite(a) or a<=0 or v is None or not math.isfinite(v) or v<0:
        return False
    # Historic CSVs are rounded. Permit only one cent or a tiny relative error.
    tol=max(.01,row['close']*1e-5)
    return row['low']<=min(row['open'],row['close'])+tol and row['high']+tol>=max(row['open'],row['close']) and row['high']>=row['low']


def name_tokens(name):
    ignored={'INC','CORP','CORPORATION','COMPANY','CO','LTD','PLC','CLASS','COMMON','STOCK','SHARES','THE','HOLDINGS','GROUP','A','B','C','ORDINARY','COM'}
    return {t for t in re.findall('[A-Z0-9]+',(name or '').upper()) if len(t)>2 and t not in ignored}


def names_agree(a,b):
    x,y=name_tokens(a),name_tokens(b)
    return bool(x and y and (x==y or len(x&y)/min(len(x),len(y))>=.5))


def audit_overlap(anchor, candidate):
    days=sorted(set(anchor.rows)&set(candidate.rows))
    days=[d for d in days if valid_bar(anchor.rows[d]) and valid_bar(candidate.rows[d])]
    report=dict(anchor=anchor.key,candidate=candidate.key,overlap=len(days),first=days[0] if days else None,
                last=days[-1] if days else None,identity_name_agreement=names_agree(anchor.name,candidate.name),accepted=False)
    if not days:
        return dict(report,reason='no_overlap_identity_and_scale_unresolved')
    a=np.array([anchor.rows[d]['adjusted_close'] for d in days])
    b=np.array([candidate.rows[d]['adjusted_close'] for d in days])
    scale=float(np.median(a/b))
    error=np.abs(b*scale/a-1)
    # Differences of adjacent common-date log returns also catch changed history.
    re=np.abs(np.diff(np.log(a))-np.diff(np.log(b)))
    informative=int(np.count_nonzero(np.abs(np.diff(np.log(a)))>1e-5))
    volume_a=np.array([anchor.rows[d]['volume'] for d in days])
    volume_b=np.array([candidate.rows[d]['volume'] for d in days])
    vg=(volume_a>0)&(volume_b>0)
    vr=volume_a[vg]/volume_b[vg]
    volume_scale=float(np.median(vr)) if len(vr) else None
    report.update(scale=scale,informative_returns=informative,median_scale_error=float(np.median(error)),p99_scale_error=float(np.quantile(error,.99)),
        max_scale_error=float(np.max(error)),p99_return_error=float(np.quantile(re,.99)) if len(re) else None,
        conflicting_dates=[d for d,e in zip(days,error) if e>POLICY['conflict_tolerance']],
        volume_scale=volume_scale,volume_p99_scale_error=float(np.quantile(np.abs(vr/volume_scale-1),.99)) if len(vr) else None,
        raw_close_ratio_median=float(np.median([anchor.rows[d]['close']/candidate.rows[d]['close'] for d in days])))
    report['accepted']=bool(len(days)>=POLICY['min_overlap'] and informative>=POLICY['minimum_informative_returns'] and report['identity_name_agreement']
        and report['median_scale_error']<=POLICY['median_scale_error']
        and report['p99_scale_error']<=POLICY['p99_scale_error']
        and report['p99_return_error']<=POLICY['p99_return_error'])
    report['reason']='overlap_and_identity_pass' if report['accepted'] else ('identity_review' if not report['identity_name_agreement'] else 'insufficient_overlap_or_price_conflict')
    if (anchor.basis==candidate.basis=='split_adjusted' and anchor.action_start
        and anchor.action_start<=candidate.vintage[:10]<=anchor.vintage[:10]
        and anchor.action_end and anchor.action_end>=anchor.vintage[:10]
        and len(days)>=POLICY['min_overlap'] and report['identity_name_agreement']):
        intervening=split_multiplier(anchor.actions,candidate.vintage[:10],anchor.vintage[:10])
        if intervening:
            ce=np.abs(np.array([anchor.rows[d]['close']/candidate.rows[d]['close'] for d in days])*intervening-1)
            report.update(intervening_split_product=intervening,split_basis_price_error_p99=float(np.quantile(ce,.99)),
                raw_basis_agreement=bool(np.quantile(ce,.99)<=POLICY['raw_basis_price_tolerance']))
            if len(vr):
                report.update(split_basis_volume_error_p99=float(np.quantile(np.abs(vr/intervening-1),.99)),
                              raw_volume_basis_agreement=bool(np.quantile(np.abs(vr/intervening-1),.99)<=POLICY['raw_basis_volume_tolerance']))
    return report


def factor_audit(source):
    """Check dividend-factor changes against reported actions, preserving failures."""
    days=sorted(d for d,r in source.rows.items() if valid_bar(r))
    events={}
    split_dates={e['date'] for e in source.actions if e['kind']=='splits'}
    for e in source.actions:
        if e['kind'] in ('dividends','capitalGains') and e.get('amount') is not None:
            events[e['date']]=events.get(e['date'],0)+e['amount']
    failures=[]
    if source.basis!='split_adjusted':
        return failures
    for prev,day in zip(days,days[1:]):
        a,b=source.rows[prev],source.rows[day]
        before,after=a['adjusted_close']/a['close'],b['adjusted_close']/b['close']
        expected=1-events.get(day,0)/a['close']
        observed=before/after
        if abs(observed-expected)>POLICY['dividend_factor_tolerance']:
            failures.append(dict(date=day,issue='unexplained_adjustment_factor',observed=observed,expected=expected,
                                 previous_date=prev,reported_distribution=events.get(day,0)))
        if day in split_dates and abs(math.log(b['close']/a['close']))>.8:
            failures.append(dict(date=day,issue='split_day_price_continuity_requires_review',
                                 previous_date=prev,close_ratio=b['close']/a['close']))
    return failures


def split_multiplier(actions, day, vintage):
    applicable=[e.get('ratio') for e in actions if e['kind']=='splits' and day<e['date']<=vintage]
    if any(r is None or r<=0 or not math.isfinite(r) for r in applicable):
        return None
    return math.prod(applicable)


def consolidate(symbol, sources, sessions, cutoff):
    """One row/session; unresolved gaps remain absent and explicit in the audit.

    A candidate can fill/extend only after overlap and identity agreement. The
    best source wins on overlaps. No interpolation or forward fill is allowed.
    """
    sources=sorted(sources,key=lambda s:(s.priority,s.vintage,len(s.rows)),reverse=True)
    usable=[s for s in sources if s.metadata.get('identity_eligible',True) and s.basis!='unknown'
            and any(valid_bar(r) and d<=cutoff and d in sessions for d,r in s.rows.items())]
    if not usable:
        return [],dict(symbol=symbol,status='unavailable',rows=0,sources=[dict(source_id=s.key,name=s.name,
            accepted=False,scale=None,price_basis=s.basis,raw_sha256=s.raw_hash,observations=len(s.rows)) for s in sources],
            overlaps=[],gaps=[],raw_rows=0),[dict(**e,source_id=s.key,source_hash=s.raw_hash,symbol=symbol) for s in sources for e in s.actions]
    anchor=usable[0]
    listing_boundary=anchor.metadata.get('listing_boundary_date')
    boundary_basis='provider_firstTradeDate' if listing_boundary else 'preferred_source_first_observation_identity_floor'
    if not listing_boundary:
        listing_boundary=min(d for d,r in anchor.rows.items() if valid_bar(r) and d in sessions and d<=cutoff)
    # A CSV can contain an old issuer followed by a new issuer reusing its
    # ticker. Agreement AFTER the new IPO does not validate the earlier era.
    # Treat the preferred provider's start date as a conservative boundary,
    # not as independently certified listing history. Original rows survive.
    before_listing={s.key:[d for d in s.rows if listing_boundary and d<listing_boundary] for s in sources}
    accepted={anchor.key:1.0}
    overlaps=[]
    # Compare every pair, not just pairs that happen to contribute output rows.
    for i,a in enumerate(usable):
        for b in usable[i+1:]:
            overlaps.append(audit_overlap(a,b))
    for s in usable[1:]:
        match=next(r for r in overlaps if r['anchor']==anchor.key and r['candidate']==s.key)
        if match['accepted']:
            accepted[s.key]=match['scale']
    failures={s.key:factor_audit(s) if s.action_start else [] for s in usable}
    raw_basis_blocked={key for r in overlaps if r.get('raw_basis_agreement') is False for key in (r['anchor'],r['candidate'])}
    volume_basis_blocked={key for r in overlaps if r.get('raw_volume_basis_agreement') is False for key in (r['anchor'],r['candidate'])}
    # Fresh full-range actions can support an older Yahoo vintage only if the
    # old source passed the identity/overlap gate; never apply today's ticker to
    # a disjoint legacy security. Only events before that vintage are reversed.
    action_source=next((s for s in usable if s.action_start and s.key in accepted),None)
    rows={}
    for source in usable:
        if source.key not in accepted:
            continue
        factor=accepted[source.key]
        actions=source.actions if source.action_start else (action_source.actions if action_source else [])
        actions=[e for e in actions if e['kind']=='splits']
        action_start=source.action_start or (action_source.action_start if action_source else None)
        action_end=source.action_end or (action_source.action_end if action_source else None)
        if not source.action_start and action_source and action_start:
            # A full-range request does not establish an action ledger before
            # that provider's own observed price history begins.
            action_start=max(action_start,min(action_source.rows))
        bad_before=max((x['date'] for x in failures[source.key]),default='')
        for d,r in sorted(source.rows.items()):
            if d>cutoff or (listing_boundary and d<listing_boundary) or d not in sessions or d in rows or not valid_bar(r):
                continue
            adj_factor=r['adjusted_close']/r['close']*factor
            raw_allowed=(source.basis=='split_adjusted' and action_start is not None and action_start<=d
                         and action_end is not None and action_end>=source.vintage[:10] and d>=bad_before
                         and symbol not in COMPLEX_IDENTITIES and source.key not in raw_basis_blocked)
            split=split_multiplier(actions,d,source.vintage[:10]) if raw_allowed else None
            flags=['historical_vintage_uncertified']
            if split is None:
                flags.append('raw_unresolved')
            if r['volume']==0:
                flags.append('zero_volume_observed')
            if source.key!=anchor.key:
                flags.append('joined_source')
            if failures[source.key]:
                flags.append('source_adjustment_requires_review')
            if source.key in raw_basis_blocked:
                flags.append('unexplained_cross_vintage_raw_price_basis')
            if source.key in volume_basis_blocked:
                flags.append('unexplained_cross_vintage_volume_basis')
            row=dict(symbol=symbol,trade_date=d,source_id=source.key,source_hash=source.raw_hash,
                     source_point_key=r.get('source_point_key',d),source_vintage=source.vintage,
                     dividend_factor=adj_factor,split_multiplier=split,source_volume=r['volume'],
                     raw_volume=r['volume']/split if split and source.key not in volume_basis_blocked else None,quality_flags=flags,
                     adjustment_status='reported_distribution_checks_pass' if source.action_start and not failures[source.key]
                     else 'provider_adjustment_not_independently_reconstructed')
            for f in FIELDS:
                row['adjusted_'+f]=r[f]*adj_factor
                row['raw_'+f]=r[f]*split if split else None
            rows[d]=row
    days=sorted(rows)
    if not days:
        # A provider may update an old/delisted symbol's metadata to a future
        # listing while leaving the old prices in its response. Do not fall
        # back to that previous economic identity when the boundary removes it.
        return [],dict(symbol=symbol,name=anchor.name,status='unavailable',rows=0,raw_rows=0,raw_volume_rows=0,
            internal_gaps=0,gaps=[],overlaps=overlaps,primary_source=anchor.key,
            reason='all_observations_precede_provider_listing_boundary',
            listing_boundary=dict(date=listing_boundary,source_id=anchor.key,basis=boundary_basis,certified=False),
            pre_listing_source_observations=sum(len(dates) for dates in before_listing.values()),
            sources=[dict(source_id=s.key,name=s.name,accepted=False,scale=None,price_basis=s.basis,
                          raw_sha256=s.raw_hash,observations=len(s.rows),eligible_from=listing_boundary,
                          pre_listing_observations=len(before_listing[s.key])) for s in sources]),[
                              dict(**e,source_id=s.key,source_hash=s.raw_hash,symbol=symbol) for s in sources for e in s.actions]
    expected=[d for d in sorted(sessions) if days[0]<=d<=days[-1]]
    gaps=[d for d in expected if d not in rows]
    conflicts=set()
    for audit in overlaps:
        if audit['anchor']==anchor.key and audit['identity_name_agreement']:
            conflicts.update(audit.get('conflicting_dates',[]))
    for d in conflicts & rows.keys():
        rows[d]['quality_flags'].append('cross_source_price_conflict')
    seams=[]
    for prev,day in zip(days,days[1:]):
        if rows[prev]['source_id']!=rows[day]['source_id']:
            seams.append(dict(date=day,previous_date=prev,source_before=rows[prev]['source_id'],source_after=rows[day]['source_id'],
                              adjusted_return=rows[day]['adjusted_close']/rows[prev]['adjusted_close']-1))
    audits=[]
    for source in sources:
        sd=sorted(source.rows)
        invalid=[d for d,r in source.rows.items() if not valid_bar(r)]
        nonsession=[d for d in sd if d<=cutoff and d not in sessions]
        comparison_scale=accepted.get(source.key)
        if comparison_scale is None:
            diagnostic=next((r for r in overlaps if r['anchor']==anchor.key and r['candidate']==source.key
                             and r['identity_name_agreement']),None)
            comparison_scale=diagnostic.get('scale') if diagnostic else None
        audits.append(dict(source_id=source.key,name=source.name,provider=source.provider,price_basis=source.basis,
                           raw_sha256=source.raw_hash,vintage=source.vintage,first=sd[0] if sd else None,last=sd[-1] if sd else None,
                           observations=len(sd),accepted=source.key in accepted,scale=accepted.get(source.key),comparison_scale=comparison_scale,
                           eligible_from=listing_boundary,pre_listing_observations=len(before_listing[source.key]),
                           pre_listing_first=min(before_listing[source.key],default=None),pre_listing_last=max(before_listing[source.key],default=None),
                           invalid_dates=invalid,non_session_dates=nonsession,duplicate_issues=source.issues,
                           raw_basis_blocked=source.key in raw_basis_blocked,raw_volume_basis_blocked=source.key in volume_basis_blocked,
                           factor_failures=failures.get(source.key,[]),action_count=len(source.actions)))
    raw_rows=sum(r['raw_close'] is not None for r in rows.values())
    volume_conflicts=sum(r.get('volume_p99_scale_error',0) is not None and r.get('volume_p99_scale_error',0)>.05 for r in overlaps)
    large_seams=[s for s in seams if abs(s['adjusted_return'])>.5]
    for seam in large_seams:
        rows[seam['date']]['quality_flags'].append('large_join_return_requires_review')
    review=bool(gaps or conflicts or any(failures.values()) or symbol in COMPLEX_IDENTITIES or volume_conflicts or large_seams
                or anchor.metadata.get('provisional_identity') or raw_basis_blocked or volume_basis_blocked
                or boundary_basis!='provider_firstTradeDate' or any(before_listing.values()))
    summary=dict(symbol=symbol,name=anchor.name,status='review' if review else 'audited_with_limitations',
                 rows=len(rows),raw_rows=raw_rows,first=days[0],last=days[-1],expected_sessions=len(expected),
                 raw_volume_rows=sum(r['raw_volume'] is not None for r in rows.values()),
                 adjusted_internal_coverage_complete=not gaps,raw_internal_coverage_complete=not gaps and raw_rows==len(rows),
                 internal_gaps=len(gaps),gaps=gaps,conflict_dates=len(conflicts & rows.keys()),sources=audits,overlaps=overlaps,seams=seams,
                 primary_source=anchor.key,joined_rows=sum(r['source_id']!=anchor.key for r in rows.values()),
                 listing_boundary=dict(date=listing_boundary,source_id=anchor.key,basis=boundary_basis,certified=False),
                 pre_listing_source_observations=sum(len(dates) for dates in before_listing.values()),
                 volume_conflict_pairs=volume_conflicts,
                 identity_status='complex_identity_requires_review' if symbol in COMPLEX_IDENTITIES else 'provider_identity_not_security_master_certified',
                 tail_status='current_to_cutoff' if days[-1]==cutoff else 'stale_or_delisted_unverified',
                 full_listing_history_certified=False,raw_tape_certified=False,historical_available_at=None)
    actions=[dict(**e,source_id=s.key,source_hash=s.raw_hash,symbol=symbol) for s in sources for e in s.actions]
    return [rows[d] for d in days],summary,actions
