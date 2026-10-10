from dataclasses import replace
from datetime import date
from decimal import Decimal
import pytest

from systematic_trading.research import instruments_for_definition,instantiate_overlays
from systematic_trading.research.strategy_catalog import m1_14_definition,defensive_cash_definition,registered_strategy_definition
from systematic_trading.research.strategy_lifecycle import replay_supported
from systematic_trading.research.strategy_diagram import decision_diagrams
from systematic_trading.research.candidate_pool import CandidatePool,AuditedActivity
from systematic_trading.lean.strategy import targets_for_day
from test_candidate_pool import fixture


def test_m1_registration_preserves_exact_selector_and_separate_universe():
    d=m1_14_definition();base=defensive_cash_definition()
    assert registered_strategy_definition(d.key)==d and replay_supported(d.key)
    assert d.promoted_on is None and d.state=='tracked'
    assert len(instruments_for_definition(d))==14 and len(instruments_for_definition(base))==12
    assert set(instruments_for_definition(d))-set(instruments_for_definition(base))=={'XLE','XLB'}
    assert 'XOP' not in instruments_for_definition(d)
    assert list(instruments_for_definition(d))==sorted(instruments_for_definition(d))
    targets,context=fixture()
    expected=CandidatePool(instantiate_overlays(base)[0],'M1').apply(targets,context)
    actual=instantiate_overlays(d)[0].apply(targets,context)
    assert [t.target_weight for t in actual]==[t.target_weight for t in expected]
    assert not any(o.kind=='final_weight_cap' for o in d.overlays)


def test_m1_activity_requires_raw_binding_and_does_not_substitute():
    targets,context=fixture();activity=next(o for o in instantiate_overlays(m1_14_definition()) if isinstance(o,AuditedActivity))
    with pytest.raises(ValueError,match='explicitly bound'):activity.apply(targets,context)
    d=m1_14_definition();prefix=replace(d,overlays=(d.overlays[0],d.overlays[4]))
    rows={s:[r.model_dump(mode='json') for r in v] for s,v in context.bars_by_symbol.items()}
    with pytest.raises(ValueError,match='raw activity input'):targets_for_day(rows,context.as_of,definition=prefix)
    raw={s:[dict(r) for r in v] for s,v in rows.items()}
    before=targets_for_day(rows,context.as_of,definition=prefix,raw_rows=raw)
    assert len([t for t in before if t.target_weight>0])<=6
    for s in raw:raw[s].append(dict(raw[s][-1],trade_date=str(context.as_of),close='1',volume=999999))
    assert targets_for_day(rows,context.as_of,definition=prefix,raw_rows=raw)==before


def test_m1_diagram_reports_actual_horizons_basis_and_gate():
    text=decision_diagrams(m1_14_definition(),accounting_currency='USD')[0]['svg']
    assert '21/63/126d trend' in text and 'positive 126d momentum' in text
    assert 'Audited raw close × raw volume' in text
    assert 'Adjusted-price direction' in text
    assert 'positive 252d momentum' not in text


def test_missing_14th_asset_prevents_target_calculation():
    targets,context=fixture();d=replace(m1_14_definition(),overlays=(m1_14_definition().overlays[0],))
    rows={s:[r.model_dump(mode='json') for r in v] for s,v in context.bars_by_symbol.items() if s!='XLE'}
    with pytest.raises((KeyError,ValueError)):targets_for_day(rows,context.as_of,definition=d)


def test_benchmark_inception_prefix_is_not_strategy_warmup_or_a_filled_gap():
    from systematic_trading.research.m1_monitoring import validate_calendars
    calendar=['2012-01-05','2012-01-06','2015-12-31','2016-01-04','2016-01-05']
    records={'SPY':[dict(trade_date=d) for d in calendar], 'URTH':[dict(trade_date=d) for d in calendar[2:]]}
    validate_calendars(records,calendar,'2016-01-04',['SPY'])
    with pytest.raises(ValueError,match='benchmark'):validate_calendars(dict(records,URTH=records['URTH'][1:]),calendar,'2016-01-04',['SPY'])
    with pytest.raises(ValueError,match='M1/14 missing'):validate_calendars(dict(records,SPY=records['SPY'][1:]),calendar,'2016-01-04',['SPY'])
