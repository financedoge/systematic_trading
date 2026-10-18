"""Immutable compressed fragments with PostgreSQL atomic manifest commits.

Each query uses its own in-memory DuckDB connection. No process opens a shared
writable DuckDB database. Payload strings remain exact, including decimal text.
"""
from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from hashlib import sha256, file_digest
import json
import os
from pathlib import Path
from threading import BoundedSemaphore
from uuid import uuid4

from psycopg.types.json import Jsonb

from systematic_trading.market_data.analytics_store import digest, encode, timestamp
from systematic_trading.storage.postgres import PostgresStore

QUERY_SLOTS = BoundedSemaphore(2)
INDEX_COLUMNS = ('point_key', 'entity', 'family', 'observed_at', 'available_at', 'source_id', 'version')


@lru_cache(maxsize=8)
def native_pool(config):
    import atexit
    from psycopg_pool import ConnectionPool
    from psycopg.rows import dict_row
    pool=ConnectionPool(kwargs=dict(host=config.host,port=config.port,dbname=config.database,
        user=config.user,password=config.password,sslmode=config.sslmode,application_name='native-analytics',
        options='-c timezone=UTC',row_factory=dict_row),min_size=1,max_size=4,timeout=30,open=True)
    atexit.register(pool.close)
    return pool


class PostgresManifestCatalog:
    def __init__(self, store, workspace):
        self.store, self.workspace = store, workspace

    def connect(self):
        return native_pool(self.store.config).connection()

    def initialize(self):
        with self.connect() as c:
            if not c.execute("SELECT to_regclass('native_analytics.datasets') AS present").fetchone()['present']:
                raise RuntimeError('Apply native analytical PostgreSQL migrations before startup')

    @contextmanager
    def writer(self, key):
        with self.connect() as c:
            c.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s,0))', (self.workspace + '/' + key,))
            yield c

    def get(self, key, revision=None, *, connection=None):
        def read(c):
            if revision is None:
                return c.execute('SELECT d.manifest,d.manifest_sha256,d.revision FROM native_analytics.heads h '
                    'JOIN native_analytics.datasets d USING(workspace,dataset_key,revision) '
                    'WHERE h.workspace=%s AND h.dataset_key=%s', (self.workspace,key)).fetchone()
            return c.execute('SELECT manifest,manifest_sha256,revision FROM native_analytics.datasets '
                'WHERE workspace=%s AND dataset_key=%s AND revision=%s', (self.workspace,key,revision)).fetchone()
        if connection is not None:
            return read(connection)
        with self.connect() as c:
            return read(c)

    def commit(self, c, key, revision, manifest, *, expected_head=None, advance=True):
        previous = self.get(key, connection=c)
        if (previous['revision'] if previous else None) != expected_head:
            raise ValueError('Native publication head changed; retry from a fresh snapshot')
        identity = digest(encode(manifest))
        c.execute('INSERT INTO native_analytics.datasets(workspace,dataset_key,revision,manifest_sha256,manifest) '
                  'VALUES(%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING',
                  (self.workspace,key,revision,identity,Jsonb(manifest)))
        recorded = self.get(key, revision, connection=c)
        if recorded['manifest_sha256'] != identity:
            raise ValueError('Immutable native dataset revision already has different contents')
        if advance:
            c.execute('INSERT INTO native_analytics.heads(workspace,dataset_key,revision) VALUES(%s,%s,%s) '
                      'ON CONFLICT(workspace,dataset_key) DO UPDATE SET revision=excluded.revision,changed_at=now()',
                      (self.workspace,key,revision))


