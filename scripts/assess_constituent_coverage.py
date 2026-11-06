"""P4.21 data coverage only. Read pinned native publications and measure admission ceilings."""
import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
import json
import math
from zoneinfo import ZoneInfo

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.live.trading_calendar import is_us_trading_day, us_equity_market_close
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.recorders.issuer_etfs import IssuerInputs, load_fund
from systematic_trading.research.governed_inputs import GovernedInputs

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/p421-coverage-20261104-v1'
POOL=ROOT/'research/class-vol-net-20261103-v1'
LEGACY={'ivv-constituents-2012-2026-v1':'IVV','underlying-sector-hhi-20260926-v1':'ITOT'}
NY=ZoneInfo('America/New_York')


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def pin():
    if (OUT/'pins.json').exists():
        raise FileExistsError('Use the existing pins or start a new assessment.')
    db=AnalyticsStore.from_settings(AppSettings())
    pub=db.latest('governance/catalog')
    price=dict(batch=pub['version'],root=json.loads(pub['provenance'])['root'])
    with db.catalog.connect() as c:
        rows=c.execute("SELECT source_id,version FROM native_analytics.publication_heads WHERE workspace=%s AND source_id LIKE 'sector-research/%%/holdings/%%' ORDER BY source_id",(db.workspace,)).fetchall()
        issuer_heads=c.execute("SELECT source_id FROM native_analytics.publication_heads WHERE workspace=%s AND source_id LIKE 'governance/issuer-etfs/%%' ORDER BY source_id",(db.workspace,)).fetchall()
    issuers={}
    for head in issuer_heads:
        symbol=head['source_id'].split('/')[-1]
        _,issuers[symbol]=load_fund(db,symbol)
    use=ROOT/'research/expanded-fr25-net-20261102-v1/protocol.json'
    manifest=read(use.parent/'artifact-manifest.json')
    assert sha256(use)==manifest['protocol.json']
    construction=POOL/'construction.json'
    assert sha256(construction)==read(POOL/'artifact-manifest.json')['construction.json']
    symbols=read(use)['symbols']
    classes={s:k for k,ss in read(construction)['classes'].items() for s in ss}
    write_json(OUT/'pins.json',dict(pinned_at=datetime.now(timezone.utc).isoformat(),price=price,
        issuers=issuers,legacy=[dict(r) for r in rows],funds={s:classes[s] for s in symbols},
        pool_protocol_sha256=sha256(use),construction_sha256=sha256(construction),
        scope='Coverage assessment for the prior 52-fund cohort. Historical monthly decisions January 2021–October 2026 plus a separate November 2 operational example. Use the preceding New York market close for information availability.',
        screening='Compare to the legacy diagnostic reference of 95% holding value and 70% names. Ticker-only published price-status matches are optimistic coverage screens, not verified identities, complete lookbacks, or a license to compute signals. Unknown historical availability remains unknown. Scope bonds, commodities and bills separately from equity look-through.'))


def upper_bound(positions,catalog):
    """Count every supplied line in the denominator, including unidentifiable ones."""
    n=len(positions)
    known=all(value is not None for _,value in positions)
    candidates=[(s,v) for s,v in positions if s and catalog.get(s,{}).get('status')=='audited_with_limitations']
    denominator=sum(abs(v) for _,v in positions if v is not None)
    return dict(lines=n,status_matched_lines=len(candidates),
        name_fraction=len(candidates)/n if n else None,
        value_fraction=sum(abs(v) for _,v in candidates if v is not None)/denominator if known and denominator>0 else None,
        unresolved_values=sum(v is None for _,v in positions))


def parse_value(value):
    try:
        number=float(str(value).replace(',',''))
        return number if math.isfinite(number) else None
    except (ValueError,TypeError):return None


