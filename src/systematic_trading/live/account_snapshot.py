from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from threading import Event, Thread
from typing import Protocol

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import Currency, OrderEnvironment
from systematic_trading.domain.portfolio import CashBalance
from systematic_trading.execution.broker import BrokerConnectionProfile, InteractiveBrokersAdapter
from systematic_trading.live.sota import AccountPositionInput, LiveAccountSnapshotInput
from systematic_trading.research import current_sota_definition, instruments_for_definition


@dataclass(frozen=True)
class AccountSummaryRow:
    account: str
    tag: str
    value: str
    currency: str


@dataclass(frozen=True)
class IbPositionRow:
    account: str
    symbol: str
    security_type: str
    currency: str
    quantity: Decimal
    average_cost: Decimal


@dataclass(frozen=True)
class SnapshotBuildResult:
    snapshot: LiveAccountSnapshotInput
    warnings: list[str]


@dataclass(frozen=True)
class FetchedAccountSnapshot:
    output_path: Path
    snapshot: LiveAccountSnapshotInput
    warnings: list[str]
    managed_accounts: list[str]


class AccountSnapshotClient(Protocol):
    def fetch(self, profile: BrokerConnectionProfile) -> tuple[list[AccountSummaryRow], list[IbPositionRow], list[str]]:
        """Fetch IB account summary rows, positions, and managed account ids."""


class IbAccountSnapshotClient:
    def __init__(self, *, timeout_seconds: float = 20.0) -> None:
        self.timeout_seconds = timeout_seconds

    def fetch(self, profile: BrokerConnectionProfile) -> tuple[list[AccountSummaryRow], list[IbPositionRow], list[str]]:
        try:
            from ibapi.client import EClient
            from ibapi.wrapper import EWrapper
        except ImportError as exc:
            raise RuntimeError("IB account snapshots require the ibapi package.") from exc

        class _App(EWrapper, EClient):  # type: ignore[misc, valid-type]
            def __init__(self) -> None:
                EClient.__init__(self, self)
                self.ready = Event()
                self.summary_done = Event()
                self.positions_done = Event()
                self.summary_rows: list[AccountSummaryRow] = []
                self.position_rows: list[IbPositionRow] = []
                self.managed_accounts: list[str] = []
                self.errors: list[str] = []

            def nextValidId(self, orderId: int) -> None:  # noqa: N802 - IB API callback name
                self.ready.set()

            def managedAccounts(self, accountsList: str) -> None:  # noqa: N802
                self.managed_accounts = [account for account in accountsList.split(",") if account]

            def accountSummary(  # noqa: N802
                self,
                reqId: int,
                account: str,
                tag: str,
                value: str,
                currency: str,
            ) -> None:
                self.summary_rows.append(AccountSummaryRow(account=account, tag=tag, value=value, currency=currency))

            def accountSummaryEnd(self, reqId: int) -> None:  # noqa: N802
                self.summary_done.set()

            def position(self, account: str, contract: object, position: float, avgCost: float) -> None:  # noqa: N802
                symbol = str(getattr(contract, "symbol", "")).upper()
                security_type = str(getattr(contract, "secType", "")).upper()
                currency = str(getattr(contract, "currency", "")).upper()
                self.position_rows.append(
                    IbPositionRow(
                        account=account,
                        symbol=symbol,
                        security_type=security_type,
                        currency=currency,
                        quantity=Decimal(str(position)),
                        average_cost=Decimal(str(avgCost)),
                    )
                )

            def positionEnd(self) -> None:  # noqa: N802
                self.positions_done.set()

            def error(self, reqId: int, errorCode: int, errorString: str, advancedOrderRejectJson: str = "") -> None:  # noqa: N802
                self.errors.append(f"{reqId}:{errorCode}:{errorString}")

        app = _App()
        app.connect(profile.host, profile.port, profile.client_id)
        thread = Thread(target=app.run, daemon=True)
        thread.start()
        try:
            if not app.ready.wait(self.timeout_seconds):
                raise TimeoutError(f"Timed out waiting for IB nextValidId callback for client_id {profile.client_id}.")
            app.reqAccountSummary(
                9101,
                "All",
                "TotalCashValue,CashBalance,AvailableFunds,NetLiquidationByCurrency,ExchangeRate",
            )
            app.reqPositions()
            if not app.summary_done.wait(self.timeout_seconds):
                raise TimeoutError("Timed out waiting for IB account summary.")
            if not app.positions_done.wait(self.timeout_seconds):
                raise TimeoutError("Timed out waiting for IB positions.")
        finally:
            try:
                app.cancelAccountSummary(9101)
            except Exception:
                pass
            try:
                app.cancelPositions()
            except Exception:
                pass
            app.disconnect()
            thread.join(timeout=2)
        return app.summary_rows, app.position_rows, app.managed_accounts


