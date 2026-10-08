"""Run the application-owned research ETF recorder once; no research input bypass."""
import json

from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.recorders.research_etfs import refresh_research_etfs, recorder_status


if __name__ == "__main__":
    settings = AppSettings()
    try:
        refresh_research_etfs(settings, AnalyticsStore.from_settings(settings))
    finally:
        print(json.dumps(recorder_status(settings), indent=2))
