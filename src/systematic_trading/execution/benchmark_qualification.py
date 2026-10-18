"""Publish retrospective execution references against verified governed raw history.

This limited audit does not admit intraday data to strategy research or certify a tape.
"""
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import gzip
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from systematic_trading.execution.benchmark_archive import validate_ready
from systematic_trading.execution.twap_benchmark import calculate_twap
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.price_governance import POLICY as DAILY_POLICY


POLICY = dict(version=1, purpose="retrospective_execution_diagnostics_only",
    ohlc_relative_tolerance=DAILY_POLICY["raw_basis_price_tolerance"],
    close_definition="Published governed reconstructed raw daily close; not certified auction price",
    twap_definition="Duration-weighted one-minute closes",
    vwap_definition="IB filtered historical TRADES: sum(minute WAP * provider volume) / sum(provider volume)",
    volume_units="Provider-reported quantity units within one contract/session; no shares or dollar-volume claim",
    split_handling="Reject any known subsequent split through either retained source vintage; no inferred rebasing",
    missing="Withhold on missing intervals, daily rows, identity, OHLC, positive-volume WAP or published hashes",
    limitations=["Paper fills are not live fills; references are not counterfactual executions",
        "Retrospective vintages do not establish historical publication availability",
        "Governed raw prices are reconstructed, never tape-certified; IB trade filtering and WAP rounding remain",
        "Corporate actions after the governed source vintage are not independently covered; OHLC agreement is a consistency check",
        "Provider quantity scale is not certified in shares; a common within-session scale cancels in VWAP",
        "No fees, FX, market impact, opportunity cost or unfilled quantity"])


def session_statistics(candidate):
    """Strict full-interval OHLC/WAP validation, including conflicting duplicate fields."""
    start, end = (datetime.fromisoformat(candidate[k]) for k in ("window_start", "window_end"))
    _, count = calculate_twap(candidate["bars"], start, end)
    points = {}
    for bar in candidate["bars"]:
        at = datetime.fromisoformat(bar["at"])
        if not start <= at < end:
            continue
        if at.second or at.microsecond or at + timedelta(minutes=1) > end:
            raise ValueError("Session reference requires whole minute bars")
        values = {key: Decimal(str(bar[key])) for key in ("open", "high", "low", "close", "volume")}
        if any(not value.is_finite() for value in values.values()):
            raise ValueError("Non-finite session observation")
        if not (0 < values["low"] <= min(values["open"], values["close"])
                <= max(values["open"], values["close"]) <= values["high"]) or values["volume"] < 0:
            raise ValueError("Invalid OHLC or negative session volume")
        # A zero-volume interval contributes no value; do not invent a WAP.
        values["wap"] = Decimal(str(bar["wap"])) if values["volume"] else None
        if values["volume"] and (not values["wap"].is_finite()
                or not values["low"] <= values["wap"] <= values["high"]):
            raise ValueError("Missing or out-of-range positive-volume WAP")
        if at in points and points[at] != values:
            raise ValueError("Conflicting session bar fields")
        points[at] = values
    ordered = [points[at] for at in sorted(points)]
    volume = sum(b["volume"] for b in ordered)
    if not volume:
        raise ValueError("No positive session volume")
    return dict(open=ordered[0]["open"], close=ordered[-1]["close"],
        high=max(b["high"] for b in ordered), low=min(b["low"] for b in ordered),
        vwap=sum(b["wap"] * b["volume"] for b in ordered if b["volume"]) / volume,
        provider_volume=volume, bar_count=count)


class PublishedDaily:
    """Bind file history to its published catalog and per-symbol ClickHouse storage batch."""
    def __init__(self, analytics):
        self.analytics = analytics
        publication = analytics.latest("governance/catalog")
        if not publication:
            raise ValueError("No published governed daily catalog")
        self.batch = publication["version"]
        self.inputs = GovernedInputs(Path(json.loads(publication["provenance"])["root"]), self.batch)
        manifest = analytics.document("governance/catalog", "manifest.json")
        if not manifest or manifest[1]["version"] != self.batch or digest(manifest[0]["payload"]) != self.batch:
            raise ValueError("Published governed manifest mismatch")
        self.catalog = {r["symbol"]: r for r in json.loads(self.inputs.checked("catalog.json").read_text(encoding="utf-8"))}
        self.cache = {}

    def get(self, symbol, day):
        if symbol not in self.cache:
            audit = self.inputs.audit(symbol)
            if audit["status"] != "audited_with_limitations" or audit["symbol"] != symbol:
                raise ValueError("Daily identity or audit unavailable")
            rows = self.inputs.rows(symbol, "1950-01-01", "2100-01-01")
            with gzip.open(self.inputs.checked(f"actions/{symbol}.jsonl.gz"), "rt", encoding="utf-8") as stream:
                actions = [json.loads(line) for line in stream]
            self.cache[symbol] = {r["trade_date"]: r for r in rows}, actions
        rows, actions = self.cache[symbol]
        if day not in rows:
            raise ValueError("Missing published governed daily row")
        row = rows[day]
        storage = self.catalog[symbol].get("storage_batch", self.batch)
        publication = self.analytics.latest(f"governance-batch/{storage}/{symbol}")
        if not publication or publication["version"] != storage:
            raise ValueError("Daily storage batch is not published")
        published = self.analytics.governed_rows('governed_daily',storage,symbol,start=day,end=day,limit=2)
        if (len(published) != 1 or digest(published[0]["payload"]) != published[0]["payload_hash"]
                or json.loads(published[0]["payload"]) != row):
            raise ValueError("Daily row publication/hash mismatch")
        return dict(row=row, actions=actions, catalog_batch=self.batch, storage_batch=storage,
                    row_sha256=published[0]["payload_hash"], input_hashes=dict(self.inputs.used))


