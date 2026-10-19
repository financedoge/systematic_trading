"""Joint lifecycle research: bounded mixed parameters, causal state, explicit utility.

Numba is optional acceleration for the finite optimizer. The identical Python
function remains the reference implementation; no JIT dependency reaches trading.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd

try:
    from numba import njit
except ImportError:
    def njit(*args, **kwargs):
        def decorate(fn):
            fn.py_func = fn
            return fn
        return decorate


WINDOWS = np.array([21,42,63,126,252,504,756,1008,1260])
TAILS = (.01,.05,.10,.20)
WIDTH_REFERENCES = (252,756,1260)
ATR_PERIODS = (5,10,20,40,60)
VOLUME_PERIODS = (20,63,126,252)
TIME_LIMITS = np.array([0,5,10,20,42,63,126])

# name, lower, upper, integral; inactive conditional dimensions remain explicit.
PARAMETERS = (
    ('absolute_width',.05,1.,False), ('relative_width_percentile',.1,.9,False),
    ('range_basis',0,1,True), ('minimum_window_index',0,4,True), ('maximum_window_index',3,8,True),
    ('band_tail_index',0,3,True), ('maximum_drift_fraction',.05,1.,False),
    ('drift_block_index',0,2,True), ('short_vol_fraction_index',0,2,True),
    ('maximum_short_long_vol_ratio',.4,1.6,False), ('width_reference_index',0,2,True),
    ('atr_period_index',0,4,True), ('breakout_buffer_atr',0.,2.,False),
    ('confirmation_sessions',1,10,True), ('volume_confirmation',0,1,True),
    ('confirmation_volume_ratio',.75,3.,False), ('entry_volume_reference_index',0,3,True),
    ('initial_stop_atr',.5,12.,False), ('failed_range_buffer_atr',-1.,6.,False),
    ('initial_upper_floor_atr',-1.,6.,False), ('trailing_basis',0,2,True),
    ('trailing_atr',1.,20.,False), ('trailing_percentage',.04,.40,False),
    ('trailing_activation_gain_atr',0.,6.,False), ('heat_enabled',0,1,True),
    ('heat_extension_atr',1.,12.,False), ('heat_near_high_atr',.25,4.,False),
    ('heat_volume_ratio',1.,5.,False), ('heat_trail_multiplier',.2,1.,False),
    ('heat_volume_reference_index',0,3,True), ('time_exit_index',0,6,True),
    ('time_exit_required_gain_atr',0.,4.,False), ('cooldown_sessions',0,63,True),
)
BOUNDS = np.array([(p[1],p[2]) for p in PARAMETERS])
INTEGRAL = np.array([p[3] for p in PARAMETERS])


def canonical(parameters):
    p=np.asarray(parameters,float).copy()
    if p.shape!=(len(PARAMETERS),) or not np.isfinite(p).all():
        raise ValueError('Invalid joint parameter vector')
    p=np.clip(p,BOUNDS[:,0],BOUNDS[:,1]);p[INTEGRAL]=np.round(p[INTEGRAL])
    p[4]=max(p[3],p[4])
    return p


def v1_anchor():
    return canonical([.25,.5,0,1,6,1,.5,1,1,1.,1,2,.5,3,1,1.2,1,2,.5,1,0,4,.2,0,1,3,1,2,.5,1,3,1,21])


def describe(p):
    p=canonical(p)
    result={row[0]:int(x) if row[3] else float(x) for row,x in zip(PARAMETERS,p,strict=True)}
    result.update(windows=WINDOWS[int(p[3]):int(p[4])+1].tolist(),band_tail=TAILS[int(p[5])],
        atr_period=ATR_PERIODS[int(p[11])],volume_reference=VOLUME_PERIODS[int(p[16])],
        heat_volume_reference=VOLUME_PERIODS[int(p[29])],time_exit_sessions=int(TIME_LIMITS[int(p[30])]),
        trailing_basis_name=('current_atr','entry_atr','percent')[int(p[20])],
        range_basis_name=('absolute','relative')[int(p[2])])
    return result


@dataclass
class History:
    arrays: tuple
    days: np.ndarray

    @classmethod
    def build(cls,a):
        c,o,h,lo,v=(np.asarray(a[k],float) for k in ('close','open','high','low','volume'))
        if any(x.shape!=c.shape or not np.isfinite(x).all() or (x<=0).any() for x in (o,h,lo,v,c)):
            raise ValueError('Unsupported price/volume observations')
        if np.any(h<c) or np.any(lo>c) or np.any(h<lo):
            raise ValueError('Inconsistent OHLC')
        n=len(c);x=pd.Series(np.log(c));r=x.diff()
        upper,lower,width=(np.full((4,9,n),np.nan) for _ in range(3))
        drift,shortvol=(np.full((3,9,n),np.nan) for _ in range(2))
        longvol=np.full((9,n),np.nan);rank=np.full((4,3,9,n),np.nan)
        for j,L in enumerate(WINDOWS):
            roll=x.rolling(int(L),min_periods=int(L))
            longvol[j]=r.rolling(int(L)-1).std().shift(1).to_numpy()
            for k,q in enumerate(TAILS):
                lowq=roll.quantile(q).shift(1).to_numpy();upq=roll.quantile(1-q).shift(1).to_numpy()
                upper[k,j],lower[k,j],width[k,j]=np.exp(upq),np.exp(lowq),upq-lowq
                for z,ref in enumerate(WIDTH_REFERENCES):
                    # Every W is already prior-close data. Today's known W is
                    # included in the empirical rank; no crossing close enters.
                    rank[k,z,j]=pd.Series(width[k,j]).rolling(ref,min_periods=252).rank(pct=True).to_numpy()
            for k,frac in enumerate((.1,.25,.5)):
                block=min(63,max(10,int(L*frac)))
                med=x.rolling(block).median()
                drift[k,j]=(med-med.shift(int(L)-block)).abs().shift(1).to_numpy()
            for k,frac in enumerate((.15,1/3,.5)):
                count=min(63,max(5,int(L)//3 if k==1 else int(L*frac)))
                shortvol[k,j]=r.rolling(count).std().shift(1).to_numpy()
        tr=np.maximum(h-lo,np.maximum(np.abs(h-np.r_[c[0],c[:-1]]),np.abs(lo-np.r_[c[0],c[:-1]])))
        atr=np.array([pd.Series(tr).rolling(L).mean().to_numpy() for L in ATR_PERIODS])
        volume=np.array([pd.Series(v).rolling(L).median().shift(1).to_numpy() for L in VOLUME_PERIODS])
        packed=(c,o,v,np.r_[0,np.cumsum(v)],upper,lower,width,drift,shortvol,longvol,rank,atr,volume)
        return cls(tuple(np.ascontiguousarray(x) for x in packed),np.asarray(a['days']))

    def signals(self,p):
        active,stop,upper,duration,reasons,risk=lifecycle_joint(canonical(p),*self.arrays)
        return dict(active=active,stop=stop,upper=upper,duration=duration,exit_reason=reasons,risk=risk)


@njit(cache=True)
def lifecycle_joint(p,c,o,v,vsum,ub,lb,width,drift,vs,vl,wrank,atr,vol):
    n=len(c);active=np.zeros(n,np.bool_);stops=np.full(n,np.nan)
    uppers=np.full(n,np.nan);duration=np.zeros(n,np.int64);reasons=np.zeros(n,np.int8)
    mode,mn,mx,tail=int(p[2]),int(p[3]),int(p[4]),int(p[5])
    block,short,ref,ap=int(p[7]),int(p[8]),int(p[10]),int(p[11])
    conf,ev,hv=int(p[13]),int(p[16]),int(p[29])
    limit=TIME_LIMITS[int(p[30])]
    pending=-1;live=False;heated=False;fill=-1;reset=-1
    u=0.;ea=1.;level=0.;volref=0.;dur=0;entry=0.;peak=0.;stop=0.
    risk=np.full((n,2),np.nan)
    for t in range(1,n):
        current_atr=atr[ap,t]
        if live:
            if t==fill:
                entry=o[t];peak=o[t];stop=max(0.,entry-p[17]*ea)
                if p[19]>=0:
                    stop=max(stop,u-p[19]*ea)
                effective=stop
                if p[18]>=0:
                    effective=max(effective,u-p[18]*ea)
                distance=max(0.,(entry-effective)/entry)
                risk[t,0]=distance
            peak=max(peak,c[t])
            if p[24]>=.5 and c[t]>=u+p[25]*ea and c[t]>=peak-p[26]*current_atr and v[t]>=p[27]*vol[hv,t]:
                heated=True
            multiplier=p[28] if heated else 1.
            if peak>=entry+p[23]*ea:
                basis=int(p[20])
                proposed=peak*(1-p[22]*multiplier) if basis==2 else peak-p[21]*multiplier*(current_atr if basis==0 else ea)
                stop=max(stop,proposed)
            effective=stop
            if p[18]>=0:
                effective=max(effective,u-p[18]*ea)
            distance=max(0.,(peak-effective)/peak)
            risk[t,1]=distance
            stops[t]=effective;uppers[t]=u;duration[t]=dur
            reason=0
            if p[18]>=0 and c[t]<u-p[18]*ea:
                reason=1
            elif c[t]<stop:
                reason=2
            elif limit>0 and t-fill>=limit and peak<entry+p[31]*ea:
                reason=3
            if reason:
                live=False;reset=t+int(p[32]);reasons[t]=reason
            else:
                active[t]=True
            continue
        if t<=reset:
            continue
        if pending>=0:
            if c[t]<=level:
                pending=-1
                continue
            if t-pending==conf-1:
                mean_volume=(vsum[t+1]-vsum[pending])/(t-pending+1)
                if p[14]<.5 or mean_volume>=p[15]*volref:
                    live=True;heated=False;fill=t+1;active[t]=True;uppers[t]=u;duration[t]=dur
                pending=-1
            continue
        previous_atr=atr[ap,t-1]
        if not np.isfinite(previous_atr) or previous_atr<=0:
            continue
        chosen=-1
        for j in range(mx,mn-1,-1):
            w=width[tail,j,t]
            narrow=w<=np.log1p(p[0]) if mode==0 else wrank[tail,ref,j,t]<=p[1]
            if narrow and drift[block,j,t]<=p[6]*w and vs[short,j,t]<=p[9]*vl[j,t]:
                chosen=j
                break
        if chosen<0:
            continue
        boundary=ub[tail,chosen,t]+p[12]*previous_atr
        if c[t]>boundary and c[t-1]<=boundary:
            pending=t;level=boundary;u=ub[tail,chosen,t];ea=previous_atr;volref=vol[ev,t];dur=WINDOWS[chosen]
            if conf==1:
                if p[14]<.5 or v[t]>=p[15]*volref:
                    live=True;heated=False;fill=t+1;active[t]=True;uppers[t]=u;duration[t]=dur
                pending=-1
    return active,stops,uppers,duration,reasons,risk


@njit(cache=True)
def screen_stats(c,o,active,start,end,cost=5.,delay=0):
    """Fractional held units for screening only; four rows = full +3 IS blocks.

    Columns: CAGR,Sharpe,regularized Calmar,maxDD,exposure,correlation,closed trades.
    Accounts do not reset at block boundaries. Risk-free rate is zero.
    """
    size=end-start;cash=1.;q=0.;adopted=False;previous=1.
    sums=np.zeros((4,7));peaks=np.ones(4);first=np.ones(4);last=np.ones(4);dd=np.zeros(4)
    counts=np.zeros(4,np.int64);closed=np.zeros(4,np.int64)
    for t in range(start,end):
        b=1+min(2,(t-start)*3//size)
        if counts[b]==0:
            peaks[b]=previous;first[b]=previous
        want=active[t-1-delay] if t-1-delay>=0 else False
        sold=False
        if want!=adopted:
            if not want:
                cash+=q*o[t]*(1-cost/10000);q=0.;sold=True
            else:
                amount=.98*cash;q=amount/o[t];cash-=amount*(1+cost/10000)
            adopted=want
        nav=cash+q*c[t];r=nav/previous-1;ar=c[t]/c[t-1]-1
        for j in (0,b):
            counts[j]+=1;closed[j]+=int(sold)
            sums[j,0]+=r;sums[j,1]+=r*r;sums[j,2]+=ar;sums[j,3]+=ar*ar;sums[j,4]+=r*ar
            sums[j,5]+=q*c[t]/nav
            peaks[j]=max(peaks[j],nav);dd[j]=min(dd[j],nav/peaks[j]-1);last[j]=nav
        previous=nav
    result=np.zeros((4,7))
    for j in range(4):
        count=max(1,counts[j]);mean=sums[j,0]/count
        variance=max(0.,(sums[j,1]-sums[j,0]*mean)/max(1,count-1));sd=np.sqrt(variance)
        cagr=(last[j]/first[j])**(252./count)-1
        avar=max(0.,(sums[j,3]-sums[j,2]**2/count)/max(1,count-1))
        cov=(sums[j,4]-sums[j,0]*sums[j,2]/count)/max(1,count-1)
        corr=cov/(sd*np.sqrt(avar)) if sd>1e-12 and avar>1e-24 else 0.
        result[j,0]=cagr;result[j,1]=mean/sd*np.sqrt(252) if sd>1e-12 else 0.
        result[j,2]=cagr/max(.03,-dd[j]);result[j,3]=dd[j];result[j,4]=sums[j,5]/count
        result[j,5]=min(1.,max(-1.,corr));result[j,6]=closed[j]
    return result


def utility(stats,buyhold):
    """45/40/15; returns in 10pp units, capped *levels* of S/Calmar suppress cash tricks."""
    r=(np.clip(stats[:,0],-1,1)-np.clip(buyhold[:,0],-1,1))/.10
    s=np.clip(stats[:,1],-3,3)-np.clip(buyhold[:,1],-3,3)
    c=np.clip(stats[:,2],-3,3)-np.clip(buyhold[:,2],-3,3)
    return .45*r+.40*s+.15*c


def penalties(stats,risk):
    hold=np.clip((stats[0,4]-.85)/.15,0,1)*np.clip((stats[0,5]-.85)/.15,0,1)
    stop=.5*(min(3.,risk[2])+min(3.,risk[3]))
    scarcity=max(0.,12-stats[0,6])/12
    return float(hold),float(stop),float(scarcity)


def risk_stats(tapes,opens,start,end):
    """Only the evaluated window can contribute risk penalties, including a fresh account entry."""
    values=tapes['risk'][start:end]
    initial=values[np.isfinite(values[:,0]),0]
    trail=values[np.isfinite(values[:,1]),1]
    if start>0 and tapes['active'][start-1] and not np.isfinite(values[0,0]):
        stop=tapes['stop'][start-1]
        if np.isfinite(stop):
            initial=np.r_[max(0.,(opens[start]-stop)/opens[start]),initial]
    return np.array([initial.mean() if len(initial) else 0.,trail.mean() if len(trail) else 0.,
        np.maximum(0.,initial-.10).mean()/.10 if len(initial) else 0.,
        np.maximum(0.,trail-.20).mean()/.20 if len(trail) else 0.,len(initial)])


def objective_components(stats,buyhold,risk):
    u=utility(stats,buyhold);hold,stop,scarcity=penalties(stats,risk)
    penalty=.20*hold+.20*stop
    chronology=.5*u[0]+.5*np.median(u[1:])-.25*np.std(u[1:])
    return dict(raw=float(u[0]),weak=float(u[0]-.5*penalty),moderate=float(u[0]-penalty),
        strong=float(u[0]-2*penalty),stable=float(chronology-penalty-.10*scarcity),
        hold_penalty=hold,stop_penalty=stop,scarcity_penalty=scarcity)
