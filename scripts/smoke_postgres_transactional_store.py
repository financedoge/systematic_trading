from __future__ import annotations

import argparse
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systematic_trading.config import AppSettings  # noqa: E402
from systematic_trading.domain import (  # noqa: E402
    ApprovalDecision,
    AssetClass,
    BrokerOrderRecord,
    BrokerOrderStatus,
    Currency,
    Exchange,
    FundamentalSnapshot,
    Instrument,
    OrderRequest,
    OrderSide,
    OrderType,
    PnLBaseline,
    PnLSnapshot,
    ProposalReasoning,
    ProposalStatus,
    ThesisMemo,
    TradeProposal,
)
from systematic_trading.storage import create_transactional_store  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test the Postgres transactional store adapter.")
    parser.add_argument("--keep-records", action="store_true", help="Leave smoke rows in Postgres for inspection.")
    args = parser.parse_args()

    settings = AppSettings(transactional_store_backend="postgres")
    store = create_transactional_store(settings)
    store.initialize()

    smoke_id = f"pgsmoke{uuid4().hex[:8]}"
    symbol = "STSMOKE"
    proposal_id = f"{smoke_id}-proposal"
    local_order_id = f"{smoke_id}-order"

    instrument = Instrument(
        symbol=symbol,
        name="Postgres Smoke Instrument",
        asset_class=AssetClass.ETF,
        exchange=Exchange.OTHER,
        quote_currency=Currency.USD,
        country="US",
        sector="Smoke",
    )
    thesis = ThesisMemo(
        symbol=symbol,
        summary="Postgres transactional smoke.",
        valuation_case="Synthetic adapter test.",
        catalyst_window="Immediate.",
        hold_horizon_months=1,
    )
    fundamental = FundamentalSnapshot(
        symbol=symbol,
        period_end=date(2026, 6, 30),
        filing_date=date(2026, 7, 1),
        available_date=date(2026, 7, 2),
        source="smoke",
        revenue_growth_yoy=Decimal("0.01"),
    )
    order = OrderRequest(
        symbol=symbol,
        side=OrderSide.BUY,
        order_type=OrderType.TWAP,
        quantity=10,
        reference_price=Decimal("10.00"),
        currency=Currency.USD,
        notional_cnh=Decimal("680.00"),
        rationale="Adapter smoke order.",
    )
    proposal = TradeProposal(
        proposal_id=proposal_id,
        created_at=datetime(2026, 7, 11, 1, 0, tzinfo=UTC),
        as_of=date(2026, 7, 10),
        intended_trade_date=date(2026, 7, 13),
        sleeve="postgres-smoke",
        summary="Postgres smoke proposal.",
        orders=[order],
        reasoning=ProposalReasoning(summary="Smoke test."),
    )
    decision = ApprovalDecision(
        proposal_id=proposal_id,
        status=ProposalStatus.APPROVED,
        decided_at=datetime(2026, 7, 11, 1, 5, tzinfo=UTC),
        comment="Smoke approval.",
    )
    broker_record = BrokerOrderRecord(
        local_order_id=local_order_id,
        proposal_id=proposal_id,
        order_index=0,
        order=order,
        order_ref=f"st-{proposal_id}-00",
        broker_order_id=987654,
        status=BrokerOrderStatus.FILLED,
        submitted_at=datetime(2026, 7, 11, 1, 10, tzinfo=UTC),
        updated_at=datetime(2026, 7, 11, 1, 20, tzinfo=UTC),
        filled_quantity=10,
        remaining_quantity=0,
        average_fill_price=Decimal("10.05"),
    )
    baseline = PnLBaseline(
        baseline_id=f"{smoke_id}-baseline",
        cutoff_at=datetime(2026, 7, 11, 1, 30, tzinfo=UTC),
    )
    snapshot = PnLSnapshot(
        snapshot_id=f"{smoke_id}-snapshot",
        as_of=datetime(2026, 7, 11, 1, 35, tzinfo=UTC),
        baseline_id=baseline.baseline_id,
        total_pnl_cnh=Decimal("1.23"),
    )

    store.upsert_instrument(instrument)
    store.upsert_thesis(thesis)
    store.upsert_fundamental_snapshot(fundamental)
    store.save_proposal(proposal)
    approved = store.apply_decision(decision)
    store.save_broker_order_record(broker_record)
    store.save_pnl_baseline(baseline)
    store.save_pnl_snapshot(snapshot)

    pending = store.list_pending_platform_events(limit=20)
    records = store.list_broker_order_records(proposal_id=proposal_id)
    latest_baseline = store.latest_pnl_baseline()
    latest_fundamental = store.latest_fundamental_snapshot(symbol, as_of=date(2026, 7, 11))

    print(f"smoke_id={smoke_id}")
    print(f"proposal_status={approved.status.value}")
    print(f"broker_records={len(records)}")
    print(f"pending_events={len(pending)}")
    print(f"latest_baseline_id={latest_baseline.baseline_id if latest_baseline else ''}")
    print(f"latest_fundamental_symbol={latest_fundamental.symbol if latest_fundamental else ''}")

    if not args.keep_records:
        _cleanup(settings, symbol=symbol, proposal_id=proposal_id, local_order_id=local_order_id, smoke_id=smoke_id)
        print("cleanup=done")
    else:
        print("cleanup=skipped")
    return 0


def _cleanup(
    settings: AppSettings,
    *,
    symbol: str,
    proposal_id: str,
    local_order_id: str,
    smoke_id: str,
) -> None:
    store = create_transactional_store(settings)
    with store._connect() as connection:
        connection.execute("DELETE FROM execution.fills WHERE local_order_id = %s", (local_order_id,))
        connection.execute(
            "DELETE FROM execution.broker_order_status_history WHERE local_order_id = %s",
            (local_order_id,),
        )
        connection.execute("DELETE FROM execution.broker_orders WHERE local_order_id = %s", (local_order_id,))
        connection.execute("DELETE FROM portfolio.approval_decisions WHERE proposal_id = %s", (proposal_id,))
        connection.execute("DELETE FROM portfolio.proposal_orders WHERE proposal_id = %s", (proposal_id,))
        connection.execute("DELETE FROM portfolio.proposal_targets WHERE proposal_id = %s", (proposal_id,))
        connection.execute("DELETE FROM portfolio.proposals WHERE proposal_id = %s", (proposal_id,))
        connection.execute("DELETE FROM portfolio.pnl_snapshots WHERE snapshot_id = %s", (f"{smoke_id}-snapshot",))
        connection.execute("DELETE FROM portfolio.pnl_baselines WHERE baseline_id = %s", (f"{smoke_id}-baseline",))
        connection.execute("DELETE FROM core.fundamental_snapshots WHERE symbol = %s", (symbol,))
        connection.execute("DELETE FROM core.theses WHERE symbol = %s", (symbol,))
        connection.execute("DELETE FROM core.instruments WHERE symbol = %s", (symbol,))
        connection.execute(
            "DELETE FROM events.platform_event_outbox WHERE event_id LIKE %s",
            (f"%{smoke_id}%",),
        )


if __name__ == "__main__":
    raise SystemExit(main())
