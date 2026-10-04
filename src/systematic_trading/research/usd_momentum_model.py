"""Small fixed ridge ablation: identical sample, model budget and portfolio tilt."""
from decimal import Decimal as D

from systematic_trading.research.flow_concentration import FlowConcentrationSpec, apply_concentration_targets
from systematic_trading.signals.trend import _rank_metric


def ridge_predict(records,current,fit_close,use_usd):
    import numpy as np
    train=[r for r in records if r['label_end']<fit_close and r['known_through']<fit_close]
    if len({r['known_through'][:7] for r in train})<60:
        return None
    symbols=sorted(current)
    prediction={};details={}
    columns=['S','L','vol63']+(['USD21','USD63'] if use_usd else [])
    for s in symbols:
        sample=[r for r in train if r['symbol']==s]
        if len(sample)<60:raise ValueError('Incomplete matched USD training panel')
        x=np.asarray([[r['features'][k] for k in columns] for r in sample]);y=np.asarray([r['label'] for r in sample])
        mean=x.mean(axis=0);scale=x.std(axis=0);scale=np.where(scale>1e-12,scale,1.)
        z=(x-mean)/scale;intercept=y.mean()
        # Objective mean squared error + 1.0 ||beta||^2; no tuning.
        beta=np.linalg.solve(z.T@z+len(y)*np.eye(len(columns)),z.T@(y-intercept))
        prediction[s]=float(intercept+((np.array([current[s][k] for k in columns])-mean)/scale)@beta)
        details[s]=dict(features=columns,coefficients=beta.tolist(),means=mean.tolist(),scales=scale.tolist(),
                        intercept=float(intercept),training_months=len(y),max_label_end=max(r['label_end'] for r in sample))
    return dict(predictions=prediction,models=details,fit_close=fit_close)


def apply_usd_predictions(targets,predictions):
    ranks=_rank_metric({s:D(str(v)) for s,v in predictions.items()})
    features={s:dict(signal=v) for s,v in ranks.items()}
    tilted=apply_concentration_targets(targets,features,FlowConcentrationSpec(relative_tilt=.12,active_cap=.03))
    return [t.model_copy(update=dict(rationale=t.rationale.rsplit('; research activity',1)[0]+'; registered ridge prediction rank tilt')) for t in tilted]
