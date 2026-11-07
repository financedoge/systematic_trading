"""Actual-calendar control for the largest CRSP/SIP daily-volume difference."""
import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path

import capture_early_close_sources as scope
import reconcile_volume_exceptions as shared
from reconcile_large_volume_sources import baseline, signature, strict_shares
from capture_csl_trade_sources import timestamp_ns
from probe_alpaca_sip_source import ROOT, save, sha


def clock_bucket(stamp, opened, closed):
    if stamp < opened:
        return "before_open"
    if stamp < closed:
        return "regular_before_close"
    if stamp < closed + 60:
        return "closing_minute"
    return "after_closing_minute"


def assess(alpaca_root, ibkr_root):
    prior = json.loads((ROOT / "research/p421-large-volume-20261107-v1/protocol.json").read_text())
    frozen = baseline(prior)
    scope.configure()
    p = scope.base.protocol()
    ref = p["crsp_comparison"]
    raw = Path(ref["details_path"]).read_bytes()
    if sha(raw) != ref["details_sha256"]:
        raise ValueError("Changed CRSP selection evidence")
    crsp = json.loads(raw)["rows"]
    largest = max(crsp,key=lambda r:abs(r["volume_vs_sip_percent"]))
    case = p["cases"][0]
    if (largest["symbol"],largest["date"]) != (case["symbol"],case["date"]):
        raise ValueError("Changed early-close case selection")
    calendar = json.loads((scope.STUDY / "calendar.json").read_text())
    if calendar["session"] != case["date"] or not calendar["close_new_york"].endswith("13:00:00-04:00"):
        raise ValueError("Wrong early-close calendar")
    opened,closed = [int(datetime.fromisoformat(calendar[k]).timestamp()) for k in ("open_utc","close_utc")]
    am,bm = shared.load_manifest(alpaca_root,"alpaca"),shared.load_manifest(ibkr_root,"ibkr")
    trades = shared.alpaca_rows(alpaca_root,am,case)
    valid = [r for r in trades if shared.eligible(r,p["rules"])]
    ib,coverage = shared.ib_rows(ibkr_root,bm,case)
    a,b = Counter(signature(r,"alpaca") for r in valid),Counter(signature(r,"ibkr") for r in ib)
    a_bins,b_bins = defaultdict(int),defaultdict(int)
    for r in valid:
        a_bins[clock_bucket(timestamp_ns(r["t"])//10**9,opened,closed)] += r["s"]
    for r in ib:
        b_bins[clock_bucket(r["time"],opened,closed)] += strict_shares(r["size"])
    old = frozen[case["symbol"]+"/"+case["date"]]
    av,bv = sum(r["s"] for r in valid),sum(strict_shares(r["size"]) for r in ib)
    row = dict(**case,records=len(trades),eligible_records=len(valid),alpaca_volume=av,
        retained_sip_daily=old["sip_raw_volume"],published_volume=old["published_raw_volume"],
        trades_minus_sip_daily=av-old["sip_raw_volume"],ibkr_volume=bv,ibkr_minus_alpaca=bv-av,
        crsp_daily_equals_alpaca=largest["crsp_volume"]==av,
        source_update_states=dict(Counter(r.get("u") or "no_update_flag" for r in trades)),
        price_size_condition_multisets_exact=a==b,alpaca_only_occurrences=sum((a-b).values()),
        ibkr_only_occurrences=sum((b-a).values()),alpaca_clock_bins=dict(a_bins),ibkr_clock_bins=dict(b_bins),
        actual_session=calendar,**coverage)
    # Licensed values remain with the protected WRDS archive, outside Git.
    detail_path = Path(ref["details_path"]).parent / "early-close-control.json"
    save(detail_path,dict(crsp=largest,alpaca_volume=av,ibkr_volume=bv,
                         crsp_minus_alpaca=largest["crsp_volume"]-av,
                         alpaca_only=[dict(price=k[0],size=k[1],conditions=k[2],count=n) for k,n in (a-b).items()],
                         ibkr_only=[dict(price=k[0],size=k[1],conditions=k[2],count=n) for k,n in (b-a).items()]))
    result = dict(status="comparison_complete",protocol_sha256=scope.PROTOCOL_HASH,cases=[row],
        sources=[dict(archive=str(root),manifest_sha256=sha((root/"manifest.json").read_bytes()),
                      requests=len(m["requests"]),payloads=sum("path" in r for r in m["requests"]))
                 for root,m in ((alpaca_root,am),(ibkr_root,bm))],
        licensed_detail=dict(path=str(detail_path),sha256=sha(detail_path.read_bytes())),
        limitations=["One diagnosed outlier does not validate all CRSP or SIP histories.",
                     "No same-day availability or historical correction timing inferred.",
                     "No forced source-clock matching or changed acceptance threshold."],
        runner_sha256=sha(Path(__file__).read_bytes()))
    save(scope.STUDY / "assessment.json",result)
    print(json.dumps(row),flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("alpaca",type=Path)
    parser.add_argument("ibkr",type=Path)
    args = parser.parse_args()
    assess(args.alpaca,args.ibkr)
