"""P4.17 — Alpha101 time-series alphas and their per-alpha screen."""
import json
from pathlib import Path

import numpy as np
import pytest

from systematic_trading.research import alpha101 as lib
from systematic_trading.research import alpha101_screen as screening

ROOT = Path('var/research/alpha101-screen-20261011-v2')
PAPER = Path('research_tmp/101_formulaic_alphas.pdf')
BUILT = pytest.mark.skipif(not (ROOT / 'screen.json').exists(), reason='frozen alpha screen not built')


def history(**columns):
    """A History from column arrays; unspecified columns default from ``close``."""
    size = max(len(value) for value in columns.values())
    filled = {}
    for name in ('open', 'high', 'low', 'close', 'volume'):
        value = columns.get(name, columns.get('close'))
        assert value is not None, 'give at least close'
        filled[name] = np.array(list(value) + [value[-1]] * (size - len(value)), dtype=float)
    return lib.History(symbol='T', date='2026-01-02', **filled)


def walk(size=320, seed=7):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0004, 0.01, size)))
    high = close * (1 + np.abs(rng.normal(0, 0.004, size)))
    low = close * (1 - np.abs(rng.normal(0, 0.004, size)))
    open_ = close * (1 + rng.normal(0, 0.003, size))
    volume = rng.integers(1_000_000, 9_000_000, size).astype(float)
    return lib.History(symbol='T', date='2026-01-02', open=open_, high=high, low=low, close=close, volume=volume)


# --- operators ---------------------------------------------------------------

def test_operators_match_their_definitions():
    x = np.array([1.0, 2.0, 4.0, 8.0])
    assert lib.delta(x, 1) == 4.0 and lib.delta(x, 3) == 7.0
    assert lib.delay(x, 2) == 2.0
    assert lib.ts_sum(x, 2) == 12.0 and lib.ts_mean(x, 2) == 6.0
    assert lib.ts_min(x, 3) == 2.0 and lib.ts_max(x, 3) == 8.0
    assert lib.stddev(x, 4) == pytest.approx(np.std([1, 2, 4, 8]))
    assert lib.correlation(np.array([1.0, 2, 3]), np.array([2.0, 4, 6]), 3) == pytest.approx(1.0)
    assert lib.ts_rank(np.array([5.0, 1.0, 3.0]), 3) == pytest.approx(2 / 3)
    assert lib.adv(np.array([2.0, 2.0]), np.array([10.0, 20.0]), 2) == pytest.approx(30.0)


def test_operators_return_missing_rather_than_a_filled_value():
    x = np.array([1.0, 2.0])
    assert lib.delta(x, 2) is None and lib.delay(x, 2) is None
    assert lib.ts_sum(x, 3) is None and lib.correlation(x, x, 3) is None
    assert lib.ts_rank(x, 3) is None and lib.adv(x, x, 3) is None
    # a window with no variation has no correlation to report
    assert lib.correlation(np.array([1.0, 1, 1]), np.array([1.0, 2, 3]), 3) is None


# --- the formulas the library implements -------------------------------------

@BUILT
def test_every_implemented_formula_is_the_paper_formula():
    formulas = json.loads((ROOT / 'formulas.json').read_text(encoding='utf8'))
    assert formulas['paper_sha256'] == screening.PAPER_SHA256
    assert formulas['mismatched'] == []
    declared = {name: screening.clean_formula(lib.FORMULAS[name]) for name in lib.REGISTERED}
    extracted = {name: screening.clean_formula(formulas['extracted'][name]) for name in lib.REGISTERED}
    assert declared == extracted


@pytest.mark.skipif(not PAPER.exists(), reason='paper copy not present')
def test_the_registered_family_is_the_declared_sixteen():
    assert lib.REGISTERED == ('6', '7', '9', '12', '21', '23', '24', '26', '35', '43', '46', '49', '51', '53', '54',
                              '101')
    assert set(lib.FORMULAS) == set(lib.ALPHAS) == set(lib.REGISTERED)
    extracted = screening.extract_formulas()
    assert set(extracted) == set(lib.REGISTERED)


