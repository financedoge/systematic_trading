from dataclasses import replace
from datetime import date,timedelta

import pytest

from systematic_trading.research.price_governance import (
    PriceSource, audit_overlap, consolidate, factor_audit, split_multiplier, yahoo_source, governed_sessions,
)


def source(key='new',scale=1,start=0,end=100):
    days=[(date(2020,1,1)+timedelta(days=i)).isoformat() for i in range(start,end)]
    rows={d:dict(open=(100+i)*scale,high=(101+i)*scale,low=(99+i)*scale,close=(100+i)*scale,
        adjusted_close=(100+i)*scale,volume=1000) for i,d in enumerate(days,start)}
    return PriceSource(key,'TEST','Example Technology Inc','yahoo','hash','2020-04-10',rows,
        action_start='1950-01-01',action_end='2020-04-10',priority=100 if key=='new' else 50,
        metadata={'listing_boundary_date':'2020-01-01'})


def test_split_reversal_uses_strictly_subsequent_events_and_source_vintage():
    actions=[dict(kind='splits',date='2020-02-01',ratio=2),dict(kind='splits',date='2021-01-01',ratio=4)]
    assert split_multiplier(actions,'2020-01-31','2020-04-10')==2
    assert split_multiplier(actions,'2020-02-01','2020-04-10')==1
    s=source()
    s.actions=actions
    # Price is already split-adjusted. Reconstruct old tape price, divide old
    # adjusted share volume, and leave the split day itself unchanged.
    bars,_,_=consolidate('TEST',[s],set(s.rows),'2020-04-09')
    row=next(r for r in bars if r['trade_date']=='2020-01-31')
    assert row['raw_close']==260 and row['raw_volume']==500
    assert next(r for r in bars if r['trade_date']=='2020-02-01')['split_multiplier']==1


def test_dividend_adjustment_audit_and_ohlc_basis_are_distinct():
    s=source(end=3)
    s.actions=[dict(kind='dividends',date='2020-01-02',amount=1)]
    s.rows['2020-01-01']['adjusted_close']=99
    assert factor_audit(s)==[]
    bars,_,_=consolidate('TEST',[s],set(s.rows),'2020-01-03')
    assert bars[0]['raw_close']==100 and bars[0]['adjusted_close']==99
    assert bars[0]['adjusted_high']==pytest.approx(99.99)
    s.actions=[]
    assert factor_audit(s)[0]['issue']=='unexplained_adjustment_factor'
    bars,_,_=consolidate('TEST',[s],set(s.rows),'2020-01-03')
    assert bars[0]['raw_close'] is None


def test_rebased_overlap_extends_history_without_scale_jump():
    old=source('old',scale=4)
    new=source(start=20)
    r=audit_overlap(new,old)
    assert r['accepted'] and r['scale']==.25
    bars,audit,_=consolidate('TEST',[new,old],set(old.rows),'2020-04-09')
    assert len(bars)==100 and audit['joined_rows']==20
    assert bars[19]['adjusted_close']==119 and bars[20]['adjusted_close']==120
    assert len(audit['seams'])==1


def test_no_overlap_name_mismatch_and_price_conflict_never_authorize_join():
    a=source()
    assert not audit_overlap(a,replace(source('old'),name='Unrelated Biotech'))['accepted']
    assert not audit_overlap(a,source('old',start=150,end=250))['accepted']
    b=source('old')
    for r in b.rows.values():
        r['adjusted_close']=r['close']**1.2
    assert not audit_overlap(a,b)['accepted']
    _,report,_=consolidate('TEST',[a,b],set(a.rows),'2020-04-09')
    assert report['conflict_dates']>0


def test_gaps_stooq_raw_and_insufficient_action_coverage_remain_explicit():
    s=source(end=10)
    sessions=set(s.rows)
    del s.rows['2020-01-05']
    bars,audit,_=consolidate('TEST',[s],sessions,'2020-01-10')
    assert len(bars)==9 and audit['gaps']==['2020-01-05']
    s.basis='dividend_adjusted'
    assert all(r['raw_close'] is None for r in consolidate('TEST',[s],sessions,'2020-01-10')[0])
    s.basis='split_adjusted'
    s.action_end='2020-04-01'
    assert all(r['raw_close'] is None for r in consolidate('TEST',[s],sessions,'2020-01-10')[0])


def test_bad_ohlc_and_identity_rejected_sources_cannot_fill_gaps():
    s=source(end=10)
    s.rows['2020-01-02']['high']=1
    other=source('other',end=10)
    other.metadata['identity_eligible']=False
    bars,audit,_=consolidate('TEST',[s,other],set(s.rows),'2020-01-10')
    assert len(bars)==9 and audit['gaps']==['2020-01-02']
    assert '2020-01-02' in audit['sources'][0]['invalid_dates']


