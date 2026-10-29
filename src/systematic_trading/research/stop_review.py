"""Standing protection and causal review of reversed trading decisions.

Daily OHLC stop execution is a fill model, not observed intraday execution.
All signal changes use closes and fill at a subsequent open. No broker access.
"""
from dataclasses import dataclass,field
import numpy as np
from . import entry_value as parent

VERSION='stop-review-v1'
ARMS=('baseline','stop','review')


@dataclass
class Features:
    days:np.ndarray
    open:np.ndarray
    high:np.ndarray
    low:np.ndarray
    close:np.ndarray
    volume:np.ndarray
    hmm_models:dict=field(default_factory=dict)
    coupled_cache:dict=field(default_factory=dict)

    @classmethod
    def build(cls,data):
        arrays=[np.asarray(data[k],float) for k in ('open','high','low','close','volume')]
        if any(not np.isfinite(a).all() or np.any(a<=0) for a in arrays):raise ValueError('Complete audited OHLCV required')
        o,h,l,c,v=arrays;tol=1e-7*np.maximum(1,c)
        if np.any(l>np.minimum(o,c)+tol) or np.any(h<np.maximum(o,c)-tol) or np.any(h<l):raise ValueError('Invalid OHLC geometry')
        return cls(np.asarray(data['days'],dtype='datetime64[D]'),*arrays)

    def truncated(self,cutoff):
        n=int(np.sum(self.days<=np.datetime64(cutoff)))
        return Features(self.days[:n],*[getattr(self,k)[:n] for k in ('open','high','low','close','volume')],self.hmm_models)


def activity(f):
    prev=np.r_[f.close[0],f.close[:-1]]
    tr=np.maximum(f.high-f.low,np.maximum(abs(f.high-prev),abs(f.low-prev)))
    atr=np.empty(len(prev));atr[0]=tr[0]
    for t in range(1,len(prev)):atr[t]=atr[t-1]+(tr[t]-atr[t-1])/20
    signed=np.sign(f.close-prev)*f.volume;pressure=np.zeros(len(prev))
    for t in range(len(prev)):
        a=max(0,t-2);pressure[t]=signed[a:t+1].sum()/f.volume[a:t+1].sum()
    location=np.divide(f.close-f.low,f.high-f.low,out=np.full(len(prev),.5),where=f.high>f.low)
    return dict(atr=atr,pressure=pressure,location=location)


def policies(cl,rule):
    out=[]
    for delta,scale,extra in ((0.,1.,0),(-.05,.75,-1),(.05,1.25,1)):
        p=dict(cl['parameters']);p.update(entry=float(np.clip(p['entry']+delta,.5,.9)),exit=float(np.clip(p['exit']+delta,.45,.9)),
            aligned_exit=float(np.clip(p['aligned_exit']+delta,.65,.95)),tight=p['tight']*scale,wide=p['wide']*scale)
        r=dict(rule)
        if r.get('enabled'):r['count']=max(1,r['count']+extra)
        out.append(parent.parent.thesis_exit.classification(cl,p,r))
    return out


def recovered(f,cl,info,t,q,fee):
    if info is None or not 1<=t-info['day']<=10:return False
    if not info['price']*(1+2*fee)<=f.close[t]<=info['price']+info['atr']:return False
    return bool(cl['fast_probability'][t,2]>=.55 and cl['fast_probability'][t,0]<=.35 and
        (cl['fast_slope'][t]>0 or cl['fast_slope'][t]>cl['fast_slope'][t-1]) and
        f.close[t]>f.close[t-1] and f.close[t]>f.open[t] and q['location'][t]>=.6 and q['pressure'][t]>=0)


