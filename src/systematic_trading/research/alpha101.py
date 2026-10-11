"""Alpha101 Tier-A time-series alphas (P4.17), as point-in-time features.

The sixteen alphas the programme registered — 6, 7, 9, 12, 21, 23, 24, 26, 35, 43, 46,
49, 51, 53, 54, 101 — implemented from the paper's own formulas (Appendix A of
Kakushadze 2016), which are reproduced verbatim in :data:`FORMULAS` and pinned against a
hash-checked extraction of the paper copy in the study's evidence root. Each function
documents the formula it implements; a test asserts the registry matches the pinned
extraction, so a transcription slip cannot pass silently.

**Point-in-time contract.** Every function takes a :class:`History` whose arrays end at the
last *known* session — the caller slices, this module never looks forward — and returns
``None`` when the formula's window is not fully available. Nothing is filled, interpolated
or forward-filled: an unsupported observation stays missing.

**Data basis.** Prices are the audited dividend/split-adjusted series (return research
basis); ``volume`` is audited raw traded volume, because these formulas use traded activity.
``adv{d}`` follows the paper's own definition — *average daily dollar volume* — so it is
mean(adjusted close x raw volume, d).

**Disclosed unit quirk in the published formulas.** The paper defines ``adv{d}`` as dollar
volume while ``volume`` is share volume, and three registered alphas compare or divide the
two directly: alpha 7's ``adv20 < volume``, alpha 21's ``volume / adv20`` and alpha 43's
``ts_rank(volume / adv20, 20)``. Implemented verbatim on share volume these conditions are
dominated by price level, and alpha 7 collapses to its constant ``-1`` branch. That is a
property of the published formulas, not of this implementation: it is measured, reported
per alpha in the screen, and never silently repaired. A dollar-volume-consistent variant is
a different, declared candidate family.

**Declared conventions**, where the paper leaves normalisation open:

* ``ts_rank(x, d)`` is the rank of the current value among the window's ``d`` values scaled
  to ``(0, 1]`` — ties share the highest rank — which is the convention the corroborating
  reference implementation uses.
* ``stddev`` and ``correlation`` are population statistics over the window.
* Selection only ever uses the *ordering* of these values across instruments, so any
  strictly monotone rescaling of a formula leaves the study's mappings unchanged.
"""
from dataclasses import dataclass
from typing import Callable

import numpy as np

WINDOW = 200  # the longest lookback any registered alpha needs


@dataclass(frozen=True)
class History:
    """One instrument's audited history, ending at the last known session."""

    symbol: str
    date: str
    open: np.ndarray
    high: np.ndarray
    low: np.ndarray
    close: np.ndarray
    volume: np.ndarray

    def __len__(self) -> int:
        return len(self.close)


# --- operators (all point-in-time: index -1 is the last known session) --------

def delta(x: np.ndarray, d: int) -> float | None:
    if len(x) <= d:
        return None
    return float(x[-1] - x[-1 - d])


def delay(x: np.ndarray, d: int) -> float | None:
    if len(x) <= d:
        return None
    return float(x[-1 - d])


def ts_sum(x: np.ndarray, d: int) -> float | None:
    if len(x) < d:
        return None
    return float(np.sum(x[-d:]))


def ts_mean(x: np.ndarray, d: int) -> float | None:
    if len(x) < d:
        return None
    return float(np.mean(x[-d:]))


def ts_min(x: np.ndarray, d: int) -> float | None:
    if len(x) < d:
        return None
    return float(np.min(x[-d:]))


def ts_max(x: np.ndarray, d: int) -> float | None:
    if len(x) < d:
        return None
    return float(np.max(x[-d:]))


def stddev(x: np.ndarray, d: int) -> float | None:
    if len(x) < d:
        return None
    return float(np.std(x[-d:]))


def correlation(x: np.ndarray, y: np.ndarray, d: int) -> float | None:
    if len(x) < d or len(y) < d:
        return None
    left, right = x[-d:], y[-d:]
    if np.std(left) == 0 or np.std(right) == 0:
        return None
    return float(np.corrcoef(left, right)[0, 1])


def ts_rank(x: np.ndarray, d: int) -> float | None:
    """Rank of the current value within the window, scaled to (0, 1]."""
    if len(x) < d:
        return None
    window = x[-d:]
    return float(np.sum(window <= window[-1]) / d)


def adv(close: np.ndarray, volume: np.ndarray, d: int) -> float | None:
    """The latest d-session mean dollar volume. For a rolling series use ``rolling_adv``."""
    if len(close) < d or len(volume) < d:
        return None
    return float(np.mean(close[-d:] * volume[-d:]))


