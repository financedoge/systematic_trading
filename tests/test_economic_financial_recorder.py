from datetime import date
from copy import deepcopy

import pytest

from systematic_trading.recorders.economics import audit_csv, first_observation, next_observation, configuration
from systematic_trading.config import AppSettings


def registry():
    return {s['id']:s for s in configuration(AppSettings())['series']}


def fixture(spec, end='2016-01-01'):
    day = first_observation(date(2006,1,1),spec['frequency'])
    rows = [f'observation_date,{spec["id"]}_{end.replace("-","")}']
    while str(day) <= end:
        rows.append(f'{day},-0.5')
        day = next_observation(day,spec['frequency'])
    return rows


@pytest.mark.parametrize('symbol',['T10Y3M','T10Y2Y','NFCICREDIT','DRTSCILM','DRTSCIS'])
def test_frequency_contract_and_negative_values(symbol):
    spec=registry()[symbol];rows=fixture(spec)
    audit=audit_csv('\n'.join(rows).encode(),spec,'2016-01-01','2006-01-01')
    assert audit['usable'] and audit['observations'][-1]['value']=='-0.5'
    with pytest.raises(ValueError,match='calendar gap'):
        audit_csv('\n'.join(rows[:5]+rows[6:]).encode(),spec,'2016-01-01','2006-01-01')


def test_daily_holiday_null_is_preserved_and_weekend_not_inserted():
    spec=registry()['T10Y3M'];rows=fixture(spec)
    rows[1]='2006-01-02,.'
    result=audit_csv('\n'.join(rows).encode(),spec,'2016-01-01','2006-01-01')
    assert result['observations'][0]['value'] is None and result['missing']==1
    assert all(date.fromisoformat(r['date']).weekday()<5 for r in result['observations'])
    rows[4]=rows[4].replace('2006-01-05','2006-01-07')
    with pytest.raises(ValueError,match='frequency'):
        audit_csv('\n'.join(rows).encode(),spec,'2016-01-01','2006-01-01')


def test_quarter_date_is_not_release_date_and_stale_is_visible():
    spec=registry()['DRTSCILM'];rows=fixture(spec)
    result=audit_csv('\n'.join(rows).encode().replace(b'20160101',b'20161201'),spec,'2016-12-01','2006-01-01')
    assert not result['usable'] and result['last']=='2016-01-01'
    assert next_observation(date(2015,10,1),'quarterly')==date(2016,1,1)


def test_initial_closed_holiday_is_disclosed_but_missing_open_day_rejected():
    spec=registry()['T10Y2Y'];rows=fixture(spec)
    rows.pop(1)
    result=audit_csv('\n'.join(rows).encode(),spec,'2016-01-01','2006-01-01')
    assert result['first']=='2006-01-03' and result['unsupported_prefix_dates']==['2006-01-02']
    rows.pop(1)
    with pytest.raises(ValueError,match='starts late'):
        audit_csv('\n'.join(rows).encode(),spec,'2016-01-01','2006-01-01')


def test_additive_registry_preserves_original_eleven_contracts():
    current=configuration(AppSettings())
    old=deepcopy(current)
    old['series']=old['series'][:11]
    old['version']='us-leading-context-v2'
    from systematic_trading.recorders.economics import validate_registry_extension
    validate_registry_extension(current,old)
    assert len(current['series'])==16
    assert {s['id'] for s in current['series']}- {s['id'] for s in old['series']} == {'T10Y3M','T10Y2Y','NFCICREDIT','DRTSCILM','DRTSCIS'}
