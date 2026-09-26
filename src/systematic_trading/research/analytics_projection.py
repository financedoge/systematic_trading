"""Read-only builders for analytical histories and precomputed Strategy pages."""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

from systematic_trading.market_data.analytics_store import digest, encode, timestamp
from systematic_trading.research.market_data_view import StrategyMarketDataView


DATE_KEYS = ("trade_date", "rate_date", "date", "as_of", "filled_at", "exchange_timestamp",
             "timestamp", "observed_at", "captured_at", "available_date", "period_end", "start", "end",
             "startDate", "endDate", "decision_date", "execution_date")


def observation(key, family, entity, payload, observed_at=None, available_at=None):
    return dict(point_key=key, family=family, entity=entity,
                observed_at=timestamp(observed_at), available_at=timestamp(available_at), payload=encode(payload))


def extract_series(payload, *, family, entity, prefix=""):
    """Preserve dated rows, nested series and date-keyed maps with JSON-path IDs."""
    rows = []
    if isinstance(payload, dict):
        day = next((payload[key] for key in DATE_KEYS if timestamp(payload.get(key))), None)
        if day is None and isinstance(payload.get("period"), str):
            period = payload["period"]
            # Period summaries use a logical bucket start, not an asserted
            # vendor observation/publication time. Keep original labels intact.
            if re.fullmatch(r"\d{4}", period):
                day = period + "-01-01"
            elif re.fullmatch(r"\d{4}-\d{2}", period):
                day = period + "-01"
            elif re.fullmatch(r"\d{4}-?Q[1-4]", period):
                day = f"{period[:4]}-{(int(period[-1]) - 1) * 3 + 1:02d}-01"
        if day is not None:
            rows.append(observation(prefix or "/", family, str(payload.get("symbol") or entity), payload,
                                    day, payload.get("available_at") or payload.get("available_date")))
        for key, value in payload.items():
            path = prefix + "/" + str(key).replace("~", "~0").replace("/", "~1")
            if timestamp(key) and isinstance(value, (dict, int, float, str)):
                rows.append(observation(path, family, entity, {"date": key, "value": value}, key))
            else:
                rows.extend(extract_series(value, family=family, entity=entity, prefix=path))
    elif isinstance(payload, list):
        for index, value in enumerate(payload):
            rows.extend(extract_series(value, family=family, entity=entity, prefix=f"{prefix}/{index}"))
    return rows


def file_signature(paths):
    return [(str(p.resolve()), p.stat().st_size, p.stat().st_mtime_ns) for p in sorted(paths)]


def import_json_group(analytics, source_id, paths, family):
    paths = list(paths)
    before = file_signature(paths)
    latest = analytics.latest(source_id)
    extractor = digest(Path(__file__).read_bytes())
    if (latest and json.loads(latest["provenance"]).get("extractor") == extractor
            and json.loads(latest["provenance"]).get("file_signature") == json.loads(encode(before))):
        return False
    rows, hashes, documents = [], {}, []
    for path in sorted(paths):
        raw = path.read_bytes()
        hashes[str(path)] = digest(raw)
        payload = json.loads(raw.decode("utf-8-sig"))
        if family == "execution_benchmark":
            documents.append(dict(point_key=path.stem, media_type="application/json", payload=encode(payload)))
        identity = str(path.resolve())
        extracted = extract_series(payload, family=family, entity=path.stem, prefix=identity)
        if family == "account_snapshot":
            # Preserve undated legacy snapshots too; consumers still use the
            # existing explicit filename/capture-time rules when needed.
            extracted = [observation(identity, family, path.name,
                                     {"path": str(path), "snapshot": payload},
                                     payload.get("as_of"), payload.get("captured_at"))]
        rows.extend(extracted)
    if file_signature(paths) != before:
        raise RuntimeError(f"{source_id} changed during import; retrying next cycle")
    version = digest(encode({"files": hashes, "extractor": extractor}))
    return analytics.publish(source_id, version, rows, documents,
                             provenance={"files": hashes, "file_signature": before, "extractor": extractor, "format": 1})


