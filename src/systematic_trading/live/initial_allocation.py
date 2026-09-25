"""Monitor portfolio alignment and stage approval-only TWAP proposals."""
from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from hashlib import sha256
from time import monotonic
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import BrokerOrderStatus, Currency, OrderEnvironment, OrderType, ProposalStatus
from systematic_trading.domain.portfolio import CashBalance
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.execution.window import proposal_is_expired
from systematic_trading.live.sota import LiveAccountSnapshotInput, build_sota_live_rebalance_plan, write_sota_live_plan_artifacts
from systematic_trading.live.trading_calendar import next_us_trading_day, previous_us_trading_day, us_equity_market_close
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.storage.interfaces import TradingStore

NY = ZoneInfo("America/New_York")


class InitialAllocationResult(BaseModel):
    status: str
    message: str
    proposal_id: str | None = None
    artifact_path: str | None = None
    valuation_date: date | None = None
    target_as_of: date | None = None
    holdings: list[dict[str, str]] = Field(default_factory=list)


def initial_allocation_window(settings: AppSettings, now: datetime) -> tuple[date, datetime, datetime]:
    """Use only completed daily bars and the earliest full regular-session TWAP."""
    local = now.astimezone(NY)
    today = local.date()
    close_time = us_equity_market_close(today)
    decision_date = today if close_time and local.time() >= close_time else previous_us_trading_day(today)
    configured_start = time.fromisoformat(settings.execution_twap_start_time)
    configured_end = time.fromisoformat(settings.execution_twap_end_time)
    duration = datetime.combine(today, configured_end) - datetime.combine(today, configured_start)
    if duration <= timedelta(0) or duration > timedelta(hours=3, minutes=30):
        raise ValueError("Initial allocation requires a positive TWAP duration fitting an early-close session.")
    earliest = (local + timedelta(minutes=2)).replace(second=0, microsecond=0) + timedelta(minutes=1)
    start = max(datetime.combine(today, time(9, 30), NY), earliest)
    if close_time is None or start + duration > datetime.combine(today, close_time, NY):
        start = datetime.combine(next_us_trading_day(today), time(9, 30), NY)
    return decision_date, start, start + duration


def stage_initial_allocation(
    *, settings: AppSettings, store: TradingStore, now: datetime, order_client=None,
) -> InitialAllocationResult:
    return stage_portfolio_alignment(settings=settings, store=store, now=now, order_client=order_client, initial_only=True)