def rolling_adv(close: np.ndarray, volume: np.ndarray, d: int) -> np.ndarray:
    """Each session's own trailing d-session mean dollar volume, aligned to the input.

    Published formulas that divide one series by another (``volume / adv20``) need every date's own
    average. Dividing a series by the *latest* average is a different and wrong quantity, so the
    element-wise form lives here and is what the alphas use.
    """
    dollar = close * volume
    if len(dollar) < d:
        return np.array([])
    cumulative = np.concatenate([[0.0], np.cumsum(dollar)])
    return (cumulative[d:] - cumulative[:-d]) / d


def sign(value: float | None) -> float | None:
    if value is None or not np.isfinite(value):
        return None
    return float(np.sign(value))


def returns(close: np.ndarray, d: int = 1) -> np.ndarray:
    """Simple returns over the trailing d sessions, aligned to the series."""
    if len(close) <= d:
        return np.array([])
    previous, current = close[:-d], close[d:]
    if np.any(previous == 0):
        return np.array([])
    return current / previous - 1.0


# --- the sixteen registered alphas --------------------------------------------

def alpha_6(h: History) -> float | None:
    """(-1 * correlation(open, volume, 10))"""
    value = correlation(h.open, h.volume.astype(float), 10)
    return None if value is None else -1.0 * value


def alpha_7(h: History) -> float | None:
    """((adv20 < volume) ? ((-1 * ts_rank(abs(delta(close, 7)), 60)) * sign(delta(close, 7))) : (-1 * 1))"""
    average = adv(h.close, h.volume, 20)
    if average is None or not len(h.volume):
        return None
    if average < h.volume[-1]:
        if len(h.close) < 8:
            return None
        changes = h.close[7:] - h.close[:-7]
        rank = ts_rank(np.abs(changes), 60)
        direction = sign(delta(h.close, 7))
        if rank is None or direction is None:
            return None
        return -1.0 * rank * direction
    return -1.0


def alpha_9(h: History) -> float | None:
    """(0 < ts_min(delta(close, 1), 5)) ? delta(close, 1) : ((ts_max(delta(close, 1), 5) < 0)
    ? delta(close, 1) : (-1 * delta(close, 1)))"""
    if len(h.close) < 7:
        return None
    steps = h.close[1:] - h.close[:-1]
    lowest, highest, change = ts_min(steps, 5), ts_max(steps, 5), delta(h.close, 1)
    if lowest is None or highest is None or change is None:
        return None
    if lowest > 0:
        return change
    if highest < 0:
        return change
    return -1.0 * change


def alpha_12(h: History) -> float | None:
    """(sign(delta(volume, 1)) * (-1 * delta(close, 1)))"""
    volume_change = delta(h.volume.astype(float), 1)
    close_change = delta(h.close, 1)
    if volume_change is None or close_change is None:
        return None
    direction = sign(volume_change)
    return None if direction is None else direction * -1.0 * close_change


def alpha_21(h: History) -> float | None:
    """(((sum(close, 8) / 8) + stddev(close, 8)) < (sum(close, 2) / 2)) ? (-1)
    : (((sum(close, 2) / 2) < ((sum(close, 8) / 8) - stddev(close, 8))) ? 1
    : (((1 < (volume / adv20)) || ((volume / adv20) == 1)) ? 1 : (-1)))"""
    mean8 = ts_mean(h.close, 8)
    mean2 = ts_mean(h.close, 2)
    spread = stddev(h.close, 8)
    average = adv(h.close, h.volume, 20)
    if mean8 is None or mean2 is None or spread is None or not average or not len(h.volume):
        return None
    if mean8 + spread < mean2:
        return -1.0
    if mean2 < mean8 - spread:
        return 1.0
    return 1.0 if h.volume[-1] / average >= 1 else -1.0


def alpha_23(h: History) -> float | None:
    """(((sum(high, 20) / 20) < high) ? (-1 * delta(high, 2)) : 0)"""
    mean = ts_mean(h.high, 20)
    if mean is None:
        return None
    if mean < h.high[-1]:
        change = delta(h.high, 2)
        return None if change is None else -1.0 * change
    return 0.0


def alpha_24(h: History) -> float | None:
    """((((delta((sum(close, 100) / 100), 100) / delay(close, 100)) < 0.05)
    || ((delta((sum(close, 100) / 100), 100) / delay(close, 100)) == 0.05))
    ? (-1 * (close - ts_min(close, 100))) : (-1 * delta(close, 3)))"""
    if len(h.close) < WINDOW:
        return None
    means = np.array([np.mean(h.close[i:i + 100]) for i in range(len(h.close) - 100 + 1)])
    change = delta(means, 100)
    base = delay(h.close, 100)
    if change is None or base is None or base == 0:
        return None
    slope = change / base
    if slope <= 0.05:
        lowest = ts_min(h.close, 100)
        return None if lowest is None else -1.0 * (h.close[-1] - lowest)
    fallback = delta(h.close, 3)
    return None if fallback is None else -1.0 * fallback


