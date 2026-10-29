"""Component study: constrained fast HMM and causal entry confirmation.

Market filters and base execution policy are frozen per ETF. No shadow-policy
learning in any arm. HMM smoothing is training-only; trading uses filtering.
Derived slopes are serially correlated: state probabilities are model scores,
not calibrated probabilities of future profitable trades.
"""
import numpy as np
from scipy.stats import spearmanr
from . import latent_slope, thesis_exit, trend_hmm

VERSION='regime-entry-v1'
ARMS=('control','hmm','guarded')
BANDS=(.05,.10)


def guard_grid():
    return [dict(enabled=True,count=k,advance=a) for k in (2,3) for a in (.5,1.)]


def fit_hmm(x,band,iterations=25):
    x=np.asarray(x,float).reshape(-1,1)
    if len(x)<500 or not np.isfinite(x).all() or band not in BANDS:
        raise ValueError('Complete training history and declared band required')
    best=None
    for amplitude in (.15,.4):
        initial_mean=max(amplitude,2*band)
        means=np.array([[-initial_mean],[0.],[initial_mean]])
        variance=np.full((3,1),max(float(x.var()),.0001));variance[1]=band**2
        a=np.full((3,3),.03);np.fill_diagonal(a,.94);pi=np.ones(3)/3
        for it in range(iterations):
            gamma,xi,ll=trend_hmm.expectation(trend_hmm.emissions(x,means,variance),pi,a)
            objective=ll+3*np.log(np.diag(a)).sum()+.1*np.log(a).sum()
            if best is None or objective>best['objective']:
                best=dict(means=means.tolist(),variance=variance.tolist(),transition=a.tolist(),initial=pi.tolist(),
                          band=band,objective=float(objective),log_likelihood=float(ll),iteration=it,amplitude=amplitude)
            w=gamma.sum(axis=0)+1e-12
            means=gamma.T@x/w[:,None]
            means[0,0]=np.clip(means[0,0],-2,-2*band);means[1,0]=0
            means[2,0]=np.clip(means[2,0],2*band,2)
            variance=np.clip((gamma*(x-means.T)**2).sum(axis=0)[:,None]/w[:,None],.000025,4.)
            variance[1,0]=min(variance[1,0],band**2)
            counts=xi+.1+np.eye(3)*3;a=counts/counts.sum(axis=1,keepdims=True)
            for j in range(3):
                stay=np.clip(a[j,j],.65,.98);other=np.arange(3)!=j
                a[j,other]*=(1-stay)/a[j,other].sum();a[j,j]=stay
            pi=(gamma[0]+.1)/1.3
    return best


def filtered(x,m):
    return trend_hmm.forward(trend_hmm.emissions(np.asarray(x)[:,None],np.asarray(m['means']),np.asarray(m['variance'])),
                             np.asarray(m['initial']),np.asarray(m['transition']))


def select_hmm(x):
    """Final 252 training slopes select width by predictive slope likelihood.

    Existing Kalman fits use full training: this is an HMM-only holdback, not a
    nested holdout of the entire pipeline. Refit the selected width on all x.
    """
    candidates=[]
    for band in BANDS:
        m=fit_hmm(x[:-252],band)
        _,sc,_,ll=filtered(x,m)
        loge=trend_hmm.emissions(np.asarray(x)[:,None],np.asarray(m['means']),np.asarray(m['variance']))
        score=float(np.sum(np.log(sc[-252:])+loge[-252:].max(axis=1)))
        candidates.append(dict(band=band,score=score))
    band=max(candidates,key=lambda v:(v['score'],-v['band']))['band']
    return dict(model=fit_hmm(x,band),candidates=candidates)


def classification(f,p,exit_rule,hmm=None):
    cl=latent_slope.classify(f,p)
    if hmm is not None:
        hp=np.full((len(f.days),3),np.nan)
        hp[252:]=filtered(cl['fast_slope'][252:]/cl['sigma'],hmm)[0]
        cl=dict(cl,fast_probability=hp)
    return thesis_exit.classification(cl,thesis_exit.grid(p)[0],exit_rule)


