"""Idempotent, read-only-source migration and verified analytical publication."""
from pathlib import Path
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.research.analytics_service import AnalyticsService
from systematic_trading.storage.factory import create_trading_store


def main():
    settings = AppSettings()
    if settings.market_data_store_backend != "clickhouse":
        raise SystemExit("Analytical migration requires configured ClickHouse storage.")
    service = AnalyticsService(settings, create_trading_store(settings), AnalyticsStore.from_settings(settings))
    result = service.refresh()
    print(json.dumps(result, indent=2))
    return 2 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
