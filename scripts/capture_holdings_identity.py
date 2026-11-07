"""Retain bounded dated identities, one mixed-receipt control and public identifier rules."""
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import gzip
import json
from pathlib import Path

import acquire_ten_qualification as public
from audit_wrds_holdings_coverage import candidates
from capture_wrds_holdings_coverage import identifiers
from probe_alpaca_sip_source import ROOT, save, sha
from setup_wrds_access import WrdsProxyTunnel, connect, default_passfile, write_ca_bundle

STUDY=ROOT/'research/p421-holdings-identity-20261107-v1'
PROTOCOL_HASH='98e686cf8a7ddc982c858eb9b0fb7abf1896c01925cd9a506c5f86900880f142'


def checked(path,h):
    raw=path.read_bytes()
    if sha(raw)!=h:
        raise ValueError('Changed retained input: '+str(path))
    return raw


def protocol():
    p=json.loads(checked(STUDY/'protocol.json',PROTOCOL_HASH))
    checked(ROOT/'scripts/setup_wrds_access.py',p['connection_helper_sha256'])
    checked(ROOT/'scripts/acquire_ten_qualification.py',p['public_capture_helper_sha256'])
    return p


def prior(p):
    a=json.loads(checked(ROOT/p['source_assessment'],p['source_assessment_sha256']))
    detail=json.loads(checked(Path(a['details']['path']),p['source_detail_sha256']))
    root=Path(a['source_archive'])
    m=json.loads(checked(root/'manifest.json',a['source_manifest_sha256']))
    rows={}
    for q in m['queries']:
        raw=gzip.decompress(checked(root/q['path'],q['sha256']))
        if sha(raw)!=q['response_sha256']:
            raise ValueError('Changed original WRDS response')
        d=json.loads(raw)
        rows[q['name']]=[dict(zip(d['columns'],r,strict=True)) for r in d['rows']]
    return detail,rows


def public_sources():
    p=protocol()
    cache=ROOT/'var/research'/STUDY.name/'public'
    cache.mkdir(parents=True,exist_ok=True)
    public.CACHE=cache

    def one(item):
        key,url=item
        try:
            _,r=public.capture(key,url)
            return key,dict(status='captured',**r,path=str(cache/(key+'.gz')))
        except Exception as error:
            response=getattr(error,'response',None)
            return key,dict(status='failed',url=url,error_type=type(error).__name__,
                http_status=getattr(response,'status_code',None),captured_at=datetime.now(UTC).isoformat())

    with ThreadPoolExecutor(max_workers=4) as pool:
        results=dict(pool.map(one,p['public_sources'].items()))
    save(STUDY/'public-sources.json',dict(protocol_sha256=PROTOCOL_HASH,sources=results,
        runner_sha256=sha(Path(__file__).read_bytes())))
    print(json.dumps({k:dict(status=v['status'],http_status=v.get('http_status')) for k,v in results.items()}),flush=True)


