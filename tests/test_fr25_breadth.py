from pathlib import Path
import sys

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import research_fr25_breadth as study


@pytest.mark.parametrize('pool,threshold', [(14,4),(45,13),(49,14),(52,15)])
def test_proportional_breadth_rounds_up(pool, threshold):
    assert study.required_count(4,14,pool) == threshold


def test_breadth_is_independent_of_width_and_equality_passes():
    # The first axis denotes decision date, row zero the defensive targets.
    table = np.arange(3*7*2).reshape(3,7,2)
    selected = study.training_path(table, np.array([14,15,16]), 2,15)
    np.testing.assert_array_equal(selected, np.stack([table[0,0],table[1,2],table[2,2]]))


def test_selection_uses_requested_prefix_and_predeclared_tie_order():
    def row(m,n,is_sharpe,later):
        return dict(m=m,n=n,prefix={'2024':{'sharpe':is_sharpe}},later={'sharpe':later})
    grid=[row(1,1,.8,100),row(5,15,.9,2),row(6,15,.9,1),row(6,14,.9,4)]
    assert study.best(grid,'2024') is grid[2]
