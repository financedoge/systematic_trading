"""Capture official EIA releases with the same publisher used by the app."""
import json

from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.recorders.energy import catalog, refresh_energy


if __name__ == "__main__":
    settings = AppSettings()
    analytics = AnalyticsStore.from_settings(settings)
    analytics.initialize()
    changed = refresh_energy(settings, analytics)
    result = catalog(analytics, settings)
    print(json.dumps(dict(changed=changed, products=[dict(id=p["id"], pin=p["pin"],
        captures=len(p["captures"]), metrics=len(p["latest"]["metrics"]) if p["latest"] else 0,
        report_date=p["latest"]["report_date"] if p["latest"] else None) for p in result["products"]]), indent=2))
