"""Independent price/volume decision review, with causal predictive model averaging.

Research model: Gaussian class likelihoods are working approximations, not
calibrated financial probabilities or an implementation of BOCPD.
"""
from copy import deepcopy
import numpy as np
from . import stop_review as parent

VERSION='decision-review-v1'
ARMS=('baseline','stop','review')  # display: protection, decision review, adaptive review
Features=parent.Features
activity=parent.activity
HORIZON=5
THRESHOLD=float(np.log(4))


def observations(f,sigma):
    q=activity(f);c=f.close;n=len(c);r=np.r_[0,np.diff(np.log(c))]
    x=np.zeros((n,6));x[:,0]=r/sigma
    for t in range(n):
        x[t,1]=r[max(0,t-2):t+1].sum()/(sigma*np.sqrt(3))
        x[t,4]=np.log(f.volume[t]/np.mean(f.volume[max(0,t-20):max(1,t)]))
    x[:,2]=2*q['location']-1;x[:,3]=q['pressure']
    x[1:,5]=np.diff(f.low)/np.maximum(q['atr'][:-1],1e-12)
    return np.clip(x,-4,4)


def fit(f,sigma):
    x=observations(f,sigma);indices=np.arange(max(252,len(x)-762),len(x)-6)
    if len(indices)<100:raise ValueError('Insufficient matured training observations')
    y=np.log(f.open[indices+6]/f.open[indices+1])/(sigma*np.sqrt(5))
    label=y>0;d=x.shape[1]
    n=np.array([np.sum(label==j) for j in (0,1)],float)
    if min(n)<20:raise ValueError('Insufficient direction coverage')
    sx=np.array([x[indices[label==j]].sum(axis=0) for j in (0,1)])
    xx=np.array([x[indices[label==j]].T@x[indices[label==j]] for j in (0,1)])
    sy=np.array([y[label==j].sum() for j in (0,1)])
    diagonal=np.maximum(np.var(x[indices],axis=0),.05)
    return dict(n=n.tolist(),sx=sx.tolist(),xx=xx.tolist(),sy=sy.tolist(),diagonal=diagonal.tolist(),
                observations=len(indices),last_origin=str(f.days[indices[-1]]),last_maturity=str(f.days[indices[-1]+6]),
                cutoff=str(f.days[-1]),sigma=float(sigma))


class Expert:
    def __init__(self,seed,cap=None):
        self.n=np.array(seed['n'],float);self.sx=np.array(seed['sx'],float)
        self.xx=np.array(seed['xx'],float);self.sy=np.array(seed['sy'],float)
        self.diagonal=np.array(seed['diagonal'],float)
        if cap:
            scale=min(1,cap/self.n.sum())
            self.n*=scale;self.sx*=scale;self.xx*=scale;self.sy*=scale
        self.recalculate()

    def recalculate(self):
        self.means=self.sx/self.n[:,None]
        covariance=(self.xx-np.einsum('ki,kj,k->kij',self.means,self.means,self.n)).sum(axis=0)/self.n.sum()
        covariance=.5*covariance+.5*np.diag(self.diagonal)+.05*np.eye(len(self.diagonal))
        self.inverse=np.linalg.inv(covariance)
        self.constant=-.5*np.linalg.slogdet(covariance)[1]
        self.prior=self.n/self.n.sum();self.value=self.sy/self.n

    def forecast(self,x):
        residual=x-self.means
        logjoint=self.constant-.5*np.einsum('ki,ij,kj->k',residual,self.inverse,residual)+np.log(self.prior)
        p=1/(1+np.exp(np.clip(logjoint[0]-logjoint[1],-40,40)))
        return dict(p=float(p),mu=float((1-p)*self.value[0]+p*self.value[1]),prior=float(self.prior[1]))

    def update(self,x,y,half_life):
        rho=2**(-1/half_life)
        self.n*=rho;self.sx*=rho;self.xx*=rho;self.sy*=rho
        j=int(y>0);self.n[j]+=1;self.sx[j]+=x;self.xx[j]+=np.outer(x,x);self.sy[j]+=y
        self.recalculate()


