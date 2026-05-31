from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal

from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.domain import (
    BrokerOrderRecord,
    BrokerOrderStatus,
    Currency,
    OrderSide,
    PnLBaseline,
    PnLOpenLot,
    PnLSnapshot,
    SymbolPnL,
)
from systematic_trading.storage.sqlite import SQLiteStore

PNL_FILL_STATUSES = {BrokerOrderStatus.FILLED, BrokerOrderStatus.PARTIALLY_FILLED}


@dataclass(frozen=True)
class _LedgerFill:
    fill_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: Decimal
    currency: Currency
    traded_at: datetime


def build_dashboard_pnl_snapshot(store: SQLiteStore, *, as_of: date | None = None) -> PnLSnapshot:
    return _build_pnl_snapshot(store, as_of=as_of, use_reference_prices=False)


def build_reference_pnl_snapshot(store: SQLiteStore, *, as_of: date | None = None) -> PnLSnapshot:
    return _build_pnl_snapshot(store, as_of=as_of, use_reference_prices=True)


def _build_pnl_snapshot(
    store: SQLiteStore,
    *,
    as_of: date | None = None,
    use_reference_prices: bool,
) -> PnLSnapshot:
    as_of_date = as_of or date.today()
    as_of_at = datetime.combine(as_of_date, time.max, tzinfo=UTC)
    baseline = store.latest_pnl_baseline()
    warnings: list[str] = []
    lots_by_symbol: dict[str, list[PnLOpenLot]] = {}
    realized_by_symbol = _decimal_map()
    baseline_trade_count = 0
    baseline_id: str | None = None
    baseline_cutoff_at: datetime | None = None

    if baseline is not None:
        baseline_id = baseline.baseline_id
        baseline_cutoff_at = _ensure_aware(baseline.cutoff_at)
        baseline_trade_count = baseline.filled_trade_count
        for symbol, realized in baseline.realized_pnl_by_symbol_cnh.items():
            realized_by_symbol[symbol.upper()] += Decimal(realized)
        for lot in baseline.open_lots:
            lots_by_symbol.setdefault(lot.symbol.upper(), []).append(lot)
        warnings.extend(baseline.warnings)

    fills = _broker_record_fills(store, warnings, use_reference_prices=use_reference_prices)
    if baseline_cutoff_at is not None:
        fills = [fill for fill in fills if fill.traded_at > baseline_cutoff_at]
    fills = [fill for fill in fills if fill.traded_at <= as_of_at]
    _apply_fills(store, fills, lots_by_symbol, realized_by_symbol, as_of_date, warnings)
    symbol_rows, valuation_complete = _symbol_pnl_rows(store, lots_by_symbol, realized_by_symbol, as_of_date, warnings)
    realized_total = sum((row.realized_pnl_cnh for row in symbol_rows), Decimal("0"))
    unrealized_total = sum((row.unrealized_pnl_cnh or Decimal("0") for row in symbol_rows), Decimal("0"))
    cost_total = sum((row.cost_basis_cnh for row in symbol_rows), Decimal("0"))
    market_total = sum((row.market_value_cnh or Decimal("0") for row in symbol_rows), Decimal("0"))
    processed_trade_count = len(fills)
    if baseline is None and not fills:
        warnings.append(
            "No filled broker order records are available yet; PnL will remain zero until execution fills are synced."
        )
    if baseline_trade_count + processed_trade_count:
        warnings.append("PnL currently excludes commissions and fees because broker execution records do not store them yet.")
    source = "broker_order_reference_prices" if use_reference_prices else "broker_order_records"
    return PnLSnapshot(
        as_of=as_of_at,
        source=source,
        baseline_id=baseline_id,
        baseline_cutoff_at=baseline_cutoff_at,
        realized_pnl_cnh=quantize_money(realized_total),
        unrealized_pnl_cnh=quantize_money(unrealized_total),
        total_pnl_cnh=quantize_money(realized_total + unrealized_total),
        open_cost_basis_cnh=quantize_money(cost_total),
        open_market_value_cnh=quantize_money(market_total),
        filled_trade_count=baseline_trade_count + processed_trade_count,
        open_lot_count=sum(len(lots) for lots in lots_by_symbol.values()),
        valuation_complete=valuation_complete,
        symbols=symbol_rows,
        warnings=_dedupe(warnings),
    )


