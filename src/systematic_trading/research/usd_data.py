"""Acquire, audit, publish and verify broad-dollar inputs for the application.

Archives are inspection evidence. Consumers read only committed, hash-verified batches.
"""
from datetime import UTC, date, datetime, timedelta
import json
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.usd_index_governance import audit_snapshot

SOURCE = 'governance/usd-broad-index'


def load_usd(analytics):
    publication = analytics.latest(SOURCE)
    if not publication:
        raise ValueError('No published USD vintage history')
    root = Path(json.loads(publication['provenance'])['root']).resolve()
    if sha256(root/'manifest.json') != publication['version']:
        raise ValueError('USD publication manifest changed')
    manifest = json.loads((root/'manifest.json').read_text(encoding='utf8'))
    for name, expected in manifest.items():
        path = (root/name).resolve()
        if not path.is_relative_to(root) or sha256(path) != expected:
            raise ValueError('USD publication input changed: '+name)
    rows = json.loads((root/'snapshots.json').read_text(encoding='utf8'))
    return rows, dict(batch=publication['version'], root=str(root), files=manifest,
        basis='Same-vintage nominal broad dollar index; Jan 2006 average = 100',
        limitations=rows[-1]['limitations'])


def refresh_usd(settings, analytics, known):
    """Idempotent app refresh; retain the previous complete publication on failure."""
    from systematic_trading.live.trading_calendar import next_us_trading_day
    from systematic_trading.runtime_io import exclusive_lock
    with exclusive_lock(settings.data_dir/'run/usd-publication.lock'):
        snapshots, previous = load_usd(analytics)
        existing = {r['known_through']: r for r in snapshots}
        history = analytics.document(SOURCE, 'history')
        if known in existing and history:
            return False
        vintage = str(date.fromisoformat(known)-timedelta(days=1))
        # Daily archives are used only after their conservative end-of-day cutoff.
        if date.fromisoformat(vintage) >= datetime.now(UTC).date():
            raise ValueError('USD vintage has not completed')
        params = dict(id='DTWEXBGS', cosd='2006-01-01', coed=vintage, vintage_date=vintage)
        url = 'https://alfred.stlouisfed.org/graph/alfredgraph.csv?'+urlencode(params)
        archive = settings.data_dir/'market_data/usd_archives'/vintage
        archive.mkdir(parents=True, exist_ok=True)
        raw = archive/'DTWEXBGS.csv'
        meta = archive/'receipt.json'
        if raw.exists() and meta.exists():
            metadata = json.loads(meta.read_text(encoding='utf8'))
            if sha256(raw) != metadata['sha256']:
                raise ValueError('Changed USD provider archive')
        else:
            with urlopen(Request(url, headers={'User-Agent': 'Mozilla/5.0 research data audit'}), timeout=35) as response:
                content = response.read(4_000_000)
            raw.write_bytes(content)
            metadata = dict(url=url, retrieved_at=datetime.now(UTC).isoformat(), sha256=sha256(raw))
            write_json(meta, metadata)
        row = audit_snapshot(raw.read_text(encoding='utf-8-sig'), dict(metadata, vintage_date=vintage,
            known_through=known, decision_date=str(next_us_trading_day(date.fromisoformat(known)))))
        row.update(source_url=url, source_sha256=metadata['sha256'], retrieved_at=metadata['retrieved_at'])
        if known in existing and row['features'] != existing[known]['features']:
            raise ValueError('Existing historical USD features changed; review required')
        existing[known] = row
        snapshots = sorted(existing.values(), key=lambda r: r['known_through'])
        history = dict(series='DTWEXBGS', name='USD · nominal broad dollar index',
            units='Index, January 2006 average = 100', vintage_date=vintage,
            observation_date=row['observation_date'], available_at=row['available_at'],
            observations=row['observations'], features=row['features'], source_url=url,
            limitations=row['limitations'],
            basis='One revised vintage for display; historical decisions use their own archived vintages. Not DXY or USD/CNH.',
            published_vintages=len(snapshots), known_through=known)
        audit = dict(policy='usd-broad-v2', previous_batch=previous['batch'], source_sha256=metadata['sha256'],
            history_use='Display current-vintage history; never substitute it for past signal vintages',
            accepted=len(snapshots), known_through=known, code_sha256=sha256(Path(__file__)))
        content_hash = digest(encode(dict(snapshots=snapshots, audit=audit, history=history)))
        root = settings.data_dir/'governance'/('usd-'+content_hash)
        root.mkdir(parents=True, exist_ok=True)
        for name, value in [('snapshots.json', snapshots), ('audit.json', audit), ('history.json', history)]:
            path = root/name
            if path.exists() and json.loads(path.read_text(encoding='utf8')) != value:
                raise ValueError('Immutable USD batch collision')
            write_json(path, value)
        write_json(root/'manifest.json', {name: sha256(root/name) for name in ('snapshots.json','audit.json','history.json')})
        batch = sha256(root/'manifest.json')
        observations = [dict(point_key=r['known_through'], family='usd_index_vintage', entity='DTWEXBGS',
            observed_at=r['observation_date'], available_at=r['available_at'], payload=encode(r)) for r in snapshots]
        analytics.publish(SOURCE, batch, observations,
            [dict(point_key=k, media_type='application/json', payload=encode(v)) for k,v in [('audit',audit),('history',history)]],
            provenance=dict(root=str(root.resolve()), batch=batch, series='DTWEXBGS', audit=audit))
        load_usd(analytics)
        return True
