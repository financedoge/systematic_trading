"""P4.19 retained-evidence audit; no broker requests, price downloads or database writes."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trading.domain.execution import BrokerOrderRecord  # noqa: E402
from systematic_trading.execution.twap_benchmark import benchmark_window, calculate_twap  # noqa: E402


SOURCES = (
    "scripts/analyze_execution_timing.py",
    "src/systematic_trading/domain/execution.py",
    "src/systematic_trading/domain/enums.py",
    "src/systematic_trading/execution/twap_benchmark.py",
)


def encoded(value):
    return json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n"


def file_hash(path):
    return sha256(path.read_bytes()).hexdigest()


def evidence_issues(record, identifiers):
    issues = []
    fills = record.execution_fills
    if record.execution_sync_issue:
        issues.append("execution_sync_issue")
    if not fills:
        return issues + ["missing_execution_details"]
    if sum(fill.quantity for fill in fills) != record.filled_quantity:
        issues.append("execution_quantity_mismatch")
    if any(not fill.execution_id or identifiers[fill.execution_id] != 1 for fill in fills):
        issues.append("missing_or_duplicate_execution_id")
    if any(fill.symbol != record.order.symbol or fill.side != record.order.side
           or fill.currency != record.order.currency or fill.order_ref != record.order_ref
           or fill.broker_order_id != record.broker_order_id for fill in fills):
        issues.append("execution_identity_mismatch")
    if any(fill.filled_at.tzinfo is None for fill in fills):
        issues.append("execution_time_without_timezone")
    if record.average_fill_price is None:
        issues.append("missing_average_fill_price")
    else:
        average = sum(fill.average_price * fill.quantity for fill in fills) / sum(fill.quantity for fill in fills)
        if abs(average - record.average_fill_price) > Decimal("0.0001"):
            issues.append("execution_average_mismatch")
    return issues


def analyze(snapshot):
    """Coverage first; only complete retained executions may contribute measured price cost."""
    records = [BrokerOrderRecord.model_validate(row) for row in snapshot["orders"]]
    if len({row.local_order_id for row in records}) != len(records):
        raise ValueError("Duplicate local order identity")
    publication = snapshot["benchmark_publication"]
    documents = snapshot["benchmark_documents"]
    if documents and not publication:
        raise ValueError("Unpublished benchmark documents")
    if publication and len(documents) != int(publication["document_count"]):
        raise ValueError("Published document count mismatch")
    published = {}
    for row in documents:
        if row["point_key"] in published:
            raise ValueError("Duplicate published benchmark identity")
        if sha256(row["payload"].encode()).hexdigest() != row["payload_sha256"]:
            raise ValueError("Published benchmark payload hash mismatch")
        published[row["point_key"]] = json.loads(row["payload"])

    identifiers = Counter(fill.execution_id for row in records for fill in row.execution_fills)
    rows = []
    for record in records:
        if record.environment.value != "paper" or record.filled_quantity == 0:
            continue
        issues = evidence_issues(record, identifiers)
        row = dict(local_order_id=record.local_order_id, symbol=record.order.symbol,
                   currency=record.order.currency.value, order_type=record.order.order_type.value,
                   status=record.status.value, requested_quantity=record.order.quantity, side=record.order.side.value,
                   filled_quantity=record.filled_quantity, execution_count=len(record.execution_fills),
                   fill_dates=sorted({fill.filled_at.astimezone(UTC).date().isoformat()
                                      for fill in record.execution_fills if fill.filled_at.tzinfo}),
                   evidence_issues=issues, original_window=None, routed_window=None,
                   twap_status="unavailable", benchmark_price=None, slippage_bps=None,
                   price_cost=None, benchmark_notional=None,
                   close_status="no_pinned_close_benchmark", vwap_status="no_pinned_vwap_benchmark")
        try:
            start, end = benchmark_window(record, original_intent=True)
            row["original_window"] = [start.isoformat(), end.isoformat()]
            row["routed_window"] = [at.isoformat() for at in benchmark_window(record)]
        except ValueError:
            row["twap_status"] = "no_explicit_twap_window"
            rows.append(row)
            continue
        key = sha256(f"v1:{record.order.symbol}:{start.isoformat()}:{end.isoformat()}".encode()).hexdigest()
        candidate = published.get(key)
        if candidate is None:
            row["twap_status"] = "no_published_benchmark"
        else:
            try:
                if (candidate["status"], candidate["symbol"], candidate["window_start"], candidate["window_end"]) != (
                    "ready", record.order.symbol, start.isoformat(), end.isoformat()
                ):
                    raise ValueError("Benchmark identity mismatch")
                observed = datetime.fromisoformat(candidate["observed_at"])
                cutoff = datetime.fromisoformat(snapshot["captured_at"])
                if observed.tzinfo is None or not end <= observed <= cutoff:
                    raise ValueError("Benchmark observation time is not valid at the frozen cutoff")
                price, count = calculate_twap(candidate["bars"], start, end)
                row.update(benchmark_price=str(price), benchmark_bar_count=count,
                           twap_status="withheld_execution_evidence" if issues else "ready")
                if not issues:
                    quantity = record.filled_quantity
                    average = sum(fill.average_price * fill.quantity for fill in record.execution_fills) / quantity
                    sign = Decimal(1) if record.order.side.value == "buy" else Decimal(-1)
                    cost = sign * (average - price) * quantity
                    row.update(price_cost=str(cost), benchmark_notional=str(price * quantity),
                               slippage_bps=str(cost / (price * quantity) * 10000))
            except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
                row.update(twap_status="invalid_published_benchmark", benchmark_error=str(exc), benchmark_price=None)
        rows.append(row)

    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["symbol"], row["currency"])].append(row)

    def summarize(group):
        ready = [row for row in group if row["twap_status"] == "ready"]
        cost = sum((Decimal(row["price_cost"]) for row in ready), Decimal(0))
        notional = sum((Decimal(row["benchmark_notional"]) for row in ready), Decimal(0))
        return dict(filled_orders=len(group), detailed_orders=sum(not row["evidence_issues"] for row in group),
                    partially_filled_orders=sum(row["filled_quantity"] < row["requested_quantity"] for row in group),
                    twap_orders=sum(row["order_type"] == "twap" for row in group),
                    benchmark_ready_orders=len(ready), close_ready_orders=0, vwap_ready_orders=0,
                    signed_price_cost=str(cost) if ready else None,
                    gross_benchmark_notional=str(notional) if ready else None,
                    slippage_bps=str(cost / notional * 10000) if ready else None)

    return dict(
        status="blocked_no_matched_style_evidence",
        captured_at=snapshot["captured_at"],
        scope="All retained paper history; not current-account PnL and not a matched execution-style experiment",
        retained_orders=len(records), unfilled_paper_orders=sum(
            row.environment.value == "paper" and not row.filled_quantity for row in records),
        published_benchmark_documents=len(documents),
        retained_execution_details=sum(row["execution_count"] for row in rows),
        evidence_issue_counts=dict(Counter(issue for row in rows for issue in row["evidence_issues"])),
        twap_status_counts=dict(Counter(row["twap_status"] for row in rows)),
        fill_dates=sorted({day for row in rows for day in row["fill_dates"]}),
        per_symbol=[dict(symbol=symbol, currency=currency, **summarize(group))
                    for (symbol, currency), group in sorted(grouped.items())],
        per_currency=[dict(currency=currency, **summarize([row for row in rows if row["currency"] == currency]))
                      for currency in sorted({row["currency"] for row in rows})],
        per_style=[dict(style=style, currency=currency,
                        **summarize([row for row in rows if row["currency"] == currency and row["order_type"] == style]))
                   for style, currency in sorted({(row["order_type"], row["currency"]) for row in rows})],
        limitations=[
            "No ranking of TWAP, close or session VWAP is supported without matched published benchmarks.",
            "TWAP uses complete minute trade closes, not tick-exact TWAP; session VWAP needs traded value/volume.",
            "Price slippage excludes commissions, fees, funding and FX; paper fills do not establish live execution quality.",
            "Operational publication/coverage validation does not certify audited continuous research history.",
            "Filled-order-only costs omit nonexecution/opportunity cost; partial fills remain identified in coverage.",
        ],
        orders=rows,
    )


def freeze(root):
    from systematic_trading.config import AppSettings
    from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
    from systematic_trading.storage import create_transactional_store

    root.mkdir(parents=True, exist_ok=False)
    protocol = dict(version=1, item="P4.19", purpose="Retained execution evidence and benchmark coverage audit",
                    evidence="All retained paper orders; pinned operational benchmark publication; no online inputs",
                    comparison="Signed actual-fill cost versus complete original-intent minute-close TWAP, if available",
                    aggregation="Sum signed costs / sum gross benchmark notional, by currency; positive is worse",
                    average_price_tolerance="0.0001", no_fees_or_live_inference=True,
                    style_ranking_requires="Matched same-decision TWAP/close/VWAP audited coverage; otherwise blocked",
                    preflight_disclosure="Inventory established an empty published benchmark source before this audit",
                    plan_sha256=file_hash(ROOT / "docs/signal-decay-and-alpha-plan.md"))
    (root / "protocol.json").write_text(encoded(protocol), encoding="utf-8")
    for name in SOURCES:
        path = root / "source" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((ROOT / name).read_bytes())
    settings = AppSettings()
    analytics = AnalyticsStore.from_settings(settings)
    publication = analytics.latest("execution-benchmarks")
    documents = []
    if publication:
        provenance = json.loads(publication["provenance"])
        version = digest(encode({"files": provenance["files"], "extractor": provenance["extractor"]}))
        if version != publication["version"]:
            raise ValueError("Benchmark publication version does not match its provenance")
        documents = analytics.query(
            "SELECT point_key, payload, lower(hex(SHA256(payload))) AS payload_sha256 "
            "FROM analytics.documents FINAL WHERE " + analytics._where("execution-benchmarks", version)
            + " ORDER BY point_key")
    orders = create_transactional_store(settings).list_broker_order_records()
    snapshot = dict(captured_at=datetime.now(UTC).isoformat(), orders=[row.model_dump(mode="json") for row in orders],
                    benchmark_publication=publication, benchmark_documents=documents)
    (root / "inputs.json").write_text(encoded(snapshot), encoding="utf-8")
    files = [root / "protocol.json", root / "inputs.json", *(root / "source" / name for name in SOURCES)]
    manifest = dict(files={path.relative_to(root).as_posix(): file_hash(path) for path in files},
                    current_sources={name: file_hash(ROOT / name) for name in SOURCES})
    (root / "manifest.json").write_text(encoded(manifest), encoding="utf-8")


def run(root, *, verify=False):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if file_hash(root / name) != expected:
            raise ValueError("Frozen evidence hash mismatch: " + name)
    for name, expected in manifest["current_sources"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError("Calculation source changed: " + name)
    result = analyze(json.loads((root / "inputs.json").read_text(encoding="utf-8")))
    output = encoded(result)
    path = root / "analysis.json"
    if verify:
        if path.read_text(encoding="utf-8") != output:
            raise ValueError("Frozen result does not reproduce")
    else:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(output)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        freeze(args.root)
    result = run(args.root, verify=args.verify)
    print(encoded({key: result[key] for key in (
        "status", "retained_orders", "published_benchmark_documents", "retained_execution_details",
        "evidence_issue_counts", "twap_status_counts", "per_currency")}))


if __name__ == "__main__":
    main()
