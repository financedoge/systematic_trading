"""Replay the frozen 14-day volume exception inspection; never publishes inputs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import json
from pathlib import Path

from assess_alpaca_ibkr_sources import verify_receipts
from capture_volume_exception_trades import STUDY, key, protocol, retained_state, verified_payload, window
from capture_volume_exception_ibkr import saved_progress
from capture_csl_trade_sources import timestamp_ns
from compare_alpaca_sip_source import compare, read, read_capture, sha
from probe_alpaca_sip_source import save
from reconcile_csl_trades import ib_identity


def eligible(row: dict, rules: dict, price: bool = False) -> bool:
    tape = row["z"]
    if tape not in ("A", "C") or set(row["c"]) - set(rules[tape + "_known"]):
        raise ValueError("Unknown tape/condition rule")
    if row.get("u") not in (None, "canceled", "incorrect", "corrected"):
        raise ValueError("Unknown update state")
    excluded = rules["minute_price_excluded_" + tape] if price else rules["volume_excluded"]
    return row.get("u") not in rules["invalid_update_states"] and not set(row["c"]).intersection(excluded)


def load_manifest(root: Path, provider: str) -> dict:
    manifest = read(root / "manifest.json")
    if manifest["provider"] != provider or manifest["status"] != "captured_pending_qualification":
        raise ValueError("Incomplete or wrong provider capture")
    if manifest["protocol_sha256"] != sha((STUDY / "protocol.json").read_bytes()):
        raise ValueError("Changed protocol")
    for name, digest in manifest["files_sha256"].items():
        if sha((root / name).read_bytes()) != digest:
            raise ValueError("Changed executed recipe file")
    for receipt in manifest["requests"]:
        if "path" in receipt:
            verified_payload(root, receipt)
    return manifest


def alpaca_rows(root: Path, manifest: dict, case: dict) -> list:
    seen, _, _, pages, complete = retained_state(root, manifest, case)
    if not complete or not seen or manifest["cases"][key(case)] != {"rows": len(seen), "pages": pages, "complete": True}:
        raise ValueError("Case completeness mismatch")
    return [row for receipt in manifest["requests"] if receipt["case"] == key(case) and receipt.get("http_status") == 200
            for row in verified_payload(root, receipt)["trades"]]


def ib_rows(root: Path, manifest: dict, case: dict) -> tuple[list, dict]:
    _, pages, boundary, tail_complete = saved_progress(root, manifest, case)
    if not boundary or not tail_complete:
        raise ValueError("Incomplete independent IB control")
    start, end = window(case)
    rows, tail, spill = [], [], 0
    for receipt in manifest["requests"]:
        if receipt["case"] != key(case) or not receipt["complete_callback"] or receipt["error_codes"]:
            continue
        captured = verified_payload(root, receipt)["rows"]
        if receipt["direction"] == "tail":
            tail.extend(captured)
        else:
            rows.extend(r for r in captured if start <= r["time"] < end)
            spill += sum(not start <= r["time"] < end for r in captured)
    if not tail or any(not start <= r["time"] < end for r in tail):
        raise ValueError("Backward control outside target day")
    cutoff = min(r["time"] for r in tail)
    if Counter(ib_identity(r) for r in tail) != Counter(ib_identity(r) for r in rows if r["time"] >= cutoff):
        raise ValueError("Independent backward control differs from forward pages")
    return rows, {"forward_pages": pages, "tail_rows": len(tail), "spill_rows": spill,
                  "backward_tail_multiset_exact": True}


def bucket(stamp: int, start: int) -> str:
    minute = (stamp - start) // 60
    return ("before_0930" if minute < 570 else "0930_to_before_1600" if minute < 960
            else "1600_minute" if minute == 960 else "1601_onward")


def summarize_case(case: dict, rows: list, bars: list, old: dict, rules: dict) -> tuple[dict, dict]:
    start, end = window(case)
    valid = [r for r in rows if eligible(r, rules)]
    minutes = defaultdict(lambda: {"volume": 0, "count": 0, "price_eligible_count": 0})
    bins = defaultdict(int)
    groups, updates = defaultdict(lambda: {"records": 0, "size": 0, "eligible_volume": 0}), Counter()
    for row in rows:
        label = "|".join(row["c"])
        groups[label]["records"] += 1
        groups[label]["size"] += row["s"]
        groups[label]["eligible_volume"] += row["s"] if eligible(row, rules) else 0
        updates[row.get("u", "valid/no_update_flag")] += 1
    for row in valid:
        stamp = timestamp_ns(row["t"]) // 10**9
        minutes[stamp // 60 * 60]["volume"] += row["s"]
        minutes[stamp // 60 * 60]["count"] += 1
        minutes[stamp // 60 * 60]["price_eligible_count"] += int(eligible(row, rules, price=True))
        bins[bucket(stamp, start)] += row["s"]
    observed = {timestamp_ns(r["t"]) // 10**9: r for r in bars if r["symbol"] == case["symbol"]
                and start * 10**9 <= timestamp_ns(r["t"]) < end * 10**9}
    mismatches = [{"second": second, "bar_volume": bar["v"], "trade_volume": minutes[second]["volume"]}
                  for second, bar in observed.items() if bar["v"] != minutes[second]["volume"]]
    absent = [{"second": second, **data} for second, data in minutes.items() if second not in observed]
    volume = sum(r["s"] for r in valid)
    result = {**case, "records": len(rows), "eligible_records": len(valid),
              "all_record_sizes": sum(r["s"] for r in rows), "eligible_volume": volume,
              "archived_daily_volume": old["alpaca_daily_volume"], "published_volume": old["published_volume"],
              "eligible_minus_archived_daily": volume - old["alpaca_daily_volume"],
              "eligible_minus_published": volume - old["published_volume"],
              "relative_published_difference_pct": 100 * (volume - old["published_volume"]) / old["published_volume"],
              "nearest_100_minus_published": round(volume / 100) * 100 - old["published_volume"],
              "retained_ibkr_regular_bar": old["ibkr_regular_volume"],
              "observed_minute_count": len(observed), "observed_minute_volume": sum(r["v"] for r in observed.values()),
              "present_minute_volume_mismatches": len(mismatches), "absent_minutes_with_activity": len(absent),
              "absent_minute_volume": sum(r["volume"] for r in absent),
              "absent_minutes_without_price_trade": sum(r["price_eligible_count"] == 0 for r in absent),
              "clock_bins": dict(bins), "update_counts": dict(updates),
              "first_trade": rows[0]["t"], "last_trade": rows[-1]["t"], "independent_ibkr_tick_control": None}
    detail = {"conditions": dict(groups), "absent_minutes": absent, "bar_volume_mismatches": mismatches}
    return result, detail


def independent_control(case: dict, a_rows: list, ib: list, rules: dict, old: dict) -> dict:
    start, _ = window(case)
    filtered = [r for r in a_rows if eligible(r, rules)]
    a_groups = Counter(("".join(sorted(c for c in r["c"] if c.strip() and c != "@")), r["s"]) for r in filtered)
    b_groups = Counter(("".join(sorted(r["special_conditions"].replace(" ", "").replace("@", ""))), int(Decimal(r["size"]))) for r in ib)
    bins, unflagged_bins = defaultdict(int), defaultdict(int)
    for row in ib:
        size = int(Decimal(row["size"]))
        label = bucket(row["time"], start)
        bins[label] += size
        unflagged_bins[label] += 0 if row["unreported"] else size
    a_bins = defaultdict(int)
    for row in filtered:
        a_bins[bucket(timestamp_ns(row["t"]) // 10**9, start)] += row["s"]
    volume = sum(int(Decimal(r["size"])) for r in ib)
    return {"rows": len(ib), "volume": volume, "delta_vs_alpaca_eligible": volume - sum(r["s"] for r in filtered),
            "condition_size_multisets_exact": a_groups == b_groups,
            "alpaca_unmatched_condition_size_occurrences": sum((a_groups - b_groups).values()),
            "ibkr_unmatched_condition_size_occurrences": sum((b_groups - a_groups).values()),
            "clock_bins_exact": dict(a_bins) == dict(bins), "clock_bins": dict(bins),
            "unflagged_clock_bins": dict(unflagged_bins),
            "unflagged_rth_minus_retained_bar": unflagged_bins["0930_to_before_1600"] - old["ibkr_regular_volume"],
            "limitation": "Regular sale is normalized across feed encodings; matching condition/size multisets does not establish unique trade identity"}


def assess(alpaca_root: Path, ibkr_root: Path) -> dict:
    p = protocol()
    comparison_path = Path(p["comparison_archive"])
    if sha(comparison_path.read_bytes()) != p["comparison_sha256"]:
        raise ValueError("Changed original comparison")
    comparison = read(comparison_path)
    if compare(comparison_path.parent) != comparison:
        raise ValueError("Pinned published comparison no longer replays")
    expected = {(r["symbol"], r["date"]) for r in comparison["rows"]
                if round(r["alpaca_daily_volume"] / 100) * 100 != r["published_volume"]}
    if expected != {(c["symbol"], c["date"]) for c in p["cases"]} or len(expected) != 14:
        raise ValueError("Changed frozen case selection")
    verify_receipts(p["existing_source_inputs"]["archives"])
    _, bars = read_capture(comparison_path.parent)
    a_manifest, b_manifest = load_manifest(alpaca_root, "alpaca"), load_manifest(ibkr_root, "ibkr")
    records, details = [], {}
    for case in p["cases"]:
        rows = alpaca_rows(alpaca_root, a_manifest, case)
        old = next(r for r in comparison["rows"] if (r["symbol"], r["date"]) == (case["symbol"], case["date"]))
        result, detail = summarize_case(case, rows, bars["1Min"], old, p["rules"])
        if any(key(case) == key(c) for c in p["ibkr_tick_controls"]):
            ib, coverage = ib_rows(ibkr_root, b_manifest, case)
            result["independent_ibkr_tick_control"] = {**coverage, **independent_control(case, rows, ib, p["rules"], old)}
        records.append(result)
        details[key(case)] = detail
    detail_path = alpaca_root / "exception-reconciliation.json"
    save(detail_path, details)
    result = {"status": "fourteen_exception_comparison_complete_qualification_open", "cases": records,
              "summary": {"stock_days": len(records), "symbols": len({r["symbol"] for r in records}),
                          "source_trade_records": sum(r["records"] for r in records),
                          "daily_reconstruction_exact": sum(r["eligible_minus_archived_daily"] == 0 for r in records),
                          "present_minute_volume_mismatches": sum(r["present_minute_volume_mismatches"] for r in records),
                          "published_exact_matches": sum(r["eligible_minus_published"] == 0 for r in records),
                          "nearest_100_matches": sum(r["nearest_100_minus_published"] == 0 for r in records),
                          "independent_ibkr_controls": sum(r["independent_ibkr_tick_control"] is not None for r in records)},
              "sources": [{"archive": str(root), "manifest_sha256": sha((root / "manifest.json").read_bytes()),
                           "requests": len(m["requests"]), "payloads": sum("path" in r for r in m["requests"])}
                          for root, m in ((alpaca_root, a_manifest), (ibkr_root, b_manifest))],
              "protocol_sha256": sha((STUDY / "protocol.json").read_bytes()),
              "runner_sha256": sha(Path(__file__).read_bytes()), "detail_archive": str(detail_path),
              "detail_sha256": sha(detail_path.read_bytes()), "catalog_publications": 0, "strategy_replays": 0,
              "limitations": ["Exceptions selected from an already inspected sample; not random independent validation",
                              "Independent tick controls cover three cases only",
                              "Historical capture does not establish publication/correction availability",
                              "Matching a provider's bars to its trades is internal reconciliation, not independent validation"]}
    save(STUDY / "assessment.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("alpaca", type=Path)
    parser.add_argument("ibkr", type=Path)
    args = parser.parse_args()
    result = assess(args.alpaca, args.ibkr)
    print(json.dumps({"status": result["status"], "summary": result["summary"]}))


if __name__ == "__main__":
    main()
