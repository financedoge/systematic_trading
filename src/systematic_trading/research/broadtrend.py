"""BroadTrend v1: causal frozen ETF policies and monthly sleeve capital.

This adapter owns daily monitoring calculations. Fractional adjusted USD units
are a research/monitoring contract; the broker allocation gate stays closed.
"""
from datetime import date, timedelta
import json
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256
from . import entry_value, trend_sleeve_portfolio
from .coupled_trends import Features

KEY = 'broadtrend_full_pool_v1'
NAME = 'BroadTrend · Full-Pool ETF Trend'
PACK = Path(__file__).with_name('broadtrend_models_v1.json')
PACK_SHA256 = '40cb164b06d0052ab7f7641d6446d0ee9f93c810ae8204d05f3b6114e74a994e'


def model_pack():
    if sha256(PACK) != PACK_SHA256:
        raise ValueError('BroadTrend model pack changed; a new version is required')
    return json.loads(PACK.read_text(encoding='utf8'))


def definition():
    from .strategy_catalog import StrategyDefinition, OverlaySpec
    p = model_pack()
    return StrategyDefinition(key=KEY, name=NAME, sleeve_name=KEY, state='tracked',
        description='51 frozen per-ETF symmetric-HMM trend sleeves. Equal capital monthly, daily next-open signals, retained sleeve cash. App monitoring only.',
        universe_key='broadtrend_51_v1', scheduler='monthly_capital_daily_signals',
        universe_members=tuple(p['universe_members']),
        overlays=(OverlaySpec('broadtrend_frozen_policy', dict(version=p['version'], model_sha256=PACK_SHA256)),))


def calendar(first, last):
    from systematic_trading.live.trading_calendar import is_us_trading_day
    a, b = date.fromisoformat(first), date.fromisoformat(last)
    # Historical NYSE exceptions predating the operational calendar's coverage.
    # NYSE special closings / ISDA Equity Derivatives Market Practice Issues.
    closed={'1994-04-27','2001-09-11','2001-09-12','2001-09-13','2001-09-14','2004-06-11','2007-01-02'}
    # NYSE began observing Martin Luther King Day in 1998.
    opened={'1994-01-17','1995-01-16','1996-01-15','1997-01-20'}
    return [str(d) for i in range((b-a).days+1) if str(d:=a+timedelta(days=i)) not in closed
        and (is_us_trading_day(d) or str(d) in opened)]


def load_inputs(settings, analytics, config=None):
    from .governed_inputs import GovernedInputs
    from .candidate_pool import audited_bar
    from systematic_trading.daily_quality import completed_session
    pub = analytics.latest('governance/catalog')
    if not pub:
        raise ValueError('BroadTrend requires published audited histories')
    reader = GovernedInputs(Path(json.loads(pub['provenance'])['root']), pub['version'])
    pack = model_pack(); records = {}; identities = {}
    for s, m in pack['models'].items():
        audit = reader.audit(s)
        if audit.get('symbol') != s or audit['status'] != 'audited_with_limitations':
            raise ValueError('BroadTrend unsupported audit: '+s)
        if m['isin'] and audit.get('research_recorder', {}).get('isin') != m['isin']:
            raise ValueError('BroadTrend identity changed: '+s)
        rows = reader.rows(s, m['history_start'], str(date.today()))
        if not rows or rows[0]['trade_date'] != m['history_start']:
            raise ValueError('BroadTrend history origin missing: '+s)
        if any(r.get('symbol') != s for r in rows):
            raise ValueError('BroadTrend bar identity mismatch: '+s)
        identities[s] = dict(symbol=s, isin=m['isin'], identity_status=audit.get('identity_status'),
            full_listing_history_certified=audit.get('full_listing_history_certified',False))
        records[s] = rows
    end = min(rows[-1]['trade_date'] for rows in records.values())
    if not completed_session(date.fromisoformat(end)):
        raise ValueError('BroadTrend requires completed sessions')
    data = {}
    for s, rows in records.items():
        rows = [r for r in rows if r['trade_date'] <= end]
        if [r['trade_date'] for r in rows] != calendar(pack['models'][s]['history_start'], end):
            raise ValueError('BroadTrend missing audited session: '+s)
        bars = [audited_bar(r) for r in rows]
        data[s] = dict(days=np.array([r['trade_date'] for r in bars]),
            **{k: np.array([float(r[k]) for r in bars]) for k in ('open','high','low','close','volume')})
    return dict(data=data, provenance=dict(batch=pub['version'], governed_files=reader.used,
        model_sha256=PACK_SHA256, price_through=end, valuation_through=end,
        identity_evidence=identities,
        latest_by_symbol={s:r[-1]['trade_date'] for s,r in records.items()},
        price_basis='Dividend/split-adjusted OHLC; separately audited raw volume (descriptive only)',
        historical_availability='Reconstructed audited vintages; historical dissemination and cohort membership uncertified',
        history_origins={s:m['history_start'] for s,m in pack['models'].items()}, accounting_currency='USD'))


