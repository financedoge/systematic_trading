"""The Alpha101 family tilt as a production overlay.

This is the deployable form of the rule that P4.17b–P4.17f measured: rank the names the book already
holds by the equal-weight mean of the sixteen registered alphas' rank scores, and move a bounded,
NAV-neutral amount of weight from the bottom of that ranking to the top. It never adds or removes an
instrument, never changes the gross, and shrinks as a whole so no name breaches the 45% cap or goes
negative.

**Provenance and disclosure.** The 5% budget was selected on an already inspected sample. Earlier
P4.17 evidence is superseded by the 2026-10-11 timing, funding and raw-activity repairs. The corrected
fixed-pair replay still has lower return and Sharpe than FR25; it establishes implementation parity,
not an incremental edge. It is monitored so that prospective evidence can
accumulate; the overlay grants no allocation, approval or execution authority, and the bundle
contracts record every calculation as `promotion_eligible: False`.

The arithmetic is deliberately the same as the research rule, and a test asserts that this overlay
reproduces it exactly on shared inputs, so the deployed strategy cannot silently drift from the thing
that was measured.
"""
from decimal import Decimal as D

from systematic_trading.research import alpha101 as lib

VERSION = 'alpha101-family-tilt-v2'
DEFAULT_BUDGET = D('0.05')
DEFAULT_MAX_WEIGHT = D('0.45')
DEFAULT_LOOKBACK = 260
MIN_NAMES = 2

# The single registered recipe. The catalog validates against it exactly, so a strategy cannot be
# registered with a budget, an alpha list or a cap this module never measured.
PARAMETERS = dict(version=VERSION, budget=str(DEFAULT_BUDGET), alphas=list(lib.REGISTERED),
                  lookback=DEFAULT_LOOKBACK, maxWeight=str(DEFAULT_MAX_WEIGHT))


def rank_scores(held, values):
    """Linear rank scores in [-1, +1] with zero mean, or None when nothing can be ranked."""
    ranked = sorted(symbol for symbol in held if symbol in values)
    if len(ranked) < MIN_NAMES:
        return None
    if len({round(values[symbol], 12) for symbol in ranked}) < 2:
        return None
    order = sorted(ranked, key=lambda symbol: (-values[symbol], symbol))
    size = len(order)
    if size == 2:
        return {order[0]: 1.0, order[1]: -1.0}
    return {symbol: (size - 1 - 2 * index) / (size - 1) for index, symbol in enumerate(order)}


def composite_scores(held, per_alpha):
    """The mean of each alpha's rank scores: scale-free, so averaging across alphas is meaningful."""
    contributions = [rank_scores(held, values) for values in per_alpha.values()]
    contributions = [item for item in contributions if item]
    if not contributions:
        return None
    symbols = sorted(set().union(*contributions))
    averaged = {symbol: sum(item.get(symbol, 0.0) for item in contributions) / len(contributions)
                for symbol in symbols}
    if len({round(value, 12) for value in averaged.values()}) < 2:
        return None
    return averaged


def tilt_vector(weights, scores, budget, max_weight=DEFAULT_MAX_WEIGHT):
    """The NAV-neutral tilt with one shrink factor for the cap and the zero floor."""
    budget = float(budget)
    held = [symbol for symbol, weight in weights.items() if weight > 0 and symbol in scores]
    if len(held) < MIN_NAMES:
        return {}, dict(applied=False, reason='fewer than two held names carry a value')
    positive = sum(scores[symbol] for symbol in held if scores[symbol] > 0)
    negative = -sum(scores[symbol] for symbol in held if scores[symbol] < 0)
    if positive <= 0 or negative <= 0:
        return {}, dict(applied=False, reason='the ranks carry no spread')
    tilts = {symbol: D(str((budget / 2) * (scores[symbol] / positive if scores[symbol] > 0
                                           else scores[symbol] / negative))) for symbol in held}
    over_cap = [symbol for symbol in held if weights[symbol] > max_weight]
    scale = D('1')
    for symbol, tilt in tilts.items():
        if tilt == 0:
            continue
        weight = weights[symbol]
        if tilt > 0:
            headroom = max_weight - weight
            scale = D('0') if headroom <= 0 else min(scale, headroom / tilt)
        else:
            scale = min(scale, weight / -tilt)
    scale = max(D('0'), scale)
    return {symbol: scale * tilt for symbol, tilt in tilts.items()}, dict(
        applied=scale > 0, scale=float(scale), names=len(held), cap_binding=scale < D('1'),
        over_cap_names=len(over_cap))


