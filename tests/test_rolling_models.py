from copy import deepcopy
from datetime import date, timedelta
import importlib.util
import math

import pytest

from systematic_trading.research.chronological_tree import select_base_tree
from systematic_trading.research.rolling_models import (
    PortableEnsemble, fit_record, fit_model, training_rows, window_start,
)


def rows():
    return [dict(symbol=str(i % 12), known_through=str(date(2022, 1, 1)+timedelta(days=i)),
                 label_end=str(date(2022, 2, 1)+timedelta(days=i)),
                 inputs={'a': math.sin(i*.07), 'b': math.cos(i*.09)},
                 relative_return=math.sin(i*.07)*.06+math.cos(i*.09)*.015)
            for i in range(360)]


def test_rolling_bounds_and_label_embargo_are_strict():
    records = [dict(symbol='A', known_through=d, label_end=e, inputs={'x': x}, relative_return=.1)
               for d, e, x in [('2023-02-28', '2023-03-31', 1), ('2023-02-27', '2023-03-31', 1),
                               ('2024-01-01', '2024-02-29', 1), ('2024-01-01', '2024-02-28', 1),
                               ('2024-01-02', '2024-02-28', None), ('2024-01-03', '2024-02-28', math.nan)]]
    accepted = training_rows(records, '2024-02-29', 1, ['x'])
    assert [r['known_through'] for r in accepted] == ['2023-02-28', '2024-01-01']
    assert window_start('2024-02-29', 1) == '2023-02-28'


def test_future_labels_and_outside_window_cannot_change_fit():
    original = rows()
    record = fit_record(original, '2023-01-01', 1, ['a', 'b'], 'tree')
    changed = deepcopy(original)
    for r in changed:
        if r['label_end'] >= '2023-01-01':
            r['relative_return'] = 9999
            r['inputs'] = {'a': -999, 'b': -999}
    assert fit_record(changed, '2023-01-01', 1, ['a', 'b'], 'tree') == record
    assert record['max_label_end'] < record['fit_as_of']
    assert record['min_feature_date'] >= record['window_start']
    schedule = {'2023-01-01': record}
    with pytest.raises(ValueError, match='No historical'):
        select_base_tree(schedule, '2022-12-31')
    with pytest.raises(ValueError, match='future'):
        select_base_tree({'2023-01-01': dict(record, max_label_end='2023-01-01')}, '2023-01-02')
    with pytest.raises(ValueError, match='outside'):
        select_base_tree({'2023-01-01': dict(record, min_feature_date='2021-12-31')}, '2023-01-02')


@pytest.mark.parametrize('family', ['forest', 'xgboost'])
def test_portable_ensemble_matches_native_on_unseen_inputs(family):
    if importlib.util.find_spec('sklearn') is None or importlib.util.find_spec('xgboost') is None:
        pytest.skip('Optional rolling-research training dependencies')
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor
    from xgboost import XGBRegressor
    records = rows()
    payload, details = fit_model(records, ['a', 'b'], family)
    estimator = RandomForestRegressor if family == 'forest' else XGBRegressor
    x = np.array([[r['inputs'][f] for f in ['a', 'b']] for r in records], dtype=np.float32)
    native = estimator(**details['settings']).fit(x, [r['relative_return'] for r in records])
    unseen = np.random.default_rng(89).uniform(-2, 2, size=(500, 2)).astype(np.float32)
    portable = PortableEnsemble(payload)
    actual = [portable.predict({'a': a, 'b': b}) for a, b in unseen]
    assert np.max(np.abs(actual-native.predict(unseen))) < 1e-7
    assert len(set(actual)) > 5  # Exercise branches, not only constant trees.
    with pytest.raises(ValueError, match='finite'):
        portable.predict({'a': None, 'b': 1})


def test_portable_split_semantics_and_float32_boundary():
    tree = dict(left=[1, -1, -1], right=[2, -1, -1], feature=[0, 0, 0],
                threshold=[1., 0., 0.], value=[0., -.1, .2])
    forest = PortableEnsemble(dict(schema_version=1, kind='forest', max_depth=1, feature_names=['x'], trees=[tree]))
    xgb = PortableEnsemble(dict(schema_version=1, kind='xgboost', max_depth=1, feature_names=['x'], trees=[tree]))
    assert forest.predict({'x': 1+1e-10}) == -.1  # sklearn casts to float32 before <=.
    assert xgb.predict({'x': 1}) == pytest.approx(.2)  # XGBoost uses strict <.


def test_unknown_model_and_inadequate_training_fail_closed():
    with pytest.raises(ValueError, match='Unsupported'):
        PortableEnsemble(dict(kind='unknown', schema_version=1))
    with pytest.raises(ValueError, match='100'):
        fit_model(rows()[:50], ['a', 'b'], 'tree')
