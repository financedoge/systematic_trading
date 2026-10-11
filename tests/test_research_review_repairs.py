"""Regression counterexamples for the second research review."""
from datetime import date, timedelta
from decimal import Decimal
import json

import numpy as np
import pytest

from systematic_trading.research import alpha101 as alpha
from systematic_trading.research import alpha101_tilt as tilt
from systematic_trading.research import alpha101_tilt_daily_study as daily
from systematic_trading.research import alpha101_tilt_exit_study as exits
from systematic_trading.research import alpha101_tilt_overlay as overlay
from systematic_trading.research import turnover_gate as gate
from systematic_trading.research import turnover_gate_analysis as calibration


def bars(count=50):
    return [dict(trade_date=str(date(2025, 1, 1) + timedelta(days=i)),
                 open=100+i, high=102+i, low=99+i, close=101+i, volume=100+i*3)
            for i in range(count)]


def test_activity_join_is_by_date_raw_and_strict_cutoff():
    adjusted = bars()
    raw = [dict(r, close=r['close'] * 2, volume=r['volume'] * 3) for r in adjusted]
    cutoff = adjusted[-2]['trade_date']
    h = alpha.history_from_rows('SPY', adjusted, cutoff, raw_rows=raw)
    assert h.raw_close[-1] == raw[-2]['close']
    assert h.volume[-1] == raw[-2]['volume']
    value = alpha.value('43', h)
    assert value is not None
    raw[-1]['close'] = 1e20
    assert alpha.value('43', alpha.history_from_rows('SPY', adjusted, cutoff, raw_rows=raw)) == value
    missing = alpha.history_from_rows('SPY', adjusted, cutoff, raw_rows=raw[:-2])
    assert np.isnan(missing.raw_close[-1])
    assert alpha.value('43', missing) is None
    assert alpha.value('21', missing) is None
    with pytest.raises(ValueError, match='Duplicate'):
        alpha.history_from_rows('SPY', adjusted, cutoff, raw_rows=raw + raw[:1])


def test_monitored_overlay_receives_same_raw_history_as_research():
    from systematic_trading.domain.market import PriceBar
    adjusted = bars()
    raw = [dict(r, close=r['close'] * 2) for r in adjusted]
    # PriceBar needs explicit symbol and currency; inherit the registered example contract.
    typed = [PriceBar.model_validate(dict(r, symbol='SPY', currency='USD')) for r in adjusted]
    typed_raw = [PriceBar.model_validate(dict(r, symbol='SPY', currency='USD')) for r in raw]
    history = overlay.history('SPY', typed, 260, typed_raw)
    research = alpha.history_from_rows('SPY', adjusted, adjusted[-1]['trade_date'], raw_rows=raw)
    for key in alpha.REGISTERED:
        assert alpha.value(key, history) == alpha.value(key, research)
    assert alpha.value('43', history) is not None


@pytest.mark.parametrize('ic,expected', [(0, 'reject'), (-.1, 'reject'), (.1, 'pass')])
def test_zero_cost_never_substitutes_for_positive_information(ic, expected):
    result = gate.screen(0, sigma=.05, candidate_ic=ic)
    assert result['status'] == expected
    assert result['ic_margin'] is None
    json.dumps(result, allow_nan=False)


@pytest.mark.parametrize('cost', [-2, 0, 2])
@pytest.mark.parametrize('payoff', [None, -1, 0, 1, 5, 6, 10])
def test_payoff_requires_information_and_declared_margin_independently(cost, payoff):
    limits = dict(max_annual_cost_bps=4, cost_tolerance=0, min_ic_margin=3)
    result = tilt.payoff_gate(payoff, cost, limits)
    expected = ('insufficient' if payoff is None else
                'pass' if payoff > 0 and payoff >= 3 * max(0, cost) else 'reject')
    assert result['status'] == expected


def test_payoff_cost_margin_is_invariant_to_exposure_scale():
    limits = dict(max_annual_cost_bps=4, cost_tolerance=0, min_ic_margin=3)
    for scale in (.1, .5, 1):
        result = tilt.payoff_gate(12 * scale, 2 * scale, limits)
        assert result['payoff_cost_margin'] == pytest.approx(6)
        assert result['status'] == 'pass'


def test_missing_forward_leg_cannot_be_dropped_from_payoff(monkeypatch):
    base, moved = {'a': .3, 'b': .3}, {'a': .325, 'b': .275}
    monkeypatch.setattr(tilt.screening, 'forward_returns', lambda *a: {'a': .1})
    assert tilt.tilt_payoff('2026-01-02', moved, base) is None
    monkeypatch.setattr(tilt.screening, 'forward_returns', lambda *a: {'a': .1, 'b': -.1})
    assert tilt.tilt_payoff('2026-01-02', moved, base) == pytest.approx(.005)
    assert tilt.tilt_payoff('2026-01-02', base, base) == 0


def test_unchanged_monthly_targets_still_rebalance_but_not_between_months():
    days = ['2026-01-02', '2026-01-05', '2026-02-02', '2026-02-03']
    books = {d: {'SPY': .3, 'GLD': .3} for d in days}
    desired = {d: {'SPY': .025, 'GLD': -.025} for d in days}
    rebals = {days[0], days[2]}
    rows, _ = daily.simulate(books, rebals, .05, 3, desired)
    hold, _ = exits.simulate(books, rebals, .05, 'HOLD', desired, {})
    assert set(rows) == set(hold) == rebals


