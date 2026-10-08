"""Drain a bounded number of app-owned acquisition cycles; no strategy execution."""
import argparse
import json
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.recorders.economics import load_catalog, refresh_economics, recorder_status


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=1)
    args = parser.parse_args()
    settings = AppSettings()
    analytics = AnalyticsStore.from_settings(settings)
    analytics.initialize()
    for i in range(args.cycles):
        try:
            changed = refresh_economics(settings, analytics)
        except (OSError, ValueError) as exc:
            print(json.dumps(dict(cycle=i + 1, error=str(exc))), flush=True)
            break
        catalog, pin = load_catalog(analytics)
        print(json.dumps(dict(cycle=i + 1, completed=catalog["completed"], expected=catalog["expected"], **pin)), flush=True)
        if not changed or catalog["completed"] == catalog["expected"]:
            break
    print(json.dumps(recorder_status(settings)), flush=True)
