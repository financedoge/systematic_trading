"""Verify parent inputs and publish missing daily macro vintages in study namespace.

No price downloads, live catalog replacement, strategy changes, or broker access.
Every capture is audited before publication. A failed capture remains quarantined.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, timedelta
import argparse
import importlib.metadata
from pathlib import Path
import shutil
import sys
from urllib.parse import urlencode

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.recorders.economics import (
    capture, configuration, EconomicInputs, fetch_csv, publish_files,
)
from systematic_trading.research.candidate_pool import audited_bar
from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
from systematic_trading.research.momentum_replay import checked_files, read_json, verify_usd_bundle
from systematic_trading.research.usd_index_governance import audit_snapshot

ROOT = Path('var/research/target-change-rebalance-20261015-v1')
PUBLISHED = Path('var/tracked_strategies/354bcca802d6b71bedeebfa26d0873e0f4adf9a5552914ee349a426906601597')
PARENTS = {'FR25': ('m1_14', 'research_fr25_14_v1'), 'F3': ('usd', 'research_fallback_f3_v1')}


class StudyPublications:
    """Use the normal verified store but never replace the app's input pointers."""
    def __init__(self, store):
        self.store = store

    def publish(self, source, *args, **kwargs):
        return self.store.publish('research-inputs/target-change-20261015/' + source, *args, **kwargs)


def prepare(root):
    if (root/'preflight_manifest.json').exists():
        checked_files(root, 'preflight_manifest.json')
        return
    root.mkdir(parents=True, exist_ok=True)
    protocol = read_json(Path('research/target-change-rebalance-20261015-v1/protocol.json'))
    source = GovernedInputs(Path('var/governance/research-2026-10-14-ea07a1df6659'),
        protocol['inputs']['published_price_batch_reference'])
    receipts = {}
    for arm, (folder, key) in PARENTS.items():
        parent = PUBLISHED/folder
        checked_files(parent, 'input_manifest.json')
        verify_usd_bundle(parent/'bundles'/key)
        publication = read_json(Path('var/tmp')/f'target-change-{arm}-publication.json')
        if publication['input_provenance']['batch'] != source.batch:
            raise ValueError('Published parent batch changed')
        worker = read_json(parent/'worker.json')
        for symbol, bars in worker['bars'].items():
            rows = source.rows(symbol, bars[0]['trade_date'], bars[-1]['trade_date'])
            expected = [audited_bar(r) if arm == 'FR25' else etf_bar(r) for r in rows]
            # PriceBar permits optional symbol; compare effective fields only.
            fields = ('trade_date','open','high','low','close','volume')
            if [{k:r[k] for k in fields} for r in expected] != [{k:r[k] for k in fields} for r in bars]:
                raise ValueError('Frozen worker differs from audited publication: '+arm+'/'+symbol)
            if arm == 'FR25':
                raw = [audited_bar(r, raw=True) for r in rows]
                if [{k:r[k] for k in fields} for r in raw] != [{k:r[k] for k in fields} for r in worker['raw_bars'][symbol]]:
                    raise ValueError('Raw activity differs from publication')
        usd = publication['input_provenance']['usd']
        if sha256(Path(usd['root'])/'manifest.json') != usd['batch']:
            raise ValueError('USD manifest changed')
        checked_files(Path(usd['root']), 'manifest.json')
        if read_json(Path(usd['root'])/'snapshots.json') != worker['usd']['snapshots']:
            raise ValueError('Frozen USD snapshots differ')
        destination = root/'parents'/arm
        destination.mkdir(parents=True, exist_ok=True)
        for name in ('worker.json','protocol.json','input_manifest.json'):
            shutil.copyfile(parent/name, destination/name)
        for name in ('decisions.json','quotes.json','sessions.json','spec.json'):
            shutil.copyfile(parent/'bundles'/key/name, destination/name)
        write_json(destination/'publication.json', publication)
        receipts[arm] = dict(root=str(parent.resolve()), input_manifest=sha256(parent/'input_manifest.json'),
            worker=sha256(parent/'worker.json'), bundle_manifest=sha256(parent/'bundles'/key/'manifest.json'))
    worker = read_json(root/'parents/FR25/worker.json')
    reader = EconomicInputs(**worker['economic']['pin'])
    entries = {(r['series'],r['vintage']):r for r in reader.catalog['snapshots']}
    days = [r['trade_date'] for r in worker['bars']['SPY']]
    needed = [days[i-1] for i,d in enumerate(days) if '2021-01-04' <= d <= '2026-10-14'] + [days[-1]]
    financial = worker['economic']['provenance']['series']
    missing = []
    for known in needed:
        vintage = str(date.fromisoformat(known)-timedelta(days=1))
        for series in financial:
            if (series, vintage) not in entries:
                missing.append(dict(kind='financial', series=series, vintage=vintage, known=known))
    usd_known = {r['known_through'] for r in worker['usd']['snapshots']}
    missing += [dict(kind='usd', series='DTWEXBGS', known=k,
        vintage=str(date.fromisoformat(k)-timedelta(days=1))) for k in needed if k >= '2024-03-28' and k not in usd_known]
    write_json(root/'registered_protocol.json', protocol)
    write_json(root/'coverage.json', dict(needed_closes=needed, missing=missing,
        financial_existing=len(entries), usd_existing=len(usd_known), price_files=source.used,
        parents=receipts, limitations=[
            'F3 uses its published adjusted-price/source-volume legacy proxy; not audited raw activity confirmation.',
            'Daily financial inference requires current daily features and frozen monthly coefficients; no daily refit.',
            'Historical macro archive_daily availability is retrospective, not an observed publication timestamp.']))
    write_json(root/'environment.json', dict(python=sys.version,
        dependencies={k:importlib.metadata.version(k) for k in ('numpy','scikit-learn','xgboost','pydantic')}))
    shutil.copyfile(Path(__file__), root/'prepare_runner.py')
    write_json(root/'preflight_manifest.json', {p.relative_to(root).as_posix():sha256(p)
        for p in sorted(root.rglob('*')) if p.is_file()})
    print('Verified parents; missing daily captures:',len(missing),flush=True)


