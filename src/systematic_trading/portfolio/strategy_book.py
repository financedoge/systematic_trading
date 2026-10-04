"""Fractional virtual ownership, exact net orders, and execution-time attribution.

This is an attribution ledger. It does not change the account's FIFO tax lots.
Unexplained cash, fees and currency movements remain an explicit account residual.
"""
from copy import deepcopy
from datetime import datetime
from decimal import Decimal

D = lambda value: Decimal(str(value))
RESERVE = 'portfolio-reserve'


def initial_book(snapshot, allocations):
    capital = {r['strategy_key']: D(r['weight']) for r in allocations}
    capital[RESERVE] = 1 - sum(capital.values())
    return {key: dict(positions={p['symbol']: str(D(p['quantity'])*share) for p in snapshot['positions']},
        cash={c['currency']: str(D(c['amount'])*share) for c in snapshot['cash']}) for key, share in capital.items()}


def book_value(sleeve, prices, fx):
    return sum((D(q)*D(prices[s])*D(fx['USD']) for s, q in sleeve['positions'].items() if D(q)), D(0)) + sum(
        (D(v)*D(fx[c]) for c, v in sleeve['cash'].items()), D(0))


def move(book, key, symbol, quantity, price, currency='USD'):
    sleeve = book[key]
    sleeve['positions'][symbol] = str(D(sleeve['positions'].get(symbol, 0)) + quantity)
    sleeve['cash'][currency] = str(D(sleeve['cash'].get(currency, 0)) - quantity * price)
    if D(sleeve['positions'][symbol]) < D('-0.00000001'):
        raise ValueError('Virtual strategy ownership became negative; reconcile fills before proceeding.')


def rebalance_intent(book, target_weights, capital, prices, fx, *, reset_capital=False):
    """Cross opposing sleeve deltas, leaving only net demand for the broker.

    Capital changes are explicit internal cash transfers at the valuation FX.
    Between monthly capital resets each sleeve keeps its own drifting NAV.
    """
    working = deepcopy(book)
    values = {k: book_value(v, prices, fx) for k, v in book.items()}
    total = sum(values.values())
    transfers = {}
    if reset_capital:
        for key, share in capital.items():
            transfer = (total * share - values[key]) / D(fx['USD'])
            transfers[key] = str(transfer)
            working[key]['cash']['USD'] = str(D(working[key]['cash'].get('USD', 0)) + transfer)
        values = {k: total * capital[k] for k in working}
    elif values.get(RESERVE, D(0)) < 0:
        # A fee or unclassified withdrawal can overdraw a zero-target reserve.
        # Fund the shared residual pro rata as explicit capital transfers; never
        # label an unclassified cash movement as an individual strategy's loss.
        donors = {k:v for k,v in values.items() if k != RESERVE and v > 0}
        deficit = -values[RESERVE]
        available = sum(donors.values())
        if available <= deficit:
            raise ValueError('Shared cash residual exceeds available strategy capital.')
        remaining = deficit / D(fx['USD'])
        transfers[RESERVE] = str(remaining)
        for index, key in enumerate(sorted(donors)):
            amount = remaining if index == len(donors)-1 else deficit / D(fx['USD']) * donors[key] / available
            remaining -= amount
            transfers[key] = str(-amount)
        for key, amount in transfers.items():
            working[key]['cash']['USD'] = str(D(working[key]['cash'].get('USD', 0)) + D(amount))
        values = {k:book_value(v, prices, fx) for k,v in working.items()}
    symbols = sorted({s for v in working.values() for s in v['positions']} | {s for v in target_weights.values() for s in v})
    crosses, demands = [], {}
    for symbol in symbols:
        price = D(prices[symbol])
        delta = {k: values[k]*D(target_weights.get(k, {}).get(symbol, 0))/(price*D(fx['USD'])) - D(v['positions'].get(symbol, 0))
            for k, v in working.items()}
        buys = {k: q for k, q in delta.items() if q > 0}
        sells = {k: -q for k, q in delta.items() if q < 0}
        for seller in sorted(sells):
            for buyer in sorted(buys):
                q = min(sells[seller], buys[buyer])
                if q <= 0:
                    continue
                crosses.append(dict(symbol=symbol, seller=seller, buyer=buyer, quantity=str(q), price=str(price)))
                sells[seller] -= q
                buys[buyer] -= q
        demands[symbol] = {k: str(q) for k, q in {**{k:q for k,q in buys.items() if q},
            **{k:-q for k,q in sells.items() if q}}.items()}
    return dict(cash_transfers=transfers, crosses=crosses, demands=demands,
        capital_reset=reset_capital, capital_nav_cnh={k: str(v) for k,v in values.items()},
        prices={s: str(v) for s,v in prices.items()}, fx={c: str(v) for c,v in fx.items()})