# --- alpha spot checks -------------------------------------------------------

def test_single_bar_formulas_are_exact():
    single = lib.History(symbol='T', date='2026-01-02', open=np.array([10.0]), high=np.array([12.0]),
                         low=np.array([9.0]), close=np.array([11.0]), volume=np.array([100.0]))
    assert lib.alpha_101(single) == pytest.approx(1 / 3.001)
    assert lib.alpha_54(single) == pytest.approx(200_000 / -483_153)


def test_alpha_12_is_sign_of_volume_change_times_negative_close_change():
    growing = history(close=[10.0, 11.0], volume=[100.0, 200.0])
    assert lib.alpha_12(growing) == pytest.approx(-1.0)
    shrinking = history(close=[10.0, 11.0], volume=[200.0, 100.0])
    assert lib.alpha_12(shrinking) == pytest.approx(1.0)


def test_alpha_9_takes_the_signed_branch_the_formula_declares():
    rising = history(close=[10.0, 11, 12, 13, 14, 15, 16])
    assert lib.alpha_9(rising) == pytest.approx(1.0)
    falling = history(close=[16.0, 15, 14, 13, 12, 11, 10])
    assert lib.alpha_9(falling) == pytest.approx(-1.0)
    # neither extreme holds, so the formula negates the one-step change
    mixed = history(close=[10.0, 11, 10, 11, 10, 11, 10])
    assert lib.alpha_9(mixed) == pytest.approx(1.0)
    assert lib.alpha_9(history(close=[10.0, 11, 12])) is None


def test_alpha_7_falls_to_its_constant_branch_when_dollar_volume_exceeds_volume():
    flat = history(close=[10.0] * 25, volume=[100.0] * 25)
    assert lib.alpha_7(flat) == -1.0


def test_alpha_21_uses_the_volume_ratio_branch_when_price_range_is_flat():
    flat = history(close=[10.0] * 25, volume=[100.0] * 25)
    assert lib.alpha_21(flat) == -1.0


def test_alpha_46_49_51_read_the_declared_gap():
    # gap = ((delay(close,20) - delay(close,10)) / 10) - ((delay(close,10) - close) / 10)
    high_gap = history(close=[1.0] + [1.0] * 9 + [2.0] * 10 + [10.0])
    assert lib.alpha_46(high_gap) == -1.0
    low_gap = history(close=[10.0] + [10.0] * 9 + [9.0] * 10 + [1.0])
    assert lib.alpha_49(low_gap) == 1.0 and lib.alpha_51(low_gap) == 1.0


def test_alpha_53_is_the_negated_nine_step_change_of_the_range_ratio():
    close = np.linspace(10.0, 12.0, 12)
    below = 0.5 * (1 + np.arange(12) / 10)     # distance to the low
    above = 0.3 * (1 + np.arange(12) / 20)     # distance to the high, deliberately different
    low, high = close - below, close + above
    series = ((close - low) - (high - close)) / (close - low)
    expected = -1.0 * (series[-1] - series[-10])
    value = lib.alpha_53(history(close=list(close), low=list(low), high=list(high)))
    assert value == pytest.approx(expected)
    assert value != 0.0


def test_long_window_alphas_report_missing_until_their_window_exists():
    short = walk(size=60)
    assert lib.alpha_24(short) is None          # needs 200 sessions
    assert lib.value('24', short) is None
    assert lib.value('26', walk(size=400)) is not None


def test_an_unregistered_alpha_is_refused():
    with pytest.raises(ValueError, match='Unregistered alpha'):
        lib.value('1', walk(size=300))


# --- point-in-time discipline ------------------------------------------------