def alpha_26(h: History) -> float | None:
    """(-1 * ts_max(correlation(ts_rank(volume, 5), ts_rank(high, 5), 5), 3))"""
    size = len(h.volume)
    if size < 12 or len(h.high) < 12:
        return None
    volume = h.volume.astype(float)
    ranked_volume = np.array([np.sum(volume[i - 4:i + 1] <= volume[i]) / 5 for i in range(4, size)])
    ranked_high = np.array([np.sum(h.high[i - 4:i + 1] <= h.high[i]) / 5 for i in range(4, len(h.high))])
    length = min(len(ranked_volume), len(ranked_high))
    correlations = [correlation(ranked_volume[:end + 1], ranked_high[:end + 1], 5)
                    for end in range(max(4, length - 3), length)]
    available = [value for value in correlations if value is not None]
    if len(available) < 3:
        return None
    return -1.0 * max(available[-3:])


def alpha_35(h: History) -> float | None:
    """((Ts_Rank(volume, 32) * (1 - Ts_Rank(((close + high) - low), 16))) * (1 - Ts_Rank(returns, 32)))"""
    ranked_volume = ts_rank(h.volume.astype(float), 32)
    combined = ts_rank((h.close + h.high) - h.low, 16)
    daily = returns(h.close, 1)
    ranked_returns = ts_rank(daily, 32) if len(daily) >= 32 else None
    if ranked_volume is None or combined is None or ranked_returns is None:
        return None
    return ranked_volume * (1 - combined) * (1 - ranked_returns)


def alpha_43(h: History) -> float | None:
    """(ts_rank((volume / adv20), 20) * ts_rank((-1 * delta(close, 7)), 8))

    The ratio is element-wise against **each date's own** rolling average dollar volume. Dividing the
    whole volume series by the latest average (as this function did until 2026-10-11) computes a
    different quantity and changes the ts_rank; it was caught in peer review and is covered by a test
    that recomputes the published formula independently.
    """
    average = rolling_adv(h.close, h.volume.astype(float), 20)
    if not len(average) or np.any(average == 0):
        return None
    ratio = h.volume[-len(average):].astype(float) / average
    first = ts_rank(ratio, 20)
    if len(h.close) < 8:
        return None
    negated = -(h.close[7:] - h.close[:-7])
    second = ts_rank(negated, 8)
    if first is None or second is None:
        return None
    return first * second


def _trend_gap(h: History) -> float | None:
    """((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)"""
    far, near = delay(h.close, 20), delay(h.close, 10)
    if far is None or near is None:
        return None
    return ((far - near) / 10) - ((near - h.close[-1]) / 10)


def alpha_46(h: History) -> float | None:
    """(0.25 < gap) ? (-1) : ((gap < 0) ? 1 : (-1 * (close - delay(close, 1))))"""
    gap = _trend_gap(h)
    if gap is None:
        return None
    if gap > 0.25:
        return -1.0
    if gap < 0:
        return 1.0
    change = delta(h.close, 1)
    return None if change is None else -1.0 * change


def alpha_49(h: History) -> float | None:
    """(gap < (-1 * 0.1)) ? 1 : ((-1 * 1) * (close - delay(close, 1)))"""
    gap = _trend_gap(h)
    if gap is None:
        return None
    if gap < -0.1:
        return 1.0
    change = delta(h.close, 1)
    return None if change is None else -1.0 * change


def alpha_51(h: History) -> float | None:
    """(gap < (-1 * 0.05)) ? 1 : ((-1 * 1) * (close - delay(close, 1)))"""
    gap = _trend_gap(h)
    if gap is None:
        return None
    if gap < -0.05:
        return 1.0
    change = delta(h.close, 1)
    return None if change is None else -1.0 * change


def alpha_53(h: History) -> float | None:
    """(-1 * delta((((close - low) - (high - close)) / (close - low)), 9))"""
    if len(h.close) < 10:
        return None
    close, low, high = h.close[-10:], h.low[-10:], h.high[-10:]
    denominator = close - low
    if np.any(denominator == 0):
        return None
    series = ((close - low) - (high - close)) / denominator
    return -1.0 * float(series[-1] - series[-10])


def alpha_54(h: History) -> float | None:
    """((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))"""
    denominator = (h.low[-1] - h.high[-1]) * (h.close[-1] ** 5)
    if denominator == 0:
        return None
    return (-1.0 * ((h.low[-1] - h.close[-1]) * (h.open[-1] ** 5))) / denominator


