"""Admission is causal, never fills observations, and preserves source receipts."""
from datetime import date, timedelta
import gzip
import json

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.etf_expansion import admission_for_day, load_published_pool
from systematic_trading.research.governed_inputs import GovernedInputs


def test_liquidity_duplicates_and_future_invariance():
    days = [str(date(2020,1,1)+timedelta(days=i)) for i in range(300)]
    records = {s:[dict(trade_date=d,raw_close=10,raw_volume=v) for d in days]
               for s,v in [('A',1_000_000),('B',2_000_000),('C',10)]}
    candidates = [dict(symbol=s,candidate_id=s,duplicate_review_group='same' if s!='C' else 'other') for s in records]
    result = admission_for_day(records,candidates,days[270])
    assert result['admitted']==['B']
    assert result['excluded']['A']=='Duplicate representative: B'
    assert 'thresholds' in result['excluded']['C']
    for rows in records.values():
        for r in rows[270:]:
            r['raw_volume']=None
    assert admission_for_day(records,candidates,days[270])==result
    assert not admission_for_day(records,candidates,days[250])['admitted']


def test_missing_units_and_gaps_are_excluded_without_fill(tmp_path):
    dates=['2026-10-08','2026-10-09','2026-10-12']
    candidates=[]
    for symbol in ['A','GAP','RAW']:
        candidates.append(dict(symbol=symbol,requires_recorder=False))
        write_json(tmp_path/f'audits/{symbol}.json',dict(status='audited_with_limitations'))
        rows=[dict(symbol=symbol,trade_date=d,raw_volume=100,
                   **{f'{basis}_{field}':10 for basis in ('raw','adjusted') for field in ('open','high','low','close')}) for d in dates]
        if symbol=='GAP':rows.pop(1)
        if symbol=='RAW':rows[1]['raw_volume']=None
        (tmp_path/'bars').mkdir(exist_ok=True)
        with gzip.open(tmp_path/f'bars/{symbol}.jsonl.gz','wt') as f:
            f.write('\n'.join(json.dumps(r) for r in rows))
    write_json(tmp_path/'manifest.json',{p.relative_to(tmp_path).as_posix():sha256(p) for p in tmp_path.rglob('*') if p.is_file()})
    reader=GovernedInputs(tmp_path,sha256(tmp_path/'manifest.json'))
    pool=load_published_pool(reader,candidates,through=dates[-1])
    assert list(pool['bars'])==['A']
    assert set(pool['exclusions'])=={'RAW','GAP'}
    assert pool['provenance']['batch']==reader.batch
    assert 'bars/RAW.jsonl.gz' in pool['provenance']['files']


def test_nested_governed_parent_preserves_verified_hash(tmp_path):
    parent=None
    for n in range(3):
        root=tmp_path/str(n);root.mkdir()
        if parent is None:write_json(root/'value.json',{'value':1})
        else:write_json(root/'parent.json',dict(root=str(parent),batch=sha256(parent/'manifest.json')))
        write_json(root/'manifest.json',{p.name:sha256(p) for p in root.iterdir()})
        parent=root
    reader=GovernedInputs(root,sha256(root/'manifest.json'))
    result=reader.checked('value.json')
    assert reader.used['parent/value.json']==sha256(result)
