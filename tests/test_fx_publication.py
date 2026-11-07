import json
from types import SimpleNamespace

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.tracked_inputs import publish_observed_fx
from systematic_trading.research.usd_monitored import cnh_bridge
from test_analytics_projection import MemoryAnalytics


def evidence(settings, days):
    rows = [dict(trade_date=day, open='7', high='7', low='7', close='7', volume=0) for day in days]
    root = settings.data_dir / 'market_data/fx_observations'
    root.mkdir(parents=True, exist_ok=True)
    path = root / 'USD_CNH_test.json'
    path.write_text(json.dumps(dict(pair='USD/CNH', source='interactive-brokers', data_type='MIDPOINT',
        observed_at='2026-11-07T00:00:00+00:00', legs={'USD/CNH': rows}, rates=rows)))
    return path


def test_publication_and_bridge_advance_only_on_audited_exact_dates(tmp_path):
    settings = AppSettings(data_dir=tmp_path)
    analytics = MemoryAnalytics()
    analytics.observations = lambda source, **kwargs: analytics.rows[source]
    path = evidence(settings, ['2026-10-30'])
    publish_observed_fx(settings, analytics)
    old = analytics.latest('governance/fx-usd-cnh')['version']
    nav = [dict(trade_date=d, nav_cnh='100') for d in ['2026-10-30', '2026-11-02', '2026-11-03']]
    assert len(cnh_bridge(analytics, nav)[0]) == 1
    evidence(settings, ['2026-10-30', '2026-11-03'])
    publish_observed_fx(settings, analytics)
    rows, pin = cnh_bridge(analytics, nav)
    assert pin['version'] != old
    assert rows == [dict(trade_date=d, nav_cnh='700') for d in ['2026-10-30', '2026-11-03']]
    writes = analytics.writes
    publish_observed_fx(settings, analytics)
    assert analytics.writes == writes
    path.write_text(path.read_text() + ' ')
    with pytest.raises(ValueError, match='source file changed'):
        cnh_bridge(analytics, nav)


def test_invalid_raw_leg_never_replaces_complete_publication(tmp_path):
    settings = AppSettings(data_dir=tmp_path)
    analytics = MemoryAnalytics()
    path = evidence(settings, ['2026-10-30'])
    publish_observed_fx(settings, analytics)
    previous = analytics.latest('governance/fx-usd-cnh')
    invalid = json.loads(path.read_text())
    invalid['rates'][0]['close'] = '6.9'
    path.write_text(json.dumps(invalid))
    with pytest.raises(ValueError, match='differs'):
        publish_observed_fx(settings, analytics)
    assert analytics.latest('governance/fx-usd-cnh') == previous


def test_m1_only_monitoring_publishes_fx_and_invalidates_calculation_on_new_fx(tmp_path, monkeypatch):
    from systematic_trading.research import tracked_runtime as runtime, usd_monitored, m1_monitoring, strategy_lifecycle
    from systematic_trading.portfolio import strategy_allocation
    from systematic_trading.storage import artifact_budget
    from systematic_trading.research import strategy_assets

    settings = AppSettings(data_dir=tmp_path)
    analytics = MemoryAnalytics()
    definition = SimpleNamespace(key='research_m1_14_v1', universe_key='multi_asset_14',
        scheduler='static_monthly', overlays=[], to_dict=lambda: {'key': 'research_m1_14_v1'})
    monkeypatch.setattr(strategy_lifecycle, 'effective_config', lambda *args: dict(schema_version=2,
        monitored_strategy_ids=[definition.key], calculation={}))
    monkeypatch.setattr(runtime, 'registered_strategy_definition', lambda key: definition)
    monkeypatch.setattr(strategy_allocation, 'sota_definition', lambda store: definition)
    # Isolate the FX bridge; this synthetic definition deliberately has no model
    # overlays. Real M1 demand and automatic model signals have separate tests.
    monkeypatch.setattr(strategy_assets, 'live_plan', lambda *args: {'jobs':['fx-usdcnh-v1']})
    monkeypatch.setattr(runtime, 'load_tracked_inputs', lambda *args: pytest.fail('No legacy CNH strategy'))
    monkeypatch.setattr(usd_monitored, 'load_inputs', lambda *args: dict(provenance={'batch': 'audited'}))
    monkeypatch.setattr(m1_monitoring, 'load_inputs', lambda *args: dict(provenance={'batch': 'audited'}))
    monkeypatch.setattr(runtime, 'calculation_revision', lambda *args: 'recipe')
    evidence(settings, ['2026-10-30'])
    publish_observed_fx(settings, analytics)
    old = analytics.latest('governance/fx-usd-cnh')['version']
    version = digest(encode(['recipe', definition.to_dict(), old]))
    analytics.publish(runtime.SOURCE, version, [])
    assert not runtime._refresh_tracked_strategies(settings, None, analytics)

    class ReplayRequired(Exception):
        pass

    def admit(*args):
        raise ReplayRequired

    monkeypatch.setattr(artifact_budget, 'admit', admit)
    evidence(settings, ['2026-10-30', '2026-11-02'])
    with pytest.raises(ReplayRequired):
        runtime._refresh_tracked_strategies(settings, None, analytics)
    assert analytics.latest('governance/fx-usd-cnh')['version'] != old
    assert analytics.latest(runtime.SOURCE)['version'] == version
