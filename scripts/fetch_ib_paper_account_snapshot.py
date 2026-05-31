from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.live import (
    AccountSummaryRow,
    IbAccountSnapshotClient,
    IbPositionRow,
    build_live_snapshot,
    default_account_snapshot_path,
    fetch_and_write_account_snapshot,
)

__all__ = [
    "AccountSummaryRow",
    "IbAccountSnapshotClient",
    "IbPositionRow",
    "build_live_snapshot",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch a paper TWS account snapshot for the SOTA rebalance job.")
    parser.add_argument("--timeout-seconds", type=float, default=20.0)
    parser.add_argument("--output-path", default=None)
    parser.add_argument("--as-of", default=None, help="Optional snapshot date. Defaults to today.")
    parser.add_argument(
        "--sota-universe-only",
        action="store_true",
        help="Drop IB positions outside the SOTA all-weather ETF universe and print a warning.",
    )
    args = parser.parse_args()

    settings = AppSettings()
    result = fetch_and_write_account_snapshot(
        settings=settings,
        output_path=Path(args.output_path) if args.output_path else default_account_snapshot_path(settings),
        as_of=date.fromisoformat(args.as_of) if args.as_of else None,
        sota_universe_only=args.sota_universe_only,
        timeout_seconds=args.timeout_seconds,
    )

    print(result.output_path)
    print("managed_accounts=" + ",".join(result.managed_accounts))
    print(f"cash_balances={len(result.snapshot.cash)}")
    print(f"positions={len(result.snapshot.positions)}")
    for warning in result.warnings:
        print(f"warning: {warning}")


if __name__ == "__main__":
    main()