def apply_internal(book, intent):
    for currency, amount in intent.get('account_cash_adjustments', {}).items():
        book[RESERVE]['cash'][currency] = str(D(book[RESERVE]['cash'].get(currency, 0)) + D(amount))
    for key, amount in intent['cash_transfers'].items():
        book[key]['cash']['USD'] = str(D(book[key]['cash'].get('USD', 0)) + D(amount))
    for cross in intent['crosses']:
        q, p = D(cross['quantity']), D(cross['price'])
        move(book, cross['seller'], cross['symbol'], -q, p)
        move(book, cross['buyer'], cross['symbol'], q, p)


def apply_fill(book, intent, fill, *, reference_price=None):
    sign = 1 if str(fill.side) in ('BUY', 'buy') else -1
    demand = {k: abs(D(q)) for k,q in intent['demands'].get(fill.symbol, {}).items() if D(q)*sign > 0}
    total = sum(demand.values())
    if not total:
        raise ValueError('Execution has no matching strategy demand; attribution needs reconciliation.')
    price = D(reference_price) if reference_price is not None else fill.average_price
    remaining = D(fill.quantity)
    for index, key in enumerate(sorted(demand)):
        q = remaining if index == len(demand)-1 else D(fill.quantity) * demand[key]/total
        remaining -= q
        move(book, key, fill.symbol, q*sign, price, str(fill.currency or 'USD'))


def replay_book(store, active, *, through=None, reference=False):
    """Sort by economic time, so a delayed execution report stays in its period."""
    opening = active.get('opening')
    if not opening:
        raise ValueError('No verified virtual-ledger opening for this allocation.')
    book = deepcopy(opening['book'])
    cutoff = datetime.fromisoformat(opening['at'])
    proposals = {p.proposal_id:p for p in store.list_proposals()}
    approvals = store.strategy_approval_times()
    events, warnings = [], []
    for proposal in proposals.values():
        allocation = proposal.input_provenance.get('allocation', {})
        if allocation.get('version') != active['version'] or 'intent' not in allocation:
            continue
        approved = approvals.get(proposal.proposal_id)
        if approved and proposal.status.value == 'approved':
            at = datetime.fromisoformat(approved)
            if at > cutoff and (through is None or at <= through):
                events.append((at, 0, proposal.proposal_id, 'internal', allocation['intent']))
    seen = set()
    for record in store.list_broker_order_records():
        proposal = proposals.get(record.proposal_id)
        if record.filled_quantity and not record.execution_fills and (record.submitted_at or record.updated_at) > cutoff:
            warnings.append('An order has aggregate fills without execution timestamps; attribution is incomplete.')
        for fill in record.execution_fills:
            if fill.filled_at <= cutoff or (through is not None and fill.filled_at > through):
                continue
            identity = fill.execution_id or (record.local_order_id, fill.filled_at.isoformat(), fill.quantity, str(fill.average_price))
            if identity in seen:
                continue
            seen.add(identity)
            allocation = proposal.input_provenance.get('allocation', {}) if proposal else {}
            if allocation.get('version') != active['version']:
                warnings.append('Execution from a different allocation needs an explicit handover reconciliation.')
                continue
            if record.proposal_id not in approvals:
                warnings.append('Execution approval evidence is unavailable.')
                continue
            events.append((fill.filled_at, 1, str(identity), 'fill', (allocation['intent'], fill, record.order.reference_price)))
    for _, _, _, kind, payload in sorted(events, key=lambda row:row[:3]):
        if kind == 'internal':
            apply_internal(book, payload)
        else:
            intent, fill, reference_price = payload
            apply_fill(book, intent, fill, reference_price=reference_price if reference else None)
    return book, sorted(set(warnings))
