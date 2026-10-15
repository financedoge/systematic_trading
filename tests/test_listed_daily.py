import json
from datetime import UTC, datetime

from systematic_trading.lean.contracts import sha256
from systematic_trading.recorders import listed_daily as module
from systematic_trading.research import governed_refresh
from test_governed_refresh import governed


def prepare(governed):
    settings, analytics, fetch, written = governed
    settings = settings.model_copy(update={'governed_refresh_enabled': True})
    publication = analytics.latest('governance/catalog')
    root = settings.data_dir / 'original'
    catalog = [dict(symbol=s, name=s+' Example ETF', rows=140, last='2026-08-03',
        requested_cutoff='2026-08-03', status='review', listing_boundary={'date': '2026-01-02'})
        for s in ('URTH', 'X')]
    governed_refresh._write(root, 'catalog.json', catalog)
    governed_refresh._write(root, 'manifest.json', {p.relative_to(root).as_posix():sha256(p)
        for p in root.rglob('*') if p.is_file() and p.name != 'manifest.json'})
    analytics.publish('governance/catalog', sha256(root/'manifest.json'), [], provenance=json.loads(publication['provenance']))
    return settings, analytics, fetch, written


def test_full_catalog_queue_is_bounded_and_resumes_other_symbols(governed):
    settings, analytics, fetch, written = prepare(governed)
    now = datetime(2026, 8, 4, 22, tzinfo=UTC)
    assert module.refresh_listed_daily(settings, analytics, now=now, fetch=fetch, batch_size=1)
    state = module.load_state(settings)['symbols']
    assert state['URTH']['status'] == 'published' and 'X' not in state
    assert module.refresh_listed_daily(settings, analytics, now=now, fetch=fetch, batch_size=1)
    assert module.load_state(settings)['symbols']['X']['status'] == 'published'
    assert not module.refresh_listed_daily(settings, analytics, now=now, fetch=fetch, batch_size=1)


def test_one_failed_identity_does_not_block_peer_publication(governed):
    settings, analytics, fetch, written = prepare(governed)
    def changed(symbol, now):
        raw = json.loads(fetch(symbol, now))
        if symbol == 'URTH':
            raw['chart']['result'][0]['meta']['currency'] = 'CAD'
        return json.dumps(raw).encode()
    assert module.refresh_listed_daily(settings, analytics, now=datetime(2026, 8, 4, 22, tzinfo=UTC), fetch=changed)
    state = module.load_state(settings)['symbols']
    assert state['URTH']['status'] == 'quarantined'
    assert state['X']['status'] == 'published'
    assert all(s == 'X' for _, _, s, _ in written)


def test_equity_can_refresh_without_erasing_prior_conflicts(governed):
    settings, analytics, fetch, written = prepare(governed)
    root = settings.data_dir / 'original'
    old = json.loads((root/'audits/URTH.json').read_text())
    old.update(status='review', conflict_dates=42, volume_conflict_pairs=3)
    governed_refresh._write(root, 'audits/URTH.json', old)
    governed_refresh._write(root, 'manifest.json', {p.relative_to(root).as_posix():sha256(p)
        for p in root.rglob('*') if p.is_file() and p.name != 'manifest.json'})
    analytics.publish('governance/catalog', sha256(root/'manifest.json'), [], provenance={'root':str(root)})
    def equity(symbol, now):
        data = json.loads(fetch(symbol, now))
        data['chart']['result'][0]['meta']['instrumentType'] = 'EQUITY'
        return json.dumps(data).encode()
    assert module.refresh_listed_daily(settings, analytics, now=datetime(2026, 8, 4, 22, tzinfo=UTC), fetch=equity)
    latest = analytics.latest('governance/catalog')
    published = json.loads((module.Path(json.loads(latest['provenance'])['root'])/'audits/URTH.json').read_text())
    assert published['status'] == 'review'
    assert published['previous_audit']['conflict_dates'] == 42
