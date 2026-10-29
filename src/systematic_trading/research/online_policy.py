"""Discounted Bayesian policy learning; research only, no broker authority.

Separate posterior for each counterfactual policy, without treating correlated
policies as independent observations of one common reward. Underlying market
filter parameters are deliberately unchanged. Trading uses later-open fills.
"""
from __future__ import annotations

import numpy as np

from . import coupled_trends

VERSION = 'online-policy-v1'
ARMS = ('fixed', 'bayes', 'warning')
RHO = 2**(-1/126)


def grid(base):
    """Nine bounded policy parameter tuples; baseline is index zero."""
    pairs = [(0., 1.)] + [(d, s) for d in (-.1, 0., .1) for s in (.5, 1., 1.5)
                          if (d, s) != (0., 1.)]
    return [dict(base, entry=float(np.clip(base['entry']+d, .5, .9)),
                 exit=float(np.clip(base['exit']+.2*(s-1), .45, .9)),
                 tight=base['tight']*s, wide=base['wide']*s,
                 aligned_exit=float(np.clip(.85+.2*(s-1), .65, .95)),
                 entry_delta=d, protection_scale=s) for d, s in pairs]


def classification(cl, p):
    threshold = np.where(cl['aligned'] & p['context'], p['aligned_exit'], p['exit'])
    return dict(cl, parameters=p,
                eligible=(cl['fast_probability'][:, 2] >= p['entry']) & (cl['fast_slope'] > 0),
                fast_down=cl['fast_probability'][:, 0] >= threshold)


def reward(e, sigma, fee):
    r = e['exit_price']/e['entry']*(1-fee)/(1+fee)-1
    duration = max(1, e['exit_index']-e['entry_index'])
    return float(np.clip(r/(sigma*np.sqrt(duration)), -3, 3)), float(r)


def initialize(f, cl):
    """Training-only recency sufficient statistics, capped at four trades."""
    result=[]
    for p in grid(cl['parameters']):
        sim=coupled_trends.simulate(f, classification(cl,p))
        n=s=w=0.;count=0
        for e in sim['episodes']:
            if e['exit_index'] is None: continue
            y,r=reward(e,cl['sigma'],.0005)
            weight=RHO**(len(f.days)-1-e['exit_index'])
            n+=weight;s+=weight*y;w+=weight*(r>0);count+=1
        scale=min(1.,4/max(n,1e-12))
        result.append(dict(n=n*scale,s=s*scale,w=w*scale,closed=count))
    return result


class Posterior:
    """N(0,1/4) prior, unit-variance powered Gaussian reward likelihood.

    Beta(1,1) win-rate is a diagnostic, not multiplied into that likelihood.
    Effective counts are discounted weights, not independent sample sizes.
    """
    def __init__(self, initial):
        self.n=np.array([x['n'] for x in initial],float)
        self.s=np.array([x['s'] for x in initial],float)
        self.w=np.array([x['w'] for x in initial],float)
        self.fresh=np.zeros(len(initial),int)

    def discount(self, factor=RHO):
        if not 0 < factor <= 1: raise ValueError('Invalid discount')
        self.n*=factor;self.s*=factor;self.w*=factor

    def observe(self, j, y, win):
        if not np.isfinite(y) or abs(y)>3: raise ValueError('Invalid reward')
        self.n[j]+=1;self.s[j]+=y;self.w[j]+=bool(win);self.fresh[j]+=1

    def values(self):
        mean=self.s/(4+self.n);sd=1/np.sqrt(4+self.n)
        return mean,sd,(1+self.w)/(2+self.n)

    def choose(self, current):
        mean,sd,_=self.values();score=mean-.25*sd
        eligible=self.fresh>=1
        eligible[current]=True
        best=int(np.argmax(np.where(eligible,score,-np.inf)))
        return best if score[best]>score[current]+.05 else current