def acquire(root, limit, workers):
    checked_files(root, 'preflight_manifest.json')
    settings = AppSettings()
    store = StudyPublications(AnalyticsStore.from_settings(settings))
    config = configuration(settings)
    series = {s['id']:s for s in config['series']}
    jobs = read_json(root/'coverage.json')['missing']
    def job(row):
        destination = root/'captures'/row['series']/row['vintage']
        if (destination/'published.json').exists():
            result = read_json(destination/'published.json')
            checked_files(Path(result['root']), 'manifest.json')
            if sha256(Path(result['root'])/'manifest.json') != result['batch']:
                raise ValueError('Capture manifest changed')
            return 'cached'
        destination.mkdir(parents=True, exist_ok=True)
        if row['kind'] == 'financial':
            result = capture(settings, store, config, series[row['series']], row['vintage'], datetime.now(UTC), fetch_csv)
        else:
            from systematic_trading.live.trading_calendar import next_us_trading_day
            url = 'https://alfred.stlouisfed.org/graph/alfredgraph.csv?' + urlencode(dict(
                id='DTWEXBGS',cosd='2006-01-01',coed=row['vintage'],vintage_date=row['vintage']))
            raw = fetch_csv(url)
            snapshot = audit_snapshot(raw.decode('utf-8-sig'),dict(vintage_date=row['vintage'],
                known_through=row['known'], decision_date=str(next_us_trading_day(date.fromisoformat(row['known'])))))
            published = destination/'audited'
            published.mkdir(exist_ok=True)
            (published/'source.csv').write_bytes(raw)
            snapshot.update(source_url=url,source_sha256=sha256(published/'source.csv'),retrieved_at=datetime.now(UTC).isoformat())
            write_json(published/'snapshot.json',snapshot)
            batch = publish_files(store,'usd-broad-index/'+row['known'],published,dict(snapshot=snapshot),
                provenance=dict(known_through=row['known'],vintage=row['vintage']),observations=[])
            result = dict(root=str(published.resolve()),batch=batch,known_through=row['known'])
        write_json(destination/'published.json',result)
        return 'published'
    pending = [r for r in jobs if not (root/'captures'/r['series']/r['vintage']/'published.json').exists()]
    if limit:
        pending = pending[:limit]
    failures = []
    print('Capture jobs:',len(pending), 'workers:',workers,flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(job,r):r for r in pending}
        for i,future in enumerate(as_completed(futures),1):
            try:
                future.result()
            except Exception as exc:
                failures.append(dict(job=futures[future],error=str(exc)))
                print('Quarantined',futures[future],str(exc),flush=True)
            if i%25 == 0 or i == len(pending):
                print('Captures',i,'/',len(pending),'failures',len(failures),flush=True)
    write_json(root/('capture-attempt-'+datetime.now(UTC).strftime('%Y%m%dT%H%M%S')+'.json'),
        dict(requested=len(pending), failures=failures))
    return not failures


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT)
    parser.add_argument('--acquire',action='store_true')
    parser.add_argument('--limit',type=int,default=0)
    parser.add_argument('--workers',type=int,default=3,choices=range(1,9))
    args=parser.parse_args()
    prepare(args.root.resolve())
    if args.acquire and not acquire(args.root.resolve(),args.limit,args.workers):
        raise SystemExit(1)
