"""Frozen ten-stock SIP capture, field audit and isolated evidence publication."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import gzip
import json
from pathlib import Path
import time

from probe_alpaca_sip_source import fetch, inspect_page, load_credentials, CREDENTIALS, sha, save
from compare_alpaca_sip_source import read_capture
from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.sip_volume_pilot import activity_day, audit_bars, audit_pair, eligible_at


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research/p421-sip-volume-pilot-20261107-v1"
PROTOCOL_HASH = "97fb0548e0d656275c9e1aaf329ef671f6942747be9136f61e26ef959f5d6635"
ARCHIVES = Path("D:/systematic_trading_data/source-archives/alpaca")
OUTPUT = ROOT / "var/governance/pilots/p421-sip-volume-20261107-v1"


def read(path):
    return json.loads(path.read_text(encoding="utf8"))


def checked(path, expected):
    raw = path.read_bytes()
    if sha(raw) != expected:
        raise ValueError("Changed pinned artifact: " + path.name)
    return raw


def protocol():
    p = json.loads(checked(STUDY / "protocol.json", PROTOCOL_HASH))
    for path, expected in p["input_pins"].items():
        checked(Path(path), expected)
    return p


def parameters(p, token=None):
    first, last = p["new_capture_window"]
    result = dict(symbols=",".join(p["symbols"]), timeframe="1Day",
                  start=first + "T00:00:00-05:00", end=last + "T23:59:59-05:00",
                  feed="sip", adjustment="raw", asof="-", currency="USD", sort="asc", limit=10000)
    if token is not None:
        result["page_token"] = token
    return result


def new_payload(root, receipt):
    if Path(receipt["path"]).name != receipt["path"]:
        raise ValueError("Invalid archive payload path")
    raw = gzip.decompress(checked(root / receipt["path"], receipt["sha256"]))
    if sha(raw) != receipt["response_sha256"]:
        raise ValueError("Changed decompressed response")
    return json.loads(raw)


def replay_new(root, p, *, complete=True):
    m = read(root / "manifest.json")
    if m["protocol_sha256"] != PROTOCOL_HASH:
        raise ValueError("Capture used a different protocol")
    for name, expected in m["runners"].items():
        checked(root / name, expected)
    checked(root / "protocol.json", PROTOCOL_HASH)
    dates = [d for d in p["sessions"] if p["new_capture_window"][0] <= d <= p["new_capture_window"][1]]
    token, seen, tokens, bars, lineage, ended = None, set(), set(), [], {}, False
    for r in m["requests"]:
        if r["parameters"] != parameters(p, token) or ended:
            raise ValueError("Source query/page-token chain changed")
        payload = new_payload(root, r) if r.get("path") else None
        if r["status"] != "ok":
            continue
        if r["http_status"] != 200 or payload is None:
            raise ValueError("Successful receipt lacks a successful response")
        page = inspect_page(payload, r["parameters"], dates, seen)
        if len(page) != r["row_count"]:
            raise ValueError("Capture row count changed")
        for b in page:
            lineage[b["symbol"], activity_day(b)] = dict(archive=str(root), payload=r["path"],
                response_sha256=r["response_sha256"], captured_at=r["captured_at"], reused=False)
        bars.extend(page)
        token = payload.get("next_page_token")
        if token is not None and (not isinstance(token, str) or not token or token in tokens):
            raise ValueError("Invalid or repeated pagination token")
        tokens.add(token)
        ended = token is None
    if complete and (not ended or m["status"] != "captured_pending_audit"):
        raise ValueError("Incomplete capture")
    return m, bars, lineage, token, ended


def capture(resume=None):
    p = protocol()
    root = resume or ARCHIVES / ("sip-pilot-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
    if resume:
        m, _, _, token, ended = replay_new(root, p, complete=False)
        if ended:
            print(json.dumps(dict(archive=str(root), status=m["status"])))
            return
        for name, expected in m["runners"].items():
            checked(ROOT / "scripts" / name, expected)
    else:
        root.mkdir(parents=True, exist_ok=False)
        names = [Path(__file__).name, "probe_alpaca_sip_source.py"]
        for name in names:
            (root / name).write_bytes((ROOT / "scripts" / name).read_bytes())
        (root / "protocol.json").write_bytes((STUDY / "protocol.json").read_bytes())
        m = dict(created_at=datetime.now(UTC).isoformat(), status="in_progress", protocol_sha256=PROTOCOL_HASH,
                 runners={n:sha((root / n).read_bytes()) for n in names}, requests=[],
                 endpoint=p["acquisition"]["endpoint"], transport="verified_https_ipv4_local_proxy_stdin_auth")
        token = None
        save(root / "manifest.json", m)
    credentials = load_credentials(CREDENTIALS, ROOT / ".env")
    dates = [d for d in p["sessions"] if d <= p["new_capture_window"][1]]
    completed_pages = sum(r["status"] == "ok" for r in m["requests"])
    for _ in range(completed_pages, p["acquisition"]["max_pages"]):
        params = parameters(p, token)
        for attempt in range(p["acquisition"]["max_transport_attempts"]):
            receipt = dict(parameters=params, started_at=datetime.now(UTC).isoformat(), status="pending")
            m["requests"].append(receipt)
            try:
                status, raw = fetch(params, credentials, local_proxy=True)
                name = f"daily-{len(m['requests']):02d}.json.gz"
                blob = gzip.compress(raw, mtime=0)
                (root / name).write_bytes(blob)
                receipt.update(path=name, sha256=sha(blob), response_sha256=sha(raw), http_status=status,
                               captured_at=datetime.now(UTC).isoformat())
                if status != 200:
                    raise ValueError(f"HTTP {status}; retained response, no subscription change")
                payload = json.loads(raw)
                page = inspect_page(payload, params, dates, set())
                receipt.update(status="ok", row_count=len(page))
                token = payload.get("next_page_token")
                m["status"] = "captured_pending_audit" if token is None else "in_progress"
                save(root / "manifest.json", m)
                replay_new(root, p, complete=token is None)
                break
            except OSError as exc:
                receipt.update(status="transport_failed", error_type=type(exc).__name__)
                save(root / "manifest.json", m)
                if attempt == p["acquisition"]["max_transport_attempts"] - 1:
                    raise
                time.sleep(attempt + 1)
            except (ValueError, KeyError, TypeError):
                receipt["status"] = "rejected"
                save(root / "manifest.json", m)
                raise
        if token is None:
            print(json.dumps(dict(archive=str(root), status=m["status"], requests=len(m["requests"]))))
            return
    raise ValueError("Bounded daily pagination did not complete")


def prior_artifact(folder, name):
    parent = ROOT / "research" / folder
    return json.loads(checked(parent / name, read(parent / "artifact-manifest.json")[name]))


def audit(root):
    p = protocol()
    m, new, lineage, _, _ = replay_new(root, p)
    sample_root = Path(p["reused_archive"])
    old_manifest, old = read_capture(sample_root)
    audit_bars(new, p["symbols"], [d for d in p["sessions"] if d <= p["new_capture_window"][1]])
    audit_bars(old["1Day"], p["symbols"], p["reused_dates"])
    for r in old_manifest["requests"]:
        if r["parameters"]["timeframe"] != "1Day":
            continue
        if r["parameters"] != dict(parameters(p), start="2025-02-24T00:00:00-05:00", end="2025-02-28T23:59:59-05:00"):
            raise ValueError("Reused daily scope differs")
        payload = json.loads(gzip.decompress(checked(sample_root / r["path"], r["sha256"])))
        for symbol, bars in payload["bars"].items():
            for b in bars:
                lineage[symbol, activity_day(b)] = dict(archive=str(sample_root), payload=r["path"],
                    response_sha256=r["response_sha256"], captured_at=r["captured_at"], reused=True)
    all_bars = sorted(new + old["1Day"], key=lambda b:(b["symbol"], b["t"]))
    indexed = audit_bars(all_bars, p["symbols"], p["sessions"])
    g = GovernedInputs(Path(p["price"]["root"]), p["price"]["batch"])
    contracts = prior_artifact("p421-ten-qualification-20261106-v1", "ib-contracts.json")["funds"]
    identities = {x["symbol"]:x for x in p["identities"]}
    rows, per_symbol, audits, actions = [], {}, {}, {}
    for symbol in p["symbols"]:
        contract = contracts[symbol]["details"]["contract"]
        if (contract["conId"], contract["symbol"], contract["currency"], contract["secType"]) != (
                identities[symbol]["broker_conid"], symbol, "USD", "STK"):
            raise ValueError("Frozen broker identity changed")
        security_ids = contracts[symbol]["details"].get("secIdList", [])
        if {r["value"] for r in security_ids if r["tag"] == "ISIN"} != {identities[symbol]["isin"]}:
            raise ValueError("Frozen broker ISIN differs")
        ib = {r["date"]:r for r in prior_artifact("p421-ibkr-reconcile-20261106-v1", f"differences/{symbol}.json")}
        pub = g.rows(symbol, *p["window"])
        if {r["trade_date"] for r in pub} != set(p["sessions"]) or set(ib) != set(p["sessions"]):
            raise ValueError("Incomplete comparison window")
        audits[symbol] = g.audit(symbol)
        with gzip.open(g.checked(f"actions/{symbol}.jsonl.gz"), "rt", encoding="utf8") as handle:
            actions[symbol] = [r for line in handle if p["window"][0] <= (r := json.loads(line))["date"] <= p["window"][1]]
        selected = [audit_pair(indexed[symbol, r["trade_date"]], r, ib[r["trade_date"]],
                     lineage[symbol, r["trade_date"]], identities[symbol], audits[symbol],
                     close_diagnostic=p["audit"]["close_diagnostic_usd"]) for r in pub]
        rows.extend(selected)
        per_symbol[symbol] = summary(selected)
        per_symbol[symbol].update(prior_status=audits[symbol]["status"], action_count=len(actions[symbol]),
                                 action_kinds=sorted({r["kind"] for r in actions[symbol]}))
    result = dict(protocol_sha256=PROTOCOL_HASH, status="field_audit_complete_with_unresolved_reviews",
                  new_archive=str(root), new_manifest_sha256=sha((root / "manifest.json").read_bytes()),
                  new_rows=len(new), reused_rows=len(old["1Day"]), total=summary(rows), by_symbol=per_symbol,
                  published_inputs=g.used, historical_strategy_eligible_rows=0,
                  close_exceptions=[{k:r[k] for k in ("symbol", "activity_date", "source_daily_close",
                    "paired_published_raw_close", "ibkr_rth_close", "close_delta_usd", "close_delta_vs_ibkr_usd")}
                    for r in rows if "close_difference_requires_review" in r["flags"]],
                  largest_volume_residuals=[{k:r[k] for k in ("symbol", "activity_date", "sip_raw_volume",
                    "published_raw_volume", "volume_delta_shares", "volume_delta_percent")}
                    for r in sorted(rows, key=lambda r:abs(r["volume_delta_percent"]), reverse=True)[:10]],
                  limitations=["Historical dated identity and availability remain uncertified for every row.",
                    "Prior series/action reviews retained; this pilot does not certify completeness of action ledgers.",
                    "Full-year daily bars have not been independently reconstructed trade by trade.",
                    "Existing close half-cent diagnostic is not a qualification or promotion tolerance.",
                    "No current history, registered input, strategy consumer or execution contract changes."])
    if OUTPUT.exists():
        raise FileExistsError("Immutable audit output already exists")
    OUTPUT.mkdir(parents=True)
    payload = "".join(encode(r) + "\n" for r in rows).encode()
    (OUTPUT / "rows.jsonl.gz").write_bytes(gzip.compress(payload, mtime=0))
    for name, value in (("assessment.json", result), ("prior-audits.json", audits), ("actions.json", actions)):
        save(OUTPUT / name, value)
    (OUTPUT / "protocol.json").write_bytes((STUDY / "protocol.json").read_bytes())
    for source in (Path(__file__), ROOT / "src/systematic_trading/research/sip_volume_pilot.py"):
        (OUTPUT / source.name).write_bytes(source.read_bytes())
    save(OUTPUT / "manifest.json", {f.name:sha(f.read_bytes()) for f in OUTPUT.iterdir() if f.is_file()})
    save(STUDY / "assessment.json", result)
    print(json.dumps(dict(root=str(OUTPUT), batch=sha((OUTPUT / "manifest.json").read_bytes()), **result["total"])))


def summary(rows):
    import statistics

    relative = [abs(r["volume_delta_percent"]) for r in rows]
    return dict(rows=len(rows), exact_volume_matches=sum(r["volume_delta_shares"] == 0 for r in rows),
                max_abs_volume_delta_shares=max(abs(r["volume_delta_shares"]) for r in rows),
                median_abs_volume_delta_percent=statistics.median(relative), max_abs_volume_delta_percent=max(relative),
                close_within_half_cent=sum(abs(r["close_delta_usd"]) <= 0.005 for r in rows),
                close_vs_ibkr_within_half_cent=sum(abs(r["close_delta_vs_ibkr_usd"]) <= 0.005 for r in rows),
                max_abs_close_delta_usd=max(abs(r["close_delta_usd"]) for r in rows),
                nonunit_split_rows=sum(r["published_split_multiplier"] != 1 for r in rows),
                zero_activity_rows=sum("zero_activity_requires_review" in r["flags"] for r in rows))


def publish():
    p = protocol()
    manifest = read(OUTPUT / "manifest.json")
    for name, expected in manifest.items():
        checked(OUTPUT / name, expected)
    result = read(OUTPUT / "assessment.json")
    root = Path(result["new_archive"])
    checked(root / "manifest.json", result["new_manifest_sha256"])
    replay_new(root, p)
    read_capture(Path(p["reused_archive"]))
    g = GovernedInputs(Path(p["price"]["root"]), p["price"]["batch"])
    for symbol in p["symbols"]:
        g.rows(symbol, *p["window"])
        g.audit(symbol)
        g.checked(f"actions/{symbol}.jsonl.gz")
    if g.used != result["published_inputs"]:
        raise ValueError("Published comparison lineage differs")
    with gzip.open(OUTPUT / "rows.jsonl.gz", "rt", encoding="utf8") as handle:
        rows = [json.loads(line) for line in handle]
    if len(rows) != p["audit"]["required_stock_days"] or summary(rows) != result["total"]:
        raise ValueError("Frozen row coverage or assessment changed")
    now = datetime.now(UTC).isoformat()
    if any(eligible_at(r, "2025-02-28T16:00:00-05:00", now) for r in rows):
        raise ValueError("Retrospective capture became historically eligible")
    source, family = p["publication"]["source_id"], p["publication"]["family"]
    if source != "governance/pilots/p421-sip-volume-v1" or family != "sip_volume_pilot_audit":
        raise ValueError("Refuse main catalog or strategy publication")
    batch = sha((OUTPUT / "manifest.json").read_bytes())
    observations = [dict(point_key=r["symbol"] + "/" + r["activity_date"], family=family,
                        entity=r["symbol"], observed_at=r["session_start"],
                        available_at=None, payload=encode(r)) for r in rows]
    documents = [dict(point_key=name, media_type="application/json", payload=(OUTPUT / name).read_text(encoding="utf8"))
                 for name in ("manifest.json", "protocol.json", "assessment.json", "prior-audits.json", "actions.json")]
    settings = AppSettings()
    if settings.market_data_store_backend != "parquet":
        raise ValueError("Pilot requires the native analytical runtime")
    store = AnalyticsStore.from_settings(settings)
    before = store.latest("governance/catalog")
    store.publish(source, batch, observations, documents,
                  provenance=dict(root=str(OUTPUT), protocol_sha256=PROTOCOL_HASH, research_only=True,
                      pilot_audit_only=True, historical_strategy_eligible=False, volume_basis="raw_sip_full_day",
                      price_batch=p["price"]["batch"], registry_migrations=[], publication_scope=p["publication"]["scope"]))
    actual = store.pinned_rows("observations", source, batch)
    docs = store.pinned_rows("documents", source, batch)
    if {r["point_key"]:digest(r["payload"]) for r in actual} != {r["point_key"]:digest(r["payload"]) for r in observations}:
        raise ValueError("Pilot observation readback differs")
    if any(r["available_at"] is not None for r in actual):
        raise ValueError("Publication invented historical availability")
    if {r["point_key"]:digest(r["payload"]) for r in docs} != {r["point_key"]:digest(r["payload"]) for r in documents}:
        raise ValueError("Pilot document readback differs")
    after = store.latest("governance/catalog")
    receipt = dict(source_id=source, batch=batch, root=str(OUTPUT), rows=len(actual), documents=len(docs),
                   published_at=store.publication(source, batch)["published_at"], storage=store.storage_name,
                   verification="Every payload and document SHA256 read back from pinned native publication; historical available_at remains null.",
                   main_catalog_before=before["version"], main_catalog_after=after["version"],
                   main_catalog_written=False, strategy_eligible_rows=0)
    save(STUDY / "publication.json", receipt)
    print(json.dumps(receipt))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("capture", "audit", "publish"))
    parser.add_argument("--source", type=Path)
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    if args.stage == "capture":
        capture(args.resume)
    elif args.stage == "audit":
        if args.source is None:
            parser.error("audit requires --source")
        audit(args.source)
    else:
        publish()
