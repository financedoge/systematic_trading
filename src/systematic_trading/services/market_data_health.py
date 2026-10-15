"""Data delivery health, independent of process liveness and batch timestamps."""
from datetime import UTC, datetime, timedelta
import json

from systematic_trading.recorders.listed_daily import eligibility, expected_session, load_state
from systematic_trading.recorders.recovery import recovery_windows


def series_freshness(row, *, cutoff, enabled=True, receipt=None):
    reason = eligibility(row)
    latest = row.get('last')
    stale = not latest or latest < cutoff
    receipt = receipt or {}
    status = ('missing' if not latest else 'stale' if stale else 'current')
    recorder = ('review_required' if reason else 'disabled' if not enabled else receipt.get('status', 'pending')
                if stale else 'current')
    message = f"{row['symbol']}: {status}; last published session {latest or 'none'}, expected {cutoff}."
    if reason:
        message += ' Automatic refresh held: ' + reason + '.'
    elif not enabled:
        message += ' Automatic daily refresh is disabled.'
    elif stale:
        message += ' Recorder ' + recorder.replace('_', ' ') + '.'
    if receipt.get('error') and stale:
        message += ' ' + receipt['error']
    return dict(status=status, stale=stale, expected_session=cutoff, last_session=latest,
                recorder_status=recorder, message=message)


def daily_coverage(settings, rows, *, now=None):
    now = now or datetime.now(UTC)
    cutoff = expected_session(now)
    receipts = load_state(settings).get('symbols', {})
    annotated = [dict(row, freshness=series_freshness(row, cutoff=cutoff,
        enabled=settings.governed_refresh_enabled, receipt=receipts.get(row['symbol']))) for row in rows]
    supported = [r for r in annotated if not eligibility(r)]
    stale = [r for r in supported if r['freshness']['stale']]
    held = [r for r in annotated if eligibility(r)]
    current = len(supported)-len(stale)
    quarantined = sum(r['freshness']['recorder_status'] in {'quarantined', 'publication_failed'} for r in stale)
    message = (f'Daily histories: {current}/{len(supported)} supported current-listing candidates current through {cutoff}; '
               f'{len(stale)} stale or pending, {quarantined} acquisition/audit failures; {len(held)} histories require listing/identity review.')
    if stale:
        message += ' Stale examples: ' + ', '.join(r['symbol'] for r in stale[:8]) + '.'
    if not rows:
        message = 'No published daily catalog is available.'
    return dict(status='degraded' if stale or not supported else 'ok', message=message,
                expected_session=cutoff, current=current, supported=len(supported), stale=len(stale),
                quarantined=quarantined, review_required=len(held), series=annotated)


def intraday_coverage(settings, *, now=None):
    now = now or datetime.now(UTC)
    path = settings.data_dir / 'run/market_data_recorder.recovery.state.json'
    try:
        state = json.loads(path.read_text(encoding='utf8'))
        heartbeat = datetime.fromisoformat(state['heartbeat_at'])
        details = state['details']
        symbols = details['symbols']
        if not state.get('running') or (now-heartbeat).total_seconds() > 180 or not symbols:
            raise ValueError('Recovery worker stopped, heartbeat stale, or no symbols configured')
        windows = recovery_windows(symbols, (now-timedelta(days=7)).date(), now-timedelta(minutes=5))
        expected = max((w.end.isoformat() for w in windows), default=None)
        latest = details.get('latest_complete_end_by_symbol', {})
        missing = [s for s in symbols if expected and latest.get(s, '') < expected]
        counts = details.get('windows_by_status', {})
        gaps = sum(counts.get(s, 0) for s in ('pending', 'retry', 'source_partial', 'expired', 'in_progress'))
        status = 'degraded' if missing or gaps or state.get('last_error') else 'ok'
        message = (f'Intraday OHLCV: {len(symbols)} configured symbols; {len(missing)} behind expected window '
                   f'{expected}; {gaps} unresolved historical windows. Delayed quote samples are separate.')
        if missing:
            message += ' Missing/stale: ' + ', '.join(missing) + '.'
        if state.get('last_error'):
            message += ' ' + state['last_error']
        return dict(status=status, message=message, symbols=symbols, expected_window_end=expected,
                    latest_complete_end_by_symbol=latest, missing_symbols=missing, unresolved_windows=gaps)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return dict(status='error', message=f'Intraday coverage unavailable: {exc}')


def check_market_data(settings, analytics, *, now=None):
    now = now or datetime.now(UTC)
    try:
        rows = [json.loads(r['payload']) for r in analytics.observations(
            'governance/catalog', family='governed_series_catalog', limit=100000)]
        daily = daily_coverage(settings, rows, now=now)
        daily.pop('series')
    except Exception as exc:
        daily = dict(status='error', message=f'Daily coverage check failed: {exc}')
    intraday = intraday_coverage(settings, now=now)
    status = 'error' if 'error' in {daily['status'], intraday['status']} else (
        'degraded' if 'degraded' in {daily['status'], intraday['status']} else 'ok')
    return dict(status=status, checked_at=now.isoformat(), daily=daily, intraday=intraday,
                message=daily['message'] + ' ' + intraday['message'])
