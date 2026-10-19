"""Read-only explanation of the frozen joint lifecycle; exact parity is mandatory."""
from __future__ import annotations
import numpy as np
from .range_joint import History,canonical,WINDOWS,TIME_LIMITS,WIDTH_REFERENCES

REASONS={0:'none',1:'failed_range',2:'initial_or_trailing_stop',3:'time_no_follow_through'}


def range_rows(h:History,p,t):
    """All configured windows, whether or not current state permits a new scan."""
    p=canonical(p)
    _,_,_,_,ub,lb,width,drift,vs,vl,rank,_,_=h.arrays
    tail,block,short,ref=map(int,(p[5],p[7],p[8],p[10]))
    rows=[]
    for j in range(int(p[3]),int(p[4])+1):
        L=int(WINDOWS[j]);w=width[tail,j,t];d=drift[block,j,t];sv=vs[short,j,t];lv=vl[j,t];rk=rank[tail,ref,j,t]
        width_limit=np.log1p(p[0]);width_ok=w<=width_limit if p[2]<.5 else rk<=p[1]
        drift_ok=d<=p[6]*w;vol_ok=sv<=p[9]*lv
        rows.append(dict(index=j,sessions=L,start=t-L,end=t-1,lower=lb[tail,j,t],upper=ub[tail,j,t],width=w,
            width_percent=np.expm1(w),width_limit=width_limit,rank=rk,rank_limit=p[1],reference=WIDTH_REFERENCES[ref],
            drift=d,drift_limit=p[6]*w,short_vol=sv,long_vol=lv,vol_limit=p[9]*lv,
            width_ok=bool(width_ok),drift_ok=bool(drift_ok),vol_ok=bool(vol_ok),
            passes=bool(width_ok and drift_ok and vol_ok)))
    return rows


