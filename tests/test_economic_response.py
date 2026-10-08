from copy import deepcopy
from datetime import date, timedelta
from decimal import Decimal as D
import math

import pytest

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research.economic_response import GROUPS, fit_predict, ready, tilt, training_rows


def sample():
    states, opens = {}, {'A':{},'B':{}}
    price_a, price_b = 100.,100.
    for i in range(55):
        day = date(2016+i//12,i%12+1,4)
        known = day-timedelta(days=1)
        state = dict(known_at=str(known)+'T16:00:00-05:00',vintage=str(known-timedelta(days=1)),
            leading_ready=True,context_ready=True,
            features={f:str(math.sin(i/4+j)) for j,f in enumerate(GROUPS['combined'])})
        states[str(day)] = state
        opens['A'][str(day)] = str(price_a);opens['B'][str(day)] = str(price_b)
        shock = math.sin(i/4)
        price_a *= 1+.01+.02*shock;price_b *= 1+.01-.02*shock
    return states,opens


def test_completed_labels_and_future_poison_cannot_change_fit():
    states,opens = sample();day = sorted(states)[43];known = states[day]['known_at'][:10]
    result = fit_predict(day,known,states,opens,'leading')
    assert result['ready'] and result['last_label_end'] < day
    assert all(r['end'] <= known and r['vintage'] < r['start'] for r in result['training_labels'])
    poisoned = deepcopy(opens)
    for series in poisoned.values():
        for d in series:
            if d>=day:series[d] = 'NaN'
    future = deepcopy(states)
    for d in future:
        if d>day:future[d]['features'] = {'corrupted_future':'invalid'}
    assert fit_predict(day,known,future,poisoned,'leading') == result
    # Opposite synthetic asset responses are learned separately.
    models=result['models']
    assert models['A']['sensitivities']['ICSA']['linear']*models['B']['sensitivities']['ICSA']['linear'] < 0


def test_context_comparisons_match_rows_and_current_abstention():
    states,opens=sample();days=sorted(states);day=days[-1];known=states[day]['known_at'][:10]
    for d in days[5:10]:states[d]['context_ready']=False
    matched=fit_predict(day,known,states,opens,'matched');combined=fit_predict(day,known,states,opens,'combined')
    leading=fit_predict(day,known,states,opens,'leading')
    assert matched['sample_sha256']==combined['sample_sha256']
    assert matched['training_rows']==combined['training_rows']==leading['training_rows']-5
    assert len(matched['query'])==7 and len(combined['query'])==13
    states[day]['context_ready']=False
    assert ready(states[day],'leading') and not ready(states[day],'matched')
    assert not fit_predict(day,known,states,opens,'combined')['ready']


def test_insufficient_training_abstains_and_future_features_abort():
    states,opens=sample();day=sorted(states)[20];known=states[day]['known_at'][:10]
    assert not fit_predict(day,known,states,opens,'leading')['ready']
    states[day]['known_at']=day+'T16:00:00-04:00'
    with pytest.raises(ValueError,match='availability'):
        fit_predict(day,known,states,opens,'leading')


def targets(weights):
    return [AllocationTarget(symbol=s,sleeve='test',target_weight=D(w),rationale='parent') for s,w in weights.items()]


def fitted(increments, forecasts=None):
    return dict(group='leading',ready=True,models={s:dict(tree_increment=v,tree_forecast=(forecasts or {}).get(s,.03))
        for s,v in increments.items()})


@pytest.mark.parametrize('weights', [dict(A='.44',B='.30',C='.10',Z='0'),dict(A='.45',B='.45'),dict(A='.45',Z='0'),dict(A='0',B='0')])
def test_tilt_preserves_gross_membership_and_cap(weights):
    parent=targets(weights);model=fitted({s:.01 if s=='A' else -.01 for s in weights})
    result=tilt(parent,model,'tree')
    assert sum(t.target_weight for t in result)==sum(t.target_weight for t in parent)
    assert {t.symbol for t in result if t.target_weight}>={t.symbol for t in parent if t.target_weight}
    assert {t.symbol for t in result if t.target_weight}=={t.symbol for t in parent if t.target_weight}
    assert all(0<=t.target_weight<=D('.45') for t in result)
    if len(weights)>2 and weights['A']=='.44':
        assert result[0].target_weight > parent[0].target_weight
        assert result[1].target_weight < parent[1].target_weight


def test_abstention_keeps_parent_and_limits_are_fail_closed():
    parent=targets(dict(A='.40',B='.30'))
    assert tilt(parent,dict(ready=False),'tree') == parent
    with pytest.raises(ValueError,match='capped parent'):
        tilt(targets(dict(A='.60')),dict(ready=False),'tree')
    with pytest.raises(ValueError,match='Invalid economic forecast'):
        tilt(parent,fitted(dict(A=float('nan'),B=.01)),'tree')


def test_label_calendar_never_stretches_over_a_missing_economic_month():
    states,opens=sample();days=sorted(states)
    states[days[10]]['leading_ready']=False
    rows=training_rows(days[-1],states[days[-1]]['known_at'][:10],states,opens,'leading')
    assert next(r for r in rows if r['start']==days[9])['end']==days[10]
    assert days[10] not in {r['start'] for r in rows}


def test_long_decimal_targets_keep_the_exact_parent_budget_after_reweighting():
    parent=targets(dict(A='.1523456789012345678901234567',B='.2234567890123456789012345678',
        C='.2643863541898424854597478759',D='.1398111778965772677488940998',E='.2000000000000000000000000000'))
    result=tilt(parent,fitted(dict(A=.01,B=-.01,C=.02,D=-.02,E=0)),'tree')
    assert sum(t.target_weight for t in parent)==sum(t.target_weight for t in result)
