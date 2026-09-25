from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.recorders import dry_run_raw_replay, load_storage_policy


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Dry-run replay validation for raw market-data JSONL.")
    parser.add_argument("--storage-policy", default=None, help="Defaults to ST_MARKET_DATA_STORAGE_POLICY_PATH.")
    parser.add_argument("--root", default=None, help="Raw root. Defaults to hot_spool_root from storage policy.")
    parser.add_argument("--source", default="interactive-brokers")
    parser.add_argument("--environment", default="paper")
    parser.add_argument("--data-kind", default="bar")
    parser.add_argument("--date", required=True, help="UTC recorder partition date, YYYY-MM-DD.")
    parser.add_argument("--symbol", required=True)
    args = parser.parse_args(argv)

    policy = load_storage_policy(_resolve_repo_path(args.storage_policy or AppSettings().market_data_storage_policy_path))
    root = Path(args.root) if args.root else policy.hot_spool_root
    summary = dry_run_raw_replay(
        root,
        source=args.source,
        environment=args.environment,
        data_kind=args.data_kind,
        day=date.fromisoformat(args.date),
        symbol=args.symbol,
    )
    print(json.dumps(summary.model_dump(mode="json"), sort_keys=True))
    return 1 if summary.records_invalid or summary.payload_hash_mismatches else 0


def _resolve_repo_path(value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


if __name__ == "__main__":
    raise SystemExit(main())
