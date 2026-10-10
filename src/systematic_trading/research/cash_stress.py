"""Finite, cash-funded stress sleeves; no production strategy or broker mutation."""
from decimal import Decimal as D
from statistics import fmean

from systematic_trading.signals.trend import _rank_metric

RULES={
    'R0':dict(reserve=0,entry='none',basket='market'),
    'R1':dict(reserve=0,entry='scheduled',basket='market'),
    'R2':dict(reserve=0,entry='stress',basket='market'),
    'R3':dict(reserve=0,entry='confirmed',basket='market'),
    'L2':dict(reserve=0,entry='stress',basket='losers'),
    'L3':dict(reserve=0,entry='confirmed',basket='losers'),
    'W2':dict(reserve=0,entry='stress',basket='winners'),
    'W3':dict(reserve=0,entry='confirmed',basket='winners'),
    **{f'B{n}_{kind}':dict(reserve=n/100,entry=entry,basket='market')
       for n in (10,20) for kind,entry in [('fixed','none'),('stress','stress'),('confirm','confirmed')]},
}
COMPARISONS=[('R2','R1'),('R3','R2'),('R1','R0'),('R2','R0'),('R3','R0'),
    ('L2','R2'),('L3','R3'),('L2','W2'),('L3','W3'),('W2','R2'),('W3','R3')]
for n in (10,20):
    COMPARISONS += [(f'B{n}_fixed','R0'),(f'B{n}_stress',f'B{n}_fixed'),
        (f'B{n}_confirm',f'B{n}_fixed'),(f'B{n}_confirm',f'B{n}_stress'),
        (f'B{n}_stress','R0'),(f'B{n}_confirm','R0')]


def signal_rows(bars,parent):
    """Monthly stress state and ranking from completed adjusted closes only."""
    symbols=sorted(bars);days=[r['trade_date'] for r in bars['SPY']]
    if any([r['trade_date'] for r in v]!=days for v in bars.values()):raise ValueError('Unaligned stress histories')
    out={};episode=0;active=False;armed=True;anchor=None;age=0;max_level=0;start=None
    for day in sorted(parent):
        i=days.index(day);history={s:[D(r['close']) for r in v[:i]] for s,v in bars.items()}
        if i<253:raise ValueError('Incomplete stress/ranking warmup')
        spy=history['SPY'];close=spy[-1];peak=max(spy[-252:]);window_dd=close/peak-1
        exit_reason=None
        if not armed and anchor is not None and close>=anchor*D('.95'):armed=True
        if active:
            age+=1
            if close>=anchor*D('.95') or age>=12:
                exit_reason='recovered_to_95pct_anchor' if close>=anchor*D('.95') else '12_month_limit'
                active=False;armed=exit_reason!='12_month_limit'
        elif armed and window_dd<=D('-.10'):
            episode+=1;anchor=peak;active=True;armed=False;age=0;max_level=0;start=day
        dd=close/anchor-1 if active else window_dd
        if active:max_level=max(max_level,sum(dd<=threshold for threshold in (D('-.10'),D('-.20'),D('-.30'))))
        ranks={h:_rank_metric({s:v[-1]/v[-h-1]-1 for s,v in history.items()}) for h in (63,126,252)}
        score={s:D('.20')*ranks[63][s]+D('.35')*ranks[126][s]+D('.45')*ranks[252][s] for s in symbols}
        losers=sorted(symbols,key=lambda s:(score[s],s))[:3]
        winners=sorted(symbols,key=lambda s:(-score[s],s))[:3]
        out[day]=dict(known_through=days[i-1],episode_id=episode,active=active,episode_start=start,age_months=age,
            peak_window=252,anchor=str(anchor) if anchor else None,drawdown=str(dd),window_drawdown=str(window_dd),
            max_level=max_level if active else 0,exit_reason=exit_reason,
            confirmed=close>D(str(fmean(spy[-63:]))) and close>spy[-22],
            scores={s:str(v) for s,v in score.items()},losers=losers,winners=winners)
    return out


