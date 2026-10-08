"""Versioned research target controls, using the shared TargetOverlay contract.

No recipe is automatically registered, monitored or authorized for execution.
"""
from dataclasses import dataclass
from decimal import Decimal as D
from systematic_trading.signals.trend import AssetPoolFilterOverlay


class ForecastRankPool(AssetPoolFilterOverlay):
    """Replace only pool ordering; preserve the validated parent's eligibility,
    fallback and sizing implementation. Forecasts must be bound causally first.
    """
    def __init__(self, pool, forecasts):
        self.__dict__.update(vars(pool))
        self.forecasts = {s:D(str(v)) for s,v in forecasts.items()}
        self.name = f'xgboost-pool-ranking-top{self.top_n}-v1'

    def _selection_scores(self, targets, context):
        from dataclasses import replace
        if set(self.forecasts)!={t.symbol for t in targets} or any(not f.is_finite() for f in self.forecasts.values()):
            raise ValueError('Complete finite forecasts are required for selection')
        scores = super()._selection_scores(targets,context)
        if scores is None:
            raise ValueError('Complete momentum eligibility inputs are required')
        return {s:replace(score,total=self.forecasts[s],components={'xgboostForecast':self.forecasts[s]})
                for s,score in scores.items()}


def gross(targets):
    if not targets or len({t.symbol for t in targets}) != len(targets):
        raise ValueError('A complete unique target universe is required')
    weights = [t.target_weight for t in targets]
    if any(not w.is_finite() or w < 0 for w in weights):
        raise ValueError('Finite nonnegative weights are required')
    total = sum(weights, D(0))
    if total > 1 + D('1e-20'):
        raise ValueError('Unlevered target budget exceeded')
    return total


@dataclass(frozen=True)
class ConstantExposureOverlay:
    scale: D
    name: str = 'construction-constant-exposure-v1'

    def __post_init__(self):
        if not self.scale.is_finite() or not 0 <= self.scale <= 1:
            raise ValueError('Exposure scale must be finite and within [0, 1]')

    def apply(self, targets, context):
        gross(targets)
        return [t.model_copy(update=dict(target_weight=t.target_weight*self.scale,
            rationale=t.rationale+' Fixed research exposure scale '+str(self.scale)+'.')) for t in targets]


@dataclass(frozen=True)
class FinalWeightCapOverlay:
    cap: D = D('.45')
    name: str = 'construction-final-target-cap-v1'

    def __post_init__(self):
        if not self.cap.is_finite() or not 0 < self.cap <= 1:
            raise ValueError('Final target cap must be finite and within (0, 1]')

    def apply(self, targets, context):
        gross(targets)
        return [t.model_copy(update=dict(target_weight=min(t.target_weight, self.cap),
            rationale=t.rationale+' Final target cap '+str(self.cap)+'; excess remains cash.')) for t in targets]


def match_gross(targets, reference):
    """Keep F0 composition while matching the same-date F3 invested budget."""
    base, wanted = gross(targets), gross(reference)
    if {t.symbol for t in targets} != {t.symbol for t in reference}:
        raise ValueError('Matched controls need the same universe')
    if wanted > base + D('1e-20'):
        raise ValueError('Matching would require increased exposure')
    scale = min(D(1), wanted/base) if base else D(0)
    return ConstantExposureOverlay(scale).apply(targets, None)


def calibrate_exposure(parent, candidate, *, evaluation_start='2021-01-04'):
    """Equally weighted monthly decision budgets, ending before evaluation.

    No evaluation returns, budgets or decision records enter calibration.
    """
    from systematic_trading.domain.portfolio import AllocationTarget
    days = sorted(d for d in parent if '2016-01-04' <= d < evaluation_start)
    if not days or days != sorted(d for d in candidate if '2016-01-04' <= d < evaluation_start):
        raise ValueError('Calibration calendars must be nonempty and identical')
    totals = []
    for source in (parent, candidate):
        value = D(0)
        for day in days:
            if source[day]['known_through'] >= day:
                raise ValueError('Calibration contains unavailable information')
            value += gross([AllocationTarget.model_validate(t) for t in source[day]['targets']])
        totals.append(value/len(days))
    if totals[0] <= 0 or totals[1] > totals[0]:
        raise ValueError('Invalid calibration exposure budget')
    return dict(scale=str(totals[1]/totals[0]), decisions=len(days), first=days[0], last=days[-1],
                evaluation_start=evaluation_start, parent_mean_gross=str(totals[0]), candidate_mean_gross=str(totals[1]),
                method='Ratio of mean monthly F3/F0 target gross, using only 2016–2020 decisions; no leverage.')