def qualify(candidate, daily):
    symbol = candidate["symbol"]
    contract = candidate.get("contract") or {}
    if (candidate.get("format_version") != 2 or not contract.get("con_id") or contract.get("symbol") != symbol
            or contract.get("currency") != "USD" or contract.get("security_type") != "STK"
            or not contract.get("primary_exchange")):
        raise ValueError("Unresolved session contract identity")
    day = datetime.fromisoformat(candidate["window_start"]).astimezone(ZoneInfo("America/New_York")).date().isoformat()
    row = daily["row"]
    if row["symbol"] != symbol or row["trade_date"] != day:
        raise ValueError("Daily/session identity mismatch")
    if set(row["quality_flags"]) - {"historical_vintage_uncertified", "joined_source"}:
        raise ValueError("Unresolved governed raw basis")
    if row.get("split_multiplier") != 1:
        raise ValueError("Subsequent split requires separately qualified intraday rebasing")
    vintage = max(row["source_vintage"][:10], candidate["observed_at"][:10])
    if any(a["kind"] == "splits" and day < a["date"] <= vintage for a in daily["actions"]):
        raise ValueError("Subsequent split requires separately qualified intraday rebasing")
    stats = session_statistics(candidate)
    deviations = {}
    for field in ("open", "high", "low", "close"):
        raw = Decimal(str(row["raw_" + field]))
        if not raw.is_finite() or raw <= 0:
            raise ValueError("Unresolved governed raw price")
        deviation = abs(stats[field] / raw - 1)
        deviations[field] = str(deviation * 10000)
        if deviation > Decimal(str(POLICY["ohlc_relative_tolerance"])):
            raise ValueError("Session/governed raw OHLC disagreement: " + field)
    return dict(status="qualified_with_limitations", purpose=POLICY["purpose"], research_approved=False,
        symbol=symbol, currency="USD", session_date=day, session=candidate, daily=daily,
        reference_prices=dict(close=str(row["raw_close"]), session_vwap=str(stats["vwap"])),
        statistics={k: str(v) for k, v in stats.items()}, ohlc_difference_bps=deviations)


def publish_references(settings, analytics, sessions):
    """Audit all ready sessions, publish both admitted references and explicit exclusions."""
    if analytics is None or not analytics.latest("governance/catalog"):
        return dict(status="unavailable", message="No governed catalog publication")
    daily = PublishedDaily(analytics)
    audits = []
    for key, result in sorted(sessions.items()):
        audit = dict(status="unavailable", message=result.get("message", result["status"]), session_key=key)
        if result["status"] == "ready":
            try:
                path = settings.data_dir / "execution_benchmarks" / (key + ".json")
                candidate = json.loads(path.read_text(encoding="utf-8"))
                start, end = (datetime.fromisoformat(candidate[k]) for k in ("window_start", "window_end"))
                validate_ready(candidate, root=settings.data_dir, symbol=candidate["symbol"], start=start, end=end)
                from systematic_trading.live.trading_calendar import us_equity_market_close
                zone = ZoneInfo("America/New_York")
                day = start.astimezone(zone).date()
                close = us_equity_market_close(day)
                expected_start = datetime.combine(day, datetime.min.time().replace(hour=9, minute=30), zone).astimezone(UTC)
                if close is None or start != expected_start or end != datetime.combine(day, close, zone).astimezone(UTC):
                    raise ValueError("Reference is not a complete regular session")
                audit = dict(qualify(candidate, daily.get(candidate["symbol"], str(day))), session_key=key)
            except (OSError, ValueError, KeyError, TypeError, ArithmeticError) as exc:
                audit["message"] = str(exc)
        audits.append(audit)
    policy = dict(POLICY, qualifier_source_sha256=digest(Path(__file__).read_bytes()))
    documents = [dict(point_key=a["session_key"], media_type="application/json", payload=encode(a)) for a in audits]
    documents.append(dict(point_key="policy", media_type="application/json", payload=encode(policy)))
    hashes = {d["point_key"]: digest(d["payload"]) for d in documents}
    version = digest(encode(hashes))
    analytics.publish("execution-reference-audits", version, [], documents,
        provenance=dict(catalog_batch=daily.batch, policy=policy, document_hashes=hashes))
    return dict(status="published", version=version, catalog_batch=daily.batch, session_count=len(audits),
                qualified_count=sum(a["status"] == "qualified_with_limitations" for a in audits),
                exclusions=[dict(session_key=a["session_key"], message=a["message"]) for a in audits if "message" in a])
