from copy import deepcopy
from datetime import date,timedelta
from decimal import Decimal as D
import math

import pytest

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research.expanded_economics import cap_row,overlay_row


def parent(weights):
    return dict(signal_session='2026-10-01',known_through='2026-09-30',targets=[
        AllocationTarget(symbol=s,sleeve='test',target_weight=D(w),rationale='M1 selection').model_dump(mode='json') for s,w in weights.items()])


def model(ready=True):
    return dict(group='financial',ready=ready,reason='test',training_rows=40,training_sha256='test',last_label_end='2026-09-01',
        models={s:dict(linear_increment=v,linear_forecast=.04) for s,v in [('SPY',.01),('XLE',-.01),('XLB',99)]})


def test_cap_bridge_is_explicit_and_never_allocates_a_new_candidate():
    original=parent(dict(SPY='.60',XLE='.38',XLB='0'));frozen=deepcopy(original);capped=cap_row(original)
    assert original==frozen
    assert [D(t['target_weight']) for t in capped['targets']]==[D('.45'),D('.38'),D(0)]


def test_information_overlay_preserves_cash_and_rejected_sector_stays_zero():
    base=parent(dict(SPY='.40',XLE='.38',XLB='0'));out=overlay_row(base,model(),'linear')
    weights={t['symbol']:D(t['target_weight']) for t in out['targets']}
    assert sum(weights.values())==D('.78') and weights['XLB']==0
    assert weights['SPY']>D('.40') and weights['XLE']<D('.38')


def test_unavailable_model_abstains_and_uncapped_parent_fails_closed():
    base=parent(dict(SPY='.40',XLE='.38',XLB='0'));out=overlay_row(base,model(False),'linear')
    assert out['targets']==base['targets']
    with pytest.raises(ValueError,match='capped parent'):overlay_row(parent(dict(SPY='.60')),model(False),'linear')


def test_fourteen_models_ignore_future_prices_and_match_augmented_samples():
    from systematic_trading.research.economic_financial import GROUPS,fit_predict
    symbols=['SPY','VGK','EWJ','EWH','EWY','MCHI','GLD','TLT','IEF','LQD','HYG','DBC','XLE','XLB']
    states={};opens={s:{} for s in symbols}
    for i in range(50):
        day=date(2016+i//12,i%12+1,4);known=day-timedelta(days=1)
        states[str(day)]=dict(known_at=str(known)+'T16:00:00-05:00',vintage=str(known-timedelta(days=1)),
            leading_ready=True,context_ready=True,financial_ready=i!=10,features={k:str(math.sin(i/5+j)) for j,k in enumerate(GROUPS['augmented'])})
        for j,s in enumerate(symbols):opens[s][str(day)]=str(100*math.exp(.003*i+.02*math.sin(i/5+j)))
    day=sorted(states)[45];known=states[day]['known_at'][:10]
    matched=fit_predict(day,known,states,opens,'matched');combined=fit_predict(day,known,states,opens,'augmented')
    assert matched['ready'] and len(matched['models'])==14
    assert matched['sample_sha256']==combined['sample_sha256'] and matched['last_label_end']<day
    for values in opens.values():
        for d in values:
            if d>=day:values[d]='NaN'
    for d in states:
        if d>day:states[d]['features']={}
    assert fit_predict(day,known,states,opens,'augmented')==combined
