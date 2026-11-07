"""Data-definition diagnostics only: no new signals, provider or publication."""
import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request

import numpy as np

from systematic_trading.data.http import read_bytes
from systematic_trading.research.governed_inputs import GovernedInputs

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'research/p421-volume-contract-20261107-v1'
CACHE=ROOT/'var/research/p421-volume-contract-20261107-v1'
PRIOR=ROOT/'research/p421-ibkr-reconcile-20261106-v1'


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,indent=2,sort_keys=True,allow_nan=False)+'\n',encoding='utf8',newline='\n')


def pinned(name):
    path=PRIOR/name
    if sha(path)!=read(PRIOR/'artifact-manifest.json')[name]:
        raise ValueError('Changed prior evidence '+name)
    return read(path)


def ratio_diagnostics(values):
    x=np.asarray(values,dtype=float)
    if len(x)<2 or not np.isfinite(x).all() or (x<=0).any():
        raise ValueError('Need positive, finite ratios')
    middle=float(np.median(x))
    return dict(count=len(x),minimum=float(x.min()),p01=float(np.quantile(x,.01)),median=middle,
        p99=float(np.quantile(x,.99)),maximum=float(x.max()),
        median_relative_error_by_multiplier={str(k):float(np.median(np.abs(k*x-1))) for k in (.01,1,100)},
        best_constant_multiplier_diagnostic=1/middle,
        p99_residual_after_median_scaling=float(np.quantile(np.abs(x/middle-1),.99)))


def available_activity(row, cutoff):
    """Illustrate the proposed actual-availability gate; not an app input adapter."""
    try:
        end,published,captured,decision=[datetime.fromisoformat(v) for v in
            [row['session_end'],row['published_at'],row['captured_at'],cutoff]]
        if any(v.tzinfo is None for v in [end,published,captured,decision]):
            return False
        return end <= published <= captured <= decision
    except (KeyError,TypeError,ValueError):
        return False


def freeze():
    prior=pinned('protocol.json')
    protocol=dict(created_at='2026-11-07',scope='Source-definition and unit diagnostics; no strategy inputs or publications.',
        symbols=prior['symbols'],window=prior['window'],prior_manifest_sha256=sha(PRIOR/'artifact-manifest.json'),
        comparisons=['As-returned ratios and fixed 0.01/1/100 multiplier diagnostics',
                     'Median-scale residual is descriptive, never a data conversion',
                     'Reuse CSL/WSO/XPO regular versus all-hours controls; no additional broker capture'],
        nasdaq_probe=[dict(symbol=s,start='2025-02-24',end='2025-02-28') for s in ['CSL','WSO','XPO','MANH']]
                      +[dict(symbol='CSL',start='2026-11-02',end='2026-11-04')],
        qualification='Do not resolve volume by close agreement, curve fitting, unit guessing or new tolerances.',
        point_in_time='November 2026 captures cannot certify historical publication availability.')
    if (OUT/'protocol.json').exists() and read(OUT/'protocol.json')!=protocol:
        raise ValueError('Changed declared comparison')
    save(OUT/'protocol.json',protocol)
    return protocol


def probe(protocol):
    results=[]
    for item in protocol['nasdaq_probe']:
        label=item['symbol']+'-'+item['start']
        url=('https://api.nasdaq.com/api/quote/'+item['symbol']+'/historical?assetclass=stocks'
             +'&fromdate='+item['start']+'&todate='+item['end']+'&limit=50')
        path=CACHE/(label+'.json.gz')
        receipt=OUT/'probes'/(label+'.json')
        if receipt.exists():
            r=read(receipt)
            if r.get('source_sha256') and sha(path)!=r['source_sha256']:
                raise ValueError('Changed source capture')
            results.append(r)
            continue
        r=dict(**item,url=url,captured_at=datetime.now(UTC).isoformat())
        try:
            raw=read_bytes(Request(url,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json',
                     'Origin':'https://www.nasdaq.com'}),timeout=15,max_bytes=2_000_000,attempts=2,native_fallback=True)
            CACHE.mkdir(parents=True,exist_ok=True)
            path.write_bytes(gzip.compress(raw,mtime=0))
            r.update(source_path=str(path),source_sha256=sha(path),response_bytes=len(raw))
            data=json.loads(raw)
            payload=data.get('data') or {}
            rows=(payload.get('tradesTable') or {}).get('rows') or []
            r.update(total_records=payload.get('totalRecords'),rows=rows,status=data.get('status'))
        except (OSError,ValueError) as exc:
            r.update(error=type(exc).__name__+': '+str(exc))
        save(receipt,r)
        results.append(r)
        print(label,'rows',len(r.get('rows',[])),'error',r.get('error'),flush=True)
    save(OUT/'source-probes.json',results)


def run():
    protocol=freeze()
    price=read(ROOT/'research/p421-coverage-20261104-v1/pins.json')['price']
    g=GovernedInputs(Path(price['root']),price['batch'])
    rows=[]
    all_ratios=[]
    for symbol in protocol['symbols']:
        differences=pinned('differences/'+symbol+'.json')
        ratios=[r['volume_ratio'] for r in differences]
        all_ratios.extend(ratios)
        bars=g.rows(symbol,*protocol['window'])
        assert len(bars)==len(differences)==253
        audit=g.audit(symbol)
        rows.append(dict(symbol=symbol,**ratio_diagnostics(ratios),
             split_multipliers=sorted({r['split_multiplier'] for r in bars}),
             source_raw_volume_equal=all(r['source_volume']==r['raw_volume'] for r in bars),
             date_aligned=all(b['trade_date']==d['date'] for b,d in zip(bars,differences)),
             published_status=audit['status'],
             source_coverage_metadata_present=all(k in bars[0] for k in ['volume_unit','volume_session','volume_trade_coverage'])))
    controls=[]
    for old in pinned('session-control.json'):
        symbol=old['symbol']
        rec=pinned('receipts/'+symbol+'-TRADES-ALL.json')
        path=Path(rec['source_path'])
        if sha(path)!=rec['source_sha256']:
            raise ValueError('Changed broker capture')
        byday={datetime.strptime(r['date'],'%Y%m%d').date().isoformat():r
               for r in json.loads(gzip.decompress(path.read_bytes()))['rows']}
        detail=pinned('differences/'+symbol+'.json')
        ratios=[float(byday[r['date']]['volume'])/r['published_volume'] for r in detail]
        controls.append(dict(symbol=symbol,all_hours=ratio_diagnostics(ratios),
            regular_ratio_median=float(np.median([r['volume_ratio'] for r in detail])),
            all_hours_greater_than_regular=sum(float(byday[r['date']]['volume'])>r['broker_volume_as_returned'] for r in detail),
            all_hours_below_published=sum(float(byday[r['date']]['volume'])<r['published_volume'] for r in detail)))
    save(OUT/'assessment.json',dict(price_batch=g.batch,used=g.used,stocks=rows,controls=controls,
         pooled=ratio_diagnostics(all_ratios),new_publications=0,new_assets_registered=0,
         point_in_time_certified=False,runner_sha256=sha(Path(__file__))))
    probe(protocol)


if __name__=='__main__':
    run()
