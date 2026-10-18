"""P4.19 matched retrospective references; read-only published inputs, immutable replay."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts.analyze_execution_timing import evidence_issues, encoded, file_hash  # noqa: E402
from systematic_trading.domain.execution import BrokerOrderRecord  # noqa: E402
from systematic_trading.execution.benchmark_archive import validate_ready  # noqa: E402
from systematic_trading.execution.benchmark_qualification import POLICY, PublishedDaily, qualify  # noqa: E402
from systematic_trading.execution.twap_benchmark import benchmark_window, calculate_twap, session_window  # noqa: E402
from systematic_trading.market_data.analytics_store import digest, encode  # noqa: E402


SOURCES = ["scripts/analyze_execution_references.py", "scripts/analyze_execution_timing.py",
    "src/systematic_trading/domain/execution.py", "src/systematic_trading/domain/enums.py",
    "src/systematic_trading/execution/benchmark_qualification.py",
    "src/systematic_trading/execution/benchmark_archive.py", "src/systematic_trading/execution/twap_benchmark.py",
    "src/systematic_trading/live/trading_calendar.py", "src/systematic_trading/research/governed_inputs.py",
    "src/systematic_trading/research/price_governance.py", "src/systematic_trading/market_data/analytics_store.py"]
STYLES = ("original_twap", "original_close", "original_vwap", "routed_twap", "routed_close", "routed_vwap")
PROTOCOL = dict(version=1, item="P4.19", universe="All retained filled IB paper USD TWAP orders; no symbol selection",
    matching="Same local order, symbol, side, executed quantity; all six references required",
    eligible="Complete unique execution IDs, quantity/average/identity checks; fills on routed US session",
    price_cost="side_sign * (quantity-weighted actual fill - reference) * executed quantity; positive is worse",
    aggregation="Sum signed USD price cost / gross reference notional * 10000; never net buys/sells",
    comparisons="Original and routed date comparisons kept distinct; intervening market movement is not isolated approval causality",
    reference_qualification=POLICY, no_style_ranking=True,
    inference="Descriptive paper-fill reference comparison only; no achievable execution-style effect or strategy performance inference")


def key_for(symbol, start, end):
    return sha256(f"v1:{symbol}:{start.isoformat()}:{end.isoformat()}".encode()).hexdigest()


def verify_documents(snapshot, source):
    item = snapshot[source]
    publication, docs = item["publication"], item["documents"]
    if not publication or len(docs) != publication["document_count"]:
        raise ValueError("Missing or incomplete publication: " + source)
    hashes = {d["point_key"]: digest(d["payload"]) for d in docs}
    if len(hashes) != len(docs):
        raise ValueError("Duplicate published identity")
    provenance = json.loads(publication["provenance"])
    if source == "execution-reference-audits":
        if hashes != provenance["document_hashes"] or digest(encode(hashes)) != publication["version"]:
            raise ValueError("Reference publication hash mismatch")
    else:
        if digest(encode(dict(files=provenance["files"], extractor=provenance["extractor"]))) != publication["version"]:
            raise ValueError("Benchmark publication provenance mismatch")
    if any(digest(d["payload"]) != d["payload_sha256"] for d in docs):
        raise ValueError("Document hash mismatch")
    return {d["point_key"]: json.loads(d["payload"]) for d in docs}


def references(record, audits, benchmarks, evidence_root, cutoff):
    prices, dates, deviations = {}, {}, {}
    for label, original in (("original", True), ("routed", False)):
        session_start, session_end = session_window(record, original_intent=original)
        session_key = key_for(record.order.symbol, session_start, session_end)
        audit = audits.get(session_key)
        if not audit or audit["status"] != "qualified_with_limitations":
            raise ValueError(label + " session: " + (audit or {}).get("message", "no published qualified reference"))
        if audit["purpose"] != POLICY["purpose"]:
            raise ValueError("Wrong reference usage contract")
        session = audit["session"]
        validate_ready(session, root=evidence_root, symbol=record.order.symbol, start=session_start, end=session_end)
        replay = dict(qualify(session, audit["daily"]), session_key=session_key)
        if replay != audit:
            raise ValueError("Reference audit does not reproduce")
        start, end = benchmark_window(record, original_intent=original)
        candidate = benchmarks.get(key_for(record.order.symbol, start, end))
        if candidate is None:
            raise ValueError(label + " TWAP: no published window")
        validate_ready(candidate, root=evidence_root, symbol=record.order.symbol, start=start, end=end)
        if candidate["contract"] != session["contract"]:
            raise ValueError("Window/session contract mismatch")
        if any(datetime.fromisoformat(c["observed_at"]) > cutoff for c in (session, candidate)):
            raise ValueError("Observation after frozen cutoff")
        # Both windows and sessions must be on precisely the same retained price
        # vintage for their overlapping minutes. Do not hide provider revisions.
        session_prices = {datetime.fromisoformat(b["at"]): Decimal(b["close"]) for b in session["bars"]}
        if any(session_prices.get(datetime.fromisoformat(b["at"])) != Decimal(b["close"])
               for b in candidate["bars"] if start <= datetime.fromisoformat(b["at"]) < end):
            raise ValueError("Window/session observation revision mismatch")
        prices[label + "_twap"] = str(calculate_twap(candidate["bars"], start, end)[0])
        prices[label + "_close"] = audit["reference_prices"]["close"]
        prices[label + "_vwap"] = audit["reference_prices"]["session_vwap"]
        dates[label] = audit["session_date"]
        deviations[label] = audit["ohlc_difference_bps"]
    if any(f.filled_at.astimezone(ZoneInfo("America/New_York")).date().isoformat() != dates["routed"]
           or not session_start <= f.filled_at <= session_end for f in record.execution_fills):
        raise ValueError("Execution occurred outside the routed session date")
    return prices, dates, deviations


def summarize(rows):
    if not rows:
        return dict(orders=0, styles={})
    styles = {}
    for style in STYLES:
        cost = sum(Decimal(r["price_cost"][style]) for r in rows)
        notional = sum(Decimal(r["prices"][style]) * r["filled_quantity"] for r in rows)
        styles[style] = dict(price_cost_usd=str(cost), gross_reference_notional_usd=str(notional),
                             signed_bps=str(cost / notional * 10000))
    return dict(orders=len(rows), styles=styles)


def analyze(snapshot, root):
    audits = verify_documents(snapshot, "execution-reference-audits")
    benchmarks = verify_documents(snapshot, "execution-benchmarks")
    if audits["policy"] != dict(POLICY, qualifier_source_sha256=file_hash(ROOT / SOURCES[4])):
        raise ValueError("Published policy differs from frozen analysis contract")
    records = [BrokerOrderRecord.model_validate(r) for r in snapshot["orders"]]
    if len({r.local_order_id for r in records}) != len(records):
        raise ValueError("Duplicate local order identity")
    ids = Counter(f.execution_id for r in records for f in r.execution_fills)
    rows = []
    for record in records:
        if record.environment.value != "paper" or not record.filled_quantity:
            continue
        row = dict(local_order_id=record.local_order_id, symbol=record.order.symbol, side=record.order.side.value,
                   filled_quantity=record.filled_quantity, requested_quantity=record.order.quantity,
                   status="excluded", issues=evidence_issues(record, ids))
        if record.broker != "interactive-brokers" or record.order.environment.value != "paper" or record.order.currency.value != "USD":
            row["issues"].append("unsupported broker/environment/currency")
        try:
            prices, dates, deviations = references(record, audits, benchmarks, root / "evidence", datetime.fromisoformat(snapshot["captured_at"]))
            if not row["issues"]:
                average = sum(f.average_price * f.quantity for f in record.execution_fills) / record.filled_quantity
                sign = 1 if record.order.side.value == "buy" else -1
                row.update(status="matched", prices=prices, dates=dates, ohlc_difference_bps=deviations,
                    average_fill_price=str(average), delayed_session=dates["original"] != dates["routed"],
                    price_cost={k: str(sign * (average - Decimal(p)) * record.filled_quantity) for k, p in prices.items()})
        except (ValueError, KeyError, OSError, TypeError, ArithmeticError) as exc:
            row["issues"].append(str(exc))
        rows.append(row)
    ready = [r for r in rows if r["status"] == "matched"]
    sessions = sorted({r["dates"]["routed"] for r in ready})
    leave_one_out = {d: summarize([r for r in ready if r["dates"]["routed"] != d]) for d in sessions}
    return dict(status="descriptive_reference_comparison" if ready else "no_matched_evidence", paper_filled_orders=len(rows),
        exclusions=dict(Counter(i for r in rows for i in r["issues"])), matched=summarize(ready),
        same_date=summarize([r for r in ready if not r["delayed_session"]]),
        delayed_date=summarize([r for r in ready if r["delayed_session"]]),
        by_symbol={s: summarize([r for r in ready if r["symbol"] == s]) for s in sorted({r["symbol"] for r in rows})},
        by_routed_date={d: summarize([r for r in ready if r["dates"]["routed"] == d]) for d in sessions},
        leave_one_session_out=leave_one_out,
        original_minus_routed_twap_cost_usd=str(sum(Decimal(r["price_cost"]["original_twap"])
            - Decimal(r["price_cost"]["routed_twap"]) for r in ready)),
        rows=rows, conclusion="Do not rank or change execution styles from this descriptive paper sample",
        limitations=POLICY["limitations"])


def freeze(root):
    from systematic_trading.config import AppSettings
    from systematic_trading.market_data.analytics_store import AnalyticsStore
    from systematic_trading.storage.factory import create_transactional_store
    root.mkdir(parents=True, exist_ok=False)
    (root / "protocol.json").write_text(encoded(PROTOCOL), encoding="utf-8")
    settings = AppSettings()
    analytics = AnalyticsStore.from_settings(settings)
    snapshot = dict(captured_at=datetime.now(UTC).isoformat(),
        orders=[r.model_dump(mode="json") for r in create_transactional_store(settings).list_broker_order_records()])
    for source in ("execution-benchmarks", "execution-reference-audits"):
        pub = analytics.latest(source)
        if pub is None:
            raise ValueError("No published input: " + source)
        docs = [dict(point_key=r['point_key'],payload=r['payload'],payload_sha256=digest(r['payload']))
            for r in analytics.pinned_rows('documents',source,pub['version'],order=[('point_key','ASC')])]
        snapshot[source] = dict(publication=pub, documents=docs)
    audits = verify_documents(snapshot, "execution-reference-audits")
    daily = PublishedDaily(analytics)
    snapshot["governance_catalog_publication"] = analytics.latest("governance/catalog")
    if snapshot["governance_catalog_publication"]["version"] != daily.batch:
        raise ValueError("Governed catalog advanced during freeze")
    candidates = list(verify_documents(snapshot, "execution-benchmarks").values())
    for key, audit in audits.items():
        if key == "policy" or audit["status"] != "qualified_with_limitations":
            continue
        verified = daily.get(audit["symbol"], audit["session_date"])
        if any(verified[k] != audit["daily"][k] for k in ("row", "row_sha256", "actions", "catalog_batch", "storage_batch")):
            raise ValueError("Published governed qualification changed; wait for app refresh")
        candidates.append(audit["session"])
    for c in candidates:
        start, end = (datetime.fromisoformat(c[k]) for k in ("window_start", "window_end"))
        validate_ready(c, root=settings.data_dir, symbol=c["symbol"], start=start, end=end)
        ref = c["audit"]["raw_ref"]
        target = root / "evidence" / ref
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((settings.data_dir / ref).read_bytes())
    # Preserve checked published history files alongside the row-level snapshot.
    for name in list(daily.inputs.used):
        relative = name
        while relative.startswith("parent/"):
            relative = relative[len("parent/"):]
        source = daily.inputs.checked(relative)
        target = root / "governed" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    parent = daily.inputs
    while parent:
        source = parent.root / "manifest.json"
        target = root / "governed" / "manifests" / (file_hash(source) + ".json")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
        parent = parent.parent
    snapshot["governed_input_hashes"] = dict(daily.inputs.used)
    (root / "inputs.json").write_text(encoded(snapshot), encoding="utf-8")
    for name in SOURCES:
        target = root / "source" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT / name).read_bytes())
    manifest = dict(files={p.relative_to(root).as_posix(): file_hash(p) for p in root.rglob("*") if p.is_file()},
                    current_sources={name: file_hash(ROOT / name) for name in SOURCES})
    (root / "manifest.json").write_text(encoded(manifest), encoding="utf-8")


def run(root, verify=False):
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files"].items():
        if file_hash(root / name) != expected:
            raise ValueError("Frozen evidence changed: " + name)
    for name, expected in manifest["current_sources"].items():
        if file_hash(ROOT / name) != expected:
            raise ValueError("Calculation source changed: " + name)
    if json.loads((root / "protocol.json").read_text(encoding="utf-8")) != PROTOCOL:
        raise ValueError("Frozen protocol changed")
    result = analyze(json.loads((root / "inputs.json").read_text(encoding="utf-8")), root)
    output = encoded(result)
    if verify:
        if (root / "analysis.json").read_text(encoding="utf-8") != output:
            raise ValueError("Analysis does not reproduce")
    else:
        with (root / "analysis.json").open("x", encoding="utf-8") as stream:
            stream.write(output)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--freeze", action="store_true")
    mode.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    if args.freeze:
        freeze(args.root)
    result = run(args.root, args.verify)
    print(encoded({k: result[k] for k in ("status", "paper_filled_orders", "exclusions", "matched", "same_date", "delayed_date")}))
