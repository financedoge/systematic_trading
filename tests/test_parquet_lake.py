from contextlib import contextmanager
from copy import deepcopy
import json
from threading import Lock

import pytest

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.market_data.native_market import NativeMarketDataClient
from systematic_trading.storage.parquet_lake import ParquetLake


class Catalog:
    workspace = 'fixture'
    def __init__(self):
        self.rows, self.heads, self.lock = {}, {}, Lock()
    def initialize(self):
        pass
    @contextmanager
    def writer(self, key):
        with self.lock:
            before = deepcopy((self.rows,self.heads))
            try: yield self
            except BaseException:
                self.rows,self.heads = before
                raise
    def get(self,key,revision=None,**kwargs):
        revision = revision or self.heads.get(key)
        return self.rows.get((key,revision))
    def commit(self,c,key,revision,manifest,*,expected_head=None,advance=True):
        if self.heads.get(key) != expected_head:
            raise ValueError('head changed')
        row = dict(revision=revision,manifest=manifest,manifest_sha256=digest(encode(manifest)))
        if (key,revision) in self.rows and self.rows[key,revision] != row:
            raise ValueError('Immutable revision changed')
        self.rows[key,revision] = row
        if advance:self.heads[key] = revision


@pytest.fixture
def lake(tmp_path):
    return ParquetLake(tmp_path,Catalog(),memory_limit='64MB',spill_limit='128MB')


def test_exact_payload_and_pinned_reader_survive_next_publication(lake):
    rows = [dict(point_key='a',observed_at='2026-10-15',payload='{"price":"0.12345678901234567890","missing":null,"name":"沪"}')]
    lake.replace('history','one',rows)
    pinned = lake.manifest('history')
    lake.replace('history','two',[dict(rows[0],point_key='b')],expected_head='one')
    assert lake.select([pinned]) == rows
    assert lake.select([lake.manifest('history')])[0]['point_key']=='b'
    assert lake.select([pinned],filters=[('observed_at','>=','2026-10-16')])==[]


def test_stale_writer_and_revision_reuse_cannot_replace_committed_data(lake):
    lake.replace('history','one',[dict(point_key='a',payload='a')])
    with pytest.raises(ValueError,match='head changed'):
        lake.replace('history','two',[dict(point_key='b')])
    with pytest.raises(ValueError,match='Immutable'):
        lake.replace('history','one',[dict(point_key='changed')],expected_head='one')
    assert lake.select([lake.manifest('history')])[0]['point_key']=='a'


def test_uncommitted_fragments_are_not_reader_visible(lake):
    lake.prepare([dict(point_key='partial')])
    assert lake.manifest('history') is None
    assert lake.select([None])==[]


def test_shared_fragment_reads_only_selected_source_and_revision_once(lake):
    rows=[dict(source_id=source,version=version,point_key='same',payload=source+version)
          for source,version in [('a','old'),('a','new'),('b','one'),('c','one')]]
    manifest=lake.prepare(rows)
    selected=[dict(manifest,selection=('a','new')),dict(manifest,selection=('b','one'))]
    actual=lake.select(selected,order=[('source_id','ASC')])
    assert actual==[rows[1],rows[2]]
    assert lake.select([dict(manifest,selection=('a','old'))])==[rows[0]]
    assert lake.select([dict(manifest,selection=('absent','one'))])==[]


def test_corrupt_fragment_and_unsafe_reference_rejected(lake):
    lake.replace('history','one',[dict(point_key='a')])
    manifest = lake.manifest('history')
    path = lake.root / manifest['fragments'][0]['path']
    path.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='checksum'):
        lake.select([manifest])
    with pytest.raises(ValueError,match='Unsafe'):
        lake.verify_file(dict(path='../unrelated',sha256='0'*64))


def test_market_updates_keep_newer_observation_and_do_not_mutate_old_manifest(lake):
    client = NativeMarketDataClient(lake)
    row = dict(symbol='ABC',trade_date='2026-10-15',close=12.25,ingested_at='2026-10-16T12:00:00+00:00')
    client.insert_daily_bar_rows([row])
    old = lake.manifest('market/daily_bars/ABC')
    client.insert_daily_bar_rows([dict(row,close=99,ingested_at='2026-10-16T11:00:00+00:00')])
    assert client.query_daily_bars(symbol='abc')[0]['close']==12.25
    assert client.query_daily_bar_dates(symbol='ABC')==['2026-10-15']
    assert client.delete_daily_bar_dates(symbol='ABC',trade_dates=['2026-10-15'])==1
    assert client.query_daily_bars(symbol='ABC')==[]
    assert lake.select([old])[0]['close']==12.25
