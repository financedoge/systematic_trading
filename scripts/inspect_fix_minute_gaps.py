"""Re-query three fixed minutes; retain exact records and source-gap evidence."""
from collections import Counter, defaultdict
from datetime import UTC, datetime
import json
from pathlib import Path
import time

import capture_volume_exception_trades as transport
import capture_large_volume_sources as scope
import reconcile_volume_exceptions as shared
from capture_csl_trade_sources import retain, timestamp_ns, TRANSIENT
from probe_alpaca_sip_source import ROOT, CREDENTIALS, load_credentials, save, sha


STUDY = ROOT / "research/p421-fix-minute-gaps-20261107-v1"
PROTOCOL_HASH = "fa0aee0422e1f9b838189b8fcca7363e9321b52bb9c74d08f55918f5f90591cc"


def protocol():
    raw = (STUDY / "protocol.json").read_bytes()
    if sha(raw) != PROTOCOL_HASH:
        raise ValueError("Changed minute-query scope")
    p = json.loads(raw)
    if sha((ROOT/"scripts/capture_volume_exception_trades.py").read_bytes()) != p["source_helper_sha256"]:
        raise ValueError("Changed source transport")
    return p


def params(case):
    return dict(start=case["start"],end=case["end"],feed="sip",asof="-",currency="USD",sort="asc",limit=10000)


def validate_minute(payload, case):
    start,end = timestamp_ns(case["start"]),timestamp_ns(case["end"])
    records,_ = transport.validate_page(payload,case,set(),start)
    if payload.get("next_page_token", "missing") is not None:
        raise ValueError("Minute query is not terminal; requires a separately bounded follow-up")
    if any(not start <= timestamp_ns(r["t"]) <= end for r in records):
        raise ValueError("Trade outside the declared minute")
    return records


