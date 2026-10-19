"""Bounded two-dimensional GLD confirmation/patience experiment."""
import numpy as np
from .range_joint import canonical, TIME_LIMITS

CONFIRMATIONS=(1,2,3,4,5,6,8)
DEADLINES=(5,10,20,42,63,126,0)  # zero removes the time rule
OBJECTIVES=('raw','moderate','strong','stable','neighbor')


def candidate_id(confirmation,deadline):
    return f'c{confirmation:02d}_t{deadline:03d}'


def candidates(base):
    result={}
    for c in CONFIRMATIONS:
        for d in DEADLINES:
            p=canonical(base);p[13]=c;p[30]=int(np.flatnonzero(TIME_LIMITS==d)[0])
            result[candidate_id(c,d)]=dict(confirmation=c,deadline=d,parameters=p.tolist())
    return result


def neighbors(c,d):
    ci,di=CONFIRMATIONS.index(c),DEADLINES.index(d)
    return [candidate_id(CONFIRMATIONS[i],DEADLINES[j]) for i,j in
        ((ci,di),(ci-1,di),(ci+1,di),(ci,di-1),(ci,di+1))
        if 0<=i<len(CONFIRMATIONS) and 0<=j<len(DEADLINES)]


def scores(exact):
    return {name:min(s['components'][name] for s in exact['scenarios'].values())
            for name in OBJECTIVES if name!='neighbor'}


def fit_variants(rows):
    for row in rows.values():
        values=[rows[k]['scores']['moderate'] if rows[k]['evidence'] else -10.
                for k in neighbors(row['confirmation'],row['deadline'])]
        row['scores']['neighbor']=float(np.median(values)-.5*np.std(values))
        row['neighbors']=neighbors(row['confirmation'],row['deadline'])
    feasible={k:r for k,r in rows.items() if r['evidence']}
    if not feasible:raise ValueError('No sufficiently supported IS candidate')
    passing={k:r for k,r in feasible.items() if r['exact']['guard_pass']}
    pool=passing or feasible
    variants={name:min(pool,key=lambda k:(-pool[k]['scores'][name],pool[k]['deadline']!=0,
                    pool[k]['confirmation'],-pool[k]['deadline'],k)) for name in OBJECTIVES}
    return dict(variants=variants,IS_guard_pool=bool(passing),feasible=len(feasible))


def select_validation(rows,grid,tolerance=.03):
    passing={k:r for k,r in rows.items() if r['guard_pass']}
    pool=passing or rows
    best=max(r['score'] for r in pool.values())
    near=[k for k,r in pool.items() if r['score']>=best-tolerance]
    chosen=min(near,key=lambda k:(pool[k]['scenarios']['5:0']['metrics']['annual_turnover'],
                                grid[k]['deadline']!=0,grid[k]['confirmation'],-grid[k]['deadline'],k))
    return dict(selected=chosen,guard_pass=bool(passing),best_score=best,near_ties=near)
