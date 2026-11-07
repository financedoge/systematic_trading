"""Bounded CRSP holdings access inspection; retain every response locally."""
from datetime import UTC, datetime
import gzip
import json
from pathlib import Path

from psycopg import sql

from probe_alpaca_sip_source import ROOT, save, sha
from setup_wrds_access import WrdsProxyTunnel, connect, default_passfile, write_ca_bundle

STUDY = ROOT / 'research/p421-wrds-holdings-access-20261107-v1'
PROTOCOL_HASH = '2c61993ed70fdf21529e00d4d7dcc1de76eefbe37b84ea0e5316ec439c264701'
READ_TABLES = {'holdings', 'fund_hdr', 'fund_names', 'fund_summary', 'crsp_portno_map'}


def protocol():
    raw = (STUDY / 'protocol.json').read_bytes()
    if sha(raw) != PROTOCOL_HASH:
        raise ValueError('Changed holdings inspection scope')
    p = json.loads(raw)
    for name, h in [(p['prior_pool_file'], p['prior_pool_sha256']),
                    ('scripts/setup_wrds_access.py', p['connection_helper_sha256'])]:
        if sha((ROOT/name).read_bytes()) != h:
            raise ValueError('Changed frozen prerequisite')
    return p


def read_query(schema, table):
    if schema != 'crsp_q_mutualfunds' or table not in READ_TABLES:
        raise ValueError('Unapproved holdings access scope')
    return sql.SQL('SELECT 1 AS row_present FROM {} LIMIT 1').format(sql.Identifier(schema, table))


def main():
    p = protocol()
    root = Path('D:/systematic_trading_data/source-archives/wrds') / (
        'holdings-access-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ'))
    root.mkdir(parents=True, exist_ok=False)
    files = [Path(__file__), ROOT/'scripts/setup_wrds_access.py', STUDY/'protocol.json']
    for f in files:
        (root/f.name).write_bytes(f.read_bytes())
    ca = root/'trusted-ca.pem'
    write_ca_bundle(ca)
    m = dict(status='in_progress', protocol_sha256=PROTOCOL_HASH, queries=[],
        files={f.name:sha(f.read_bytes()) for f in files}, source_release=None,
        started_at=datetime.now(UTC).isoformat(), holdings_rows_extracted=0,
        historical_availability_certified=False, tls='verify-full', transaction_read_only=True)
    save(root/'manifest.json', m)

    def extract(connection, name, query, params, limit):
        rendered = query.as_string(connection) if isinstance(query, sql.Composable) else query
        q = dict(name=name, query=rendered, parameters=params, started_at=datetime.now(UTC).isoformat())
        m['queries'].append(q)
        save(root/'manifest.json', m)
        try:
            with connection.transaction():
                with connection.cursor() as cur:
                    cur.execute(query, params)
                    columns = [c.name for c in cur.description]
                    types = [c.type_code for c in cur.description]
                    rows = cur.fetchall()
            raw = json.dumps(dict(columns=columns, postgres_type_oids=types, rows=rows),
                             default=str, allow_nan=False).encode()
            blob = gzip.compress(raw, mtime=0)
            path = root/(name+'.json.gz')
            path.write_bytes(blob)
            q.update(path=path.name, sha256=sha(blob), response_sha256=sha(raw), row_count=len(rows),
                     captured_at=datetime.now(UTC).isoformat(), status='captured')
            save(root/'manifest.json', m)
            if len(rows) > limit:
                raise ValueError('Metadata exceeds bounded scope')
            return [dict(zip(columns,r,strict=True)) for r in rows]
        except Exception as error:
            q.update(status='failed', error_type=type(error).__name__, sqlstate=getattr(error,'sqlstate',None))
            save(root/'manifest.json', m)
            raise

    tunnel = None
    print(json.dumps(dict(archive=str(root), status='connecting_read_only')), flush=True)
    try:
        tunnel = WrdsProxyTunnel('http://127.0.0.1:7892')
        tunnel.start()
        with connect('wudf26', default_passfile(), ca, via_proxy=True) as connection:
            state = extract(connection,'connection',"SELECT current_setting('transaction_read_only') AS read_only",None,1)
            if state != [dict(read_only='on')]:
                raise ValueError('Read-only connection required')
            tables = extract(connection,'tables',
                "SELECT c.relname AS name,c.relkind AS kind,has_schema_privilege(n.oid,'USAGE') AS schema_usage,"
                "has_table_privilege(c.oid,'SELECT') AS table_select FROM pg_class c "
                "JOIN pg_namespace n ON c.relnamespace=n.oid WHERE n.nspname=%s "
                "AND c.relkind IN ('r','v','m','p','f') ORDER BY c.relname LIMIT 101",[p['schema']],100)
            columns = extract(connection,'columns',
                'SELECT c.relname AS relation,a.attname AS name,format_type(a.atttypid,a.atttypmod) AS type,'
                'col_description(c.oid,a.attnum) AS description FROM pg_attribute a '
                'JOIN pg_class c ON c.oid=a.attrelid JOIN pg_namespace n ON n.oid=c.relnamespace '
                'WHERE n.nspname=%s AND a.attnum>0 AND NOT a.attisdropped '
                'ORDER BY c.relname,a.attnum LIMIT 2001',[p['schema']],2000)
            checks = []
            for row in tables:
                if row['name'] not in READ_TABLES or not row['schema_usage'] or not row['table_select']:
                    continue
                try:
                    result = extract(connection,'read-'+row['name'],read_query(p['schema'],row['name']),None,1)
                    checks.append(dict(table=row['name'], read_succeeded=True, has_rows=bool(result)))
                except Exception as error:
                    checks.append(dict(table=row['name'], read_succeeded=False,
                        error_type=type(error).__name__,sqlstate=getattr(error,'sqlstate',None)))
        m.update(status='inspection_complete',completed_at=datetime.now(UTC).isoformat())
        save(root/'manifest.json',m)
        assessment = dict(status='access_inspection_complete', protocol_sha256=PROTOCOL_HASH,
            archive=str(root),manifest_sha256=sha((root/'manifest.json').read_bytes()),tables=tables,
            read_checks=checks,holdings_columns=[r for r in columns if r['relation']=='holdings'],
            metadata_column_count=len(columns),holdings_rows_extracted=0,strategy_input_use=False,
            historical_available_at=None,runner_sha256=sha(Path(__file__).read_bytes()))
        save(STUDY/'assessment.json',assessment)
        print(json.dumps(dict(archive=str(root),table_count=len(tables),read_checks=checks,
            holdings_columns=[r['name'] for r in columns if r['relation']=='holdings'])),flush=True)
    except Exception as error:
        m.update(status='incomplete',error_type=type(error).__name__,sqlstate=getattr(error,'sqlstate',None))
        save(root/'manifest.json',m)
        raise
    finally:
        if tunnel:
            tunnel.close()


if __name__ == '__main__':
    main()
