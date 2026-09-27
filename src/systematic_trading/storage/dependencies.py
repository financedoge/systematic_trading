"""Explicit recovery prerequisites for analytical data outside SQL backups.

Do not advertise a SQL-only restore as a complete workstation transfer. Missing
immutable histories or publications stop handoff before ownership or DB writes.
"""
import json
from pathlib import Path

from systematic_trading.lean.contracts import sha256
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.research.governed_inputs import GovernedInputs


def dependency_receipt(settings):
    if settings.market_data_store_backend != "clickhouse":
        return dict(schema_version=1, storage="transactional_only", files={}, publications={})
    analytics = AnalyticsStore.from_settings(settings)
    publications = analytics.publication_index("")
    files = {}
    config_path = settings.strategy_monitoring_config_path.resolve()
    if config_path.exists():
        files[str(config_path)] = sha256(config_path)
        protocol = json.loads(config_path.read_text(encoding="utf8")).get("calculation", {})
        for name in ("base_models", "legacy_fx"):
            if name + "_path" in protocol:
                path = Path(protocol[name + "_path"]).resolve()
                actual = sha256(path)
                if actual != protocol[name + "_sha256"]:
                    raise ValueError("Recovery dependency hash mismatch: " + str(path))
                files[str(path)] = actual
    latest = analytics.latest("governance/catalog")
    roots = []
    if latest:
        root = Path(json.loads(latest["provenance"])["root"])
        reader = GovernedInputs(root, latest["version"])
        while reader:
            roots.append(dict(root=str(reader.root.resolve()), manifest_sha256=sha256(reader.root / "manifest.json")))
            for name, expected in reader.manifest.items():
                path = reader.root / name
                if sha256(path) != expected:
                    raise ValueError("Recovery input changed: " + str(path))
            reader = reader.parent
    # Current tracked result directories include code, model artifacts and LEAN
    # replay inputs. Keep exact locations/hashes in the prerequisite inventory.
    for folder in (settings.data_dir / "tracked_models", settings.data_dir / "tracked_strategies",
                   settings.data_dir / "market_data/fx_observations"):
        for path in folder.rglob("*"):
            if path.is_file():
                files[str(path.resolve())] = sha256(path)
    return dict(schema_version=1, storage="external_dependencies_required", analytics_workspace=analytics.workspace,
        files=files, governed_roots=roots,
        publications={key:value["version"] for key,value in publications.items()},
        note="SQL files are backed up. ClickHouse and the listed immutable artifacts must be copied/restored separately; prepare verifies them before changing databases or ownership.")


def verify_dependencies(settings, receipt):
    if not receipt:
        if settings.market_data_store_backend == "clickhouse":
            raise ValueError("Legacy SQL-only backup lacks analytical recovery prerequisites; create a new backup on the source PC")
        return
    for name, expected in receipt.get("files", {}).items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            raise ValueError("Restore prerequisite missing or changed: " + name)
    for root in receipt.get("governed_roots", []):
        reader = GovernedInputs(Path(root["root"]), root["manifest_sha256"])
        for name in reader.manifest:
            reader.checked(name)
    if receipt.get("publications"):
        analytics = AnalyticsStore.from_settings(settings)
        if analytics.workspace != receipt["analytics_workspace"]:
            raise ValueError("Analytical workspace differs; restore the original namespace before handoff")
        current = analytics.publication_index("")
        missing = [key for key,value in receipt["publications"].items() if current.get(key, {}).get("version") != value]
        if missing:
            raise ValueError("ClickHouse publications missing or changed: " + ", ".join(missing[:5]))
