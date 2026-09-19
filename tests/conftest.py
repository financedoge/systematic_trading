"""Keep tests independent of the operator's database and automation settings."""

import pytest


@pytest.fixture(autouse=True)
def isolated_application_defaults(tmp_path, monkeypatch):
    from systematic_trading.config import get_settings

    for key, value in {
        "ST_DATA_DIR": str(tmp_path),
        "ST_DATABASE_PATH": str(tmp_path / "default.db"),
        "ST_TRANSACTIONAL_STORE_BACKEND": "sqlite",
        "ST_MARKET_DATA_STORE_BACKEND": "sqlite",
        "ST_AUTOMATION_ENABLED": "false",
        "ST_AUTOMATION_ALERT_SMTP_HOST": "",
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
