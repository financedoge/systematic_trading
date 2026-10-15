"""Registered finite joint selection-width / adoption-threshold research policy."""
from decimal import Decimal

from systematic_trading.research.target_change_rebalance import guards


def select_pair(widths, thresholds, metrics):
    """At least one passing immediate neighbor in the two-dimensional grid."""
    baseline=metrics['6/monthly']
    passing={}
    for width in widths:
        for threshold in thresholds:
            key=f'{width}/{threshold}';candidate=metrics[key]
            passing[key]=guards(candidate['5-0'],baseline['5-0'],.05) and all(
                guards(candidate[s],baseline[s],0.) and candidate[s]['sharpe']>baseline[s]['sharpe']
                for s in ('10-0','5-1'))
    eligible=[]
    for i,width in enumerate(widths):
        for j,threshold in enumerate(thresholds):
            key=f'{width}/{threshold}'
            neighbors=[f'{widths[a]}/{thresholds[b]}' for a,b in ((i-1,j),(i+1,j),(i,j-1),(i,j+1))
                if 0<=a<len(widths) and 0<=b<len(thresholds)]
            if passing[key] and any(passing[k] for k in neighbors):eligible.append(key)
    plateau=[]
    if eligible:
        best=max(metrics[k]['5-0']['sharpe'] for k in eligible)
        plateau=[k for k in eligible if metrics[k]['5-0']['sharpe']>=best-.02]
    def tie(key):
        width,threshold=key.split('/')
        n=Decimal('Infinity') if threshold=='monthly' else Decimal(threshold)
        x=10000 if width=='all' else int(width)
        return metrics[key]['5-0']['annual_turnover'],-n,-x
    selected=min(plateau,key=tie) if plateau else '6/monthly'
    return dict(selected=selected,passing=passing,eligible=eligible,plateau=plateau,metrics=metrics)


def mixed_tape(tapes, switches, *, initial_width='6'):
    """A chronological target tape, with no NAV splicing or anchor reset."""
    days=list(tapes[initial_width])
    if any(list(t)!=days for t in tapes.values()):
        raise ValueError('Selection-width tapes must share the complete calendar')
    width=initial_width;result={}
    for day in days:
        if day in switches:width=switches[day].split('/')[0]
        result[day]=dict(tapes[width][day],selected_width=width)
    return result
