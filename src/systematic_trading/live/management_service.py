from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, Field

from systematic_trading.config import AppSettings
from systematic_trading.domain import BrokerFillSyncResult, OrderEnvironment, OrderType, TradeProposal
from systematic_trading.data.ib import IbHistoricalDailyBarProvider
from systematic_trading.execution.broker import (
    IBExecutionSyncClient,
    InteractiveBrokersAdapter,
    InteractiveBrokersExecutionSynchronizer,
)
from systematic_trading.live.account_snapshot import AccountSnapshotClient, fetch_and_write_account_snapshot
from systematic_trading.live.alerts import AutomationAlertNotifier
from systematic_trading.live.market_data import DailyBarProvider, MarketDataRefreshResult, refresh_sota_market_data
from systematic_trading.live.pnl import build_dashboard_pnl_snapshot
from systematic_trading.live.sota import LiveAccountSnapshotInput, build_sota_live_rebalance_plan, write_sota_live_plan_artifacts
from systematic_trading.live.trading_calendar import is_us_trading_day, next_us_trading_day, previous_us_trading_day, us_trading_dates_after
from systematic_trading.research import current_sota_definition
from systematic_trading.storage.sqlite import SQLiteStore

ACCOUNT_SNAPSHOT_PATTERN = re.compile(r"ib_paper_account_snapshot_(\d{8})(?:_\d{6})?\.json$")


class TradingServiceEvent(BaseModel):
    timestamp: datetime
    event_type: str
    status: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class TradingServiceStatus(BaseModel):
    enabled: bool = False
    running: bool = False
    started_at: datetime | None = None
    heartbeat_at: datetime | None = None
    timezone: str = "America/New_York"
    after_close_time: str = "16:20"
    execution_poll_seconds: int = 60
    next_execution_sync_at: datetime | None = None
    next_eod_attempt_at: datetime | None = None
    pending_eod_date: date | None = None
    pending_eod_dates: list[date] = Field(default_factory=list)
    last_execution_sync_at: datetime | None = None
    last_execution_sync_fills_seen: int | None = None
    last_execution_sync_records_updated: int | None = None
    last_eod_date: date | None = None
    last_eod_pnl_date: date | None = None
    last_eod_pnl_snapshot_id: str | None = None
    last_eod_pnl_total_cnh: str | None = None
    last_market_data_refresh_at: datetime | None = None
    last_market_data_date: date | None = None
    last_market_data_symbols_updated: int | None = None
    last_market_data_bars_upserted: int | None = None
    last_account_snapshot_path: str | None = None
    last_rebalance_proposal_id: str | None = None
    last_rebalance_artifact_path: str | None = None
    last_error: str | None = None
    events: list[TradingServiceEvent] = Field(default_factory=list)


def trading_service_state_path(settings: AppSettings) -> Path:
    return settings.data_dir / "live" / "trading_management_service_state.json"


def load_trading_service_status(settings: AppSettings) -> TradingServiceStatus:
    path = trading_service_state_path(settings)
    if not path.exists():
        return TradingServiceStatus(
            enabled=settings.automation_enabled,
            running=False,
            timezone=settings.automation_timezone,
            after_close_time=settings.automation_after_close_time,
            execution_poll_seconds=settings.automation_execution_poll_seconds,
        )
    try:
        status = TradingServiceStatus.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return TradingServiceStatus(
            enabled=settings.automation_enabled,
            running=False,
            timezone=settings.automation_timezone,
            after_close_time=settings.automation_after_close_time,
            execution_poll_seconds=settings.automation_execution_poll_seconds,
            last_error=f"Could not read automation state file: {path}",
        )
    pending_eod_dates = list(status.pending_eod_dates)
    pending_eod_date = status.pending_eod_date
    if pending_eod_date is None and status.last_eod_pnl_date is not None and status.last_eod_date != status.last_eod_pnl_date:
        pending_eod_date = status.last_eod_pnl_date
    if pending_eod_date is not None and pending_eod_date not in pending_eod_dates:
        pending_eod_dates.append(pending_eod_date)
    pending_eod_dates = sorted(_dedupe_dates(pending_eod_dates))
    pending_eod_date = pending_eod_dates[0] if pending_eod_dates else pending_eod_date
    return status.model_copy(
        update={
            "enabled": settings.automation_enabled,
            "pending_eod_date": pending_eod_date,
            "pending_eod_dates": pending_eod_dates,
        }
    )