def shadow(data, m, *, cost_bp=5, delay=0, anchor='2022-12-30'):
    f = Features.build(data)
    # The parent classifier replaces its fast probabilities with this same HMM.
    # Supplying it in both slots removes the need for a retired predecessor fit.
    f.hmm_models = dict(slow=m['slow'], fast=m['fast'], sigma=m['sigma'], hmm=m['fast_hmm'])
    cl = entry_value.classification(f, m['policy'], m['thesis_rule'], m['fast_hmm'])
    start = int(np.searchsorted(f.days, np.datetime64(anchor)))
    if start >= len(f.days) or str(f.days[start]) != anchor:
        raise ValueError('Exact shadow anchor required')
    sim = entry_value.simulate(f, cl, start=start, cost_bp=cost_bp, delay=delay, fc=None)
    return f, cl, sim, start


def replay(inputs, *, cost_bp=5, delay=0):
    pack = model_pack(); symbols = list(pack['models']); pieces=[]; states={}; days=None
    for s in symbols:
        f, cl, sim, start = shadow(inputs['data'][s], pack['models'][s], cost_bp=cost_bp, delay=delay)
        these = f.days[start:].astype(str)
        if days is not None and not np.array_equal(days, these):
            raise ValueError('BroadTrend aligned signal calendars required')
        days = these
        pieces.append(dict(open=f.open[start:],close=f.close[start:],
            **{k:sim[k][start:] for k in ('nav','desired','held')}))
        states[s] = dict(fast_up=float(cl['fast_probability'][-1,2]),
            fast_down=float(cl['fast_probability'][-1,0]), slow_up=float(cl['slow_probability'][-1,2]),
            desired=bool(sim['desired'][-1]), held=bool(sim['held'][-1]),
            close_test_stop=float(sim['stop'][-1]) if np.isfinite(sim['stop'][-1]) else None,
            last_trade=sim['episodes'][-1] if sim['episodes'] else None)
    arrays = {k:np.column_stack([v[k] for v in pieces]) for k in pieces[0]}
    start = int(np.searchsorted(days, pack['portfolio_anchor']))
    if start >= len(days)-1 or days[start] != pack['portfolio_anchor']:
        raise ValueError('BroadTrend exact portfolio anchor required')
    result = trend_sleeve_portfolio.run(days,symbols,arrays['open'],arrays['close'],arrays['nav'],
        arrays['desired'],arrays['held'],start=start,source='all',cost_bp=cost_bp,delay=delay)
    independent_ledger(result, arrays['close'][start:])
    return result, arrays, states


def independent_ledger(result, closes):
    """Reconstruct global cash/shares from fills, independent of sleeve budgets."""
    cash=1.; units=np.zeros(len(result['symbols'])); index={s:j for j,s in enumerate(result['symbols'])}; fills={}
    for f in result['fills']: fills.setdefault(f['date'],[]).append(f)
    error=0.
    for t,day in enumerate(result['days']):
        for f in fills.get(day,[]):
            q=f['units']*(1 if f['side']=='buy' else -1)
            units[index[f['symbol']]]+=q;cash-=q*f['price']+f['fee']
        error=max(error,abs(cash+units@closes[t]-result['nav'][t]))
    if error>1e-10 or cash < -1e-10 or np.min(units)<-1e-10:
        raise ValueError('BroadTrend independent ledger reconciliation failed')
    return dict(max_nav_error=error, cash=cash, units=units.tolist())


def diagram():
    from .strategy_diagram import label
    steps=[('Verify published batch, identities, model hashes and complete sessions','No unsupported observation is filled; retain the previous report on failure.'),
        ('For every ETF: update fast and slow local-linear Kalman filters','Frozen per-ETF variances; forward symmetric three-state HMM of normalized fast slope.'),
        ('Update the virtual long/cash state at each completed close','Entry / rearm, down-state or thesis failure exit, and nonloosening close-tested stop.'),
        ('Freeze the decision for the next session open','No same-close execution or assumed intraday stop fills; the old position bears the gap.'),
        ('Month-end: assign 1/51 capital to every sleeve','Otherwise preserve each sleeve\u2019s cash and shares. No redistribution of idle cash.'),
        ('Execute net sleeve trades and deduct one fee per side','Fractional adjusted USD accounting, zero cash interest; no leverage or broker orders.'),
        ('Publish daily NAV, held/target weights, decisions and report','App-owned monitoring; execution allocation remains disabled for this contract.')]
    parts=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 {len(steps)*100}" role="img" aria-label="BroadTrend full decision flow">']
    for i,lines in enumerate(steps):
        y=10+i*100
        if i:parts.append(f'<path d="M500 {y-25} V{y}" stroke="#487a99" stroke-width="2"/>')
        parts.append(f'<rect x="30" y="{y}" width="940" height="75" rx="10" fill="#edf7f3" stroke="#9bb6c9"/>')
        parts.append(label((f'{i+1}. '+lines[0],lines[1]),45,y+27,14))
    return [dict(title='BroadTrend complete decision flow',svg=''.join(parts)+'</svg>')]
