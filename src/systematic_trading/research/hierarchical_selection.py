"""Hierarchical selection: qualify asset classes, choose the top K, then select inside them.

This extends the existing balanced-group overlay instead of reimplementing it. The
per-class ranking, the budget split, the weight arithmetic and the "never force an
ineligible asset" contract are the parent's own code; this class decides only **which
classes receive a budget on each decision**.

Frozen rule (see ``hierarchical_construction_study`` for the registered protocol):

* a class qualifies only if at least one member passes the positive long-momentum gate;
* qualifying classes are scored by the mean of their two best eligible members;
* the top ``top_classes`` qualify for an equal share of the incoming gross, and the
  rest receive a zero budget;
* a decision with no qualifying class is entirely cash.
"""
from decimal import Decimal as D

from systematic_trading.signals.balanced import BalancedAssetGroupOverlay


class HierarchicalSelection(BalancedAssetGroupOverlay):
    """Drop classes with no eligible member, rank the survivors, select inside the chosen ones."""

    def __init__(self, *, top_classes: int, **kwargs) -> None:
        super().__init__(**kwargs)
        if int(top_classes) < 1:
            raise ValueError('top_classes must be at least 1')
        self.top_classes = int(top_classes)
        self.observed = None

    def _class_score(self, values):
        ranked = sorted(values, reverse=True)[: self.top_n_per_sleeve]
        return sum(ranked) / D(len(ranked))

    def apply(self, targets, context):
        target_list = list(targets)
        scores = self._scores(target_list, context)
        if not scores:
            # not enough ranking history: inherit the parent's neutral behaviour
            self.observed = dict(chosen=[], qualifying=[], reason='insufficient ranking history', cash_only=False)
            return target_list
        eligible = {symbol: score for symbol, score in scores.items()
                    if score.long_momentum is not None and score.long_momentum > self.min_long_momentum}
        by_class: dict[str, list] = {}
        for symbol, score in eligible.items():
            sleeve = self.sleeve_by_symbol.get(symbol)
            if sleeve is not None:
                by_class.setdefault(sleeve, []).append(score.total)
        ranked = sorted(((self._class_score(values), sleeve) for sleeve, values in by_class.items()),
                        key=lambda item: (-item[0], item[1]))
        chosen = [sleeve for _, sleeve in ranked[: self.top_classes]]
        self.observed = dict(eligible=sorted(eligible), qualifying=sorted(by_class),
                             class_scores={sleeve: str(score) for score, sleeve in ranked},
                             chosen=sorted(chosen), excluded=sorted(set(by_class) - set(chosen)),
                             cash_only=not chosen)
        if not chosen:
            # every class is in a downtrend: hold cash rather than force representation
            return [target.model_copy(update=dict(
                target_weight=D(0),
                rationale=target.rationale + ' Hierarchical selection held cash: no asset class had an eligible '
                                             'member.')) for target in target_list]
        shared = D(1) / D(len(chosen))
        self.sleeve_budgets = {sleeve: (shared if sleeve in chosen else D(0)) for sleeve in self.sleeve_budgets}
        return super().apply(targets, context)
