import importlib.util
from pathlib import Path

import pytest

np = pytest.importorskip('numpy', reason='Optional research analysis dependency')

MODULE = Path(__file__).resolve().parents[1] / 'scripts/analyze_flow_concentration_research.py'
spec = importlib.util.spec_from_file_location('flow_analysis', MODULE)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def test_period_return_includes_boundary_day_and_drawdown_from_start():
    economic = dict(nav=[dict(date='2022-12-30', nav='1100000', cash='0'),
                         dict(date='2023-01-03', nav='990000', cash='0'),
                         dict(date='2023-01-04', nav='1089000', cash='0')], fills=[])
    result = analysis.metrics(economic, '2023-01-01', '2023-12-31')
    assert result['total_return'] == pytest.approx(-.01)
    assert result['max_drawdown'] == pytest.approx(-.1)


def test_paired_bootstrap_reproducible_and_family_adjustment_conservative():
    matrix = np.random.default_rng(2).normal(0, .01, (300, 3))
    a = analysis.block_audit(matrix, ['a', 'b', 'c'], replicates=250)
    b = analysis.block_audit(matrix, ['a', 'b', 'c'], replicates=250)
    assert a == b
    for row in a['trials'].values():
        assert row['max_t_family_adjusted_p'] >= row['one_sided_p']
        assert row['ci95'][0] <= row['ci95'][1]


def test_external_benchmark_refuses_missing_session():
    assert analysis.price_benchmark([], {'2023-01-02': '7'}, ['2023-01-03']) is None