def test_yahoo_dates_use_exchange_timezone_and_duplicates_are_quarantined():
    # 00:00 UTC is still the previous New York session date.
    raw={'chart':{'result':[{'meta':{'exchangeTimezoneName':'America/New_York','longName':'Test'},
        'timestamp':[1577923200,1577923201], 'indicators':{'quote':[{'open':[1,1],'high':[1,1],'low':[1,1],
        'close':[1,1],'volume':[10,10]}],'adjclose':[{'adjclose':[1,1]}]}}]}}
    s=yahoo_source(raw,key='x',symbol='X',raw_hash='hash',vintage='2020-04-10',priority=1,action_start='1950-01-01')
    assert s.rows=={} and s.issues[0]['date']=='2020-01-01'
    raw['chart']['result'][0]['timestamp']=[-252322200]
    s=yahoo_source(raw,key='x',symbol='X',raw_hash='hash',vintage='2020-04-10',priority=1,action_start='1950-01-01')
    assert list(s.rows)==['1962-01-02']


def test_known_complex_corporate_identity_never_claims_raw_certification():
    s=source(end=10)
    bars,audit,_=consolidate('GE',[s],set(s.rows),'2020-01-10')
    assert audit['status']=='review' and not audit['raw_tape_certified']
    assert all(r['raw_close'] is None for r in bars)


def test_unexplained_cross_vintage_price_rewrite_withholds_raw():
    old=source('old')
    old.vintage='2020-04-09'
    new=source(scale=.8)
    report=audit_overlap(new,old)
    assert report['accepted']  # Adjusted prices differ only by a constant.
    assert report['raw_basis_agreement'] is False  # No split explains Close.
    bars,audit,_=consolidate('TEST',[new,old],set(new.rows),'2020-04-09')
    assert all(r['raw_close'] is None for r in bars)
    assert audit['sources'][0]['raw_basis_blocked']


def test_historical_holidays_do_not_create_false_gaps():
    days,meta=governed_sessions('1962-01-01','2026-09-25')
    assert '1962-07-03' in days
    for d in ('1962-07-04','1962-12-25','1968-06-12','2001-09-11','2012-10-29','2025-01-09'):
        assert d not in days
    assert '1962-07-04' in meta['removed_default_range_artifacts']


def test_matching_recent_overlap_cannot_join_a_previous_ticker_era():
    # Same contemporary name and exact modern returns can still hide a
    # different issuer in the beginning of a historical CSV.
    old=source('old')
    new=source(start=20)
    new.metadata['listing_boundary_date']='2020-01-21'
    assert audit_overlap(new,old)['accepted']
    bars,audit,_=consolidate('TEST',[new,old],set(old.rows),'2020-04-09')
    assert len(bars)==80 and bars[0]['trade_date']=='2020-01-21'
    assert audit['joined_rows']==0 and audit['pre_listing_source_observations']==20
    assert audit['sources'][1]['eligible_from']=='2020-01-21'
    assert audit['status']=='review'
    assert not audit['listing_boundary']['certified']


def test_listing_boundary_still_allows_valid_post_listing_gap_fill():
    old=source('old')
    new=source(start=20)
    new.metadata['listing_boundary_date']='2020-01-21'
    del new.rows['2020-02-20']
    bars,audit,_=consolidate('TEST',[new,old],set(old.rows),'2020-04-09')
    assert len(bars)==80 and audit['joined_rows']==1 and not audit['gaps']
    assert next(r for r in bars if r['trade_date']=='2020-02-20')['source_id']=='old'


def test_recycled_metadata_with_no_current_era_prices_stays_unavailable():
    current=source()
    current.metadata['listing_boundary_date']='2021-01-01'
    bars,audit,_=consolidate('TEST',[current,source('old')],set(current.rows),'2020-04-09')
    assert bars==[] and audit['status']=='unavailable'
    assert audit['reason']=='all_observations_precede_provider_listing_boundary'
    assert all(not s['accepted'] for s in audit['sources'])


def test_archive_without_listing_metadata_cannot_extend_into_unknown_issuer_era():
    old,new=source('old'),source(start=20)
    new.metadata={}
    bars,audit,_=consolidate('TEST',[new,old],set(old.rows),'2020-04-09')
    assert bars[0]['trade_date']=='2020-01-21' and audit['joined_rows']==0
    assert audit['listing_boundary']['basis']=='preferred_source_first_observation_identity_floor'


def test_borrowed_action_ledger_does_not_certify_period_before_its_price_coverage():
    old,new=source('old'),source(start=20)
    old.action_start=old.action_end=None
    bars,audit,_=consolidate('TEST',[new,old],set(old.rows),'2020-04-09')
    assert len(bars)==100 and audit['joined_rows']==20
    assert all(r['raw_close'] is None for r in bars[:20])
    assert all(r['raw_close'] is not None for r in bars[20:])