def import_account_histories(settings, analytics):
    paths = sorted((settings.data_dir / "live" / "account_snapshots").glob("*.json"))
    before = file_signature(paths)
    index = analytics.publication_index("account-history/")
    current_sources, pending = set(), []
    for path in paths:
        source = "account-history/" + path.name
        current_sources.add(source)
        signature = file_signature([path])
        prior = index.get(source)
        if prior and json.loads(prior["provenance"]).get("signature") == json.loads(encode(signature)):
            continue
        raw = path.read_bytes()
        payload = json.loads(raw.decode("utf-8-sig"))
        if file_signature([path]) != signature:
            raise RuntimeError(f"Account capture changed during import: {path}")
        row = observation(path.name, "account_snapshot", path.name, {"path": str(path), "snapshot": payload},
                          payload.get("as_of"), payload.get("captured_at"))
        pending.append((source, digest(raw), [row], {"signature": signature}))
    for source in index.keys() - current_sources:
        if index[source]["version"] != "removed":
            pending.append((source, "removed", [], {"removed": True}))
    if before != file_signature(paths):
        raise RuntimeError("Account history changed during import; refresh will retry")
    changed = analytics.publish_batch(pending)
    # Summary is a readiness marker. Individual immutable captures are stored
    # once, not recopied every minute as the history grows.
    changed |= analytics.publish("account-history", digest(encode(before)), [],
                                 provenance={"file_signature": before, "count": len(paths), "layout": "per_capture_v1"})
    return changed


def import_lean_histories(analytics, store):
    store = getattr(store, "transactional_store", store)
    if store.__class__.__name__ != "PostgresStore":
        return False
    with store._connect() as connection:
        exists = connection.execute("SELECT to_regclass('ops.lean_research_runs') AS name").fetchone()
        if not exists["name"]:
            return False
        runs = connection.execute("SELECT artifact_path, payload FROM ops.lean_research_runs").fetchall()
    paths = []
    for run in runs:
        root = Path(run["artifact_path"])
        for name in ("reference.json", "economic.json"):
            path = root / name
            if not path.is_file():
                raise FileNotFoundError(f"Registered LEAN series unavailable: {path}")
            expected = run["payload"]["receipt"]["artifacts"][name]
            if digest(path.read_bytes()) != expected:
                raise ValueError(f"Registered LEAN series changed: {path}")
            paths.append(path)
    return import_json_group(analytics, "lean-history", paths, "lean_research")


def import_transactional_histories(analytics, store):
    # PostgreSQL remains authoritative. Snapshot exact source payloads without
    # changing execution records, approvals, reset boundaries or outbox state.
    if hasattr(store, "transactional_store"):
        store = store.transactional_store
    rows = []
    if hasattr(store, "_connect") and store.__class__.__name__ == "PostgresStore":
        with store._connect() as connection:
            for table, family, key, day in (
                ("portfolio.pnl_snapshots", "pnl_snapshot", "snapshot_id", "as_of"),
                ("execution.broker_orders", "execution_order", "local_order_id", "updated_at"),
                ("core.fundamental_snapshots", "fundamental", "snapshot_id", "available_date"),
            ):
                # These table names are fixed application identifiers.
                for row in connection.execute(f"SELECT payload FROM {table}").fetchall():
                    payload = row["payload"]
                    identity = str(payload.get(key) or digest(encode(payload)))
                    rows.append(observation(f"{family}/{identity}", family,
                                            str(payload.get("symbol") or identity), payload,
                                            payload.get(day), payload.get("available_at") or payload.get("available_date")))
                    if family == "execution_order":
                        rows.extend(extract_series(payload.get("execution_fills", payload.get("fills", [])),
                                                   family="execution_fill", entity=identity, prefix=f"fills/{identity}"))
    version = digest(encode(sorted(rows, key=lambda row: row["point_key"])))
    return analytics.publish("transactional-history", version, rows, provenance={"authority": "postgresql"})


def strategy_inputs(settings, analytics):
    from systematic_trading.research.tracked_runtime import SOURCE
    files = list((settings.data_dir / "backtests").rglob("*.json"))
    files += list((settings.data_dir / "backtests").rglob("*.html"))
    if settings.strategy_monitoring_config_path.exists():
        files.append(settings.strategy_monitoring_config_path)
    code_root = Path(__file__).resolve().parents[1]
    files += [code_root / name for name in ("web/api.py", "backtest/reporting.py", "chart_navigation.py", "research/catalog.py",
                                          "research/analytics_projection.py", "research/market_data_view.py",
                                          "research/tracked_runtime.py", "research/strategy_diagram.py")]
    return digest(encode({"files": file_signature(files), "market": analytics.market_revision(),
                          "research_tracking": (analytics.latest(SOURCE) or {}).get("version"),
                          "day": datetime.now(UTC).date().isoformat()}))


