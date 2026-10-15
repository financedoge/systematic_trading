import json
from datetime import UTC, datetime, timedelta

from systematic_trading.config import AppSettings
from systematic_trading.recorders.listed_daily import eligibility, expected_session
from systematic_trading.services.market_data_health import daily_coverage, intraday_coverage, series_freshness


def row(symbol='AAPL', last='2026-09-25'):
    return dict(symbol=symbol, name=symbol, rows=200, last=last,
                requested_cutoff=last, status='review', listing_boundary={'date': '2000-01-03'})


def test_stale_history_not_hidden_by_new_catalog_or_fresh_etfs(tmp_path):
    settings = AppSettings(data_dir=tmp_path)
    data = daily_coverage(settings, [row(), row('SPY', '2026-10-14')],
                          now=datetime(2026, 10, 15, 14, tzinfo=UTC))
    assert data['status'] == 'degraded'
    assert data['current'] == data['stale'] == 1
    assert 'AAPL' in data['message']
    assert data['series'][0]['freshness']['expected_session'] == '2026-10-14'


def test_listing_holds_missing_and_disabled_never_claim_current():
    assert eligibility(row('BWX'))
    unsupported = dict(row(), last=None, rows=0)
    assert series_freshness(unsupported, cutoff='2026-10-14')['status'] == 'missing'
    data = series_freshness(row(), cutoff='2026-10-14', enabled=False)
    assert data['stale'] and data['recorder_status'] == 'disabled'
    assert eligibility(dict(row(), last='2026-08-01'))


def test_daily_deadline_respects_close_grace_weekend_and_holiday():
    assert expected_session(datetime(2026, 10, 15, 20, 19, tzinfo=UTC)) == '2026-10-14'
    assert expected_session(datetime(2026, 10, 15, 20, 20, tzinfo=UTC)) == '2026-10-15'
    assert expected_session(datetime(2026, 10, 17, 20, tzinfo=UTC)) == '2026-10-16'
    assert expected_session(datetime(2026, 12, 25, 20, tzinfo=UTC)) == '2026-12-24'


def test_intraday_checks_each_symbol_not_only_heartbeat_or_last_success(tmp_path):
    settings = AppSettings(data_dir=tmp_path)
    now = datetime(2026, 10, 15, 14, 10, tzinfo=UTC)
    path = tmp_path / 'run/market_data_recorder.recovery.state.json'
    path.parent.mkdir()
    state = dict(running=True, heartbeat_at=now.isoformat(), details=dict(symbols=['SPY', 'QQQ'],
        windows_by_status={'complete': 10}, latest_complete_end_by_symbol={
            'SPY': '2026-10-14T20:00:00+00:00', 'QQQ': '2026-09-25T20:00:00+00:00'}))
    path.write_text(json.dumps(state), encoding='utf8')
    result = intraday_coverage(settings, now=now)
    assert result['status'] == 'degraded' and result['missing_symbols'] == ['QQQ']
    state['details']['latest_complete_end_by_symbol']['QQQ'] = '2026-10-14T20:00:00+00:00'
    path.write_text(json.dumps(state), encoding='utf8')
    assert intraday_coverage(settings, now=now)['status'] == 'ok'
    assert intraday_coverage(settings, now=now+timedelta(minutes=5))['status'] == 'error'


def test_missing_and_malformed_recovery_is_an_error(tmp_path):
    settings = AppSettings(data_dir=tmp_path)
    assert intraday_coverage(settings)['status'] == 'error'
    path = tmp_path / 'run/market_data_recorder.recovery.state.json'
    path.parent.mkdir()
    path.write_text('{}', encoding='utf8')
    assert intraday_coverage(settings)['status'] == 'error'
