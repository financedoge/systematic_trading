from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.recorders import load_storage_policy, query_raw_catalog, rebuild_raw_catalog


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Query or rebuild the raw market-data catalog manifest.")
    parser.add_argument("--storage-policy", default=None, help="Defaults to ST_MARKET_DATA_STORAGE_POLICY_PATH.")
    parser.add_argument("--root", default=None, help="Raw root. Defaults to hot_spool_root from storage policy.")
    parser.add_argument("--source", default=None)
    parser.add_argument("--environment", default=None)
    parser.add_argument("--data-kind", default=None)
    parser.add_argument("--symbol", default=None)
    parser.add_argument("--date", default=None, help="Recorder partition date, YYYY-MM-DD.")
    parser.add_argument("--raw-schema-version", type=int, default=None)
    parser.add_argument("--rebuild", action="store_true", help="Scan raw files and append manifest entries before querying.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum query entries to print.")
    args = parser.parse_args(argv)

    policy = load_storage_policy(_resolve_repo_path(args.storage_policy or AppSettings().market_data_storage_policy_path))
    root = Path(args.root) if args.root else policy.hot_spool_root
    day = date.fromisoformat(args.date) if args.date else None
    if args.limit < 1:
        raise SystemExit("--limit must be positive")

    rebuild_summary = None
    if args.rebuild:
        rebuild_summary = rebuild_raw_catalog(
            root,
            source=args.source,
            environment=args.environment,
            data_kind=args.data_kind,
            symbol=args.symbol,
            day=day,
        )

    query = query_raw_catalog(
        root,
        source=args.source,
        environment=args.environment,
        data_kind=args.data_kind,
        symbol=args.symbol,
        day=day,
        raw_schema_version=args.raw_schema_version,
    )
    payload = {
        "rebuild": rebuild_summary.model_dump(mode="json") if rebuild_summary is not None else None,
        "query": {
            **query.model_dump(mode="json", exclude={"entries"}),
            "entry_count": len(query.entries),
            "entries": [entry.model_dump(mode="json") for entry in query.entries[: args.limit]],
            "entries_truncated": max(len(query.entries) - args.limit, 0),
        },
    }
    print(json.dumps(payload, sort_keys=True))
    return 1 if query.records_invalid or (rebuild_summary is not None and rebuild_summary.records_invalid) else 0


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
