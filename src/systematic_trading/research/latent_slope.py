"""Forward local-linear price slopes and a separately fitted fast-state HMM.

This is a two-stage filter/classifier, not jointly inferred switching Kalman
states. The derived slope observations are serially correlated; HMM probabilities
must not be presented as calibrated confidence. No rolling trend windows.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import ndtr

from . import coupled_trends as execution
from . import trend_hmm

VERSION = 'latent-slope-1.0.0'
Features = execution.Features
simulate = execution.simulate


def kalman(log_price, ratio, variance=1.):
    """Local linear trend with Q=diag(0, ratio*R), R=variance.

    Unit-R covariance recursion makes profiling R exact, conditional on the
    first observation and the declared scaled initial covariance.
    """
    y = np.asarray(log_price, float)
    if not np.isfinite(y).all() or ratio <= 0 or variance <= 0:
        raise ValueError('Finite observations and positive variances required')
    n = len(y)
    level, slope, p00, p01, p11 = float(y[0]), 0., 1., 0., 1.
    levels, slopes, level_var, slope_var = [np.zeros(n) for _ in range(4)]
    innovations, unit_innovation_var = np.zeros(n), np.ones(n)
    levels[0], level_var[0], slope_var[0] = level, variance, variance
    for t in range(1, n):
        # F=[[1,1],[0,1]], H=[1,0]; scalar algebra avoids tiny matrix overhead.
        predicted = level + slope
        a, b, c = p00 + 2*p01 + p11, p01 + p11, p11 + ratio
        s = a + 1.
        k0, k1 = a/s, b/s
        error = y[t] - predicted
        level, slope = predicted + k0*error, slope + k1*error
        p00, p01, p11 = a/s, b/s, c-b*b/s
        levels[t], slopes[t] = level, slope
        level_var[t], slope_var[t] = p00*variance, max(p11, 0.)*variance
        innovations[t], unit_innovation_var[t] = error, s
    return dict(level=levels, slope=slopes, level_variance=level_var,
                slope_variance=slope_var, innovation=innovations,
                innovation_variance=unit_innovation_var*variance)


def fit_filter(log_price, bounds):
    y = np.asarray(log_price, float)
    def objective(log_ratio, return_model=False):
        ratio = float(np.exp(log_ratio)); q = kalman(y, ratio)
        error, v = q['innovation'][252:], q['innovation_variance'][252:]
        variance = max(float(np.mean(error**2/v)), 1e-12)
        nll = .5*float(np.sum(np.log(2*np.pi*v*variance) + error**2/(v*variance)))
        return dict(ratio=ratio, variance=variance, nll=nll) if return_model else nll
    result = minimize_scalar(objective, bounds=np.log(bounds), method='bounded',
                             options=dict(xatol=.15, maxiter=18))
    candidates=[objective(float(x), True) for x in (*np.log(bounds), result.x)]
    best=min(candidates,key=lambda m:m['nll'])
    return dict(**best, bounds=list(bounds), optimizer_success=bool(result.success),
                evaluations=int(result.nfev)+2, training_rows=len(y)-252)


def fit_hmm(values, iterations=25):
    z=np.asarray(values,float)[:,None]
    if not np.isfinite(z).all() or len(z)<500:
        raise ValueError('Complete training slopes required')
    best=None
    for amplitude in (.05,.2):
        means=np.array([[-amplitude],[0.],[amplitude]])
        var=np.full((3,1),max(float(np.var(z)),.0001))
        a=np.full((3,3),.03);np.fill_diagonal(a,.94)
        initial=np.ones(3)/3
        for iteration in range(iterations):
            gamma,xi,ll=trend_hmm.expectation(trend_hmm.emissions(z,means,var),initial,a)
            objective=ll+3*np.log(np.diag(a)).sum()+.1*np.log(a).sum()
            if best is None or objective>best['objective']:
                best=dict(means=means.tolist(),variance=var.tolist(),transition=a.tolist(),
                          initial=initial.tolist(),log_likelihood=ll,objective=objective,
                          iteration=iteration,initial_amplitude=amplitude)
            weights=gamma.sum(axis=0)+1e-12
            means=gamma.T@z/weights[:,None]
            means[0,0]=np.clip(means[0,0],-2.,-.005)
            means[1,0]=0.
            means[2,0]=np.clip(means[2,0],.005,2.)
            variance=max(float(np.sum(gamma*(z-means.T)**2)/len(z)),.0001)
            var[:]=variance
            counts=xi+.1+np.eye(3)*3
            a=counts/counts.sum(axis=1,keepdims=True)
            for j in range(3):
                stay=np.clip(a[j,j],.65,.98);other=np.arange(3)!=j
                a[j,other]*=(1-stay)/a[j,other].sum();a[j,j]=stay
            initial=(gamma[0]+.1)/1.3
    return best


def fit_models(f):
    y=np.log(f.close)
    slow=fit_filter(y,(1e-10,1e-6))
    fast=fit_filter(y,(1e-5,1e-2))
    sigma=float(np.std(np.diff(y)))
    q=kalman(y,fast['ratio'],fast['variance'])
    hmm=fit_hmm(q['slope'][252:]/sigma)
    return dict(slow=slow,fast=fast,hmm=hmm,sigma=sigma,training_end=str(f.days[-1]))


def probabilities(f):
    if 'latent' in f.coupled_cache:return f.coupled_cache['latent']
    m=f.hmm_models;y=np.log(f.close);n=len(y)
    slow=kalman(y,m['slow']['ratio'],m['slow']['variance'])
    fast=kalman(y,m['fast']['ratio'],m['fast']['variance'])
    band=.02*m['sigma']
    def probability(q):
        sd=np.sqrt(np.maximum(q['slope_variance'],1e-20))
        lower=ndtr((-band-q['slope'])/sd)
        upper=ndtr((band-q['slope'])/sd)
        return np.column_stack((lower,upper-lower,1-upper))
    sp,fp=probability(slow),probability(fast)
    h=m['hmm'];emission=trend_hmm.emissions((fast['slope'][252:]/m['sigma'])[:,None],
        np.asarray(h['means']),np.asarray(h['variance']))
    filtered,*_=trend_hmm.forward(emission,np.asarray(h['initial']),np.asarray(h['transition']))
    hp=np.full((n,3),np.nan);hp[252:]=filtered
    result=dict(slow=slow,fast=fast,slow_probability=sp,slope_probability=fp,hmm_probability=hp)
    f.coupled_cache['latent']=result
    return result


def classify(f,p):
    q=probabilities(f)
    fast=q['slope_probability'] if p['family']=='slope' else q['hmm_probability']
    slow=q['slow_probability']
    aligned=slow[:,2]>=.7;counter=slow[:,0]>=.7
    threshold=np.where(aligned & p['context'],.85,p['exit'])
    up=(fast[:,2]>=p['entry']) & (q['fast']['slope']>0)
    down=fast[:,0]>=threshold
    state=np.where(down,-1,np.where(up,1,0))
    context=np.where(counter,-1,np.where(aligned,1,2))
    return dict(parameters=p,fast_probability=fast,slow_probability=slow,
        fast_slope=q['fast']['slope'],slow_slope=q['slow']['slope'],
        fast_variance=q['fast']['slope_variance'],slow_variance=q['slow']['slope_variance'],
        fast_level=q['fast']['level'],slow_level=q['slow']['level'],
        slow_level_variance=q['slow']['level_variance'],fast_level_variance=q['fast']['level_variance'],
        eligible=up,fast_down=down,aligned=aligned,counter=counter,state=state,context=context,
        sigma=f.hmm_models['sigma'])
