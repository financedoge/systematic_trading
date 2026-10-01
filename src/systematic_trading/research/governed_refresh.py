"""Application-owned acquisition -> audit -> verified publication for tracked ETFs.

Provider bytes are evidence only. No consumer sees a new catalog until every
symbol, action ledger, file hash and ClickHouse row has been verified.
"""
from datetime import UTC, datetime
import gzip
import json
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4

import numpy as np

from systematic_trading.lean.contracts import sha256
from systematic_trading.live.trading_calendar import previous_us_trading_day
from systematic_trading.daily_quality import completed_session
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.market_data.governance_store import GovernanceStore
from systematic_trading.portfolio.context import NY
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.research.analytics_projection import observation
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.price_governance import POLICY, governed_sessions, yahoo_source, consolidate, names_agree


def acquire(symbol, now):
    from systematic_trading.data.yahoo import fetch_chart_bytes
    query = urlencode(dict(period1=-631152000, period2=int(now.timestamp()), interval="1d", events="div,splits,capitalGains"))
    return fetch_chart_bytes(symbol, query)


def _write(root, name, value):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(encode(value), encoding="utf8")


def _rows(root, name, rows):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", encoding="utf8") as stream:
        for row in rows:
            stream.write(encode(row) + "\n")


def validate_revision(symbol, previous, rows, old_audit, audit, cutoff):
    if not rows or rows[-1]["trade_date"] != cutoff or audit["internal_gaps"]:
        raise ValueError(f"Incomplete governed refresh: {symbol}")
    if audit["status"] != "audited_with_limitations" or not names_agree(old_audit["name"], audit["name"]):
        raise ValueError(f"Identity or adjustment audit requires review: {symbol}")
    before = {r["trade_date"]: r["adjusted_close"] for r in previous}
    after = {r["trade_date"]: r["adjusted_close"] for r in rows}
    if not before.keys() <= after.keys():
        raise ValueError(f"Refresh would truncate supported history: {symbol}")
    days = sorted(before)
    if len(days) < POLICY["min_overlap"]:
        raise ValueError(f"Insufficient governed overlap: {symbol}")
    # Uniform rebasing from a newly reported dividend is allowed; changed return
    # paths are quarantined, never silently substituted in a new publication.
    a, b = np.array([before[d] for d in days]), np.array([after[d] for d in days])
    errors = np.abs(a[1:] / a[:-1] - b[1:] / b[:-1])
    if np.max(errors) > POLICY["p99_return_error"]:
        raise ValueError(f"Historical return revision needs review: {symbol}")


def refresh_governed_etfs(settings, analytics, *, now=None, fetch=acquire):
    now = now or datetime.now(UTC)
    day = now.astimezone(NY).date()
    if not completed_session(day, now=now):
        day = previous_us_trading_day(day)
    cutoff = str(day)
    publication = analytics.latest("governance/catalog")
    if not publication:
        raise ValueError("Governed refresh needs an initial audited catalog")
    root = Path(json.loads(publication["provenance"])["root"])
    prior = GovernedInputs(root, publication["version"])
    symbols = sorted({*instruments_for_definition(current_sota_definition()), "URTH"})
    old_rows = {s: prior.rows(s, "1950-01-01", cutoff) for s in symbols}
    if all(rows and rows[-1]["trade_date"] == cutoff for rows in old_rows.values()):
        return False
    # Failed acquisitions are retained; retry within five minutes after reconnect.
    state = settings.data_dir / "governance/refresh-state.json"
    if state.exists():
        last = json.loads(state.read_text(encoding="utf8"))
        if last.get("cutoff") == cutoff and (now - datetime.fromisoformat(last["attempted_at"])).total_seconds() < 300:
            if last.get("error"):
                raise ValueError(last["error"])
            return False
    receipt = dict(cutoff=cutoff, attempted_at=now.isoformat(), parent=publication["version"])
    _write(state.parent, state.name, receipt)
    output = settings.data_dir.resolve() / "governance" / (cutoff + "-" + uuid4().hex[:12])
    try:
        return _build_publish(analytics, prior, publication, output, symbols, old_rows, cutoff, now, fetch)
    except Exception as exc:
        _write(state.parent, state.name, dict(receipt, error=str(exc), quarantined_root=str(output)))
        raise


