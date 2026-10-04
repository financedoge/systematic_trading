"""Dated allocation performance, published by the application's analytics worker."""
import json
from datetime import datetime, date
from pathlib import Path

from systematic_trading.domain.enums import Currency
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.portfolio.context import session_end
from systematic_trading.portfolio.strategy_allocation import control_events, control_state
from systematic_trading.portfolio.strategy_book import D, RESERVE, book_value, replay_book
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.strategy_catalog import registered_strategy_definition


def allocation_revision(store):
    return digest(encode(control_state(store)))


def allocation_ledger_revision(store):
    """Late fills and virtual-only approvals must invalidate saved attribution."""
    if control_state(store)['active']['version'] == 'legacy':
        return 'legacy'
    proposals = [p.model_dump(mode='json') for p in store.list_proposals()
        if p.input_provenance.get('allocation') and p.status.value == 'approved']
    records = [dict(id=r.local_order_id, proposal=r.proposal_id, quantity=r.filled_quantity,
        price=str(r.average_fill_price), issue=r.execution_sync_issue,
        reference_price=str(r.order.reference_price),
        fills=[f.model_dump(mode='json') for f in r.execution_fills])
        for r in store.list_broker_order_records() if r.filled_quantity or r.execution_sync_issue]
    return digest(encode(dict(proposals=sorted(proposals,key=lambda p:p['proposal_id']),
        records=sorted(records,key=lambda r:r['id']), approvals=store.strategy_approval_times())))


def allocation_timeline(store):
    events = [e for e in control_events(store) if e['kind'] == 'allocation_activated']
    return [dict(version=e['active']['version'], effective_close=e['effective_close'],
        activated_at=e['at'], approved_at=e['active']['approved_at'],
        label=' + '.join(f"{D(r['weight'])*100:g}% {registered_strategy_definition(r['strategy_key']).name}"
            for r in e['active']['allocations']), allocations=e['active']['allocations'],
        operator=e['operator'], reason=e['reason']) for e in events]


def period_for(timeline, day):
    # A close handover assigns the subsequent session's return to the new mix.
    candidates = [r for r in timeline if r['effective_close'] < str(day)]
    return candidates[-1] if candidates else dict(version='legacy', label='Legacy / unverified strategy assignment')


def build_allocation_analytics(settings, store, analytics):
    events = [e for e in control_events(store) if e['kind'] == 'allocation_activated']
    result = dict(revision=allocation_revision(store), ledger_revision=allocation_ledger_revision(store), timeline=allocation_timeline(store),
        periods=[], reference=[], sleeve_series=[], warnings=[],
        reference_label='Approved allocation reference · adjusted units at next-session close · 25 bp/year model cost',
        legacy_label='Legacy / unverified strategy assignment')
    if not events:
        result['warnings'] = ['No dated allocation handover has been recorded. Earlier account history is labelled legacy; standalone strategy curves are comparisons.']
        return result
    publication = analytics.latest('governance/catalog')
    if not publication:
        raise ValueError('Published audited marks are required for allocation performance.')
    reader = GovernedInputs(Path(json.loads(publication['provenance'])['root']), publication['version'])
    symbols = {s for e in events for s in e['active']['opening']['prices']}
    first = events[0]['effective_close']
    rows = {s:{r['trade_date']:r for r in reader.rows(s, first, str(date.today()))} for s in symbols}
    sessions = sorted({d for values in rows.values() for d in values})
    proposals = store.list_proposals()
    approvals = store.strategy_approval_times()
    for index, event in enumerate(events):
        active, opening = event['active'], event['active']['opening']
        end = events[index+1]['effective_close'] if index+1 < len(events) else sessions[-1]
        close_time = datetime.fromisoformat(events[index+1]['at']) if index+1 < len(events) else None
        marked_through = session_end(date.fromisoformat(end))
        if close_time:
            marked_through = min(marked_through, close_time)
        opening_values = {k:book_value(v,opening['prices'],opening['fx']) for k,v in opening['book'].items()}
        last_values = opening_values
        period_warnings, capital_flows = [], {k:D(0) for k in opening_values}
        unclassified_cash = D(0)
        for proposal in proposals:
            allocation = proposal.input_provenance.get('allocation', {})
            approved = approvals.get(proposal.proposal_id)
            if allocation.get('version') == active['version'] and approved and proposal.status.value == 'approved':
                if not datetime.fromisoformat(opening['at']) < datetime.fromisoformat(approved) <= marked_through:
                    continue
                intent = allocation['intent']
                unclassified_cash += sum(D(v)*D(intent['fx'][c]) for c,v in intent.get('account_cash_adjustments', {}).items())
                for k,v in intent['cash_transfers'].items():
                    capital_flows[k] += D(v)*D(intent['fx']['USD'])
        for day in (d for d in sessions if event['effective_close'] <= d <= end):
            try:
                prices, fx = dated_marks(store, rows, day, opening['fx'].keys())
                through = min(session_end(date.fromisoformat(day)), close_time) if close_time else session_end(date.fromisoformat(day))
                if through < datetime.fromisoformat(opening['at']):
                    values, warnings = opening_values, []
                else:
                    book, warnings = replay_book(store, active, through=through)
                    values = {k:book_value(v,prices,fx) for k,v in book.items()}
                period_warnings.extend(warnings)
                if warnings:
                    break
                last_values = values
                result['sleeve_series'].append(dict(trade_date=day, version=active['version'],
                    values={k:str(v) for k,v in values.items()}, total=str(sum(values.values()))))
            except (ValueError, KeyError) as exc:
                period_warnings.append(str(exc))
                break
        names = {r['strategy_key']:registered_strategy_definition(r['strategy_key']).name for r in active['allocations']}
        names[RESERVE] = 'Reserve cash / shared account residual'
        result['periods'].append(dict(version=active['version'], start=event['effective_close'], end=end,
            label=result['timeline'][index]['label'], complete=not period_warnings, unclassified_cash_cnh=str(unclassified_cash),
            sleeves=[dict(strategy_key=k,name=names[k],opening_nav_cnh=str(v),
                closing_nav_cnh=str(last_values[k]),capital_flow_cnh=str(capital_flows[k]),
                pnl_cnh=str(last_values[k]-v-capital_flows[k]) if not period_warnings and (k != RESERVE or unclassified_cash == 0) else None)
                for k,v in opening_values.items()], warnings=sorted(set(period_warnings))))
    try:
        result['reference'] = replay_reference(events, proposals, approvals, sessions, rows, store)
    except (ValueError, KeyError) as exc:
        result['warnings'].append('Allocation reference unavailable: '+str(exc))
    result['warnings'].append('Reference trades assume dividend/split-adjusted ETF units, next-session closes, USD cash conversion at observed FX, and 25 bp/year accrued over 252 sessions. This model cost is not an observed broker fee.')
    result['input_provenance'] = dict(batch=publication['version'], files=reader.used,
        price_basis='audited_raw', reference_price_basis='dividend_split_adjusted_units', fx_basis='stored FX; historical availability is not fully audited')
    result['warnings'].append('Sleeve PnL uses marked handovers and actual fills. Cash movements, dividends, fees or FX changes without classified evidence remain a shared account residual; flow-adjusted returns are withheld when evidence is incomplete.')
    return result


