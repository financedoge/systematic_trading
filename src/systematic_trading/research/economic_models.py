"""Ex-ante, asset-specific economic response models with frozen small capacity."""
from decimal import Decimal as D
import math

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.construction_controls import gross

FEATURES = ["ICSA", "PERMIT", "IPMAN"]
MODEL_SPEC = dict(version="asset-economic-response-v1",features=FEATURES,
    target="Next scheduled rebalance open / current rebalance open - 1, dividend/split-adjusted USD returns",
    training="Expanding from 2016; only historically fresh vintage features and labels ending by the prior close; at least 36 complete monthly rows",
    tree=dict(max_depth=2,min_samples_leaf=12,criterion="squared_error",random_state=20261007),
    linear="Ridge alpha=1, standardized with training-only means/scales; same rows and labels as the tree",
    prediction="Each ETF's conditional forecast minus its own mean return over the same training rows",
    tilt="Raw multiplier 1.10 for forecast increment >0.25% AND positive absolute forecast, 0.90 for increment below -0.25%, otherwise 1.00; then preserve exact parent gross",
    scope="Only existing positive parent targets; no resurrected ETF or country-sign assumption; original defensive/cash membership retained",
    unavailable="Stale/missing current features or fewer than 36 completed labels: abstain for all assets; integrity errors abort",
    tuning="No hyperparameter, threshold, feature or training-window search")


def vector(state):
    values = [float(state["features"][s]["value"]) for s in FEATURES]
    if not all(math.isfinite(v) for v in values):
        raise ValueError("Nonfinite economic feature")
    return values


def training_rows(day, known, states, opens):
    """Read a label only after its terminal session is known; never current open."""
    days = sorted(states)
    rows = []
    for start, end in zip(days, days[1:]):
        if start >= day or end > known:
            continue
        state = states[start]["state"]
        if not state["ready"]:
            continue
        if state["known_at"][:10] >= start or state["vintage"] >= start:
            raise ValueError("Training feature availability violation")
        labels = {}
        for s, values in opens.items():
            before, after = D(values[start]), D(values[end])
            if not before.is_finite() or not after.is_finite() or min(before, after) <= 0:
                raise ValueError("Invalid audited label prices")
            labels[s] = float(after/before-1)
        rows.append(dict(start=start,end=end,x=vector(state),y=labels,vintage=state["vintage"]))
    return rows


def predict_tree(tree, values):
    node=0
    while tree["left"][node] != -1:
        node=tree["left"][node] if values[tree["feature"][node]] <= tree["threshold"][node] else tree["right"][node]
    return tree["value"][node]


def fit_predict(day, known, states, opens):
    import numpy as np
    from sklearn.linear_model import Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.tree import DecisionTreeRegressor
    rows=training_rows(day,known,states,opens)
    state=states[day]["state"]
    result=dict(version=MODEL_SPEC["version"],decision=day,known_through=known,training_rows=len(rows),
        training_start=rows[0]["start"] if rows else None,last_label_end=rows[-1]["end"] if rows else None,
        training_sha256=digest(encode(rows)),training_labels=rows,ready=False,models={},
        reason="current economics unavailable" if not state["ready"] else "insufficient completed labels")
    if not state["ready"] or len(rows)<36:
        return result
    x=np.array([r["x"] for r in rows]);query=np.array([vector(state)])
    scaler=StandardScaler().fit(x)
    for s in sorted(opens):
        y=np.array([r["y"][s] for r in rows]);mean=float(y.mean());centered=y-mean
        tree=DecisionTreeRegressor(**MODEL_SPEC["tree"]).fit(x,centered)
        linear=Ridge(alpha=1).fit(scaler.transform(x),centered)
        prediction=float(tree.predict(query)[0]);ridge=float(linear.predict(scaler.transform(query))[0])
        frozen=dict(left=tree.tree_.children_left.tolist(),right=tree.tree_.children_right.tolist(),
            feature=tree.tree_.feature.tolist(),threshold=tree.tree_.threshold.tolist(),value=tree.tree_.value[:,0,0].tolist(),
            samples=tree.tree_.n_node_samples.tolist())
        # sklearn uses float32 for tree inference. Freeze that exact input basis.
        if abs(predict_tree(frozen,query[0].astype(np.float32))-prediction)>1e-12:
            raise ValueError("Frozen tree prediction differs")
        result["models"][s]=dict(mean_return=mean,tree_increment=prediction,linear_increment=ridge,
            tree_forecast=mean+prediction,linear_forecast=mean+ridge,tree=frozen,
            linear=dict(coefficients=linear.coef_.tolist(),intercept=float(linear.intercept_),
                        feature_means=scaler.mean_.tolist(),feature_scales=scaler.scale_.tolist()))
    result.update(ready=True,reason="fitted on completed historical labels only",query=vector(state))
    return result


def tilt(targets, fitted, kind):
    total=gross(targets)
    if kind not in {"tree","linear"} or type(fitted.get("ready")) is not bool:
        raise ValueError("Invalid economic model result")
    if not fitted["ready"]:
        return list(targets)
    multipliers={}
    for t in targets:
        value=D(str(fitted["models"][t.symbol][kind+"_increment"]))
        if not value.is_finite():raise ValueError("Invalid economic forecast")
        absolute=D(str(fitted["models"][t.symbol][kind+"_forecast"]))
        if not absolute.is_finite():raise ValueError("Invalid absolute economic forecast")
        multipliers[t.symbol]=D("1.10") if value>D(".0025") and absolute>0 else D(".90") if value<D("-.0025") else D(1)
    weighted=sum((t.target_weight*multipliers[t.symbol] for t in targets),D(0))
    if not weighted or len({multipliers[t.symbol] for t in targets if t.target_weight>0})<=1:
        return list(targets)
    result=[t.model_copy(update=dict(target_weight=t.target_weight*multipliers[t.symbol]*total/weighted,
        rationale=t.rationale+f" Asset-specific {kind} economic response; raw multiplier {multipliers[t.symbol]}, parent gross preserved.")) for t in targets]
    # Reconcile decimal rounding deterministically without changing membership.
    residual=total-gross(result)
    index=max(range(len(result)),key=lambda i:result[i].target_weight)
    result[index]=result[index].model_copy(update=dict(target_weight=result[index].target_weight+residual))
    return result