def simulate(f,cl,*,start,cost_bp=5,delay=0,mode='stop',rule=None,recovery=False,adaptive=False,reset=True,
             seed=None,shadows=None,loss_threshold=None,slip_bp=5):
    if mode=='baseline':return parent.parent.simulate(f,cl,start=start,cost_bp=cost_bp,delay=delay)
    if mode not in ('stop','touch_close','close_next','stop_close_stress') or delay not in (0,1) or not 0<=cost_bp<10000 or not 0<=slip_bp<10000:raise ValueError('Invalid execution')
    n=len(f.days);fee=cost_bp/1e4;slip=slip_bp/1e4;lag=1+delay;q=activity(f)
    classes=policies(cl,rule or dict(enabled=False));rho=2**(-1/63)
    if seed is None:seed=dict(n=0.,s=[0.,0.,0.])
    count=float(seed['n']);sums=np.array(seed['s'],float);selected=0;last_change=-10000
    def choose(current):
        scores=sums/(4+count)-.25/np.sqrt(4+count);best=int(np.argmax(scores))
        return best if scores[best]>scores[current]+.02 else current
    if adaptive:
        if shadows is None:raise ValueError('Causal shadow return histories required')
        selected=choose(0)
    nav=np.full(n,np.nan);stop=nav.copy();policy=np.zeros(n,int);desired=np.zeros(n,bool);held=np.zeros(n,bool)
    invested=np.zeros(n,bool);review_signal=np.zeros(n,bool);reset_series=np.zeros(n,bool);score=np.full((n,3),np.nan)
    cash=1.;units=0.;target=False;armed=True;pending={};fills=[];episodes=[];events=[];episode=None;watch=None
    level=peak=risk=np.nan;entry_policy=0;streak=0
    for t in range(start,n):
        warnings=[];sold=False;was_invested=units>0
        def sell(price,reason,signal,phase,trigger=None):
            nonlocal cash,units,target,armed,episode,level,peak,watch,sold,streak
            if units<=0:raise ValueError('Sell without position')
            fills.append(dict(session=t,side='sell',units=float(units),price=float(price),fee=float(units*price*fee),phase=phase,trigger=trigger))
            cash+=units*price*(1-fee);units=0.;r=price/episode['entry']*(1-fee)/(1+fee)-1
            episode.update(exit_index=t,exit_price=float(price),exit_signal=signal,exit_reason=reason,exit_policy=entry_policy,net_return=float(r))
            if r<0 and t-episode['entry_index']<=10:warnings.append('quick_failed_buy')
            streak=streak+1 if r<0 else 0
            if streak in (3,4):warnings.append('loss_streak')
            if loss_threshold is not None and r < -max(loss_threshold,2*fee):warnings.append('large_loss')
            watch=dict(day=t,price=float(price),atr=float(q['atr'][max(0,signal)]),reason=reason)
            target=False
            # Opening signal fills must preserve rearming observed while waiting.
            # A new protective event invalidates the current entry cycle instead.
            if phase!='open':armed=False
            level=peak=np.nan;sold=True
        order=pending.pop(t,None)
        if order:
            if order['side']=='buy':
                if units:raise ValueError('Overlapping buy')
                price=float(f.open[t]);units=cash/(price*(1+fee));cash=0.;entry_policy=order['policy'];peak=price;risk=price*cl['sigma']
                level=price-order['distance']*risk
                episode=dict(entry_index=t,entry=price,entry_signal=order['signal'],entry_policy=entry_policy,entry_reason=order['reason'],
                    initial_risk_fraction=order['distance']*cl['sigma'],exit_index=None,exit_price=None,exit_signal=None,exit_reason=None,
                    context='up' if cl['aligned'][order['signal']] else 'down' if cl['counter'][order['signal']] else 'uncertain')
                episodes.append(episode);fills.append(dict(session=t,side='buy',units=float(units),price=price,fee=float(units*price*fee),phase='open',trigger=None));watch=None
            else:sell(float(f.open[t]),order['reason'],order['signal'],'open')
        active=units>0;invested[t]=was_invested or active
        if active:stop[t]=level
        # The level was set before this bar, or immediately after its opening buy.
        # Today's high never ratchets a level tested against today's low.
        if active and mode!='close_next' and f.low[t]<=level:
            trigger=float(level)
            if mode=='touch_close':price=f.close[t]*(1-slip);phase='conditional_close'
            elif mode=='stop_close_stress':price=min(f.open[t],level,f.close[t])*(1-slip);phase='conservative_stop'
            else:price=min(f.open[t],level)*(1-slip);phase='open_gap' if f.open[t]<=level else 'intraday_stop'
            sell(float(price),'intraday_protection',t,'open_gap' if phase=='open_gap' else phase,trigger)
            pending.clear() # Protective OCO supersedes stale exits for this position.
            active=False
        if adaptive and t>start:
            count*=rho;sums*=rho;count+=1;sums+=shadows[t]/cl['sigma']
        reversal=bool(recovery and not units and not target and not pending and not sold and recovered(f,cl,watch,t,q,fee))
        if reversal:warnings.append('exit_reversed');review_signal[t]=True
        if adaptive and warnings and reset:
            a=max(start+1,t-20);indices=np.arange(a,t+1);weights=rho**(t-indices)
            count=float(weights.sum());sums=np.sum(shadows[indices]/cl['sigma']*weights[:,None],axis=0) if len(indices) else np.zeros(3)
            reset_series[t]=True
        old=selected
        if adaptive and not units and not pending and (warnings or t-last_change>=5):
            selected=choose(selected)
            if selected!=old:last_change=t
        if warnings or old!=selected:events.append(dict(session=t,day=str(f.days[t]),reasons=warnings,reset=bool(reset_series[t]),old_policy=old,policy=selected,changed=old!=selected))
        current=classes[entry_policy if units else selected];p=current['parameters']
        if current['fast_probability'][t,2]<p['reset']:armed=True
        if target and (current['fast_down'][t] or (units and mode=='close_next' and f.close[t]<level)):
            reason='protection' if units and mode=='close_next' and f.close[t]<level else 'thesis_failed' if current['thesis_exit'][t] else 'fast_down'
            pending[t+lag]=dict(side='sell',signal=t,reason=reason);target=False;armed=False
        elif not target and not units and not pending and ((armed and current['eligible'][t]) or reversal):
            distance=p['wide'] if p['context'] and current['aligned'][t] else p['tight']
            pending[t+lag]=dict(side='buy',signal=t,policy=selected,distance=distance,reason='exit_review' if reversal else 'ordinary');target=True;armed=False
        if units:
            peak=max(peak,f.close[t]);distance=p['wide'] if p['context'] and current['aligned'][t] else p['tight']
            level=max(level,peak-distance*risk)
        nav[t]=cash+units*f.close[t];desired[t]=target;held[t]=units>0;policy[t]=selected;score[t]=sums/(4+count)
    return dict(nav=nav,stop=stop,desired=desired,held=held,exposure=held.astype(float),invested_session=invested,policy=policy,
        review_signal=review_signal,reset=reset_series,posterior_mean=score,episodes=episodes,fills=fills,events=events)


def shadow_returns(f,cl,rule,*,start,cost_bp=5,delay=0,slip_bp=5,mode='stop'):
    # All candidates include the same review entry rule. Each runs independently.
    sims=[simulate(f,c,start=start,cost_bp=cost_bp,delay=delay,slip_bp=slip_bp,mode=mode,rule=r,recovery=True)
          for c,r in zip(policies(cl,rule),[rule,dict(rule,count=max(1,rule.get('count',1)-1)),dict(rule,count=rule.get('count',1)+1)])]
    out=np.zeros((len(f.days),3))
    for j,s in enumerate(sims):out[start+1:,j]=s['nav'][start+1:]/s['nav'][start:-1]-1
    return out


def seed_from_returns(returns,start):
    ix=np.arange(start+1,len(returns));weights=2**(-(len(returns)-1-ix)/63);count=weights.sum()
    scale=min(1.,20/max(count,1e-12))
    return dict(n=float(count*scale),s=(np.sum(returns[ix]*weights[:,None],axis=0)*scale).tolist())
