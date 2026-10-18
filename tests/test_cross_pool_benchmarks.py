from dataclasses import replace
from types import SimpleNamespace

import pytest

from systematic_trading.lean.contracts import write_json
from systematic_trading.research import usd_monitored as usd
from systematic_trading.research.strategy_catalog import registered_strategy_definition, risk_parity_definition


def test_promoted_fourteen_asset_sota_stays_out_of_twelve_asset_worker():
    risk=replace(risk_parity_definition(),universe_key='multi_asset')
    fallback=registered_strategy_definition('research_fallback_f3_v1')
    sota=registered_strategy_definition('research_fr25_14_v1')
    family=usd.calculation_family(risk,[fallback],sota)
    assert set(family)=={risk.key,fallback.key}
    assert fallback.key in usd.calculation_family(risk,[fallback],fallback)
    with pytest.raises(ValueError,match='mixed strategy universes'):
        usd.calculation_family(risk,[fallback,sota],sota)


def test_benchmark_extra_assets_require_matching_prices_and_full_calendar():
    own={'SPY':{'2026-10-14':100.,'2026-10-15':101.}}
    rows={'SPY':[dict(trade_date=d,close=p) for d,p in own['SPY'].items()],
          'XLE':[dict(trade_date=d,close=p*2) for d,p in own['SPY'].items()]}
    assert usd.comparison_prices(own,rows)['XLE']['2026-10-15']==202.
    assert set(own)=={'SPY'}
    with pytest.raises(ValueError,match='calendar or basis'):
        usd.comparison_prices(own,{'XLE':rows['XLE'][:1]})
    with pytest.raises(ValueError,match='calendar or basis'):
        usd.comparison_prices(own,{'SPY':rows['XLE']})


def test_comparison_uses_frozen_quote_precision_and_raw_initial_anchor():
    own={'SPY':{'2015-12-31':169.123456,'2016-01-04':169.05}}
    bars={'SPY':[dict(trade_date='2015-12-31',close='169.123456'),
                 dict(trade_date='2016-01-04',close='169.0518035888672')],
          'XLE':[dict(trade_date='2015-12-31',close='52.123456'),
                 dict(trade_date='2016-01-04',close='51.0267')]}
    prices=usd.comparison_prices(own,bars,anchor='2015-12-31')
    assert prices['SPY']==own['SPY']
    assert prices['XLE']=={'2015-12-31':52.123456,'2016-01-04':51.03}
    bars['SPY'][1]['close']='169.0618035888672'
    with pytest.raises(ValueError,match='basis differs'):
        usd.comparison_prices(own,bars,anchor='2015-12-31')


@pytest.mark.parametrize('matching_batch',[True,False])
def test_cross_pool_reports_attach_completed_same_batch_benchmark(tmp_path,monkeypatch,matching_batch):
    from systematic_trading.research import momentum_replay
    sota=registered_strategy_definition('research_fr25_14_v1')
    bundle=tmp_path/'bundles'/sota.key;bundle.mkdir(parents=True)
    write_json(bundle/'manifest.json',{'frozen':'benchmark'})
    write_json(tmp_path/'python'/(sota.key+'.json'),{'nav':[{'date':'2026-10-15','nav':'101'}]})
    monkeypatch.setattr(momentum_replay,'verify_usd_bundle',lambda p:dict(spec=SimpleNamespace(start_date='2020-01-02',end_date='2026-10-15')))
    monkeypatch.setattr(usd,'build_reports',lambda **kwargs:kwargs)
    prepared=dict(sota=sota,config={'calculation':{'start':'2020-01-02','engine':'python'}},
        inputs={'provenance':{'batch':'batch-a','price_through':'2026-10-15'}},economics={},receipts={},comparisons={})
    source={'provenance':{'batch':'batch-a' if matching_batch else 'batch-b'},'bars':{'XLE':[]}}
    if not matching_batch:
        with pytest.raises(ValueError,match='matching audited batch'):
            usd.complete_cross_pool_reports(prepared,tmp_path,source)
        assert not prepared['economics']
    else:
        report=usd.complete_cross_pool_reports(prepared,tmp_path,source)
        assert report['external_bundles'][sota.key]==bundle
        assert report['economics'][sota.key]['nav'][0]['nav']=='101'
        assert report['comparison_bars'] is source['bars']
        assert report['inputs']['provenance']['sota_benchmark']['strategy']==sota.key