def _build_publish(analytics, prior, publication, output, symbols, old_rows, cutoff, now, fetch):
    sessions, calendar = governed_sessions("1950-01-01", cutoff)
    catalog = json.loads(prior.checked("catalog.json").read_text(encoding="utf8"))
    inherited = [dict(item, storage_batch=item.get("storage_batch", publication["version"]))
                 for item in catalog if item["symbol"] not in symbols]
    # The same complete ETF set is replaced each run; untouched histories remain
    # pinned to the original parent instead of accumulating an unbounded chain.
    parent = prior.parent or prior
    _write(output, "parent.json", dict(root=str(parent.root), batch=sha256(parent.root / "manifest.json")))
    _write(output, "policy.json", POLICY)
    _write(output, "calendar.json", dict(**calendar, sessions=sorted(sessions)))
    prepared, index = {}, []
    for symbol in symbols:
        raw = fetch(symbol, now)
        raw_path = output / "sources" / (symbol + ".json")
        raw_path.parent.mkdir(parents=True, exist_ok=True)
        raw_path.write_bytes(raw)
        source_id = f"governance-source/{output.name}/bars/{symbol}"
        source = yahoo_source(json.loads(raw), key=source_id, symbol=symbol, raw_hash=digest(raw),
                              vintage=now.isoformat(), priority=100, action_start="1950-01-01")
        if source.metadata.get("symbol") != symbol or source.metadata.get("currency") != "USD" or source.metadata.get("instrumentType") != "ETF":
            raise ValueError("Provider ETF identity changed: " + symbol)
        source.metadata["identity_eligible"] = True
        bars, audit, actions = consolidate(symbol, [source], sessions, cutoff)
        validate_revision(symbol, old_rows[symbol], bars, prior.audit(symbol), audit, cutoff)
        audit["requested_cutoff"] = cutoff
        accepted_days = {b["trade_date"] for b in bars}
        comparisons = [dict(symbol=symbol, trade_date=d, source_id=source_id, source_hash=source.raw_hash,
            source_close=r["close"], source_adjusted_close=r["adjusted_close"], source_volume=r["volume"],
            rebased_adjusted_close=r["adjusted_close"], accepted=d in accepted_days, price_basis=source.basis)
            for d,r in source.rows.items() if d <= cutoff]
        for kind, values in (("bars", bars), ("comparisons", comparisons), ("actions", actions)):
            _rows(output, f"{kind}/{symbol}.jsonl.gz", values)
        _write(output, f"audits/{symbol}.json", audit)
        compact = {k:v for k,v in audit.items() if k not in ("sources", "overlaps", "gaps", "seams")}
        compact.update(source_count=1, rejected_sources=0)
        inherited.append(compact)
        index.append(dict(symbol=symbol, path=str(raw_path), source_id=source_id, raw_sha256=source.raw_hash))
        prepared[symbol] = bars, comparisons, actions, audit, raw.decode("utf8"), source_id
    _write(output, "source_index.json", index)
    _write(output, "catalog.json", sorted(inherited, key=lambda r:r["symbol"]))
    _write(output, "producer.json", dict(parent=publication["version"], published_policy=POLICY, cutoff=cutoff,
        source_hash=sha256(Path(__file__)), audit_code_hash=sha256(Path(__file__).with_name("price_governance.py"))))
    manifest = {p.relative_to(output).as_posix():sha256(p) for p in output.rglob("*") if p.is_file()}
    _write(output, "manifest.json", manifest)
    batch = sha256(output / "manifest.json")
    governance = GovernanceStore(analytics)
    governance.initialize()
    for symbol, (bars, comparisons, actions, audit, raw, source_id) in prepared.items():
        governance.insert_verified("governed_daily", batch, symbol, bars)
        governance.insert_verified("governance_comparisons", batch, symbol, comparisons)
        docs = [dict(point_key="audit", media_type="application/json", payload=encode(audit)),
                dict(point_key=source_id, media_type="application/json", payload=raw)]
        analytics.publish(f"governance-batch/{batch}/{symbol}", batch,
            [observation(str(i), "governed_corporate_action", symbol, row, row["date"]) for i,row in enumerate(actions)], docs,
            provenance=dict(symbol=symbol, manifest_sha256=batch, rows=len(bars), owner="application"))
    if analytics.latest("governance/catalog")["version"] != publication["version"]:
        raise ValueError("Catalog changed during refresh; retaining newer committed publication")
    docs = [dict(point_key=name, media_type="application/json", payload=(output/name).read_text(encoding="utf8"))
            for name in ("manifest.json", "parent.json", "policy.json", "producer.json")]
    analytics.publish("governance/catalog", batch,
        [observation(r["symbol"], "governed_series_catalog", r["symbol"], r) for r in inherited], docs,
        provenance=dict(root=str(output), parent=publication["version"], cutoff=cutoff, owner="application", policy=POLICY))
    return True
