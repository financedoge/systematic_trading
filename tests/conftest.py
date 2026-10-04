"""Keep tests independent of the operator's database and automation settings."""

import pytest


@pytest.fixture
def neutral_usd_publication(monkeypatch):
    """Synthetic neutral published models for existing order/approval unit fixtures.

    These tests exercise execution gates without external databases. Dedicated
    test_usd_promotion tests verify real inference, publication binding and failure.
    """
    from datetime import date, timedelta
    from systematic_trading.research import instruments_for_definition, current_sota_definition
    from systematic_trading.research import usd_tracking
    symbols = instruments_for_definition(current_sota_definition())
    model = dict(features=['S','L','vol63','USD21','USD63'], coefficients=[0]*5,
        means=[0]*5, scales=[1]*5, intercept=0, training_months=60, max_label_end='2010-01-01')
    dates = [str(date(2024,1,1)+timedelta(days=i)) for i in range(4*366)]
    schedule = dict(version=usd_tracking.VERSION,
        models={d:dict(models={s:model for s in symbols},fit_close=d) for d in dates},
        snapshots=[dict(known_through=d,vintage_date=str(date.fromisoformat(d)-timedelta(days=1)),
            observation_date=str(date.fromisoformat(d)-timedelta(days=2)),features=dict(USD21=0,USD63=0)) for d in dates])
    monkeypatch.setattr(usd_tracking, 'published_live_schedule', lambda *args: (schedule, {'synthetic_test_publication': True}))


@pytest.fixture(autouse=True)
def isolated_application_defaults(tmp_path, monkeypatch):
    from systematic_trading.config import get_settings

    for key, value in {
        "ST_DATA_DIR": str(tmp_path),
        "ST_DATABASE_PATH": str(tmp_path / "default.db"),
        "ST_TRANSACTIONAL_STORE_BACKEND": "sqlite",
        "ST_MARKET_DATA_STORE_BACKEND": "sqlite",
        "ST_AUTOMATION_ENABLED": "false",
        "ST_IB_PNL_ENABLED": "false",
        "ST_HEALTH_MONITOR_ENABLED": "false",
        # Legacy unit fixtures contain synthetic transactional bars. Dedicated
        # governed-input tests enable the production default explicitly.
        "ST_REQUIRE_GOVERNED_DECISION_INPUTS": "false",
        "ST_GOVERNED_REFRESH_ENABLED": "false",
        "ST_AUTOMATION_ALERT_SMTP_HOST": "",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