def trace(h:History,parameters):
    p=canonical(parameters);c,o,v,vsum,ub,lb,width,drift,vs,vl,rank,atr,vol=h.arrays;n=len(c)
    ap,conf,ev,hv=map(int,(p[11],p[13],p[16],p[29]));limit=int(TIME_LIMITS[int(p[30])])
    pending=-1;live=False;heated=False;fill=-1;reset=-1;u=0.;ea=1.;level=0.;volref=0.;dur=0;entry=0.;peak=0.;stop=0.;origin=-1
    rows=[];episodes=[];episode=None
    for t in range(n):
        candidates=range_rows(h,p,t);passing=[r for r in candidates if r['passes']]
        longest=passing[-1] if passing else None;current_atr=atr[ap,t]
        r=dict(i=t,date=str(h.days[t]),state_before='live' if live else 'cooldown' if t<=reset else 'confirming' if pending>=0 else 'seeking',
            state_after='',action='',active=False,stop=np.nan,upper=np.nan,duration=0,exit_reason=0,risk_initial=np.nan,risk_trail=np.nan,
            pending_count=0,episode=None if episode is None else episode['id'],range_scan=False,
            qualifying_index=longest['index'] if longest else -1,qualifying_start=longest['start'] if longest else -1,
            qualifying_end=t-1 if longest else -1,qualifying_upper=longest['upper'] if longest else np.nan,
            qualifying_lower=longest['lower'] if longest else np.nan,
            frozen_start=-1,frozen_end=-1,crossing=-1,confirmation=-1,virtual_entry=-1,entry=np.nan,entry_atr=np.nan,
            frozen_lower=np.nan,frozen_upper=np.nan,breakout_level=np.nan,atr=current_atr,initial_raw=np.nan,initial_floor=np.nan,
            initial_stop=np.nan,range_stop=np.nan,ratchet=np.nan,trail_candidate=np.nan,trail_activation=np.nan,
            trail_enabled=False,peak=np.nan,time_age=-1,time_deadline=-1,time_required=np.nan,time_rule_enabled=limit>0,
            time_failed=False,close_below_initial=False,close_below_stop=False,close_below_range=False,low_below_stop=False,
            heat=False,volume_reference=np.nan,volume_mean=np.nan,previous_below=False,current_above=False,reset_until=reset)
        if t==0:
            r['action']='warmup';r['state_after']=r['state_before'];rows.append(r);continue
        if live:
            if t==fill:
                entry=o[t];peak=o[t];stop=max(0.,entry-p[17]*ea)
                if p[19]>=0:stop=max(stop,u-p[19]*ea)
                effective=max(stop,u-p[18]*ea) if p[18]>=0 else stop
                r['risk_initial']=max(0.,(entry-effective)/entry)
                episode.update(virtual_entry=t,entry=entry,initial_stop=stop,initial_effective=effective)
            peak=max(peak,c[t])
            if p[24]>=.5 and c[t]>=u+p[25]*ea and c[t]>=peak-p[26]*current_atr and v[t]>=p[27]*vol[hv,t]:
                heated=True
            multiplier=p[28] if heated else 1.;proposed=np.nan;activation=entry+p[23]*ea
            if peak>=activation:
                basis=int(p[20])
                proposed=peak*(1-p[22]*multiplier) if basis==2 else peak-p[21]*multiplier*(current_atr if basis==0 else ea)
                stop=max(stop,proposed)
            effective=max(stop,u-p[18]*ea) if p[18]>=0 else stop
            r.update(risk_trail=max(0.,(peak-effective)/peak),stop=effective,upper=u,duration=dur,
                frozen_start=origin-dur,frozen_end=origin-1,crossing=origin,confirmation=episode['confirmation'],
                virtual_entry=fill,entry=entry,entry_atr=ea,frozen_lower=episode['lower'],breakout_level=level,
                initial_raw=entry-p[17]*ea,initial_floor=u-p[19]*ea if p[19]>=0 else np.nan,
                initial_stop=episode['initial_stop'],range_stop=u-p[18]*ea if p[18]>=0 else np.nan,
                ratchet=stop,trail_candidate=proposed,trail_activation=activation,trail_enabled=bool(peak>=activation),
                peak=peak,time_age=t-fill,time_deadline=fill+limit if limit>0 else -1,time_required=entry+p[31]*ea,
                close_below_initial=bool(c[t]<episode['initial_stop']),close_below_stop=bool(c[t]<stop),
                close_below_range=bool(p[18]>=0 and c[t]<u-p[18]*ea),
                heat=heated,volume_reference=volref,episode=episode['id'])
            reason=0
            if p[18]>=0 and c[t]<u-p[18]*ea:reason=1
            elif c[t]<stop:reason=2
            elif limit>0 and t-fill>=limit and peak<entry+p[31]*ea:reason=3
            r['time_failed']=bool(limit>0 and t-fill>=limit and peak<entry+p[31]*ea)
            if reason:
                live=False;reset=t+int(p[32]);r['exit_reason']=reason;r['action']='exit_'+REASONS[reason]
                episode.update(exit_signal=t,exit_reason=reason,peak_at_exit=peak,exit_close=float(c[t]))
            else:
                r['active']=True;r['action']='virtual_fill_and_hold' if t==fill else 'hold'
        elif t<=reset:
            r['action']='cooldown'
        elif pending>=0:
            r.update(pending_count=t-pending+1,crossing=origin,frozen_start=origin-dur,frozen_end=origin-1,
                frozen_lower=episode['lower'] if episode else lb[int(p[5]),WINDOWS.tolist().index(dur),origin],
                breakout_level=level,entry_atr=ea,volume_reference=volref,current_above=bool(c[t]>level))
            if c[t]<=level:
                r['action']='confirmation_cancel_price';pending=-1
            elif t-pending==conf-1:
                mean_volume=(vsum[t+1]-vsum[pending])/(t-pending+1);r['volume_mean']=mean_volume
                if p[14]<.5 or mean_volume>=p[15]*volref:
                    live=True;heated=False;fill=t+1;r.update(active=True,upper=u,duration=dur,action='entry_confirmed')
                    episode=dict(id=len(episodes)+1,crossing=origin,range_start=origin-dur,range_end=origin-1,
                        sessions=dur,upper=u,lower=lb[int(p[5]),WINDOWS.tolist().index(dur),origin],
                        breakout_level=level,entry_atr=ea,confirmation=t,virtual_entry=None,exit_signal=None,exit_reason=None)
                    episodes.append(episode);r.update(episode=episode['id'],confirmation=t,frozen_lower=episode['lower'])
                else:r['action']='confirmation_reject_volume'
                pending=-1
            else:r['action']='confirmation_wait'
        else:
            previous_atr=atr[ap,t-1];r['range_scan']=True
            if not np.isfinite(previous_atr) or previous_atr<=0:
                r['action']='no_positive_prior_atr'
            elif longest is None:
                r['action']='no_qualifying_range'
            else:
                boundary=longest['upper']+p[12]*previous_atr
                r.update(breakout_level=boundary,previous_below=bool(c[t-1]<=boundary),current_above=bool(c[t]>boundary))
                if c[t]>boundary and c[t-1]<=boundary:
                    pending=t;origin=t;level=boundary;u=longest['upper'];ea=previous_atr;volref=vol[ev,t];dur=longest['sessions']
                    r.update(action='breakout_cross',pending_count=1,crossing=t,frozen_start=t-dur,frozen_end=t-1,
                             frozen_lower=longest['lower'],entry_atr=ea,volume_reference=volref)
                    # Discard the old episode only after a new crossing starts.
                    episode=None
                    if conf==1:
                        if p[14]<.5 or v[t]>=p[15]*volref:
                            live=True;heated=False;fill=t+1;r.update(active=True,upper=u,duration=dur,action='entry_confirmed')
                            episode=dict(id=len(episodes)+1,crossing=t,range_start=t-dur,range_end=t-1,sessions=dur,
                                upper=u,lower=longest['lower'],breakout_level=level,entry_atr=ea,confirmation=t,
                                virtual_entry=None,exit_signal=None,exit_reason=None)
                            episodes.append(episode);r.update(episode=episode['id'],confirmation=t)
                        else:r['action']='confirmation_reject_volume'
                        pending=-1
                else:r['action']='above_boundary_without_new_cross' if c[t]>boundary else 'below_breakout_boundary'
        r['reset_until']=reset
        if r['crossing']>=0:
            r['frozen_upper']=u
        r['state_after']='live' if live else 'cooldown' if t<=reset else 'confirming' if pending>=0 else 'seeking'
        rows.append(r)
    # Never let an explanatory implementation silently differ from the original.
    original=h.signals(p)
    for k in ('active','stop','upper','duration','exit_reason'):
        np.testing.assert_allclose(np.array([r[k] for r in rows]),original[k],equal_nan=True,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(np.array([[r['risk_initial'],r['risk_trail']] for r in rows]),original['risk'],equal_nan=True,rtol=1e-12,atol=1e-12)
    return rows,episodes

