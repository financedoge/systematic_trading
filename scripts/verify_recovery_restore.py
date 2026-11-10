"""Verify files restored FROM NAS in an isolated native database and NATS server.

Run system_backup.py restore-files first. Never reads a production data file as
a substitute for a missing restored dependency. No application or broker workers.
"""
import argparse
import asyncio
from datetime import UTC, datetime
import fnmatch
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import time
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'src'))

import psycopg
from psycopg import sql

from systematic_trading.config import AppSettings
from systematic_trading.market_data.native_analytics import NativeAnalyticsStore
from systematic_trading.storage.nas_sync import file_hash, read_json, write_json
from systematic_trading.storage.recovery_checks import database_checks, recovery_policy_hash, validate_recovery_coverage
from systematic_trading.storage.dependencies import publication_versions, transient_dependency_reason
from verify_native_restore import port, restore_queue


def mapped_path(original, mapping):
    original = Path(original).resolve()
    for row in sorted(mapping, key=lambda r: len(Path(r['original']).parts), reverse=True):
        source, target = Path(row['original']).resolve(), Path(row['restored']).resolve()
        if row['type'] == 'file' and original == source:
            return target/source.name
        if row['type'] == 'dir' and original.is_relative_to(source):
            return target/original.relative_to(source)
    raise ValueError('Dependency absent from restored sources: '+str(original))


def verify_files(dependencies, mapping, *, excludes=(), ignored=None):
    checked = 0
    for original, expected in dependencies['files'].items():
        reason = transient_dependency_reason(original, expected)
        # Older captures pinned loose runtime files which their own explicit
        # exclusion policy omitted. Record that inventory correction; every
        # sealed artifact and every durable file still requires its exact hash.
        if reason and any(fnmatch.fnmatchcase(original.replace('\\', '/').lower(), pattern.lower())
                          for pattern in excludes):
            if ignored is not None:
                ignored.append(dict(path=original, sha256=expected, reason=reason))
            continue
        target = mapped_path(original, mapping)
        if file_hash(target) != expected:
            raise ValueError('Restored dependency hash differs: '+original)
        checked += 1
        if target.name in {'manifest.json', 'run.json'}:
            record = read_json(target)
            inventory = record.get('files', record) if target.name == 'manifest.json' else record.get('artifacts', {})
            if inventory and all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in inventory.values()):
                for name, checksum in inventory.items():
                    p = (target.parent/name).resolve()
                    if not p.is_relative_to(target.parent.resolve()) or file_hash(p) != checksum:
                        raise ValueError('Restored bundle differs: '+str(p))
                    checked += 1
                actual = {p.relative_to(target.parent).as_posix() for p in target.parent.rglob('*') if p.is_file() and p != target}
                if actual != set(inventory):
                    raise ValueError('Restored bundle inventory differs: '+str(target))
    for pin in dependencies['governed_roots']:
        root = mapped_path(pin['root'], mapping)
        if file_hash(root/'manifest.json') != pin['manifest_sha256']:
            raise ValueError('Restored governed manifest differs')
        for name, checksum in read_json(root/'manifest.json').items():
            p = (root/name).resolve()
            if not p.is_relative_to(root) or file_hash(p) != checksum:
                raise ValueError('Restored governed input differs: '+name)
            checked += 1
    return checked