def wrds_sources():
    p=protocol()
    detail,old=prior(p)
    unmatched=[r for r in detail['unmatched_crsp'] if r['permno'] is not None]
    if sorted(r['ticker'] for r in unmatched)!=p['candidate_symbols'] or len(unmatched)!=19:
        raise ValueError('Changed unmatched equity candidates')
    permnos=identifiers(unmatched,'permno',19)
    c=p['mixed_receipt_case']
    ports=candidates(old['fund-names'],old['portfolio-map'],c['symbol'],c['report_date'])
    if len(ports)!=1:
        raise ValueError('Mixed-receipt control lacks unique dated portfolio')
    root=Path('D:/systematic_trading_data/source-archives/wrds')/(
        'holdings-identity-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
    root.mkdir(parents=True,exist_ok=False)
    files=[Path(__file__),ROOT/'scripts/setup_wrds_access.py',STUDY/'protocol.json']
    for f in files:
        (root/f.name).write_bytes(f.read_bytes())
    ca=root/'trusted-ca.pem'
    write_ca_bundle(ca)
    m=dict(status='in_progress',protocol_sha256=PROTOCOL_HASH,queries=[],
        files={f.name:sha(f.read_bytes()) for f in files},source_release=None,
        started_at=datetime.now(UTC).isoformat(),tls='verify-full',read_only=True,
        historical_availability_certified=False)
    save(root/'manifest.json',m)

    def extract(connection,name,query,params,limit):
        q=dict(name=name,query=query,parameters=params,started_at=datetime.now(UTC).isoformat())
        m['queries'].append(q)
        save(root/'manifest.json',m)
        try:
            with connection.cursor() as cur:
                cur.execute(query,params)
                columns=[c.name for c in cur.description]
                types=[c.type_code for c in cur.description]
                rows=cur.fetchall()
            raw=json.dumps(dict(columns=columns,postgres_type_oids=types,rows=rows),default=str,allow_nan=False).encode()
            blob=gzip.compress(raw,mtime=0)
            path=root/(name+'.json.gz')
            path.write_bytes(blob)
            q.update(status='captured',path=path.name,sha256=sha(blob),response_sha256=sha(raw),
                row_count=len(rows),captured_at=datetime.now(UTC).isoformat())
            save(root/'manifest.json',m)
            if len(rows)>limit:
                raise ValueError('Source query exceeded frozen bound')
            print(json.dumps(dict(query=name,rows=len(rows),status='retained_locally')),flush=True)
            return [dict(zip(columns,r,strict=True)) for r in rows]
        except Exception as error:
            q.update(status='failed',error_type=type(error).__name__,sqlstate=getattr(error,'sqlstate',None))
            save(root/'manifest.json',m)
            raise

    tunnel=None
    print(json.dumps(dict(archive=str(root),status='connecting_read_only')),flush=True)
    try:
        tunnel=WrdsProxyTunnel('http://127.0.0.1:7892')
        tunnel.start()
        with connect('wudf26',default_passfile(),ca,via_proxy=True) as connection:
            state=extract(connection,'connection',"SELECT current_setting('transaction_read_only') AS read_only",None,1)
            if state!=[dict(read_only='on')]:
                raise ValueError('Read-only session required')
            start,end=p['identity_window']
            extract(connection,'security-history',
                'SELECT * FROM crsp_a_stock.stksecurityinfohist WHERE permno=ANY(%s) '
                'AND secinfostartdt<=%s AND secinfoenddt>=%s ORDER BY permno,secinfostartdt LIMIT 501',
                [permnos,end,start],p['limits']['identity_rows'])
            extract(connection,'legacy-name-history',
                'SELECT * FROM crsp_a_stock.dsenames WHERE permno=ANY(%s) '
                'AND namedt<=%s AND nameendt>=%s ORDER BY permno,namedt LIMIT 501',
                [permnos,end,start],p['limits']['identity_rows'])
            extract(connection,'mixed-receipt-holdings',
                'SELECT * FROM crsp_q_mutualfunds.holdings WHERE crsp_portno=%s AND report_dt=%s '
                'ORDER BY eff_dt,security_rank LIMIT 5001',[ports[0],c['report_date']],p['limits']['holdings_rows'])
        m.update(status='captured_pending_qualification',completed_at=datetime.now(UTC).isoformat())
        save(root/'manifest.json',m)
        save(STUDY/'capture.json',dict(archive=str(root),manifest_sha256=sha((root/'manifest.json').read_bytes()),
            protocol_sha256=PROTOCOL_HASH,query_count=len(m['queries']),strategy_input_use=False))
        print(json.dumps(dict(archive=str(root),status=m['status'])),flush=True)
    except Exception as error:
        m.update(status='incomplete',error_type=type(error).__name__,sqlstate=getattr(error,'sqlstate',None))
        save(root/'manifest.json',m)
        raise
    finally:
        if tunnel:
            tunnel.close()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage',choices=['wrds','public'])
    args=parser.parse_args()
    (wrds_sources if args.stage=='wrds' else public_sources)()