def stage_portfolio_alignment(
    *, settings: AppSettings, store: TradingStore, now: datetime, order_client=None, initial_only=False,
) -> InitialAllocationResult:
    from systematic_trading.execution.management import TERMINAL, sync_orders
    from systematic_trading.execution.reconciliation import load_latest_ib_reconciliation, submission_reconciliation_issues

    started = monotonic()
    if not settings.automation_queue_rebalance:
        return InitialAllocationResult(status="disabled", message="Automatic proposal staging is disabled.")
    issues = submission_reconciliation_issues(settings, now=now)
    if issues:
        return InitialAllocationResult(status="blocked", message=issues[0])
    report = load_latest_ib_reconciliation(settings)
    if report is None:
        return InitialAllocationResult(status="blocked", message="A fresh IB reconciliation is required.")
    empty = not report.broker_positions and not report.ib_position_count
    if not empty and initial_only:
        return InitialAllocationResult(status="invested", message="Portfolio has holdings; monitor drift against active strategy targets.")
    if report.ib_position_count != len(report.broker_positions):
        return InitialAllocationResult(status="blocked", message="IB position count does not match the portfolio snapshot.")
    label = "Initial allocation" if empty else "Portfolio rebalance"
    if report.warnings or len(report.managed_accounts) != 1 or not report.managed_accounts[0].startswith("DU"):
        return InitialAllocationResult(status="blocked", message=f"{label} requires one verified paper account and a warning-free portfolio snapshot.")
    cash = [CashBalance.model_validate(row) for row in report.broker_cash]
    if not cash or any(not item.amount.is_finite() or item.amount < 0 for item in cash) or (empty and not any(item.amount > 0 for item in cash)):
        return InitialAllocationResult(status="blocked", message=f"{label} requires investable assets without cash liabilities.")

    decision_date, start, end = initial_allocation_window(settings, now)
    definition = current_sota_definition()
    baseline = store.latest_pnl_baseline()
    records = [record for record in store.list_broker_order_records() if record.environment == OrderEnvironment.PAPER]
    proposals = store.list_proposals()
    # An operator portfolio reset starts a new episode; routine PnL compaction does not.
    reset = baseline.account_reset_at if baseline else None
    # New execution evidence also permits a new build after a later full liquidation.
    fill_times = [fill.filled_at for record in records for fill in record.execution_fills]
    fill_times.extend(record.submitted_at or record.updated_at for record in records
        if record.filled_quantity and not record.execution_fills)
    last_fill = max(fill_times).isoformat() if fill_times else "none"
    episode = f"{report.managed_accounts[0]}:{definition.key}:{reset or 'initial'}:{last_fill}"

    missing = [symbol for symbol in instruments_for_definition(definition)
        if not any(bar.trade_date == decision_date and bar.volume > 0
                   for bar in store.list_price_bars(symbol, start_date=decision_date, end_date=decision_date))]
    if missing:
        return InitialAllocationResult(status="blocked", message=f"{label} needs complete {decision_date} daily bars: {', '.join(sorted(missing))}.")
    currencies = {item.currency for item in cash} | {item.quote_currency for item in instruments_for_definition(definition).values()}
    missing_fx = []
    for currency in sorted(currencies - {Currency.CNH}):
        rates = store.list_fx_rates(currency, end_date=decision_date)
        if not rates or rates[-1].rate_date != decision_date:
            latest = str(rates[-1].rate_date) if rates else "none"
            missing_fx.append(f"{currency.value}/CNH (latest {latest})")
    if missing_fx:
        return InitialAllocationResult(status="blocked", message=f"{label} needs {decision_date} FX rates: {', '.join(missing_fx)}.")
    snapshot = LiveAccountSnapshotInput(as_of=decision_date, captured_at=report.checked_at, cash=cash, positions=report.broker_positions)
    target_date = decision_date if empty else latest_monthly_target_date(decision_date)
    target_source = None
    if not empty:
        sources = [p for p in proposals if p.sleeve == definition.sleeve_name and p.targets
            and p.status == ProposalStatus.APPROVED and target_date <= (p.target_as_of or p.as_of) <= decision_date
            and (reset is None or p.created_at >= reset)]
        target_source = max(sources, key=lambda p: (p.target_as_of or p.as_of, p.created_at), default=None)
    broker = InteractiveBrokersAdapter(settings)
    try:
        plan = build_sota_live_rebalance_plan(store=store, broker=broker, account_snapshot=snapshot,
            decision_date=decision_date, intended_trade_date=start.date(), environment=OrderEnvironment.PAPER,
            order_type=OrderType.TWAP, queue=False, target_decision_date=target_date, target_proposal=target_source)
    except ValueError as exc:
        return InitialAllocationResult(status="blocked", message=str(exc))
    if plan.validation_issues:
        return InitialAllocationResult(status="blocked", message="; ".join(plan.validation_issues))
    holdings = portfolio_drift(store, snapshot, plan.proposal.targets, decision_date)
    evidence = dict(valuation_date=decision_date, target_as_of=plan.proposal.target_as_of, holdings=holdings)
    threshold = settings.automation_rebalance_drift_threshold
    breached = any(abs(Decimal(row["drift"])) >= threshold and Decimal(row["drift"]) != 0 for row in holdings)
    if not plan.proposal.orders or (not empty and not breached):
        return InitialAllocationResult(status="aligned", message=f"Holdings are within the {threshold * 100:g} percentage point tolerance, or remaining differences are below one share.", **evidence)

    if not empty:
        target_key = str([(target.symbol, str(target.target_weight)) for target in sorted(plan.proposal.targets, key=lambda t: t.symbol)])
        quantities = str(sorted((p.symbol, p.quantity) for p in report.broker_positions))
        episode += f":{plan.proposal.target_as_of}:{target_key}:{quantities}"
    prefix = ("initial-" if empty else "drift-") + sha256(episode.encode()).hexdigest()[:12] + "-"
    proposal_id = prefix + start.strftime("%Y%m%d")
    for proposal in proposals:
        if proposal.proposal_id.startswith(prefix) and proposal.status in {ProposalStatus.APPROVED, ProposalStatus.REJECTED}:
            return InitialAllocationResult(status="review", proposal_id=proposal.proposal_id,
                message=f"{label} {proposal.proposal_id} is {proposal.status.value}; manage that decision before building again.", **evidence)
        historical_approval = False
        if (baseline is not None and proposal.status == ProposalStatus.APPROVED
                and proposal.intended_trade_date is None and proposal.created_at <= baseline.cutoff_at):
            attempts = [record for record in records if record.proposal_id == proposal.proposal_id]
            historical_approval = ({record.order_index for record in attempts} == set(range(len(proposal.orders)))
                and all((record.submitted_at or record.updated_at) <= baseline.cutoff_at for record in attempts))
        if not historical_approval and proposal.status in {ProposalStatus.PENDING, ProposalStatus.APPROVED} and not proposal_is_expired(proposal, settings, now=now):
            return InitialAllocationResult(status="pending", proposal_id=proposal.proposal_id,
                message=f"Proposal {proposal.proposal_id} is already awaiting approval or execution.", **evidence)
        if proposal.proposal_id == proposal_id:
            return InitialAllocationResult(status="review", proposal_id=proposal_id,
                message="Today's rebalance window has expired; no duplicate will be created for this session.", **evidence)
        if not empty and proposal.sleeve == definition.sleeve_name and proposal.status == ProposalStatus.REJECTED and proposal.trigger == "scheduled_rebalance" and (proposal.target_as_of or proposal.as_of) == plan.proposal.target_as_of:
            return InitialAllocationResult(status="review", proposal_id=proposal.proposal_id,
                message="The current monthly target proposal was rejected; review that decision before rebalancing.", **evidence)

    cutoff = baseline.cutoff_at if baseline else None
    active = {BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.ACKNOWLEDGED, BrokerOrderStatus.PARTIALLY_FILLED}
    for record in records:
        if record.pending_action or record.execution_sync_issue or record.status == BrokerOrderStatus.PENDING_SUBMIT:
            return InitialAllocationResult(status="blocked", message="Resolve the pending or uncertain local order before rebalancing.", **evidence)
        # History covered by the reconciled baseline remains intact, not falsely cancelled.
        in_current_ledger = cutoff is None or (record.submitted_at or record.updated_at) > cutoff
        if in_current_ledger and record.status in active:
            return InitialAllocationResult(status="blocked", message="An existing local order is still working or unconfirmed.", **evidence)

    broker_snapshot = sync_orders(settings, store, client=order_client)
    if any(row.get("status") not in TERMINAL for row in broker_snapshot["orders"]):
        return InitialAllocationResult(status="blocked", message="IB reports an open or uncertain order; rebalancing will wait.", **evidence)
    # Reading prices and broker orders can take time. Never stage against an expired snapshot.
    checked_now = now + timedelta(seconds=monotonic() - started)
    issues = submission_reconciliation_issues(settings, now=checked_now)
    if issues or checked_now >= end.astimezone(UTC):
        return InitialAllocationResult(status="blocked", message=issues[0] if issues else "The TWAP window elapsed during validation; retry with fresh state.")
    fresh = load_latest_ib_reconciliation(settings)
    if fresh is None or (fresh.broker_cash, fresh.broker_positions, fresh.managed_accounts) != (report.broker_cash, report.broker_positions, report.managed_accounts):
        return InitialAllocationResult(status="blocked", message="IB portfolio changed during validation; retry with the new snapshot.", **evidence)
    proposal = plan.proposal.model_copy(update={
        "proposal_id": proposal_id, "created_at": now, "trigger": "empty_portfolio" if empty else "portfolio_drift",
        "automation_strategy_key": definition.key,
        "execution_deadline_at": min(end, start + timedelta(minutes=max(settings.execution_rebalance_timeout_minutes, 0))).astimezone(UTC),
        "summary": f"{label}. " + plan.proposal.summary,
        "orders": [order.model_copy(update={"execution_start_time": start.strftime("%H:%M"),
            "execution_end_time": end.strftime("%H:%M")}) for order in plan.proposal.orders],
        "reasoning": plan.proposal.reasoning.model_copy(update={
            "drivers": ["Fresh reconciliation confirms an empty paper portfolio." if empty else f"A holding differs from its active target by at least {threshold * 100:g} percentage points.",
                f"TWAP {start:%Y-%m-%d %H:%M}–{end:%H:%M} America/New_York; explicit approval is required.",
                *plan.proposal.reasoning.drivers],
        }),
    })
    saved = store.queue_proposal_once(proposal)
    plan = plan.model_copy(update={"proposal": saved, "queued": True})
    json_path, _ = write_sota_live_plan_artifacts(plan, settings.data_dir / "live" / "sota_rebalance")
    return InitialAllocationResult(status="queued", proposal_id=saved.proposal_id, artifact_path=str(json_path),
        message=f"{label} staged for approval: {start:%Y-%m-%d %H:%M}–{end:%H:%M} New York time, using {decision_date} data.", **evidence)


