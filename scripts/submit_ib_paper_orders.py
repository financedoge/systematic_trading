from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution import InteractiveBrokersOrderRouter
from systematic_trading.storage.sqlite import SQLiteStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit an approved proposal to Interactive Brokers paper trading.")
    parser.add_argument("--database", default=None)
    parser.add_argument("--proposal-id", required=True)
    parser.add_argument(
        "--environment",
        choices=[OrderEnvironment.PAPER.value, OrderEnvironment.LIVE.value],
        default=OrderEnvironment.PAPER.value,
    )
    parser.add_argument("--allow-resubmit", action="store_true")
    parser.add_argument(
        "--confirm-submit",
        action="store_true",
        help="Required to connect to IB and place orders. Without it the command validates and exits.",
    )
    args = parser.parse_args()

    settings = AppSettings()
    database_path = Path(args.database) if args.database else settings.database_path
    store = SQLiteStore(database_path)
    store.initialize()
    proposal = store.get_proposal(args.proposal_id)
    if proposal is None:
        raise SystemExit(f"Unknown proposal: {args.proposal_id}")

    environment = OrderEnvironment(args.environment)
    router = InteractiveBrokersOrderRouter(settings)
    validation_issues = router.validate_proposal_for_submission(
        proposal=proposal,
        store=store,
        environment=environment,
        allow_resubmit=args.allow_resubmit,
    )
    if validation_issues:
        print("validation_issues:")
        for issue in validation_issues:
            print(f"- {issue}")
        raise SystemExit(2)
    if not args.confirm_submit:
        print("Validation passed. Re-run with --confirm-submit to route orders to IB.")
        return

    result = router.submit_approved_proposal(
        proposal=proposal,
        store=store,
        environment=environment,
        allow_resubmit=args.allow_resubmit,
    )
    print(json.dumps(result.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    main()
