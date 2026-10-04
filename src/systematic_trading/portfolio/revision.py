"""Content revision of financial inputs, excluding routine broker polling metadata."""
import hashlib
import json


def accounting_revision(store, day):
    from systematic_trading.domain.enums import Currency
    from systematic_trading.research import current_sota_definition, instruments_for_definition
    records = store.list_broker_order_records()
    symbols = set(instruments_for_definition(current_sota_definition())) | {r.order.symbol for r in records if r.filled_quantity}
    baseline = store.latest_pnl_baseline()
    from systematic_trading.portfolio.allocation_analytics import allocation_revision
    inputs = dict(allocation=allocation_revision(store), baseline=baseline.model_dump(mode="json") if baseline else None,
        executions=[dict(id=r.local_order_id, quantity=r.filled_quantity, price=r.average_fill_price,
            fills=[f.model_dump(mode="json") for f in r.execution_fills], issue=r.execution_sync_issue)
            for r in sorted(records, key=lambda r:r.local_order_id) if r.filled_quantity or r.execution_sync_issue],
        marks={s:[r.model_dump(mode="json") for r in store.list_price_bars(s, start_date=day, end_date=day)] for s in sorted(symbols)},
        fx={c.value:[r.model_dump(mode="json") for r in store.list_fx_rates(c, end_date=day)]
            for c in sorted({Currency.USD} | {r.order.currency for r in records if r.filled_quantity})})
    return hashlib.sha256(json.dumps(inputs, sort_keys=True, default=str).encode()).hexdigest()
