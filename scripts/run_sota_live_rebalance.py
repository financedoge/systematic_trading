from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment, OrderType
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.live import (
    build_sota_live_rebalance_plan,
    load_account_snapshot,
    write_sota_live_plan_artifacts,
)
from systematic_trading.storage.sqlite import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate the current SOTA overnight rebalance plan and optional paper proposal queue entry."
    )
    parser.add_argument("--database", default=None)
    parser.add_argument("--account-snapshot", required=True, help="JSON file with cash and current positions.")
    parser.add_argument("--as-of", default=None, help="Decision date. Defaults to the latest stored SOTA price date.")
    parser.add_argument("--intended-trade-date", default=None, help="Planned order date. Defaults to the next weekday.")
    parser.add_argument("--output-dir", default="var/live/sota_rebalance")
    parser.add_argument("--queue", action="store_true", help="Persist the generated proposal to the approval queue.")
    parser.add_argument("--environment", choices=[item.value for item in OrderEnvironment], default=OrderEnvironment.PAPER.value)
    parser.add_argument("--order-type", choices=[item.value for item in OrderType], default=OrderType.TWAP.value)
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    store = SQLiteStore(database_path)
    store.initialize()
    broker = InteractiveBrokersAdapter(settings)
    account_snapshot = load_account_snapshot(Path(args.account_snapshot))
    plan = build_sota_live_rebalance_plan(
        store=store,
        broker=broker,
        account_snapshot=account_snapshot,
        decision_date=date.fromisoformat(args.as_of) if args.as_of else None,
        intended_trade_date=date.fromisoformat(args.intended_trade_date) if args.intended_trade_date else None,
        environment=OrderEnvironment(args.environment),
        order_type=OrderType(args.order_type),
        queue=args.queue,
    )
    json_path, markdown_path = write_sota_live_plan_artifacts(plan, Path(args.output_dir))
    print(json_path)
    print(markdown_path)
    if plan.validation_issues:
        print("validation_issues:")
        for issue in plan.validation_issues:
            print(f"- {issue}")


if __name__ == "__main__":
    main()
