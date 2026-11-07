"""Replay five frozen daily-volume residuals against retained trade responses."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from decimal import Decimal
import gzip
import json
from pathlib import Path

import capture_large_volume_sources as scope
import reconcile_volume_exceptions as shared
import p421_sip_volume_pilot as pilot
from capture_csl_trade_sources import timestamp_ns
from capture_volume_exception_trades import key, window
from probe_alpaca_sip_source import save, sha
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest


def baseline(p):
    pilot.protocol()
    compact = pilot.STUDY / "artifact-manifest.json"
    if sha(compact.read_bytes()) != p["prior_pilot_manifest_sha256"]:
        raise ValueError("Prior pilot findings changed")
    for name, expected in json.loads(compact.read_text()).items():
        pilot.checked(pilot.STUDY / name, expected)
    ref = p["baseline"]
    root = Path(ref["root"])
    pilot.checked(root / "manifest.json", ref["batch"])
    for name, expected in json.loads((root / "manifest.json").read_text()).items():
        pilot.checked(root / name, expected)
    with gzip.open(root / "rows.jsonl.gz", "rt", encoding="utf8") as handle:
        frozen = {r["symbol"] + "/" + r["activity_date"]: r for line in handle if (r := json.loads(line))}
    store = AnalyticsStore.from_settings(AppSettings())
    rows = store.pinned_rows("observations", ref["source_id"], ref["batch"])
    from systematic_trading.market_data.analytics_store import encode

    if {r["point_key"]:digest(r["payload"]) for r in rows} != {k:digest(encode(v)) for k,v in frozen.items()}:
        raise ValueError("Native pilot publication differs from frozen payloads")
    if any(r["available_at"] is not None for r in rows):
        raise ValueError("Historical availability was invented")
    largest = sorted(frozen.values(), key=lambda r:abs(r["volume_delta_percent"]), reverse=True)[:5]
    if [(r["symbol"], r["activity_date"]) for r in largest] != [(c["symbol"], c["date"]) for c in p["cases"]]:
        raise ValueError("Frozen five-case selection changed")
    return frozen


def condition(row, provider):
    codes = row["c"] if provider == "alpaca" else row["special_conditions"]
    return "".join(sorted(c for c in codes if c.strip() and c != "@"))


def strict_shares(value):
    n = Decimal(str(value))
    if not n.is_finite() or n < 0 or n != n.to_integral_value():
        raise ValueError("Nonintegral or invalid IBKR share volume")
    return int(n)


def signature(row, provider):
    price = Decimal(str(row["p"] if provider == "alpaca" else row["price"]))
    if not price.is_finite() or price <= 0:
        raise ValueError("Invalid trade price")
    size = row["s"] if provider == "alpaca" else strict_shares(row["size"])
    return str(price.normalize()), size, condition(row, provider)


def residual_records(rows, counts, provider):
    remaining, result = counts.copy(), []
    for r in rows:
        sig = signature(r, provider)
        if remaining[sig]:
            result.append(r)
            remaining[sig] -= 1
    return result


def compare_case(case, trades, old, rules, ib=None):
    valid = [r for r in trades if shared.eligible(r, rules)]
    groups = defaultdict(lambda:dict(records=0, size=0, eligible_volume=0))
    updates, bins = Counter(), defaultdict(int)
    start, _ = window(case)
    for r in trades:
        update = r.get("u") or "no_update_flag"
        group = groups["|".join(r["c"]) + ";" + update]
        group["records"] += 1
        group["size"] += r["s"]
        if shared.eligible(r, rules):
            group["eligible_volume"] += r["s"]
            bins[shared.bucket(timestamp_ns(r["t"]) // 10**9, start)] += r["s"]
        updates[update] += 1
    total = sum(r["s"] for r in valid)
    result = dict(**case, records=len(trades), eligible_records=len(valid), eligible_volume=total,
                  all_record_sizes=sum(r["s"] for r in trades), source_update_states=dict(updates),
                  retained_sip_daily=old["sip_raw_volume"], retained_published_volume=old["published_raw_volume"],
                  trades_minus_sip_daily=total-old["sip_raw_volume"],
                  trades_minus_published=total-old["published_raw_volume"],
                  clock_bins=dict(bins), independent_ibkr=None)
    detail = dict(condition_update_groups=dict(groups), alpaca_unmatched=[], ibkr_unmatched=[])
    if ib is not None:
        for r in ib:
            strict_shares(r["size"])
        control = shared.independent_control(case, trades, ib, rules,
                                            {"ibkr_regular_volume": old["ibkr_regular_volume"]})
        a, b = Counter(signature(r, "alpaca") for r in valid), Counter(signature(r, "ibkr") for r in ib)
        a_only, b_only = a-b, b-a
        control.update(delta_vs_sip_daily=control["volume"]-old["sip_raw_volume"],
                       delta_vs_published=control["volume"]-old["published_raw_volume"],
                       price_size_condition_multisets_exact=a == b,
                       alpaca_only_occurrences=sum(a_only.values()), ibkr_only_occurrences=sum(b_only.values()),
                       alpaca_only_shares=sum(k[1]*n for k,n in a_only.items()),
                       ibkr_only_shares=sum(k[1]*n for k,n in b_only.items()))
        detail.update(alpaca_unmatched=residual_records(valid,a_only,"alpaca"),
                      ibkr_unmatched=residual_records(ib,b_only,"ibkr"))
        result["independent_ibkr"] = control
    return result, detail


def assess(alpaca_root, ibkr_root=None):
    scope.configure()
    p = scope.protocol()
    frozen = baseline(p)
    am = shared.load_manifest(alpaca_root, "alpaca")
    bm = shared.load_manifest(ibkr_root, "ibkr") if ibkr_root else None
    records, details = [], {}
    for case in p["cases"]:
        old = dict(frozen[case["symbol"] + "/" + case["date"]])
        previous = pilot.prior_artifact("p421-ibkr-reconcile-20261106-v1", f"differences/{case['symbol']}.json")
        old["ibkr_regular_volume"] = next(r["broker_volume_as_returned"] for r in previous if r["date"] == case["date"])
        trades = shared.alpaca_rows(alpaca_root, am, case)
        ib, coverage = shared.ib_rows(ibkr_root, bm, case) if ibkr_root else (None, None)
        row, detail = compare_case(case, trades, old, p["rules"], ib)
        if coverage is not None:
            row["independent_ibkr"].update(coverage)
        records.append(row)
        details[key(case)] = detail
    stage = "complete" if bm else "alpaca-only"
    detail_path = alpaca_root / ("large-residuals-" + stage + ".json")
    save(detail_path, details)
    result = dict(status="comparison_complete" if bm else "alpaca_reconstructed_independent_control_pending",
                  protocol_sha256=scope.PROTOCOL_HASH, baseline=p["baseline"], cases=records,
                  sources=[dict(archive=str(r), manifest_sha256=sha((r / "manifest.json").read_bytes()),
                               requests=len(m["requests"]), payloads=sum("path" in v for v in m["requests"]))
                           for r,m in [(alpaca_root, am), *([(ibkr_root, bm)] if bm else [])]],
                  summary=dict(cases=len(records), trade_records=sum(r["records"] for r in records),
                               exact_alpaca_daily=sum(r["trades_minus_sip_daily"] == 0 for r in records),
                               independent_ibkr_cases=sum(r["independent_ibkr"] is not None for r in records)),
                  details=dict(path=str(detail_path), sha256=sha(detail_path.read_bytes())),
                  limitations=["Case selection is diagnostic, not random validation.",
                               "No retrospective publication/correction availability inferred.",
                               "Condition/price/size multisets do not identify unique cross-provider trades.",
                               "No source replacement, strategy replay or promotion."],
                  runner_sha256=sha(Path(__file__).read_bytes()))
    save(scope.STUDY / ("assessment.json" if bm else "alpaca-reconstruction.json"), result)
    print(json.dumps(dict(status=result["status"], summary=result["summary"],
        cases=[{k:r[k] for k in ("symbol","date","eligible_volume","trades_minus_sip_daily","trades_minus_published","source_update_states","independent_ibkr")} for r in records])), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("alpaca", type=Path)
    parser.add_argument("--ibkr", type=Path)
    args = parser.parse_args()
    assess(args.alpaca, args.ibkr)