def decisions():
    start=date(2020,12,1)
    days=[start+timedelta(days=i) for i in range((date(2026,11,3)-start).days+1) if is_us_trading_day(start+timedelta(days=i))]
    return [(str(d),datetime.combine(days[i-1],us_equity_market_close(days[i-1]),NY))
            for i,d in enumerate(days) if i and d.year>=2021 and d.month!=days[i-1].month]


def assess_legacy(db,pins,catalog):
    totals={}
    for dataset,fund in LEGACY.items():
        archive=Path('D:/systematic_trading_data/research')/dataset
        manifest=read(archive/'holdings_manifest.json')
        history=[]
        for pinrow in pins['legacy']:
            source=pinrow['source_id']
            if source.split('/')[1]!=dataset:continue
            day=source.split('/')[-1];file='holdings/'+day+'.json'
            if sha256(archive/file)!=manifest[file]:raise ValueError('Changed historical exclusions '+file)
            parsed=read(archive/file)
            rows=db.pinned_rows('observations',source,pinrow['version'])
            records=[json.loads(row['payload']) for row in rows]
            if len(records)!=len(parsed['rows']) or not records:
                raise ValueError('Native history disagrees with archived row count')
            if any(row['snapshot_as_of']!=day or row['source_raw_sha256']!=parsed['raw_sha256'] for row in records):
                raise ValueError('Historical row provenance mismatch')
            positions=[(r.get('resolved_yahoo') or r.get('yahoo'),parse_value(r['market_value'])) for r in records]
            # Excluded source lines may carry unresolved ticker reuse. Retain value and name in denominator.
            excluded=[r for r in parsed['excluded'] if r.get('Asset Class','Equity').lower()=='equity']
            positions.extend((None,parse_value(r.get('Market Value'))) for r in excluded)
            dated=sum(row.get('historical_available_at') is not None for row in records)
            history.append(dict(as_of=day,rows=len(rows),excluded_equity_lines=len(excluded),
                historical_availability_rows=dated,stored_available_at_rows=sum(r['available_at'] is not None for r in rows),
                retrieved_at=parsed['retrieved_at'],
                archive_snapshot_sha256=manifest[file],**upper_bound(positions,catalog)))
        totals[fund]=history
    return totals


def assess_issuers(pins,catalog):
    result={}
    for symbol,pinrow in pins['issuers'].items():
        reader=IssuerInputs(**pinrow);captures=[]
        for entry in reader.catalog['captures']:
            snap=reader.capture(entry['batch']);hold=snap['holdings'];rows=hold['rows']
            captures.append(dict(first_seen=snap['first_seen_at'],as_of=hold['as_of'],batch=entry['batch'],
                rows=len(rows),has_identifier=sum(bool(r['identifier']) for r in rows),
                has_sector=sum(bool(r['sector']) for r in rows),reported_weight_sum=hold['weight_sum_percent'],
                weights_reconciled=hold['weights_reconciled'],residual_percent=hold['weight_residual_percent'],
                **upper_bound([(r['ticker'],parse_value(r['weight_percent'])) for r in rows],catalog)))
        eligible={}
        for day,cutoff in decisions():
            try:
                snap=reader.snapshot(decision_at=cutoff,groups=('holdings',))
            except ValueError as exc:
                if not any(s in str(exc) for s in ('No issuer capture was available','stale or future-dated','missing observations','Issuer holdings weight residual is unresolved')):raise
                eligible[day]=dict(status='unavailable',reason=str(exc))
            else:
                eligible[day]=dict(status='available',as_of=snap['dates']['holdings'],first_seen=snap['first_seen_at'])
        result[symbol]=dict(in_frozen_pool=symbol in pins['funds'],captures=captures,decisions=eligible)
    return result


