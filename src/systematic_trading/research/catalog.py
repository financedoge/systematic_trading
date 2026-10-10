from __future__ import annotations

import json
import math
from bisect import bisect_right
from calendar import monthrange
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class StrategyArtifact:
    strategy_id: str
    name: str
    artifact_path: str
    is_sota: bool
    start_date: date
    end_date: date
    observations: int
    initial_nav_cnh: float
    final_nav_cnh: float
    total_return: float
    annualized_return: float | None
    annualized_volatility: float | None
    sharpe: float | None
    max_drawdown: float | None
    calmar: float | None
    allocation: tuple[dict[str, Any], ...]
    return_1m: float | None = None
    return_ytd: float | None = None
    return_1y: float | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.__dict__,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "allocation": list(self.allocation),
        }


@lru_cache(maxsize=8)
def discover_strategy_artifacts(backtests_root: Path, sota_key: str) -> tuple[StrategyArtifact, ...]:
    if not backtests_root.exists():
        return ()
    artifacts: list[StrategyArtifact] = []
    seen: set[tuple[str, date, date]] = set()
    paths = sorted(
        backtests_root.rglob("*.json"),
        key=lambda item: (item.relative_to(backtests_root).as_posix() != f"sota_current/{sota_key}.json", str(item)),
    )
    for path in paths:
        artifact = _read_artifact(path, backtests_root, sota_key)
        if artifact is None:
            continue
        identity = (artifact.strategy_id, artifact.start_date, artifact.end_date)
        if identity in seen:
            continue
        seen.add(identity)
        artifacts.append(artifact)
    return tuple(sorted(artifacts, key=lambda item: (not item.is_sota, item.name.lower(), item.end_date)))


def _read_artifact(path: Path, root: Path, sota_key: str) -> StrategyArtifact | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("nav_series"), list):
        return None
    points: list[tuple[date, float]] = []
    for row in payload["nav_series"]:
        if not isinstance(row, dict):
            continue
        try:
            value = float(row["nav_cnh"])
            trade_date = date.fromisoformat(str(row["trade_date"]))
        except (KeyError, TypeError, ValueError):
            continue
        if value > 0 and math.isfinite(value):
            points.append((trade_date, value))
    points.sort()
    if len(points) < 2:
        return None
    strategy_id = _strategy_id(payload, path)
    returns = [points[index][1] / points[index - 1][1] - 1 for index in range(1, len(points))]
    years = max((points[-1][0] - points[0][0]).days / 365.25, 1 / 252)
    total_return = points[-1][1] / points[0][1] - 1
    annualized_return = (points[-1][1] / points[0][1]) ** (1 / years) - 1
    volatility = _sample_std(returns)
    annualized_volatility = volatility * math.sqrt(252) if volatility is not None else None
    sharpe = (sum(returns) / len(returns)) / volatility * math.sqrt(252) if volatility and volatility > 0 else None
    max_drawdown = _max_drawdown([point[1] for point in points])
    calmar = annualized_return / abs(max_drawdown) if max_drawdown < 0 else None
    relative = path.relative_to(root).as_posix()
    return StrategyArtifact(
        strategy_id=strategy_id,
        name=_strategy_name(payload, strategy_id),
        artifact_path=relative,
        is_sota=relative == f"sota_current/{sota_key}.json",
        start_date=points[0][0],
        end_date=points[-1][0],
        observations=len(points),
        initial_nav_cnh=points[0][1],
        final_nav_cnh=points[-1][1],
        total_return=total_return,
        annualized_return=annualized_return,
        annualized_volatility=annualized_volatility,
        sharpe=sharpe,
        max_drawdown=max_drawdown,
        calmar=calmar,
        allocation=tuple(_allocation(payload)),
        **summarize_period_returns(points),
    )


def _strategy_id(payload: dict[str, Any], path: Path) -> str:
    research_case = payload.get("researchCase") or payload.get("research_case")
    if isinstance(research_case, dict):
        for key in ("key", "strategy_key", "name"):
            if research_case.get(key):
                return str(research_case[key])
    return path.stem