def history(symbol, bars, lookback, raw_bars=None):
    """A point-in-time history from the engine's own context bars (already truncated to before as-of)."""
    window = list(bars)[-lookback:]
    if len(window) < 2:
        return None
    return lib.history_from_rows(symbol, window, str(window[-1].trade_date),
                                 raw_rows=raw_bars, lookback=lookback)


class Alpha101FamilyTiltOverlay:
    """Apply the family tilt to whatever the book already holds."""

    cash_budget_active = False
    name = 'alpha101-tilt'

    def __init__(self, *, budget=DEFAULT_BUDGET, alphas=lib.REGISTERED, lookback=DEFAULT_LOOKBACK,
                 max_weight=DEFAULT_MAX_WEIGHT, version=VERSION, raw=None):
        self.budget = D(str(budget))
        self.alphas = tuple(alphas)
        self.lookback = int(lookback)
        self.max_weight = D(str(max_weight))
        self.version = version
        self.raw = raw
        self.diagnostics = {}

    def values_for(self, held, context):
        """Each alpha's value for the held names, computed from bars strictly before the decision."""
        per_alpha = {}
        for alpha in self.alphas:
            values = {}
            for symbol in held:
                bars = context.bars_by_symbol.get(symbol)
                if not bars:
                    continue
                window = history(symbol, bars, self.lookback, (self.raw or {}).get(symbol))
                if window is None:
                    continue
                value = lib.value(alpha, window)
                if value is not None:
                    values[symbol] = value
            per_alpha[alpha] = values
        return per_alpha

    def apply(self, targets, context):
        targets = list(targets)
        held = [t.symbol for t in targets if t.target_weight > 0]
        if len(held) < MIN_NAMES:
            self.diagnostics = dict(applied=False, reason='fewer than two held names')
            return targets
        scores = composite_scores(held, self.values_for(held, context))
        if not scores:
            self.diagnostics = dict(applied=False, reason='the held cross-section cannot be ranked')
            return targets
        weights = {t.symbol: t.target_weight for t in targets}
        tilts, diagnostics = tilt_vector(weights, scores, self.budget, self.max_weight)
        self.diagnostics = diagnostics
        if not tilts:
            return targets
        adjusted = []
        for target in targets:
            tilt = tilts.get(target.symbol)
            if tilt is None or tilt == 0:
                adjusted.append(target)
                continue
            moved = target.target_weight + tilt
            if moved < 0 <= moved + D('1e-24'):
                moved = D('0')
            ceiling = max(target.target_weight, self.max_weight)
            if moved > ceiling and moved < ceiling + D('1e-24'):
                moved = ceiling
            if moved < 0 or moved > ceiling:
                raise ValueError('Tilt breached the zero floor or an over-cap weight on ' + target.symbol)
            adjusted.append(target.model_copy(update={
                'target_weight': moved,
                'rationale': target.rationale + f' Alpha101 family tilt {self.version}.'}))
        gross_before = sum((t.target_weight for t in targets), D(0))
        gross_after = sum((t.target_weight for t in adjusted), D(0))
        if abs(gross_after - gross_before) > D('1e-12'):
            raise ValueError('Tilt changed the gross book, which the fallback budget protects')
        return adjusted