def fetch_and_write_account_snapshot(
    *,
    settings: AppSettings,
    client: AccountSnapshotClient | None = None,
    as_of: date | None = None,
    output_path: Path | None = None,
    sota_universe_only: bool = False,
    timeout_seconds: float = 20.0,
) -> FetchedAccountSnapshot:
    profile = InteractiveBrokersAdapter(settings).profile_for(OrderEnvironment.PAPER).model_copy(
        update={"client_id": settings.ib_account_snapshot_client_id or settings.ib_client_id + 40}
    )
    resolved_client = client or IbAccountSnapshotClient(timeout_seconds=timeout_seconds)
    summary_rows, position_rows, managed_accounts = resolved_client.fetch(profile)
    result = build_live_snapshot(
        summary_rows=summary_rows,
        position_rows=position_rows,
        as_of=as_of or date.today(),
        sota_universe_only=sota_universe_only,
    )
    resolved_output_path = output_path or default_account_snapshot_path(settings)
    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
    resolved_output_path.write_text(result.snapshot.model_dump_json(indent=2), encoding="utf-8")
    return FetchedAccountSnapshot(
        output_path=resolved_output_path,
        snapshot=result.snapshot,
        warnings=result.warnings,
        managed_accounts=managed_accounts,
    )


def build_live_snapshot(
    *,
    summary_rows: list[AccountSummaryRow],
    position_rows: list[IbPositionRow],
    as_of: date | None,
    sota_universe_only: bool,
) -> SnapshotBuildResult:
    warnings: list[str] = []
    cash = _cash_balances(summary_rows, warnings)
    positions = _positions(position_rows, warnings, sota_universe_only=sota_universe_only)
    snapshot = LiveAccountSnapshotInput(as_of=as_of, cash=cash, positions=positions)
    return SnapshotBuildResult(snapshot=snapshot, warnings=warnings)


def default_account_snapshot_path(settings: AppSettings) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return settings.data_dir / "live" / "account_snapshots" / f"ib_paper_account_snapshot_{stamp}.json"


def _cash_balances(rows: list[AccountSummaryRow], warnings: list[str]) -> list[CashBalance]:
    for tag in ("TotalCashValue", "CashBalance", "AvailableFunds"):
        balances: dict[Currency, Decimal] = defaultdict(Decimal)
        for row in rows:
            if row.tag != tag:
                continue
            currency = _currency_or_none(row.currency)
            if currency is None:
                continue
            try:
                amount = Decimal(row.value)
            except InvalidOperation:
                warnings.append(f"ignored non-decimal cash value for {row.currency}: {row.value}")
                continue
            if amount != Decimal("0"):
                balances[currency] += amount
        if balances:
            return [CashBalance(currency=currency, amount=amount) for currency, amount in sorted(balances.items())]
    warnings.append("IB account summary did not include supported non-zero cash balances.")
    return []


def _positions(
    rows: list[IbPositionRow],
    warnings: list[str],
    *,
    sota_universe_only: bool,
) -> list[AccountPositionInput]:
    positions: list[AccountPositionInput] = []
    sota_universe = instruments_for_definition(current_sota_definition()) if sota_universe_only else {}
    for row in sorted(rows, key=lambda item: item.symbol):
        if row.quantity == Decimal("0"):
            continue
        if sota_universe_only and row.symbol not in sota_universe:
            warnings.append(f"ignored non-SOTA position {row.symbol} quantity={row.quantity}")
            continue
        if row.quantity < Decimal("0"):
            warnings.append(f"ignored short position {row.symbol} quantity={row.quantity}; current SOTA live model is long-only")
            continue
        if row.quantity != row.quantity.to_integral_value():
            warnings.append(f"ignored fractional position {row.symbol} quantity={row.quantity}; current SOTA live model uses whole shares")
            continue
        positions.append(
            AccountPositionInput(
                symbol=row.symbol,
                quantity=int(row.quantity),
                average_cost=max(row.average_cost, Decimal("0")),
            )
        )
    return positions


def _currency_or_none(value: str) -> Currency | None:
    try:
        return Currency(value.upper())
    except ValueError:
        return None
