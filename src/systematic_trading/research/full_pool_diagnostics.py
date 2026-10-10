"""Read-only diagnosis of frozen full-pool forecasts and portfolio replays.

No fitting, new candidate arms, data substitution or promotion decisions.
"""
from collections import defaultdict
from decimal import Decimal as D
from pathlib import Path
from types import SimpleNamespace
import shutil

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.construction_analysis import ranks
from systematic_trading.research.expanded_economics import VARIANTS, job_name
from systematic_trading.research.momentum_analysis import statistics, paired_bootstrap, holm
from systematic_trading.research.momentum_replay import read_json, checked_files, verify_usd_bundle

ARMS = tuple(a for a in VARIANTS if a != 'MR')


def correlation(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if len(a) < 3 or np.std(a) < 1e-12 or np.std(b) < 1e-12:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def rank_ic(a, b):
    return correlation(ranks(np.asarray(a)), ranks(np.asarray(b)))


def partial_rank_ic(a, b, controls):
    """Correlation of rank residuals, not a fitted trading rule."""
    x = np.column_stack([np.ones(len(a)), *[ranks(np.asarray(c)) for c in controls]])
    ra, rb = ranks(np.asarray(a)), ranks(np.asarray(b))
    return correlation(ra-x@np.linalg.lstsq(x, ra, rcond=None)[0],
                       rb-x@np.linalg.lstsq(x, rb, rcond=None)[0])


def average(values):
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else None


def weights(row, symbols):
    w = {t['symbol']:float(t['target_weight']) for t in row['targets']}
    if set(w) != set(symbols):
        raise ValueError('Candidate universe changed')
    return np.array([w[s] for s in symbols])


def multiplier(increment, forecast):
    return 1.1 if increment > .0025 and forecast > 0 else .9 if increment < -.0025 else 1.


def steering(parent, candidate, returns):
    delta = np.asarray(candidate)-np.asarray(parent)
    if abs(sum(delta)) > 1e-10:
        raise ValueError('Cash budget changed')
    return dict(active_share=float(np.abs(delta).sum()/2),
                gross_return_delta=float(delta@returns),
                asset_contributions=(delta*np.asarray(returns)).tolist())


def ic_inference(records, days, replications, seed):
    """Resample calendar months jointly; missing months stay in place."""
    keys = [(arm, metric) for arm in ARMS for metric in
            ('total_ic', 'mean_ic', 'increment_ic', 'total_minus_mean_ic')]
    lookup = {(r['arm'],r['decision']):r for r in records}
    matrix = np.array([[lookup.get((arm,day),{}).get(metric) for arm,metric in keys]
                       for day in days], dtype=float)
    family = [i for i,(_,m) in enumerate(keys) if m in ('increment_ic','total_minus_mean_ic')]
    out = {}
    for block in (3,6,12):
        raw = paired_bootstrap(matrix, block=block, replications=replications, seed=seed)
        adjusted = dict(zip(family, holm([raw[i]['p'] for i in family]), strict=True))
        out[str(block)] = {}
        for i,((arm,metric),row) in enumerate(zip(keys,raw,strict=True)):
            out[str(block)][arm+'/'+metric] = dict(n=row['n'], mean=row['mean_annual']/12,
                ci95=[v/12 for v in row['ci95']], p=row['p'],
                holm_p=float(adjusted[i]) if i in adjusted else None)
    return out


def selector_states(bars, parents, days):
    """Replay only the existing selector features from the verified adjusted bars."""
    from systematic_trading.signals.trend import AssetPoolFilterOverlay
    from systematic_trading.research.candidate_pool import CandidatePool
    selector = CandidatePool(AssetPoolFilterOverlay(min_selected=4), 'M1')
    rows = {s:[SimpleNamespace(**{k:(D(v) if k in ('open','high','low','close') else v)
                                  for k,v in r.items()}) for r in history] for s,history in bars.items()}
    targets = [SimpleNamespace(symbol=s) for s in sorted(bars)]
    states = {}
    for day in days:
        known = parents[day]['known_through']
        histories = {s:[r for r in history if r.trade_date<=known][-254:] for s,history in rows.items()}
        if known >= day or any(len(v)<254 for v in histories.values()):
            raise ValueError('Incomplete or future selector inputs')
        scores = selector._selection_scores(targets, SimpleNamespace(bars_by_symbol=histories,as_of=day))
        spy = [float(r.close) for r in rows['SPY'] if r.trade_date<=known]
        states[day] = dict(scores={s:float(v.total) for s,v in scores.items()},
            eligible=[s for s,v in scores.items() if v.raw_metrics['longMomentum']>0],
            spy_trend63=spy[-1]/spy[-64]-1, spy_drawdown=spy[-1]/max(spy)-1)
    return states


def forecast_diagnostics(base, protocol):
    models = read_json(base/'models.json')
    bars = read_json(base/'bars.json')
    parents = read_json(base/'decisions/CP.json')
    days = sorted(models)
    evaluation = [d for d in days if d>=protocol['evaluation_start']]
    symbols = sorted(bars)
    states = selector_states(bars,parents,evaluation)
    opens = {s:{r['trade_date']:float(r['open']) for r in rows} for s,rows in bars.items()}
    records, allocation = [], []
    for arm in ARMS:
        group, kind = VARIANTS[arm]
        decisions = read_json(base/'decisions'/(arm+'.json'))
        for day in evaluation:
            m, state = models[day][group], states[day]
            if m['last_label_end'] and m['last_label_end']>m['known_through']:
                raise ValueError('Future model label')
            parent, candidate = weights(parents[day],symbols), weights(decisions[day],symbols)
            active = abs(candidate-parent).sum()/2
            if not np.array_equal(parent>0,candidate>0):
                raise ValueError('Selection changed')
            held = np.flatnonzero(parent>0)
            row = dict(arm=arm,decision=day,ready=m['ready'],gross=float(sum(parent)),
                active_share=float(active),held=len(held),changed=bool(active>1e-10),
                parent_weights=dict(zip(symbols,parent.tolist(),strict=True)),
                delta_weights=dict(zip(symbols,(candidate-parent).tolist(),strict=True)),**state)
            row['gross_state'] = 'cash' if row['gross']<1e-10 else 'below75' if row['gross']<.75 else 'atleast75'
            row['trend_state'] = 'down' if state['spy_trend63']<=0 else 'up'
            row['stress_state'] = 'drawdown10' if state['spy_drawdown']<=-.10 else 'shallower'
            if m['ready']:
                forecasts = np.array([m['models'][s][kind+'_forecast'] for s in symbols])
                means = np.array([m['models'][s]['mean_return'] for s in symbols])
                increments = np.array([m['models'][s][kind+'_increment'] for s in symbols])
                if not np.allclose(forecasts,means+increments,atol=1e-14):
                    raise ValueError('Forecast decomposition changed')
                mult = [multiplier(increments[i],forecasts[i]) for i in held]
                row.update(multipliers=dict(zip([symbols[i] for i in held],mult,strict=True)),
                    uniform_multiplier=len(set(mult))<=1,
                    deadzone=int(sum(abs(increments[i])<=.0025 for i in held)),
                    positive_forecast_gate_blocked=int(sum(increments[i]>.0025 and forecasts[i]<=0 for i in held)),
                    top6_forecasts_held=len(set(np.argsort(-forecasts)[:6])&set(held)),
                    top6_increments_held=len(set(np.argsort(-increments)[:6])&set(held)))
            allocation.append(row)
            ix = days.index(day)
            if ix == len(days)-1:
                continue  # incomplete last label is never manufactured
            end = days[ix+1]
            actual = np.array([opens[s][end]/opens[s][day]-1 for s in symbols])
            transfer = steering(parent,candidate,actual)
            record = dict(row,label_end=end,**transfer,
                realized_returns=dict(zip(symbols,actual.tolist(),strict=True)))
            record['asset_contributions'] = dict(zip(symbols,transfer['asset_contributions'],strict=True))
            if m['ready']:
                total, baseline = rank_ic(forecasts,actual),rank_ic(means,actual)
                score = [state['scores'][s] for s in symbols]
                record.update(total_ic=total,mean_ic=baseline,increment_ic=rank_ic(increments,actual),
                    total_minus_mean_ic=total-baseline,
                    increment_residual_label_ic=rank_ic(increments,actual-means),
                    partial_ic=partial_rank_ic(forecasts,actual,[means,score]),
                    selector_ic=rank_ic(score,actual),
                    selected_total_ic=rank_ic(forecasts[held],actual[held]),
                    selected_increment_ic=rank_ic(increments[held],actual[held]),
                    weight_increment_rank_alignment=rank_ic(candidate-parent,increments),
                    mae=float(abs(forecasts-actual).mean()),mean_mae=float(abs(means-actual).mean()))
            records.append(record)
    summary = {}
    for arm in ARMS:
        rows = [r for r in records if r['arm']==arm and r['ready']]
        alloc = [r for r in allocation if r['arm']==arm]
        ready_alloc = [r for r in alloc if r['ready']]
        changed = [r for r in rows if r['changed']]
        metrics = ('total_ic','mean_ic','increment_ic','total_minus_mean_ic','partial_ic',
                   'selector_ic','selected_total_ic','selected_increment_ic',
                   'increment_residual_label_ic','mae','mean_mae','weight_increment_rank_alignment')
        summary[arm] = dict(months=len(rows),ready_decisions=len(ready_alloc),decisions=len(alloc),
            changed_decisions=sum(r['changed'] for r in alloc),
            selected_ic_months=sum(r['selected_total_ic'] is not None for r in rows),
            all14_ic_on_selected_months=average([r['total_ic'] for r in rows if r['selected_total_ic'] is not None]),
            increment_ic_on_selected_months=average([r['increment_ic'] for r in rows if r['selected_increment_ic'] is not None]),
            **{k:average([r[k] for r in rows]) for k in metrics},
            mean_active_share=average([r['active_share'] for r in alloc]),
            mean_active_share_when_changed=average([r['active_share'] for r in alloc if r['changed']]),
            top6_forecasts_held=average([r['top6_forecasts_held'] for r in ready_alloc]),
            positive_total_ic_months=sum(r['total_ic']>0 for r in rows),
            positive_steering_changed_months=sum(r['gross_return_delta']>0 for r in changed),
            changed_complete_months=len(changed),
            positive_ic_negative_steering=sum(r['total_ic']>0 and r['gross_return_delta']<0 for r in changed),
            unavailable_nochange=sum(not r['ready'] and not r['changed'] for r in alloc),
            ready_nochange=sum(not r['changed'] for r in ready_alloc),
            ready_cash=sum(r['gross']<1e-10 for r in ready_alloc),
            ready_uniform_multiplier=sum(r['uniform_multiplier'] for r in ready_alloc),
            ready_single_holding=sum(r['held']==1 for r in ready_alloc),
            ready_multi_uniform=sum(r['uniform_multiplier'] and r['held']>1 for r in ready_alloc),
            mean_gross_steering_bps=1e4*average([r['gross_return_delta'] for r in records if r['arm']==arm]),
            selected_deadzone=sum(r['deadzone'] for r in ready_alloc),
            selected_positive_gate_blocks=sum(r['positive_forecast_gate_blocked'] for r in ready_alloc),
            selected_observations=sum(r['held'] for r in ready_alloc))
        groups = {}
        for key in ('year','gross_state','trend_state','stress_state','ready'):
            labels = sorted(set(str(r['decision'][:4] if key=='year' else r[key]) for r in records if r['arm']==arm))
            groups[key] = {}
            for label in labels:
                subset = [r for r in records if r['arm']==arm and str(r['decision'][:4] if key=='year' else r[key])==label]
                groups[key][label] = dict(months=len(subset),ready=sum(r['ready'] for r in subset),
                    changed=sum(r['changed'] for r in subset),
                    total_ic=average([r.get('total_ic') for r in subset]),
                    increment_ic=average([r.get('increment_ic') for r in subset]),
                    mean_gross_steering_bps=1e4*average([r['gross_return_delta'] for r in subset]))
        summary[arm]['conditions'] = groups
    infer = ic_inference(records,[d for d in evaluation if d!=days[-1]],
                         protocol['bootstrap_replications'],protocol['seed'])
    return dict(summary=summary,records=records,allocation=allocation,inference=infer,symbols=symbols)


def monthly_contributions(stats):
    """Asset net PnL / own month-start NAV; sums exactly to monthly return."""
    out = defaultdict(lambda:defaultdict(float))
    wealth = 1.
    previous_month = None
    for i,(day,ret) in enumerate(zip(stats['dates'],stats['daily_returns'],strict=True)):
        month = day[:7]
        if month != previous_month:
            wealth = 1.
        for s,values in stats['asset_daily_contribution'].items():
            out[month][s] += values[i]*wealth
        wealth *= 1+ret
        previous_month = month
    if any(abs(sum(values.values())-stats['monthly'][m])>1e-8 for m,values in out.items()):
        raise ValueError('Monthly net contribution reconciliation failed')
    return {m:dict(v) for m,v in out.items()}


def drawdown_episode(economic):
    rows = economic['nav']
    nav = np.array([1e6]+[float(r['nav']) for r in rows])
    days = ['initial cash']+[r['date'] for r in rows]
    dd = nav/np.maximum.accumulate(nav)-1
    trough = int(np.argmin(dd))
    peak = int(np.argmax(nav[:trough+1]))
    recovery = next((i for i in range(trough+1,len(nav)) if nav[i]>=nav[peak]),None)
    return dict(peak=days[peak],trough=days[trough],recovery=days[recovery] if recovery else None,
                drawdown=float(dd[trough]))


def interval_contributions(stats, start, end):
    """Net asset return contributions from start close through end close."""
    out = {s:0. for s in stats['asset_daily_contribution']}
    wealth = 1.
    for i,day in enumerate(stats['dates']):
        if start < day <= end:
            for s,values in stats['asset_daily_contribution'].items():
                out[s] += values[i]*wealth
            wealth *= 1+stats['daily_returns'][i]
    if abs(sum(out.values())-(wealth-1))>1e-8:
        raise ValueError('Interval attribution does not reconcile')
    return out


def ratio_decomposition(candidate, parent):
    mu_a = float(np.mean(candidate['daily_returns'])*252)
    mu_b = float(np.mean(parent['daily_returns'])*252)
    va, vb = candidate['volatility'],parent['volatility']
    da, db = abs(candidate['max_drawdown']),abs(parent['max_drawdown'])
    result = dict(annual_mean_delta=mu_a-mu_b,annual_volatility_delta=va-vb,
        sharpe_mean_effect=(mu_a-mu_b)/vb,sharpe_vol_effect=mu_a*(1/va-1/vb),
        calmar_cagr_effect=(candidate['cagr']-parent['cagr'])/db,
        calmar_drawdown_effect=candidate['cagr']*(1/da-1/db))
    assert abs(result['sharpe_mean_effect']+result['sharpe_vol_effect']-
               (candidate['sharpe_zero_cash']-parent['sharpe_zero_cash']))<1e-12
    assert abs(result['calmar_cagr_effect']+result['calmar_drawdown_effect']-
               (candidate['cagr']/da-parent['cagr']/db))<1e-12
    return result


def portfolio_diagnostics(base, frozen_stats):
    all_stats, monthly, economics, provenance = {}, {}, {}, {}
    for arm in ('CP',*ARMS):
        name = job_name((arm,5,0,'evaluation'))
        file, bundle = base/'python'/(name+'.json'),base/'bundles'/name
        verify_usd_bundle(bundle)
        if read_json(file.with_suffix('.receipt.json')) != dict(sha256=sha256(file),manifest_sha256=sha256(bundle/'manifest.json')):
            raise ValueError('Replay receipt changed')
        economics[arm] = read_json(file)
        all_stats[arm] = statistics(economics[arm],read_json(bundle/'quotes.json'))
        for metric in ('cagr','volatility','max_drawdown','terminal_nav','sharpe_zero_cash'):
            if abs(all_stats[arm][metric]-frozen_stats[name][metric])>1e-12:
                raise ValueError('Frozen statistics no longer reproduce')
        monthly[arm] = monthly_contributions(all_stats[arm])
        provenance[name] = dict(economic=sha256(file),bundle=sha256(bundle/'manifest.json'))
    parent = all_stats['CP']
    parent_episode = drawdown_episode(economics['CP'])
    comparisons = {}
    for arm in ARMS:
        s = all_stats[arm]
        months = []
        for month in parent['monthly']:
            contrib = {asset:monthly[arm][month][asset]-monthly['CP'][month][asset] for asset in monthly[arm][month]}
            delta = s['monthly'][month]-parent['monthly'][month]
            assert abs(sum(contrib.values())-delta)<1e-8
            months.append(dict(month=month,parent=parent['monthly'][month],candidate=s['monthly'][month],
                               delta=delta,asset_contributions=contrib))
        dollar = {asset:s['asset_pnl_usd'][asset]-parent['asset_pnl_usd'][asset] for asset in s['asset_pnl_usd']}
        assert abs(sum(dollar.values())-(s['terminal_nav']-parent['terminal_nav']))<.02
        nav = {r['date']:float(r['nav']) for r in economics[arm]['nav']}
        common_dd = nav[parent_episode['trough']]/nav[parent_episode['peak']]-1
        pa = interval_contributions(s,parent_episode['peak'],parent_episode['trough'])
        pb = interval_contributions(parent,parent_episode['peak'],parent_episode['trough'])
        common_contribution = {asset:pa[asset]-pb[asset] for asset in pa}
        assert abs(sum(common_contribution.values())-(common_dd-parent_episode['drawdown']))<1e-8
        compact = ('cagr','sharpe_zero_cash','volatility','max_drawdown','annual_turnover','annual_cost_bps',
                   'total_fees_usd','terminal_nav','calendar_returns')
        comparisons[arm] = dict(metrics={k:s[k] for k in compact},
            deltas={k:s[k]-parent[k] for k in compact if k!='calendar_returns'},
            ratio_decomposition=ratio_decomposition(s,parent),months=months,
            years={y:dict(parent=v,candidate=s['calendar_returns'][y],delta=s['calendar_returns'][y]-v)
                   for y,v in parent['calendar_returns'].items()},
            positive_net_months=sum(r['delta']>0 for r in months),
            best_months=sorted(months,key=lambda r:-r['delta'])[:5],
            worst_months=sorted(months,key=lambda r:r['delta'])[:5],
            asset_pnl_difference_usd=dollar,worst_drawdown=drawdown_episode(economics[arm]),
            parent_peak_trough_return=common_dd,
            parent_peak_trough_asset_contributions=common_contribution,
            gross_asset_pnl_difference_usd=s['terminal_nav']-parent['terminal_nav']+s['total_fees_usd']-parent['total_fees_usd'])
    return dict(parent={k:v for k,v in parent.items() if k not in ('asset_daily_contribution','daily_returns','dates')},
                parent_worst_drawdown=parent_episode,comparisons=comparisons,provenance=provenance)


def analyze(root):
    root = Path(root)
    protocol = read_json(root/'protocol.json')
    base = Path(protocol['parent'])
    if sha256(base/'protocol.json')!=protocol['parent_protocol_sha256']:
        raise ValueError('Parent protocol changed')
    counts = {m:len(checked_files(base,m)) for m in ('input_manifest.json','decision_manifest.json','feature_manifest.json')}
    for relative in ('research/momentum_analysis.py','research/construction_analysis.py',
                     'signals/trend.py','research/candidate_pool.py'):
        if sha256(Path('src/systematic_trading')/relative)!=sha256(base/'source/systematic_trading'/relative):
            raise ValueError('Frozen helper source changed: '+relative)
    if read_json(base/'statistics_receipt.json')['sha256']!=sha256(base/'statistics.json'):
        raise ValueError('Frozen statistics changed')
    frozen_stats = read_json(base/'statistics.json')
    if frozen_stats['MR-cost5-delay0-evaluation']!=frozen_stats['CR-cost5-delay0-evaluation']:
        raise ValueError('Duplicate MR control no longer matches CR')
    forecast = forecast_diagnostics(base,protocol)
    portfolio = portfolio_diagnostics(base,frozen_stats)
    write_json(root/'analysis.json',dict(protocol=protocol,forecast=forecast,portfolio=portfolio,verified_files=counts))
    files = ['protocol.json','input_manifest.json','decision_manifest.json','feature_manifest.json','statistics.json',
             'statistics_receipt.json','models.json','bars.json']
    write_json(root/'parent_receipt.json',{f:sha256(base/f) for f in files})
    source = root/'source'
    source.mkdir(exist_ok=True)
    for f in (Path(__file__),Path('src/systematic_trading/research/momentum_analysis.py'),
              Path('src/systematic_trading/research/construction_analysis.py'),
              Path('src/systematic_trading/signals/trend.py'),Path('src/systematic_trading/research/candidate_pool.py')):
        shutil.copyfile(f,source/f.name)
    write_json(root/'analysis_receipt.json',dict(protocol=sha256(root/'protocol.json'),analysis=sha256(root/'analysis.json'),
        parent_receipt=sha256(root/'parent_receipt.json'),sources={f.name:sha256(f) for f in source.iterdir()}))
    return root/'analysis.json'
