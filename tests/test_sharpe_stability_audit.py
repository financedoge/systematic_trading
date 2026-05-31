import json
from pathlib import Path

from scripts.audit_sharpe_stability import audit_backtest_root


def test_audit_backtest_root_computes_oos_to_in_sample_sharpe_ratio(tmp_path) -> None:
    strategy_dir = tmp_path / "case"
    strategy_dir.mkdir()
    _write_backtest(
        strategy_dir / "stable.json",
        start_nav=100.0,
        in_sample_daily_return=0.001,
        out_sample_daily_return=0.00085,
    )

    rows = audit_backtest_root(
        backtest_root=tmp_path,
        split_date=_date(2023, 1, 1),
        min_observations=10,
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["outToInSharpeRatio"] is not None
    assert 0.7 < row["outToInSharpeRatio"] < 1.0


def _write_backtest(
    path: Path,
    *,
    start_nav: float,
    in_sample_daily_return: float,
    out_sample_daily_return: float,
) -> None:
    nav = start_nav
    nav_series = []
    for index in range(30):
        trade_date = _date(2022, 12, 1 + index)
        nav *= 1 + in_sample_daily_return + (0.0001 if index % 2 else -0.0001)
        nav_series.append({"trade_date": trade_date.isoformat(), "nav_cnh": str(nav)})
    for index in range(30):
        trade_date = _date(2023, 1, 1 + index)
        nav *= 1 + out_sample_daily_return + (0.0001 if index % 2 else -0.0001)
        nav_series.append({"trade_date": trade_date.isoformat(), "nav_cnh": str(nav)})
    path.write_text(json.dumps({"nav_series": nav_series}), encoding="utf-8")


def _date(year: int, month: int, day: int):
    from datetime import date

    return date(year, month, day)
