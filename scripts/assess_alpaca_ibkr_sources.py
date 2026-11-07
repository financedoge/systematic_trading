"""Replay the frozen P4.21 source-access diagnostics without acquiring new data."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import gzip
import json
from pathlib import Path
from statistics import median

from compare_alpaca_sip_source import compare, read, read_capture, sha


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research/p421-alpaca-access-20261107-v1"
ARCHIVES = Path("D:/systematic_trading_data/source-archives")
SAMPLE = ARCHIVES / "alpaca/sample-20261107T105628852021Z"
TICKS = ARCHIVES / "ibkr/access-20261107T104817113627Z"
HISTORY = ARCHIVES / "ibkr/access-20261107T105031824028Z"


def verify_receipts(receipts: list[dict]) -> dict:
    """Verify every retained response, including unsuccessful access attempts."""
    manifests = {}
    for receipt in receipts:
        root = Path(receipt["archive"])
        raw = (root / "manifest.json").read_bytes()
        if sha(raw) != receipt["manifest_sha256"]:
            raise ValueError(f"Changed source manifest: {root.name}")
        manifest = json.loads(raw)
        runner = ("probe_alpaca_sip_source.py" if receipt["provider"] == "alpaca"
                  else "probe_ibkr_source_access.py")
        if sha((root / runner).read_bytes()) != manifest["runner_sha256"]:
            raise ValueError("Changed executed acquisition runner")
        for payload in receipt["payloads"]:
            if Path(payload["path"]).name != payload["path"]:
                raise ValueError("Invalid source payload path")
            blob = (root / payload["path"]).read_bytes()
            if sha(blob) != payload["sha256"]:
                raise ValueError("Changed archived response")
            raw_payload = gzip.decompress(blob)
            data = json.loads(raw_payload)
            if receipt["provider"] == "alpaca":
                count = sum(len(rows or []) for rows in data["bars"].values())
                request = next(r for r in manifest["requests"]
                               if r.get("path") == payload["path"])
                if sha(raw_payload) != request["response_sha256"]:
                    raise ValueError("Changed uncompressed API response")
            else:
                count = len(data.get("rows", data.get("ticks", [])))
            if count != payload["rows"]:
                raise ValueError("Source row-count mismatch")
        manifests[str(root)] = manifest
    return manifests


def ib_rows(root: Path, name: str) -> list[dict]:
    return json.loads(gzip.decompress((root / name).read_bytes()))["rows"]


def shares(value) -> int:
    number = Decimal(str(value))
    if number != number.to_integral_value():
        raise ValueError("Fractional share volume needs an explicit contract")
    return int(number)


def interval_diagnostic(alpaca_bars: list[dict]) -> dict:
    ticks = ib_rows(TICKS, "CSL-historical-ticks.json.gz")
    start = int(datetime(2025, 2, 24, 14, 30, tzinfo=timezone.utc).timestamp())
    # Include complete minutes only; the requested page ends partway through one.
    stop = max(row["time"] for row in ticks) // 60 * 60
    selected = [r for r in ticks if start <= r["time"] < stop]
    by_minute, flagged = defaultdict(int), defaultdict(int)
    for row in selected:
        minute = row["time"] // 60 * 60
        by_minute[minute] += shares(row["size"])
        if row["unreported"]:
            flagged[minute] += shares(row["size"])
    alpaca = {}
    for row in alpaca_bars:
        stamp = int(datetime.fromisoformat(row["t"]).timestamp())
        if row["symbol"] == "CSL" and start <= stamp < stop:
            alpaca[stamp] = shares(row["v"])
    bars = ib_rows(HISTORY, "CSL-history-97003.json.gz")
    ib_volume = sum(shares(r["volume"]) for r in bars if start <= int(r["date"]) < stop)
    common = by_minute.keys() & alpaca.keys()
    missing = by_minute.keys() - alpaca.keys()
    return {
        "symbol": "CSL", "date": "2025-02-24",
        "start_utc": datetime.fromtimestamp(start, timezone.utc).isoformat(),
        "end_exclusive_utc": datetime.fromtimestamp(stop, timezone.utc).isoformat(),
        "selection": "Complete minutes in the predeclared 1000-tick access probe; partial final minute excluded",
        "ticks": len(selected), "all_ib_tick_volume": sum(by_minute.values()),
        "ib_ticks_without_unreported_flag_volume": sum(by_minute.values()) - sum(flagged.values()),
        "ib_flagged_tick_volume": sum(flagged.values()),
        "ib_historical_minute_volume": ib_volume, "ib_tick_minutes": len(by_minute),
        "alpaca_observed_minutes": len(alpaca),
        "alpaca_observed_minute_volume": sum(alpaca.values()),
        "common_minutes": len(common),
        "exact_common_minute_volume_matches": sum(by_minute[m] == alpaca[m] for m in common),
        "ib_tick_volume_in_missing_alpaca_minutes": sum(by_minute[m] for m in missing),
        "missing_alpaca_minutes_all_ib_ticks_flagged": all(by_minute[m] == flagged[m] for m in missing),
        "unreported_flag_matches_odd_lot_I_in_full_access_sample": all(
            r["unreported"] == ("I" in r["special_conditions"]) for r in ticks),
        "limitation": "IB unreported is a vendor flag, not proof of absence from the tape; the short interval does not certify full-day filtering or corrections",
    }


def main() -> None:
    inputs = read(STUDY / "source-inputs.json")
    manifests = verify_receipts(inputs["archives"])
    stored_comparison = (SAMPLE / "comparison.json").read_bytes()
    if sha(stored_comparison) != inputs["comparison_sha256"]:
        raise ValueError("Changed source comparison")
    comparison = compare(SAMPLE)  # Rechecks pinned published inputs and prior IB evidence.
    if comparison != json.loads(stored_comparison):
        raise ValueError("Replayed comparison differs from captured assessment")
    manifest, bars = read_capture(SAMPLE)
    rows = comparison["rows"]

    def pct(row):
        return 100 * abs(row["daily_volume_delta_vs_published"]) / row["published_volume"]

    def coverage(row):
        return 100 * row["observed_minute_volume"]["all_observed_minutes"] / row["alpaca_daily_volume"]

    rounded = sum(round(r["alpaca_daily_volume"] / 100) * 100 == r["published_volume"] for r in rows)
    history, tick_manifest = manifests[str(HISTORY)], manifests[str(TICKS)]
    for request in history["histories"] + tick_manifest["histories"]:
        if not request["complete_callback"] or not request["history_returned"]:
            raise ValueError("Incomplete successful historical probe")
    csl = next(r for r in rows if (r["symbol"], r["date"]) == ("CSL", "2025-02-24"))
    all_hours = next(r for r in ib_rows(HISTORY, "CSL-history-97002.json.gz") if r["date"] == "20250224")
    result = {
        "status": "bounded_source_comparison_complete",
        "assessment_runner_sha256": sha(Path(__file__).read_bytes()),
        "source_inputs_sha256": sha((STUDY / "source-inputs.json").read_bytes()),
        "sample_archive": str(SAMPLE), "comparison_sha256": sha(stored_comparison),
        "price_batch": comparison["price_batch"],
        "sample": {
            "stocks": len(manifest["symbols"]), "days_per_stock": len(manifest["dates"]),
            "daily_rows": len(bars["1Day"]), "minute_rows": len(bars["1Min"]),
            **comparison["summary"],
            "max_abs_daily_volume_delta_shares": max(abs(r["daily_volume_delta_vs_published"]) for r in rows),
            "max_abs_daily_volume_difference_pct": max(map(pct, rows)),
            "median_abs_daily_volume_difference_pct": median(map(pct, rows)),
            "max_abs_close_difference_usd": max(abs(r["raw_price_differences_usd"]["close"]) for r in rows),
            "matches_after_nearest_100_rounding": rounded,
            "remaining_rounding_exceptions": len(rows) - rounded,
            "observed_minute_to_daily_volume_pct_range": [min(map(coverage, rows)), max(map(coverage, rows))],
        },
        "stocks": [],
        "ibkr": {
            "historical_ticks": tick_manifest["histories"][0]["row_count"],
            "csl_daily_rth_rows": history["histories"][0]["row_count"],
            "csl_daily_all_hours_rows": history["histories"][1]["row_count"],
            "csl_minute_rows": history["histories"][2]["row_count"],
            "current_quote_api_denials": {s["symbol"]: 10089 for s in history["snapshots"] if 10089 in s["message_codes"]},
            "csl_quote_result": "No ticks or explicit error in bounded frozen quote test",
            "earlier_session_ip_errors_reproduced_on_retry": any(
                m["code"] in (10187, 10197) for m in history["messages"] + tick_manifest["messages"]),
            "operator_reports_no_other_live_session": True, "billing_subscriptions_verified": False,
        },
        "daily_example": {**csl, "ibkr_all_hours_volume": shares(all_hours["volume"])},
        "interval_diagnostic": interval_diagnostic(bars["1Min"]),
        "limitations": [
            "No new universal qualification tolerance was selected",
            "Daily-volume residuals are small but nonzero; nearest-100 rounding is compatible with only 36 of 50 comparisons",
            "Observed minute OHLC bars do not reconstruct complete daily activity",
            "Historical identity, corporate actions, conditions/corrections and point-in-time availability remain subject to qualification",
            "Source agreement can share upstream feed lineage",
        ],
        "catalog_publications": 0, "strategy_replays": 0,
        "source_archive_receipts": inputs["archives"],
    }
    for symbol in manifest["symbols"]:
        selected = [r for r in rows if r["symbol"] == symbol]
        result["stocks"].append({
            "symbol": symbol, "days": len(selected),
            "max_abs_daily_volume_delta_shares": max(abs(r["daily_volume_delta_vs_published"]) for r in selected),
            "max_abs_daily_volume_difference_pct": max(map(pct, selected)),
            "max_abs_close_difference_usd": max(abs(r["raw_price_differences_usd"]["close"]) for r in selected),
            "lowest_observed_minute_to_daily_volume_pct": min(map(coverage, selected)),
        })
    (STUDY / "assessment.json").write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "sample": result["sample"],
                      "interval_diagnostic": result["interval_diagnostic"],
                      "verified_payloads": sum(len(r["payloads"]) for r in inputs["archives"])}))


if __name__ == "__main__":
    main()
