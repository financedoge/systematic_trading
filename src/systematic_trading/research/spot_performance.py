"""Provisional intraday marks over a pinned, completed daily publication.

No online research input, daily history rewrite, signal calculation or orders.
Broker position marks revalue published held weights; FX stays at the close.
"""
import json
from datetime import UTC, date, datetime, time
from decimal import Decimal as D
from pathlib import Path

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.portfolio.context import NY, portfolio_context, utc
from systematic_trading.portfolio.allocation_performance import positive
from systematic_trading.live.trading_calendar import next_us_trading_day, us_equity_market_close
from systematic_trading.research.governed_inputs import GovernedInputs


def prepare_spot_basis(settings, store, analytics, payload):
    """Background-only input preparation, verified against the same publication."""
    from systematic_trading.web.api import _latest_account_snapshot
    from systematic_trading.portfolio.allocation_analytics import dated_marks
    result = dict(warnings=[])
    if not payload.get('theoretical_periods') or not payload.get('strategy'):
        return result
    period = payload['theoretical_periods'][-1]
    day = period['through']
    if not day or payload['strategy'][-1]['trade_date'] != day:
        return result
    try:
        publication = analytics.latest('governance/catalog')
        if not publication:
            raise ValueError('Published audited close marks are unavailable.')
        reader = GovernedInputs(Path(json.loads(publication['provenance'])['root']), publication['version'])
        epoch = payload['allocation_timeline'][-1]
        growth = D(period['theoretical_return']) + 1
        components, symbols = [], set()
        for allocation in epoch['allocations']:
            key = allocation['strategy_key']
            saved = analytics.document('strategy-serving', 'detail/'+key)
            if not saved or saved[1]['version'] != payload['theoretical_sources'][key]['publication']:
                raise ValueError('Strategy publication changed during spot preparation.')
            detail = json.loads(saved[0]['payload'])
            held = detail.get('current_allocation', {})
            if (not detail.get('app_tracking') or held.get('valuation_date') != day
                    or detail.get('input_provenance', {}).get('batch') != publication['version']):
                raise ValueError('Held strategy weights and audited closes are not from the same completed session and batch.')
            navs = {r['trade_date']: D(str(r['nav_cnh'])) for r in detail.get(
                'cnh_nav_series' if detail.get('accounting_currency')=='USD' else 'nav_series', [])}
            weight = D(allocation['weight']) * navs[day] / navs[period['start']] / growth
            holdings = {r['symbol']:str(r['weight']) for r in held['holdings'] if D(str(r['weight'])) != 0}
            if any(D(w) < 0 for w in holdings.values()) or abs(sum(D(w) for w in holdings.values())-1) > D('.00001'):
                raise ValueError('Incomplete published held weights.')
            symbols.update(s for s in holdings if s != 'Cash')
            components.append(dict(key=key, weight=str(weight), holdings=holdings,
                                   next_rebalance=held.get('next_rebalance')))
        path, snapshot = _latest_account_snapshot(settings, [])
        account = None
        context = portfolio_context(store)
        accounts = {f.account for r in store.list_broker_order_records() for f in r.execution_fills
                    if f.account and context.includes(f.filled_at)}
        account_id = context.account_id or (next(iter(accounts)) if len(accounts) == 1 else None)
        if snapshot and snapshot.captured_at and snapshot.observation_kind == 'broker_live' and account_id:
            account = dict(snapshot.model_dump(mode='json'), account_id=account_id, path=str(path))
            symbols.update(p.symbol for p in snapshot.positions if p.quantity)
        rows = {s:{r['trade_date']:r for r in reader.rows(s, day, day)} for s in symbols}
        currencies = {c['currency'] for c in account['cash']} | {p['currency'] for p in account['positions']} if account else {'USD'}
        prices, fx = dated_marks(store, rows, day, currencies)
        result.update(close_date=day, session=str(next_us_trading_day(date.fromisoformat(day))),
            batch=publication['version'], files=reader.used, closes={s:str(v) for s,v in prices.items()},
            fx={c:str(v) for c,v in fx.items()}, components=components, account=account,
            period=period, epoch=epoch, base_nav_cnh=payload['theoretical_base_nav_cnh'],
            account_base_nav_cnh=payload['account'][0]['nav_cnh'],
            last_strategy=payload['strategy'][-1], episode_id=context.episode_id)
        # New cash captures can refresh the account endpoint without invalidating
        # a browser's identical return anchors between its daily-history polls.
        result['id'] = digest(encode({k:v for k,v in result.items() if k not in {'account', 'warnings'}}))
    except (ValueError, KeyError, TypeError) as exc:
        result['warnings'].append('Intraday preview unavailable: '+str(exc))
    return result


