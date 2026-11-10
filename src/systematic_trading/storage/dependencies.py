"""Explicit recovery prerequisites for analytical data outside SQL backups.

Do not advertise a SQL-only restore as a complete workstation transfer. Missing
immutable histories or publications stop handoff before ownership or DB writes.
"""
import json
from contextlib import contextmanager, nullcontext
import os
from pathlib import Path
import re

from systematic_trading.lean.contracts import sha256
from systematic_trading.market_data.analytics_store import AnalyticsStore
from systematic_trading.research.governed_inputs import GovernedInputs


def publication_versions(analytics, *, native=False):
    """A recovery receipt needs head identities, not large historical provenance."""
    if native:
        with analytics.catalog.connect() as connection:
            return {r['source_id']: r['version'] for r in connection.execute(
                'SELECT source_id,version FROM native_analytics.publication_heads '
                'WHERE workspace=%s ORDER BY source_id', (analytics.workspace,))}
    return {key: value['version'] for key, value in analytics.publication_index('').items()}


@contextmanager
def native_backup_snapshot(settings, *, progress=None):
    """Pin dependency reads and pg_dump to the same committed database view."""
    from systematic_trading.market_data.native_analytics import NativeAnalyticsStore
    analytics=NativeAnalyticsStore.from_settings(settings)
    # Use a dedicated connection, closed at exit. A cached idle pool would
    # falsely look like a live application writer during a subsequent restore.
    with analytics.catalog.store._connect() as connection:
        connection.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY')
        snapshot=connection.execute('SELECT pg_export_snapshot() AS id').fetchone()['id']
        analytics.catalog.connect=lambda: nullcontext(connection)
        yield snapshot,dependency_receipt(settings,analytics=analytics,progress=progress)


def directory_pins(folder, *, progress=None):
    """Pin immutable inventories once; directly hash files outside those bundles."""
    files = {}
    for parent, directories, names in os.walk(folder):
        if progress:
            progress()
        root = Path(parent)
        inventory_path = next((root / name for name in ('manifest.json', 'run.json') if name in names), None)
        if inventory_path:
            record = json.loads(inventory_path.read_text(encoding='utf8'))
            entries = record.get('files',record) if inventory_path.name == 'manifest.json' else record.get('artifacts')
            if isinstance(entries, dict) and entries and all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in entries.values()):
                files[str(inventory_path.resolve())] = sha256(inventory_path)
                directories[:] = []
                continue
        for name in names:
            path = root / name
            checksum = sha256(path)
            if not transient_dependency_reason(path, checksum):
                files[str(path.resolve())] = checksum
    return files


def transient_dependency_reason(path, checksum):
    """Recognize loose worker coordination files, never sealed bundle entries.

    Dataset/run locks contain no payload. A UUID-suffixed request is an
    uncommitted atomic write; consumers open only request.json. Keep this narrow
    so a filename suffix alone cannot excuse a missing durable artifact.
    """
    name = str(path).replace('\\', '/').lower()
    if (checksum == 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
            and re.search(r'/tracked_strategies/[0-9a-f]{64}/(?:datasets|runs)/'
                          r'(?:[^/]+\.lock|[^/]+\.worker-[0-9a-f]{32}/bundle\.lock)$', name)):
        return 'empty strategy worker lock'
    if re.search(r'/tracked_models/[0-9a-f]{64}/request\.json\.[0-9a-f]{32}\.tmp$', name):
        return 'uncommitted atomic model request'
    return None