def simulate(f,cl,*,start,cost_bp=5,delay=0,guard=None):
    if not isinstance(delay,int) or delay<0 or not 0<=cost_bp<10000 or not 0<=start<len(f.days)-1:
        raise ValueError('Invalid execution parameters')
    n=len(f.days);p=cl['parameters'];fee=cost_bp/10000;lag=1+delay
    nav=np.full(n,np.nan);stop=nav.copy();desired=np.zeros(n,bool);held=np.zeros(n,bool)
    required=np.zeros(n,int);run_series=np.zeros(n,int);blocked=np.zeros(n,bool);gate=np.zeros(n,bool)
    advance_series=nav.copy();anchor_series=nav.copy()
    cash=1.;units=0.;target=False;active=False;armed=True;failed=False;reset_seen=True
    level=peak=risk=np.nan;episode=None;episodes=[];fills=[];reasons={};run=0;anchor=np.nan
    for t in range(start,n):
        adopted=bool(desired[t-lag]) if t>=lag else False
        multiplier=p['wide'] if p['context'] and cl['aligned'][t] else p['tight']
        if adopted and not active:
            price=float(f.open[t]);units=cash/(price*(1+fee));cash=0.;peak=price;risk=price*cl['sigma']
            known=p['wide'] if p['context'] and cl['aligned'][t-lag] else p['tight'];level=price-known*risk
            episode=dict(entry_index=t,entry=price,entry_signal=t-lag,entry_policy=0,exit_policy=0,
                initial_risk_fraction=known*cl['sigma'],exit_index=None,exit_price=None,exit_signal=None,exit_reason=None,
                context='up' if cl['aligned'][t-lag] else 'down' if cl['counter'][t-lag] else 'uncertain')
            episodes.append(episode);fills.append(dict(session=t,side='buy',units=float(units),price=price,fee=float(units*price*fee)))
        elif not adopted and active:
            price=float(f.open[t]);cash=units*price*(1-fee)
            fills.append(dict(session=t,side='sell',units=float(units),price=price,fee=float(units*price*fee)));units=0.
            r=price/episode['entry']*(1-fee)/(1+fee)-1
            episode.update(exit_index=t,exit_price=price,exit_signal=t-lag,exit_reason=reasons[t-lag],net_return=float(r))
            failed=r<0;reset_seen=not failed;run=0;anchor=np.nan;level=peak=np.nan
        active=adopted
        up=float(cl['fast_probability'][t,2])
        if up<p['reset']:armed=True;reset_seen=True
        guarded=bool(guard and guard['enabled'] and (not cl['aligned'][t] or failed))
        high=up>=max(.8,p['entry']) and cl['fast_slope'][t]>0
        # Evidence starts from a flat, funded opportunity; no pre-exit credit.
        if not active and not target and high and reset_seen:
            if run==0:anchor=float(f.close[max(0,t-1)])
            run+=1
        elif active or not high or not reset_seen:
            run=0;anchor=np.nan
        needed=guard['count']+int(failed) if guarded else 1
        advance=np.log(f.close[t]/anchor) if np.isfinite(anchor) else np.nan
        confirmation=not guarded or (reset_seen and run>=needed and advance>=guard['advance']*cl['sigma']+2*fee)
        stop_hit=active and f.close[t]<level
        if target and (cl['fast_down'][t] or stop_hit):
            target=False;armed=False
            reasons[t]='protection' if stop_hit else 'thesis_failed' if cl['thesis_exit'][t] else 'fast_down'
        elif not target and not active and armed and cl['eligible'][t]:
            if confirmation:target=True;armed=False
            else:blocked[t]=True
        if active:stop[t]=level;peak=max(peak,f.close[t]);level=max(level,peak-multiplier*risk)
        nav[t]=cash+units*f.close[t];desired[t]=target;held[t]=active
        required[t]=needed;run_series[t]=run;gate[t]=confirmation;advance_series[t]=advance;anchor_series[t]=anchor
    return dict(nav=nav,stop=stop,desired=desired,held=held,exposure=held.astype(float),episodes=episodes,fills=fills,
                blocked=blocked,gate=gate,required=required,run=run_series,advance=advance_series,anchor=anchor_series)


def dependence(strategy,asset):
    """Daily arithmetic returns; zero cash rate, descriptive HAC(5) alpha."""
    y,x=np.asarray(strategy,float),np.asarray(asset,float)
    if len(x)!=len(y) or not np.isfinite(x).all() or not np.isfinite(y).all():raise ValueError('Aligned finite returns required')
    design=np.column_stack((np.ones(len(x)),x));bread=np.linalg.pinv(design.T@design)
    coef=bread@design.T@y;u=y-design@coef;xu=design*u[:,None];meat=xu.T@xu
    for k in range(1,min(5,len(x)-1)+1):
        s=xu[k:].T@xu[:-k];meat+=(1-k/6)*(s+s.T)
    cov=bread@meat@bread*len(x)/max(1,len(x)-2);se=np.sqrt(max(0,cov[0,0]))
    corr=float(np.corrcoef(y,x)[0,1]) if y.std()>1e-15 and x.std()>1e-15 else None
    return dict(correlation=corr,beta=float(coef[1]),alpha_annual=float(252*coef[0]),
                alpha_t_hac=float(coef[0]/se) if se>1e-15 else None,
                down_capture=float(y[x<0].mean()/x[x<0].mean()) if np.any(x<0) else None,
                up_capture=float(y[x>0].mean()/x[x>0].mean()) if np.any(x>0) else None)


def ic(f,cl,start,delay=0):
    # Five-session holding returns begin at the earliest executable open.
    idx=np.arange(start,len(f.days)-6-delay);score=cl['fast_probability'][idx,2]-cl['fast_probability'][idx,0]
    future=f.open[idx+6+delay]/f.open[idx+1+delay]-1
    valid=np.isfinite(score)&np.isfinite(future)
    return float(spearmanr(score[valid],future[valid]).statistic) if valid.sum()>10 and np.std(score[valid])>1e-12 else None
