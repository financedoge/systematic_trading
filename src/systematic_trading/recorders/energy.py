"""Application-owned EIA capture, verified publication and first-seen readers."""
from __future__ import annotations

from datetime import UTC, date, datetime
import json
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.recorders.energy_parsers import natural_gas, petroleum
from systematic_trading.runtime_io import atomic_json, exclusive_lock

PREFIX = "governance/eia-energy/"
PARSERS = {"petroleum": petroleum, "natural-gas": natural_gas}
POLICY = "eia-first-seen-v1"


def utc_now():
    return datetime.now(UTC)


def aware(value):
    value = datetime.fromisoformat(value) if isinstance(value, str) else value
    if value.tzinfo is None:
        raise ValueError("Energy timestamps must include timezone")
    return value.astimezone(UTC)


def configuration(settings):
    config = json.loads(settings.energy_recorder_config_path.read_text(encoding="utf-8"))
    ids = [p["id"] for p in config["products"]]
    if not ids or len(set(ids)) != len(ids) or not set(ids) <= PARSERS.keys():
        raise ValueError("Invalid energy recorder registry")
    if config["refresh_seconds"] < 60 or config["max_age_days"] < 1:
        raise ValueError("Invalid energy recorder interval")
    for product in config["products"]:
        if any(Path(name).name != name or not url.startswith("https://ir.eia.gov/")
               for name, url in product["files"].items()):
            raise ValueError("Invalid EIA source file")
    return config


def fetch_bytes(url):
    request = Request(url, headers={"User-Agent": "systematic-trading-research/0.1"})
    with urlopen(request, timeout=30) as response:
        content = response.read(10_000_001)
    if not content or len(content) > 10_000_000:
        raise ValueError("Unexpected EIA response size")
    return content


def seal(root):
    files = {p.name: digest(p.read_bytes()) for p in root.iterdir() if p.is_file() and p.name != "manifest.json"}
    atomic_json(root / "manifest.json", files)
    return digest((root / "manifest.json").read_bytes())


def checked(root, batch, name):
    root = Path(root).resolve()
    manifest = (root / "manifest.json").read_bytes()
    if digest(manifest) != batch:
        raise ValueError("Energy manifest hash mismatch")
    files = json.loads(manifest)
    if name not in files:
        raise ValueError("Unpublished energy document")
    for relative, expected in files.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or digest(path.read_bytes()) != expected:
            raise ValueError("Energy input hash mismatch")
    return json.loads((root / name).read_text(encoding="utf-8"))


def load_product(analytics, product):
    publication = analytics.latest(PREFIX + product)
    if publication is None:
        return None, None
    root = json.loads(publication["provenance"])["root"]
    pin = dict(root=root, batch=publication["version"])
    data = checked(**pin, name="catalog.json")
    if data["product"]["id"] != product or data["policy"] != POLICY:
        raise ValueError("Energy catalog identity mismatch")
    return data, pin


class EnergyInputs:
    """Read only pinned audited captures; source release time never grants availability."""
    def __init__(self, root, batch):
        self.catalog = checked(root, batch, "catalog.json")
        if self.catalog["policy"] != POLICY:
            raise ValueError("Unsupported energy availability policy")
        self.batch = batch

    def capture(self, batch):
        entry = next((e for e in self.catalog["captures"] if e["batch"] == batch), None)
        if entry is None:
            raise ValueError("Energy capture not in pinned catalog")
        snapshot = checked(entry["root"], entry["batch"], "snapshot.json")
        for key in ["product", "report_date", "source_release_at", "first_seen_at", "fingerprint"]:
            if snapshot[key] != entry[key]:
                raise ValueError("Energy capture identity mismatch")
        if snapshot["policy"] != POLICY:
            raise ValueError("Energy capture availability policy mismatch")
        return snapshot

    def snapshot(self, *, decision_at):
        decision_at = aware(decision_at)
        eligible = [e for e in self.catalog["captures"] if aware(e["first_seen_at"]) < decision_at]
        if not eligible:
            raise ValueError("No energy capture was available at decision time")
        entry = max(eligible, key=lambda e: (e["source_release_at"], e["first_seen_at"]))
        snapshot = self.capture(entry["batch"])
        if aware(snapshot["source_release_at"]) >= decision_at:
            raise ValueError("Energy release was unavailable at decision time")
        age = (decision_at.date() - date.fromisoformat(snapshot["report_date"])).days
        if age > self.catalog["config"]["max_age_days"]:
            raise ValueError("Energy input is stale")
        if any(m["value"] is None for m in snapshot["metrics"]):
            raise ValueError("Energy input contains missing observations")
        return snapshot


