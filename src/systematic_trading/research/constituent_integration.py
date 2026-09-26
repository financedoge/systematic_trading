"""Earlier, research-only integration with neutral missing inputs and bounded risk."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

from systematic_trading.research.constituent_signals import apply_constituent_targets
from systematic_trading.signals.decision_tree import DecisionTreeSignalOverlay, SimpleDecisionTreeModel
from systematic_trading.signals.library import compute_signal_features
from systematic_trading.signals.trend import AssetPoolFilterOverlay


def residual_inputs(price_features, base_forecast, constituent_row):
    return dict(mom_63=price_features['mom_63'], mom_126=price_features['mom_126'],
                base_forecast=base_forecast, breadth=constituent_row['values']['breadth'],
                signed_activity=constituent_row['values']['signed_activity'])


class EarlyAllocation:
    name = 'research-constituent-before-tree'

    def __init__(self, spec, score):
        self.spec, self.score = spec, score

    def apply(self, targets, context):
        return apply_constituent_targets(list(targets), self.score, self.spec)


class ConstituentSelection(AssetPoolFilterOverlay):
    def __init__(self, base, score, boost):
        self.__dict__.update(base.__dict__)
        self.constituent_score, self.boost = Decimal(str(score)), Decimal(str(boost))

    def _selection_scores(self, targets, context):
        scores = super()._selection_scores(targets, context)
        if scores is not None and 'SPY' in scores:
            old = scores['SPY']
            scores['SPY'] = replace(old, total=old.total+self.boost*self.constituent_score,
                                   components={**old.components, 'constituent': self.constituent_score})
        return scores


def choose_residual_model(features, known_through, kind):
    models = features.get('integration_models', {}).get(kind, {})
    available = [d for d in models if d <= known_through]
    if not available:
        return None
    record = models[max(available)]
    if record['fit_as_of'] != max(available) or record['max_label_end'] >= record['fit_as_of']:
        raise ValueError('Residual tree includes an unavailable training label')
    if record['training_samples'] < 18 or record['max_feature_date'] >= record['fit_as_of']:
        raise ValueError('Residual tree has insufficient or future training inputs')
    return SimpleDecisionTreeModel.from_dict(record['model'])


class ConstituentTree(DecisionTreeSignalOverlay):
    def __init__(self, base, residual_model, row):
        self.__dict__.update(base.__dict__)
        self.residual_model, self.constituent_row = residual_model, row

    def _forecasts(self, targets, context):
        forecasts = super()._forecasts(targets, context)
        if 'SPY' in forecasts:
            x = residual_inputs(compute_signal_features(symbol='SPY', context=context), forecasts['SPY'], self.constituent_row)
            correction = max(-.01, min(.01, .25*self.residual_model.predict(x)))
            forecasts['SPY'] += correction
        return forecasts


def integration_overlays(overlays, spec, score, features, known_through, row):
    modified = list(overlays)
    if spec.stage == 'early':
        modified.insert(1, EarlyAllocation(spec, score))
    elif spec.stage == 'selection':
        if not isinstance(modified[0], AssetPoolFilterOverlay):
            raise ValueError('Unexpected SOTA selection stage')
        modified[0] = ConstituentSelection(modified[0], score, spec.selection_boost)
    elif spec.stage == 'tree':
        model = choose_residual_model(features, known_through, spec.tree_inputs)
        if model is None:
            return None
        if not isinstance(modified[1], DecisionTreeSignalOverlay):
            raise ValueError('Unexpected SOTA tree stage')
        modified[1] = ConstituentTree(modified[1], model, row)
    else:
        raise ValueError('Unknown earlier integration stage')
    return modified


def constrain_to_base(base, proposed, cap):
    """Blend the earlier-stage candidate with SOTA under identical gross/active caps.

    Selection may introduce a small SPY position absent from SOTA. Blending can
    retain members from both baskets; it is not a hard six-ETF replacement.
    """
    bw = {t.symbol: t.target_weight for t in base}
    pw = {t.symbol: t.target_weight for t in proposed}
    if set(bw) != set(pw) or any(w < 0 or not w.is_finite() for w in pw.values()):
        raise ValueError('Invalid earlier-stage candidate universe/weights')
    gross, candidate_gross = sum(bw.values()), sum(pw.values())
    if not candidate_gross:
        return base
    pw = {s: w*gross/candidate_gross for s, w in pw.items()}
    delta = {s: pw[s]-bw[s] for s in bw}
    alpha = Decimal(1)
    bound = Decimal(str(cap))
    for symbol, change in delta.items():
        if change:
            alpha = min(alpha, bound/abs(change))
        if change > 0:
            alpha = min(alpha, max(Decimal('.45')-bw[symbol], Decimal(0))/change)
    return [t.model_copy(update=dict(target_weight=bw[t.symbol]+alpha*delta[t.symbol],
        rationale=t.rationale+'; research earlier-stage constituent integration, bounded blend')) for t in base]
