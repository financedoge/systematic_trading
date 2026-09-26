import gzip
import json
from pathlib import Path

import numpy as np
import pytest

from systematic_trading.lean.contracts import sha256
from systematic_trading.research.constituent_signals import WINDOW
from systematic_trading.research.governed_inputs import GovernedInputs, diagnostic_features, etf_bar, fixed_cohort_return


def test_governed_reader_checks_batch_file_hash_and_date_order(tmp_path: Path):
    (tmp_path/'bars').mkdir()
    path=tmp_path/'bars/X.jsonl.gz'
    with gzip.open(path,'wt') as out:
        out.write(json.dumps(dict(trade_date='2020-01-02',raw_close=None))+'\n')
    (tmp_path/'manifest.json').write_text(json.dumps({'bars/X.jsonl.gz':sha256(path)}))
    reader=GovernedInputs(tmp_path,sha256(tmp_path/'manifest.json'))
    assert reader.rows('X','2020-01-01','2020-02-01')[0]['raw_close'] is None
    with pytest.raises(ValueError,match='manifest mismatch'):
        GovernedInputs(tmp_path,'wrong')
    path.write_bytes(b'changed')
    with pytest.raises(ValueError,match='Changed'):
        reader.rows('X','2020-01-01','2020-02-01')


def test_raw_dollar_concentration_survives_split_but_share_hhi_changes():
    close=np.ones((WINDOW,3))*np.array([10.,20.,30.])
    volume=np.ones_like(close)*100
    adjusted=close.copy()
    before,_=diagnostic_features(close,volume,adjusted,np.arange(3),np.ones(3),np.ones(3,dtype=bool))
    close[-1,0]/=2;volume[-1,0]*=2
    after,_=diagnostic_features(close,volume,adjusted,np.arange(3),np.ones(3),np.ones(3,dtype=bool))
    assert after['values']['dollar_hhi']==pytest.approx(before['values']['dollar_hhi'])
    assert after['values']['dollar_d2']==pytest.approx(0)
    assert after['values']['shares_hhi']!=pytest.approx(before['values']['shares_hhi'])
    assert after['values']['hhi_smoothed']==pytest.approx(after['values']['dollar_ema'])


def test_missing_raw_does_not_borrow_adjusted_prices_or_reduce_coverage_denominator():
    raw=np.ones((WINDOW,3))*10;adjusted=raw.copy();volume=np.ones_like(raw)*100
    raw[0,0]=np.nan
    result,valid=diagnostic_features(raw,volume,adjusted,np.arange(3),np.array([80,10,10]),np.ones(3,dtype=bool))
    assert valid.tolist()==[False,True,True]
    assert result['value_coverage']==pytest.approx(.2)
    assert result['expected_names']==3


def test_forward_label_refuses_survivor_reweighting():
    a=np.array([10.,20.]);b=np.array([12.,np.nan]);w=np.array([.8,.2]);selected=np.array([True,True])
    assert fixed_cohort_return(a,b,w,selected) is None
    assert fixed_cohort_return(a,np.array([12.,18.]),w,selected)==pytest.approx(.14)
    assert fixed_cohort_return(a,b,w,np.array([False,False])) is None


def test_etf_convention_explicit_and_missing_adjusted_price_rejected():
    row=dict(trade_date='2020-01-02',adjusted_open=9,adjusted_high=11,adjusted_low=8,adjusted_close=10,source_volume=100,raw_close=20)
    assert etf_bar(row)['close']=='10'
    assert etf_bar(row)['volume']==100
    with pytest.raises(ValueError,match='Unsupported adjusted'):
        etf_bar(dict(row,adjusted_close=None))
