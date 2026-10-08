"""Run the application-owned CFTC positioning recorder once."""
import json

from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.recorders.positioning import catalog, refresh_positioning


if __name__ == "__main__":
    settings = AppSettings()
    analytics = AnalyticsStore.from_settings(settings)
    analytics.initialize()
    try:
        changed = refresh_positioning(settings, analytics)
        print(json.dumps({"published": changed, **catalog(analytics, settings)}, indent=2))
    except Exception as exc:
        print(json.dumps({"published": False, "error": str(exc)}, indent=2))
        raise
