import runpy
import sys

import pytest


@pytest.mark.parametrize("script,flags", [
    ("backfill_yahoo_adjusted.py", []),
    ("backfill_tushare_us.py", []),
    ("run_stock_replacement_backtest.py", ["--output-dir"]),
])
def test_legacy_fx_fetchers_cannot_contaminate_server_store(script, flags, tmp_path, monkeypatch):
    import systematic_trading.storage as storage

    monkeypatch.setenv("ST_TRANSACTIONAL_STORE_BACKEND", "postgres")
    monkeypatch.setenv("ST_MARKET_DATA_STORE_BACKEND", "clickhouse")

    class NoWrites:
        def initialize(self):
            pytest.fail("Must reject proxy ingestion before initializing or writing to server stores")

    monkeypatch.setattr(storage, "create_trading_store", lambda *a, **k: NoWrites())
    arguments = [script, *flags, str(tmp_path / "output")] if flags else [script]
    monkeypatch.setattr(sys, "argv", arguments)
    module = runpy.run_path("scripts/" + script)
    with pytest.raises(ValueError, match="CNY"):
        module["main"]()
