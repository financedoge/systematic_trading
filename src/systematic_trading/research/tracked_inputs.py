"""App-owned, versioned inputs for monitored strategies; no provider fallback."""
from datetime import UTC, date, datetime, time
from decimal import Decimal
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from systematic_trading.daily_quality import valid_ohlc, completed_session
from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.contracts import sha256
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar
from systematic_trading.research import current_sota_definition, instruments_for_definition


def validated_fx_observations(paths):
    """Audit direct USD/CNH midpoint observations against their stored raw leg."""
    selected, files = {}, {}
    for path in sorted(paths):
        payload = json.loads(path.read_text(encoding="utf8"))
        files[str(path)] = sha256(path)
        if payload.get("pair") != "USD/CNH":
            continue
        if payload.get("source") != "interactive-brokers" or payload.get("data_type") != "MIDPOINT":
            raise ValueError("Unsupported USD/CNH observation source")
        observed = datetime.fromisoformat(payload["observed_at"])
        if observed.tzinfo is None:
            raise ValueError("FX capture has no timezone")
        legs = {r["trade_date"]: r for r in payload["legs"].get("USD/CNH", [])}
        for row in payload["rates"]:
            day = date.fromisoformat(row["trade_date"])
            if observed < datetime.combine(day, time(17), ZoneInfo("America/New_York")):
                raise ValueError("FX capture precedes the completed FX session")
            if row != legs.get(str(day)) or not valid_ohlc(PriceBar.model_validate(row)):
                raise ValueError("FX output differs from observed USD/CNH leg")
            item = dict(rate=str(Decimal(row["close"])), available_at=observed.astimezone(UTC).isoformat(),
                        source_path=str(path), source_sha256=files[str(path)])
            old = selected.get(str(day))
            if old is None or item["available_at"] > old["available_at"]:
                selected[str(day)] = item
            elif item["available_at"] == old["available_at"] and item["rate"] != old["rate"]:
                raise ValueError("Conflicting simultaneous FX observations")
    return selected, files


def load_tracked_inputs(settings, analytics, config):
    protocol = config["calculation"]
    publication = analytics.latest("governance/catalog")
    if not publication:
        raise ValueError("No published audited price history; tracked strategies cannot use raw bars")
    batch = publication["version"]
    root = Path(json.loads(publication["provenance"])["root"])
    governed = GovernedInputs(root, batch)
    symbols = list(instruments_for_definition(current_sota_definition()))
    raw = {symbol: governed.rows(symbol, protocol["warmup_start"], str(date.today())) for symbol in [*symbols, "URTH"]}
    if any(not rows for rows in raw.values()):
        raise ValueError("Missing audited ETF or benchmark history")
    price_through = min(rows[-1]["trade_date"] for rows in raw.values())
    if not completed_session(date.fromisoformat(price_through)):
        raise ValueError("Audited price endpoint is not a completed session")
    model_path, fx_path = Path(protocol["base_models_path"]), Path(protocol["legacy_fx_path"])
    if sha256(model_path) != protocol["base_models_sha256"] or sha256(fx_path) != protocol["legacy_fx_sha256"]:
        raise ValueError("Pinned model or historical FX snapshot changed")
    legacy_fx = json.loads(fx_path.read_text(encoding="utf8"))
    observed, files = validated_fx_observations((settings.data_dir / "market_data/fx_observations").glob("USD_CNH_*.json"))
    fx = {d: v for d, v in legacy_fx.items() if d <= protocol["legacy_fx_through"]}
    fx.update({d: r["rate"] for d, r in observed.items() if d > protocol["legacy_fx_through"]})
    days = [r["trade_date"] for r in raw[symbols[0]] if r["trade_date"] <= price_through]
    missing = next((d for d in days if d not in fx), None)
    usable = [d for d in days if missing is None or d < missing]
    if not usable or usable[-1] < protocol["start"]:
        raise ValueError("No complete audited price / supported FX interval")
    end = usable[-1]
    bars = {s: [etf_bar(r) for r in raw[s] if r["trade_date"] <= end] for s in symbols}
    # Buy-and-hold does not consume volume; zero historical ETF volume is not a
    # reason to invent activity or discard a supported adjusted price.
    urth = [dict(trade_date=r["trade_date"], open=str(r["adjusted_open"]), close=str(r["adjusted_close"]))
            for r in raw["URTH"] if r["trade_date"] <= end]
    provenance = dict(batch=batch, governed_files=governed.used, price_through=price_through, valuation_through=end,
        fx_evidence=observed, fx_files=files, legacy_fx_sha256=protocol["legacy_fx_sha256"],
        legacy_fx_through=protocol["legacy_fx_through"], first_missing_fx=missing,
        price_basis="Audited dividend/split-adjusted OHLC and split-adjusted source volume",
        historical_availability="Revised historical price vintages; no certified historical availability")
    records = [dict(point_key=d, family="validated_fx_observation", entity="USD/CNH", observed_at=d,
                    available_at=r["available_at"], payload=encode(r)) for d, r in observed.items()]
    analytics.publish("governance/fx-usd-cnh", digest(encode(observed)), records,
        provenance=dict(method="observed midpoint leg equality, positive OHLC and post-close capture", files=files))
    latest_bars = {s: [etf_bar(r) for r in raw[s] if r["trade_date"] <= price_through] for s in symbols}
    return dict(bars=bars, fx={d: fx[d] for d in usable}, urth=urth,
                models=json.loads(model_path.read_text(encoding="utf8")), provenance=provenance, latest_bars=latest_bars)
