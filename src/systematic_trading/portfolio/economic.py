"""A signed cash ledger and explicit bridge from security P&L to account NAV."""
from decimal import Decimal

from systematic_trading.domain.enums import OrderSide
from systematic_trading.domain.events import CashEventRecordedEvent, PlatformEventType
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.portfolio.context import portfolio_context, NY, session_end
from systematic_trading.portfolio.valuation import fx_rate
from systematic_trading.live.pnl import _broker_record_fills, PnlReadView


def record_cash_event(store, event: CashEventRecordedEvent):
    context = portfolio_context(store)
    if event.payload.portfolio_episode_id != context.episode_id or not context.includes(event.occurred_at):
        raise ValueError("Cash event does not belong to the active portfolio episode")
    if event.source.environment is None or event.source.environment.value != context.environment:
        raise ValueError("Cash event environment differs from portfolio")
    if context.account_id and event.payload.account_id != context.account_id:
        raise ValueError("Cash event account differs from portfolio")
    if not context.account_id:
        accounts = {f.account for r in store.list_broker_order_records() if r.environment.value == context.environment
                    for f in r.execution_fills if f.account and context.includes(f.filled_at)}
        if accounts != {event.payload.account_id}:
            raise ValueError("Cash event requires a uniquely identified portfolio account")
    event_id = digest(encode([event.payload.account_id, context.environment, event.payload.external_id]))
    event = event.model_copy(update={"event_id": event_id})
    old = store.get_platform_event_outbox_record(event_id)
    if old and old.payload != event:
        raise ValueError("Conflicting cash event identity; append an explicit reversing event")
    return old or store.append_platform_event(event)


def economic_bridge(store, opening, opening_nav, closing_nav, security_pnl, day):
    context, warnings = portfolio_context(store), []
    view = PnlReadView(store)
    result = dict(portfolio_context=context.model_dump(mode="json"), as_of=str(day),
        opening_nav_cnh=opening_nav, closing_nav_cnh=closing_nav, security_pnl_cnh=security_pnl,
        external_flows_cnh=Decimal(0), income_cnh=Decimal(0), fees_and_taxes_cnh=Decimal(0),
        cash_adjustments_cnh=Decimal(0), cash_fx_pnl_cnh=Decimal(0), unexplained_cnh=None,
        reconciled=False, flow_adjusted_return=None, return_method="Modified Dietz; withheld until reconciled",
        warnings=warnings)
    if opening is None or opening_nav is None or closing_nav is None or security_pnl is None or context.cutoff_at is None:
        warnings.append("Opening evidence or complete valuations are unavailable; economic reconciliation is incomplete.")
        return result
    # Cash positions plus every dated cash movement explain currency translation.
    movements = [(b.currency, b.amount, opening.as_of) for b in opening.cash]
    for fill in _broker_record_fills(view, warnings):
        if context.includes(fill.traded_at, through=session_end(day)):
            movements.append((fill.currency, fill.quantity * fill.price * (-1 if fill.side == OrderSide.BUY else 1),
                              fill.traded_at.astimezone(NY).date()))
    ledger = store.list_platform_event_outbox_records(event_type=PlatformEventType.CASH_EVENT_RECORDED, limit=100001)
    if len(ledger) > 100000:
        warnings.append("Cash ledger exceeds read limit; reconciliation withheld.")
        return result
    weighted_flows = Decimal(0)
    seconds = Decimal(str((session_end(day) - context.cutoff_at).total_seconds()))
    for record in ledger:
        event, payload = record.payload, record.payload.payload
        if payload.portfolio_episode_id != context.episode_id or not context.includes(event.occurred_at, through=session_end(day)):
            continue
        event_day = event.occurred_at.astimezone(NY).date()
        rate = fx_rate(view, payload.currency, event_day, warnings)
        if rate is None:
            continue
        category = {"external_flow":"external_flows_cnh", "dividend":"income_cnh", "interest":"income_cnh",
                    "fee":"fees_and_taxes_cnh", "tax":"fees_and_taxes_cnh", "cash_adjustment":"cash_adjustments_cnh"}[payload.kind]
        result[category] += payload.amount * rate
        if payload.kind == "external_flow" and seconds > 0:
            weight = Decimal(str((session_end(day) - event.occurred_at).total_seconds())) / seconds
            weighted_flows += payload.amount * rate * weight
        movements.append((payload.currency, payload.amount, event_day))
    for currency, amount, movement_day in movements:
        initial = fx_rate(view, currency, movement_day, warnings) if movement_day else None
        final = fx_rate(view, currency, day, warnings)
        if initial is None or final is None:
            warnings.append("Missing cash FX observation; reconciliation withheld.")
            continue
        result["cash_fx_pnl_cnh"] += amount * (final - initial)
    if warnings:
        return result
    change = closing_nav - opening_nav
    explained = security_pnl + sum(result[k] for k in ("external_flows_cnh", "income_cnh", "fees_and_taxes_cnh", "cash_adjustments_cnh", "cash_fx_pnl_cnh"))
    result.update(nav_change_cnh=change, unexplained_cnh=(change-explained).quantize(Decimal(".01")),
                  net_economic_pnl_cnh=change-result["external_flows_cnh"])
    result["reconciled"] = abs(result["unexplained_cnh"]) <= Decimal(".02")
    if result["reconciled"] and opening_nav + weighted_flows > 0:
        result["flow_adjusted_return"] = result["net_economic_pnl_cnh"] / (opening_nav + weighted_flows)
        result["return_method"] = "Modified Dietz"
    if not result["reconciled"]:
        warnings.append("Unexplained NAV change remains. Import broker statement cash flows, income, commissions and taxes before treating this as reconciled.")
    return result
