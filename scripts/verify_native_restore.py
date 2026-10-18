"""Restore a native SQL/Parquet/JetStream capture into new isolated local stores.

Requires an existing verified export receipt. Never restores into production.
The new directory is retained for inspection; services stop on success or failure.
"""
import argparse
import asyncio
from datetime import UTC, datetime
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

import nats
import psycopg
from psycopg import sql

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.native_analytics import NativeAnalyticsStore
from systematic_trading.portfolio.strategy_allocation import control_state
from systematic_trading.storage.dependencies import native_backup_snapshot, verify_dependencies
from systematic_trading.storage.nas_sync import LocalDatabases
from systematic_trading.storage.postgres import PostgresStore
from systematic_trading.storage.system_backup import snapshot_nats


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def table_counts(connection):
    tables = connection.execute("SELECT schemaname,tablename FROM pg_tables WHERE schemaname NOT LIKE 'pg_%' "
                                "AND schemaname <> 'information_schema' ORDER BY 1,2").fetchall()
    return {schema+'.'+table: connection.execute(sql.SQL('SELECT count(*) FROM {}.{}').format(
        sql.Identifier(schema), sql.Identifier(table))).fetchone()[0] for schema, table in tables}


async def restore_queue(url, folder):
    connection = await nats.connect(url, allow_reconnect=False, connect_timeout=3)
    try:
        inventory = json.loads((folder/'streams.json').read_text())
        checks = {}
        for name, source in inventory.items():
            response = json.loads((await connection.request('$JS.API.STREAM.RESTORE.'+name,
                json.dumps({key:source[key] for key in ('config','state')}).encode(), timeout=30)).data)
            if response.get('error'): raise ValueError(response['error'])
            with (folder/(name+'.snapshot')).open('rb') as stream:
                while chunk := stream.read(131072):
                    ack = await connection.request(response['deliver_subject'], chunk, timeout=60)
                    if ack.data: raise ValueError('Unexpected restore chunk response')
            result = json.loads((await connection.request(response['deliver_subject'], b'', timeout=120)).data)
            if result.get('error'): raise ValueError(result['error'])
            # The typed Python StreamState omits num_subjects on this client
            # version. Compare the unabridged server response to the snapshot.
            actual = json.loads((await connection.request('$JS.API.STREAM.INFO.'+name, b'{}', timeout=30)).data)
            if actual.get('error'): raise ValueError(actual['error'])
            state = actual['state']
            for key in ('messages','bytes','first_seq','last_seq','consumer_count','num_subjects'):
                if state.get(key,0) != source['state'].get(key,0):
                    raise ValueError('Restored queue state differs: '+name+'/'+key)
            checks[name] = state
        return checks
    finally:
        await connection.close()


