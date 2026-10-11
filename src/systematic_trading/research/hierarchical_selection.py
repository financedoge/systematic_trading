"""Hierarchical selection: qualify asset classes, choose the top K, then select inside them.

This extends the existing balanced-group overlay instead of reimplementing it. The
per-class ranking, the budget split, the weight arithmetic and the "never force an
ineligible asset" contract are the parent's own code; this class decides only **which
classes receive a budget on each decision**.

Frozen rule (see ``hierarchical_construction_study`` for the registered protocol):

* a class qualifies only if at least one member passes the positive long-momentum gate;
* a qualifying class is scored by the mean of the members **it will actually hold**;
* the top ``top_classes`` qualify for an equal share of the incoming gross, and the
  rest receive a zero budget;
* a decision with no qualifying class is entirely cash.

**Which populations are used, registered explicitly (peer-review repair, 2026-10-11).**
Two populations meet here and they are deliberately different:

1. *Held members.* The members a chosen class holds are decided by the parent's own
   within-sleeve reranking (``BalancedAssetGroupOverlay._select_sleeve``): eligibility is
   the absolute 126-session gate measured per member, and among the members that pass,
   the top ``top_n_per_sleeve`` of the **within-sleeve** rank table are selected. That is
   the parent primitive's contract and this class does not re-rank it.
2. *Member scores.* The number attached to each of those held members is its score in the
   **global** cross-section rank table over all incoming targets. The global table is the
   only population in which a one-name class (``DBC``, ``GLD``) can be scored at all, and
   it keeps every class on one comparable scale.

The class score is therefore the mean of the global member scores of exactly the members
the within-sleeve rule will hold — not the mean of the globally top-ranked members, which
is what the first version of this rule did and which could score names the rule did not
hold. Before the top-K choice, the class's own selection is computed once and reused, so
the score and the holdings cannot drift apart.
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

    def _class_score(self, member_scores):
        """Mean of the member scores of exactly the members the class would hold.

        ``member_scores`` is the global-table score of each held member, one entry per
        member the parent's own within-sleeve selection picked. An empty selection has no
        score and the class does not qualify.
        """
        values = list(member_scores)
        if not values:
            return None
        return sum(values, D(0)) / D(len(values))

    def _gate_passes(self, score):
        return (not self.require_positive_long_momentum
                or (score.long_momentum is not None and score.long_momentum > self.min_long_momentum))

    def apply(self, targets, context):
        target_list = list(targets)
        scores = self._scores(target_list, context)
        if not scores:
            # not enough ranking history: inherit the parent's neutral behaviour
            self.observed = dict(chosen=[], qualifying=[], reason='insufficient ranking history', cash_only=False)
            return target_list
        by_class = {}
        for target in target_list:
            sleeve = self.sleeve_by_symbol.get(target.symbol)
            if sleeve is None or sleeve not in self.sleeve_budgets:
                continue
            by_class.setdefault(sleeve, []).append(target)
        selections, class_members = {}, {}
        for sleeve, sleeve_targets in by_class.items():
            # One selection pass, reused for the class score and (deterministically) by the
            # parent's weight pass below: the scored population is the held population.
            selection = self._select_sleeve(sleeve_targets, context)
            selections[sleeve] = selection
            held = [target.symbol for target in selection.selected]
            if not held:
                continue
            class_members[sleeve] = sorted(held)
        class_scores = {sleeve: self._class_score([scores[symbol].total for symbol in members])
                        for sleeve, members in class_members.items()}
        ranked = sorted(((score, sleeve) for sleeve, score in class_scores.items()),
                        key=lambda item: (-item[0], item[1]))
        chosen = [sleeve for _, sleeve in ranked[: self.top_classes]]
        self.observed = dict(
            eligible=sorted(symbol for symbol, score in scores.items() if self._gate_passes(score)),
            qualifying=sorted(class_members),
            class_scores={sleeve: str(score) for score, sleeve in ranked},
            class_members={sleeve: class_members[sleeve] for _, sleeve in ranked},
            unchosen_reasons={sleeve: selections[sleeve].reason for sleeve in by_class
                              if not selections[sleeve].selected},
            chosen=sorted(chosen), excluded=sorted(set(class_members) - set(chosen)),
            cash_only=not chosen)
        if not chosen:
            # every class is in a downtrend: hold cash rather than force representation
            return [target.model_copy(update=dict(
                target_weight=D(0),
                rationale=target.rationale + ' Hierarchical selection held cash: no asset class had an eligible '
                                             'member.')) for target in target_list]
        shared = D(1) / D(len(chosen))
        self.sleeve_budgets = {sleeve: (shared if sleeve in chosen else D(0)) for sleeve in self.sleeve_budgets}
        result = super().apply(targets, context)
        # A class that failed to qualify says why: it was dropped because no member passed
        # the absolute-momentum gate, not because the ranking placed it low.
        denied = {target.symbol: f' Hierarchical selection did not qualify the {sleeve} class: '
                                 f'{selections[sleeve].reason}.'
                  for sleeve, sleeve_targets in by_class.items() if not selections[sleeve].selected
                  for target in sleeve_targets}
        if not denied:
            return result
        return [target.model_copy(update=dict(rationale=target.rationale + denied[target.symbol]))
                if target.symbol in denied else target for target in result]
