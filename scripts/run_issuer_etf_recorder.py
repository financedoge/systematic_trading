"""Capture issuer snapshots through the application's governed publisher."""
import json

from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.recorders.issuer_etfs import catalog, refresh_issuer_etfs


if __name__ == "__main__":
    settings = AppSettings()
    analytics = AnalyticsStore.from_settings(settings)
    analytics.initialize()
    changed = refresh_issuer_etfs(settings, analytics)
    result = catalog(analytics, settings)
    print(json.dumps(dict(changed=changed, funds=[dict(symbol=f["symbol"], pin=f["pin"],
        captures=len(f["captures"]), dates=f["latest"]["dates"] if f["latest"] else None,
        warnings=f["latest"]["warnings"] if f["latest"] else [], error=f["verification_error"])
        for f in result["funds"]]), indent=2))