def capture():
    p = protocol()
    root = Path("D:/systematic_trading_data/source-archives/alpaca") / (
        "fix-minute-gaps-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
    root.mkdir(parents=True,exist_ok=False)
    files = [Path(__file__),STUDY/"protocol.json",ROOT/"scripts/capture_volume_exception_trades.py",
             ROOT/"scripts/capture_csl_trade_sources.py",ROOT/"scripts/probe_alpaca_sip_source.py"]
    for f in files:
        (root/f.name).write_bytes(f.read_bytes())
    m = dict(status="in_progress",protocol_sha256=PROTOCOL_HASH,
             files={f.name:sha(f.read_bytes()) for f in files},requests=[])
    save(root/"manifest.json",m)
    credentials = load_credentials(CREDENTIALS,ROOT/".env")
    transport.protocol = protocol
    transport.parameters = params
    try:
        for i,case in enumerate(p["cases"]):
            receipt = dict(case=case,parameters=params(case),attempts=[])
            m["requests"].append(receipt)
            for attempt in range(p["retries"]):
                try:
                    code,raw = transport.fetch(case,params(case),credentials)
                    receipt["attempts"].append(dict(http_status=code))
                    break
                except OSError as error:
                    receipt["attempts"].append(dict(curl_code=error.errno))
                    save(root/"manifest.json",m)
                    if error.errno not in TRANSIENT or attempt==p["retries"]-1:
                        raise
                    time.sleep(1)
            receipt.update(http_status=code,captured_at=datetime.now(UTC).isoformat(),
                           **retain(root,f"minute-{i+1}",raw))
            save(root/"manifest.json",m)
            if code != 200:
                raise ValueError("Minute query failed")
            receipt.update(rows=len(validate_minute(json.loads(raw),case)),status="captured")
            save(root/"manifest.json",m)
        m["status"] = "captured_pending_qualification"
    except Exception as error:
        m.update(status="incomplete",error_type=type(error).__name__)
        raise
    finally:
        save(root/"manifest.json",m)
        print(json.dumps(dict(archive=str(root),status=m["status"])),flush=True)
    return root


def source_roots(prior):
    sources = {}
    for source in prior["sources"]:
        root = Path(source["archive"])
        if sha((root / "manifest.json").read_bytes()) != source["manifest_sha256"]:
            raise ValueError("Changed original full-day source manifest")
        provider = root.parent.name
        if provider not in {"alpaca", "ibkr"} or provider in sources:
            raise ValueError("Unexpected or repeated full-day source")
        sources[provider] = root
    if set(sources) != {"alpaca", "ibkr"}:
        raise ValueError("Both full-day sources are required")
    return sources


def compare(root):
    p = protocol()
    m = json.loads((root/"manifest.json").read_text())
    if m["status"] != "captured_pending_qualification" or m["protocol_sha256"] != PROTOCOL_HASH:
        raise ValueError("Incomplete minute capture")
    for name,h in m["files"].items():
        if sha((root/name).read_bytes()) != h:
            raise ValueError("Changed minute-query recipe")
    prior_path = ROOT/p["prior_assessment"]
    if sha(prior_path.read_bytes()) != p["prior_assessment_sha256"]:
        raise ValueError("Changed five-case comparison")
    prior = json.loads(prior_path.read_text())
    scope.configure()
    sources = source_roots(prior)
    am,bm = shared.load_manifest(sources["alpaca"],"alpaca"),shared.load_manifest(sources["ibkr"],"ibkr")
    cached,minute_differences,results = {},{},[]
    rules = p["rules"]
    for case in scope.protocol()["cases"]:
        if case["symbol"] != "FIX":
            continue
        aa = shared.alpaca_rows(sources["alpaca"],am,case)
        bb,_ = shared.ib_rows(sources["ibkr"],bm,case)
        cached[case["date"]] = aa,bb
        bins = defaultdict(lambda:[0,0,0,0])
        for r in aa:
            if shared.eligible(r,rules):
                b = bins[timestamp_ns(r["t"])//10**9//60*60]
                b[0] += r["s"]
                b[2] += 1
        for r in bb:
            b = bins[r["time"]//60*60]
            b[1] += int(r["size"])
            b[3] += 1
        minute_differences[case["date"]] = [dict(utc=datetime.fromtimestamp(k,UTC).isoformat(),
            alpaca_shares=v[0],ibkr_shares=v[1],difference=v[1]-v[0],alpaca_trades=v[2],ibkr_trades=v[3])
            for k,v in sorted(bins.items()) if v[0] != v[1]]
    for receipt,case in zip(m["requests"],p["cases"],strict=True):
        if receipt["case"] != case or receipt["parameters"] != params(case) or receipt["http_status"] != 200:
            raise ValueError("Changed direct-minute request")
        payload = transport.verified_payload(root,receipt)
        fresh = validate_minute(payload,case)
        aa,bb = cached[case["date"]]
        start,end = timestamp_ns(case["start"]),timestamp_ns(case["end"])
        old = [r for r in aa if start <= timestamp_ns(r["t"]) <= end]
        ib = [r for r in bb if start//10**9 <= r["time"] <= end//10**9]
        record = lambda r:json.dumps(r,sort_keys=True,separators=(",",":"))
        av = sum(r["s"] for r in fresh if shared.eligible(r,rules))
        bv = sum(int(r["size"]) for r in ib)
        results.append(dict(**case,full_day_records=len(old),direct_minute_records=len(fresh),
            exact_record_multiset_match=Counter(map(record,old))==Counter(map(record,fresh)),
            alpaca_eligible_volume=av,ibkr_volume=bv,ibkr_minus_alpaca=bv-av))
    result = dict(status="direct_minute_comparison_complete",protocol_sha256=PROTOCOL_HASH,cases=results,
        minute_differences=minute_differences,source_archive=str(root),source_manifest_sha256=sha((root/"manifest.json").read_bytes()),
        source_snapshot_changed=False if all(r["exact_record_multiset_match"] for r in results) else True,
        conclusion="Direct queries test pagination only; they cannot determine which upstream corrections or vendor capture rules caused missing records.",
        runner_sha256=sha(Path(__file__).read_bytes()))
    save(STUDY/"assessment.json",result)
    print(json.dumps(dict(status=result["status"],cases=results)),flush=True)


if __name__ == "__main__":
    import argparse

    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive",type=Path)
    args=parser.parse_args()
    compare(args.archive or capture())
