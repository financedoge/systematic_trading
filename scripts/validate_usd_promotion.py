"""Reproduce the selected model before requesting complete application calculations."""
import argparse
from datetime import date
import json
from pathlib import Path

from systematic_trading.config import AppSettings
from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.contracts import write_json, sha256
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.research.tracked_inputs import load_tracked_inputs
from systematic_trading.research.usd_data import load_usd, refresh_usd
from systematic_trading.research.usd_tracking import prepare_usd_schedule, usd_prediction


def run(calculate=False):
    settings = AppSettings()
    analytics = AnalyticsStore.from_settings(settings)
    config = json.loads(settings.strategy_monitoring_config_path.read_text(encoding='utf8'))
    inputs = load_tracked_inputs(settings, analytics, config)
    refresh_usd(settings, analytics, inputs['provenance']['price_through'])
    snapshots, receipt = load_usd(analytics)
    schedule = prepare_usd_schedule(inputs['latest_bars'], snapshots)
    old = json.loads(Path('var/research/momentum-20261001-v1b/U1-M-models.json').read_text(encoding='utf8'))
    frozen_root = Path('var/research/momentum-20261001-v1b')
    manifest = json.loads((frozen_root/'input_manifest.json').read_text(encoding='utf8'))
    if sha256(frozen_root/'bars.json') != manifest['bars.json']:
        raise ValueError('Frozen study price inputs changed')
    reproduction = prepare_usd_schedule(json.loads((frozen_root/'bars.json').read_text(encoding='utf8')), snapshots)
    differences = []
    for day, model in old.items():
        current = reproduction['models'][model['fit_close']]
        differences.extend(abs(current['predictions'][s]-value) for s, value in model['predictions'].items())
    if max(differences) > 1e-12:
        raise ValueError('Application USD model differs from registered U1 study')
    known = inputs['provenance']['price_through']
    from systematic_trading.live.trading_calendar import next_us_trading_day
    latest = usd_prediction(schedule, {s:[PriceBar.model_validate(r) for r in rows] for s, rows in inputs['latest_bars'].items()},
        next_us_trading_day(date.fromisoformat(known)))
    result = dict(usd_batch=receipt['batch'], price_batch=inputs['provenance']['batch'],
        matched_models=len(old), max_prediction_difference=max(differences), latest_fit=latest['fit_close'],
        current_batch_max_prediction_change=max(abs(schedule['models'][m['fit_close']]['predictions'][s]-v)
            for m in old.values() for s,v in m['predictions'].items()),
        latest_price=known, latest_usd_observation=latest['snapshot']['observation_date'])
    write_json(settings.data_dir/'research/usd-promotion-model-parity.json', result)
    print(json.dumps(result), flush=True)
    if calculate:
        from systematic_trading.research.tracked_runtime import refresh_tracked_strategies
        from systematic_trading.storage.factory import create_trading_store
        refresh_tracked_strategies(settings, create_trading_store(settings), analytics)
        print('Application strategy publication completed', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--calculate', action='store_true')
    run(parser.parse_args().calculate)