def main(target, snapshot):
    target = target.resolve()
    mapping = read_json(target/'restore-map.json')
    config = read_json(ROOT/'config/system-backup.json')
    source = read_json(target/'restore-source.json')
    if source != dict(snapshot=snapshot, repository=config['repository']):
        raise ValueError('Restore snapshot or repository identity differs')
    capture = mapped_path(Path(config['staging_root'])/'capture', mapping)
    manifest = read_json(capture/'manifest.json')
    if manifest.get('scope') != 'recovery-v1':
        raise ValueError('Recovery-only capture required')
    validate_recovery_coverage(manifest, config, ROOT)
    for name, pin in manifest['files'].items():
        if file_hash(capture/name) != pin['sha256']:
            raise ValueError('Capture hash mismatch: '+name)
    dependencies = read_json(capture/'dependencies.json')
    print('Verifying every restored dependency, bundle and canonical history', flush=True)
    ignored = []
    checked = verify_files(dependencies, mapping, excludes=manifest['excludes'], ignored=ignored)
    print('Verified '+str(checked)+' file dependencies', flush=True)
    expected = read_json(capture/'restore-checks.json')
    server = target/'verification-postgres'
    if server.exists():
        raise ValueError('Use a new isolated PostgreSQL directory')
    binaries = Path('C:/Program Files/PostgreSQL/18/bin')
    pg_port, password = port(), uuid4().hex
    settings = AppSettings()
    pwfile = target/'temporary-init-password.txt'
    pwfile.write_text(password, encoding='ascii')
    env = dict(os.environ, PGHOST='127.0.0.1', PGPORT=str(pg_port), PGUSER='postgres',
               PGPASSWORD=password, PGDATABASE=settings.postgres_database)
    env.pop('PGOPTIONS', None)

    def command(program, *args):
        with (target/(program+'.log')).open('ab') as log:
            result = subprocess.run([str(binaries/(program+'.exe')), *map(str, args)], env=env,
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, timeout=1800,
                creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError(program+' failed; see '+str(target/(program+'.log')))

    queue = None
    try:
        try:
            command('initdb', '-D', server, '-U', 'postgres', '--auth=scram-sha-256',
                    '--pwfile', pwfile, '--no-locale', '--encoding=UTF8')
        finally:
            pwfile.unlink(missing_ok=True)
        command('pg_ctl', '-D', server, '-l', target/'postgres-server.log', '-o',
                f'-h 127.0.0.1 -p {pg_port}', '-w', 'start')
        with psycopg.connect(host='127.0.0.1', port=pg_port, user='postgres', password=password,
                              dbname='postgres', autocommit=True) as c:
            for role in expected['roles']:
                if role != 'postgres':
                    c.execute(sql.SQL('CREATE ROLE {}').format(sql.Identifier(role)))
            c.execute(sql.SQL('CREATE DATABASE {} OWNER {}').format(
                sql.Identifier(settings.postgres_database), sql.Identifier(settings.postgres_owner_role)))
        env['PGOPTIONS'] = '-c role='+settings.postgres_owner_role
        print('Restoring NAS PostgreSQL dump into isolated server', flush=True)
        command('pg_restore', '--no-password', '--no-owner', '--exit-on-error', '--single-transaction',
                '--dbname', settings.postgres_database, capture/'postgres.dump')
        with psycopg.connect(host='127.0.0.1', port=pg_port, user='postgres', password=password,
                              dbname=settings.postgres_database) as c:
            actual = database_checks(c)
        if actual != expected:
            raise ValueError('Restored database counts, roles or portfolio controls differ')
        lake = mapped_path(Path(dependencies['native_analytics']['root'])/'parquet', mapping).parent
        restored = settings.model_copy(update=dict(postgres_port=pg_port, postgres_app_user='postgres',
            postgres_app_password=password, postgres_migrator_user='postgres', postgres_migrator_password=password,
            native_analytics_root=lake, analytics_workspace=dependencies['analytics_workspace']))
        analytics = NativeAnalyticsStore.from_settings(restored)
        if publication_versions(analytics, native=True) != dependencies['publications']:
            raise ValueError('Restored publication heads differ')
        reports = {}
        for source in ('tracked-strategies/calculations', 'strategy-serving', 'governance/catalog'):
            pub = analytics.latest(source)
            if not pub:
                raise ValueError('Missing restored serving publication: '+source)
            rows = analytics.pinned_rows('documents', source, pub['version'])
            for row in rows:
                if row.get('media_type') == 'application/json':
                    json.loads(row['payload'])
            reports[source] = dict(version=pub['version'], documents=len(rows))
        print('Database counts, controls, publication heads and current reports match', flush=True)
        nats_port = port()
        runtime = read_json(ROOT/'config/native-runtime.json')
        nats_config = target/'verification-nats.conf'
        nats_config.write_text(f'listen: "127.0.0.1:{nats_port}"\njetstream {{ store_dir: "{(target/"verification-jetstream").as_posix()}", max_mem_store: 64MB, max_file_store: 8GB }}\n')
        with (target/'verification-nats.log').open('ab') as log:
            queue = subprocess.Popen([str((ROOT/runtime['nats_binary']).resolve()), '-c', str(nats_config)],
                stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(100):
            try:
                with socket.create_connection(('127.0.0.1', nats_port), timeout=.2):
                    break
            except OSError:
                time.sleep(.1)
        states = asyncio.run(restore_queue(f'nats://127.0.0.1:{nats_port}', capture/'nats'))
        receipt = dict(passed=True, scope='recovery-v1', repository=config['repository'], snapshot=snapshot,
            policy_sha256=recovery_policy_hash(config),
            at=datetime.now(UTC).isoformat(), manifest_sha256=file_hash(capture/'manifest.json'),
            verified_file_dependencies=checked, table_counts=actual['table_counts'], controls_match=True,
            excluded_runtime_pins=ignored,
            publication_heads_match=True, reports=reports, nats_streams=states,
            restored_root=str(target), evidence='Actual NAS restore; no production data fallback')
        write_json(target/'acceptance.json', receipt)
        write_json(ROOT/config['retention_acceptance'], receipt)
        print('PASSED: '+str(target/'acceptance.json'), flush=True)
    finally:
        if queue:
            queue.terminate(); queue.wait(timeout=30)
        if (server/'postmaster.pid').exists():
            command('pg_ctl', '-D', server, '-m', 'fast', '-w', 'stop')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target', type=Path, required=True)
    parser.add_argument('--snapshot', required=True)
    args = parser.parse_args()
    if not re.fullmatch('[0-9a-f]{64}', args.snapshot):
        parser.error('Use an exact snapshot ID')
    main(args.target, args.snapshot)