def dated_marks(store, rows, day, currencies, *, adjusted=False):
    prices = {}
    for symbol, values in rows.items():
        row = values.get(day)
        column = 'adjusted_close' if adjusted else 'raw_close'
        if not row or row.get(column) is None or D(row[column]) <= 0:
            raise ValueError(f'Missing audited {column} for {symbol} on {day}; series stopped.')
        prices[symbol] = D(row[column])
    fx = {'CNH':D(1)}
    for c in set(currencies)|{'USD'}:
        if c == 'CNH':
            continue
        values = store.list_fx_rates(Currency(c), start_date=date.fromisoformat(day), end_date=date.fromisoformat(day))
        if not values or values[-1].rate_date.isoformat() != day:
            raise ValueError(f'Missing {c}/CNH FX on {day}; series stopped.')
        fx[c] = values[-1].rate
    return prices, fx


def replay_reference(events, proposals, approvals, sessions, rows, store):
    """Carry holdings across epochs; never splice standalone strategy NAVs.

    Reference trades occur at the next session close. It is a stated comparison
    convention, separate from actual-fill and order-reference-price attribution.
    """
    opening = events[0]['active']['opening']
    positions = {p['symbol']:D(p['quantity']) for p in opening['snapshot']['positions']}
    cash = {c['currency']:D(c['amount']) for c in opening['snapshot']['cash']}
    book = dict(positions=positions,cash=cash)
    from systematic_trading.live.trading_calendar import next_us_trading_day
    changes = {}
    for event in events:
        day = str(next_us_trading_day(date.fromisoformat(event['effective_close'])))
        changes[day] = (event['at'], event['active']['opening']['targets'],event['active']['version'])
    for p in proposals:
        allocation = p.input_provenance.get('allocation', {})
        approved = approvals.get(p.proposal_id)
        if allocation.get('version') and approved and p.status.value == 'approved' and p.intended_trade_date:
            day = str(p.intended_trade_date)
            if datetime.fromisoformat(approved) > session_end(p.intended_trade_date):
                day = str(next_us_trading_day(datetime.fromisoformat(approved).date()))
            if day not in changes or approved > changes[day][0]:
                changes[day] = (approved,[t.model_dump(mode='json') for t in p.targets],allocation['version'])
    points, base, version = [], None, events[0]['active']['version']
    for day in sessions:
        prices, fx = dated_marks(store,rows,day,cash.keys(),adjusted=True)
        if base is None:
            # Translate real shares into adjusted accounting units at the opening
            # mark. Subsequent total returns include distributions and splits.
            raw, _ = dated_marks(store,rows,day,cash.keys())
            for symbol in positions:
                positions[symbol] = positions[symbol]*raw[symbol]/prices[symbol]
        nav = book_value(book,prices,fx)
        if base is None:
            base = nav
        else:
            cost = nav * D('0.0025')/D(252)
            cash['USD'] = D(cash.get('USD',0)) - cost/fx['USD']
            nav -= cost
        if day in changes:
            # Reference assumes currency conversion at the observed FX mark.
            cash['USD'] = sum(D(v)*fx[c] for c,v in cash.items())/fx['USD']
            for currency in list(cash):
                if currency != 'USD':
                    cash[currency] = D(0)
            _, targets, version = changes[day]
            weights = {t['symbol']:D(t['target_weight']) for t in targets}
            for symbol in set(positions)|weights.keys():
                quantity = nav*weights.get(symbol,D(0))/(prices[symbol]*fx['USD'])
                cash['USD'] = D(cash.get('USD',0)) - (quantity-positions.get(symbol,D(0)))*prices[symbol]
                positions[symbol] = quantity
        points.append(dict(trade_date=day,nav_cnh=str(nav),index=str(nav/base*100),version=version))
    return points
