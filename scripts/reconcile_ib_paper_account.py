from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systematic_trading.config import AppSettings  # noqa: E402
from systematic_trading.execution.reconciliation import reconcile_ib_paper_account  # noqa: E402
from systematic_trading.storage import create_trading_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile local paper order records against IB paper account state.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for the JSON reconciliation report. Defaults to ST_DATA_DIR/reconciliation.",
    )
    parser.add_argument(
        "--record-pnl-reset-baseline",
        action="store_true",
        help="Write an empty PnL baseline when the fetched IB paper account has zero positions.",
    )
    parser.add_argument(
        "--confirm-paper-reset",
        action="store_true",
        help="Required with --record-pnl-reset-baseline. Confirms the operator intentionally reset the IB paper account.",
    )
    args = parser.parse_args()

    settings = AppSettings(transactional_store_backend="postgres", market_data_store_backend="clickhouse")
    store = create_trading_store(settings)
    store.initialize()
    report = reconcile_ib_paper_account(
        settings=settings,
        store=store,
        record_pnl_reset_baseline=args.record_pnl_reset_baseline,
        confirm_paper_reset=args.confirm_paper_reset,
    )
    output_dir = args.output_dir or settings.data_dir / "reconciliation"
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"ib_paper_reconciliation_{stamp}.json"
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")

    print(f"report={output_path}")
    print(f"has_breaks={str(report.has_breaks).lower()}")
    print(f"local_filled_order_count={report.local_filled_order_count}")
    print(f"ib_fill_count={report.ib_fill_count}")
    print(f"ib_position_count={report.ib_position_count}")
    print(f"unmatched_local_orders={len(report.unmatched_local_orders)}")
    print(f"unmatched_ib_fills={len(report.unmatched_ib_fills)}")
    print(f"position_differences={len(report.position_differences)}")
    if report.pnl_reset_baseline_id:
        print(f"pnl_reset_baseline_id={report.pnl_reset_baseline_id}")
    for action in report.suggested_actions:
        print(f"suggested_action={action}")
    return 1 if report.has_breaks else 0


if __name__ == "__main__":
    raise SystemExit(main())
