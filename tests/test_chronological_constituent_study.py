import copy
from datetime import date
from pathlib import Path
import sys

import pytest

from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.research import current_sota_definition, instantiate_overlays
from systematic_trading.research.chronological_tree import select_base_tree
from systematic_trading.lean.contracts import BacktestRunSpec, write_json, sha256
from test_flow_concentration import histories

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from prepare_tenyear_constituent_study import fit_base_models
from fetch_long_constituent_data import parse_snapshot
from prepare_long_constituent_features import build


def schedule():
    model=instantiate_overlays(current_sota_definition())[1].model.to_dict()
    return {'2024-01-01':dict(fit_as_of='2024-01-01',max_label_end='2023-12-29',
        max_feature_date='2023-11-30',training_samples=120,model=model)}


def test_base_tree_never_uses_a_future_fit_or_incomplete_label():
    data=schedule()
    with pytest.raises(ValueError,match='No historical'):
        select_base_tree(data,'2023-12-29')
    expected=select_base_tree(data,'2024-04-30')
    data['2025-01-01']={'malformed_future_model':True}
    assert select_base_tree(data,'2024-04-30')==expected
    data['2024-01-01']['max_label_end']='2024-01-01'
    with pytest.raises(ValueError,match='future labels'):
        select_base_tree(data,'2024-04-30')


def test_expanding_fit_is_unchanged_by_future_outcomes():
    template=instantiate_overlays(current_sota_definition())[1].model
    records=[dict(known_through='2023-01-31',label_end='2023-02-28',inputs={template.feature_names[0]:i/100},
        relative_return=i/1000) for i in range(120)]
    expected=fit_base_models(records,template,[2024])
    records.append(dict(known_through='2023-12-29',label_end='2024-01-02',inputs={},relative_return=999))
    assert fit_base_models(records,template,[2024])==expected


def test_target_schedule_is_causal_and_default_model_is_preserved():
    rows=histories()
    day=date(2024,5,1)
    expected=targets_for_day(rows,day)
    assert targets_for_day(rows,day,base_tree_models=schedule())==expected
    changed=copy.deepcopy(rows)
    for series in changed.values():
        for row in series:
            if row['trade_date']>=str(day):
                row.update(close='99999',high='99999',low='99999',open='99999')
    models=schedule();models['2025-01-01']={'malformed':True}
    assert targets_for_day(changed,day,base_tree_models=models)==expected
    models['2024-01-01']['model']['root'].update(feature=None,left=None,right=None,value=0)
    targets_for_day(rows,day,base_tree_models=models)
    assert targets_for_day(rows,day)==expected


def test_benchmark_cannot_claim_a_tree_schedule():
    with pytest.raises(ValueError,match='benchmark'):
        BacktestRunSpec(strategy='benchmark',base_tree_model_schedule=True,start_date='2024-01-02',
            end_date='2024-02-01',warmup_start='2022-01-03',strategy_hash='x',source_hash='y',repository_commit='z')


def test_wrong_issuer_holdings_date_is_rejected():
    with pytest.raises(ValueError,match='date mismatch'):
        parse_snapshot(b'Fund\nFund Holdings as of,"31-Dec-2015"\n','2016-01-29')


def test_archive_features_exclude_incomplete_windows_and_stale_holdings(tmp_path):
    source,archive,out=[tmp_path/p for p in ('source','archive','out')]
    for p in (source/'holdings',source/'bars_metadata',source/'bars_raw',archive,out):
        p.mkdir(parents=True,exist_ok=True)
    write_json(source/'symbol_aliases.json',{'aliases':{}})
    write_json(source/'protocol.json',{'sectors':['Technology']})
    write_json(source/'holdings/2012-01-31.json',dict(as_of='2012-01-31',rows=[dict(ticker='AAA',yahoo='AAA',name='Alpha',sector='Technology',market_value=100)]))
    write_json(source/'bars_metadata/AAA.json',dict(status='ok',name='Alpha'))
    # An HTTP-success response without any prices is still missing data.
    write_json(source/'bars_raw/AAA.json',{'chart':{'result':[{'indicators':{'quote':[{}]}}]}})
    write_json(source/'data_manifest.json',{p.relative_to(source).as_posix():sha256(p) for p in source.rglob('*') if p.is_file()})
    write_json(archive/'archive_index.json',[])
    write_json(archive/'archive_manifest.json',{'archive_index.json':sha256(archive/'archive_index.json')})
    write_json(tmp_path/'bars.json',{'SPY':[]})
    build(dict(stock_root=str(source),archive_root=str(archive),etf_snapshot=str(tmp_path),end='2012-09-28'),out)
    import json
    rows=json.loads((out/'features.json').read_text())['45']
    assert rows
    assert max(rows)<='2012-06-19'
    assert all(row['value_coverage']==0 and row['scores'] is None for row in rows.values())


def test_archive_keeps_exact_crlf_source_bytes(tmp_path,monkeypatch):
    import import_public_equity_archive as importer
    from types import SimpleNamespace
    raw=b'Date,Open,High,Low,Close,Volume\r\n2016-01-04,10,11,9,10,123\r\n'
    (tmp_path/'stock.csv').write_bytes(raw)
    item=dict(provider='stooq2017',symbol='AAA',path='stock.csv',raw_sha256=sha256(tmp_path/'stock.csv'),
              price_convention='adjusted',identity_method='dated ticker')
    write_json(tmp_path/'archive_index.json',[item])
    write_json(tmp_path/'archive_manifest.json',{n:sha256(tmp_path/n) for n in ('stock.csv','archive_index.json')})
    documents=[]
    class Store:
        client=SimpleNamespace(timeout_seconds=0)
        def publication_index(self,prefix):return {}
        def publish_batch(self,batch):
            assert batch[0][2][0]['observed_at'].startswith('2016-01-04')
        def publish(self,source,version,rows,docs,provenance=None):documents.extend(docs)
    monkeypatch.setattr(importer.ResearchBatchAnalytics,'from_settings',lambda settings:Store())
    monkeypatch.setattr(sys,'argv',['import','--root',str(tmp_path)])
    importer.main()
    source=next(d for d in documents if d['point_key']=='stock.csv')
    assert source['payload'].encode('utf8')==raw
