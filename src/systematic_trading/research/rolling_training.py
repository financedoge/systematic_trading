"""Isolated application worker: causal fits only; no store or broker access."""
from concurrent.futures import ProcessPoolExecutor, as_completed
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.rolling_models import fit_record
from systematic_trading.research.rolling_models import training_rows
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.rolling_tracking import rolling_xgboost_spec, monthly_training_records, monthly_fit_dates
from systematic_trading.signals.library import signal_feature_ids


def initialize(records, cache, recipe_code, versions):
    global RECORDS, CACHE, RECIPE_CODE, VERSIONS
    RECORDS = json.loads(Path(records).read_text(encoding='utf8'))
    CACHE, RECIPE_CODE, VERSIONS = Path(cache), recipe_code, versions


def fit(cutoff):
    spec = rolling_xgboost_spec()
    rows = training_rows(RECORDS, cutoff, 1, signal_feature_ids())
    identity = digest(encode(dict(cutoff=cutoff, rows=rows, recipe=spec, code=RECIPE_CODE, versions=VERSIONS)))
    cached = CACHE/(identity+'.json')
    if cached.exists():
        item = json.loads(cached.read_text(encoding='utf8'))
        if item['identity'] != identity or item['model_sha256'] != digest(encode(item['model'])):
            raise ValueError('Changed cached rolling fit')
        return cutoff, item['model'], True
    result = fit_record(RECORDS, cutoff, spec['window_years'], signal_feature_ids(), spec['family'], seed=spec['seed'])
    if result['details']['settings'] != spec['parameters']:
        raise ValueError('Training implementation differs from the registered recipe')
    write_json(cached.with_suffix('.tmp'), dict(identity=identity, model=result, model_sha256=digest(encode(result))))
    cached.with_suffix('.tmp').replace(cached)
    return cutoff, result, False


def train(root, attempt):
    started = time.perf_counter()
    request = json.loads((root/'request.json').read_text(encoding='utf8'))
    if request['recipe'] != rolling_xgboost_spec():
        raise ValueError('Unsupported training recipe')
    versions = {n: importlib.metadata.version(n) for n in ('numpy', 'xgboost', 'scikit-learn')}
    if versions['xgboost'] != '3.2.0' or versions['scikit-learn'] != '1.8.0':
        raise ValueError('Install the pinned rolling-research dependency versions')
    records = monthly_training_records(request['bars'], request['symbols'])
    write_json(attempt/'training_records.json', records)
    dates = monthly_fit_dates(request['bars'], request['start'])
    schedule = {}
    cached_count = 0
    cache = root.parent/'fits'
    cache.mkdir(exist_ok=True)
    source = Path(__file__).resolve().parents[1]
    recipe_code = {str(p.relative_to(source)): sha256(p) for p in
        [source/'research'/n for n in ('rolling_models.py', 'rolling_training.py', 'rolling_tracking.py')]
        + list((source/'signals').glob('*.py'))}
    with ProcessPoolExecutor(max_workers=min(os.cpu_count() or 1, len(dates)), initializer=initialize,
                             initargs=(str(attempt/'training_records.json'), str(cache), recipe_code, versions)) as pool:
        jobs = [pool.submit(fit, cutoff) for cutoff in dates]
        for future in as_completed(jobs):
            cutoff, model, cached = future.result()
            schedule[cutoff] = model
            cached_count += cached
    write_json(attempt/'schedule.json', schedule)
    write_json(attempt/'receipt.json', dict(status='succeeded', request_sha256=sha256(root/'request.json'),
        recipe=request['recipe'], versions=versions, monthly_fits=len(schedule), reused_fits=cached_count,
        new_fits=len(schedule)-cached_count, cores=os.cpu_count(),
        elapsed_seconds=time.perf_counter()-started, promotion_eligible=False,
        files={n: sha256(attempt/n) for n in ('training_records.json', 'schedule.json')}))


if __name__ == '__main__':
    train(Path(sys.argv[1]), Path(sys.argv[2]))
