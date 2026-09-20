"""Preview or apply a reviewed execution-history repair; never connects to IB."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.execution.recovery import ExecutionRecoveryRequest, preview_execution_recovery
from systematic_trading.storage import create_transactional_store


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", required=True, type=Path, help="Reviewed recovery request JSON.")
    parser.add_argument("--database", type=Path, help="Existing SQLite file when SQLite is configured.")
    parser.add_argument("--apply", action="store_true", help="Apply exactly the preview identified by --review-token.")
    parser.add_argument("--review-token", help="Token printed by the preview command.")
    args = parser.parse_args(argv)
    if args.apply and not args.review_token:
        parser.error("--apply requires the --review-token from a reviewed preview")
    try:
        request = ExecutionRecoveryRequest.model_validate_json(args.evidence.read_text(encoding="utf-8"))
        settings = AppSettings()
        if args.database and settings.transactional_store_backend.strip().lower() != "sqlite":
            raise ValueError("--database is only valid when the transactional backend is SQLite; it cannot redirect Postgres.")
        if settings.transactional_store_backend.strip().lower() == "sqlite":
            if not (args.database or settings.database_path).is_file():
                raise ValueError("Recovery requires an existing SQLite database.")
        store = create_transactional_store(settings, database_path=args.database)
        # No initialize(): a preview must not create/upgrade a database.
        if args.apply:
            recovered = store.recover_broker_executions(request, review_token=args.review_token)
            print(recovered.execution_recoveries[-1].model_dump_json(indent=2))
        else:
            record = next((row for row in store.list_broker_order_records()
                           if row.local_order_id == request.local_order_id), None)
            if record is None:
                raise ValueError(f"Unknown local order: {request.local_order_id}")
            print(preview_execution_recovery(record, request, store.latest_pnl_baseline()).model_dump_json(indent=2))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(2, f"Recovery refused: {exc}\n")


if __name__ == "__main__":
    main()