def test_base_book_never_reads_later_decision_in_same_month(monkeypatch, tmp_path):
    decisions = {'2026-01-02': {'targets': [dict(symbol='SPY', target_weight='.3')]},
                 '2026-02-03': {'targets': [dict(symbol='GLD', target_weight='.3')]}}
    data = {'SPY': [dict(trade_date=d) for d in ['2026-01-02', '2026-02-02', '2026-02-03']]}
    monkeypatch.setitem(daily.BASES, 'TEST', dict(root=tmp_path, bars_root=tmp_path, arm='TEST'))
    monkeypatch.setattr(daily, 'read_json', lambda p: data if p.name == 'bars.json' else decisions)
    result = daily.base_books('TEST')
    assert result['2026-02-02'] == {'SPY': .3}
    assert result['2026-02-03'] == {'GLD': .3}


def test_pnl_proxy_uses_pre_entry_close_and_cannot_see_future_close():
    days = ['2026-01-02', '2026-01-05', '2026-01-06']
    books = {d: {'SPY': .3, 'GLD': .3} for d in days}
    wanted = {d: {'SPY': .025, 'GLD': -.025} for d in days}
    closes = {s: {'2025-12-31': 100, **{d: 100 for d in days}} for s in ('SPY', 'GLD')}
    closes['SPY'][days[0]] = 150
    rows, events = exits.simulate(books, {days[0]}, .05, 'EXIT-TP-1', wanted, closes)
    assert events['exit_days'] == [days[1]]  # entry-day gain is not discarded
    closes['SPY'][days[1]] = .01
    poisoned, _ = exits.simulate(books, {days[0]}, .05, 'EXIT-TP-1', wanted, closes)
    assert rows == poisoned


def test_daily_event_metadata_uses_its_own_cutoff():
    template = dict(signal_session='2026-01-02', known_through='2025-12-31',
                    targets=[dict(symbol='SPY', target_weight='.3')])
    row = daily.tilt_row(template, {'SPY': .3}, day='2026-01-06', known_through='2026-01-05')
    assert row['signal_session'] == '2026-01-06'
    assert row['known_through'] == '2026-01-05'
    with pytest.raises(ValueError, match='strictly prior'):
        daily.tilt_row(template, {'SPY': .3}, day='2026-01-06', known_through='2026-01-06')


def test_calibration_matches_replay_calendar(monkeypatch, tmp_path):
    dates = ['2021-01-04', '2021-02-01']
    name = 'CP-cost5-delay0-evaluation'
    decisions = {d: dict(targets=[dict(symbol='SPY', target_weight='.3')])
                 for d in ['2016-01-04', *dates, '2026-01-02']}
    replay = dict(decisions={d: decisions[d] for d in dates}, nav=[dict(date=d) for d in dates])
    def read(path):
        return replay if path.parent.name == 'python' else decisions
    monkeypatch.setattr(calibration, 'read_json', read)
    stats = {name: dict(dates=dates, annual_turnover=1, annual_cost_bps=5)}
    row = calibration.arm_row('CP', stats, tmp_path)
    assert row['decisions'] == 2 and row['first'] == dates[0] and row['last'] == dates[-1]
    replay['decisions'].pop(dates[-1])
    with pytest.raises(ValueError, match='calendars differ'):
        calibration.arm_row('CP', stats, tmp_path)


def test_verification_does_not_overwrite_frozen_measurement(monkeypatch, tmp_path):
    (tmp_path / 'input_manifest.json').write_text(json.dumps({'files': {}}))
    original = '{"old": true}'
    (tmp_path / 'tilt.json').write_text(original)
    monkeypatch.setattr(tilt, '_DATA', {})
    monkeypatch.setattr(tilt, 'run', lambda root: (root / 'tilt.json').write_text('{"new":true}'))
    assert tilt.verify(tmp_path)['reproduced'] is False
    assert (tmp_path / 'tilt.json').read_text() == original


def test_old_missing_activity_does_not_poison_later_complete_adv_window():
    prices, volume = np.ones(60), np.ones(60)
    prices[0] = np.nan
    actual = alpha.rolling_adv(prices, volume, 20)
    assert np.isnan(actual[0])
    assert np.all(actual[-20:] == 1)


def test_event_template_uses_latest_actual_decision_not_future_month(monkeypatch, tmp_path):
    days = ['2026-01-02', '2026-02-02', '2026-02-03']
    rows = {days[0]: {'id': 'old'}, days[2]: {'id': 'new'}}
    monkeypatch.setitem(daily.BASES, 'TEST', dict(bars_root=tmp_path))
    monkeypatch.setattr(daily, 'read_json', lambda p: {'SPY': [dict(trade_date=d) for d in ['2025-12-31', *days]]})
    templates, prior = daily.event_context('TEST', rows, days)
    assert templates[days[1]]['id'] == 'old' and templates[days[2]]['id'] == 'new'
    assert prior[days[1]] == days[0]


def test_gate_contract_and_decay_coverage_include_alpha_variant():
    from systematic_trading.portfolio.strategy_allocation import allocation_contract_issue
    from systematic_trading.research.strategy_catalog import alpha101_tilt_definition, defensive_cash_definition
    from systematic_trading.research.signal_decay_job import KEY_SIGNALS, COVERAGE_GAPS
    key = alpha101_tilt_definition().key
    assert '14-ETF paper execution contract' in allocation_contract_issue(alpha101_tilt_definition())
    assert allocation_contract_issue(defensive_cash_definition()) is None
    assert key in KEY_SIGNALS
    assert any(g['name'] == 'alpha101_family_tilt' and key in g['used_by'] for g in COVERAGE_GAPS)