def build_pnl_baseline(store: SQLiteStore, *, cutoff_date: date) -> PnLBaseline:
    cutoff_at = datetime.combine(cutoff_date, time.max, tzinfo=UTC)
    warnings: list[str] = []
    lots_by_symbol: dict[str, list[PnLOpenLot]] = {}
    realized_by_symbol = _decimal_map()
    fills = [fill for fill in _broker_record_fills(store, warnings) if fill.traded_at <= cutoff_at]
    _apply_fills(store, fills, lots_by_symbol, realized_by_symbol, cutoff_date, warnings)
    open_lots = [
        lot
        for symbol in sorted(lots_by_symbol)
        for lot in lots_by_symbol[symbol]
        if lot.quantity != 0
    ]
    if not fills:
        warnings.append(f"No filled broker order records were available on or before {cutoff_date}; baseline is empty.")
    return PnLBaseline(
        cutoff_at=cutoff_at,
        realized_pnl_cnh=quantize_money(sum(realized_by_symbol.values(), Decimal("0"))),
        realized_pnl_by_symbol_cnh={
            symbol: quantize_money(value)
            for symbol, value in sorted(realized_by_symbol.items())
            if value != 0
        },
        open_lots=open_lots,
        filled_trade_count=len(fills),
        warnings=_dedupe(warnings),
    )


def _broker_record_fills(
    store: SQLiteStore,
    warnings: list[str],
    *,
    use_reference_prices: bool = False,
) -> list[_LedgerFill]:
    fills: list[_LedgerFill] = []
    for record in store.list_broker_order_records():
        if record.filled_quantity <= 0 or record.average_fill_price is None:
            continue
        if record.status not in PNL_FILL_STATUSES:
            warnings.append(
                f"{record.local_order_id}: using filled_quantity despite broker status {record.status.value}."
            )
        price = record.order.reference_price if use_reference_prices else record.average_fill_price
        fills.append(
            _LedgerFill(
                fill_id=record.local_order_id,
                symbol=record.order.symbol.upper(),
                side=record.order.side,
                quantity=record.filled_quantity,
                price=price,
                currency=record.order.currency,
                traded_at=_record_trade_time(record),
            )
        )
    fills.sort(key=lambda fill: (fill.traded_at, fill.fill_id))
    return fills


def _apply_fills(
    store: SQLiteStore,
    fills: list[_LedgerFill],
    lots_by_symbol: dict[str, list[PnLOpenLot]],
    realized_by_symbol: dict[str, Decimal],
    as_of: date,
    warnings: list[str],
) -> None:
    for fill in fills:
        fx = _fx_to_cnh(store, fill.currency, fill.traded_at.date(), warnings)
        if fx is None:
            fx = _fx_to_cnh(store, fill.currency, as_of, warnings)
            if fx is not None:
                warnings.append(f"{fill.symbol}: used {as_of} FX for fill {fill.fill_id}; trade-date FX was unavailable.")
        if fx is None:
            warnings.append(f"{fill.symbol}: skipped fill {fill.fill_id}; missing {fill.currency}/CNH FX.")
            continue
        lots = lots_by_symbol.setdefault(fill.symbol, [])
        signed_quantity = fill.quantity if fill.side == OrderSide.BUY else -fill.quantity
        _apply_signed_fill(lots, realized_by_symbol, fill, signed_quantity, fx)
        lots_by_symbol[fill.symbol] = [lot for lot in lots if lot.quantity != 0]