def alpha_101(h: History) -> float | None:
    """((close - open) / ((high - low) + .001))"""
    return float((h.close[-1] - h.open[-1]) / ((h.high[-1] - h.low[-1]) + 0.001))


FORMULAS: dict[str, str] = {
    '6': '(-1 * correlation(open, volume, 10))',
    '7': '((adv20 < volume) ? ((-1 * ts_rank(abs(delta(close, 7)), 60)) * sign(delta(close, 7))) : (-1 * 1))',
    '9': '((0 < ts_min(delta(close, 1), 5)) ? delta(close, 1) : ((ts_max(delta(close, 1), 5) < 0) ? delta(close, 1) '
         ': (-1 * delta(close, 1))))',
    '12': '(sign(delta(volume, 1)) * (-1 * delta(close, 1)))',
    '21': '((((sum(close, 8) / 8) + stddev(close, 8)) < (sum(close, 2) / 2)) ? (-1 * 1) : (((sum(close, 2) / 2) < '
          '((sum(close, 8) / 8) - stddev(close, 8))) ? 1 : (((1 < (volume / adv20)) || ((volume / adv20) == 1)) '
          '? 1 : (-1 * 1))))',
    '23': '(((sum(high, 20) / 20) < high) ? (-1 * delta(high, 2)) : 0)',
    '24': '((((delta((sum(close, 100) / 100), 100) / delay(close, 100)) < 0.05) || '
          '((delta((sum(close, 100) / 100), 100) / delay(close, 100)) == 0.05)) ? '
          '(-1 * (close - ts_min(close, 100))) : (-1 * delta(close, 3)))',
    '26': '(-1 * ts_max(correlation(ts_rank(volume, 5), ts_rank(high, 5), 5), 3))',
    '35': '((Ts_Rank(volume, 32) * (1 - Ts_Rank(((close + high) - low), 16))) * (1 - Ts_Rank(returns, 32)))',
    '43': '(ts_rank((volume / adv20), 20) * ts_rank((-1 * delta(close, 7)), 8))',
    '46': '((0.25 < (((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10))) ? (-1 * 1) '
          ': (((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < 0) ? 1 : '
          '((-1 * 1) * (close - delay(close, 1)))))',
    '49': '(((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 * 0.1)) ? 1 : '
          '((-1 * 1) * (close - delay(close, 1))))',
    '51': '(((((delay(close, 20) - delay(close, 10)) / 10) - ((delay(close, 10) - close) / 10)) < (-1 * 0.05)) ? 1 '
          ': ((-1 * 1) * (close - delay(close, 1))))',
    '53': '(-1 * delta((((close - low) - (high - close)) / (close - low)), 9))',
    '54': '((-1 * ((low - close) * (open^5))) / ((low - high) * (close^5)))',
    '101': '((close - open) / ((high - low) + .001))',
}

ALPHAS: dict[str, Callable[[History], float | None]] = {
    '6': alpha_6, '7': alpha_7, '9': alpha_9, '12': alpha_12, '21': alpha_21, '23': alpha_23, '24': alpha_24,
    '26': alpha_26, '35': alpha_35, '43': alpha_43, '46': alpha_46, '49': alpha_49, '51': alpha_51,
    '53': alpha_53, '54': alpha_54, '101': alpha_101,
}
REGISTERED = tuple(ALPHAS)


def value(name: str, history: History) -> float | None:
    """One alpha's point-in-time value, or ``None`` when its window is unavailable."""
    function = ALPHAS.get(name)
    if function is None:
        raise ValueError('Unregistered alpha: ' + str(name))
    if len(history) < 2:
        return None
    result = function(history)
    if result is None:
        return None
    return result if np.isfinite(result) else None


def values_for_day(name: str, histories: dict[str, History]) -> dict[str, float]:
    """The alpha's available values across instruments, missing observations dropped."""
    out = {}
    for symbol, history in histories.items():
        result = value(name, history)
        if result is not None:
            out[symbol] = result
    return out


def history_from_rows(symbol: str, rows, end: str) -> History | None:
    """Build a history ending at ``end`` (inclusive) from audited bar rows."""
    window = [row for row in rows if str(row['trade_date']) <= end]
    if len(window) < 2:
        return None
    return History(symbol=symbol, date=end,
                   open=np.array([float(r['open']) for r in window]),
                   high=np.array([float(r['high']) for r in window]),
                   low=np.array([float(r['low']) for r in window]),
                   close=np.array([float(r['close']) for r in window]),
                   volume=np.array([float(r['volume']) for r in window]))