class ReviewModels:
    def __init__(self,seed,adaptive):
        self.models=[Expert(seed),Expert(seed,40)];self.adaptive=adaptive
        self.weights=np.array([.5,.5]) if adaptive else np.array([1.,0.])
        self.pending={};self.fast_until=-1;self.scores=[]

    def mature(self,t,f,x):
        origin=t-6
        if origin not in self.pending:return
        predictions=self.pending.pop(origin)
        y=float(np.log(f.open[t]/f.open[origin+1]));label=int(y>0)
        p=np.clip([a['p'] for a in predictions],.01,.99)
        logscore=np.log(p if label else 1-p)
        self.scores.append(dict(origin=origin,maturity=t,label=label,probabilities=p.tolist(),logscore=logscore.tolist(),
                                mixture_p=float(np.dot(predictions[0]['origin_weights'],p))))
        if self.adaptive:
            # Overlapping five-session labels: temper each score by 1/5.
            logw=.98*np.log(self.weights)+np.clip(logscore-logscore.mean(),-2,2)/5
            w=np.exp(logw-logw.max());self.weights=w/w.sum()
            self.models[1].update(x[origin],y/(f.review_sigma*np.sqrt(5)),10 if t<=self.fast_until else 63)

    def warning(self,t):
        if self.adaptive:
            # Allow reconsideration; never force challenger selection or loosen risk.
            self.weights=np.sqrt(self.weights);self.weights/=self.weights.sum();self.fast_until=t+21

    def forecast(self,t,x):
        predictions=[m.forecast(x) for m in self.models]
        predictions[0]['origin_weights']=self.weights.tolist();self.pending[t]=deepcopy(predictions)
        p=float(self.weights@np.array([q['p'] for q in predictions]))
        prior=float(self.weights@np.array([q['prior'] for q in predictions]))
        # CUSUM-style evidence of favorable price action relative to its base rate.
        odds=lambda z:np.log(np.clip(z,1e-6,1-1e-6)/(1-np.clip(z,1e-6,1-1e-6)))
        evidence=float(np.clip(odds(p)-odds(prior),-2,2))
        return p,float(self.weights@np.array([q['mu'] for q in predictions])),evidence