class StressPolicy:
    """Virtual ownership partitions actual holdings; never tops up a spent tranche.

    All investment and cash accounting is performed by the shared engine. The
    fractional sleeve quantities are an attribution partition, not extra assets.
    """
    def __init__(self,arm,parking,signals,parent,quotes,risk_weight=None):
        self.arm,self.parking,self.signals,self.parent,self.quotes=arm,parking,signals,parent,quotes
        self.rule=RULES.get(arm,dict(reserve=0,entry='none',basket='market'))
        self.risk_weight=risk_weight
        self.quantities={s:D(0) for s in quotes};self.desired=dict(self.quantities)
        self.cycle=None;self.budget=None;self.levels=0;self.basket=[];self.scheduled_age=0;self.serial=0
        self.events={};self.pending=None

    def plan(self,signal_day,trade_day,positions,cash):
        refs={s:D(q[signal_day]['reference']) for s,q in self.quotes.items()}
        nav=cash+sum(D(q)*refs[s] for s,q in positions.items())
        if nav<=0:raise ValueError('Nonpositive cash-study NAV')
        if self.arm=='XRM':base={'URTH':D(str(self.risk_weight))}
        else:
            scale=1-D(str(self.rule['reserve']))
            base={t['symbol']:D(t['target_weight'])*scale for t in self.parent[signal_day]['targets']}
        entry=self.rule['entry'];sig=self.signals[signal_day]
        capacity=max(D(0),(D('.98')-sum(base.values()))*nav)
        sleeve_limit=D(str(self.rule['reserve'])) if self.rule['reserve'] else D('.20')
        capacity=min(capacity,sleeve_limit*nav)
        old_cycle=self.cycle;exit_reason=None
        if entry=='scheduled':
            if self.cycle is not None:
                self.scheduled_age+=1
                if self.scheduled_age>=12:self.cycle=None;exit_reason='scheduled_12_month_limit'
            elif capacity>=D('.01')*nav:
                self.serial+=1;self.cycle='scheduled-'+str(self.serial);self.scheduled_age=0
            level=min(3,self.scheduled_age+1) if self.cycle else 0
        elif entry in ('stress','confirmed'):
            self.cycle=sig['episode_id'] if sig['active'] else None
            level=sig['max_level'] if sig['active'] and (entry=='stress' or sig['confirmed']) else 0
            if old_cycle and not self.cycle:exit_reason=sig['exit_reason'] or 'episode_closed'
        else:self.cycle=None;level=0
        if self.cycle!=old_cycle:
            self.budget=None;self.levels=0;self.basket=[]
        desired=dict(self.quantities) if self.cycle and self.cycle==old_cycle else {s:D(0) for s in self.quotes}
        # Parent re-entry has priority. Trim to current funding/concentration
        # limits, but do not recycle reductions into new purchases this cycle.
        def constrain(q):
            total=sum(q[s]*refs[s] for s in q)
            if total>capacity:
                q={s:v*capacity/total for s,v in q.items()}
            for s in q:
                room=max(D(0),max(D('.45'),base.get(s,D(0)))-base.get(s,D(0)))*nav
                q[s]=min(q[s],room/refs[s])
            return q
        desired=constrain(desired)
        first_budget=False;tranches=0;requested=D(0)
        if self.cycle and self.budget is None and capacity>=D('.01')*nav:
            self.budget=capacity;first_budget=True
        if level>self.levels and capacity>0 and self.budget is not None:
            if not self.basket:self.basket=['SPY'] if self.rule['basket']=='market' else list(sig[self.rule['basket']])
            tranches=level-self.levels;requested=self.budget*D(tranches)/3
            for s in self.basket:desired[s]+=requested/D(len(self.basket))/refs[s]
            desired=constrain(desired)
            self.levels=level # clipped/unfilled portions stay cash; never re-arm a spent stage
        stress={s:q*refs[s]/nav for s,q in desired.items()}
        targets={s:base.get(s,D(0))+stress[s] for s in self.quotes}
        if self.parking=='BIL':targets['BIL']=min(D('.45'),max(D(0),D('.98')-sum(targets.values())))
        if sum(targets.values())>D('.980000000000001'):raise ValueError('Stress budget exceeds cash floor')
        if any(w<0 for w in targets.values()):raise ValueError('Negative stress target')
        if any(q>self.quantities[s]+D('1e-18') for s,q in desired.items()) and tranches==0:
            raise ValueError('A spent tranche was topped up')
        self.desired=desired
        self.pending=dict(signal_session=signal_day,known_through=sig['known_through'],trade_day=trade_day,
            cycle=self.cycle,episode_id=sig['episode_id'],active_stress=sig['active'],exit_reason=exit_reason,
            basket=list(self.basket),levels_spent=self.levels,new_tranches=tranches,requested_usd=str(requested),
            cycle_budget_usd=str(self.budget) if self.budget is not None else None,first_budget=first_budget,
            signal_nav=str(nav),drawdown=sig['drawdown'],confirmed=sig['confirmed'],
            desired_stress_weight=str(sum(stress.values())),parent_gross=str(sum(base.values())),
            reserve_fraction=self.rule['reserve'],parking=self.parking)
        return targets

    def filled(self,day,before,after,prices,fees):
        old=dict(self.quantities);actual={s:min(q,D(after.get(s,0))) for s,q in self.desired.items()}
        allocated_fees={}
        for s in actual:
            change=actual[s]-old[s];total_change=D(after.get(s,0)-before.get(s,0));core_change=total_change-change
            denominator=abs(change)+abs(core_change)
            allocated_fees[s]=D(fees.get(s,0))*abs(change)/denominator if denominator else D(0)
        self.quantities=actual
        event=dict(self.pending,quantities={s:str(q) for s,q in actual.items()},
            changes={s:str(actual[s]-old[s]) for s in actual},fees={s:str(v) for s,v in allocated_fees.items()},
            execution_prices={s:str(v) for s,v in prices.items()})
        event['phase']='replenishment' if event['exit_reason'] else 'deployed' if any(actual.values()) else 'stress_waiting' if event['active_stress'] else 'peaceful_waiting'
        self.events[day]=event
