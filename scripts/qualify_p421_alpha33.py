"""Audit only consumed fields, then publish an isolated immutable native projection."""
from collections import Counter, defaultdict
from datetime import datetime
from hashlib import sha256
import gzip
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo

import research_p421_alpha33 as s
from capture_p421_alpha33 import holding_cusip
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, encode
from systematic_trading.research.governed_inputs import GovernedInputs


def norm(ticker):
    return str(ticker or '').replace('.','-').upper()


def in_window(row, day):
    return row['secinfostartdt'] <= day <= row['secinfoenddt']


def price_check(row, crsp, identity):
    if crsp.get('dlyprcflg') != 'TR':
        return 'non_trade_close'
    if str(crsp.get('cusip')) != str(identity.get('cusip')):
        return 'dated_cusip_disagreement'
    values = [row.get(k) for k in ('raw_open','raw_close','adjusted_open','adjusted_close')]
    values += [crsp.get('dlyopen'), crsp.get('dlyclose')]
    try:
        ro,rc,ao,ac,co,cc = map(float, values)
    except (ValueError,TypeError):
        return 'missing_price'
    if not all(math.isfinite(x) and x>0 for x in (ro,rc,ao,ac,co,cc)):
        return 'nonpositive_price'
    if abs(ro/co-1) > .005 or abs(rc/cc-1) > .005:
        return 'independent_price_disagreement'
    if abs((ao/ro)/(ac/rc)-1)>1e-6:
        return 'adjustment_factor_inconsistent'
    return None


def window_rows(reader,symbol,start,end):
    """Reuse the pinned reader's whole-file check; decode only the scoped window.

    The published canonical JSONL ends with trade_date. Noncanonical encodings
    fall back to full JSON decoding; no source replacement or date filling.
    """
    rows=[]
    with gzip.open(reader.checked(f'bars/{symbol}.jsonl.gz'),'rt',encoding='utf8') as stream:
        for line in stream:
            marker='"trade_date":"'
            day=line.rsplit(marker,1)[-1][:10] if marker in line else json.loads(line)['trade_date']
            if start<=day<=end:
                row=json.loads(line)
                if row['trade_date']!=day:
                    raise ValueError('Date extraction mismatch')
                rows.append(row)
    dates=[r['trade_date'] for r in rows]
    if dates!=sorted(set(dates)):
        raise ValueError('Duplicate or unsorted published dates')
    return rows


def source_rows():
    cap=s.read(s.OUT/'capture.json')
    if cap['protocol_sha256']!=s.digest(s.OUT/'protocol.json'):
        raise ValueError('Capture protocol changed')
    root=Path(cap['archive'])
    m=s.read(s.checked(root/'manifest.json',cap['manifest_sha256']))
    if m['status']!='captured_pending_qualification':
        raise ValueError('Incomplete capture')
    for name,h in m['files'].items():
        s.checked(root/name,h)
    out={}
    for q in m['queries']:
        raw=gzip.decompress(s.checked(root/q['path'],q['sha256']).read_bytes())
        if sha256(raw).hexdigest()!=q['response_sha256']:
            raise ValueError('Changed source rows')
        d=json.loads(raw)
        out[q['name']]=[dict(zip(d['columns'],r,strict=True)) for r in d['rows']]
    return cap,out


