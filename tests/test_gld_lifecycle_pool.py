"""Focused tests for the 52-ETF pool selection pipeline."""
from __future__ import annotations

import numpy as np
import pandas as pd

import sys
from pathlib import Path

ROOT = Path(r"D:\projects\systematic_trading")
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))
import run_gld_lifecycle_pool as pool  # noqa: E402


def test_cap_weights_respects_budget_and_cap():
    raw = np.array([10.0, 5.0, 2.0, 1.0])
    weights = pool.cap_weights(raw, budget=0.98, cap=0.45)
    assert abs(weights.sum() - 0.98) < 1e-9
    assert weights.max() <= 0.45 + 1e-9
    assert np.all(np.diff(weights) <= 1e-12)  # larger raw weight -> larger weight


def test_cap_weights_binds_with_many_names():
    raw = np.ones(10)
    weights = pool.cap_weights(raw, budget=0.98, cap=0.45)
    assert np.all(weights <= 0.45 + 1e-9)
    assert abs(weights.sum() - 0.98) < 1e-9


def test_monthly_indices_unique_and_month_ends():
    panel = {"days": np.array([f"2022-{m:02d}-{d:02d}" for m in (10, 11, 12)
                               for d in (3, 30)] + ["2023-01-03", "2023-01-31",
                                                     "2023-02-01", "2023-02-28"])}
    indices = pool.monthly_indices(panel)
    assert len(indices) == len(set(int(i) for i in indices))
    days = [str(d) for d in panel["days"]]
    assert days[indices[0]] == "2022-12-30"
    assert all(days[i][:7] == days[min(i + 1, len(days) - 1)][:7]
               or days[i + 1][:7] != days[i][:7] for i in indices)


def test_event_indices_are_sorted_and_include_monthly_anchors():
    panel = {"days": np.array([f"2023-{m:02d}-{d:02d}" for m in (1, 2, 3) for d in (3, 28)])}
    base = np.array([0, 2])
    targets = np.zeros((6, 3))
    targets[:, 0] = 0.5
    indices = pool.event_indices(panel, targets, base)
    assert np.all(np.diff(indices) > 0)
    assert set(int(i) for i in base).issubset(set(int(i) for i in indices))
