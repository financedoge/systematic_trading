"""Context-aware thesis exits with matched shadow learning; frozen parent retained."""
import numpy as np
from scipy.special import ndtr

from . import coupled_trends, latent_slope, online_policy as parent, trend_hmm

VERSION='thesis-exit-v1'
ARMS=('control','thesis','directional')
grid,reward=parent.grid,parent.reward


def exit_grid():
    return [dict(enabled=True, floor=q, count=k) for q in (.1,.2,.3) for k in (2,3)]


def classification(cl, p, rule=None, directional=False):
    base=parent.classification(cl,p)
    n=len(cl['fast_slope']);zero=np.zeros(n,bool)
    if not rule or not rule['enabled']:
        return dict(base, thesis_exit=zero, shallow_exit=zero, effective_down=cl['fast_probability'][:,0],
                    thesis_floor=np.full(n,np.nan), thesis_count=np.zeros(n,int), bad_run=np.zeros(n,int))
    # Daily context may tighten again when the slow uptrend ceases to qualify.
    strong=cl['aligned']
    floor=np.where(strong,rule['floor']/2,rule['floor'])
    count=np.where(strong,rule['count']+2,rule['count'])
    run=np.zeros(n,int)
    for t in range(n):
        run[t]=(run[t-1] if t else 0)+1 if cl['fast_probability'][t,2]<floor[t] else 0
    thesis=(run>=count)&(cl['fast_slope']<=0)
    effective=cl['fast_probability'][:,0].copy()
    if directional and p.get('family')!='slope':
        g=ndtr((-.02*cl['sigma']-cl['fast_slope'])/np.sqrt(np.maximum(cl['fast_variance'],1e-20)))
        effective+=cl['fast_probability'][:,1]*g
    threshold=np.where(strong & p['context'],p['aligned_exit'],p['exit'])
    shallow=(effective>=threshold)&~base['fast_down'] if directional else zero
    return dict(base,fast_down=base['fast_down']|thesis|shallow,thesis_exit=thesis,shallow_exit=shallow,
                effective_down=effective,thesis_floor=floor,thesis_count=count,bad_run=run)


def seed_from_shadows(f, cl, shadows):
    result=[]
    for sim in shadows:
        n=s=w=0.;count=0
        for e in sim['episodes']:
            if e['exit_index'] is None:continue
            y,r=reward(e,cl['sigma'],.0005)
            weight=parent.RHO**(len(f.days)-1-e['exit_index'])
            n+=weight;s+=weight*y;w+=weight*(r>0);count+=1
        scale=min(1.,4/max(n,1e-12))
        result.append(dict(n=n*scale,s=s*scale,w=w*scale,closed=count))
    return result


class Posterior(parent.Posterior):
    def reset(self):
        """Neutral proper priors remain; all learned evidence/freshness is gone."""
        self.n.fill(0);self.s.fill(0);self.w.fill(0);self.fresh.fill(0)


def transition_probability(log_emission,initial,transition):
    """P(z_t != z_(t-1) | observations through t), not posterior difference."""
    alpha,_,likelihood,_=trend_hmm.forward(log_emission,initial,transition)
    change=np.zeros(len(alpha))
    for t in range(1,len(alpha)):
        joint=alpha[t-1,:,None]*transition*likelihood[t,None,:]
        joint/=joint.sum();change[t]=1-np.trace(joint)
    return alpha,np.clip(change,0,1)


def confirmations(probability,change):
    """High-probability transition followed by three same-state >=.9 closes."""
    events=np.zeros(len(change),bool);pending_state=None;count=0
    for t in range(len(change)):
        row=probability[t]
        if not np.isfinite(row).all():continue
        state=int(np.argmax(row));confident=row[state]>=.9
        if change[t]>=.8 and confident:
            pending_state=state;count=1
        elif pending_state is not None:
            if confident and state==pending_state:
                count+=1
            else:
                pending_state=None;count=0
        if count>=3:
            events[t]=True;pending_state=None;count=0
    return events


def regime_signals(f):
    q=latent_slope.probabilities(f);h=f.hmm_models['hmm']
    emission=trend_hmm.emissions((q['fast']['slope'][252:]/f.hmm_models['sigma'])[:,None],
        np.asarray(h['means']),np.asarray(h['variance']))
    alpha,change=transition_probability(emission,np.asarray(h['initial']),np.asarray(h['transition']))
    p=np.full((len(f.days),3),np.nan);p[252:]=alpha
    c=np.zeros(len(f.days));c[252:]=change
    return dict(probability=p,change=c,confirmed=confirmations(p,c))