def dependency_receipt(settings, *, analytics=None, progress=None):
    if settings.market_data_store_backend not in {"clickhouse","parquet"}:
        return dict(schema_version=1, storage="transactional_only", files={}, publications={})
    analytics = analytics or AnalyticsStore.from_settings(settings)
    publications = publication_versions(analytics, native=settings.market_data_store_backend == 'parquet')
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
    usd = analytics.latest('governance/usd-broad-index')
    if usd:
        usd_root = Path(json.loads(usd['provenance'])['root']).resolve()
        # This publication is read from files by the USD model provider. The
        # previous broad var backup masked its omission from the SQL contract.
        files.update(directory_pins(usd_root, progress=progress))
    if latest:
        root = Path(json.loads(latest["provenance"])["root"])
        reader = GovernedInputs(root, latest["version"])
        while reader:
            roots.append(dict(root=str(reader.root.resolve()), manifest_sha256=sha256(reader.root / "manifest.json")))
            # Publication already verified these immutable files. A SQL checkpoint
            # records the committed manifest; full data verification remains a
            # mandatory restore/scrub operation below, not a five-minute scan of
            # millions of hard-linked history names.
            reader = reader.parent
    # Current tracked result directories include code, model artifacts and LEAN
    # replay inputs. Keep exact locations/hashes in the prerequisite inventory.
    for folder in (settings.data_dir / "tracked_models", settings.data_dir / "tracked_strategies",
                   settings.data_dir / "market_data/fx_observations"):
        files.update(directory_pins(folder, progress=progress))
    native={}
    if settings.market_data_store_backend=='parquet':
        with analytics.catalog.connect() as c:
            datasets=c.execute('SELECT dataset_key,revision,manifest_sha256,manifest FROM native_analytics.datasets '
                'WHERE workspace=%s ORDER BY dataset_key,revision',(analytics.workspace,)).fetchall()
        for index, dataset in enumerate(datasets):
            if progress and index % 1024 == 0:
                progress()
            manifest=dataset.pop('manifest')
            from systematic_trading.market_data.analytics_store import digest,encode
            if digest(encode(manifest))!=dataset['manifest_sha256']: raise ValueError('Native backup manifest identity mismatch')
            for fragment in manifest['fragments']:
                path=(analytics.lake.root/fragment['path']).resolve()
                if not path.is_relative_to(analytics.lake.root/'parquet'): raise ValueError('Unsafe native backup prerequisite')
                files[str(path)]=fragment['sha256']
        native=dict(root=str(analytics.lake.root),datasets=datasets)
    return dict(schema_version=1, storage="external_dependencies_required", analytics_workspace=analytics.workspace,
        files=files, governed_roots=roots,native_analytics=native,
        publications=publications,
        note="SQL files are backed up. The analytical backend and listed immutable artifacts must be copied/restored together; prepare verifies them before changing databases or ownership.")


def verify_dependencies(settings, receipt, *, verify_publications=True):
    if not receipt:
        if settings.market_data_store_backend in {"clickhouse","parquet"}:
            raise ValueError("Legacy SQL-only backup lacks analytical recovery prerequisites; create a new backup on the source PC")
        return
    if receipt.get('publications') and getattr(settings,'market_data_store_backend',None)=='parquet':
        from systematic_trading.market_data.analytics_store import digest
        workspace=settings.analytics_workspace or digest(str(settings.data_dir.resolve()).lower())
        if workspace!=receipt['analytics_workspace']:
            raise ValueError('Analytical workspace differs; restore the original namespace before handoff')
    for name, expected in receipt.get("files", {}).items():
        path = Path(name)
        if not path.is_file() or sha256(path) != expected:
            raise ValueError("Restore prerequisite missing or changed: " + name)
        if path.name in {'manifest.json', 'run.json'}:
            record = json.loads(path.read_text(encoding='utf8'))
            inventory = record.get('files', {}) if path.name == 'manifest.json' else record.get('artifacts', {})
            # Bundle manifests have the form {relative: sha256}; receipts wrap
            # their inventory. Validate every referenced byte before restore.
            if path.name == 'manifest.json' and not inventory and all(isinstance(v, str) and re.fullmatch('[0-9a-f]{64}', v) for v in record.values()):
                inventory = record
            for relative, checksum in inventory.items():
                target = (path.parent / relative).resolve()
                if not target.is_relative_to(path.parent.resolve()) or sha256(target) != checksum:
                    raise ValueError('Restore bundle prerequisite changed: ' + str(target))
            if inventory:
                actual = {p.relative_to(path.parent).as_posix() for p in path.parent.rglob('*') if p.is_file() and p != path}
                if actual != set(inventory):
                    raise ValueError('Restore bundle inventory changed: ' + str(path))
    for root in receipt.get("governed_roots", []):
        reader = GovernedInputs(Path(root["root"]), root["manifest_sha256"])
        for name in reader.manifest:
            reader.checked(name)
    if receipt.get("publications") and verify_publications:
        analytics = AnalyticsStore.from_settings(settings)
        if analytics.workspace != receipt["analytics_workspace"]:
            raise ValueError("Analytical workspace differs; restore the original namespace before handoff")
        current = publication_versions(analytics, native=settings.market_data_store_backend == 'parquet')
        missing = [key for key,value in receipt["publications"].items() if current.get(key) != value]
        if missing:
            raise ValueError("Analytical publications missing or changed: " + ", ".join(missing[:5]))
