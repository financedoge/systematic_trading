"""Directional emissions and causal, discounted forecasts of entry outcomes.

Research only. Forward HMM inference; matured open-to-open labels only. The
ridge posterior means are forecasts, not calibrated profitability probabilities.
"""
import numpy as np
from . import regime_entry as parent

VERSION='entry-value-v1'
ARMS=('control','hmm','value')
BAND=.10
RIDGE=4.
RISK_WEIGHT=.25


def fit_hmm(x,iterations=25):
    x=np.asarray(x,float).reshape(-1,1)
    if len(x)<100 or not np.isfinite(x).all():raise ValueError('Complete training slopes required')
    best=None
    for amplitude in (.2,.4):
        means=np.array([[-amplitude],[0.],[amplitude]])
        v=max(BAND**2,min(4.,float(x.var())))
        variance=np.array([[v],[BAND**2],[v]])
        a=np.full((3,3),.03);np.fill_diagonal(a,.94);pi=np.ones(3)/3
        for it in range(iterations):
            gamma,xi,ll=parent.trend_hmm.expectation(parent.trend_hmm.emissions(x,means,variance),pi,a)
            objective=ll+3*np.log(np.diag(a)).sum()+.1*np.log(a).sum()
            if best is None or objective>best['objective']:
                best=dict(means=means.tolist(),variance=variance.tolist(),transition=a.tolist(),initial=pi.tolist(),
                          band=BAND,objective=float(objective),log_likelihood=float(ll),iteration=it,start=amplitude)
            weight=gamma[:,0]+gamma[:,2];den=weight.sum()+1e-12
            amplitude=float(np.clip(np.sum(x[:,0]*(gamma[:,2]-gamma[:,0]))/den,2*BAND,2.))
            means=np.array([[-amplitude],[0.],[amplitude]])
            v=float(np.clip(np.sum(gamma[:,0]*(x[:,0]+amplitude)**2+gamma[:,2]*(x[:,0]-amplitude)**2)/den,BAND**2,4.))
            vr=float(np.clip(np.sum(gamma[:,1]*x[:,0]**2)/(gamma[:,1].sum()+1e-12),.000025,BAND**2))
            variance=np.array([[v],[vr],[v]])
            counts=xi+.1+3*np.eye(3);a=counts/counts.sum(axis=1,keepdims=True)
            for j in range(3):
                stay=np.clip(a[j,j],.65,.98);other=np.arange(3)!=j
                a[j,other]*=(1-stay)/a[j,other].sum();a[j,j]=stay
            pi=(gamma[0]+.1)/1.3
    return best


classification=parent.classification


def features(f,cl):
    """Bounded causal covariates. Volume uses a one-sided 63-session EMA."""
    sig=cl['sigma'];prob=cl['fast_probability'];sp=cl['slow_probability']
    average=np.empty(len(f.days));average[0]=f.volume[0]
    for i in range(1,len(average)):average[i]=average[i-1]+(2/64)*(f.volume[i]-average[i-1])
    return np.column_stack((np.ones(len(average)),prob[:,2]-prob[:,0],prob[:,1],
        np.clip(cl['fast_slope']/sig,-3,3),np.clip(cl['slow_slope']/sig,-3,3),
        np.clip((np.log(f.close)-cl['fast_level'])/sig,-3,3),
        np.clip((np.log(f.close)-cl['slow_level'])/sig,-3,3),
        sp[:,2]-sp[:,0],prob[:,2]*sp[:,0],np.clip(np.log(f.volume/average),-3,3)))


def labels(f,horizon):
    """Index i's labels mature on i+H+1. No final-exit-day close included."""
    if not isinstance(horizon,int) or not 1<=horizon<=252:raise ValueError('Invalid horizon')
    n=len(f.days);y=np.full((n,2),np.nan)
    for i in range(n-horizon-1):
        entry=f.open[i+1];end=i+horizon+1
        low=min(float(np.min(f.open[i+1:end+1])),float(np.min(f.close[i+1:end])))
        y[i]=[np.log(f.open[end]/entry),max(0.,-np.log(low/entry))]
    return y


def forecast(f,cl,horizon,memory,kind='full'):
    if memory not in (63,252) or kind not in ('full','intercept'):raise ValueError('Undeclared forecast')
    x=features(f,cl);y=labels(f,horizon);scale=cl['sigma']*np.sqrt(horizon)
    if kind=='intercept':x=x[:,:1]
    n,d=x.shape;s=np.zeros((d,d));b=np.zeros((d,2));prior=RIDGE*np.eye(d)
    rho=2**(-1/memory);weight=1/horizon
    pred=np.full((n,2),np.nan);mass=np.zeros(n);effective=0.
    for t in range(252,n):
        s*=rho;b*=rho;effective*=rho
        i=t-horizon-1
        if i>=252 and np.isfinite(y[i]).all() and np.isfinite(x[i]).all():
            s+=weight*np.outer(x[i],x[i]);b+=weight*np.outer(x[i],y[i]/scale);effective+=weight
        if np.isfinite(x[t]).all():
            pred[t]=(x[t]@np.linalg.solve(prior+s,b))*scale
            pred[t,1]=max(0.,pred[t,1])
        mass[t]=effective
    return dict(prediction=pred,labels=y,mass=mass)


def gate(cl,fc,cost_bp):
    fee=cost_bp/10000
    utility=fc['prediction'][:,0]-np.log((1+fee)/(1-fee))-RISK_WEIGHT*fc['prediction'][:,1]
    allowed=np.isfinite(utility)&(utility>0)
    return dict(cl,eligible=cl['eligible']&allowed),utility,allowed


def simulate(f,cl,*,start,cost_bp=5,delay=0,fc=None):
    if fc is None:return parent.simulate(f,cl,start=start,cost_bp=cost_bp,delay=delay)
    gated,utility,allowed=gate(cl,fc,cost_bp)
    sim=parent.simulate(f,gated,start=start,cost_bp=cost_bp,delay=delay)
    # Reconstruct original eligibility at funded, rearmed, flat decisions.
    armed=True;target=False;blocked=np.zeros(len(f.days),bool)
    for t in range(start,len(f.days)):
        if cl['fast_probability'][t,2]<cl['parameters']['reset']:armed=True
        if not target and not sim['held'][t] and armed and cl['eligible'][t] and not allowed[t]:blocked[t]=True
        if sim['desired'][t]!=target:armed=False
        target=bool(sim['desired'][t])
    sim.update(gate=allowed,blocked=blocked,utility=utility)
    return sim


def forecast_metrics(fc,indices):
    from scipy.stats import spearmanr
    p=fc['prediction'][indices];y=fc['labels'][indices]
    valid=np.isfinite(p).all(axis=1)&np.isfinite(y).all(axis=1);p=p[valid];y=y[valid]
    if not len(y):return dict(count=0,ic=None,return_mse=None,downside_mse=None)
    return dict(count=len(y),ic=float(spearmanr(p[:,0],y[:,0]).statistic) if np.std(p[:,0])>1e-12 else None,
        return_mse=float(np.mean((p[:,0]-y[:,0])**2)),downside_mse=float(np.mean((p[:,1]-y[:,1])**2)),
        mean_predicted_return=float(p[:,0].mean()),mean_return=float(y[:,0].mean()),
        mean_predicted_downside=float(p[:,1].mean()),mean_downside=float(y[:,1].mean()))