def simulate(f, cl, initial, calibration, *, start, arm='control', cost_bp=5, delay=0,
             shadows=None, regimes=None, rule=None):
    if arm not in ARMS or not isinstance(delay,int) or delay<0 or not 0<=cost_bp<10000:
        raise ValueError('Invalid arm/friction')
    if not 0<=start<len(f.days)-1 or cl['sigma']<=0: raise ValueError('Invalid data/start')
    parameters=grid(cl['parameters']);classes=[classification(cl,p,rule if arm!='control' else None,arm=='directional') for p in parameters]
    n=len(f.days);fee=cost_bp/10000;lag=1+delay
    if shadows is None:
        shadows=[coupled_trends.simulate(f,c,start=start,cost_bp=cost_bp,delay=delay) for c in classes]
    if regimes is None:
        regimes=regime_signals(f)
    updates={}
    for j,sim in enumerate(shadows):
        for e in sim['episodes']:
            if e['exit_index'] is not None:
                updates.setdefault(e['exit_index'],[]).append((j,e['entry_index'],*reward(e,cl['sigma'],fee)))
    posterior=Posterior(initial)
    sigma=calibration['winner_sigma']
    tau=max(sigma,2*fee,1e-6) if sigma is not None else None
    nav=np.full(n,np.nan);stop=nav.copy();mu=nav.copy();winprob=nav.copy();effective=nav.copy()
    desired=np.zeros(n);held=np.zeros(n,bool);exposure=np.zeros(n);policy=np.zeros(n,int)
    entry_threshold=nav.copy();distance=nav.copy();exit_threshold=nav.copy()
    cash=1.;units=0.;target=False;armed=True;selected=0;streak=0;last_alarm=-10000;last_regime=-10000;reset_session=start-1;account_peak=1.
    level=peak=entry_open=entry_risk=np.nan
    pending={};episodes=[];fills=[];events=[];episode=None
    reset_age=np.full(n,np.nan);empty=np.zeros(n,bool);reset_count=0;rejected=0
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
                level=peak=np.nan
        if units and tau is not None and not episode['marked_warning']:
            if f.close[t]/entry_open*(1-fee)/(1+fee)-1 < -tau:
                warnings.append('large_marked_loss');episode['marked_warning']=True
        account_nav=cash+units*f.close[t]
        account_peak=max(account_peak,account_nav)
        drawdown=1-account_nav/account_peak
        drawdown_threshold=max(.10,2*tau) if tau is not None else .10
        if drawdown>=drawdown_threshold:warnings.append('epoch_drawdown')
        market_event=bool(regimes['confirmed'][t])
        if market_event:warnings.append('confirmed_hmm_transition')
        loss_event=any(w!='confirmed_hmm_transition' for w in warnings)
        do_reset=bool(t-last_alarm>=20 and (loss_event or (market_event and t-last_regime>=63)))
        posterior.discount()
        before=float(posterior.n[selected])
        if do_reset:
            posterior.reset();reset_session=t;reset_count+=1;last_alarm=t
            if market_event:last_regime=t
            account_peak=account_nav;streak=0
        # Fully post-reset trade episodes only; no pre-reset or straddling payoff.
        for j,entry,y,r in updates.get(t,[]):
            if entry>reset_session:posterior.observe(j,y,r>0)
            else:rejected+=1
        old=selected
        if not pending:selected=posterior.choose(selected)
        if warnings or selected!=old:
            means,sds,wp=posterior.values()
            events.append(dict(session=t,day=str(f.days[t]),reason=', '.join(warnings) or 'posterior_preference',
                accelerated=do_reset,reset=do_reset,old_policy=old,policy=selected,changed=old!=selected,
                earliest_fill=t+lag,posterior_mean=float(means[selected]),posterior_sd=float(sds[selected]),
                win_probability=float(wp[selected]),effective_count=float(posterior.n[selected]),
                evidence_before=before,reset_session=reset_session,drawdown=float(drawdown),
                drawdown_threshold=drawdown_threshold,hmm_transition_probability=float(regimes['change'][t])))
        reset_age[t]=t-reset_session;empty[t]=not bool(np.any(posterior.fresh))
        c=classes[selected];p=parameters[selected]
        multiplier=p['wide'] if p['context'] and c['aligned'][t] else p['tight']
        if c['fast_probability'][t,2]<p['reset']:armed=True
        active=units>0
        if target and (c['fast_down'][t] or (active and f.close[t]<level)):
            target=False;armed=False
            reason=('protection' if active and f.close[t]<level else
                    'fast_down' if cl['fast_probability'][t,0] >= (p['aligned_exit'] if p['context'] and c['aligned'][t] else p['exit']) else
                    'thesis_failed' if c['thesis_exit'][t] else 'shallow_decline')
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
        episodes=episodes,fills=fills,events=events,threshold=tau,parameters=parameters,
        reset_age=reset_age,empty_evidence=empty,reset_count=reset_count,rejected_outcomes=rejected,
        regime_probability=regimes['probability'],regime_change=regimes['change'],regime_confirmed=regimes['confirmed'],
        thesis_floor=classes[0]['thesis_floor'],thesis_count=classes[0]['thesis_count'],
        bad_run=classes[0]['bad_run'],effective_down=classes[0]['effective_down'])
