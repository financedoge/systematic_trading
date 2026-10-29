"""Small diagonal Gaussian HMM: training EM and strictly forward inference.

NumPy implementation keeps research native on Python 3.14/Windows. Smoothing is
used only inside training EM, never for historical trading classifications.
"""
from __future__ import annotations

import numpy as np


def emissions(x, means, variances):
    return -.5 * (np.log(2*np.pi*variances)[None,:,:] + (x[:,None,:]-means[None,:,:])**2/variances[None,:,:]).sum(axis=2)


def forward(log_emission, initial, transition):
    offset=log_emission.max(axis=1)
    likelihood=np.exp(np.maximum(log_emission-offset[:,None],-700))
    n,k=likelihood.shape;alpha=np.zeros((n,k));scale=np.zeros(n)
    prior=np.asarray(initial,float)
    for t in range(n):
        row=prior*likelihood[t];scale[t]=row.sum();alpha[t]=row/scale[t]
        prior=alpha[t]@transition
    return alpha,scale,likelihood,float((np.log(scale)+offset).sum())


def expectation(log_emission, initial, transition):
    alpha,scale,likelihood,ll=forward(log_emission,initial,transition)
    beta=np.ones_like(alpha)
    for t in range(len(alpha)-2,-1,-1):beta[t]=transition@(likelihood[t+1]*beta[t+1])/scale[t+1]
    gamma=alpha*beta;gamma/=gamma.sum(axis=1,keepdims=True)
    xi=(alpha[:-1,:,None]*transition[None,:,:]*likelihood[1:,None,:]*beta[1:,None,:]/scale[1:,None,None]).sum(axis=0)
    return gamma,xi,ll


def observations(f, bank, volume):
    values=[np.clip(f.cache[k]['regression']['up']/np.sqrt(k),-10,10) for k in bank]
    values.extend([np.mean([f.cache[k]['efficiency'] for k in bank],axis=0),np.log(np.maximum(f.volatility,1e-6))])
    if volume:values.extend([np.mean([f.cache[k]['pressure'] for k in bank],axis=0),np.log(np.maximum(f.activity,1e-6))])
    return np.column_stack(values)


def fit(x, iterations=25):
    x=np.asarray(x,float)
    if not np.isfinite(x).all() or len(x)<100:raise ValueError('Insufficient finite HMM training observations')
    center=x.mean(axis=0);scale=np.maximum(x.std(axis=0),.05)
    z=np.clip((x-center)/scale,-10,10)
    order=np.argsort(x[:,:4].mean(axis=1));groups=np.array_split(order,3);best=None
    for seed in (17,29):
        rng=np.random.default_rng(seed)
        means=np.array([z[g].mean(axis=0) for g in groups])+rng.normal(0,.05,(3,z.shape[1]))
        variance=np.ones_like(means);initial=np.ones(3)/3;transition=np.full((3,3),.03);np.fill_diagonal(transition,.94)
        history=[]
        for _ in range(iterations):
            gamma,xi,ll=expectation(emissions(z,means,variance),initial,transition);history.append(ll)
            if best is None or ll>best['log_likelihood']:
                raw=means*scale+center;drift=raw[:,:4].mean(axis=1)
                labels=np.full(3,2,int);rank=np.argsort(drift)
                if drift[rank[0]]<-.05:labels[rank[0]]=-1
                if drift[rank[-1]]>.05:labels[rank[-1]]=1
                if abs(drift[rank[1]])<=.15:labels[rank[1]]=0
                best=dict(center=center.tolist(),scale=scale.tolist(),means=means.tolist(),variance=variance.tolist(),
                    initial=initial.tolist(),transition=transition.tolist(),labels=labels.tolist(),state_drift=drift.tolist(),
                    log_likelihood=ll,iterations=len(history),seed=seed,training_rows=len(x))
            weights=gamma.sum(axis=0)+1e-9
            new_means=gamma.T@z/weights[:,None]
            variance=np.maximum(gamma.T@(z*z)/weights[:,None]-new_means**2,.05)
            means=new_means;initial=(gamma[0]+.01)/(gamma[0].sum()+.03)
            counts=xi+.1+np.eye(3)*3.;transition=counts/counts.sum(axis=1,keepdims=True)
            if len(history)>1 and abs(history[-1]-history[-2])<.01:break
    return best


def filtered(x, model):
    x=np.asarray(x,float);valid=np.isfinite(x).all(axis=1);out=np.full((len(x),3),np.nan)
    if not valid.any():return out
    first=int(np.flatnonzero(valid)[0])
    if not valid[first:].all():raise ValueError('Missing HMM observation after warmup')
    z=np.clip((x[first:]-np.array(model['center']))/np.array(model['scale']),-10,10)
    alpha,*_=forward(emissions(z,np.array(model['means']),np.array(model['variance'])),np.array(model['initial']),np.array(model['transition']))
    labels=np.array(model['labels'])
    for j,label in enumerate((-1,0,1)):out[first:,j]=alpha[:,labels==label].sum(axis=1)
    return out


def fit_models(f, fast, slow):
    result={}
    for name,bank in (('fast',fast),('slow',slow)):
        for volume in (False,True):
            x=observations(f,bank,volume);valid=np.isfinite(x).all(axis=1)
            result[name+('_volume' if volume else '_price')]=fit(x[valid])
    return result