def simulate(f,cl,*,start,cost_bp=5,delay=0,rule=None,arm='baseline',seed=None,loss_threshold=None,
             slip_bp=5,entry_review=True,exit_review=True,warning_updates=True):
    if arm=='baseline':return parent.simulate(f,cl,start=start,cost_bp=cost_bp,delay=delay,rule=rule,slip_bp=slip_bp)
    if arm not in ('stop','review') or delay not in (0,1):raise ValueError('Invalid arm/delay')
    if seed is None:raise ValueError('Training seed required')
    n=len(f.days);fee=cost_bp/10000;slip=slip_bp/10000;lag=1+delay;q=activity(f);p=cl['parameters']
    f.review_sigma=cl['sigma'];x=observations(f,cl['sigma']);models=ReviewModels(seed,arm=='review')
    nav=np.full(n,np.nan);stop=nav.copy();held=np.zeros(n,bool);desired=held.copy();invested=held.copy()
    review_signal=held.copy();resets=held.copy();prob=nav.copy();value=nav.copy();evidence=nav.copy();weight=nav.copy()
    up_path=nav.copy();down_path=nav.copy();up=down=0.;cash=1.;units=0.;target=False;armed=True;pending={}
    fills=[];episodes=[];events=[];episode=None;watch=None;level=peak=risk=np.nan;streak=0
    for t in range(start,n):
        warnings=[];sold=False;was_invested=units>0
        models.mature(t,f,x)
        def sell(price,reason,signal,phase,trigger=None):
            nonlocal cash,units,target,armed,level,peak,watch,sold,streak,up,down
            fills.append(dict(session=t,side='sell',units=float(units),price=float(price),fee=float(units*price*fee),phase=phase,trigger=trigger))
            cash+=units*price*(1-fee);units=0.;r=price/episode['entry']*(1-fee)/(1+fee)-1
            episode.update(exit_index=t,exit_price=float(price),exit_signal=signal,exit_reason=reason,exit_policy=0,net_return=float(r))
            streak=streak+1 if r<0 else 0
            if streak in (3,4):warnings.append('loss_streak')
            if loss_threshold is not None and r < -max(loss_threshold,2*fee):warnings.append('large_loss')
            if reason=='entry_invalidated':warnings.append('entry_reversed')
            watch=dict(day=t,price=float(price),atr=float(q['atr'][max(0,t-1)]))
            target=False
            if phase!='open':armed=False
            level=peak=np.nan;sold=True;up=down=0.
        order=pending.pop(t,None)
        if order:
            if order['side']=='buy':
                # Recovery opening-price guard can cancel a stale or chased order.
                if order['reason']=='exit_review' and not order['lower']<=f.open[t]<=order['upper']:
                    target=False;warnings.append('recovery_open_cancelled')
                else:
                    price=float(f.open[t]);units=cash/(price*(1+fee));cash=0.;peak=price;risk=price*cl['sigma']
                    level=price-order['distance']*risk;up=down=0.;watch=None
                    episode=dict(entry_index=t,entry=price,entry_signal=order['signal'],entry_policy=0,entry_reason=order['reason'],
                        initial_risk_fraction=order['distance']*cl['sigma'],exit_index=None,exit_price=None,exit_signal=None,exit_reason=None,
                        context='up' if cl['aligned'][order['signal']] else 'down' if cl['counter'][order['signal']] else 'uncertain')
                    episodes.append(episode);fills.append(dict(session=t,side='buy',units=float(units),price=price,fee=float(units*price*fee),phase='open',trigger=None))
            else:sell(float(f.open[t]),order['reason'],order['signal'],'open')
        invested[t]=was_invested or units>0
        if units:
            stop[t]=level
            if f.low[t]<=level:
                trigger=float(level);phase='open_gap' if f.open[t]<=level else 'intraday_stop'
                sell(float(min(f.open[t],level)*(1-slip)),'intraday_protection',t,phase,trigger);pending.clear()
        if warning_updates and any(w in warnings for w in ('large_loss','loss_streak','entry_reversed')):models.warning(t);resets[t]=arm=='review'
        prob[t],mu,ell=models.forecast(t,x[t]);value[t]=mu*cl['sigma']*np.sqrt(5);evidence[t]=ell;weight[t]=models.weights[1]
        if units:down=max(0.,down-ell-.1)
        if watch and not sold and 1<=t-watch['day']<=20:up=max(0.,up+ell-.1)
        else:up=0.
        up_path[t]=up;down_path[t]=down
        reversal=bool(exit_review and watch and not sold and not units and not target and not pending and
            1<=t-watch['day']<=20 and up>=THRESHOLD and prob[t]>.5 and value[t]>2*fee+slip and
            watch['price']*(1+2*fee)<=f.close[t]<=watch['price']+1.5*watch['atr'] and
            f.close[t]>max(f.open[t],f.close[t-1]) and q['location'][t]>=.6 and q['pressure'][t]>=0)
        invalid=bool(entry_review and units and down>=THRESHOLD and prob[t]<.5 and value[t]<0 and
            f.close[t]<f.close[t-1] and f.close[t]<=peak-.5*q['atr'][t])
        if reversal:
            warnings.append('exit_reversed');review_signal[t]=True
            if warning_updates:models.warning(t);resets[t]=arm=='review'
        if cl['fast_probability'][t,2]<p['reset']:armed=True
        if target and (cl['fast_down'][t] or invalid):
            reason='entry_invalidated' if invalid else 'thesis_failed' if cl['thesis_exit'][t] else 'fast_down'
            pending[t+lag]=dict(side='sell',signal=t,reason=reason);target=False;armed=False
        elif not target and not units and not pending and ((armed and cl['eligible'][t]) or reversal):
            distance=p['wide'] if p['context'] and cl['aligned'][t] else p['tight']
            pending[t+lag]=dict(side='buy',signal=t,distance=distance,reason='exit_review' if reversal else 'ordinary',
                lower=watch['price'] if reversal else 0,upper=watch['price']+1.5*watch['atr'] if reversal else np.inf)
            target=True;armed=False
        if units:
            peak=max(peak,f.close[t]);distance=p['wide'] if p['context'] and cl['aligned'][t] else p['tight']
            level=max(level,peak-distance*risk)
        if warnings:events.append(dict(session=t,day=str(f.days[t]),reasons=warnings,reset=bool(resets[t]),old_policy=0,policy=0,changed=False,recent_weight=float(models.weights[1])))
        nav[t]=cash+units*f.close[t];held[t]=units>0;desired[t]=target
    return dict(nav=nav,stop=stop,held=held,desired=desired,exposure=held.astype(float),invested_session=invested,
        review_signal=review_signal,reset=resets,policy=np.zeros(n),probability=prob,forecast=value,evidence=evidence,
        recent_weight=weight,up_evidence=up_path,down_evidence=down_path,episodes=episodes,fills=fills,events=events,scores=models.scores)