def test_no_alpha_reads_beyond_its_declared_window():
    """At one session, the value must not depend on how much earlier history is supplied.

    This is the look-ahead check that matters here: the screen slices a rolling window, so an
    alpha that reached outside its own lookback — or back to the start of the series — would
    return a different number for a longer history ending on the same session.
    """
    full = walk(size=420)
    for alpha in lib.REGISTERED:
        values = []
        for start in (0, 60, 160, 210):
            window = lib.History(symbol=full.symbol, date=full.date, open=full.open[start:],
                                 high=full.high[start:], low=full.low[start:], close=full.close[start:],
                                 volume=full.volume[start:])
            values.append(lib.value(alpha, window))
        assert values[0] is not None, alpha
        assert values[0] == values[1] == values[2] == values[3], (alpha, values)


def test_the_screen_slices_histories_to_the_session_before_the_decision():
    """The point-in-time contract of the screen itself, on a small synthetic calendar."""
    screening._DATA = dict(days=['2026-01-02', '2026-01-05', '2026-01-06'],
                           selection={'2026-01-05': {}, '2026-01-06': {}}, day_cache={})
    assert screening.known_through('2026-01-05') == '2026-01-02'
    assert screening.known_through('2026-01-06') == '2026-01-05'
    with pytest.raises(ValueError, match='No prior session'):
        screening.known_through('2026-01-02')


def test_values_for_day_drops_missing_observations():
    short = {'A': walk(size=30), 'B': walk(size=400)}
    values = lib.values_for_day('24', short)
    assert set(values) == {'B'}


# --- screen rules ------------------------------------------------------------

def test_rank_ic_needs_enough_instruments_and_variation():
    values = {f'S{i}': float(i) for i in range(6)}
    returns = {f'S{i}': float(i) / 100 for i in range(6)}
    assert screening.rank_ic(values, returns) == pytest.approx(1.0)
    assert screening.rank_ic(values, {f'S{i}': 0.01 for i in range(6)}) is None
    assert screening.rank_ic(dict(list(values.items())[:5]), returns) is None


def test_rank_ic_averages_ties_instead_of_ranking_them_in_ticker_order():
    """Ordinal ranks made the statistic depend on instrument labels. Peer review, 2026-10-11."""
    values = {'A': 1.0, 'B': 2.0, 'C': 2.0, 'D': 4.0, 'E': 5.0, 'F': 5.0}
    returns = {'A': 0.10, 'B': 0.20, 'C': 0.90, 'D': 0.30, 'E': 0.40, 'F': 0.80}
    # the same pairs with the tied members renamed so their alphabetical order swaps
    renamed_values = {'Z': 1.0, 'B': 2.0, 'A': 2.0, 'D': 4.0, 'Y': 5.0, 'C': 5.0}
    renamed_returns = {'Z': 0.10, 'B': 0.20, 'A': 0.90, 'D': 0.30, 'Y': 0.40, 'C': 0.80}
    plain = screening.rank_ic(values, returns)
    renamed = screening.rank_ic(renamed_values, renamed_returns)
    assert plain == pytest.approx(renamed), 'rank IC must not depend on ticker labels'
    # and it must equal the textbook mid-rank Spearman correlation
    def midranks(series):
        order = sorted(series)
        ranks, index = {}, 0
        while index < len(order):
            end = index
            while end + 1 < len(order) and order[end + 1] == order[index]:
                end += 1
            for position in range(index, end + 1):
                ranks[order[position]] = (index + end) / 2 + 1
            index = end + 1
        return ranks
    left, right = midranks(list(values.values())), midranks(list(returns.values()))
    symbols = sorted(values)
    expected = float(np.corrcoef([left[values[s]] for s in symbols],
                                 [right[returns[s]] for s in symbols])[0, 1])
    assert plain == pytest.approx(expected)
    # a tied cross-section carries no view at all
    assert screening.rank_ic({f'S{i}': 1.0 for i in range(6)}, returns) is None


