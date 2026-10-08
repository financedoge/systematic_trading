"""One account proposal from independently calculated, capital-weighted strategies."""
from datetime import date

from systematic_trading.portfolio.strategy_allocation import (
    allocation_binding_issues, combine_targets, control_state, trading_definition,
)
from systematic_trading.portfolio.strategy_book import D, RESERVE, initial_book, rebalance_intent, replay_book
from systematic_trading.research.strategy_catalog import registered_strategy_definition


def build_allocated_plan(*, store, broker, account_snapshot, decision_date, intended_trade_date,
                         environment, order_type, queue=False, target_decision_date=None,
                         target_proposal=None, active_override=None, reuse_proposal_intent=False):
    from systematic_trading.live.sota import build_sota_live_rebalance_plan, _latest_fx_to_cnh, _required_currencies
    from systematic_trading.research import instruments_for_definition
    from systematic_trading.market_data.analytics_store import digest, encode
    from dataclasses import replace
    active = active_override or control_state(store)['active']
    from systematic_trading.research.strategy_lifecycle import require_monitored
    require_monitored(broker.settings,store,[r['strategy_key'] for r in active['allocations']])
    definition = trading_definition(store)
    if active_override:
        first = registered_strategy_definition(active['allocations'][0]['strategy_key'])
        definition = replace(first, key=active['key'], sleeve_name=active['key'], name='Proposed trading allocation')
    decision_date = decision_date or account_snapshot.as_of
    target_date = max(filter(None, (target_decision_date or decision_date,
        date.fromisoformat(active['effective_close']) if active.get('effective_close') else None)))
    plans, component_targets = {}, {}
    for row in active['allocations']:
        key = row['strategy_key']
        plan = build_sota_live_rebalance_plan(store=store, broker=broker, account_snapshot=account_snapshot,
            decision_date=decision_date, intended_trade_date=intended_trade_date, environment=environment,
            order_type=order_type, queue=False, definition=registered_strategy_definition(key),
            target_decision_date=target_date)
        plans[key] = plan
        component_targets[key] = plan.proposal.targets
    batches = {p.proposal.input_provenance.get('batch') for p in plans.values()}
    if len(batches) != 1 or None in batches:
        raise ValueError('All strategies must use the same published audited price batch.')
    instruments = instruments_for_definition(definition)
    unknown = {p.symbol for p in account_snapshot.positions} - instruments.keys()
    if unknown:
        raise ValueError('Unsupported account positions require reconciliation: '+', '.join(sorted(unknown)))
    from systematic_trading.portfolio.decision_inputs import decision_inputs
    _, marks, _ = decision_inputs(broker.settings, instruments, decision_date)
    prices = {s: D(mark['close']) for s,mark in marks.items() if mark['trade_date'] == str(decision_date)}
    if set(prices) != set(instruments):
        raise ValueError('Incomplete audited raw marks for allocation valuation.')
    fx = {str(c):v for c,v in _latest_fx_to_cnh(store=store,
        currencies=_required_currencies(instruments, account_snapshot), decision_date=decision_date).items()}
    if active.get('opening'):
        book, issues = replay_book(store, active, through=account_snapshot.captured_at)
        if issues:
            raise ValueError('; '.join(issues))
    else:
        book = initial_book(account_snapshot.model_dump(mode='json'), active['allocations'])
    actual_positions = {p.symbol:D(p.quantity) for p in account_snapshot.positions}
    for symbol in set(actual_positions) | {s for b in book.values() for s in b['positions']}:
        owned = sum(D(b['positions'].get(symbol, 0)) for b in book.values())
        if abs(owned-actual_positions.get(symbol, D(0))) > D('0.00000001'):
            raise ValueError(f'{symbol}: strategy ownership does not reconcile to the broker account.')
    # Cash changes without classified evidence stay in the shared reserve. They
    # are disclosed as residuals, never silently counted as strategy profit.
    cash_residual = {}
    actual_cash = {str(c.currency):c.amount for c in account_snapshot.cash}
    for currency in actual_cash.keys() | {c for b in book.values() for c in b['cash']}:
        residual = actual_cash.get(currency, D(0)) - sum(D(b['cash'].get(currency, 0)) for b in book.values())
        if residual:
            cash_residual[currency] = str(residual)
            book[RESERVE]['cash'][currency] = str(D(book[RESERVE]['cash'].get(currency, 0)) + residual)
    capital = {r['strategy_key']: D(r['weight']) for r in active['allocations']}
    capital[RESERVE] = 1-sum(capital.values())
    previous = [p for p in store.list_proposals() if p.status.value == 'approved'
        and p.input_provenance.get('allocation', {}).get('version') == active['version']]
    reset = not previous or max(p.target_as_of or p.as_of for p in previous) < target_date
    if target_proposal is not None:
        issues = allocation_binding_issues(store, target_proposal)
        if issues:
            raise ValueError('; '.join(issues))
        from systematic_trading.domain.portfolio import AllocationTarget
        components = target_proposal.input_provenance['allocation']['components']
        component_targets = {k:[AllocationTarget.model_validate(t) for t in components[k]['targets']]
            for k in component_targets}
    weights = {k:{t.symbol:t.target_weight for t in rows} for k,rows in component_targets.items()}
    intent = rebalance_intent(book, weights, capital, prices, fx, reset_capital=reset)
    intent['account_cash_adjustments'] = cash_residual
    navs = {k:D(v) for k,v in intent['capital_nav_cnh'].items()}
    total = sum(navs.values())
    if total <= 0 or any(v < 0 for v in navs.values()):
        raise ValueError('Strategy capital must be nonnegative and account NAV positive.')
    combined = combine_targets({k:v/total for k,v in navs.items() if k != RESERVE}, component_targets, sleeve=definition.sleeve_name)
    if target_proposal is not None and reuse_proposal_intent:
        # Rechecking an existing order must preserve its reviewed sizing. New
        # drift proposals receive fresh intents and drifting sleeve capital.
        combined = target_proposal.targets
    receipt = dict(version=active['version'], key=active['key'], allocations=active['allocations'],
        effective_close=active['effective_close'], capital_rebalance='monthly',
        components={k:dict(targets=[t.model_dump(mode='json') for t in component_targets[k]],
            inputs=p.proposal.input_provenance) for k,p in plans.items()},
        intent=intent, cash_residual=cash_residual)
    if target_proposal is not None and reuse_proposal_intent:
        receipt = dict(target_proposal.input_provenance['allocation'])
    receipt['sha256'] = digest(encode({k:v for k,v in receipt.items() if k != 'sha256'}))
    plan = build_sota_live_rebalance_plan(store=store, broker=broker, account_snapshot=account_snapshot,
        decision_date=decision_date, intended_trade_date=intended_trade_date, environment=environment,
        order_type=order_type, queue=False, definition=definition, explicit_targets=combined,
        allocation_receipt=receipt, target_decision_date=target_date)
    cap = active.get('max_batch_notional_cnh')
    if cap and sum(o.notional_cnh for o in plan.proposal.orders) > D(cap):
        raise ValueError('Net account orders exceed the allocation batch capital cap.')
    if queue:
        if plan.validation_issues:
            raise ValueError('; '.join(plan.validation_issues))
        store.save_proposal(plan.proposal)
        plan = plan.model_copy(update={'queued':True})
    return plan