def mark_spot_performance(snapshot, payload, *, now=None):
    """Only fresh callbacks can supply a provisional point; never fill gaps."""
    now = now or datetime.now(UTC)
    basis = (payload or {}).get('spot_basis', {})
    result = dict(basis_id=basis.get('id'), strategy=None, account=None, actual_rebased=None,
                  warnings=list(basis.get('warnings', [])))
    snapshot.performance = result
    local = now.astimezone(NY)
    if basis.get('session') != str(local.date()):
        result['warnings'].append('Intraday preview awaits the previous session’s published close and held weights.')
        return snapshot
    marks = {}
    duplicates = {p.symbol for p in snapshot.positions if sum(r.symbol == p.symbol for r in snapshot.positions) > 1}
    for row in snapshot.positions:
        price = positive(row.market_value / row.quantity) if row.market_value is not None and row.quantity else None
        row.market_price = price
        row.previous_close = positive(basis['closes'].get(row.symbol)) if row.currency == 'USD' and row.security_type == 'STK' else None
        row.close_date = date.fromisoformat(basis['close_date']) if row.previous_close else None
        row.daily_return = price / row.previous_close - 1 if price and row.previous_close else None
        # The app's tracked ETF universe is USD. Never match another currency
        # or ambiguous contract by ticker, and never turn stale callbacks live.
        if price and not row.stale and row.currency == 'USD' and row.security_type == 'STK' and row.symbol not in duplicates:
            marks[row.symbol] = price
    close = us_equity_market_close(local.date())
    if not close or not time(9,30) <= local.time().replace(tzinfo=None) < close:
        result['warnings'].append('Spot preview is shown during the regular US session only.')
        return snapshot
    if not snapshot.connected or snapshot.status != 'live':
        result['warnings'].append('Spot preview paused: broker callbacks are stale or disconnected.')
        return snapshot
    common = dict(trade_date=str(local.date()), provisional=True, received_at=snapshot.received_at.isoformat(),
                  allocation_version=basis['epoch']['version'], allocation_label=basis['epoch']['label'])
    components = basis['components']
    required = {s for c in components for s,w in c['holdings'].items() if s != 'Cash' and D(w) > 0}
    missing = sorted(required - marks.keys())
    pending_rebalance = any(c.get('next_rebalance') and c['next_rebalance'] <= str(local.date()) for c in components)
    if not missing and not pending_rebalance:
        factor = 1 + sum(D(c['weight']) * sum(D(w)*(marks[s]/D(basis['closes'][s])-1)
            for s,w in c['holdings'].items() if s != 'Cash' and D(w) > 0) for c in components)
        nav = D(basis['last_strategy']['nav_cnh']) * factor
        index = nav / D(basis['base_nav_cnh']) * 100
        growth = (D(basis['period']['theoretical_return'])+1)*factor
        result['strategy'] = dict(common, nav_cnh=str(nav), index=str(index), is_theoretical=True,
                                  period_start=basis['period']['start'], period_growth=str(growth))
        if positive(basis['period']['actual_start_nav_cnh']):
            result['actual_rebased'] = dict(result['strategy'],
                nav_cnh=str(D(basis['period']['actual_start_nav_cnh'])*growth))
    else:
        result['warnings'].append('Strategy spot preview awaits '+('the scheduled rebalance publication.' if pending_rebalance
            else 'fresh USD broker marks for '+', '.join(missing)+'.'))
    account = basis.get('account')
    if account:
        age = (now-utc(datetime.fromisoformat(account['captured_at']))).total_seconds()
        expected = {p['symbol']:D(p['quantity']) for p in account['positions'] if D(p['quantity'])}
        observed = {p.symbol:p.quantity for p in snapshot.positions if p.quantity}
        if (snapshot.account == account['account_id'] and 0 <= age <= 600 and expected == observed
                and not duplicates and all(s in marks for s in expected)
                and all(p['currency'] == 'USD' for p in account['positions'])):
            nav = sum(D(c['amount'])*D(basis['fx'][c['currency']]) for c in account['cash'])
            nav += sum(q*marks[s]*D(basis['fx']['USD']) for s,q in expected.items())
            if nav > 0:
                result['account'] = dict(common, nav_cnh=str(nav), index=str(nav/D(basis['account_base_nav_cnh'])*100))
        else:
            result['warnings'].append('Account spot preview awaits fresh matching holdings/cash evidence and broker marks.')
    else:
        result['warnings'].append('Account spot preview awaits an identified broker holdings/cash snapshot.')
    result['warnings'].append('Provisional IB position marks; callback time is not exchange quote time. FX is fixed at '+basis['close_date']+
        '; dividends, fees and new strategy rebalances are included only when published. Account cash is from '+
        (account['captured_at'] if account else 'the latest capture')+'.')
    return snapshot


def refresh_spot_cash(settings, payload, *, now=None):
    """Refresh current observed cash without waiting for the historical import.

    Read only the latest app-captured broker snapshot, never provider price
    archives. Its quantities, currency, timestamp and pinned account still have
    to match the live feed before it can value an endpoint.
    """
    from systematic_trading.live.sota import LiveAccountSnapshotInput
    now = now or datetime.now(UTC)
    basis = (payload or {}).get('spot_basis', {})
    prior = basis.get('account')
    if not basis.get('id') or not prior or not prior.get('account_id'):
        return payload
    paths = (settings.data_dir / 'live/account_snapshots').glob('ib_paper_account_snapshot_*.json')
    path = max(paths, key=lambda p:p.name, default=None)
    if not path or str(path) == prior.get('path'):
        return payload
    raw = path.read_bytes()
    observed = LiveAccountSnapshotInput.model_validate_json(raw)
    if (observed.observation_kind != 'broker_live' or not observed.captured_at
            or observed.as_of != now.astimezone(NY).date()
            or not 0 <= (now-utc(observed.captured_at)).total_seconds() <= 600
            or utc(observed.captured_at) <= utc(datetime.fromisoformat(prior['captured_at']))
            or any(c.currency.value not in basis['fx'] for c in observed.cash)):
        return payload
    account = dict(observed.model_dump(mode='json'), path=str(path), document_sha256=digest(raw),
                   account_id=prior['account_id'])
    return dict(payload, spot_basis=dict(basis, account=account))