def latest_monthly_target_date(as_of: date) -> date:
    if current_sota_definition().scheduler != "static_monthly":
        raise ValueError("Portfolio drift monitoring requires an explicit target policy for this scheduler.")
    candidate = as_of
    while us_equity_market_close(candidate) is None or next_us_trading_day(candidate).month == candidate.month:
        candidate -= timedelta(days=1)
    return candidate


def portfolio_drift(store, snapshot, targets, as_of):
    instruments = instruments_for_definition(current_sota_definition())
    quantities = {p.symbol: p.quantity for p in snapshot.positions}
    weights = {t.symbol: t.target_weight for t in targets}
    symbols = sorted(quantities.keys() | weights.keys())
    fx = {Currency.CNH: Decimal(1)}
    for currency in {b.currency for b in snapshot.cash} | {instruments[s].quote_currency for s in symbols}:
        if currency != Currency.CNH:
            fx[currency] = store.list_fx_rates(currency, end_date=as_of)[-1].rate
    values = {symbol: Decimal(quantities.get(symbol, 0)) * store.list_price_bars(symbol, end_date=as_of)[-1].close
        * fx[instruments[symbol].quote_currency] for symbol in symbols}
    nav = sum(values.values()) + sum(b.amount * fx[b.currency] for b in snapshot.cash)
    if nav <= 0:
        raise ValueError("Portfolio must have positive NAV to evaluate target drift.")
    return [dict(symbol=symbol, quantity=str(quantities.get(symbol, 0)), actual_weight=str(values[symbol] / nav),
        target_weight=str(weights.get(symbol, Decimal(0))), drift=str(values[symbol] / nav - weights.get(symbol, Decimal(0))))
        for symbol in symbols]
