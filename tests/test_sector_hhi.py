import pytest

np=pytest.importorskip('numpy',reason='Optional research dependency')
from systematic_trading.research.sector_hhi import (
    volume_hhi,causal_ema,lagged_derivatives,forward_returns,average_ranks,correlations,
    correlation_block_interval,
)


def test_hhi_bounds_and_common_scaling():
    assert volume_hhi(np.ones((3,11))) == pytest.approx([1/11]*3)
    activity=np.array([[100,1,1],[3,4,5]],dtype=float)
    assert np.all(volume_hhi(activity)>=1/3)
    assert np.all(volume_hhi(activity)<=1)
    assert volume_hhi(activity)==pytest.approx(volume_hhi(activity*12))


@pytest.mark.parametrize('values', [[[1,0]],[[1,np.nan]],[[1,-1]]])
def test_missing_sector_is_rejected_not_renormalized(values):
    with pytest.raises(ValueError,match='positive'):
        volume_hhi(np.array(values))


def test_forward_returns_have_exact_horizon_and_no_tail_filling():
    prices=np.array([100.,110.,121.,133.1,146.41])
    result=forward_returns(prices,2)
    assert result[:3]==pytest.approx([.21,.21,.21])
    assert np.isnan(result[-2:]).all()


def test_backward_derivatives_recover_curvature_and_are_causal():
    x=np.arange(100,dtype=float)**2
    first,second=lagged_derivatives(x,5)
    assert second[10:]==pytest.approx(np.repeat(2.,90))
    assert np.isnan(first[:5]).all() and np.isnan(second[:10]).all()
    changed=x.copy();changed[70:]=9999
    before=lagged_derivatives(causal_ema(x,10),10)
    after=lagged_derivatives(causal_ema(changed,10),10)
    for a,b in zip(before,after): np.testing.assert_allclose(a[:70],b[:70],equal_nan=True)


def test_rank_correlation_handles_ties():
    x=np.array([2,2,1,4],dtype=float)
    assert average_ranks(x)==pytest.approx([2.5,2.5,1,4])
    result=correlations(x,-x)
    assert result['pearson']==pytest.approx(-1)
    assert result['spearman']==pytest.approx(-1)


def test_block_interval_reproducible_and_degenerate_samples_declined():
    x=np.arange(100,dtype=float)
    y=np.sin(x)+x/20
    assert correlation_block_interval(x,y,block=20,replicates=100)==correlation_block_interval(x,y,block=20,replicates=100)
    assert correlation_block_interval(x,y,block=60,replicates=100) is None
