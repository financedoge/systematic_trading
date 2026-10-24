"""Opt-in, audited paper approval policy; every attempt remains a normal proposal."""
from __future__ import annotations

import platform
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from time import monotonic

from pydantic import AwareDatetime, BaseModel, Field

from systematic_trading.domain.enums import BrokerOrderStatus, OrderEnvironment, OrderType, ProposalStatus
from systematic_trading.domain.execution import ApprovalDecision
from systematic_trading.domain.events import EventSeverity, EventSource, IncidentRecordedEvent, IncidentRecordedPayload, IncidentStatus
from systematic_trading.domain.portfolio import CashBalance
from systematic_trading.execution.broker import InteractiveBrokersAdapter, InteractiveBrokersOrderRouter
from systematic_trading.execution.locks import ORDER_CONNECTION_LOCK
from systematic_trading.execution.twap_benchmark import benchmark_window
from systematic_trading.execution.window import proposal_is_expired
from systematic_trading.live.initial_allocation import NY
from systematic_trading.live.sota import LiveAccountSnapshotInput, build_sota_live_rebalance_plan
from systematic_trading.live.trading_calendar import previous_us_trading_day, us_equity_market_close
from systematic_trading.research import instruments_for_definition
from systematic_trading.portfolio.strategy_allocation import trading_definition


class PaperApprovalPolicy(BaseModel):
    enabled: bool = False
    revision: int = 0
    enabled_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None
    operator: str = ""
    reason: str = ""
    account: str = ""
    binding: str = ""
    strategy_key: str = ""
    max_batch_notional_cnh: Decimal = Field(default=Decimal("1000000"), gt=0, allow_inf_nan=False)
    attempts: dict[str, dict] = Field(default_factory=dict)
    renewals: dict[str, dict] = Field(default_factory=dict)
    history: list[dict] = Field(default_factory=list)
    message: str = "Manual approval. Automatic paper routing is off."


class PaperApprovalUpdate(BaseModel):
    enabled: bool
    expected_revision: int = Field(ge=0)
    confirm: bool = False
    operator: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=1, max_length=500)
    max_batch_notional_cnh: Decimal = Field(default=Decimal("1000000"), gt=0, allow_inf_nan=False)


