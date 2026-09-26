"""Publication workers may resume without exposing partial global catalogs."""
import gzip
import importlib.util
import json
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location(
    'governance_publisher', Path(__file__).parents[1] / 'scripts/publish_governed_prices.py')
publisher = importlib.util.module_from_spec(spec)
spec.loader.exec_module(publisher)


def fixture_worker(tmp_path, monkeypatch, committed=False):
    root, fresh = tmp_path/'built', tmp_path/'fresh'
    for folder in ('bars', 'comparisons', 'actions', 'audits'):
        (root/folder).mkdir(parents=True)
    (fresh/'metadata').mkdir(parents=True)
    (fresh/'metadata/AAPL.json').write_text('{"status":"ok"}', encoding='utf8')
    (root/'audits/AAPL.json').write_text('{"symbol":"AAPL"}', encoding='utf8')
    for folder, values in [('bars',[{'trade_date':'2020-01-02'}]),
                           ('comparisons',[{'trade_date':'2020-01-02','source_id':'s'}]),
                           ('actions',[{'date':'2020-01-02','type':'dividend'}])]:
        with gzip.open(root/folder/'AAPL.jsonl.gz','wt',encoding='utf8') as output:
            output.write('\n'.join(json.dumps(value) for value in values))
    source = fresh/'original.json'
    source.write_bytes(b'{"original":true}\r\n')
    indexed = {'AAPL':[dict(path=str(source), source_id='original', already_archived=False,
                           raw_sha256=publisher.digest(source.read_bytes()))]}
    calls = []

    class Store:
        def insert_verified(self, table, batch, symbol, values):
            calls.append(('rows',table,batch,symbol,values))

    class Analytics:
        def publish(self, source_id, version, observations, docs, **kwargs):
            calls.append(('publication',source_id,version,observations,docs))

    current = {'governance-batch/batch/AAPL':{}} if committed else {}
    monkeypatch.setattr(publisher,'_worker',(root,fresh,'batch',indexed,current,Analytics(),Store()))
    return source,calls


def test_worker_commits_only_symbol_after_verified_inserts(tmp_path,monkeypatch):
    _,calls=fixture_worker(tmp_path,monkeypatch)
    assert publisher.publish_symbol({'symbol':'AAPL'}) == dict(
        bars=1, comparisons=1, actions=1, source_documents=3, symbols=1)
    assert [call[0] for call in calls] == ['rows','rows','publication']
    assert calls[-1][1]=='governance-batch/batch/AAPL'
    assert calls[-1][4][1]['payload']=='{"original":true}\r\n'


def test_worker_resume_skips_already_verified_symbol(tmp_path,monkeypatch):
    _,calls=fixture_worker(tmp_path,monkeypatch,committed=True)
    assert publisher.publish_symbol({'symbol':'AAPL'})['bars']==1
    assert calls==[]


def test_worker_rejects_changed_original_before_writing(tmp_path,monkeypatch):
    source,calls=fixture_worker(tmp_path,monkeypatch)
    source.write_text('changed',encoding='utf8')
    with pytest.raises(ValueError,match='Source hash mismatch'):
        publisher.publish_symbol({'symbol':'AAPL'})
    assert calls==[]


def test_quarantined_policy_cannot_commit_a_catalog(tmp_path):
    (tmp_path/'policy.json').write_text('{"version":1}',encoding='utf8')
    with pytest.raises(ValueError,match='Quarantined pre-listing policy'):
        publisher.main(tmp_path,tmp_path)
