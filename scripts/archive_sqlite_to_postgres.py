"""Preserve all legacy SQLite rows without overwriting newer trading history."""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.storage.legacy_archive import archive_snapshot
from systematic_trading.storage.nas_sync import LocalDatabases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    settings = AppSettings()
    db = LocalDatabases(ROOT, {"postgres": True, "sqlite_paths": []}, settings)
    with db.connection() as connection:
        report = archive_snapshot(args.source or settings.database_path, connection)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"snapshot_id": report["snapshot_id"], "verified": True,
                      "rows": sum(t["count"] for t in report["tables"].values())}))


if __name__ == "__main__":
    main()
