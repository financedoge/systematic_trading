"""Bounded application-owned refresh of supported current catalog identities.

No strategy membership or promotion is inferred from recorder membership.
Prior historical conflicts remain review evidence in every refreshed audit.
"""
from datetime import UTC, datetime, timedelta
import json
from pathlib import Path
import re
from uuid import uuid4

from systematic_trading.daily_quality import completed_session
from systematic_trading.live.trading_calendar import previous_us_trading_day
from systematic_trading.market_data.analytics_store import digest
from systematic_trading.portfolio.context import NY
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.governed_refresh import acquire, _build_publish, validate_revision
from systematic_trading.research.price_governance import consolidate, governed_sessions, yahoo_source
from systematic_trading.runtime_io import atomic_json


def expected_session(now):
    day = now.astimezone(NY).date()
    return str(day if completed_session(day, now) else previous_us_trading_day(day))


def eligibility(row):
    from systematic_trading.research.etf_admission import admission_hold
    hold = admission_hold(row['symbol'])
    if hold:
        return hold
    if not re.fullmatch(r'[A-Z0-9][A-Z0-9.\-]{0,19}', row['symbol']):
        return 'Unsupported symbol identity'
    if not row.get('rows') or not row.get('name') or not row.get('listing_boundary', {}).get('date'):
        return 'No supported history or listing identity'
    if row.get('unresolved_historical_names'):
        return 'Historical issuer identity requires review'
    if row.get('last', '') < row.get('requested_cutoff', ''):
        return 'History ended before its audited cutoff; current listing requires review'
    if row.get('status') not in {'audited_with_limitations', 'review'}:
        return 'Audit does not support automatic refresh'
    return None


def load_state(settings):
    path = settings.data_dir / 'governance/listed-daily-state.json'
    return json.loads(path.read_text(encoding='utf8')) if path.exists() else {}


def refresh_listed_daily(settings, analytics, *, now=None, fetch=acquire, batch_size=64):
    if not settings.governed_refresh_enabled:
        return False
    now = now or datetime.now(UTC)
    cutoff = expected_session(now)
    publication = analytics.latest('governance/catalog')
    if not publication:
        raise ValueError('Listed daily recorder requires a verified initial catalog')
    prior = GovernedInputs(Path(json.loads(publication['provenance'])['root']), publication['version'])
    catalog = json.loads(prior.checked('catalog.json').read_text(encoding='utf8'))
    state = load_state(settings)
    saved = state.setdefault('symbols', {})
    candidates = []
    for row in catalog:
        if eligibility(row) or row.get('last', '') >= cutoff:
            continue
        receipt = saved.get(row['symbol'], {})
        retry = receipt.get('retry_at')
        if retry and now < datetime.fromisoformat(retry):
            continue
        candidates.append(row)
    candidates.sort(key=lambda r: (saved.get(r['symbol'], {}).get('attempted_at', ''), r['symbol']))
    chosen = candidates[:batch_size]
    if not chosen:
        return False
    output = settings.data_dir.resolve() / 'governance' / ('listed-' + cutoff + '-' + uuid4().hex[:12])
    state.update(cutoff=cutoff, checked_at=now.isoformat(), owner='application',
                 evidence_root=str(output), pending=len(candidates))
    path = settings.data_dir / 'governance/listed-daily-state.json'
    sessions, _ = governed_sessions('1950-01-01', cutoff)
    accepted, old_rows = {}, {}
    for row in chosen:
        symbol = row['symbol']
        receipt = dict(status='acquiring', attempted_at=now.isoformat(), cutoff=cutoff,
                       retry_at=(now + timedelta(minutes=5)).isoformat(), evidence_root=str(output))
        saved[symbol] = receipt
        atomic_json(path, state)
        try:
            raw = fetch(symbol, now)
            evidence = output / 'inspection' / (symbol + '.json')
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_bytes(raw)
            source = yahoo_source(json.loads(raw), key='listed-preflight/' + symbol, symbol=symbol,
                raw_hash=digest(raw), vintage=now.isoformat(), priority=100, action_start='1950-01-01')
            meta = source.metadata
            if (meta.get('symbol') != symbol or meta.get('currency') != 'USD'
                    or meta.get('instrumentType') not in {'EQUITY', 'ETF'}
                    or meta.get('exchangeTimezoneName') != 'America/New_York'):
                raise ValueError('Unsupported current provider identity, market or currency: ' + symbol)
            if meta.get('listing_boundary_date') != row['listing_boundary']['date']:
                raise ValueError('Listing boundary changed; identity review required: ' + symbol)
            source.metadata['identity_eligible'] = True
            bars, audit, _ = consolidate(symbol, [source], sessions, cutoff)
            old = prior.rows(symbol, '1950-01-01', cutoff)
            validate_revision(symbol, old, bars, prior.audit(symbol), audit, cutoff)
            accepted[symbol], old_rows[symbol] = raw, old
            receipt['status'] = 'validated_pending_publication'
        except Exception as exc:
            receipt.update(status='quarantined', error=str(exc),
                           retry_at=(now + timedelta(hours=6)).isoformat())
        atomic_json(path, state)
    if not accepted:
        return False
    try:
        _build_publish(analytics, prior, publication, output, sorted(accepted), old_rows, cutoff, now,
            lambda symbol, _: accepted[symbol], instrument_types=('EQUITY', 'ETF'), retain_prior_review=True)
    except Exception as exc:
        for symbol in accepted:
            saved[symbol].update(status='publication_failed', error=str(exc))
        atomic_json(path, state)
        raise
    published = analytics.latest('governance/catalog')['version']
    for symbol in accepted:
        saved[symbol].update(status='published', last=cutoff, batch=published, retry_at=None)
    atomic_json(path, state)
    return True
