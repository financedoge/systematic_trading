from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from statistics import median
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.backtest.comparison import _max_drawdown, _returns, _sharpe  # noqa: E402
from systematic_trading.backtest.stability import (  # noqa: E402
    TARGET_RETENTION_HIGH,
    TARGET_RETENTION_LOW,
    finite_number,
    percentile_scores,
    retention_band_distance,
    retention_band_pass,
    retention_closeness_scores,
    sharpe_retention_ratio,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit in-sample/out-of-sample Sharpe retention for saved backtests.")
    parser.add_argument("--backtest-root", default="var/backtests")
    parser.add_argument("--split-date", default="2023-01-01")
    parser.add_argument("--output-dir", default="var/backtests/sharpe_stability_audit")
    parser.add_argument("--min-observations", type=int, default=252)
    args = parser.parse_args()

    backtest_root = _resolve_path(args.backtest_root)
    output_dir = _resolve_path(args.output_dir)
    split_date = date.fromisoformat(args.split_date)
    rows = audit_backtest_root(
        backtest_root=backtest_root,
        split_date=split_date,
        min_observations=args.min_observations,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "method": {
            "backtestRoot": str(backtest_root),
            "splitDate": split_date.isoformat(),
            "minObservations": args.min_observations,
            "retentionBand": [TARGET_RETENTION_LOW, TARGET_RETENTION_HIGH],
            "score": (
                "0.35 * OOS Sharpe percentile + 0.25 * robust Sharpe floor percentile + "
                "0.20 * retention-band closeness percentile + 0.10 * OOS calendar-fold Sharpe median percentile + "
                "0.10 * OOS max-drawdown percentile."
            ),
        },
        "rows": rows,
    }
    json_path = output_dir / "sharpe_stability_audit.json"
    md_path = output_dir / "sharpe_stability_audit.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(payload), encoding="utf-8")
    print(json_path)
    print(md_path)
    return None


def audit_backtest_root(
    *,
    backtest_root: Path,
    split_date: date,
    min_observations: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for path in sorted(backtest_root.rglob("*.json")):
        if _skip_path(path):
            continue
        payload = _load_json(path)
        if payload is None or not isinstance(payload.get("nav_series"), list):
            continue
        row = _row_for_payload(path=path, payload=payload, split_date=split_date, min_observations=min_observations)
        if row is None:
            continue
        duplicate_key = row["strategyKey"]
        existing = next((item for item in rows if item["strategyKey"] == duplicate_key), None)
        if existing is not None:
            if _is_preferred_duplicate(row, existing):
                rows.remove(existing)
            else:
                continue
        elif duplicate_key in seen_keys:
            continue
        seen_keys.add(duplicate_key)
        rows.append(row)

    _score_rows(rows)
    return sorted(rows, key=lambda item: item["stabilityScore"], reverse=True)


def _row_for_payload(
    *,
    path: Path,
    payload: dict[str, Any],
    split_date: date,
    min_observations: int,
) -> dict[str, Any] | None:
    points = _nav_points(payload)
    if len(points) < min_observations * 2:
        return None
    in_sample = [(trade_date, nav) for trade_date, nav in points if trade_date < split_date]
    out_of_sample = [(trade_date, nav) for trade_date, nav in points if trade_date >= split_date]
    if len(in_sample) < min_observations or len(out_of_sample) < min_observations:
        return None
    is_returns = _returns([nav for _trade_date, nav in in_sample])
    oos_returns = _returns([nav for _trade_date, nav in out_of_sample])
    is_sharpe = _sharpe(is_returns)
    oos_sharpe = _sharpe(oos_returns)
    if is_sharpe is None or oos_sharpe is None:
        return None
    retention_ratio = sharpe_retention_ratio(is_sharpe, oos_sharpe)
    oos_fold_stats = _calendar_year_fold_stats(out_of_sample)
    robust_sharpe_floor = min(is_sharpe, oos_sharpe) if is_sharpe > 0 and oos_sharpe > 0 else None
    harmonic_sharpe = (
        (2 * is_sharpe * oos_sharpe / (is_sharpe + oos_sharpe))
        if is_sharpe > 0 and oos_sharpe > 0 and (is_sharpe + oos_sharpe) > 0
        else None
    )
    return {
        "strategyKey": _strategy_key(path, payload),
        "strategyName": _strategy_name(path, payload),
        "path": str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path),
        "startDate": points[0][0].isoformat(),
        "endDate": points[-1][0].isoformat(),
        "inSampleStart": in_sample[0][0].isoformat(),
        "inSampleEnd": in_sample[-1][0].isoformat(),
        "outOfSampleStart": out_of_sample[0][0].isoformat(),
        "outOfSampleEnd": out_of_sample[-1][0].isoformat(),
        "inSampleObservations": len(in_sample),
        "outOfSampleObservations": len(out_of_sample),
        "inSampleSharpe": is_sharpe,
        "outOfSampleSharpe": oos_sharpe,
        "outToInSharpeRatio": retention_ratio,
        "retentionBandDistance": retention_band_distance(retention_ratio),
        "robustSharpeFloor": robust_sharpe_floor,
        "harmonicSharpe": harmonic_sharpe,
        "oosCalendarFoldSharpeMin": oos_fold_stats["minSharpe"],
        "oosCalendarFoldSharpeMedian": oos_fold_stats["medianSharpe"],
        "oosCalendarFoldPositiveShare": oos_fold_stats["positiveShare"],
        "outOfSampleMaxDrawdown": _max_drawdown([nav for _trade_date, nav in out_of_sample]),
        "outOfSampleReturn": (out_of_sample[-1][1] / out_of_sample[0][1]) - 1,
    }


def _score_rows(rows: list[dict[str, Any]]) -> None:
    oos_scores = percentile_scores(rows, "outOfSampleSharpe", id_key="strategyKey")
    floor_scores = percentile_scores(rows, "robustSharpeFloor", id_key="strategyKey")
    fold_scores = percentile_scores(rows, "oosCalendarFoldSharpeMedian", id_key="strategyKey")
    drawdown_scores = percentile_scores(rows, "outOfSampleMaxDrawdown", id_key="strategyKey")
    retention_scores = retention_closeness_scores(rows, distance_key="retentionBandDistance", id_key="strategyKey")
    for row in rows:
        key = row["strategyKey"]
        row["retentionBandPass"] = retention_band_pass(row["outToInSharpeRatio"])
        row["stabilityScore"] = (
            0.35 * oos_scores.get(key, 0.0)
            + 0.25 * floor_scores.get(key, 0.0)
            + 0.20 * retention_scores.get(key, 0.0)
            + 0.10 * fold_scores.get(key, 0.0)
            + 0.10 * drawdown_scores.get(key, 0.0)
        )


def _calendar_year_fold_stats(points: list[tuple[date, float]]) -> dict[str, float | None]:
    sharpes: list[float] = []
    for year in sorted({trade_date.year for trade_date, _nav in points}):
        year_points = [nav for trade_date, nav in points if trade_date.year == year]
        if len(year_points) < 40:
            continue
        sharpe = _sharpe(_returns(year_points))
        if sharpe is not None:
            sharpes.append(sharpe)
    if not sharpes:
        return {"minSharpe": None, "medianSharpe": None, "positiveShare": None}
    return {
        "minSharpe": min(sharpes),
        "medianSharpe": median(sharpes),
        "positiveShare": sum(1 for value in sharpes if value > 0) / len(sharpes),
    }


def _nav_points(payload: dict[str, Any]) -> list[tuple[date, float]]:
    points: list[tuple[date, float]] = []
    for item in payload.get("nav_series", []):
        try:
            points.append((date.fromisoformat(str(item["trade_date"])), float(item["nav_cnh"])))
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(points, key=lambda item: item[0])


def _strategy_key(path: Path, payload: dict[str, Any]) -> str:
    metadata = payload.get("strategy") or payload.get("model") or {}
    if isinstance(metadata, dict) and metadata.get("key"):
        return str(metadata["key"])
    proposals = payload.get("proposals") or []
    if proposals and isinstance(proposals[-1], dict) and proposals[-1].get("sleeve"):
        return str(proposals[-1]["sleeve"])
    return path.stem


def _strategy_name(path: Path, payload: dict[str, Any]) -> str:
    metadata = payload.get("strategy") or payload.get("model") or {}
    if isinstance(metadata, dict) and metadata.get("name"):
        return str(metadata["name"])
    return _strategy_key(path, payload).replace("_", " ").replace("-", " ")


def _skip_path(path: Path) -> bool:
    lowered = {part.lower() for part in path.parts}
    if "history" in lowered:
        return True
    return path.name in {
        "optimization_results.json",
        "multi_asset_rankings.json",
        "sota_vs_benchmark.json",
        "risk_period_analysis.json",
        "sharpe_stability_audit.json",
        "index.json",
        "metadata.json",
    }


def _is_preferred_duplicate(candidate: dict[str, Any], existing: dict[str, Any]) -> bool:
    candidate_path = str(candidate["path"])
    existing_path = str(existing["path"])
    if "sota_current" in candidate_path and "sota_current" not in existing_path:
        return True
    if "sota_current" in existing_path and "sota_current" not in candidate_path:
        return False
    return candidate["endDate"] > existing["endDate"]


def _markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    lines = [
        "# Sharpe Stability Audit",
        "",
        f"- Split date: {payload['method']['splitDate']}",
        f"- Retention target band: {TARGET_RETENTION_LOW:.2f} to {TARGET_RETENTION_HIGH:.2f}",
        f"- Candidate count: {len(rows)}",
        "",
        "The retention ratio is out-of-sample Sharpe divided by in-sample Sharpe. Ratios materially above 1.0 are treated as unstable because they imply the OOS window outperformed the fitted history.",
        "The robust floor is min(IS Sharpe, OOS Sharpe), so a strategy must be credible in both windows. Calendar-fold Sharpe checks whether the OOS result depends on one short period.",
        "",
        "## Top Stability-Aware Strategies",
        "",
        "| Rank | Strategy | IS Sharpe | OOS Sharpe | OOS/IS | Floor | OOS Fold Median | Band Pass | OOS Max DD | Score |",
        "| ---: | --- | ---: | ---: | ---: | ---: | ---: | --- | ---: | ---: |",
    ]
    for index, row in enumerate(rows[:25], start=1):
        lines.append(_row_markdown(index, row))

    sota_rows = [row for row in rows if "sota" in row["strategyKey"].lower()]
    if sota_rows:
        lines.extend(["", "## SOTA Rows", "", "| Rank | Strategy | IS Sharpe | OOS Sharpe | OOS/IS | Band Pass | Score |", "| ---: | --- | ---: | ---: | ---: | --- | ---: |"])
        rank_by_key = {row["strategyKey"]: index for index, row in enumerate(rows, start=1)}
        for row in sorted(sota_rows, key=lambda item: rank_by_key[item["strategyKey"]]):
            lines.append(
                "| "
                + " | ".join(
                    [
                str(rank_by_key[row["strategyKey"]]),
                row["strategyName"],
                _fmt_num(row["inSampleSharpe"]),
                _fmt_num(row["outOfSampleSharpe"]),
                _fmt_num(row["outToInSharpeRatio"]),
                        "yes" if row["retentionBandPass"] else "no",
                        _fmt_num(row["stabilityScore"]),
                    ]
                )
                + " |"
            )
    return "\n".join(lines) + "\n"


def _row_markdown(index: int, row: dict[str, Any]) -> str:
    return (
        "| "
        + " | ".join(
            [
                str(index),
                row["strategyName"],
                _fmt_num(row["inSampleSharpe"]),
                _fmt_num(row["outOfSampleSharpe"]),
                _fmt_num(row["outToInSharpeRatio"]),
                _fmt_num(row["robustSharpeFloor"]),
                _fmt_num(row["oosCalendarFoldSharpeMedian"]),
                "yes" if row["retentionBandPass"] else "no",
                _fmt_pct(row["outOfSampleMaxDrawdown"]),
                _fmt_num(row["stabilityScore"]),
            ]
        )
        + " |"
    )


def _fmt_num(value: Any) -> str:
    if finite_number(value):
        return f"{float(value):.2f}"
    return "n/a"


def _fmt_pct(value: Any) -> str:
    if finite_number(value):
        return f"{float(value):.2%}"
    return "n/a"


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _resolve_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return REPO_ROOT / path


if __name__ == "__main__":
    main()