def _refresh_product(settings, analytics, config, product, fetch, clock):
    base = settings.data_dir / "governance" / "eia-energy" / product["id"]
    base.mkdir(parents=True, exist_ok=True)
    status_path = base / "status.json"
    with exclusive_lock(base / "recorder.lock"):
        now = aware(clock())
        old, pin = load_product(analytics, product["id"])
        status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        config_hash = digest(encode(config))
        if old and old["config_sha256"] != config_hash:
            raise ValueError("Energy registry changed; explicit migration required")
        if old and status.get("batch") == pin["batch"] and status.get("last_checked_at"):
            # Verify the last capture even on an unchanged/cooldown path.
            EnergyInputs(**pin).capture(old["captures"][-1]["batch"])
            elapsed = (now - aware(status["last_checked_at"])).total_seconds()
            if 0 <= elapsed < config["refresh_seconds"] and not status.get("error"):
                return False
        root = base / "captures" / uuid4().hex
        root.mkdir(parents=True)
        receipt = dict(product=product["id"], attempted_at=now.isoformat(), sources=product["files"], files={})
        atomic_json(root / "receipt.json", receipt)
        try:
            files = {}
            for name, url in product["files"].items():
                content = fetch(url)
                captured_at = aware(clock())
                if captured_at < now:
                    raise ValueError("Clock moved backwards during EIA capture")
                # Raw bytes and response completion time precede all parsing/auditing.
                (root / name).write_bytes(content)
                receipt["files"][name] = dict(sha256=digest(content), captured_at=captured_at.isoformat())
                atomic_json(root / "receipt.json", receipt)
                files[name] = content
            first_seen = max(aware(r["captured_at"]) for r in receipt["files"].values())
            parsed = PARSERS[product["id"]](files)
            if aware(parsed["source_release_at"]) > first_seen:
                raise ValueError("EIA source release is future-dated")
            fingerprint = digest(encode(dict(config=config_hash, policy=POLICY, data=parsed)))
            if old:
                latest = old["captures"][-1]
                if parsed["report_date"] < latest["report_date"] or parsed["source_release_at"] < latest["source_release_at"]:
                    raise ValueError("EIA response regressed to an older release")
                if fingerprint == latest["fingerprint"]:
                    atomic_json(root / "unchanged.json", dict(retained_capture=latest["batch"]))
                    atomic_json(status_path, dict(last_checked_at=first_seen.isoformat(), batch=pin["batch"], error=None))
                    return False
            snapshot = dict(parsed, product=product["id"], policy=POLICY, fingerprint=fingerprint,
                            first_seen_at=first_seen.isoformat(), config_sha256=config_hash,
                            parser_sha256=digest(Path(__file__).with_name("energy_parsers.py").read_bytes()),
                            recorder_sha256=digest(Path(__file__).read_bytes()), receipt=receipt,
                            limitations=config["limitations"])
            atomic_json(root / "snapshot.json", snapshot)
            atomic_json(root / "config.json", config)
            capture_batch = seal(root)
            checked(root, capture_batch, "snapshot.json")
            entry = {key: snapshot[key] for key in ["product", "report_date", "source_release_at", "first_seen_at", "fingerprint"]}
            entry.update(root=str(root.resolve()), batch=capture_batch, metrics=len(snapshot["metrics"]))
            catalog_root = base / "catalogs" / uuid4().hex
            catalog_root.mkdir(parents=True)
            catalog = dict(policy=POLICY, product=product, config=config, config_sha256=config_hash,
                           captures=[*(old["captures"] if old else []), entry])
            atomic_json(catalog_root / "catalog.json", catalog)
            batch = seal(catalog_root)
            checked(catalog_root, batch, "catalog.json")
            # Preserve every release/revision as a separately addressable record.
            observations = [dict(point_key=e["batch"], family="energy_capture", entity=product["id"],
                                 observed_at=e["report_date"], available_at=e["first_seen_at"], payload=encode(e))
                            for e in catalog["captures"]]
            changed = analytics.publish(PREFIX + product["id"], batch, observations,
                [dict(point_key="catalog", media_type="application/json", payload=encode(catalog)),
                 dict(point_key="latest", media_type="application/json", payload=encode(snapshot))],
                provenance=dict(root=str(catalog_root.resolve()), policy=POLICY, config_sha256=config_hash))
            atomic_json(status_path, dict(last_checked_at=first_seen.isoformat(), batch=batch, error=None))
            return changed
        except Exception as exc:
            # Network errors may contain signed redirects; keep user-visible messages bounded.
            message = str(exc) if isinstance(exc, (ValueError, KeyError)) else type(exc).__name__ + " during EIA capture/publication"
            atomic_json(root / "failure.json", dict(error=message, failed_at=aware(clock()).isoformat()))
            atomic_json(status_path, dict(status, last_attempt_at=now.isoformat(), error=message))
            raise ValueError(product["id"] + ": " + message) from exc


def refresh_energy(settings, analytics, *, fetch=fetch_bytes, clock=utc_now):
    config = configuration(settings)
    if not settings.governed_refresh_enabled or not config["enabled"]:
        return False
    changed, errors = False, []
    for product in config["products"]:
        try:
            changed = _refresh_product(settings, analytics, config, product, fetch, clock) or changed
        except (OSError, ValueError, KeyError) as exc:
            errors.append(str(exc))
    if errors:
        raise ValueError("Energy recorder: " + "; ".join(errors))
    return changed


def catalog(analytics, settings, *, now=None):
    config = configuration(settings)
    now = aware(now or utc_now())
    products = []
    for product in config["products"]:
        data, pin = load_product(analytics, product["id"])
        status_path = settings.data_dir / "governance" / "eia-energy" / product["id"] / "status.json"
        status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
        info = dict(product, pin=pin, recorder=status, captures=[], latest=None, stale=True)
        if data:
            inputs = EnergyInputs(**pin)
            snapshot = inputs.capture(data["captures"][-1]["batch"])
            info.update(captures=data["captures"], latest=snapshot,
                        stale=(now.date()-date.fromisoformat(snapshot["report_date"])).days > config["max_age_days"])
        products.append(info)
    return dict(policy=POLICY, products=products, limitations=config["limitations"],
                refresh_seconds=config["refresh_seconds"], availability=config["availability"])
