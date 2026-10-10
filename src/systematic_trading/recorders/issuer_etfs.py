"""Prospective issuer ETF captures, independent publication and pinned readers."""
from datetime import UTC, date, datetime
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.recorders.issuer_parsers import parse_snapshot
from systematic_trading.runtime_io import atomic_json, exclusive_lock

PREFIX = "governance/issuer-etfs/"
POLICY = "issuer-first-seen-v1"
GROUPS = {"nav", "characteristics", "allocation", "holdings"}


def utc_now():
    return datetime.now(UTC)


def aware(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if value.tzinfo is None:
        raise ValueError("Issuer timestamps must include timezone")
    return value.astimezone(UTC)


def configuration(settings):
    config = json.loads(settings.issuer_etf_recorder_config_path.read_text(encoding="utf-8"))
    symbols = [f["symbol"] for f in config["funds"]]
    if not symbols or len(set(symbols)) != len(symbols) or any(not re.fullmatch(r"[A-Z]{1,5}", s) for s in symbols):
        raise ValueError("Invalid issuer fund registry")
    if config["refresh_seconds"] < 60 or config["max_age_days"] < 1:
        raise ValueError("Invalid issuer recorder interval")
    for fund in config["funds"]:
        if set(fund["files"]) != {"fund.html", "holdings.xlsx"}:
            raise ValueError("Invalid issuer source files")
        if not all(url.startswith("https://www.ssga.com/") for url in fund["files"].values()):
            raise ValueError("Unqualified issuer source")
    return config


def fetch_bytes(url):
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 systematic-trading-research/0.1"}), timeout=30) as response:
        if not response.url.startswith("https://www.ssga.com/"):
            raise ValueError("Unqualified issuer redirect")
        raw = response.read(10_000_001)
    if not raw or len(raw) > 10_000_000:
        raise ValueError("Unexpected issuer response size")
    return raw


def seal(root):
    atomic_json(root / "manifest.json", {p.name: digest(p.read_bytes()) for p in root.iterdir()
                                       if p.is_file() and p.name != "manifest.json"})
    return digest((root / "manifest.json").read_bytes())


def checked(root, batch, name):
    root = Path(root).resolve()
    manifest = (root / "manifest.json").read_bytes()
    if digest(manifest) != batch:
        raise ValueError("Issuer manifest hash mismatch")
    files = json.loads(manifest)
    if name not in files:
        raise ValueError("Unpublished issuer document")
    for relative, expected in files.items():
        path = (root / relative).resolve()
        if Path(relative).name != relative or not path.is_relative_to(root) or digest(path.read_bytes()) != expected:
            raise ValueError("Issuer input hash mismatch")
    return json.loads((root / name).read_text(encoding="utf-8"))


def load_fund(analytics, symbol):
    publication = analytics.latest(PREFIX + symbol)
    if publication is None:
        return None, None
    pin = dict(root=json.loads(publication["provenance"])["root"], batch=publication["version"])
    data = checked(**pin, name="catalog.json")
    if data["fund"]["symbol"] != symbol or data["policy"] != POLICY:
        raise ValueError("Issuer catalog identity mismatch")
    return data, pin


class IssuerInputs:
    """No archives, implicit latest lookup, backfill, or cross-capture substitution."""
    def __init__(self, root, batch):
        self.catalog = checked(root, batch, "catalog.json")
        if self.catalog["policy"] != POLICY:
            raise ValueError("Unsupported issuer availability policy")
        self.batch = batch

    def capture(self, batch):
        entry = next((e for e in self.catalog["captures"] if e["batch"] == batch), None)
        if entry is None:
            raise ValueError("Issuer capture not in pinned catalog")
        snapshot = checked(entry["root"], batch, "snapshot.json")
        if any(snapshot[k] != entry[k] for k in ["symbol", "dates", "first_seen_at", "fingerprint"]):
            raise ValueError("Issuer capture identity mismatch")
        if snapshot["symbol"] != self.catalog["fund"]["symbol"] or snapshot["policy"] != POLICY:
            raise ValueError("Issuer capture policy or fund mismatch")
        return snapshot

    def snapshot(self, *, decision_at, groups=tuple(sorted(GROUPS))):
        decision_at = aware(decision_at)
        if not groups or not set(groups) <= GROUPS:
            raise ValueError("Unsupported issuer feature groups")
        eligible = [e for e in self.catalog["captures"] if aware(e["first_seen_at"]) < decision_at]
        if not eligible:
            raise ValueError("No issuer capture was available at decision time")
        entry = max(eligible, key=lambda e: aware(e["first_seen_at"]))
        snapshot = self.capture(entry["batch"])
        for group in groups:
            age = (decision_at.astimezone(ZoneInfo("America/New_York")).date()-date.fromisoformat(snapshot["dates"][group])).days
            if not 0 <= age <= self.catalog["config"]["max_age_days"]:
                raise ValueError("Issuer input is stale or future-dated: " + group)
        if any(m["group"] in groups and m["value"] is None for m in snapshot["metrics"]):
            raise ValueError("Issuer input contains missing observations")
        if "nav" in groups and not snapshot["nav_reconciled"]:
            raise ValueError("Issuer NAV and shares are unreconciled")
        if "holdings" in groups and not snapshot["holdings"]["weights_reconciled"]:
            raise ValueError("Issuer holdings weight residual is unresolved")
        # Return requested sections only: validating NAV must not grant holdings use.
        return dict(symbol=snapshot["symbol"], first_seen_at=snapshot["first_seen_at"],
                    catalog_batch=self.batch, capture_batch=entry["batch"],
                    dates={g: snapshot["dates"][g] for g in groups},
                    metrics=[m for m in snapshot["metrics"] if m["group"] in groups],
                    **({"holdings": snapshot["holdings"]} if "holdings" in groups else {}),
                    **({"industry_allocation": snapshot["industry_allocation"]} if "allocation" in groups else {}))


def _refresh_fund(settings, analytics, config, fund, fetch, clock):
    base = settings.data_dir / "governance" / "issuer-etfs" / fund["symbol"]
    base.mkdir(parents=True, exist_ok=True)
    status_path = base / "status.json"
    with exclusive_lock(base / "recorder.lock"):
        now = aware(clock())
        old, pin = load_fund(analytics, fund["symbol"])
        status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        config_hash = digest(encode(config))
        if old and old["config_sha256"] != config_hash:
            raise ValueError("Issuer registry changed; explicit migration required")
        if old:
            IssuerInputs(**pin).capture(old["captures"][-1]["batch"])
            if now < aware(old["captures"][-1]["first_seen_at"]):
                raise ValueError("Clock precedes latest issuer capture")
        if old and status.get("batch") == pin["batch"] and status.get("last_checked_at") and not status.get("error"):
            if 0 <= (now-aware(status["last_checked_at"])).total_seconds() < config["refresh_seconds"]:
                return False
        root = base / "captures" / uuid4().hex
        root.mkdir(parents=True)
        receipt = dict(symbol=fund["symbol"], attempted_at=now.isoformat(), sources=fund["files"], files={})
        atomic_json(root / "receipt.json", receipt)
        try:
            files = {}
            last_time = now
            for name, url in fund["files"].items():
                content = fetch(url)
                (root / name).write_bytes(content)
                captured_at = aware(clock())
                receipt["files"][name] = dict(sha256=digest(content), captured_at=captured_at.isoformat())
                atomic_json(root / "receipt.json", receipt)
                if captured_at < last_time:
                    raise ValueError("Clock moved backwards during issuer capture")
                last_time = captured_at
                files[name] = content
            first_seen = last_time
            parsed = parse_snapshot(files, fund)
            if any(date.fromisoformat(d) > first_seen.astimezone(ZoneInfo("America/New_York")).date() for d in parsed["dates"].values()):
                raise ValueError("Issuer as-of date is future-dated")
            fingerprint = digest(encode(dict(config=config_hash, policy=POLICY, data=parsed)))
            if old:
                latest = old["captures"][-1]
                if any(d < latest["dates"][group] for group, d in parsed["dates"].items()):
                    raise ValueError("Issuer source regressed to an older as-of date")
                if fingerprint == latest["fingerprint"]:
                    atomic_json(root / "unchanged.json", dict(retained_capture=latest["batch"]))
                    atomic_json(status_path, dict(last_checked_at=first_seen.isoformat(), batch=pin["batch"], error=None))
                    return False
            warnings = []
            if not parsed["holdings"]["weights_reconciled"]:
                warnings.append("Holdings weight residual is unexplained; holdings features remain unavailable. Values are not renormalized.")
            if not parsed["nav_reconciled"]:
                warnings.append("NAV/share/AUM reconciliation is unavailable because a value is missing.")
            if any(m["value"] is None for m in parsed["metrics"]):
                warnings.append("Missing statistics remain missing and block their feature group.")
            snapshot = dict(parsed, policy=POLICY, fingerprint=fingerprint, first_seen_at=first_seen.isoformat(),
                            config_sha256=config_hash, receipt=receipt, warnings=warnings, limitations=config["limitations"])
            atomic_json(root / "snapshot.json", snapshot)
            atomic_json(root / "config.json", config)
            for name in ["issuer_etfs.py", "issuer_parsers.py"]:
                (root / name).write_bytes(Path(__file__).with_name(name).read_bytes())
            capture_batch = seal(root)
            checked(root, capture_batch, "snapshot.json")
            entry = {k: snapshot[k] for k in ["symbol", "dates", "first_seen_at", "fingerprint"]}
            entry.update(root=str(root.resolve()), batch=capture_batch, holdings=len(parsed["holdings"]["rows"]))
            catalog_root = base / "catalogs" / uuid4().hex
            catalog_root.mkdir(parents=True)
            data = dict(policy=POLICY, fund=fund, config=config, config_sha256=config_hash,
                        captures=[*(old["captures"] if old else []), entry])
            atomic_json(catalog_root / "catalog.json", data)
            batch = seal(catalog_root)
            checked(catalog_root, batch, "catalog.json")
            observations = [dict(point_key=e["batch"], family="issuer_capture", entity=fund["symbol"],
                                 observed_at=e["dates"]["nav"], available_at=e["first_seen_at"], payload=encode(e))
                            for e in data["captures"]]
            changed = analytics.publish(PREFIX + fund["symbol"], batch, observations,
                [dict(point_key="catalog", media_type="application/json", payload=encode(data)),
                 dict(point_key="latest", media_type="application/json", payload=encode(snapshot))],
                provenance=dict(root=str(catalog_root.resolve()), policy=POLICY, config_sha256=config_hash))
            atomic_json(status_path, dict(last_checked_at=first_seen.isoformat(), batch=batch, error=None))
            return changed
        except Exception as exc:
            message = str(exc) if isinstance(exc, (ValueError, KeyError)) else type(exc).__name__ + " during issuer capture/publication"
            atomic_json(root / "failure.json", dict(error=message, failed_at=aware(clock()).isoformat()))
            atomic_json(status_path, dict(status, last_attempt_at=now.isoformat(), error=message))
            raise ValueError(fund["symbol"] + ": " + message) from exc


def refresh_issuer_etfs(settings, analytics, *, fetch=fetch_bytes, clock=utc_now):
    config = configuration(settings)
    if not settings.governed_refresh_enabled or not config["enabled"]:
        return False
    changed, errors = False, []
    for fund in config["funds"]:
        try:
            changed = _refresh_fund(settings, analytics, config, fund, fetch, clock) or changed
        except (OSError, ValueError, KeyError) as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError("Issuer recorder: " + "; ".join(errors))
    return changed


def catalog(analytics, settings, *, now=None):
    config = configuration(settings)
    now = aware(now or utc_now())
    funds = []
    for fund in config["funds"]:
        info = dict(fund, pin=None, captures=[], latest=None, stale=True, verification_error=None)
        status_path = settings.data_dir / "governance" / "issuer-etfs" / fund["symbol"] / "status.json"
        try:
            info["recorder"] = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
            data, pin = load_fund(analytics, fund["symbol"])
            if data:
                snapshot = IssuerInputs(**pin).capture(data["captures"][-1]["batch"])
                info.update(pin=pin, captures=data["captures"], latest=snapshot,
                            stale=any(not 0 <= (now.astimezone(ZoneInfo("America/New_York")).date()-date.fromisoformat(snapshot["dates"][g])).days <= config["max_age_days"] for g in GROUPS))
        except (OSError, ValueError, KeyError):
            info.update(verification_error="Issuer publication failed verification", recorder={})
        funds.append(info)
    return dict(policy=POLICY, funds=funds, limitations=config["limitations"],
                refresh_seconds=config["refresh_seconds"], availability=config["availability"])