def audit():
    p=read(OUT/'pins.json');db=AnalyticsStore.from_settings(AppSettings())
    governed=GovernedInputs(Path(p['price']['root']),p['price']['batch'])
    rows=read(governed.checked('catalog.json'));catalog={r['symbol']:r for r in rows}
    assert len(catalog)==len(rows)
    cohorts={}
    for role in LEGACY:
        tagged=[r for r in rows if role in r.get('roles',[])]
        cohorts[role]=dict(series=len(tagged),status=dict(Counter(r['status'] for r in tagged)),
            dated_availability=sum(r.get('historical_available_at') is not None for r in tagged),
            complete_listing_certifications=sum(bool(r.get('full_listing_history_certified')) for r in tagged))
    legacy=assess_legacy(db,p,catalog)
    issuer=assess_issuers(p,catalog)
    summary={}
    for fund,snaps in legacy.items():
        values=[s['value_fraction'] for s in snaps if s['value_fraction'] is not None]
        summary[fund]=dict(snapshots=len(snaps),rows=sum(s['rows'] for s in snaps),start=snaps[0]['as_of'],end=snaps[-1]['as_of'],
            historical_availability_rows=sum(s['historical_availability_rows'] for s in snaps),
            max_status_match_value=max(values) if values else None,max_status_match_names=max(s['name_fraction'] for s in snaps),
            meets_reference=sum(s['value_fraction'] is not None and s['value_fraction']>=.95 and s['name_fraction']>=.70 for s in snaps))
    direct={}
    for symbol,record in issuer.items():
        caps=record['captures'];eligible=record['decisions']
        direct[symbol]=dict(in_pool=record['in_frozen_pool'],captures=len(caps),holdings_dates=len({r['as_of'] for r in caps}),
            first_seen=caps[0]['first_seen'],latest=caps[-1],historical_monthly_captures=sum(
                r['status']=='available' for d,r in eligible.items() if d<'2026-11-01'),nov2=eligible['2026-11-02'])
    equity=[s for s,asset in p['funds'].items() if asset.startswith('equity_')]
    months=sum(d<'2026-11-01' for d,_ in decisions())
    pool_matrix={symbol:dict(asset_class=asset,equity_lookthrough=asset.startswith('equity_'),
        direct_catalog=symbol in issuer,available_historical_decisions=direct.get(symbol,{}).get('historical_monthly_captures',0),
        historical_decisions=months) for symbol,asset in p['funds'].items()}
    result=dict(price_catalog_entries=len(rows),price_cohorts=cohorts,legacy=summary,issuer=direct,
        supported_funds=len(pool_matrix),equity_funds=len(equity),monthly_decisions=months,
        direct_equity_fund_months=sum(pool_matrix[s]['available_historical_decisions'] for s in equity),
        assessed_equity_fund_months=months*len(equity),proof='Availability-only upper bound for direct recorded fund snapshots; missing histories stay unavailable. IVV/ITOT are outside the supported ETF cohort.',
        gates=dict(precondition='P4.16 ETF-level studies completed; standalone Alpha54 was temporal, and tilt evidence did not establish incremental superiority. Constituent breadth remains an untested hypothesis.',
            holdings='Historical decision-time coverage is insufficient.',identity='Dated permanent identity, listing/delisting and membership revisions remain unresolved.',
            prices='Most IVV-role names remain review or unavailable. Even status-admissible ticker matches still require a dated identifier join plus complete audited raw/adjusted windows.',
            formula_inputs='True VWAP, historical cap and point-in-time industry membership remain separate formula-dependent prerequisites.'),
        decision='hold_replay_pending_data',runner_sha256=sha256(Path(__file__)),catalog_sha256=governed.used['catalog.json'],
        pin_sha256=sha256(OUT/'pins.json'))
    write_json(OUT/'monthly-pool-coverage.json',pool_matrix)
    write_json(OUT/'historical-snapshot-coverage.json',legacy)
    write_json(OUT/'issuer-coverage.json',issuer)
    write_json(OUT/'assessment.json',result)
    print(json.dumps({k:result[k] for k in ('price_cohorts','legacy','equity_funds','monthly_decisions','direct_equity_fund_months')},indent=1))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['pin','audit'])
    globals()[parser.parse_args().stage]()