def validate_internal_proposal(settings, store, proposal, now):
    """A zero-net rebalance can move virtual capital without broker orders."""
    from systematic_trading.live.strategy_control import activation_issues, snapshot_for
    from systematic_trading.live.trading_calendar import previous_us_trading_day
    from systematic_trading.execution.broker import InteractiveBrokersAdapter
    from systematic_trading.execution.window import proposal_is_expired
    from systematic_trading.domain.enums import OrderEnvironment, OrderType
    from zoneinfo import ZoneInfo
    today = now.astimezone(ZoneInfo('America/New_York')).date()
    issues = allocation_binding_issues(store, proposal) + activation_issues(settings, store, now)
    from systematic_trading.execution.reconciliation import submission_reconciliation_issues
    issues += submission_reconciliation_issues(settings, now=now)
    if issues:
        raise ValueError('; '.join(issues))
    if (proposal.orders or not proposal.input_provenance.get('allocation', {}).get('intent')
            or proposal.intended_trade_date != today or proposal.as_of != previous_us_trading_day(today)
            or proposal_is_expired(proposal, settings, now=now)):
        raise ValueError('Internal transfer requires a current, reviewed allocation proposal.')
    plan = build_allocated_plan(store=store, broker=InteractiveBrokersAdapter(settings),
        account_snapshot=snapshot_for(settings, proposal.as_of), decision_date=proposal.as_of,
        intended_trade_date=today, environment=OrderEnvironment.PAPER, order_type=OrderType.TWAP,
        target_decision_date=proposal.target_as_of)
    if (plan.proposal.orders or plan.proposal.targets != proposal.targets
            or plan.proposal.input_provenance['allocation']['intent'] != proposal.input_provenance['allocation']['intent']):
        raise ValueError('Internal capital or positions changed. Rebuild the proposal before approval.')
