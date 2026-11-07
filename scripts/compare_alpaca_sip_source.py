"""Inspect captured Alpaca bars against pinned publications and prior IB evidence."""
from __future__ import annotations

import argparse
from datetime import datetime
import gzip
import hashlib
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from systematic_trading.research.governed_inputs import GovernedInputs


ROOT = Path(__file__).resolve().parents[1]
PRIOR = ROOT / "research/p421-ibkr-reconcile-20261106-v1"
PRIOR_HASH = "b2dda47ed4a6904f07be2773e92ca4d7986b867386cacb58b4c7778aa3d1ce94"
PRICE_BATCH = "ebffbedaaf8ae35bd5654887f83459156abff13d12537b2bd614e593c64ee77d"
NY = ZoneInfo("America/New_York")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_capture(root: Path) -> tuple[dict, dict]:
    manifest = read(root / "manifest.json")
    if manifest["status"] != "captured_pending_qualification":
        raise ValueError("Incomplete acquisition is not a comparison sample")
    if sha((root / "probe_alpaca_sip_source.py").read_bytes()) != manifest["runner_sha256"]:
        raise ValueError("Changed acquisition runner")
    rows = {"1Day": [], "1Min": []}
    seen = set()
    for receipt in manifest["requests"]:
        params = receipt["parameters"]
        if receipt["status"] != "ok" or receipt["http_status"] != 200:
            raise ValueError("Unsuccessful source receipt")
        if (params["feed"], params["adjustment"], params["asof"]) != ("sip", "raw", "-"):
            raise ValueError("Wrong source basis")
        if Path(receipt["path"]).name != receipt["path"]:
            raise ValueError("Invalid archive path")
        blob = (root / receipt["path"]).read_bytes()
        if sha(blob) != receipt["sha256"]:
            raise ValueError("Changed source archive")
        raw = gzip.decompress(blob)
        if sha(raw) != receipt["response_sha256"]:
            raise ValueError("Changed source payload")
        count = 0
        for symbol, bars in json.loads(raw)["bars"].items():
            for bar in bars or []:
                identity = (params["timeframe"], symbol, bar["t"])
                if identity in seen:
                    raise ValueError("Duplicate source row")
                seen.add(identity)
                rows[params["timeframe"]].append({"symbol": symbol, **bar})
                count += 1
        if count != receipt["row_count"]:
            raise ValueError("Source row-count mismatch")
    for timeframe, bars in rows.items():
        if len(bars) != manifest["series"][timeframe]["rows"]:
            raise ValueError("Aggregate row-count mismatch")
    return manifest, rows


def minute_totals(bars: list[dict]) -> dict:
    """Observed clock bins only: missing minutes are not manufactured or filled."""
    result = {}
    for row in bars:
        local = datetime.fromisoformat(row["t"]).astimezone(NY)
        identity = (row["symbol"], local.date().isoformat())
        totals = result.setdefault(identity, {"minute_bar_count": 0, "all_observed_minutes": 0,
                                             "before_0930": 0, "0930_to_before_1600": 0,
                                             "1600_minute": 0, "1601_onward": 0})
        minute = local.hour * 60 + local.minute
        bucket = ("before_0930" if minute < 570 else "0930_to_before_1600" if minute < 960
                  else "1600_minute" if minute == 960 else "1601_onward")
        totals[bucket] += row["v"]
        totals["all_observed_minutes"] += row["v"]
        totals["minute_bar_count"] += 1
    return result


def compare(root: Path) -> dict:
    manifest, bars = read_capture(root)
    prior_bytes = (PRIOR / "artifact-manifest.json").read_bytes()
    if sha(prior_bytes) != PRIOR_HASH:
        raise ValueError("Changed prior comparison manifest")
    prior_manifest = json.loads(prior_bytes)
    price = read(ROOT / "research/p421-coverage-20261104-v1/pins.json")["price"]
    if price["batch"] != PRICE_BATCH:
        raise ValueError("Changed declared price batch")
    governed = GovernedInputs(Path(price["root"]), PRICE_BATCH)
    symbols, dates = manifest["symbols"], manifest["dates"]
    published, broker = {}, {}
    for symbol in symbols:
        for row in governed.rows(symbol, dates[0], dates[-1]):
            published[symbol, row["trade_date"]] = row
        relative = f"differences/{symbol}.json"
        raw = (PRIOR / relative).read_bytes()
        if sha(raw) != prior_manifest[relative]:
            raise ValueError("Changed prior broker comparison")
        for row in json.loads(raw):
            broker[symbol, row["date"]] = row
    minutes = minute_totals(bars["1Min"])
    differences = []
    for row in bars["1Day"]:
        date = datetime.fromisoformat(row["t"]).astimezone(NY).date().isoformat()
        identity = (row["symbol"], date)
        pub, ib = published[identity], broker[identity]
        activity = minutes.get(identity)
        difference = {"symbol": row["symbol"], "date": date, "alpaca_daily_volume": row["v"],
                      "published_volume": pub["raw_volume"],
                      "ibkr_regular_volume": ib["broker_volume_as_returned"],
                      "daily_volume_delta_vs_published": row["v"] - pub["raw_volume"],
                      "raw_price_differences_usd": {field: row[short] - pub["raw_" + field]
                                                    for field, short in (("open", "o"), ("high", "h"),
                                                                         ("low", "l"), ("close", "c"))},
                      "observed_minute_volume": activity,
                      "daily_minus_observed_minutes": None if activity is None else
                      row["v"] - activity["all_observed_minutes"]}
        differences.append(difference)
    expected = {(s, d) for s in symbols for d in dates}
    observed = {(r["symbol"], r["date"]) for r in differences}
    if observed != expected or len(differences) != len(expected):
        raise ValueError("Comparison coverage differs from frozen capture scope")
    return {"source_manifest_sha256": sha((root / "manifest.json").read_bytes()),
            "source_root": str(root), "price_batch": governed.batch, "published_input_hashes": governed.used,
            "prior_comparison_manifest_sha256": PRIOR_HASH, "rows": differences,
            "summary": {"stock_days": len(differences),
                        "exact_daily_volume_matches": sum(r["daily_volume_delta_vs_published"] == 0 for r in differences),
                        "closes_within_half_cent": sum(abs(r["raw_price_differences_usd"]["close"]) <= .005 for r in differences),
                        "daily_equals_observed_minute_volume": sum(r["daily_minus_observed_minutes"] == 0 for r in differences)},
            "limitations": ["Clock bins do not identify auction or late-report conditions",
                            "Absent minute bars remain absent; totals sum returned observations only",
                            "Historical identity, corrections and historical availability remain unqualified"],
            "catalog_publications": 0, "strategy_input_use": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    args = parser.parse_args()
    result = compare(args.archive)
    path = args.archive / "comparison.json"
    with path.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({"comparison": str(path), **result["summary"]}))


if __name__ == "__main__":
    main()
