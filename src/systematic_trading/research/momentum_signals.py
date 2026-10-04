"""Causal research horizon scores and explicitly replayable membership state."""
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal as D
import math

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.signals.base import SignalContext
from systematic_trading.signals.trend import AssetPoolFilterOverlay, _rank_metric

EQUITIES = ('SPY', 'VGK', 'EWJ', 'EWH', 'EWY', 'MCHI')


def horizon_rank(histories, near, far):
    if not 0 <= near < far or any(len(b) <= far for b in histories.values()):
        raise ValueError('Invalid horizon or incomplete momentum history')
    return _rank_metric({s: b[-1-near].close/b[-1-far].close-1 for s,b in histories.items()})


def market_regime(histories):
    if any(len(histories[s]) < 127 for s in EQUITIES):
        raise ValueError('Regime requires 126 completed returns')
    returns = [sum(float(histories[s][i].close/histories[s][i-1].close-1) for s in EQUITIES)/6 for i in range(-126, 0)]
    n = len(returns)
    mean = sum(returns)/n
    m2 = sum((r-mean)**2 for r in returns)/n
    skew = math.sqrt(n*(n-1))/(n-2) * (sum((r-mean)**3 for r in returns)/n)/m2**1.5 if m2 > 1e-24 else 0.
    trend = math.prod(1+r for r in returns)-1
    return dict(trend=trend, skew=skew, trend_state='up' if trend>0 else 'down' if trend<0 else 'neutral',
                skew_state='right' if skew>.25 else 'left' if skew<-.25 else 'neutral')


def mix(a, b, weight):
    weight = D(str(weight))
    return {s: weight*a[s]+(1-weight)*b[s] for s in a}


def feature_frame(histories, as_of):
    context = SignalContext(as_of=date.fromisoformat(str(as_of)), instruments={}, bars_by_symbol=histories, trade_dates=[])
    histories = context.bars_by_symbol
    dates = [[b.trade_date for b in v] for v in histories.values()]
    if not dates or any(ds != dates[0] for ds in dates) or len(dates[0]) < 253:
        raise ValueError('Pool requires synchronous, complete histories')
    targets = [AllocationTarget(symbol=s, sleeve='momentum-research', target_weight=D(1)/len(histories), rationale='research features') for s in histories]
    parent = AssetPoolFilterOverlay(min_selected=4)._selection_scores(targets, context)
    if parent is None or set(parent) != set(histories):
        raise ValueError('Incomplete parent score')
    a = {f'A{i}': horizon_rank(histories, near, far) for i,(near,far) in enumerate(((0,5),(0,10),(0,21),(21,42),(21,63)),1)}
    a['A6'], a['A7'] = mix(a['A1'],a['A2'],.5), mix(a['A4'],a['A5'],.5)
    a['A8'] = mix(a['A6'],a['A7'],.5)
    regime = market_regime(histories)
    weights = dict(B1=.75 if regime['trend_state']=='up' else .25 if regime['trend_state']=='down' else .5,
                   B3=.75 if regime['skew_state']=='right' else .25 if regime['skew_state']=='left' else .5)
    weights.update(B2=1-weights['B1'], B4=1-weights['B3'])
    a.update({b: mix(a['A6'],a['A7'],w) for b,w in weights.items()})
    scores = {r: {s: str(D('.75')*v[s]+D('.25')*parent[s].components['volume']) for s in v} for r,v in a.items()}
    scores['parent'] = {s: str(v.total) for s,v in parent.items()}
    return dict(known_through=str(dates[0][-1]), scores=scores,
        horizons={k:{s:str(v) for s,v in values.items()} for k,values in a.items() if k.startswith('A')},
        eligible=sorted(s for s,v in parent.items() if v.raw_metrics['longMomentum']>0), regime=regime, short_weights=weights)


@dataclass
class Membership:
    recipe: str
    selected: set = field(default_factory=set)
    inside: dict = field(default_factory=dict)
    outside: dict = field(default_factory=dict)
    seeded: bool = False
    last_day: str | None = None

    def update(self, frame, scheduled):
        day = frame['known_through']
        if self.last_day is not None and day <= self.last_day:
            raise ValueError('Membership must advance once per completed session')
        self.last_day = day
        q = {s:D(v) for s,v in frame['scores']['parent'].items()}
        ranked = sorted(frame['eligible'], key=lambda s:(-q[s],s))
        if len(ranked)<4:
            self.selected.clear(); self.inside.clear(); self.outside.clear(); self.seeded=False
            return None, dict(fallback=True, desired_count=len(ranked), selected_count=None, floor_overrides=[], seed=False)
        desired = set(ranked if len(ranked)<6 else [s for s in ranked if q[s]>=q[ranked[5]]-D('.10')])
        for s in q:
            self.inside[s] = self.inside.get(s,0)+1 if s in desired else 0
            self.outside[s] = self.outside.get(s,0)+1 if s not in desired else 0
        diag = dict(fallback=False, desired_count=len(desired), floor_overrides=[], seed=False,
                    entry_streak=dict(self.inside), exit_streak=dict(self.outside))
        if not scheduled:
            return self.selected.copy(), diag
        before = self.selected.copy()
        if not self.seeded:
            self.selected = set(ranked[:6]); self.seeded=True; diag['seed']=True
        else:
            eligible = set(ranked)
            kept = {s for s in self.selected & eligible if s in desired or (self.recipe=='C1' and self.outside[s]<5)}
            entries = {s for s in desired if self.recipe!='C2' or self.inside[s]>=5}
            self.selected = kept | entries
            for s in ranked:
                if len(self.selected)>=min(6,len(ranked)):
                    break
                if s not in self.selected:
                    self.selected.add(s); diag['floor_overrides'].append(s)
        diag.update(selected_count=len(self.selected), entered=sorted(self.selected-before), exited=sorted(before-self.selected),
                    selected=sorted(self.selected), desired=sorted(desired))
        return self.selected.copy(), diag


class FixedSelection:
    name = 'registered-momentum-research-pool'
    def __init__(self, selected):
        self.selected = selected

    def apply(self, targets, context):
        if self.selected is None:
            return list(targets)
        gross = sum(t.target_weight for t in targets)
        selected_weight = sum(t.target_weight for t in targets if t.symbol in self.selected)
        if selected_weight<=0:
            raise ValueError('Selected pool has no investable weight')
        return [t.model_copy(update=dict(target_weight=t.target_weight*gross/selected_weight if t.symbol in self.selected else D(0),
                      rationale=t.rationale+'; registered research pool')) for t in targets]


def decision_sessions(days, start, cadence):
    if cadence not in ('monthly', 'weekly'):
        raise ValueError('Unregistered cadence')
    def period(day):
        return day[:7] if cadence=='monthly' else date.fromisoformat(day).isocalendar()[:2]
    return [d for i,d in enumerate(days) if i and d>=start and (d==start or period(d)!=period(days[i-1]))]
