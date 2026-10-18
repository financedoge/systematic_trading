from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import psycopg
from psycopg import sql
import pytest

from test_execution_recovery import isolated_postgres
from systematic_trading.market_data.native_analytics import NativeAnalyticsStore
from systematic_trading.storage.parquet_lake import ParquetLake, PostgresManifestCatalog
from systematic_trading.storage.postgres import PostgresConnectionConfig, PostgresStore


@pytest.fixture
def native(isolated_postgres,tmp_path):
    name='native_'+uuid4().hex[:12]
    with psycopg.connect(**isolated_postgres,dbname='postgres',autocommit=True) as c:
        c.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        if not c.execute("SELECT 1 FROM pg_roles WHERE rolname='st_app'").fetchone():
            c.execute('CREATE ROLE st_app')
    with psycopg.connect(**isolated_postgres,dbname=name,autocommit=True) as c:
        c.execute('CREATE SCHEMA ops')
        for migration in ('003_lean_research_runs.sql','004_lean_append_only.sql',
                          '006_native_analytics.sql','007_native_publication_heads.sql'):
            c.execute((Path('deploy/postgres/migrations')/migration).read_text())
    config=PostgresConnectionConfig(database=name,**isolated_postgres)
    catalog=PostgresManifestCatalog(PostgresStore(config),'fixture')
    return NativeAnalyticsStore(ParquetLake(tmp_path/'lake',catalog,memory_limit='64MB'))


def point(key='a',value='old'):
    return dict(point_key=key,family='fixture',entity='ABC',observed_at='2026-10-17',payload=value)


def test_backup_inventory_uses_exported_sql_snapshot(native,tmp_path):
    from systematic_trading.config import AppSettings
    from systematic_trading.storage.dependencies import dependency_receipt
    native.publish('fixture','old',[point()])
    with native.catalog.connect() as connection:
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        assert connection.execute('SELECT pg_export_snapshot() AS id').fetchone()['id']
        native.publish('fixture','new',[point(value='new')])
        view=NativeAnalyticsStore(ParquetLake(native.lake.root,
            PostgresManifestCatalog(native.catalog.store,native.workspace)))
        view.catalog.connect=lambda: nullcontext(connection)
        settings=AppSettings(_env_file=None,data_dir=tmp_path,market_data_store_backend='parquet',
            strategy_monitoring_config_path=tmp_path/'missing-config.json')
        receipt=dependency_receipt(settings,analytics=view)
        assert receipt['publications']=={'fixture':'old'}
        assert all('/new' not in d['dataset_key'] for d in receipt['native_analytics']['datasets'])
    assert native.latest('fixture')['version']=='new'


def test_pinned_reader_checks_publication_manifest_reference(native,monkeypatch):
    native.publish('fixture','one',[point()])
    publication=native.publication('fixture','one')
    publication['datasets']['observations']['manifest_sha256']='0'*64
    monkeypatch.setattr(native,'publication',lambda *args,**kwargs:publication)
    with pytest.raises(ValueError,match='publication manifest'):
        native.pinned_rows('observations','fixture','one')


def test_atomic_failure_preserves_previous_head_and_hides_orphan(native,monkeypatch):
    native.publish('fixture','one',[point()])
    original=native.lake.prepare
    calls=0
    def fail_documents(rows):
        nonlocal calls
        calls+=1
        if calls==2:raise RuntimeError('simulated interrupted document write')
        return original(rows)
    monkeypatch.setattr(native.lake,'prepare',fail_documents)
    with pytest.raises(RuntimeError,match='interrupted'):
        native.publish('fixture','two',[point(value='new')])
    assert native.latest('fixture')['version']=='one'
    assert native.publication('fixture','two') is None
    assert native.observations('fixture')[0]['payload']=='old'
    with native.catalog.connect() as c:
        assert c.execute("SELECT count(*) n FROM native_analytics.datasets WHERE dataset_key LIKE '%/two'").fetchone()['n']==0


def test_concurrent_same_publication_serializes_and_immutable_evidence_rejects_change(native):
    with ThreadPoolExecutor(2) as pool:
        changed=list(pool.map(lambda _:native.publish('fixture','one',[point()]),range(2)))
    assert sorted(changed)==[False,True]
    for table in ('datasets','publications','retirements'):
        with pytest.raises(psycopg.errors.RaiseException,match='append-only'):
            with native.catalog.connect() as c:c.execute('DELETE FROM native_analytics.'+table)


def test_packed_sources_do_not_leak_stale_or_unselected_rows(native):
    publications=[];rows=[]
    for source,version in [('a','old'),('b','one'),('c','one')]:
        publications.append(dict(source_id=source,version=version,published_at=datetime.now(UTC),
            observation_count=1,document_count=0,provenance='{}'))
        rows.append(dict(workspace='fixture',source_id=source,version=version,**point(value=source+version)))
    native.publish_migration_batch(publications,rows,[])
    native.publish('a','new',[point(value='anew')])
    assert native.observations('a')[0]['payload']=='anew'
    assert native.pinned_rows('observations','a','old')[0]['payload']=='aold'
    assert [r['payload'] for r in native.current_observations('b')]==['bone']
    assert {r['payload'] for r in native.current_observations('')}=={'anew','bone','cone'}
    assert native.publication_counts('a','old')['observations']==1
    assert native.publish('a','old',[point()])
    assert native.latest('a')['version']=='old'


def test_bad_migration_count_cannot_publish_any_source(native):
    publication=dict(source_id='a',version='one',published_at=datetime.now(UTC),
        observation_count=2,document_count=0,provenance='{}')
    row=dict(workspace='fixture',source_id='a',version='one',**point())
    with pytest.raises(ValueError,match='count mismatch'):
        native.publish_migration_batch([publication],[row],[])
    assert native.latest('a') is None