class TradingManagementService:
    def __init__(
        self,
        *,
        settings: AppSettings,
        store: SQLiteStore,
        execution_sync_client: IBExecutionSyncClient | None = None,
        account_snapshot_client: AccountSnapshotClient | None = None,
        market_data_provider: DailyBarProvider | None = None,
        market_data_fallback_provider: DailyBarProvider | None = None,
        fx_market_data_provider: DailyBarProvider | None = None,
        alert_notifier: AutomationAlertNotifier | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.execution_sync_client = execution_sync_client
        self.account_snapshot_client = account_snapshot_client
        self.market_data_provider = market_data_provider
        self.market_data_fallback_provider = market_data_fallback_provider
        self.fx_market_data_provider = fx_market_data_provider
        self.alert_notifier = alert_notifier or AutomationAlertNotifier(settings)
        self.state_path = trading_service_state_path(settings)
        self._lock = Lock()
        self._stop = Event()
        self._thread: Thread | None = None
        self._status = load_trading_service_status(settings).model_copy(
            update={
                "enabled": settings.automation_enabled,
                "running": False,
                "timezone": settings.automation_timezone,
                "after_close_time": settings.automation_after_close_time,
                "execution_poll_seconds": settings.automation_execution_poll_seconds,
            }
        )

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            now = datetime.now(tz=UTC)
            self._status = self._status.model_copy(
                update={
                    "enabled": True,
                    "running": True,
                    "started_at": now,
                    "heartbeat_at": now,
                    "next_execution_sync_at": now,
                    "next_eod_attempt_at": None
                    if self._status.pending_eod_date is not None or self._status.pending_eod_dates
                    else self._status.next_eod_attempt_at,
                    "last_error": None,
                }
            )
            self._record_event("service", "ok", "Trading management service started.", save=False)
            self._save_status_locked()
            self._stop.clear()
            self._thread = Thread(target=self._run, name="trading-management-service", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread = self._thread
        if thread is not None:
            thread.join(timeout=5)
        with self._lock:
            self._status = self._status.model_copy(
                update={
                    "running": False,
                    "heartbeat_at": datetime.now(tz=UTC),
                }
            )
            self._record_event("service", "ok", "Trading management service stopped.", save=False)
            self._save_status_locked()

    def status(self) -> TradingServiceStatus:
        with self._lock:
            return self._status

    def run_once(self, *, now: datetime | None = None) -> TradingServiceStatus:
        current = _as_utc(now or datetime.now(tz=UTC))
        with self._lock:
            self._status = self._status.model_copy(update={"heartbeat_at": current, "running": self._thread is not None and self._thread.is_alive()})
            self._save_status_locked()

        if not self._is_monitoring_day(current):
            self._defer_until_next_trading_day(current)
            with self._lock:
                return self._status

        if self._execution_sync_due(current):
            self._sync_executions(current)
        self._refresh_eod_backlog(current)
        processed_eod_dates: set[date] = set()
        while self._eod_due(current):
            with self._lock:
                service_date = self._status.pending_eod_date
            if service_date is None or service_date in processed_eod_dates:
                break
            processed_eod_dates.add(service_date)
            self._run_eod(current)
            self._refresh_eod_backlog(current)

        with self._lock:
            return self._status

    def _run(self) -> None:
        while not self._stop.wait(max(self.settings.automation_loop_interval_seconds, 1)):
            self.run_once()

    def _execution_sync_due(self, now: datetime) -> bool:
        with self._lock:
            due_at = self._status.next_execution_sync_at
        return due_at is None or _as_utc(now) >= due_at

    def _sync_executions(self, now: datetime) -> BrokerFillSyncResult | None:
        now_utc = _as_utc(now)
        try:
            synchronizer = InteractiveBrokersExecutionSynchronizer(
                self.settings,
                client=self.execution_sync_client,
            )
            result = synchronizer.sync_order_fills(store=self.store, environment=OrderEnvironment.PAPER)
            next_at = now_utc.timestamp() + max(self.settings.automation_execution_poll_seconds, 1)
            with self._lock:
                self._status = self._status.model_copy(
                    update={
                        "last_execution_sync_at": now_utc,
                        "last_execution_sync_fills_seen": result.fills_seen,
                        "last_execution_sync_records_updated": result.records_updated,
                        "next_execution_sync_at": datetime.fromtimestamp(next_at, tz=UTC),
                        "last_error": None,
                    }
                )
                self._record_event(
                    "execution_sync",
                    "ok",
                    f"Synced {result.records_updated} local broker record(s) from {result.fills_seen} IB fill(s).",
                    details={"warnings": result.warnings},
                    save=False,
                )
                self._save_status_locked()
            return result
        except Exception as exc:
            with self._lock:
                self._status = self._status.model_copy(
                    update={
                        "last_execution_sync_at": now_utc,
                        "next_execution_sync_at": datetime.fromtimestamp(
                            now_utc.timestamp() + max(self.settings.automation_execution_poll_seconds, 1),
                            tz=UTC,
                        ),
                        "last_error": f"Execution sync failed: {exc}",
                    }
                )
                self._record_event("execution_sync", "error", f"Execution sync failed: {exc}", save=False)
                self._save_status_locked()
            return None

    def _eod_due(self, now: datetime) -> bool:
        now_utc = _as_utc(now)
        with self._lock:
            pending_eod_date = self._status.pending_eod_date
            next_eod_attempt_at = self._status.next_eod_attempt_at
        if next_eod_attempt_at is not None and now_utc < next_eod_attempt_at:
            return False
        return pending_eod_date is not None

    def _run_eod(self, now: datetime) -> None:
        with self._lock:
            service_date = self._status.pending_eod_date or self._latest_eligible_eod_date(now)
        if service_date is None:
            return
        self._record_event("eod", "started", f"Started after-close workflow for {service_date}.")
        self._sync_executions(now)
        market_result = self._refresh_market_data(service_date)
        market_ready = market_result is not None and market_result.latest_bar_date is not None and market_result.latest_bar_date >= service_date
        pnl_ready = self._status.last_eod_pnl_date == service_date
        rebalance_ready = not self.settings.automation_queue_rebalance or _existing_staged_proposal(self.store, service_date) is not None

        account_snapshot = None
        account_snapshot_path: str | None = None
        try:
            account_result = fetch_and_write_account_snapshot(
                settings=self.settings,
                client=self.account_snapshot_client,
                as_of=service_date,
                sota_universe_only=False,
            )
            account_snapshot = account_result.snapshot
            account_snapshot_path = str(account_result.output_path)
            self._record_event(
                "account_snapshot",
                "ok",
                f"Fetched account snapshot with {len(account_result.snapshot.positions)} position(s).",
                details={"warnings": account_result.warnings, "managed_accounts": account_result.managed_accounts},
            )
        except Exception as exc:
            self._record_error("account_snapshot", f"Account snapshot refresh failed: {exc}")
            fallback = _latest_stored_account_snapshot(self.settings, service_date)
            if fallback is not None:
                account_snapshot_path, account_snapshot = fallback
                with self._lock:
                    self._status = self._status.model_copy(update={"last_account_snapshot_path": account_snapshot_path})
                    self._save_status_locked()
                self._record_event(
                    "account_snapshot",
                    "warning",
                    f"Using stored same-day account snapshot after live IB snapshot failed: {account_snapshot_path}",
                )

        if not pnl_ready and market_ready:
            try:
                pnl_snapshot = self.store.save_pnl_snapshot(build_dashboard_pnl_snapshot(self.store, as_of=service_date))
                pnl_ready = True
                with self._lock:
                    self._status = self._status.model_copy(
                        update={
                            "last_eod_pnl_date": service_date,
                            "last_eod_pnl_snapshot_id": pnl_snapshot.snapshot_id,
                            "last_eod_pnl_total_cnh": str(pnl_snapshot.total_pnl_cnh),
                            "last_account_snapshot_path": account_snapshot_path or self._status.last_account_snapshot_path,
                        }
                    )
                    self._record_event(
                        "pnl_snapshot",
                        "ok",
                        f"Saved EOD PnL snapshot {pnl_snapshot.snapshot_id}.",
                        details={"total_pnl_cnh": str(pnl_snapshot.total_pnl_cnh)},
                        save=False,
                    )
                    self._save_status_locked()
            except Exception as exc:
                self._record_error("pnl_snapshot", f"EOD PnL snapshot failed: {exc}")
        elif not pnl_ready:
            self._record_event(
                "pnl_snapshot",
                "warning",
                f"Skipped EOD PnL snapshot for {service_date}; market data is not current.",
            )

        if account_snapshot is not None and self.settings.automation_queue_rebalance and market_ready:
            try:
                existing = _existing_staged_proposal(self.store, service_date)
                if existing is None:
                    plan = build_sota_live_rebalance_plan(
                        store=self.store,
                        broker=InteractiveBrokersAdapter(self.settings),
                        account_snapshot=account_snapshot,
                        decision_date=service_date,
                        environment=OrderEnvironment.PAPER,
                        order_type=OrderType.TWAP,
                        queue=True,
                    )
                    json_path, _ = write_sota_live_plan_artifacts(
                        plan,
                        self.settings.data_dir / "live" / "sota_rebalance",
                    )
                    proposal_id = plan.proposal.proposal_id
                    artifact_path = str(json_path)
                    message = f"Staged SOTA rebalance proposal {proposal_id} with {len(plan.proposal.orders)} order(s)."
                else:
                    proposal_id = existing.proposal_id
                    artifact_path = self._status.last_rebalance_artifact_path
                    message = f"Skipped rebalance staging; proposal {proposal_id} already exists for {service_date}."
                rebalance_ready = True
                with self._lock:
                    self._status = self._status.model_copy(
                        update={
                            "last_rebalance_proposal_id": proposal_id,
                            "last_rebalance_artifact_path": artifact_path,
                        }
                    )
                    self._record_event("rebalance_stage", "ok", message, save=False)
                    self._save_status_locked()
            except Exception as exc:
                self._record_error("rebalance_stage", f"Rebalance staging failed: {exc}")
        elif self.settings.automation_queue_rebalance and not market_ready:
            self._record_event(
                "rebalance_stage",
                "warning",
                f"Skipped rebalance staging for {service_date}; market data is not current.",
            )

        with self._lock:
            if pnl_ready and rebalance_ready:
                remaining_eod_dates = [
                    pending_date
                    for pending_date in self._status.pending_eod_dates
                    if pending_date != service_date
                ]
                self._status = self._status.model_copy(
                    update={
                        "last_eod_date": service_date,
                        "next_eod_attempt_at": None,
                        "pending_eod_date": remaining_eod_dates[0] if remaining_eod_dates else None,
                        "pending_eod_dates": remaining_eod_dates,
                    }
                )
                self._record_event("eod", "ok", f"Completed after-close workflow for {service_date}.", save=False)
            else:
                retry_at = _as_utc(now) + timedelta(seconds=max(self.settings.automation_eod_retry_seconds, 60))
                pending_eod_dates = _dedupe_dates([service_date, *self._status.pending_eod_dates])
                self._status = self._status.model_copy(
                    update={
                        "next_eod_attempt_at": retry_at,
                        "pending_eod_date": service_date,
                        "pending_eod_dates": pending_eod_dates,
                    }
                )
                self._record_event(
                    "eod",
                    "retry",
                    f"After-close workflow for {service_date} is incomplete; retry scheduled at {retry_at.isoformat()}.",
                    save=False,
                )
            self._save_status_locked()

    def _refresh_eod_backlog(self, now: datetime) -> None:
        latest_eligible_date = self._latest_eligible_eod_date(now)
        with self._lock:
            pending_dates = list(self._status.pending_eod_dates)
            if self._status.pending_eod_date is not None:
                pending_dates.append(self._status.pending_eod_date)
            last_eod_date = self._status.last_eod_date
            if latest_eligible_date is not None:
                if last_eod_date is None:
                    pending_dates.append(latest_eligible_date)
                else:
                    pending_dates.extend(_business_dates_after(last_eod_date, latest_eligible_date))
            if last_eod_date is not None:
                pending_dates = [pending_date for pending_date in pending_dates if pending_date > last_eod_date]
            if latest_eligible_date is not None:
                pending_dates = [pending_date for pending_date in pending_dates if pending_date <= latest_eligible_date]
            pending_dates = _dedupe_dates(pending_dates)
            self._status = self._status.model_copy(
                update={
                    "pending_eod_date": pending_dates[0] if pending_dates else None,
                    "pending_eod_dates": pending_dates,
                    "next_eod_attempt_at": None if not pending_dates else self._status.next_eod_attempt_at,
                }
            )
            self._save_status_locked()

    def _refresh_market_data(self, service_date: date) -> MarketDataRefreshResult | None:
        try:
            result = refresh_sota_market_data(
                store=self.store,
                target_date=service_date,
                provider=self.market_data_provider,
                fallback_provider=self._market_data_fallback_provider(),
                fx_provider=self.fx_market_data_provider,
                allow_stale_carry_forward=self.settings.automation_market_data_carry_forward,
                carry_forward_max_calendar_days=self.settings.automation_market_data_carry_forward_max_calendar_days,
            )
            market_current = result.latest_bar_date is not None and result.latest_bar_date >= service_date
            status = "ok" if market_current and not result.warnings else "warning"
            latest_text = result.latest_bar_date.isoformat() if result.latest_bar_date is not None else "n/a"
            with self._lock:
                self._status = self._status.model_copy(
                    update={
                        "last_market_data_refresh_at": result.refreshed_at,
                        "last_market_data_date": result.latest_bar_date,
                        "last_market_data_symbols_updated": result.symbols_updated,
                        "last_market_data_bars_upserted": result.bars_upserted,
                    }
                )
                self._record_event(
                    "market_data",
                    status,
                    f"Market data refreshed through {latest_text}; upserted {result.bars_upserted} bar(s) across {result.symbols_updated} symbol(s).",
                    details={
                        "target_date": result.target_date.isoformat(),
                        "latest_fx_date": result.latest_fx_date.isoformat() if result.latest_fx_date else None,
                        "fx_rates_upserted": result.fx_rates_upserted,
                        "carried_forward_price_bars": result.carried_forward_price_bars,
                        "carried_forward_fx_rates": result.carried_forward_fx_rates,
                        "warnings": result.warnings,
                    },
                    save=False,
                )
                self._save_status_locked()
            return result
        except Exception as exc:
            self._record_error("market_data", f"Market data refresh failed for {service_date}: {exc}")
            return None

    def _local_now(self, now: datetime) -> datetime:
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)
        try:
            zone = ZoneInfo(self.settings.automation_timezone)
        except ZoneInfoNotFoundError:
            zone = ZoneInfo("America/New_York")
        return now.astimezone(zone)

    def _after_close_time(self) -> time:
        try:
            hour, minute = self.settings.automation_after_close_time.split(":", maxsplit=1)
            return time(hour=int(hour), minute=int(minute))
        except (ValueError, TypeError):
            return time(hour=16, minute=20)

    def _latest_eligible_eod_date(self, now: datetime) -> date | None:
        local_now = self._local_now(now)
        candidate = local_now.date()
        if is_us_trading_day(candidate) and local_now.time() >= self._after_close_time():
            return candidate
        return previous_us_trading_day(candidate)

    def _is_monitoring_day(self, now: datetime) -> bool:
        return is_us_trading_day(self._local_now(now).date())

    def _defer_until_next_trading_day(self, now: datetime) -> None:
        local_now = self._local_now(now)
        next_local = datetime.combine(
            next_us_trading_day(local_now.date()),
            time(hour=9, minute=30),
            tzinfo=local_now.tzinfo,
        )
        with self._lock:
            self._status = self._status.model_copy(
                update={
                    "next_execution_sync_at": next_local.astimezone(UTC),
                    "last_error": None,
                }
            )
            self._save_status_locked()

    def _record_error(self, event_type: str, message: str) -> None:
        with self._lock:
            self._status = self._status.model_copy(update={"last_error": message})
            self._record_event(event_type, "error", message, save=False)
            self._save_status_locked()

    def _record_event(
        self,
        event_type: str,
        status: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        save: bool = True,
    ) -> None:
        event = TradingServiceEvent(
            timestamp=datetime.now(tz=UTC),
            event_type=event_type,
            status=status,
            message=message,
            details=details or {},
        )
        events = [event, *self._status.events][:49]
        self._status = self._status.model_copy(update={"events": events})
        if save:
            self._save_status_locked()
        try:
            self.alert_notifier.notify(event)
        except Exception:
            pass

    def _save_status_locked(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.write_text(
            json.dumps(self._status.model_dump(mode="json"), indent=2),
            encoding="utf-8",
        )

    def _market_data_fallback_provider(self) -> DailyBarProvider | None:
        if self.market_data_fallback_provider is not None:
            return self.market_data_fallback_provider
        if self.market_data_provider is not None:
            return None
        return IbHistoricalDailyBarProvider(self.settings)


def _existing_staged_proposal(store: SQLiteStore, decision_date: date) -> TradeProposal | None:
    sleeve_name = current_sota_definition().sleeve_name
    for proposal in store.list_proposals():
        if proposal.as_of == decision_date and proposal.sleeve == sleeve_name:
            return proposal
    return None


def _latest_stored_account_snapshot(
    settings: AppSettings,
    snapshot_date: date,
) -> tuple[str, LiveAccountSnapshotInput] | None:
    snapshot_dir = settings.data_dir / "live" / "account_snapshots"
    if not snapshot_dir.exists():
        return None
    candidates: list[tuple[datetime, Path, LiveAccountSnapshotInput]] = []
    for path in snapshot_dir.glob("*.json"):
        try:
            snapshot = LiveAccountSnapshotInput.model_validate_json(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        inferred_date = snapshot.as_of or _account_snapshot_date(path)
        if inferred_date != snapshot_date:
            continue
        candidates.append((datetime.fromtimestamp(path.stat().st_mtime, tz=UTC), path, snapshot))
    if not candidates:
        return None
    _, path, snapshot = sorted(candidates, key=lambda item: item[0])[-1]
    return str(path), snapshot


def _account_snapshot_date(path: Path) -> date | None:
    match = ACCOUNT_SNAPSHOT_PATTERN.match(path.name)
    if match is None:
        return None
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def _business_dates_after(start_date: date, end_date: date) -> list[date]:
    return us_trading_dates_after(start_date, end_date)


def _dedupe_dates(values: list[date]) -> list[date]:
    return sorted(set(values))


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
