"""Replay one-day source reconciliation; raw observations remain in local archives."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal
import gzip
import json
from pathlib import Path

from assess_alpaca_ibkr_sources import verify_receipts
from capture_csl_trade_sources import END, START, STUDY, next_ib_second, timestamp_ns, validate_alpaca
from compare_alpaca_sip_source import compare, read, read_capture, sha
from probe_alpaca_sip_source import save


# Documented CTS/tape A rules, frozen before volume assessment. Unknown flags fail.
A_CONDITIONS = set(" BCEFHIKLMNOPQRTUVXZ45679")
VOLUME_EXCLUDED = {"M", "Q", "9"}
MINUTE_PRICE_EXCLUDED = set("BCHIMNPQRUVZ479")


def alpaca_valid(row: dict) -> bool:
    if row.get("u") not in (None, "canceled", "incorrect", "corrected"):
        raise ValueError("Unknown correction state")
    return row.get("u") not in ("canceled", "incorrect")


def eligible(row: dict, price: bool = False) -> bool:
    conditions = set(row["c"])
    if row["z"] != "A" or conditions - A_CONDITIONS:
        raise ValueError("Unsupported tape/condition rule")
    return alpaca_valid(row) and not conditions.intersection(MINUTE_PRICE_EXCLUDED if price else VOLUME_EXCLUDED)


def load_archive(root: Path) -> tuple[dict, list[tuple[dict, dict]]]:
    manifest = read(root / "manifest.json")
    if sha((root / "capture_csl_trade_sources.py").read_bytes()) != manifest["runner_sha256"]:
        raise ValueError("Changed executed runner")
    if sha((root / "protocol.json").read_bytes()) != manifest["protocol_sha256"]:
        raise ValueError("Changed captured protocol")
    if manifest["protocol_sha256"] != sha((STUDY / "protocol.json").read_bytes()):
        raise ValueError("Changed declared protocol")
    for name, digest in manifest["helper_sha256"].items():
        if sha((root / name).read_bytes()) != digest:
            raise ValueError("Changed executed helper")
    payloads = []
    for receipt in manifest["requests"]:
        if "path" not in receipt:
            continue
        if Path(receipt["path"]).name != receipt["path"]:
            raise ValueError("Invalid payload path")
        blob = (root / receipt["path"]).read_bytes()
        raw = gzip.decompress(blob)
        if sha(blob) != receipt["sha256"] or sha(raw) != receipt["response_sha256"]:
            raise ValueError("Changed source payload")
        payloads.append((receipt, json.loads(raw)))
    return manifest, payloads


def load_alpaca(root: Path) -> tuple[list, dict]:
    manifest, payloads = load_archive(root)
    seen, last_ns, token, rows, pages = set(), START * 10**9, None, [], 0
    for receipt, payload in payloads:
        if not receipt["resource"].endswith("/CSL/trades"):
            continue
        if receipt["http_status"] != 200 or (pages and token is None):
            raise ValueError("Invalid trade page sequence")
        if receipt["parameters"].get("page_token") != token:
            raise ValueError("Broken Alpaca page chain")
        validated, last_ns = validate_alpaca(payload, seen, last_ns)
        rows.extend(validated)
        if "next_page_token" not in payload:
            raise ValueError("Missing page completion")
        token = payload["next_page_token"]
        pages += 1
    if not pages or token is not None:
        raise ValueError("Incomplete Alpaca pagination")
    return rows, {"archive": str(root), "manifest_sha256": sha((root / "manifest.json").read_bytes()),
                  "original_status": manifest["status"], "revalidation": "passed",
                  "trade_pages": pages, "rows": len(rows), "payloads_verified": len(payloads)}


def ib_identity(row: dict) -> tuple:
    return (row["time"], Decimal(row["price"]), Decimal(row["size"]), row["exchange"],
            row["special_conditions"], row["unreported"], row["past_limit"])


def load_ib(root: Path, seen_roots: set | None = None) -> tuple[list, list, list]:
    seen_roots = seen_roots if seen_roots is not None else set()
    if root in seen_roots:
        raise ValueError("Cyclic resume ancestry")
    seen_roots.add(root)
    manifest, payloads = load_archive(root)
    rows, tail, receipts = [], [], []
    if manifest.get("resume_parent"):
        parent = manifest["resume_parent"]
        parent_root = Path(parent["archive"])
        if sha((parent_root / "manifest.json").read_bytes()) != parent["manifest_sha256"]:
            raise ValueError("Changed resume parent")
        rows, _, receipts = load_ib(parent_root, seen_roots)
    cursor = rows[-1]["time"] + 1 if rows else START
    for receipt, payload in payloads:
        if not receipt["complete_callback"] or receipt["error_codes"]:
            continue  # Failure remains retained; it is never a completed data page.
        if len(payload["rows"]) != receipt["row_count"]:
            raise ValueError("Changed IB row count")
        if receipt["parameters"]["endDateTime"]:
            tail = payload["rows"]
            continue
        if receipt["parameters"]["startDateTime"] != datetime.fromtimestamp(cursor, UTC).strftime("%Y%m%d %H:%M:%S UTC"):
            raise ValueError("Discontinuous IB pagination")
        cursor = next_ib_second(payload["rows"], cursor)
        rows.extend(payload["rows"])
    receipts.append({"archive": str(root), "manifest_sha256": sha((root / "manifest.json").read_bytes()),
                     "status": manifest["status"], "payloads_verified": len(payloads)})
    return rows, tail, receipts


def clock_bucket(second: int) -> str:
    offset = second - START
    return ("before_0930" if offset < 34200 else "0930_to_before_1600" if offset < 57600
            else "1600_minute" if offset < 57660 else "1601_onward")


def multiset_match(alpaca: list, ib: list) -> dict:
    # Coarse candidate matching only: IB exposes neither trade ID nor nanoseconds.
    left = Counter((timestamp_ns(r["t"]) // 10**9, Decimal(str(r["p"])), r["s"]) for r in alpaca)
    right = Counter((r["time"], Decimal(r["price"]), int(Decimal(r["size"]))) for r in ib)
    shared = left & right
    return {"matched_occurrences": sum(shared.values()),
            "matched_volume": sum(k[2] * n for k, n in shared.items()),
            "alpaca_unmatched_occurrences": sum((left - right).values()),
            "alpaca_unmatched_volume": sum(k[2] * n for k, n in (left - right).items()),
            "ibkr_unmatched_occurrences": sum((right - left).values()),
            "ibkr_unmatched_volume": sum(k[2] * n for k, n in (right - left).items()),
            "limitation": "Same second/price/size with multiplicity, not proof of unique trade identity"}


def residual_diagnostics(alpaca: list, ib: list) -> dict:
    """Post-capture explanation only; never changes the primary exact comparison."""
    left = Counter((timestamp_ns(r["t"]) // 10**9, Decimal(str(r["p"])), r["s"]) for r in alpaca)
    right = Counter((r["time"], Decimal(r["price"]), int(Decimal(r["size"]))) for r in ib)
    remaining_left, remaining_right = left - right, right - left
    results = {}
    for name, seconds, price_delta in (("ib_one_second_later", 1, Decimal(0)),
                                        ("ib_price_0001_higher_same_second", 0, Decimal("0.0001"))):
        count, volume = 0, 0
        for (second, price, size), occurrences in list(remaining_left.items()):
            key = (second + seconds, price + price_delta, size)
            matched = min(occurrences, remaining_right[key])
            remaining_left[second, price, size] -= matched
            remaining_right[key] -= matched
            count += matched
            volume += matched * size
        results[name] = {"occurrences": count, "shares": volume}
    results["unexplained_alpaca_occurrences"] = sum(remaining_left.values())
    results["unexplained_ib_occurrences"] = sum(remaining_right.values())
    results["interpretation"] = "Exploratory residual patterns, not a matching tolerance, unique trade mapping or established cause"
    return results


def assess(alpaca_root: Path, ib_root: Path) -> dict:
    alpaca, a_receipt = load_alpaca(alpaca_root)
    ib_all, tail, ib_receipts = load_ib(ib_root)
    manifest = read(ib_root / "manifest.json")
    if manifest["status"] != "captured_pending_qualification" or not manifest.get("forward_complete"):
        raise ValueError("Incomplete IB forward coverage")
    ib = [r for r in ib_all if START <= r["time"] < END]
    if not tail or any(not START <= r["time"] < END for r in tail):
        raise ValueError("Backward boundary response not confined to target day")
    tail_seen = Counter(ib_identity(r) for r in tail)
    forward_tail = Counter(ib_identity(r) for r in ib if r["time"] >= min(r["time"] for r in tail))
    if tail_seen != forward_tail:
        raise ValueError("Backward boundary check differs from forward page sequence")
    prior = STUDY.parent / "p421-alpaca-access-20261107-v1"
    source_inputs = read(STUDY / "protocol.json")["existing_input_receipts"]
    verify_receipts(source_inputs["archives"])
    legacy = read(prior / "assessment.json")
    sample = Path(legacy["sample_archive"])
    if sha((sample / "comparison.json").read_bytes()) != source_inputs["comparison_sha256"]:
        raise ValueError("Changed pinned published comparison")
    comparison = read(sample / "comparison.json")
    if compare(sample) != comparison:
        raise ValueError("Pinned published comparison no longer replays")
    _, bars = read_capture(sample)
    published = next(r for r in comparison["rows"] if (r["symbol"], r["date"]) == ("CSL", "2025-02-24"))
    a_bars = {timestamp_ns(r["t"]) // 10**9: r for r in bars["1Min"] if r["symbol"] == "CSL"
              and START * 10**9 <= timestamp_ns(r["t"]) < END * 10**9}
    ib_bar_root = Path("D:/systematic_trading_data/source-archives/ibkr/access-20261107T105031824028Z")
    b_bars = json.loads(gzip.decompress((ib_bar_root / "CSL-history-97003.json.gz").read_bytes()))["rows"]
    b_daily = json.loads(gzip.decompress((ib_bar_root / "CSL-history-97002.json.gz").read_bytes()))["rows"]
    b_bars = {int(r["date"]): r for r in b_bars if START <= int(r["date"]) < END}
    valid = [r for r in alpaca if alpaca_valid(r)]
    volume_eligible = [r for r in alpaca if eligible(r)]
    minutes = defaultdict(lambda: {"alpaca_volume": 0, "alpaca_trades": 0, "alpaca_price_eligible_trades": 0,
                                  "ibkr_volume": 0, "ibkr_without_flag_volume": 0, "ibkr_trades": 0})
    bins = defaultdict(lambda: {"alpaca_eligible_volume": 0, "ibkr_volume": 0, "ibkr_without_flag_volume": 0})
    for row in volume_eligible:
        second = timestamp_ns(row["t"]) // 10**9
        minute = minutes[second // 60 * 60]
        minute["alpaca_volume"] += row["s"]
        minute["alpaca_trades"] += 1
        minute["alpaca_price_eligible_trades"] += int(eligible(row, price=True))
        bins[clock_bucket(second)]["alpaca_eligible_volume"] += row["s"]
    for row in ib:
        size = int(Decimal(row["size"]))
        minute = minutes[row["time"] // 60 * 60]
        minute["ibkr_volume"] += size
        minute["ibkr_without_flag_volume"] += 0 if row["unreported"] else size
        minute["ibkr_trades"] += 1
        bins[clock_bucket(row["time"])]["ibkr_volume"] += size
        bins[clock_bucket(row["time"])]["ibkr_without_flag_volume"] += 0 if row["unreported"] else size
    all_minutes = minutes.keys() | a_bars.keys() | b_bars.keys()
    minute_rows = []
    for stamp in sorted(all_minutes):
        row = {"utc": datetime.fromtimestamp(stamp, UTC).isoformat(), **minutes[stamp],
               "alpaca_bar_present": stamp in a_bars, "ibkr_bar_present": stamp in b_bars,
               "alpaca_bar_volume": a_bars[stamp]["v"] if stamp in a_bars else None,
               "ibkr_bar_volume": int(Decimal(b_bars[stamp]["volume"])) if stamp in b_bars else None}
        minute_rows.append(row)
    missing = [r for r in minute_rows if not r["alpaca_bar_present"] and r["alpaca_trades"]]
    ib_mismatches = [r for r in minute_rows if r["ibkr_bar_present"]
                     and r["ibkr_bar_volume"] != r["ibkr_without_flag_volume"]]
    a_mismatches = [r for r in minute_rows if r["alpaca_bar_present"]
                    and r["alpaca_bar_volume"] != r["alpaca_volume"]]
    condition_groups = defaultdict(lambda: {"records": 0, "size": 0, "eligible_volume": 0})
    updates = defaultdict(lambda: {"records": 0, "size": 0})
    ib_groups = defaultdict(lambda: {"records": 0, "size": 0, "flagged_size": 0})
    for r in alpaca:
        key = "|".join(r["c"])
        condition_groups[key]["records"] += 1
        condition_groups[key]["size"] += r["s"]
        condition_groups[key]["eligible_volume"] += r["s"] if eligible(r) else 0
        updates[r.get("u", "valid/no_update_flag")]["records"] += 1
        updates[r.get("u", "valid/no_update_flag")]["size"] += r["s"]
    for r in ib:
        key = r["special_conditions"]
        ib_groups[key]["records"] += 1
        ib_groups[key]["size"] += int(Decimal(r["size"]))
        ib_groups[key]["flagged_size"] += int(Decimal(r["size"])) if r["unreported"] else 0
    volumes = {
        "published_daily": published["published_volume"], "alpaca_daily": published["alpaca_daily_volume"],
        "alpaca_all_trade_records": sum(r["s"] for r in alpaca),
        "alpaca_valid_or_corrected_trade_records": sum(r["s"] for r in valid),
        "alpaca_condition_eligible_trades": sum(r["s"] for r in volume_eligible),
        "alpaca_observed_minute_bars": sum(r["v"] for r in a_bars.values()),
        "alpaca_eligible_volume_in_absent_minutes": sum(r["alpaca_volume"] for r in missing),
        "ibkr_all_ticks": sum(int(Decimal(r["size"])) for r in ib),
        "ibkr_ticks_without_unreported_flag": sum(int(Decimal(r["size"])) for r in ib if not r["unreported"]),
        "ibkr_all_hours_minute_bars": sum(int(Decimal(r["volume"])) for r in b_bars.values()),
        "ibkr_all_hours_daily_bar": int(Decimal(next(r["volume"] for r in b_daily if r["date"] == "20250224"))),
        "ibkr_regular_daily_bar": published["ibkr_regular_volume"],
    }
    detail = {"minutes": minute_rows, "alpaca_bar_mismatches": a_mismatches, "ibkr_bar_mismatches": ib_mismatches,
              "alpaca_conditions": dict(condition_groups), "alpaca_updates": dict(updates),
              "ibkr_conditions": dict(ib_groups)}
    detail_path = alpaca_root / "full-day-reconciliation.json"
    save(detail_path, detail)
    result = {
        "status": "one_day_source_reconciliation_complete", "symbol": "CSL", "date": "2025-02-24",
        "runner_sha256": sha(Path(__file__).read_bytes()), "protocol_sha256": sha((STUDY / "protocol.json").read_bytes()),
        "sources": [a_receipt, *ib_receipts], "detail_archive": str(detail_path), "detail_sha256": sha(detail_path.read_bytes()),
        "counts": {"alpaca_records": len(alpaca), "alpaca_valid_records": len(valid),
                   "alpaca_volume_eligible_records": len(volume_eligible), "ibkr_in_day_ticks": len(ib),
                   "ibkr_boundary_spill_rows": len(ib_all) - len(ib), "ibkr_backward_check_ticks": len(tail),
                   "alpaca_returned_minutes": len(a_bars), "ibkr_returned_minutes": len(b_bars)},
        "coverage": {"alpaca_first": alpaca[0]["t"], "alpaca_last": alpaca[-1]["t"],
                     "ibkr_first": datetime.fromtimestamp(ib[0]["time"], UTC).isoformat(),
                     "ibkr_last": datetime.fromtimestamp(ib[-1]["time"], UTC).isoformat(),
                     "backward_tail_multiset_exact": True, "ibkr_forward_boundary": manifest["forward_boundary"]},
        "volumes": volumes, "clock_bins": dict(bins), "alpaca_updates": dict(updates),
        "alpaca_conditions": dict(condition_groups), "ibkr_conditions": dict(ib_groups),
        "minute_checks": {"alpaca_present_bar_volume_mismatches": len(a_mismatches),
                          "ibkr_bar_vs_unflagged_tick_mismatches": len(ib_mismatches),
                          "alpaca_absent_minutes_with_eligible_volume": len(missing),
                          "absent_minutes_without_price_eligible_trade": sum(r["alpaca_price_eligible_trades"] == 0 for r in missing),
                          "ibkr_flag_coincides_with_I_all_day": all(r["unreported"] == ("I" in r["special_conditions"]) for r in ib)},
        "filter_decomposition": {
            "odd_lot_shares": sum(int(Decimal(r["size"])) for r in ib if "I" in r["special_conditions"]),
            "flagged_non_odd_lot_records": sum(r["unreported"] and "I" not in r["special_conditions"] for r in ib),
            "flagged_non_odd_lot_shares": sum(int(Decimal(r["size"])) for r in ib if r["unreported"] and "I" not in r["special_conditions"]),
            "official_price_reference_records": len(alpaca) - len(volume_eligible),
            "official_price_reference_sizes_not_activity": sum(r["s"] for r in alpaca if not eligible(r)),
            "condition_size_multisets_equal": Counter(("".join(sorted(c for c in r["c"] if c.strip())), r["s"]) for r in volume_eligible)
                == Counter(("".join(sorted(r["special_conditions"].replace(" ", ""))), int(Decimal(r["size"]))) for r in ib),
        },
        "coarse_trade_match": multiset_match(volume_eligible, ib),
        "post_capture_residual_diagnostics": residual_diagnostics(volume_eligible, ib),
        "limitations": ["One diagnostic day only; no universe-wide qualification",
                        "Historical correction snapshots do not establish dissemination availability",
                        "Cross-source same-second matches do not establish unique trade IDs or independent upstream lineage",
                        "Provider clock/condition contracts remain distinct; no tolerance fitted to residuals"],
        "catalog_publications": 0, "strategy_replays": 0,
    }
    save(STUDY / "assessment.json", result)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("alpaca", type=Path)
    parser.add_argument("ibkr", type=Path)
    args = parser.parse_args()
    result = assess(args.alpaca, args.ibkr)
    print(json.dumps({k: result[k] for k in ("status", "counts", "volumes", "minute_checks", "coarse_trade_match")}))


if __name__ == "__main__":
    main()
