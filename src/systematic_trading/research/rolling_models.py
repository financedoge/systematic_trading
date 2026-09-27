"""Causal monthly research fits and portable inference for bounded tree ensembles.

Training dependencies are optional. Frozen inference uses only the standard
library, including inside the isolated LEAN worker. No execution authority.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date
import hashlib
import json
import math
import struct

from systematic_trading.signals.decision_tree import (
    DecisionTreeSample, SimpleDecisionTreeModel, train_simple_regression_tree,
)


def float32(value):
    return struct.unpack('f', struct.pack('f', value))[0]


class PortableEnsemble:
    def __init__(self, payload):
        if payload.get('schema_version') != 1 or payload.get('kind') not in ('forest', 'xgboost'):
            raise ValueError('Unsupported portable ensemble')
        self.payload = payload
        self.feature_names = tuple(payload['feature_names'])
        self.max_depth = payload['max_depth']

    def predict(self, features):
        values = [float32(float(features[f])) if features.get(f) is not None else math.nan
                  for f in self.feature_names]
        if not all(math.isfinite(v) for v in values):
            raise ValueError('Portable research ensembles require complete finite features')
        total = 0.0
        for tree in self.payload['trees']:
            node = 0
            while tree['left'][node] >= 0:
                v, threshold = values[tree['feature'][node]], tree['threshold'][node]
                left = v <= threshold if self.payload['kind'] == 'forest' else v < threshold
                node = tree['left'][node] if left else tree['right'][node]
            total += tree['value'][node]
            if self.payload['kind'] == 'xgboost':
                total = float32(total)
        return total / len(self.payload['trees']) if self.payload['kind'] == 'forest' else total


def load_model(payload):
    if 'kind' in payload:
        return PortableEnsemble(payload)
    return SimpleDecisionTreeModel.from_dict(payload)


def window_start(cutoff, years):
    d = date.fromisoformat(cutoff)
    return date(d.year-years, d.month, min(d.day, monthrange(d.year-years, d.month)[1])).isoformat()


def training_rows(records, cutoff, years, features):
    """Origin in trailing calendar years; a one-session label embargo at fit close."""
    lower = window_start(cutoff, years) if years else '0001-01-01'
    rows = [r for r in records if lower <= r['known_through'] < cutoff
            and r['known_through'] < r['label_end'] < cutoff]
    # Missing prices/features are excluded, never filled with later values.
    return [r for r in rows if all(r['inputs'].get(f) is not None and math.isfinite(r['inputs'][f])
                                  for f in features) and math.isfinite(r['relative_return'])]


def fit_model(rows, features, family, *, seed=20260927):
    if len(rows) < 100:
        raise ValueError('Fewer than 100 complete causal asset-month training observations')
    if family == 'tree':
        model = train_simple_regression_tree(
            [DecisionTreeSample(features=r['inputs'], target=r['relative_return']) for r in rows],
            feature_names=features, max_depth=3, min_samples_leaf=25)
        return model.to_dict(), {'family': family, 'max_depth': 3, 'min_samples_leaf': 25}
    import numpy as np
    x = np.array([[r['inputs'][f] for f in features] for r in rows], dtype=np.float32)
    y = np.array([r['relative_return'] for r in rows])
    if family == 'forest':
        from sklearn.ensemble import RandomForestRegressor
        settings = dict(n_estimators=100, max_depth=3, min_samples_leaf=25,
                        max_features=.75, bootstrap=True, random_state=seed, n_jobs=1)
        native = RandomForestRegressor(**settings).fit(x, y)
        trees = [dict(left=t.tree_.children_left.tolist(), right=t.tree_.children_right.tolist(),
                      feature=t.tree_.feature.tolist(), threshold=t.tree_.threshold.tolist(),
                      value=t.tree_.value[:, 0, 0].tolist()) for t in native.estimators_]
    elif family == 'xgboost':
        from xgboost import XGBRegressor
        settings = dict(n_estimators=100, max_depth=3, learning_rate=.03,
                        min_child_weight=25, subsample=.8, colsample_bytree=.75,
                        reg_lambda=10, reg_alpha=0, objective='reg:squarederror',
                        tree_method='hist', base_score=0, random_state=seed, n_jobs=1)
        native = XGBRegressor(**settings).fit(x, y)
        raw = json.loads(native.get_booster().save_raw(raw_format='json'))
        trees = [dict(left=t['left_children'], right=t['right_children'], feature=t['split_indices'],
                      threshold=[float32(v) for v in t['split_conditions']],
                      value=[float32(v) for v in t['split_conditions']])
                 for t in raw['learner']['gradient_booster']['model']['trees']]
    else:
        raise ValueError('Unknown model family: '+family)
    payload = dict(schema_version=1, kind=family, feature_names=list(features), max_depth=3, trees=trees)
    portable = PortableEnsemble(payload)
    predictions = np.array([portable.predict(r['inputs']) for r in rows])
    error = float(np.max(np.abs(predictions-native.predict(x))))
    if error > 1e-7:
        raise ValueError(f'Portable {family} prediction mismatch: {error}')
    return payload, dict(family=family, settings=settings, native_prediction_max_error=error)


def fit_record(records, cutoff, years, features, family, *, seed=20260927):
    rows = training_rows(records, cutoff, years, features)
    model, details = fit_model(rows, features, family, seed=seed)
    identity = [(r['symbol'], r['known_through'], r['label_end'], r['inputs'], r['relative_return']) for r in rows]
    return dict(fit_as_of=cutoff, window_years=years, window_start=window_start(cutoff, years) if years else None,
                min_feature_date=min(r['known_through'] for r in rows),
                max_feature_date=max(r['known_through'] for r in rows),
                max_label_end=max(r['label_end'] for r in rows), training_samples=len(rows),
                training_months=len({r['known_through'] for r in rows}),
                training_sha256=hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest(),
                embargo='label_end strictly before fit close', details=details, model=model)
