from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from audit_strategy_health import audit_trades, null_run_probability  # noqa:E402


def test_mfe_does_not_include_exit_day_close_or_future_open_trade():
    c = dict(days=[f"2023-01-0{i}" for i in range(1, 7)], close=[100, 102, 101, 500, 100, 102],
             evaluation_start="2023-01-02", nav=[100]*6, trades=[
                 dict(entry="2023-01-02", exit="2023-01-04", entry_price=100, exit_price=99,
                      net_return=-.011, reason="protection"),
                 dict(entry="2023-01-05", exit=None, net_return=.02)])
    rows = audit_trades(c)
    assert len(rows) == 1
    assert rows[0]["close_mfe"] == pytest.approx(.02)
    assert rows[0]["peak_date"] == "2023-01-02"
    assert rows[0]["earliest_action"] == "2023-01-05"
    c["evaluation_start"] = "2023-01-03"
    assert audit_trades(c) == []


def test_iid_run_probability_matches_enumeration():
    from itertools import product
    for k in (3, 4):
        sequences = list(product((0, 1), repeat=8))
        count = sum("1"*k in "".join(map(str, s)) for s in sequences)
        assert null_run_probability(8, k) == pytest.approx(count / 2**8)