def _strategy_name(payload: dict[str, Any], fallback: str) -> str:
    research_case = payload.get("researchCase") or payload.get("research_case")
    if isinstance(research_case, dict) and research_case.get("name"):
        return str(research_case["name"])
    return fallback.replace("_", " ").strip().title()


def _allocation(payload: dict[str, Any]) -> list[dict[str, Any]]:
    snapshot = payload.get("final_snapshot")
    if not isinstance(snapshot, dict):
        return []
    positions = snapshot.get("positions")
    if not isinstance(positions, list):
        return []
    values: list[tuple[str, float]] = []
    for row in positions:
        if not isinstance(row, dict):
            continue
        try:
            value = float(row.get("market_value_cnh") or float(row["quantity"]) * float(row["market_price"]))
        except (KeyError, TypeError, ValueError):
            continue
        if value > 0:
            values.append((str(row.get("symbol", "unknown")), value))
    total = sum(value for _, value in values)
    return [{"symbol": symbol, "value_cnh": value, "weight": value / total} for symbol, value in sorted(values) if total > 0]


def _sample_std(values: list[float]) -> float | None:
    if len(values) < 2:
        return None
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def summarize_nav_points(points: list[tuple[date, float]]) -> dict[str, Any]:
    clean = sorted((point_date, value) for point_date, value in points if value > 0 and math.isfinite(value))
    if len(clean) < 2:
        return {}
    returns = [clean[index][1] / clean[index - 1][1] - 1 for index in range(1, len(clean))]
    years = max((clean[-1][0] - clean[0][0]).days / 365.25, 1 / 252)
    total_return = clean[-1][1] / clean[0][1] - 1
    annualized_return = (clean[-1][1] / clean[0][1]) ** (1 / years) - 1
    volatility = _sample_std(returns)
    max_drawdown = _max_drawdown([point[1] for point in clean])
    return {
        **summarize_period_returns(points),
        "start_date": clean[0][0].isoformat(),
        "end_date": clean[-1][0].isoformat(),
        "observations": len(clean),
        "initial_nav_cnh": clean[0][1],
        "final_nav_cnh": clean[-1][1],
        "total_return": total_return,
        "annualized_return": annualized_return,
        "annualized_volatility": volatility * math.sqrt(252) if volatility is not None else None,
        "sharpe": (sum(returns) / len(returns)) / volatility * math.sqrt(252) if volatility and volatility > 0 else None,
        "max_drawdown": max_drawdown,
        "calmar": annualized_return / abs(max_drawdown) if max_drawdown < 0 else None,
    }


def summarize_period_returns(points: list[tuple[date, float]]) -> dict[str, float | None]:
    """Cumulative returns through the last published NAV, in its own currency.

    1M/1Y use calendar-month/year offsets (clamped at month end); YTD starts
    at the prior year end. The anchor is the last observed close on/before
    that boundary. No anchor means unavailable, never a since-inception
    substitute. Invalid observations in a window also leave it unavailable.
    Publication coverage checks remain responsible for absent sessions.
    """
    result = dict.fromkeys(("return_1m", "return_ytd", "return_1y"))
    if len(points) < 2:
        return result
    ordered = sorted(points)
    end, final = ordered[-1]
    if not math.isfinite(final) or final <= 0:
        return result
    dates = [day for day, _ in ordered]
    month_year, month = (end.year, end.month - 1) if end.month > 1 else (end.year - 1, 12)
    boundaries = {
        "return_1m": date(month_year, month, min(end.day, monthrange(month_year, month)[1])),
        "return_ytd": date(end.year - 1, 12, 31),
        "return_1y": date(end.year - 1, end.month, min(end.day, monthrange(end.year - 1, end.month)[1])),
    }
    for key, boundary in boundaries.items():
        index = bisect_right(dates, boundary) - 1
        if index < 0:
            continue
        if index > 0 and dates[index - 1] == dates[index]:
            continue
        window = ordered[index:]
        if any(not math.isfinite(value) or value <= 0 for _, value in window):
            continue
        if len({day for day, _ in window}) != len(window):
            continue
        result[key] = final / ordered[index][1] - 1
    return result


def _max_drawdown(values: list[float]) -> float:
    peak = values[0]
    drawdown = 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    return drawdown