class ParquetLake:
    def __init__(self, root, catalog, *, memory_limit='1GB', threads=2, spill_limit='10GB'):
        self.root = Path(root).resolve()
        self.catalog = catalog
        self.memory_limit, self.threads, self.spill_limit = memory_limit, threads, spill_limit
        self._verified = {}
        self._initialized = False

    @classmethod
    def from_settings(cls, settings):
        workspace = settings.analytics_workspace or digest(str(settings.data_dir.resolve()).lower())
        return cls(settings.native_analytics_root, PostgresManifestCatalog(PostgresStore.from_settings(settings),workspace))

    def initialize(self):
        if self._initialized:
            return
        self.catalog.initialize()
        for name in ('parquet', 'staging', 'scratch'):
            (self.root / name).mkdir(parents=True,exist_ok=True)
        self._initialized = True

    def prepare(self, rows):
        """Stream rows in <=8 MiB batches; verify independently before PG commit."""
        import pyarrow as pa
        import pyarrow.parquet as pq
        self.initialize()
        schema = pa.schema([(name,pa.string()) for name in (*INDEX_COLUMNS, 'record')])
        batch, batch_bytes, total, logical = [], 0, 0, sha256()
        fragments = []
        def flush():
            if not batch:
                return
            temporary = self.root / 'staging' / (uuid4().hex + '.parquet')
            try:
                pq.write_table(pa.Table.from_pylist(batch,schema=schema),temporary,compression='zstd',row_group_size=len(batch))
                with temporary.open('rb+') as stream:
                    os.fsync(stream.fileno())
                    checksum = file_digest(stream,'sha256').hexdigest()
                with pq.ParquetFile(temporary) as reader:
                    actual = reader.read(columns=['record'],use_threads=False).column('record').to_pylist()
                if actual != [row['record'] for row in batch]:
                    raise ValueError('Parquet canonical row readback mismatch')
                destination = self.root / 'parquet' / checksum[:2] / (checksum + '.parquet')
                destination.parent.mkdir(parents=True,exist_ok=True)
                if destination.exists():
                    self.verify_file(dict(path=destination.relative_to(self.root).as_posix(),sha256=checksum))
                    temporary.unlink()
                else:
                    temporary.rename(destination)
                fragments.append(dict(path=destination.relative_to(self.root).as_posix(),sha256=checksum,
                                      rows=len(batch),bytes=destination.stat().st_size))
            finally:
                temporary.unlink(missing_ok=True)
        for row in rows:
            record = encode(row)
            if batch and (batch_bytes + len(record.encode()) > 8*1024**2 or len(batch) >= 8192):
                flush(); batch, batch_bytes = [], 0
            logical.update(record.encode() + b'\n')
            indexed = {name: str(row[name]) if row.get(name) is not None else None for name in INDEX_COLUMNS}
            for name in ('observed_at','available_at'):
                indexed[name] = timestamp(row.get(name))
            batch.append(dict(indexed,record=record))
            batch_bytes += len(record.encode()); total += 1
        flush()
        return dict(storage_format='parquet-v1', row_count=total, logical_sha256=logical.hexdigest(),fragments=fragments)

    def verify_file(self, fragment):
        unresolved = self.root / fragment['path']
        path = unresolved.resolve()
        if not path.is_relative_to(self.root / 'parquet') or unresolved.is_symlink():
            raise ValueError('Unsafe native fragment path')
        info = path.stat()
        identity = (str(path),info.st_dev,info.st_ino,info.st_size,info.st_mtime_ns)
        if self._verified.get(identity) != fragment['sha256']:
            with path.open('rb') as stream:
                if file_digest(stream,'sha256').hexdigest() != fragment['sha256']:
                    raise ValueError('Native fragment checksum mismatch: ' + str(path))
            if len(self._verified)>10000:
                self._verified.clear()
            self._verified[identity] = fragment['sha256']
        return str(path)

    def manifest(self, key, revision=None, *, connection=None):
        record = self.catalog.get(key,revision,connection=connection)
        if record is None:
            return None
        if digest(encode(record['manifest'])) != record['manifest_sha256']:
            raise ValueError('Native manifest identity mismatch')
        return record['manifest']

    def select(self, manifests, *, filters=(), order=(), limit=None):
        """Parameter-bound projections over explicitly pinned fragments."""
        paths, conditions, values = self.pinned_source(manifests)
        if not paths:
            return []
        for column, operator, value in filters:
            if column not in INDEX_COLUMNS or operator not in ('=', '>=', '<=', '>', '<', 'LIKE'):
                raise ValueError('Unsupported native query filter')
            conditions.append(f'"{column}" {operator} ?'); values.append(value)
        ordering = []
        for name, direction in order:
            if name not in INDEX_COLUMNS or direction not in ('ASC','DESC'):
                raise ValueError('Unsupported native ordering')
            ordering.append(f'"{name}" {direction} NULLS LAST')
        query = 'SELECT record FROM read_parquet(?)'
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        if ordering:
            query += ' ORDER BY ' + ','.join(ordering)
        if limit is not None:
            if not isinstance(limit,int) or limit < 0:
                raise ValueError('Invalid row limit')
            query += ' LIMIT ?'; values.append(limit)
        return [json.loads(row['record']) for row in self.query_files(query,values)]

    def pinned_source(self,manifests):
        manifests=[m for m in manifests if m]
        paths=sorted({self.verify_file(f) for m in manifests for f in m['fragments']})
        conditions,values=[],[paths]
        selected=[m['selection'] for m in manifests if 'selection' in m]
        if selected:
            if len(selected)!=len(manifests): raise ValueError('Mixed selected and unselected publication manifests')
            conditions.append('(source_id,version) IN (SELECT unnest(?),unnest(?))')
            values.extend([[s[0] for s in selected],[s[1] for s in selected]])
        return paths,conditions,values

    def query_files(self, query, parameters):
        """Internal fixed SQL only; callers bind all values and verified paths."""
        import duckdb
        with QUERY_SLOTS, duckdb.connect(config=dict(memory_limit=self.memory_limit,threads=str(self.threads),
                 max_temp_directory_size=self.spill_limit,temp_directory=str(self.root/'scratch'/uuid4().hex))) as connection:
            result = connection.execute(query,parameters)
            names = [column[0] for column in result.description]
            return [dict(zip(names,row)) for row in result.fetchall()]

    def replace(self, key, revision, rows, *, expected_head=None):
        with self.catalog.writer(key) as c:
            manifest = self.prepare(rows)
            self.catalog.commit(c,key,revision,manifest,expected_head=expected_head)
            return manifest
