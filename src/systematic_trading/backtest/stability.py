from __future__ import annotations

import math
from typing import Any, Mapping, Sequence


TARGET_RETENTION_LOW = 0.80
TARGET_RETENTION_HIGH = 0.90


def finite_number(value: Any) -> bool:
    return isinstance(value, int | float) and math.isfinite(float(value))


def sharpe_retention_ratio(
    in_sample_sharpe: float | int | None,
    out_of_sample_sharpe: float | int | None,
) -> float | None:
    if not finite_number(in_sample_sharpe) or not finite_number(out_of_sample_sharpe):
        return None
    reference = float(in_sample_sharpe)
    if reference <= 0:
        return None
    return float(out_of_sample_sharpe) / reference


def retention_band_pass(value: float | int | None) -> bool:
    return finite_number(value) and TARGET_RETENTION_LOW <= float(value) <= TARGET_RETENTION_HIGH


def retention_band_distance(value: float | int | None) -> float | None:
    if not finite_number(value):
        return None
    ratio = float(value)
    if retention_band_pass(ratio):
        return 0.0
    return min(abs(ratio - TARGET_RETENTION_LOW), abs(ratio - TARGET_RETENTION_HIGH))


def percentile_scores(
    rows: Sequence[Mapping[str, Any]],
    key: str,
    *,
    id_key: str = "key",
    higher_is_better: bool = True,
) -> dict[str, float]:
    present = [row for row in rows if finite_number(row.get(key))]
    if not present:
        return {}
    ranked = sorted(
        present,
        key=lambda row: (
            float(row[key]) if higher_is_better else -float(row[key]),
            str(row[id_key]),
        ),
    )
    if len(ranked) == 1:
        return {str(ranked[0][id_key]): 1.0}
    denominator = len(ranked) - 1
    return {str(row[id_key]): index / denominator for index, row in enumerate(ranked)}


def retention_closeness_scores(
    rows: Sequence[Mapping[str, Any]],
    *,
    distance_key: str = "sharpeRetentionBandDistance",
    id_key: str = "key",
) -> dict[str, float]:
    return percentile_scores(rows, distance_key, id_key=id_key, higher_is_better=False)