def simulate(f, cl, initial, calibration, *, start, arm='warning', cost_bp=5, delay=0,
             shadows=None):
    if arm not in ARMS or not isinstance(delay,int) or delay<0 or not 0<=cost_bp<10000:
        raise ValueError('Invalid arm/friction')
    if not 0<=start<len(f.days)-1 or cl['sigma']<=0: raise ValueError('Invalid data/start')
    parameters=grid(cl['parameters']);classes=[classification(cl,p) for p in parameters]
    n=len(f.days);fee=cost_bp/10000;lag=1+delay
    if shadows is None:
        shadows=[coupled_trends.simulate(f,c,start=start,cost_bp=cost_bp,delay=delay) for c in classes]
    updates={}
    for j,sim in enumerate(shadows):
        for e in sim['episodes']:
            if e['exit_index'] is not None:
                updates.setdefault(e['exit_index'],[]).append((j,*reward(e,cl['sigma'],fee)))
    posterior=Posterior(initial)
    sigma=calibration['winner_sigma']
    tau=max(sigma,2*fee,1e-6) if sigma is not None else None
    nav=np.full(n,np.nan);stop=nav.copy();mu=nav.copy();winprob=nav.copy();effective=nav.copy()
    desired=np.zeros(n);held=np.zeros(n,bool);exposure=np.zeros(n);policy=np.zeros(n,int)
    entry_threshold=nav.copy();distance=nav.copy();exit_threshold=nav.copy()
    cash=1.;units=0.;target=False;armed=True;selected=0;streak=0;last_alarm=-10000
    level=peak=entry_open=entry_risk=np.nan
    pending={};episodes=[];fills=[];events=[];episode=None
    for t in range(start,n):
        warnings=[]
        if t in pending:
            order=pending.pop(t)
            if order['side']=='buy':
                if units: raise ValueError('Overlapping buy')
                units=cash/(f.open[t]*(1+fee));cash=0.;entry_open=float(f.open[t])
                entry_risk=entry_open*cl['sigma'];peak=entry_open
                level=entry_open-order['distance']*entry_risk
                episode=dict(entry_index=t,entry=entry_open,entry_signal=order['signal'],
                    entry_policy=order['policy'],initial_risk_fraction=order['distance']*cl['sigma'],
                    exit_index=None,exit_price=None,exit_signal=None,exit_reason=None,marked_warning=False)
                episodes.append(episode)
                fills.append(dict(session=t,side='buy',units=float(units),price=entry_open,fee=float(units*entry_open*fee)))
            else:
                if not units: raise ValueError('Sell without position')
                gross=units*f.open[t];cash+=gross*(1-fee)
                fills.append(dict(session=t,side='sell',units=float(units),price=float(f.open[t]),fee=float(gross*fee)))
                units=0.;r=f.open[t]/entry_open*(1-fee)/(1+fee)-1
                episode.update(exit_index=t,exit_price=float(f.open[t]),exit_signal=order['signal'],
                               exit_reason=order['reason'],exit_policy=order['policy'],net_return=float(r))
                streak=streak+1 if r<0 else 0
                if streak in (3,4): warnings.append('loss_streak_'+str(streak))
                if tau is not None and r < -tau: warnings.append('large_realized_loss')
                if r<0 and order['reason']=='protection': warnings.append('losing_stop')
                level=peak=np.nan
        if units and tau is not None and not episode['marked_warning']:
            if f.close[t]/entry_open*(1-fee)/(1+fee)-1 < -tau:
                warnings.append('large_marked_loss');episode['marked_warning']=True
        posterior.discount()
        # Forget older evidence BEFORE adding any newly closed shadow outcomes.
        accelerated=bool(arm=='warning' and warnings and t-last_alarm>=20)
        if accelerated:
            posterior.discount(.25);last_alarm=t
        for j,y,r in updates.get(t,[]):posterior.observe(j,y,r>0)
        old=selected
        # Orders already queued at an earlier close remain binding.
        if arm!='fixed' and not pending:selected=posterior.choose(selected)
        if warnings or selected!=old:
            means,sds,wp=posterior.values()
            events.append(dict(session=t,day=str(f.days[t]),reason=', '.join(warnings) or 'posterior_preference',
                accelerated=accelerated,old_policy=old,policy=selected,changed=old!=selected,
                earliest_fill=t+lag,posterior_mean=float(means[selected]),posterior_sd=float(sds[selected]),
                win_probability=float(wp[selected]),effective_count=float(posterior.n[selected])))
        c=classes[selected];p=parameters[selected]
        multiplier=p['wide'] if p['context'] and c['aligned'][t] else p['tight']
        if c['fast_probability'][t,2]<p['reset']:armed=True
        active=units>0
        if target and (c['fast_down'][t] or (active and f.close[t]<level)):
            target=False;armed=False
            reason='protection' if active and f.close[t]<level else 'fast_down'
            pending[t+lag]=dict(side='sell',signal=t,reason=reason,policy=selected)
        elif not target and not active and armed and c['eligible'][t]:
            target=True;armed=False
            pending[t+lag]=dict(side='buy',signal=t,distance=multiplier,policy=selected)
        if active:
            stop[t]=level;peak=max(peak,f.close[t]);level=max(level,peak-multiplier*entry_risk)
        nav[t]=cash+units*f.close[t];desired[t]=float(target);held[t]=active
        exposure[t]=units*f.close[t]/nav[t];policy[t]=selected
        entry_threshold[t]=p['entry'];distance[t]=multiplier
        exit_threshold[t]=p['aligned_exit'] if p['context'] and c['aligned'][t] else p['exit']
        means,_,wp=posterior.values();mu[t]=means[selected];winprob[t]=wp[selected];effective[t]=posterior.n[selected]
    return dict(nav=nav,stop=stop,held=held,desired=desired,exposure=exposure,policy=policy,
        entry_threshold=entry_threshold,exit_threshold=exit_threshold,distance=distance,
        posterior_mean=mu,win_probability=winprob,effective_count=effective,
        episodes=episodes,fills=fills,events=events,threshold=tau,parameters=parameters)