def main():
    p=s.protocol()
    if (s.OUT/'publication.json').exists():
        raise FileExistsError('Projection already published')
    store=AnalyticsStore.from_settings(AppSettings())
    if store.storage_name!='postgres-parquet-duckdb':
        raise ValueError('Native publication required')
    cap,data=source_rows()
    reader=GovernedInputs(Path(p['price_pin']['root']),p['price_pin']['batch'])
    def keys(r):
        return set(r.manifest) | (keys(r.parent) if r.parent else set())
    available=defaultdict(list)
    for key in keys(reader):
        if key.startswith('bars/') and key.endswith('.jsonl.gz'):
            name=key[5:-9]
            available[norm(name)].append(name)
    by_cusip=defaultdict(list)
    for r in data['holdings-identities']:
        by_cusip[r['cusip9']].append(r)
    by_permno=defaultdict(list)
    for r in data['signal-identities']:
        by_permno[r['permno']].append(r)
    daily={}
    for r in [r for name,rows in data.items() if name.startswith('daily-prices') for r in rows]:
        key=(r['permno'],r['dlycaldt'])
        if key in daily:
            raise ValueError('Duplicate CRSP security/date')
        daily[key]=r
    holdings=[]
    for row in s.positions():
        if row['assetCat'] not in ('EC','EP') or float(row['valUSD'])<=0:
            continue
        matches=by_cusip.get(holding_cusip(row),[])
        dated=[r for r in matches if in_window(r,p['holdings_date'])]
        holdings.append(dict(fund=row['symbol'],line=row['line'],value_usd=float(row['valUSD']),
            cusip=holding_cusip(row),permno=dated[0]['permno'] if len(dated)==1 else None,
            status='dated_identity' if len(dated)==1 else 'unsupported_or_ambiguous_identity',
            accession=row['accession'],name=row['name']))
    used_permnos={r['permno'] for r in holdings if r['permno'] is not None}
    bars,failures,cache,price_differences=[],Counter(),{},[]
    for (permno,day),crsp in daily.items():
        if permno not in used_permnos:
            continue
        ids=[r for r in by_permno[permno] if in_window(r,day)]
        if len(ids)!=1:
            failures['missing_or_ambiguous_dated_identity']+=1
            continue
        ident=ids[0]
        names={name for ticker in (ident['ticker'],ident['tradingsymbol']) for name in available[norm(ticker)]}
        if len(names)!=1:
            failures['missing_or_ambiguous_published_ticker']+=1
            continue
        symbol=next(iter(names))
        if symbol not in cache:
            cache[symbol]={r['trade_date']:r for r in window_rows(reader,symbol,p['signal_start'],p['evaluation'][1])}
        row=cache[symbol].get(day)
        if row is None:
            failures['missing_published_session']+=1
            continue
        problem=price_check(row,crsp,ident)
        if problem:
            failures[problem]+=1
            continue
        price_differences.append(dict(open_abs=abs(float(row['raw_open'])-float(crsp['dlyopen'])),
            close_abs=abs(float(row['raw_close'])-float(crsp['dlyclose'])),
            open_relative=abs(float(row['raw_open'])/float(crsp['dlyopen'])-1),
            close_relative=abs(float(row['raw_close'])/float(crsp['dlyclose'])-1)))
        bars.append(dict(permno=permno,symbol=symbol,date=day,adjusted_open=row['adjusted_open'],
            adjusted_close=row['adjusted_close'],raw_open=row['raw_open'],raw_close=row['raw_close'],
            cusip9=ident['cusip9'],source_hash=row['source_hash'],historical_available_at=None))
    bars.sort(key=lambda r:(r['date'],r['permno']))
    # Retain audited row-level evidence outside Git, including every rejection's input.
    private=s.WORK/'audited-projection.json.gz'
    blob=dict(holdings=holdings,bars=bars)
    private.write_bytes(gzip.compress(encode(blob).encode(),mtime=0))
    records=[]
    for r in holdings:
        manifest=s.read(s.QUARTER/'artifact-manifest.json')
        name='filings/'+r['accession']+'.json'
        filing=s.read(s.checked(s.QUARTER/name,manifest[name]))
        if filing['as_of']!=p['holdings_date'] or filing['filed']>p['signal_start']:
            raise ValueError('Holding not public by signal cutoff')
        public_at=datetime.fromisoformat(filing['accepted_new_york']).replace(tzinfo=ZoneInfo('America/New_York')).isoformat()
        r.update(holdings_date=p['holdings_date'],public_filed_at=public_at)
        records.append(dict(point_key=f"holding:{r['fund']}:{r['line']}",family='p421_public_holding',entity=r['fund'],
            observed_at=p['holdings_date'],available_at=public_at,payload=encode(r)))
    for r in bars:
        records.append(dict(point_key=f"price:{r['permno']}:{r['date']}",family='p421_audited_price',entity=str(r['permno']),
            observed_at=r['date'],available_at=None,payload=encode(r)))
    hashes={r['point_key']:sha256(r['payload'].encode()).hexdigest() for r in records}
    version=sha256(encode(dict(protocol=s.digest(s.OUT/'protocol.json'),rows=hashes)).encode()).hexdigest()
    source='governance/research/'+s.OUT.name
    store.publish(source,version,records,provenance=dict(protocol_sha256=s.digest(s.OUT/'protocol.json'),
        price_pin=p['price_pin'],source_capture=cap,scope='Field-qualified stock open/close and dated public SEC holdings; retrospective research only',
        historical_price_availability_certified=False,old_full_series_audits_unchanged=True))
    actual=store.pinned_rows('observations',source,version,limit=300000)
    actual_hashes={r['point_key']:sha256(r['payload'].encode()).hexdigest() for r in actual}
    if actual_hashes!=hashes or len(actual)!=len(records):
        raise ValueError('Native publication readback mismatch')
    import numpy as np
    agreement={key:dict(median=float(np.median([r[key] for r in price_differences])),
        p99=float(np.quantile([r[key] for r in price_differences],.99)),maximum=max(r[key] for r in price_differences))
        for key in ('open_abs','close_abs','open_relative','close_relative')} if price_differences else {}
    s.write(s.OUT/'publication.json',dict(source_id=source,version=version,rows=len(records),stock_rows=len(bars),
        unique_securities=len({r['permno'] for r in bars}),holdings=len(holdings),failures=dict(failures),
        qualified_price_agreement=agreement,
        price_files=reader.used,projection_path=str(private),projection_sha256=s.digest(private),
        row_payload_root=sha256(encode(hashes).encode()).hexdigest(),readback='exact',
        auditor_sha256=s.digest(Path(__file__)),capture_sha256=s.digest(s.OUT/'capture.json')))
    print('Published',len(bars),'qualified stock sessions;',len(holdings),'filed equity positions;',dict(failures),flush=True)


if __name__=='__main__':
    main()
