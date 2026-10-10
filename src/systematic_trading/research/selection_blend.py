"""Finite full-pool rank blends at the existing M1 selection boundary."""
from dataclasses import replace
from decimal import Decimal as D, ROUND_DOWN
import math

from systematic_trading.research.candidate_pool import CandidatePool
from systematic_trading.signals.trend import _rank_metric


BLENDS = dict(X25=(3,1,0),X50=(1,1,0),R25=(3,0,1),R50=(1,0,1),
              MXR=(2,1,1),EQ=(1,1,1))
MAIN = {'X25':dict(blend='X25',group=None), 'X50':dict(blend='X50',group=None)}
for prefix,group in [('C','context'),('F','financial')]:
    for code in ('R25','R50','MXR','EQ'):
        MAIN[prefix+code] = dict(blend=code,group=group)
MEAN = {a+'M':dict(v,mean_only=True) for a,v in MAIN.items() if v['group']}
SPECIAL = {
    'NX':dict(blend=None,group=None,remove_xgb=True),
    'CEQNX':dict(MAIN['CEQ'],remove_xgb=True),
    'FEQNX':dict(MAIN['FEQ'],remove_xgb=True),
    'CEQG':dict(MAIN['CEQ'],match_gross=True),
    'FEQG':dict(MAIN['FEQ'],match_gross=True),
}
VARIANTS = {**MAIN,**MEAN,**SPECIAL}
CONTROLS = ('M1','CP','CR','FR','F3','RP14','URTH')
ARMS = (*CONTROLS,*VARIANTS)
COMPARISONS = list(dict.fromkeys(
    [(a,'CP') for a in (*MAIN,*MEAN)]
    +[(a,a+'M') for a,v in MAIN.items() if v['group']]
    +[(a,'CR' if v['group']=='context' else 'FR') for a,v in MAIN.items() if v['group']]
    +[(a,b) for a in ('CEQ','FEQ') for b in ('X50', 'CR50' if a=='CEQ' else 'FR50')]
    +[('NX','CP'),('CEQNX','CEQ'),('FEQNX','FEQ'),('CEQNX','NX'),('FEQNX','NX'),
      ('CEQG','CEQ'),('FEQG','FEQ'),('CEQG','CP'),('FEQG','CP'),('CP','M1'),('CR','CP'),('FR','CP')]))
RATIO_COMPARISONS = [(a,'CP') for a in MAIN]+[(a,a+'M') for a,v in MAIN.items() if v['group']]+[
    ('CEQNX','NX'),('FEQNX','NX'),('CEQG','CP'),('FEQG','CP'),('CP','M1')]


class SelectionBlend(CandidatePool):
    """Replace only ranking totals; eligibility and fallback use original features."""
    def __init__(self,parent,recipe,xgb,ridge):
        super().__init__(parent,'M1')
        self.recipe,self.xgb,self.ridge=recipe,xgb,ridge
        self.rank_table=None
        self.abstained=False

    def _selection_scores(self,targets,context):
        scores=super()._selection_scores(targets,context)
        blend=self.recipe.get('blend')
        if blend is None:
            return scores
        weights=BLENDS[blend]
        if set(self.xgb)!=set(scores) or any(not math.isfinite(float(v)) for v in self.xgb.values()):
            raise ValueError('Incomplete XGBoost prediction universe')
        self.abstained=bool(weights[2] and not self.ridge['ready'])
        mr=_rank_metric({s:v.total for s,v in scores.items()})
        xr=_rank_metric({s:D(str(v)) for s,v in self.xgb.items()})
        rr=None
        if weights[2] and not self.abstained:
            field='mean_return' if self.recipe.get('mean_only') else 'linear_forecast'
            if set(self.ridge['models'])!=set(scores):
                raise ValueError('Incomplete ridge prediction universe')
            values={s:D(str(v[field])) for s,v in self.ridge['models'].items()}
            if any(not v.is_finite() for v in values.values()):
                raise ValueError('Nonfinite ridge prediction')
            rr=_rank_metric(values)
        total=D(sum(weights))
        self.rank_table={s:dict(momentum=str(mr[s]),xgb=str(xr[s]),ridge=str(rr[s]) if rr else None,
            combined=str(scores[s].total if self.abstained else
                         ((weights[0]*mr[s]+weights[1]*xr[s]+weights[2]*(rr[s] if rr else D(0)))/total).quantize(D('1e-18')))) for s in scores}
        if self.abstained:
            return scores  # whole selection falls back to original M1, never filled macro data
        return {s:replace(v,total=D(self.rank_table[s]['combined'])) for s,v in scores.items()}


def match_gross(targets,total,cap=D('.45')):
    """Same positive membership, proportional weights, cap; disclose capacity gap."""
    positive={t.symbol:t.target_weight for t in targets if t.target_weight>0}
    attainable=min(total,cap*len(positive))
    remaining=attainable
    assigned={}
    while positive:
        denom=sum(positive.values(),D(0))
        proposed={s:remaining*w/denom for s,w in positive.items()}
        binding=[s for s,w in proposed.items() if w>cap]
        if not binding:
            assigned.update(proposed)
            break
        for s in binding:
            assigned[s]=cap
            remaining-=cap
            del positive[s]
    assigned={s:w.quantize(D('1e-24'),rounding=ROUND_DOWN) for s,w in assigned.items()}
    residual=attainable-sum(assigned.values(),D(0))
    if residual:
        eligible=sorted(s for s,w in assigned.items() if w+residual<=cap)
        if not eligible:
            raise ValueError('Cannot reconcile matched gross rounding')
        assigned[eligible[0]]+=residual
    out=[t.model_copy(update=dict(target_weight=assigned.get(t.symbol,D(0)),
         rationale=t.rationale+' Frozen CP gross-budget control; positive membership preserved.')) for t in targets]
    return out,dict(requested=str(total),attainable=str(attainable),matched=attainable==total)
