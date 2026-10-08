from copy import deepcopy
from datetime import date, datetime, timedelta, UTC
import math

import pytest

from systematic_trading.research import economic_financial as f
from systematic_trading.research.economic_response import fit_predict as original_fit


def sample():
    states,opens={},dict(A={},B={});a,b=100.,100.
    for i in range(55):
        day=date(2016+i//12,i%12+1,4);known=day-timedelta(days=1)
        states[str(day)]=dict(known_at=str(known)+'T16:00:00-05:00',vintage=str(known-timedelta(days=1)),
            leading_ready=True,context_ready=True,financial_ready=True,
            features={key:str(math.sin(i/4+j)) for j,key in enumerate(f.GROUPS['augmented'])})
        opens['A'][str(day)]=str(a);opens['B'][str(day)]=str(b)
        shock=math.sin(i/4);a*=1+.01+.02*shock;b*=1+.01-.02*shock
    return states,opens


def test_cutoffs_future_poison_and_opposite_asset_effects():
    states,opens=sample();day=sorted(states)[45];known=states[day]['known_at'][:10]
    result=f.fit_predict(day,known,states,opens,'financial')
    assert result['ready'] and result['last_label_end']<=known
    for values in opens.values():
        for d in values:
            if d>=day:values[d]='NaN'
    for d in states:
        if d>day:states[d]['features']={}
    assert f.fit_predict(day,known,states,opens,'financial')==result
    models=result['models']
    assert models['A']['sensitivities']['T10Y3M']['linear']*models['B']['sensitivities']['T10Y3M']['linear']<0


def test_matched_context_retains_original_fitting_math():
    states,opens=sample();day=max(states);known=states[day]['known_at'][:10]
    old=original_fit(day,known,states,opens,'combined')
    new=f.fit_predict(day,known,states,opens,'matched')
    assert old['models']==new['models'] and old['training_sha256']==new['training_sha256']
    for d in sorted(states)[5:9]:states[d]['financial_ready']=False
    matched=f.fit_predict(day,known,states,opens,'matched');augmented=f.fit_predict(day,known,states,opens,'augmented')
    assert matched['sample_sha256']==augmented['sample_sha256']
    assert len(matched['query'])==13 and len(augmented['query'])==21
    states[day]['financial_ready']=False
    assert not f.fit_predict(day,known,states,opens,'matched')['ready']
    assert not f.fit_predict(day,known,states,opens,'augmented')['ready']


def test_minimum_labels_and_missing_month_do_not_stretch_labels():
    states,opens=sample();days=sorted(states);states[days[10]]['financial_ready']=False
    rows=f.training_rows(days[-1],states[days[-1]]['known_at'][:10],states,opens,'financial')
    assert next(r for r in rows if r['start']==days[9])['end']==days[10]
    assert days[10] not in {r['start'] for r in rows}
    day=days[20]
    assert not f.fit_predict(day,states[day]['known_at'][:10],states,opens,'financial')['ready']


def panel_fixture(monkeypatch):
    monkeypatch.setattr(f,'original_panel',lambda *a:dict(leading_ready=True,context_ready=True,features={},sources={},unavailable=[]))
    data={}
    for s in f.SERIES:
        values=['-2','-1','0','1','2'] if s=='NFCICREDIT' else ['-3','-1'] if s.startswith('DR') else ['-.5']
        data[s]=dict(series=dict(min=-100,max=100,max_age_days=160),usable=True,last='2026-09-25',
            archive_available_at='2026-09-30T03:59:59+00:00',observations=[dict(date='2026-09-25',value=v) for v in values])
    class Reader:
        def snapshot(self,s,v):
            assert v=='2026-09-29'
            return deepcopy(data[s])
    return data,Reader()


def test_financial_signed_levels_differences_and_exact_vintage(monkeypatch):
    _,reader=panel_fixture(monkeypatch)
    result=f.panel(reader,'2026-09-29',datetime(2026,9,30,20,tzinfo=UTC))
    assert result['financial_ready'] and len(result['features'])==8
    assert result['features']['T10Y3M']=='-0.5'
    assert result['features']['NFCICREDIT_change']=='4'
    assert result['features']['DRTSCIS_change']=='2'


@pytest.mark.parametrize('s',['T10Y2Y','NFCICREDIT','DRTSCILM'])
def test_missing_financial_window_abstains_instead_of_filling(monkeypatch,s):
    data,reader=panel_fixture(monkeypatch);data[s]['observations'][0]['value']=None
    result=f.panel(reader,'2026-09-29',datetime(2026,9,30,20,tzinfo=UTC))
    assert not result['financial_ready'] and s not in result['features']


def test_financial_future_vintage_and_stale_endpoint(monkeypatch):
    data,reader=panel_fixture(monkeypatch)
    with pytest.raises(ValueError,match='unavailable'):
        f.panel(reader,'2026-09-29',datetime(2026,9,29,20,tzinfo=UTC))
    data['DRTSCIS']['last']='2025-01-01'
    assert not f.panel(reader,'2026-09-29',datetime(2026,9,30,20,tzinfo=UTC))['financial_ready']
