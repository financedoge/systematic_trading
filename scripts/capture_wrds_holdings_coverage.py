"""Retain bounded fund mappings, holdings coverage and one MDY snapshot locally."""
from datetime import UTC, datetime
from decimal import Decimal
import gzip
import json
from pathlib import Path

from probe_alpaca_sip_source import ROOT, save, sha
from setup_wrds_access import WrdsProxyTunnel, connect, default_passfile, write_ca_bundle

STUDY = ROOT/'research/p421-wrds-holdings-coverage-20261107-v1'
PROTOCOL_HASH = '977bbefbda0d3c02ae6974cb6045e6de290f25aa3d785d3713ed706efcebc21f'


def identifiers(rows, field, limit):
    result = set()
    for row in rows:
        value = Decimal(str(row[field]))
        if not value.is_finite() or value <= 0 or value != value.to_integral_value():
            raise ValueError('Invalid permanent identifier')
        result.add(int(value))
    if not result or len(result) > limit:
        raise ValueError('Missing or excessive identifier candidates')
    return sorted(result)


def detail_portfolio(names, mappings, symbol, day):
    funds = {r['crsp_fundno'] for r in names if r['ticker'] == symbol and r['et_flag'] == 'F'
             and str(r['chgdt']) <= day <= str(r['chgenddt'])}
    rows = [r for r in mappings if r['crsp_fundno'] in funds and str(r['begdt']) <= day <= str(r['enddt'])]
    if len(funds) != 1 or len(rows) != 1:
        raise ValueError('Ambiguous dated MDY fund/portfolio mapping')
    return identifiers(rows, 'crsp_portno', 1)[0]


def main():
    raw = (STUDY/'protocol.json').read_bytes()
    if sha(raw) != PROTOCOL_HASH:
        raise ValueError('Changed holdings coverage scope')
    p = json.loads(raw)
    access = ROOT/'research/p421-wrds-holdings-access-20261107-v1/assessment.json'
    if sha(access.read_bytes()) != p['access_assessment_sha256']:
        raise ValueError('Changed access evidence')
    helper = ROOT/'scripts/setup_wrds_access.py'
    if sha(helper.read_bytes()) != p['connection_helper_sha256']:
        raise ValueError('Changed WRDS connection helper')
    root = Path('D:/systematic_trading_data/source-archives/wrds')/(
        'holdings-coverage-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
    root.mkdir(parents=True,exist_ok=False)
    files = [Path(__file__),helper,STUDY/'protocol.json']
    for f in files:
        (root/f.name).write_bytes(f.read_bytes())
    ca = root/'trusted-ca.pem'
    write_ca_bundle(ca)
    m = dict(status='in_progress',protocol_sha256=PROTOCOL_HASH,source_release=None,
        started_at=datetime.now(UTC).isoformat(),historical_availability_certified=False,
        files={f.name:sha(f.read_bytes()) for f in files},queries=[],tls='verify-full',read_only=True)
    save(root/'manifest.json',m)

    def extract(connection,name,query,params,limit):
        q = dict(name=name,query=query,parameters=params,started_at=datetime.now(UTC).isoformat())
        m['queries'].append(q)
        save(root/'manifest.json',m)
        try:
            with connection.cursor() as cur:
                cur.execute(query,params)
                columns = [c.name for c in cur.description]
                types = [c.type_code for c in cur.description]
                rows = cur.fetchall()
            raw = json.dumps(dict(columns=columns,postgres_type_oids=types,rows=rows),default=str,allow_nan=False).encode()
            blob = gzip.compress(raw,mtime=0)
            path = root/(name+'.json.gz')
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

    tunnel = None
    print(json.dumps(dict(archive=str(root),status='connecting_read_only')),flush=True)
    try:
        tunnel=WrdsProxyTunnel('http://127.0.0.1:7892')
        tunnel.start()
        with connect('wudf26',default_passfile(),ca,via_proxy=True) as connection:
            state=extract(connection,'connection',"SELECT current_setting('transaction_read_only') AS read_only",None,1)
            if state != [dict(read_only='on')]:
                raise ValueError('Read-only session required')
            start,end=p['window']
            names=extract(connection,'fund-names',
                'SELECT * FROM crsp_q_mutualfunds.fund_names WHERE ticker=ANY(%s) '
                'AND chgdt<=%s AND chgenddt>=%s ORDER BY ticker,crsp_fundno,chgdt LIMIT 2001',
                [p['funds'],end,start],p['limits']['names'])
            fundnos=identifiers(names,'crsp_fundno',p['limits']['portfolios'])
            mappings=extract(connection,'portfolio-map',
                'SELECT * FROM crsp_q_mutualfunds.crsp_portno_map WHERE crsp_fundno=ANY(%s) '
                'AND begdt<=%s AND enddt>=%s ORDER BY crsp_fundno,begdt LIMIT 3001',
                [fundnos,end,start],p['limits']['mappings'])
            ports=identifiers(mappings,'crsp_portno',p['limits']['portfolios'])
            extract(connection,'holdings-coverage',
                'SELECT crsp_portno,report_dt,eff_dt,count(*) AS rows,count(DISTINCT security_rank) AS distinct_ranks,'
                'sum(percent_tna) AS percent_tna_sum,count(*) FILTER (WHERE percent_tna IS NULL) AS missing_weights,'
                'count(*) FILTER (WHERE permno IS NULL) AS missing_permno,'
                'count(*) FILTER (WHERE cusip IS NULL OR cusip=\'\') AS missing_cusip '
                'FROM crsp_q_mutualfunds.holdings WHERE crsp_portno=ANY(%s) AND report_dt BETWEEN %s AND %s '
                'GROUP BY crsp_portno,report_dt,eff_dt ORDER BY crsp_portno,report_dt,eff_dt LIMIT 10001',
                [ports,start,end],p['limits']['coverage_rows'])
            case=p['detail_case']
            port=detail_portfolio(names,mappings,case['fund'],case['report_dt'])
            extract(connection,'mdy-december-holdings',
                'SELECT * FROM crsp_q_mutualfunds.holdings WHERE crsp_portno=%s AND report_dt=%s '
                'ORDER BY eff_dt,security_rank LIMIT 2001',[port,case['report_dt']],p['limits']['detail_rows'])
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


if __name__ == '__main__':
    main()
