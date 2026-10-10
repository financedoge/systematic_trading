"""Recorder-first ETF admissions through the existing verified price publisher.

Independent research acquisition failures retain the last committed catalog and
do not prevent the active ETF producer from refreshing on the next cycle.
"""
from datetime import UTC, datetime
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from uuid import uuid4

from systematic_trading.daily_quality import completed_session
from systematic_trading.lean.contracts import sha256
from systematic_trading.live.trading_calendar import previous_us_trading_day
from systematic_trading.portfolio.context import NY
from systematic_trading.research.etf_admission import admission_hold, hold_record
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.governed_refresh import acquire, _build_publish, _write
from systematic_trading.research.price_governance import names_agree


def fetch_issuer(url):
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=30) as response:
        return response.read()


def validate_admission(fund, source, rows, audit, sessions, cutoff):
    symbol = fund["symbol"]
    if not names_agree(fund["name"], source.name):
        raise ValueError("Issuer/provider identity disagreement: " + symbol)
    boundary = source.metadata.get("listing_boundary_date")
    if not boundary or boundary < fund["inception"] or boundary > fund["required_start"]:
        raise ValueError("Unsupported fund listing boundary: " + symbol)
    if fund.get("listing_date") and boundary != fund["listing_date"]:
        raise ValueError("Issuer/provider listing date disagreement: " + symbol)
    expected = sorted(d for d in sessions if fund["required_start"] <= d <= cutoff)
    observed = [r["trade_date"] for r in rows if r["trade_date"] >= fund["required_start"]]
    if not expected or observed != expected or audit["status"] != "audited_with_limitations":
        raise ValueError("Incomplete or quarantined research ETF history: " + symbol)
    if any(r["adjustment_status"] != "reported_distribution_checks_pass" for r in rows):
        raise ValueError("Distribution audit failed: " + symbol)


def recorder_status(settings):
    path = settings.research_etf_recorder_config_path
    if not path.exists():
        return dict(enabled=False, funds=[])
    config = json.loads(path.read_text(encoding="utf8"))
    state = settings.data_dir / "governance/research-recorder-state.json"
    saved = json.loads(state.read_text(encoding="utf8")) if state.exists() else {}
    return dict(enabled=config["enabled"], owner="application", funds=[
        dict(symbol=f["symbol"], name=f["name"], purpose=f["purpose"],
             **saved.get(f["symbol"], dict(status="pending", message="Awaiting first acquisition and audit")))
        for f in config["funds"]])


def refresh_research_etfs(settings, analytics, *, now=None, fetch=acquire, issuer_fetch=fetch_issuer):
    path = settings.research_etf_recorder_config_path
    if not settings.governed_refresh_enabled or not path.exists():
        return False
    config = json.loads(path.read_text(encoding="utf8"))
    if not config["enabled"]:
        return False
    funds = config["funds"]
    symbols = [f["symbol"] for f in funds]
    if len(set(symbols)) != len(symbols) or any(not re.fullmatch("[A-Z]{1,10}", s) for s in symbols):
        raise ValueError("Invalid research recorder universe")
    now = now or datetime.now(UTC)
    day = now.astimezone(NY).date()
    if not completed_session(day, now=now):
        day = previous_us_trading_day(day)
    cutoff = str(day)
    state_path = settings.data_dir / "governance/research-recorder-state.json"
    state = json.loads(state_path.read_text(encoding="utf8")) if state_path.exists() else {}
    changed, errors = False, []
    for fund in funds:
        symbol = fund["symbol"]
        hold = admission_hold(symbol, fund.get("admission_hold"))
        if hold:
            state[symbol] = dict(state.get(symbol, {}), status="quarantined", admission_held=True,
                                 message=hold, hold_record=hold_record(symbol), config_sha256=sha256(path))
            _write(state_path.parent, state_path.name, state)
            continue
        publication = analytics.latest("governance/catalog")
        if not publication:
            raise ValueError("Research recorder requires the initial audited catalog")
        prior = GovernedInputs(Path(json.loads(publication["provenance"])["root"]), publication["version"])
        catalog = json.loads(prior.checked("catalog.json").read_text(encoding="utf8"))
        old = prior.rows(symbol, "1950-01-01", cutoff) if any(r["symbol"] == symbol for r in catalog) else []
        previous = state.get(symbol, {})
        if old and old[-1]["trade_date"] == cutoff and previous.get("config_sha256") == sha256(path) and previous.get("status") == "published":
            continue
        if previous.get("cutoff") == cutoff and (now - datetime.fromisoformat(previous["attempted_at"])).total_seconds() < 300:
            if previous.get("status") == "quarantined":
                errors.append(previous["message"])
            continue
        output = settings.data_dir.resolve() / "governance" / ("research-" + cutoff + "-" + uuid4().hex[:12])
        receipt = dict(status="acquiring", cutoff=cutoff, attempted_at=now.isoformat(),
                       config_sha256=sha256(path), parent=publication["version"], evidence_root=str(output))
        state[symbol] = receipt
        _write(state_path.parent, state_path.name, state)
        try:
            raw = issuer_fetch(fund["issuer_url"])
            evidence = output / "issuer" / (symbol + ".html")
            evidence.parent.mkdir(parents=True, exist_ok=True)
            evidence.write_bytes(raw)
            # Compare visible identity tokens, allowing HTML tags and whitespace.
            from html import unescape
            plain = " ".join(unescape(re.sub("<[^>]+>", " ", raw.decode("utf8"))).split())
            if not all(token in plain for token in fund["issuer_required_text"]):
                raise ValueError("Issuer reference schema/identity requires review: " + symbol)
            admitted = dict(fund, captured_at=now.isoformat(), issuer_sha256=sha256(evidence),
                            parser_version="research-etf-v1", config_sha256=sha256(path), recorder_code_sha256=sha256(Path(__file__)))
            _write(output, "recorder.json", admitted)
            _build_publish(analytics, prior, publication, output, [symbol], {symbol: old}, cutoff, now, fetch,
                           admissions={symbol: admitted})
            batch = sha256(output / "manifest.json")
            audit = json.loads((output / f"audits/{symbol}.json").read_text(encoding="utf8"))
            receipt.update(status="published", batch=batch, first=audit["first"], last=audit["last"], rows=audit["rows"],
                           message="Adjusted prices and distributions audited; historical availability remains uncertified")
            changed = True
        except Exception as exc:
            receipt.update(status="quarantined", message=str(exc))
            errors.append(str(exc))
        state[symbol] = receipt
        _write(state_path.parent, state_path.name, state)
    if errors:
        raise ValueError("Research ETF recorder: " + "; ".join(errors))
    return changed