def _apply_signed_fill(
    lots: list[PnLOpenLot],
    realized_by_symbol: dict[str, Decimal],
    fill: _LedgerFill,
    signed_quantity: int,
    fx: Decimal,
) -> None:
    remaining = signed_quantity
    while remaining != 0 and lots and lots[0].quantity * remaining < 0:
        lot = lots[0]
        closing_quantity = min(abs(remaining), abs(lot.quantity))
        fill_price_cnh = fill.price * fx
        lot_price_cnh = lot.cost_price * lot.cost_fx_to_cnh
        if lot.quantity > 0:
            realized_by_symbol[fill.symbol] += (fill_price_cnh - lot_price_cnh) * Decimal(closing_quantity)
            lot_quantity = lot.quantity - closing_quantity
            remaining += closing_quantity
        else:
            realized_by_symbol[fill.symbol] += (lot_price_cnh - fill_price_cnh) * Decimal(closing_quantity)
            lot_quantity = lot.quantity + closing_quantity
            remaining -= closing_quantity
        if lot_quantity == 0:
            lots.pop(0)
        else:
            lots[0] = lot.model_copy(update={"quantity": lot_quantity})
    if remaining != 0:
        lots.append(
            PnLOpenLot(
                symbol=fill.symbol,
                quantity=remaining,
                cost_price=fill.price,
                cost_fx_to_cnh=fx,
                currency=fill.currency,
                opened_at=fill.traded_at,
                source_order_id=fill.fill_id,
            )
        )


def _symbol_pnl_rows(
    store: SQLiteStore,
    lots_by_symbol: dict[str, list[PnLOpenLot]],
    realized_by_symbol: dict[str, Decimal],
    as_of: date,
    warnings: list[str],
) -> tuple[list[SymbolPnL], bool]:
    rows: list[SymbolPnL] = []
    valuation_complete = True
    symbols = sorted(set(lots_by_symbol) | set(realized_by_symbol))
    for symbol in symbols:
        lots = lots_by_symbol.get(symbol, [])
        quantity = sum((lot.quantity for lot in lots), 0)
        currency = _symbol_currency(lots)
        cost_basis = sum(
            Decimal(lot.quantity) * lot.cost_price * lot.cost_fx_to_cnh
            for lot in lots
        )
        market_value: Decimal | None = None
        unrealized: Decimal | None = None
        market_price: Decimal | None = None
        if lots:
            market_price = _latest_price(store, symbol, as_of)
            if market_price is None:
                warnings.append(f"{symbol}: missing market price on or before {as_of}; unrealized PnL is incomplete.")
                valuation_complete = False
            elif currency is None:
                warnings.append(f"{symbol}: missing lot currency; unrealized PnL is incomplete.")
                valuation_complete = False
            else:
                fx = _fx_to_cnh(store, currency, as_of, warnings)
                if fx is None:
                    warnings.append(f"{symbol}: missing {currency}/CNH FX on or before {as_of}; unrealized PnL is incomplete.")
                    valuation_complete = False
                else:
                    market_value = Decimal(quantity) * market_price * fx
                    unrealized = market_value - cost_basis
        rows.append(
            SymbolPnL(
                symbol=symbol,
                quantity=quantity,
                currency=currency,
                market_price=market_price,
                cost_basis_cnh=quantize_money(cost_basis),
                market_value_cnh=quantize_money(market_value) if market_value is not None else None,
                realized_pnl_cnh=quantize_money(realized_by_symbol.get(symbol, Decimal("0"))),
                unrealized_pnl_cnh=quantize_money(unrealized) if unrealized is not None else None,
            )
        )
    return rows, valuation_complete


def _latest_price(store: SQLiteStore, symbol: str, as_of: date) -> Decimal | None:
    bars = store.list_price_bars(symbol, end_date=as_of)
    return bars[-1].close if bars else None


def _fx_to_cnh(store: SQLiteStore, currency: Currency, as_of: date, warnings: list[str]) -> Decimal | None:
    if currency == Currency.CNH:
        return Decimal("1")
    rates = store.list_fx_rates(currency, end_date=as_of)
    if not rates:
        return None
    return rates[-1].rate


def _record_trade_time(record: BrokerOrderRecord) -> datetime:
    return _ensure_aware(record.submitted_at or record.updated_at)


def _ensure_aware(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _symbol_currency(lots: list[PnLOpenLot]) -> Currency | None:
    currencies = {lot.currency for lot in lots}
    if len(currencies) == 1:
        return next(iter(currencies))
    return None


def _decimal_map() -> defaultdict[str, Decimal]:
    return defaultdict(lambda: Decimal("0"))


def _dedupe(messages: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for message in messages:
        if message in seen:
            continue
        seen.add(message)
        deduped.append(message)
    return deduped
