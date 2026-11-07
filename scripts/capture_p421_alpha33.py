"""Read-only bounded CRSP reconciliation extract, retained outside Git."""
from datetime import UTC, datetime
import gzip
import json
from pathlib import Path

import research_p421_alpha33 as study
from setup_wrds_access import WrdsProxyTunnel, connect, default_passfile, write_ca_bundle


def holding_cusip(row):
    """Handle the SEC projection's list-shaped identifiers without ticker guessing."""
    direct = row.get('cusip')
    if study.valid_cusip(direct) and direct != '000000000':
        return direct
    identifiers = row.get('identifiers', [])
    isins = [r['value'] for r in identifiers if r.get('type') == 'isin']
    if len(isins) == 1 and study.valid_isin(isins[0]):
        return study.embedded_cusip(isins[0])
    return None


def main():
    p = study.protocol()
    if (study.OUT/'capture.json').exists():
        raise FileExistsError('Source capture already sealed')
    ids = sorted({c for r in study.positions() if r['assetCat'] in ('EC','EP')
                  and (c := holding_cusip(r))})
    root = Path('D:/systematic_trading_data/source-archives/wrds')/('alpha33-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
    root.mkdir(parents=True)
    files = [Path(__file__), study.ROOT/'scripts/setup_wrds_access.py', study.OUT/'protocol.json']
    for f in files:
        (root/f.name).write_bytes(f.read_bytes())
    m = dict(status='in_progress', queries=[], protocol_sha256=study.digest(study.OUT/'protocol.json'),
        files={f.name:study.digest(f) for f in files}, started_at=datetime.now(UTC).isoformat(),
        historical_availability_certified=False, source_release=None, tls='verify-full', read_only=True)
    study.write(root/'manifest.json',m)

    def extract(connection, name, sql, params, limit):
        q = dict(name=name, query=sql, parameters=params, started_at=datetime.now(UTC).isoformat())
        m['queries'].append(q)
        study.write(root/'manifest.json',m)
        with connection.cursor() as cur:
            cur.execute(sql,params)
            columns=[c.name for c in cur.description]
            types=[c.type_code for c in cur.description]
            rows=cur.fetchall()
        raw=json.dumps(dict(columns=columns,postgres_type_oids=types,rows=rows),default=str,allow_nan=False).encode()
        target=root/(name+'.json.gz')
        target.write_bytes(gzip.compress(raw,mtime=0))
        from hashlib import sha256
        q.update(path=target.name,sha256=study.digest(target),response_sha256=sha256(raw).hexdigest(),
                 rows=len(rows),captured_at=datetime.now(UTC).isoformat())
        study.write(root/'manifest.json',m)
        if len(rows)>limit:
            raise ValueError('Frozen source bound exceeded')
        print(name,len(rows),'retained locally',flush=True)
        return [dict(zip(columns,r,strict=True)) for r in rows]

    tunnel=None
    try:
        ca=root/'trusted-ca.pem'
        write_ca_bundle(ca)
        tunnel=WrdsProxyTunnel('http://127.0.0.1:7892')
        tunnel.start()
        print('Connecting read-only; candidate CUSIPs',len(ids),flush=True)
        with connect('wudf26',default_passfile(),ca,via_proxy=True) as conn:
            state=extract(conn,'connection',"SELECT current_setting('transaction_read_only') AS read_only",None,1)
            if state != [dict(read_only='on')]:
                raise ValueError('Read-only connection required')
            dated=extract(conn,'holdings-identities',
                'SELECT * FROM crsp_a_stock.stksecurityinfohist WHERE cusip9=ANY(%s) '
                'AND secinfostartdt<=%s AND secinfoenddt>=%s ORDER BY permno,secinfostartdt LIMIT 20001',
                [ids,p['holdings_date'],p['holdings_date']],p['limits']['identity_rows'])
            permnos=sorted({r['permno'] for r in dated})
            if not permnos:
                raise ValueError('No dated identities')
            extract(conn,'signal-identities',
                'SELECT * FROM crsp_a_stock.stksecurityinfohist WHERE permno=ANY(%s) '
                'AND secinfostartdt<=%s AND secinfoenddt>=%s ORDER BY permno,secinfostartdt LIMIT 20001',
                [permnos,p['evaluation'][1],p['signal_start']],p['limits']['identity_rows'])
            total=0
            for offset in range(0,len(permnos),100):
                rows=extract(conn,f'daily-prices-{offset:04d}',
                    'SELECT permno,dlycaldt,cusip,ticker,dlyopen,dlyclose,dlyprc,dlyprcflg,dlyretmissflg '
                    'FROM crsp_a_stock.dsf_v2 WHERE permno=ANY(%s) AND dlycaldt BETWEEN %s AND %s '
                    'ORDER BY permno,dlycaldt LIMIT 10001',
                    [permnos[offset:offset+100],p['signal_start'],p['evaluation'][1]],10000)
                total+=len(rows)
                if total>p['limits']['daily_rows']:
                    raise ValueError('Global daily-row bound exceeded')
        m.update(status='captured_pending_qualification',completed_at=datetime.now(UTC).isoformat())
        study.write(root/'manifest.json',m)
        study.write(study.OUT/'capture.json',dict(archive=str(root),manifest_sha256=study.digest(root/'manifest.json'),
            protocol_sha256=m['protocol_sha256'],runner_sha256=study.digest(Path(__file__))))
        print('Capture complete',str(root),flush=True)
    except Exception as error:
        m.update(status='incomplete',error_type=type(error).__name__,sqlstate=getattr(error,'sqlstate',None))
        study.write(root/'manifest.json',m)
        raise
    finally:
        if tunnel:
            tunnel.close()


if __name__=='__main__':
    main()
