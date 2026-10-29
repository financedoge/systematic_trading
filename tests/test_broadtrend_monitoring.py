from pathlib import Path
import numpy as np
import pytest

from systematic_trading.research import broadtrend as b
from systematic_trading.research.broadtrend_monitoring import current_allocation


def test_forward_policy_does_not_read_future_prices():
    root=Path(__file__).resolve().parents[1]
    with np.load(root/'var/research/range-breakout-20261018-v2/assets/GLD.npz') as z:data=dict(z)
    m=b.model_pack()['models']['GLD'];f,cl,full,start=b.shadow(data,m)
    n=int(np.searchsorted(f.days,np.datetime64('2025-03-03')))
    _,pc,part,_=b.shadow({k:v[:n] for k,v in data.items()},m)
    for key in ('desired','held','stop','nav'):
        assert np.allclose(full[key][:n],part[key],equal_nan=True)
    assert np.allclose(cl['fast_probability'][:n],pc['fast_probability'],equal_nan=True)


def test_current_monthend_target_uses_future_calendar_without_future_quotes():
    result=dict(days=['2024-01-31'],symbols=['A','B'],sleeves=np.array([[.7,.3]]),holdings=np.array([[.7,0]]),
        nav=np.array([1.]),cash=np.array([.3]),adoptions=[dict(date='2024-01-02',theoretical=[.7,0,.3])])
    arrays=dict(desired=np.array([[True,False]]),close=np.array([[1.,1.]]))
    current=current_allocation(result,arrays,{'A':{},'B':{}},100)
    assert current['target_session']=='2024-02-01'
    assert current['holdings'][0]['weight']==.7
    assert current['holdings'][0]['target_weight']==.5
    assert current['holdings'][-1]['target_weight']==.5
    assert current['next_action']=='monthly capital and daily signals'


def test_nonmonthend_target_preserves_sleeve_capital():
    result=dict(days=['2024-02-05'],symbols=['A','B'],sleeves=np.array([[.7,.3]]),holdings=np.array([[.7,0]]),
        nav=np.array([1.]),cash=np.array([.3]),adoptions=[dict(date='2024-02-01',theoretical=[.5,0,.5])])
    current=current_allocation(result,dict(desired=np.array([[False,True]]),close=np.ones((1,2))),{'A':{},'B':{}},100)
    assert [r['target_weight'] for r in current['holdings']]==pytest.approx([0,.3,.7])


def test_model_pack_is_part_of_calculation_revision():
    from systematic_trading.research.tracked_runtime import calculation_code_hashes
    hashes=calculation_code_hashes()
    assert hashes[str(Path('research/broadtrend_models_v1.json'))]==b.PACK_SHA256


def test_audited_file_with_wrong_symbol_is_rejected(monkeypatch):
    from systematic_trading.research import governed_inputs
    class Reader:
        def __init__(self,*args):pass
        def audit(self,symbol):return dict(symbol='WRONG',status='audited_with_limitations')
    class Analytics:
        def latest(self,source):return dict(version='test',provenance='{"root":"unused"}')
    monkeypatch.setattr(governed_inputs,'GovernedInputs',Reader)
    monkeypatch.setattr(b,'model_pack',lambda:dict(models={'GLD':dict(history_start='2004-11-18',isin=None)}))
    with pytest.raises(ValueError,match='unsupported audit: GLD'):b.load_inputs(None,Analytics())
