"""Audited continuous CRSP raw open/close, separate from the operational catalog."""
from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
import gzip
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import research_p421_alpha33_v2 as s
from capture_p421_alpha33 import holding_cusip
from qualify_p421_alpha33 import in_window, norm, price_check, source_rows, window_rows
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, encode
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.price_governance import governed_sessions


def main():
    p=s.protocol()
    if (s.OUT/'publication.json').exists():
        raise FileExistsError('Publication already sealed')
    store=AnalyticsStore.from_settings(AppSettings())
    if store.storage_name!='postgres-parquet-duckdb':
        raise ValueError('Native store required')
    cap,data=source_rows()
    if cap!=p['source_capture']:
        raise ValueError('Changed source capture')
    reader=GovernedInputs(Path(p['price_pin']['root']),p['price_pin']['batch'])
    def keys(r):
        return set(r.manifest)|(keys(r.parent) if r.parent else set())
    available=defaultdict(list)
    for key in keys(reader):
        if key.startswith('bars/') and key.endswith('.jsonl.gz'):
            available[norm(key[5:-9])].append(key[5:-9])
    holdings_ids,intervals=defaultdict(list),defaultdict(list)
    for row in data['holdings-identities']:
        holdings_ids[row['cusip9']].append(row)
    for row in data['signal-identities']:
        intervals[row['permno']].append(row)
    holdings=[]
    filing_manifest=s.read(s.QUARTER/'artifact-manifest.json')
    for row in s.positions():
        if row['assetCat'] not in ('EC','EP') or float(row['valUSD'])<=0:
            continue
        ids=[r for r in holdings_ids.get(holding_cusip(row),[]) if in_window(r,p['holdings_date'])]
        name='filings/'+row['accession']+'.json'
        filing=s.read(s.checked(s.QUARTER/name,filing_manifest[name]))
        if filing['as_of']!=p['holdings_date'] or filing['filed']>p['signal_start']:
            raise ValueError('Public filing cutoff violated')
        public_at=datetime.fromisoformat(filing['accepted_new_york']).replace(tzinfo=ZoneInfo('America/New_York')).isoformat()
        holdings.append(dict(fund=row['symbol'],line=row['line'],value_usd=float(row['valUSD']),
            permno=ids[0]['permno'] if len(ids)==1 else None,cusip=holding_cusip(row),name=row['name'],
            accession=row['accession'],holdings_date=p['holdings_date'],public_filed_at=public_at))
    sessions,calendar=governed_sessions(p['signal_start'],p['evaluation'][1])
    source={};rejected=[];prices=[];cache={};support=Counter()
    for name,rows in data.items():
        if not name.startswith('daily-prices'):
            continue
        for row in rows:
            key=(row['permno'],row['dlycaldt'])
            if key in source:
                raise ValueError('Duplicate source security/date')
            source[key]=row
    for (permno,day),row in sorted(source.items()):
        ids=[r for r in intervals[permno] if in_window(r,day)]
        reason=None
        if day not in sessions:
            reason='unexpected_session'
        elif len(ids)!=1:
            reason='ambiguous_or_missing_dated_identity'
        elif row['cusip']!=ids[0]['cusip']:
            reason='daily_identity_disagreement'
        elif row['dlyprcflg']!='TR':
            reason='non_trade_close'
        else:
            try:
                values=[float(row[k]) for k in ('dlyopen','dlyclose')]
                if not all(math.isfinite(v) and v>0 for v in values):
                    reason='nonpositive_or_nonfinite'
            except (TypeError,ValueError):
                reason='missing_raw_price'
        status='single_source_audited'
        if reason is None:
            ident=ids[0]
            symbols={symbol for ticker in (ident['ticker'],ident['tradingsymbol']) for symbol in available[norm(ticker)]}
            if len(symbols)==1:
                symbol=next(iter(symbols))
                if symbol not in cache:
                    cache[symbol]={r['trade_date']:r for r in window_rows(reader,symbol,p['signal_start'],p['evaluation'][1])}
                existing=cache[symbol].get(day)
                if existing:
                    problem=price_check(existing,row,ident)
                    if problem in ('independent_price_disagreement','adjustment_factor_inconsistent','dated_cusip_disagreement'):
                        reason=problem
                    elif problem is None:
                        status='independent_overlap_corroborated'
        if reason:
            rejected.append(dict(permno=permno,date=day,reason=reason))
            continue
        support[status]+=1
        prices.append(dict(permno=permno,date=day,symbol=ids[0]['tradingsymbol'],raw_open=values[0],raw_close=values[1],
            cusip9=ids[0]['cusip9'],qualification=status,source='CRSP dsf_v2',historical_available_at=None))
    records=[]
    for r in holdings:
        records.append(dict(point_key=f"holding:{r['fund']}:{r['line']}",family='p421_public_holding',entity=r['fund'],
            observed_at=r['holdings_date'],available_at=r['public_filed_at'],payload=encode(r)))
    for r in prices:
        records.append(dict(point_key=f"price:{r['permno']}:{r['date']}",family='p421_audited_price',entity=str(r['permno']),
            observed_at=r['date'],available_at=None,payload=encode(r)))
    private=s.WORK/'audited-crsp-projection.json.gz'
    private.write_bytes(gzip.compress(encode(dict(holdings=holdings,prices=prices,rejected=rejected)).encode(),mtime=0))
    hashes={r['point_key']:sha256(r['payload'].encode()).hexdigest() for r in records}
    version=sha256(encode(dict(protocol=s.digest(s.OUT/'protocol.json'),rows=hashes)).encode()).hexdigest()
    source_id='governance/research/'+s.OUT.name
    store.publish(source_id,version,records,provenance=dict(protocol_sha256=s.digest(s.OUT/'protocol.json'),source_capture=cap,
        basis='Single-provider CRSP raw open/close; not total returns',historical_price_availability_certified=False,
        qualified_support=dict(support),old_catalog_unchanged=True,scope='Finite research-only continuous field projection'))
    actual=store.pinned_rows('observations',source_id,version,limit=300000)
    if len(actual)!=len(records) or {r['point_key']:sha256(r['payload'].encode()).hexdigest() for r in actual}!=hashes:
        raise ValueError('Native readback differs')
    s.write(s.OUT/'publication.json',dict(source_id=source_id,version=version,rows=len(records),stock_rows=len(prices),holdings=len(holdings),
        unique_securities=len({r['permno'] for r in prices}),qualified_support=dict(support),
        failures=dict(Counter(r['reason'] for r in rejected)),calendar=calendar,
        expected_sessions_per_continuing_security=len(sessions),missing_sessions_not_filled=True,
        price_files=reader.used,projection_path=str(private),projection_sha256=s.digest(private),
        row_payload_root=sha256(encode(hashes).encode()).hexdigest(),readback='exact',auditor_sha256=s.digest(Path(__file__))))
    print('CRSP raw field publication',len(prices),'rows',dict(support),flush=True)


if __name__=='__main__':
    main()
