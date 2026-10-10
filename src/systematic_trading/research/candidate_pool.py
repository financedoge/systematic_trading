"""Finite candidate-pool experiment; production strategy definitions stay unchanged."""
from dataclasses import replace
from decimal import Decimal as D
from math import isfinite
from statistics import stdev

from systematic_trading.signals.trend import AssetPoolFilterOverlay, _rank_metric
from systematic_trading.research.flow_concentration import concentration_features, apply_concentration_targets

POLICIES = {
    'M0': 'Existing 63/126/252-session momentum; positive 252-session gate',
    'M1': 'Faster 21/63/126-session momentum; positive 126-session gate',
    'M2': 'Skip latest 21 sessions: 63–21/126–21/252–21; positive 252–21 gate',
    'M3': '63/126/252 returns divided by 63-session volatility; positive 252-session gate',
}


class CandidatePool(AssetPoolFilterOverlay):
    def __init__(self, parent, policy):
        if policy not in POLICIES:
            raise ValueError('Unregistered momentum policy')
        self.__dict__.update(vars(parent))
        self.policy = policy
        if policy == 'M1':
            self.short_momentum_bars, self.medium_momentum_bars, self.long_momentum_bars = 21, 63, 126
        self.observation = None

    def _selection_scores(self, targets, context):
        scores = super()._selection_scores(targets, context)
        if scores is None or self.policy in ('M0', 'M1'):
            return scores
        metrics = {}
        for symbol, score in scores.items():
            rows = context.bars_by_symbol[symbol]
            raw = dict(score.raw_metrics)
            if self.policy == 'M2':
                for key, horizon in [('shortMomentum',63),('mediumMomentum',126),('longMomentum',252)]:
                    raw[key] = rows[-22].close / rows[-horizon-1].close - 1
                scale = D(1)
            else:
                prices = [float(r.close) for r in rows[-64:]]
                scale = D(str(stdev([b/a-1 for a,b in zip(prices,prices[1:])])))
                if not scale.is_finite() or scale <= 0:
                    raise ValueError('Risk-normalized momentum requires positive volatility')
            metrics[symbol] = (raw, scale)
        rank = {key: _rank_metric({s: raw[key]/scale for s,(raw,scale) in metrics.items()})
                for key in ('shortMomentum','mediumMomentum','longMomentum')}
        result = {}
        for s, score in scores.items():
            trend = sum(w*rank[key][s] for w,key in [(D('.20'),'shortMomentum'),(D('.35'),'mediumMomentum'),(D('.45'),'longMomentum')])
            volume = score.components['volume']
            result[s] = replace(score, total=(self.trend_weight*trend+self.volume_weight*volume)/(self.trend_weight+self.volume_weight),
                components=dict(trend=trend,volume=volume),raw_metrics=metrics[s][0])
        return result

    def apply(self, targets, context):
        scores = self._selection_scores(targets,context)
        output = super().apply(targets,context)
        eligible = sorted((s for s,v in scores.items() if v.raw_metrics['longMomentum'] > self.min_long_momentum),
                          key=lambda s:(-scores[s].total,s))
        self.observation = dict(eligible=eligible, selected=[t.symbol for t in output if t.target_weight>0],
            fallback=self.cash_budget_active,
            scores={s:dict(total=str(v.total),momentum={k:str(x) for k,x in v.raw_metrics.items()}) for s,v in scores.items()})
        return output


def audited_bar(row, *, raw=False):
    """Require supported raw volume and explicit adjusted/raw price columns. Never fill."""
    prefix = 'raw_' if raw else 'adjusted_'
    keys = [prefix+k for k in ('open','high','low','close')] + ['raw_volume']
    if any(row.get(k) is None or not isfinite(float(row[k])) or float(row[k])<=0 for k in keys):
        raise ValueError('Unsupported audited observation: '+str((row.get('symbol'),row.get('trade_date'))))
    volume = D(str(row['raw_volume']))
    if volume != volume.to_integral_value():
        raise ValueError('Fractional raw volume unsupported; no rounding')
    return dict(symbol=row['symbol'],trade_date=row['trade_date'],
        **{k:str(row[prefix+k]) for k in ('open','high','low','close')},volume=int(volume))


def audited_activity_features(adjusted, raw, spec):
    if spec.hurst_min is not None:
        raise ValueError('This finite contract does not register a Hurst variant')
    if set(adjusted)!=set(raw) or any([r.trade_date for r in adjusted[s]] != [r.trade_date for r in raw[s]] for s in adjusted):
        raise ValueError('Adjusted/raw calendars differ')
    values = concentration_features(raw,spec)
    # Raw dollar turnover; adjusted-price direction avoids mechanical split jumps.
    for s, v in values.items():
        bars=adjusted[s];recent=bars[-20:];previous=bars[-21:-1]
        signed=sum(r.volume*(1 if r.close>p.close else -1 if r.close<p.close else 0)
                   for r,p in zip(recent,previous))/sum(r.volume for r in recent)
        momentum=float(bars[-1].close/bars[-21].close-1)
        confirm=not spec.directional_confirmation or (v['velocity']>0 and momentum>0 and signed>0)
        v.update(momentum_20=momentum,signed_volume_20=signed,
                 signal=1 if v['z']>spec.threshold and confirm else -1 if v['z'] < -spec.threshold else 0)
    return values


class AuditedActivity:
    name = 'audited-raw-dollar-activity-adjusted-direction-v1'
    def __init__(self, spec, raw):
        self.spec,self.raw,self.state = spec,raw,{}

    def apply(self, targets, context):
        if self.raw is None:
            raise ValueError('Audited raw activity histories must be explicitly bound')
        raw={s:[r for r in rows if r.trade_date<context.as_of] for s,rows in self.raw.items()}
        return apply_concentration_targets(list(targets),audited_activity_features(context.bars_by_symbol,raw,self.spec),self.spec,self.state)