def finish_queue(root, verification):
    capture = root/'capture'
    phase = json.loads((root/'database-acceptance.json').read_text())
    if not phase.get('passed') or phase['verification_sha256'] != sha256(verification):
        raise ValueError('A verified database phase for this export is required')
    for name in ('postgres.dump', 'dependencies.json', 'nats/streams.json', 'nats/ST_EVENTS.snapshot'):
        if sha256(capture/name) != phase['capture_hashes'][name]:
            raise ValueError('Verified restore capture changed: '+name)
    attempt = root/('queue-attempt-'+uuid4().hex)
    attempt.mkdir()
    nats_port = port()
    runtime = json.loads((ROOT/'config/native-runtime.json').read_text())
    config = attempt/'nats.conf'
    config.write_text(f'listen: "127.0.0.1:{nats_port}"\njetstream {{ store_dir: "{(attempt/"jetstream").as_posix()}", max_mem_store: 64MB, max_file_store: 6GB }}\n')
    with (attempt/'nats.log').open('ab') as log:
        queue = subprocess.Popen([str((ROOT/runtime['nats_binary']).resolve()),'-c',str(config)],
            stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for _ in range(50):
            try:
                with socket.create_connection(('127.0.0.1',nats_port),timeout=.2):break
            except OSError:time.sleep(.1)
        states = asyncio.run(restore_queue(f'nats://127.0.0.1:{nats_port}',capture/'nats'))
        receipt = dict(phase,at=datetime.now(UTC).isoformat(),nats_streams=states,
            queue_attempt=str(attempt),database_phase_sha256=sha256(root/'database-acceptance.json'))
        write_json(root/'acceptance.json',receipt)
        print(json.dumps(dict(passed=True,receipt=str(root/'acceptance.json'))),flush=True)
    finally:
        queue.terminate();queue.wait(timeout=30)


def main(root, verification, binaries):
    settings = AppSettings().model_copy(update={'market_data_store_backend':'parquet'})
    proof = json.loads(verification.read_text())
    if not proof.get('verified_fragment_files') or not proof.get('strategies'):
        raise ValueError('A completed analytical verification is required')
    root = root.resolve()
    if root.exists() or len(root.parts)<3 or root.is_relative_to(settings.native_analytics_root.resolve()):
        raise ValueError('Use a new independent restore directory')
    root.mkdir(parents=True)
    capture = root/'capture'; capture.mkdir()
    databases = LocalDatabases(ROOT, {'postgres':True,'sqlite_paths':[]}, settings)
    print('Capturing consistent PostgreSQL and Parquet inventory', flush=True)
    with native_backup_snapshot(settings) as (snapshot, dependencies):
        with databases.connection() as connection:
            connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
            connection.execute(sql.SQL('SET TRANSACTION SNAPSHOT {}').format(sql.Literal(snapshot)))
            expected_counts = table_counts(connection)
            roles = [r[0] for r in connection.execute("SELECT rolname FROM pg_roles WHERE rolname NOT LIKE 'pg_%'")]
        databases.pg('pg_dump','--no-password','--format=custom','--compress=0','--no-owner',
                     '--snapshot',snapshot,'--file',capture/'postgres.dump')
    write_json(capture/'dependencies.json', dependencies)
    native_root = Path(dependencies['native_analytics']['root'])
    restored_lake = root/'analytics'
    copied = 0
    for name, expected in dependencies['files'].items():
        source = Path(name)
        if not source.is_relative_to(native_root): continue
        target = restored_lake/source.relative_to(native_root)
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        if sha256(target)!=expected: raise ValueError('Copied native fragment differs')
        copied += 1
    print(f'Copied and verified {copied} native fragments; capturing JetStream', flush=True)
    asyncio.run(snapshot_nats('nats://127.0.0.1:4222',capture/'nats'))
    data = root/'postgres'; pg_port = port()
    password = uuid4().hex
    pwfile = root/'temporary-init-password.txt'; pwfile.write_text(password,encoding='ascii')
    env = dict(os.environ,PGHOST='127.0.0.1',PGPORT=str(pg_port),PGUSER='postgres',
               PGPASSWORD=password,PGDATABASE=settings.postgres_database)
    env.pop('PGOPTIONS',None)
    def command(program, *args):
        with (root/(program+'.log')).open('ab') as log:
            result = subprocess.run([str(binaries/(program+'.exe')),*map(str,args)],env=env,
                stdout=log,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,timeout=1200,
                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode: raise RuntimeError(program+' failed; inspect '+str(root/(program+'.log')))
    try:
        try:
            command('initdb','-D',data,'-U','postgres','--auth=scram-sha-256','--pwfile',pwfile,'--no-locale','--encoding=UTF8')
        finally:
            pwfile.unlink(missing_ok=True)
        command('pg_ctl','-D',data,'-l',root/'postgres-server.log','-o',f'-h 127.0.0.1 -p {pg_port}','-w','start')
        with psycopg.connect(host='127.0.0.1',port=pg_port,user='postgres',password=password,dbname='postgres',autocommit=True) as c:
            for role in roles:
                if role!='postgres':c.execute(sql.SQL('CREATE ROLE {}').format(sql.Identifier(role)))
            c.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(sql.Identifier(settings.postgres_database),sql.Identifier(settings.postgres_owner_role)))
        env['PGOPTIONS']='-c role='+settings.postgres_owner_role
        print('Restoring SQL into the disposable native PostgreSQL server',flush=True)
        command('pg_restore','--no-password','--no-owner','--exit-on-error','--single-transaction',
                '--dbname',settings.postgres_database,capture/'postgres.dump')
        restored = settings.model_copy(update=dict(postgres_port=pg_port,postgres_app_user='postgres',
            postgres_app_password=password,postgres_migrator_user='postgres',postgres_migrator_password=password,
            native_analytics_root=restored_lake))
        with psycopg.connect(host='127.0.0.1',port=pg_port,user='postgres',password=password,
                              dbname=settings.postgres_database) as c:
            if table_counts(c)!=expected_counts:raise ValueError('Restored SQL table counts differ')
        remapped = json.loads(json.dumps(dependencies))
        remapped['files'] = {str(restored_lake/Path(name).relative_to(native_root)) if Path(name).is_relative_to(native_root) else name:h
                            for name,h in dependencies['files'].items()}
        verify_dependencies(restored,remapped)
        if control_state(PostgresStore.from_settings(restored))!=proof['control']:
            raise ValueError('Restored portfolio control differs')
        analytics = NativeAnalyticsStore.from_settings(restored)
        if not analytics.latest('governance/catalog'):raise ValueError('Restored catalog is unavailable')
        phase=dict(passed=True,at=datetime.now(UTC).isoformat(),verification_sha256=sha256(verification),
            dump_sha256=sha256(capture/'postgres.dump'),copied_fragments=copied,table_counts=expected_counts,
            dependencies_verified=True,control_unchanged=True,
            capture_hashes={name:sha256(capture/name) for name in
                ('postgres.dump','dependencies.json','nats/streams.json','nats/ST_EVENTS.snapshot')})
        write_json(root/'database-acceptance.json',phase)
        print('SQL tables, immutable dependencies, publications and control verified; restoring JetStream',flush=True)
        finish_queue(root,verification)
    finally:
        if (data/'postmaster.pid').exists():command('pg_ctl','-D',data,'-m','fast','-w','stop')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--verification',type=Path,required=True)
    parser.add_argument('--resume-queue',action='store_true',help='Retry only after a successful, hash-pinned database phase')
    parser.add_argument('--postgres-bin',type=Path,default=Path('C:/Program Files/PostgreSQL/18/bin'))
    args=parser.parse_args()
    if args.resume_queue:
        finish_queue(args.root.resolve(),args.verification)
    else:
        main(args.root,args.verification,args.postgres_bin)