def test_alpha_43_divides_by_each_dates_own_rolling_dollar_volume():
    """The published formula is ts_rank(volume / adv20, 20) with adv20 rolling per date.

    Dividing the whole volume series by the *latest* average (as the implementation did until
    2026-10-11) computes a different quantity. Peer review reported 1.00 against 0.05 on a simple
    case; this test recomputes the published formula independently and pins the equality.
    """
    size = 300
    generator = np.random.default_rng(11)
    close = 100 + np.cumsum(generator.normal(0, 1, size))
    volume = 1_000_000 * np.exp(np.cumsum(generator.normal(0, 0.05, size)))
    history = lib.History(symbol='X', date='2026-10-09', open=close * 0.999, high=close * 1.01,
                          low=close * 0.99, close=close, volume=volume)
    dollar = close * volume
    rolling = np.array([np.mean(dollar[max(0, index - 19):index + 1]) for index in range(size)])
    published = (lib.ts_rank(volume / rolling, 20)
                 * lib.ts_rank(-(close[7:] - close[:-7]), 8))
    assert lib.alpha_43(history) == pytest.approx(published)
    # the element-wise helper carries each date's own window, and nothing else
    rolling_helper = lib.rolling_adv(close, volume, 20)
    assert len(rolling_helper) == size - 19
    assert rolling_helper[0] == pytest.approx(np.mean(dollar[:20]))
    assert rolling_helper[-1] == pytest.approx(np.mean(dollar[-20:]))
    # the wrong (flat, latest-average) divisor genuinely differs on this series
    flat = lib.ts_rank(volume / np.mean(dollar[-20:]), 20) * lib.ts_rank(-(close[7:] - close[:-7]), 8)
    assert abs(flat - published) > 1e-6


def test_the_block_interval_is_deterministic_and_brackets_the_mean():
    series = {f'2020-01-{i:02d}': 0.01 * ((-1) ** i) for i in range(1, 29)}
    first = screening.block_interval(series.values())
    second = screening.block_interval(series.values())
    assert first == second
    assert first['low'] <= first['mean'] <= first['high']
    assert first['seed'] == screening.SEED and first['replications'] == screening.REPLICATIONS


@BUILT
def test_the_screen_reports_no_pass_and_names_every_reason():
    payload = json.loads((ROOT / 'screen.json').read_text(encoding='utf8'))
    rows = {row['alpha']: row for row in payload['rows']}
    assert set(rows) == set(lib.REGISTERED)
    assert not [row for row in payload['rows'] if row['gate'] and row['gate']['status'] == 'pass']
    for row in payload['rows']:
        if row['gate'] is None:
            continue
        assert row['gate']['status'] in {'reject', 'insufficient'}
        assert row['gate']['reasons'], row['alpha']
        assert row['gate']['cost_ceiling_bps'] == pytest.approx(44.0)


@BUILT
def test_a_constant_cross_section_forms_no_mapping_and_is_never_passed():
    payload = json.loads((ROOT / 'screen.json').read_text(encoding='utf8'))
    rows = {row['alpha']: row for row in payload['rows']}
    degenerate = rows['7']
    assert degenerate['coverage']['mapped'] == 0
    assert degenerate['coverage']['skip_reason'] == 'the cross-section is constant, so the alpha cannot rank'
    assert degenerate['dispersion']['constant'] is True
    assert degenerate['gate'] is None
    # it is never judged against the programme reference IC
    assert degenerate['information']['21']['mean'] is None


@BUILT
def test_every_mapped_alpha_respects_the_mapping_contract():
    payload = json.loads((ROOT / 'screen.json').read_text(encoding='utf8'))
    for row in payload['rows']:
        if row['turnover'] is None:
            continue
        assert row['coverage']['mapped'] >= 2
        assert row['turnover']['annual'] > 0
        assert row['gate'] is not None
        assert row['gate']['annual_turnover'] == pytest.approx(row['turnover']['annual'])


@BUILT
def test_the_frozen_screen_reproduces_and_its_inputs_are_unchanged():
    checks = screening.verify(ROOT)
    assert checks['parent_unchanged'] and checks['paper_unchanged']
    assert checks['formulas_match_paper'] and checks['screen_reproduced']