class PaperAutoApproval:
    RENEWAL_RETRY_SECONDS = 300

    def __init__(self, settings, store, *, order_client=None, router=None):
        self.settings, self.store = settings, store
        self.order_client = order_client
        self.router = router or InteractiveBrokersOrderRouter(settings)
        self.path = settings.data_dir / "live" / "paper_auto_approval.json"
        self._renewal_retry_at: dict[str, datetime] = {}
        self.policy = PaperApprovalPolicy()
        if self.path.exists():
            try:
                self.policy = PaperApprovalPolicy.model_validate_json(self.path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                self.policy.message = "Unreadable approval policy; automatic routing is off."
        if self.policy.enabled and (self.policy.binding != self._binding() or
                self.policy.strategy_key != trading_definition(self.store).key or not self.policy.enabled_at):
            self.policy.enabled = False
            self.policy.message = "Machine, broker profile or strategy changed. Enable paper automation again after review."

    def _binding(self):
        profile = InteractiveBrokersAdapter(self.settings).profile_for(OrderEnvironment.PAPER)
        return f"{platform.node()}:{self.path.resolve()}:{self.settings.default_environment.value}:{profile.host}:{profile.port}:{profile.client_id}"

    def status(self):
        with ORDER_CONNECTION_LOCK:
            return self.policy.model_copy(deep=True)

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(self.policy.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(self.path)

    def _account(self, now):
        from systematic_trading.execution.reconciliation import load_latest_ib_reconciliation, submission_reconciliation_issues
        issues = submission_reconciliation_issues(self.settings, now=now)
        report = load_latest_ib_reconciliation(self.settings)
        if issues or report is None:
            raise ValueError("; ".join(issues) or "Fresh matched reconciliation required.")
        if report.warnings or len(report.managed_accounts) != 1 or not report.managed_accounts[0].startswith("DU"):
            raise ValueError("One verified paper account and a warning-free snapshot are required.")
        if report.ib_position_count != len(report.broker_positions):
            raise ValueError("Incomplete portfolio snapshot.")
        return report

    def configure(self, change: PaperApprovalUpdate, *, now=None):
        now = now or datetime.now(UTC)
        with ORDER_CONNECTION_LOCK:
            if change.expected_revision != self.policy.revision:
                raise ValueError("Approval policy changed. Refresh and review the current settings.")
            if not change.operator.strip() or not change.reason.strip():
                raise ValueError("Operator and reason are required.")
            account = self.policy.account
            if change.enabled:
                if not change.confirm:
                    raise ValueError("Confirm automatic approval AND submission of new paper TWAP proposals.")
                if not self.settings.automation_enabled or self.settings.default_environment != OrderEnvironment.PAPER:
                    raise ValueError("The paper trading management service must be enabled.")
                if not InteractiveBrokersAdapter(self.settings).profile_for(OrderEnvironment.PAPER).enabled:
                    raise ValueError("Paper broker profile is disabled.")
                account = self._account(now).managed_accounts[0]
            audit = dict(at=now.isoformat(), enabled=change.enabled, operator=change.operator.strip(),
                         reason=change.reason.strip(), max_batch_notional_cnh=str(change.max_batch_notional_cnh),
                         account=account, revision=self.policy.revision + 1)
            event = IncidentRecordedEvent(source=EventSource(service="paper-auto-approval", environment=OrderEnvironment.PAPER),
                payload=IncidentRecordedPayload(status=IncidentStatus.RESOLVED, severity=EventSeverity.INFO,
                    summary="Paper automatic approval enabled" if change.enabled else "Manual paper approval restored",
                    details=audit, resolved_at=now))
            # A failed audit must never turn routing on. Turning it off is fail-safe.
            if change.enabled:
                self.store.append_platform_event(event)
            updated = self.policy.model_copy(update=dict(enabled=change.enabled, revision=self.policy.revision + 1,
                enabled_at=now if change.enabled else None, updated_at=now, operator=change.operator.strip(),
                reason=change.reason.strip(), account=account, binding=self._binding(),
                strategy_key=trading_definition(self.store).key, max_batch_notional_cnh=change.max_batch_notional_cnh,
                history=[*self.policy.history, audit], message="Waiting for eligible strategy proposals and outstanding rebalance recovery." if change.enabled
                else "Manual approval. Existing broker orders continue; no new automatic submissions."))
            previous, self.policy = self.policy, updated
            try:
                self._save()
            except Exception:
                self.policy = previous.model_copy(update={"enabled": False})
                raise
            if not change.enabled:
                self.store.append_platform_event(event)
            return self.status()

    def invalidate_stale_binding(self):
        """Disable obsolete authority without running any approval or order path."""
        with ORDER_CONNECTION_LOCK:
            if self.policy.enabled and (self.policy.binding != self._binding()
                    or self.policy.strategy_key != trading_definition(self.store).key):
                self.policy.enabled = False
                self.policy.message = "Configuration changed; automatic routing disabled."
                self._save()

    def tick(self, *, now=None):
        now = now or datetime.now(UTC)
        with ORDER_CONNECTION_LOCK:
            self.invalidate_stale_binding()
            from systematic_trading.execution.window import expire_due_proposals
            from systematic_trading.portfolio.rebalance_intents import sync_intents, route_issues, record_intent
            expire_due_proposals(self.store, self.settings, now=now)
            sync_intents(self.store, now=now)
            if not self.policy.enabled:
                return
            # A policy bound to the active allocation may renew one expired
            # application-prepared rebalance into a fresh window. The successor
            # still passes every normal approval and broker check below.
            self._renew_missed_rebalance(now)
            for proposal in sorted(self.store.list_proposals(ProposalStatus.PENDING), key=lambda p: p.created_at):
                if (proposal.created_at < self.policy.enabled_at or proposal.created_at > now or
                        proposal.automation_strategy_key != self.policy.strategy_key or
                        proposal.proposal_id in self.policy.attempts):
                    continue
                started = monotonic()
                try:
                    if route_issues(self.store, proposal):
                        continue
                    if not self._preflight(proposal, now):
                        continue
                    checked = now + timedelta(seconds=monotonic() - started)
                    self._account(checked)
                    if proposal_is_expired(proposal, self.settings, now=checked):
                        raise ValueError("Execution window elapsed during validation.")
                    # The phase distinguishes a conclusively unsubmitted claim from
                    # legacy/unknown router outcomes. Real orders reserve before send.
                    self.policy.attempts[proposal.proposal_id] = dict(at=checked.isoformat(), outcome="claimed",
                        phase='before_router')
                    self._save()
                    approved = self.store.apply_decision(ApprovalDecision(proposal_id=proposal.proposal_id,
                        status=ProposalStatus.APPROVED, comment=f"Automatic paper policy revision {self.policy.revision}; enabled by {self.policy.operator}."),
                        expected_status=ProposalStatus.PENDING)
                    if not approved.orders:
                        self.policy.attempts[proposal.proposal_id].update(outcome='internal_transfer_approved')
                        self.policy.message = f'{proposal.proposal_id}: virtual capital transfer approved; no broker order needed.'
                        self._save()
                        return
                    self.policy.attempts[proposal.proposal_id].update(phase='router_entered',
                        reserve_before_send=type(self.router) is InteractiveBrokersOrderRouter)
                    self._save()
                    result = self.router.submit_approved_proposal(proposal=approved, store=self.store,
                        environment=OrderEnvironment.PAPER, allow_resubmit=False)
                    complete = (not result.validation_issues and len(result.records) == len(proposal.orders) and
                        all(r.status in {BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.ACKNOWLEDGED, BrokerOrderStatus.FILLED}
                            for r in result.records))
                    self.policy.attempts[proposal.proposal_id].update(outcome="submitted" if complete else "review",
                        issues=result.validation_issues, records=[r.local_order_id for r in result.records])
                    self.policy.message = f"{proposal.proposal_id}: " + ("paper TWAP orders submitted." if complete
                        else "submission needs manual review; no automatic retry.")
                    self._save()
                except Exception as exc:
                    self.policy.message = f"{proposal.proposal_id}: {exc}"
                    if proposal.proposal_id in self.policy.attempts:
                        self.policy.attempts[proposal.proposal_id].update(outcome="review", error=str(exc))
                    record_intent(self.store, proposal, now=now, reason=str(exc),
                        next_retry_condition='Fresh reconciled account, complete prices/FX and a new eligible execution window.')
                    self._save()
                # Validation failures cannot starve later candidates. Once a claim
                # exists, wait for reconciliation before considering another batch.
                if proposal.proposal_id in self.policy.attempts:
                    return

    def _renew_missed_rebalance(self, now):
        """Recover the newest outstanding objective under the bound paper policy.

        Expired or stale attempts get fresh residual sizing, lineage and approval.
        Known working/uncertain orders, cancellations, supersession and limited
        catch-up authority cannot be bypassed by renewing a window.
        """
        from systematic_trading.execution.window import expire_due_proposals, proposal_is_expired
        from systematic_trading.live.deferred_rebalance import refresh_rebalance, unresolved_submission_claim
        from systematic_trading.portfolio.rebalance_intents import latest_rebalance, intent_state, CLOSED, record_intent

        definition = trading_definition(self.store)
        if definition.key != self.policy.strategy_key:
            return None

        try:
            source = latest_rebalance(self.store)
        except ValueError as exc:
            self.policy.message = str(exc)
            self._save()
            return None
        if source is None:
            return None
        if source.created_at > now:
            self.policy.message = f'{source.proposal_id}: future-dated proposal requires clock/creation-time review.'
            self._save()
            return None
        # Mark pending/approved windows that have elapsed as missed first, so the
        # durable missed-order audit exists before any renewal is created.
        if source.status in {ProposalStatus.PENDING, ProposalStatus.APPROVED} and proposal_is_expired(source, self.settings, now=now):
            expire_due_proposals(self.store, self.settings, now=now)
            source = self.store.get_proposal(source.proposal_id)
        candidates = [source]
        for source in candidates:
            if intent_state(self.store, source).get('status') in CLOSED:
                continue
            if source.status not in {ProposalStatus.MISSED, ProposalStatus.PENDING, ProposalStatus.APPROVED}:
                continue
            from systematic_trading.live.initial_allocation import initial_allocation_window
            valuation_day, _, _ = initial_allocation_window(self.settings, now)
            attempt = self.policy.attempts.get(source.proposal_id, {})
            safely_unsubmitted = attempt.get('phase') == 'before_router' or attempt.get('reserve_before_send') is True
            if not proposal_is_expired(source, self.settings, now=now) and not (
                    source.status == ProposalStatus.PENDING and source.as_of < valuation_day) and not (
                    attempt.get('outcome') in {'claimed', 'review'} and safely_unsubmitted):
                continue
            if source.input_provenance.get('late_handover'):
                # Operator catch-up authorization is explicitly session-limited.
                continue
            if unresolved_submission_claim(self.store, source, attempt):
                message = 'Legacy or uncertain submission claim requires reconciliation and operator review.'
                record_intent(self.store, source, now=now, reason=message, next_retry_condition=message)
                self.policy.message = f'{source.proposal_id}: {message}'
                self._save()
                continue
            previous = self.policy.renewals.get(source.proposal_id)
            if previous and previous.get('outcome') == 'renewed':
                continue
            retry_at = self._renewal_retry_at.get(source.proposal_id)
            if retry_at is None and previous and previous.get('next_retry_at'):
                retry_at = datetime.fromisoformat(previous['next_retry_at'])
            if retry_at is not None and now < retry_at:
                continue
            try:
                renewed = refresh_rebalance(
                    self.settings, self.store, source.proposal_id, now=now,
                    automation_strategy_key=self.policy.strategy_key,
                    automation_policy_revision=self.policy.revision, order_client=self.order_client)
            except (ValueError, OSError) as exc:
                self._renewal_retry_at[source.proposal_id] = now + timedelta(
                    seconds=self.RENEWAL_RETRY_SECONDS)
                self.policy.renewals[source.proposal_id] = dict(
                    at=now.isoformat(), outcome='blocked', source_status=source.status.value,
                    error=str(exc), next_retry_at=self._renewal_retry_at[source.proposal_id].isoformat())
                record_intent(self.store, source, now=now, reason=str(exc),
                    next_retry_condition='Retry after cooldown with fresh reconciliation, terminal orders and complete prices/FX.')
                self.policy.message = (f'{source.proposal_id}: automatic rebalance renewal is '
                    f'blocked: {exc}')
                self._save()
                return None
            self._renewal_retry_at.pop(source.proposal_id, None)
            if intent_state(self.store, renewed).get('status') == 'completed':
                self.policy.renewals[source.proposal_id] = dict(at=now.isoformat(), outcome='completed',
                    source_status=source.status.value, proposal_id=renewed.proposal_id)
                self.policy.message = f'{source.proposal_id}: reconciled objective completed; no residual order needed.'
                self._save()
                return renewed
            self.policy.renewals[source.proposal_id] = dict(
                at=now.isoformat(), outcome='renewed', source_status=source.status.value,
                source_intended_trade_date=str(source.intended_trade_date),
                proposal_id=renewed.proposal_id, new_intended_trade_date=str(renewed.intended_trade_date),
                policy_revision=self.policy.revision)
            self.policy.message = (f'{source.proposal_id}: missed paper rebalance renewed as '
                f'{renewed.proposal_id}; awaiting its TWAP window.')
            record_intent(self.store, renewed, now=now, reason='Fresh residual proposal awaits approval and its TWAP window.',
                next_retry_condition=f'TWAP session {renewed.intended_trade_date}; ordinary policy and broker preflight.')
            self._save()
            return renewed
        return None

    def _preflight(self, proposal, now):
        from systematic_trading.execution.management import TERMINAL, sync_orders
        from systematic_trading.execution.reconciliation import load_latest_ib_reconciliation
        definition = trading_definition(self.store)
        if not proposal.orders:
            from systematic_trading.live.allocated_plan import validate_internal_proposal
            validate_internal_proposal(self.settings, self.store, proposal, now)
            return True
        if proposal.sleeve != definition.sleeve_name or proposal.trigger not in {"empty_portfolio", "portfolio_drift", "scheduled_rebalance", "deferred_rebalance"}:
            raise ValueError("Proposal is outside the enabled strategy policy.")
        today = now.astimezone(NY).date()
        if proposal.intended_trade_date and proposal.intended_trade_date > today:
            return False
        if proposal.intended_trade_date != today or not us_equity_market_close(today) or proposal_is_expired(proposal, self.settings, now=now):
            raise ValueError("Proposal requires a current, unexpired US trading session.")
        if proposal.as_of != previous_us_trading_day(today):
            raise ValueError("Proposal must use the latest completed trading day's prices and FX.")
        if not proposal.orders or any(o.order_type != OrderType.TWAP or o.environment != OrderEnvironment.PAPER for o in proposal.orders):
            raise ValueError("Only paper TWAP batches are eligible.")
        from types import SimpleNamespace
        windows = [benchmark_window(SimpleNamespace(order=o)) for o in proposal.orders]
        if len(set(windows)) != 1 or any(o.intended_trade_date != today for o in proposal.orders):
            raise ValueError("Orders require one explicit TWAP session window.")
        start, end = windows[0]
        local_start, local_end = start.astimezone(NY), end.astimezone(NY)
        if local_start.strftime("%H:%M") < "09:30" or local_end.time() > us_equity_market_close(today):
            raise ValueError("TWAP must fit the regular market session.")
        if now < start:
            self.policy.message = f"{proposal.proposal_id}: waiting for the TWAP start {start.isoformat()}."
            return False
        if now >= end:
            raise ValueError("TWAP window has ended.")
        if sum(o.notional_cnh for o in proposal.orders) > self.policy.max_batch_notional_cnh:
            raise ValueError("Gross batch notional exceeds the operator's CNH cap.")
        if not proposal.targets or any(t.target_weight < 0 or t.target_weight > Decimal("0.45") for t in proposal.targets) or sum(t.target_weight for t in proposal.targets) > 1:
            raise ValueError("Strategy allocation limits failed.")
        if self.store.list_broker_order_records(proposal.proposal_id):
            raise ValueError("This proposal already has a broker attempt; review manually.")
        report = self._account(now)
        if report.managed_accounts != [self.policy.account]:
            raise ValueError("Paper account differs from the enabled policy.")
        cash = [CashBalance.model_validate(row) for row in report.broker_cash]
        if not cash or any(not b.amount.is_finite() or b.amount < 0 for b in cash):
            raise ValueError("Cash liabilities or missing cash require manual review.")
        instruments = instruments_for_definition(definition)
        for symbol in instruments:
            bars = self.store.list_price_bars(symbol, start_date=proposal.as_of, end_date=proposal.as_of)
            if not bars or bars[-1].volume <= 0 or bars[-1].close <= 0:
                raise ValueError(f"Missing complete daily market data for {symbol}.")
        snapshot = LiveAccountSnapshotInput(as_of=proposal.as_of, captured_at=report.checked_at, cash=cash, positions=report.broker_positions)
        plan = build_sota_live_rebalance_plan(store=self.store, broker=InteractiveBrokersAdapter(self.settings),
            account_snapshot=snapshot, decision_date=proposal.as_of, intended_trade_date=today,
            target_proposal=proposal, queue=False, reuse_proposal_intent=True)
        terms = lambda p: sorted((o.symbol, o.side, o.quantity, o.reference_price, o.currency, o.notional_cnh) for o in p.orders)
        if plan.validation_issues or terms(plan.proposal) != terms(proposal):
            raise ValueError("Portfolio, prices or order quantities changed; review the proposal manually.")
        baseline = self.store.latest_pnl_baseline()
        cutoff = baseline.cutoff_at if baseline else None
        for record in self.store.list_broker_order_records():
            if record.environment != OrderEnvironment.PAPER:
                continue
            if record.pending_action or record.execution_sync_issue or record.status == BrokerOrderStatus.PENDING_SUBMIT:
                raise ValueError("Resolve uncertain orders or execution history first.")
            if (cutoff is None or (record.submitted_at or record.updated_at) > cutoff) and record.status in {
                    BrokerOrderStatus.SUBMITTED, BrokerOrderStatus.ACKNOWLEDGED, BrokerOrderStatus.PARTIALLY_FILLED}:
                raise ValueError("A local order is still working or unconfirmed.")
        broker = sync_orders(self.settings, self.store, client=self.order_client)
        if any(row.get("status") not in TERMINAL for row in broker["orders"]):
            raise ValueError("IB has an open or uncertain order.")
        fresh = load_latest_ib_reconciliation(self.settings)
        if fresh is None or (fresh.broker_cash, fresh.broker_positions, fresh.managed_accounts) != (report.broker_cash, report.broker_positions, report.managed_accounts):
            raise ValueError("Portfolio changed during validation; waiting for fresh reconciliation.")
        return True