def publish_strategies(settings, store, analytics):
    from systematic_trading.web import api
    from systematic_trading.research.catalog import discover_strategy_artifacts
    from systematic_trading.research.tracked_runtime import published_strategies
    from systematic_trading.backtest.reporting import render_backtest_report_html

    version = strategy_inputs(settings, analytics)
    latest = analytics.latest("strategy-serving")
    if latest and latest["version"] == version:
        return False
    discover_strategy_artifacts.cache_clear()
    read_view = StrategyMarketDataView(store)
    # No analytics reader on this builder request: computation is confined to
    # this background worker, while ordinary HTTP requests only read documents.
    calculated = published_strategies(analytics)
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(settings=settings, store=read_view,
        calculated_strategy_ids=set(calculated))))
    catalog = api.strategy_catalog(request)
    trackers = {key: item[0] for key, item in calculated.items()}
    catalog["strategies"] = [row for row in catalog["strategies"] if row["strategy_id"] not in trackers]
    catalog["strategies"].extend({key: value for key, value in item.items()
        if key not in ("nav_series", "benchmark_series", "comparison")} for item in trackers.values())
    if trackers:
        catalog["monitoring_notes"] = "Application-calculated signals, rebalances, NAV and weights on audited histories. Tracking is separate from promotion and broker execution."
    documents = [dict(point_key="catalog", media_type="application/json", payload=encode(catalog))]
    rows, seen = [], set()
    for item in catalog["strategies"]:
        strategy_id = item["strategy_id"]
        if strategy_id in seen:
            continue
        seen.add(strategy_id)
        detail = trackers[strategy_id] if strategy_id in trackers else api.strategy_detail(strategy_id, request)
        documents.append(dict(point_key=f"detail/{strategy_id}", media_type="application/json", payload=encode(detail)))
        rows.extend(extract_series(detail["nav_series"], family="strategy_nav", entity=strategy_id, prefix=f"nav/{strategy_id}"))
        rows.extend(extract_series(detail["benchmark_series"], family="benchmark_nav", entity=strategy_id, prefix=f"benchmark/{strategy_id}"))
        if item["report_available"]:
            if strategy_id in calculated:
                body = render_backtest_report_html(calculated[strategy_id][1])
            else:
                response = api.strategy_report(strategy_id, request)
                body = response.body.decode() if hasattr(response, "body") else Path(response.path).read_text(encoding="utf-8")
            documents.append(dict(point_key=f"report/{strategy_id}", media_type="text/html", payload=body))
            match = re.search(r"const report = (.*);", body)
            if match:
                report = json.loads(match.group(1))
                for section in ("chart", "metricsByBenchmark", "holdingContributions", "signalDiagnostics", "drawdownPeriods"):
                    rows.extend(extract_series(report.get(section), family=section, entity=strategy_id,
                                               prefix=f"report/{strategy_id}/{section}"))
    if strategy_inputs(settings, analytics) != version:
        raise RuntimeError("Strategy inputs changed during calculation; retaining previous publication")
    return analytics.publish("strategy-serving", version, rows, documents,
                             provenance={"method": "app_calculated_tracked_strategies_and_archived_artifacts",
                                         "input_revision": version})


def publish_dashboard(settings, store, analytics):
    from systematic_trading.web import api
    baseline = store.latest_pnl_baseline()
    baseline_token = digest(baseline.model_dump_json()) if baseline else "none"
    inputs = {"baseline": baseline_token, "market": analytics.market_revision(),
              "account": (analytics.latest("account-history") or {}).get("version"),
              "strategy": (analytics.latest("strategy-serving") or {}).get("version")}
    if not inputs["account"] or not inputs["strategy"]:
        raise RuntimeError("Account and Strategy publications are required for the performance chart")
    version = digest(encode(inputs))
    if (analytics.latest("dashboard-serving") or {}).get("version") == version:
        return False
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(
        settings=settings, store=StrategyMarketDataView(store), strategy_analytics=analytics)))
    payload = api.dashboard_performance(request).model_dump(mode="json")
    current = store.latest_pnl_baseline()
    if (digest(current.model_dump_json()) if current else "none") != baseline_token:
        raise RuntimeError("Account reset changed during performance calculation")
    rows = extract_series(payload, family="account_performance", entity="account", prefix="performance")
    return analytics.publish("dashboard-serving", version, rows,
        [dict(point_key="performance", media_type="application/json", payload=encode(payload))], provenance=inputs)
