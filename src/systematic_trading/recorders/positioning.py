"""Raw-first CFTC positioning recorder with honest first-seen availability."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal, InvalidOperation
from hashlib import sha256 as sha256_bytes
import json
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.runtime_io import atomic_json, exclusive_lock

SOURCE = "governance/cftc-positioning"
FAMILY = "cftc_disaggregated_futures_only"
PAGE_SIZE = 50000
MIN_REFRESH_SECONDS = 6 * 60 * 60


def _file_hash(path: Path) -> str:
    return sha256_bytes(path.read_bytes()).hexdigest()


def load_config(settings):
    path = settings.positioning_recorder_config_path
    config = json.loads(path.read_text(encoding="utf-8"))
    markets = config.get("markets", [])
    codes = [m.get("code") for m in markets]
    if not config.get("enabled") or not markets or len(codes) != len(set(codes)):
        raise ValueError("Invalid CFTC positioning registry")
    if any(not isinstance(code, str) or not code.isdigit() or len(code) != 6 for code in codes):
        raise ValueError("CFTC market codes must be six-digit strings")
    return config


def fetch_cftc(config):
    """Fetch the bounded configured contract set from the official public API."""
    codes = ",".join("'" + market["code"] + "'" for market in config["markets"])
    where = ("cftc_contract_market_code in (" + codes + ") AND "+
             "report_date_as_yyyy_mm_dd >= '" + config["history_start"] + "T00:00:00.000'")
    rows, offset = [], 0
    while True:
        query = urlencode({"$where": where, "$order": "report_date_as_yyyy_mm_dd, cftc_contract_market_code",
                           "$limit": PAGE_SIZE, "$offset": offset})
        request = Request(config["source_url"] + "?" + query,
                          headers={"User-Agent": "systematic-trading-research/0.1", "Accept": "application/json"})
        with urlopen(request, timeout=45) as response:
            page = json.loads(response.read().decode("utf-8"))
        if not isinstance(page, list):
            raise ValueError("CFTC API returned an unexpected response")
        rows.extend(page)
        if len(page) < PAGE_SIZE:
            break
        offset += len(page)
    return rows


def _integer(row, name):
    value = row.get(name)
    if value in (None, ""):
        return None
    try:
        return int(Decimal(str(value)))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("CFTC position field is not an integer: " + name) from exc


def _ratio(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None
    return str(Decimal(numerator) / Decimal(denominator))


def normalize(row, market, first_seen_at):
    report_date = str(row.get("report_date_as_yyyy_mm_dd", ""))[:10]
    code = str(row.get("cftc_contract_market_code", ""))
    if code != market["code"] or len(report_date) != 10:
        raise ValueError("CFTC row identity or report date is invalid")
    oi = _integer(row, "open_interest_all")
    mm_long, mm_short = _integer(row, "m_money_positions_long_all"), _integer(row, "m_money_positions_short_all")
    pm_long, pm_short = _integer(row, "prod_merc_positions_long"), _integer(row, "prod_merc_positions_short")
    sd_long, sd_short = _integer(row, "swap_positions_long_all"), _integer(row, "swap__positions_short_all")
    return {
        "market_code": code,
        "market": market["name"],
        "group": market["group"],
        "related_etfs": market.get("related_etfs", []),
        "report_date": report_date,
        "first_seen_at": first_seen_at,
        "availability_basis": "first_app_capture; historical source dissemination timestamp not present in row",
        "open_interest": oi,
        "managed_money_long": mm_long,
        "managed_money_short": mm_short,
        "managed_money_net_pct_oi": _ratio(None if mm_long is None or mm_short is None else mm_long-mm_short, oi),
        "producer_merchant_net_pct_oi": _ratio(None if pm_long is None or pm_short is None else pm_long-pm_short, oi),
        "swap_dealer_net_pct_oi": _ratio(None if sd_long is None or sd_short is None else sd_long-sd_short, oi),
        "change_in_managed_money_long": _integer(row, "change_in_m_money_long_all"),
        "change_in_managed_money_short": _integer(row, "change_in_m_money_short_all"),
        "contract_name": row.get("contract_market_name"),
        "contract_units": row.get("contract_units"),
        "source_row": row,
    }


def refresh_positioning(settings, analytics, *, now=None, fetch=fetch_cftc):
    if not settings.governed_refresh_enabled:
        return False
    config = load_config(settings)
    now = (now or datetime.now(UTC)).astimezone(UTC)
    stamp = now.isoformat()
    config_path = settings.positioning_recorder_config_path
    root = settings.data_dir / "governance" / "cftc-positioning"
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "first-seen.json"
    with exclusive_lock(root / "recorder.lock"):
        markets = {m["code"]: m for m in config["markets"]}
        state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
        checked_at = state.get("last_checked_at")
        if checked_at:
            elapsed = (now - datetime.fromisoformat(checked_at)).total_seconds()
            if 0 <= elapsed < MIN_REFRESH_SECONDS:
                return False
        prior_rows = {}
        prior_version = state.get("capture_version")
        if prior_version:
            previous_root = root / "captures" / prior_version
            previous_receipt = json.loads((previous_root / "receipt.json").read_text(encoding="utf-8"))
            previous_data = (previous_root / "normalized.json").read_bytes()
            if digest(encode(json.loads(previous_data.decode("utf-8")))) != previous_receipt["normalized_sha256"]:
                raise ValueError("Prior CFTC normalized capture failed hash verification")
            prior_rows = {r["market_code"]+"/"+r["report_date"]: r
                          for r in json.loads(previous_data.decode("utf-8"))}
        fetch_config = dict(config)
        if prior_rows:
            latest = max(r["report_date"] for r in prior_rows.values())
            refresh_start = (datetime.fromisoformat(latest).date() - timedelta(days=365)).isoformat()
            fetch_config["history_start"] = max(config["history_start"], refresh_start)
        recent_rows = fetch(fetch_config)
        merged_source = {key: value["source_row"] for key, value in prior_rows.items()}
        for row in recent_rows:
            code = str(row.get("cftc_contract_market_code", ""))
            market = markets.get(code)
            if market is None:
                continue
            key = code + "/" + str(row.get("report_date_as_yyyy_mm_dd", ""))[:10]
            row_hash = digest(encode(row))
            prior = state.get(key)
            first_seen = prior["first_seen_at"] if prior and prior["row_hash"] == row_hash else stamp
            state[key] = {"row_hash": row_hash, "first_seen_at": first_seen}
            merged_source[key] = row
        rows = []
        for key, row in merged_source.items():
            code, report_date = key.split("/", 1)
            market = markets.get(code)
            if market is None:
                continue
            row_hash = digest(encode(row))
            prior = state.get(key)
            first_seen = prior["first_seen_at"] if prior and prior["row_hash"] == row_hash else stamp
            state[key] = {"row_hash": row_hash, "first_seen_at": first_seen}
            rows.append(normalize(row, market, first_seen))
        rows.sort(key=lambda r: (r["report_date"], r["market_code"]))
        expected = {m["code"] for m in config["markets"]}
        observed = {r["market_code"] for r in rows}
        if not rows or observed != expected:
            raise ValueError("CFTC capture incomplete for configured markets: " + ",".join(sorted(expected-observed)))
        raw_text = encode(recent_rows)
        normalized_text = encode(rows)
        config_hash = _file_hash(config_path)
        version = digest(encode({"config_sha256": config_hash, "normalized_sha256": digest(normalized_text)}))
        capture = root / "captures" / version
        if not capture.exists():
            capture.mkdir(parents=True, exist_ok=False)
            atomic_json(capture / "source.json", recent_rows)
            atomic_json(capture / "normalized.json", rows)
            receipt = {"version": version, "captured_at": stamp, "config_sha256": config_hash,
                       "source_sha256": digest(raw_text), "normalized_sha256": digest(normalized_text),
                       "rows": len(rows), "markets": sorted(observed), "source": config["source_url"],
                       "availability": config["historical_availability"], "limitations": config["limitations"]}
            atomic_json(capture / "receipt.json", receipt)
        else:
            receipt = json.loads((capture / "receipt.json").read_text(encoding="utf-8"))
            if receipt.get("normalized_sha256") != digest(normalized_text):
                raise ValueError("Existing CFTC capture does not match its version")
        observations = [dict(point_key=r["market_code"]+"/"+r["report_date"], family=FAMILY,
                             entity=r["market_code"], observed_at=r["report_date"],
                             available_at=r["first_seen_at"], payload=encode(r)) for r in rows]
        documents = [dict(point_key="source.json", media_type="application/json", payload=raw_text),
                     dict(point_key="receipt.json", media_type="application/json", payload=encode(receipt))]
        changed = analytics.publish(SOURCE, version, observations, documents,
                                    provenance={"recorder": "application", "policy": config["version"],
                                                "config_sha256": config_hash, "capture_root": str(capture.resolve())})
        state["last_checked_at"] = stamp
        state["capture_version"] = version
        atomic_json(state_path, state)
        return changed


def catalog(analytics, settings):
    config = load_config(settings)
    publication = analytics.latest(SOURCE)
    if publication is None:
        return {"config": config, "version": None, "rows": 0, "markets": [], "through": None}
    rows = analytics.observations(SOURCE, family=FAMILY, limit=50000)
    data = [json.loads(r["payload"]) for r in rows]
    return {"config": config, "version": publication["version"], "rows": len(data),
            "markets": [{"code": m["code"], "name": m["name"], "group": m["group"],
                         "rows": sum(1 for r in data if r["market_code"] == m["code"]),
                         "through": max((r["report_date"] for r in data if r["market_code"] == m["code"]), default=None)}
                        for m in config["markets"]],
            "through": max((r["report_date"] for r in data), default=None),
            "limitations": config["limitations"]}


def history(analytics, market_code, start="2000-01-01", end="2999-12-31"):
    rows = analytics.observations(SOURCE, family=FAMILY, limit=50000)
    data = [json.loads(r["payload"]) for r in rows]
    selected = [r for r in data if r["market_code"] == market_code and start <= r["report_date"] <= end]
    return sorted(selected, key=lambda r: r["report_date"])
