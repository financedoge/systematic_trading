"""Chronological selection, family inference and compact range-breakout reports."""
from __future__ import annotations

import argparse
from datetime import datetime
import html
import itertools
from pathlib import Path

import numpy as np
import pandas as pd

import run_range_breakout as study
from systematic_trading.research.range_breakout import BreakoutSpec, lifecycle, metrics

DEST = Path('research/range-breakout-20261018-v1')


def guards(candidate, control, minimum=.05):
    return (candidate['sharpe'] >= control['sharpe']+minimum
            and candidate['cagr'] >= control['cagr']-.005
            and candidate['max_drawdown'] >= control['max_drawdown']-.02)


def select_year(results, application, year):
    """Read only the registered trailing three-year windows, not later metrics."""
    names = sorted(k.removesuffix('__c5d0') for k in results
                   if k.startswith('L') and f'__{application}__' in k and k.endswith('__c5d0'))
    passing = []
    for name in names:
        control = results[name+'__c5d0']['control']
        candidate = lambda scenario: results[name+'__'+scenario]['windows'][f'train{year}']
        baseline = lambda scenario: results[control+'__'+scenario]['windows'][f'train{year}']
        if (guards(candidate('c5d0'), baseline('c5d0')) and all(
                guards(candidate(s), baseline(s), 0) and candidate(s)['sharpe'] > baseline(s)['sharpe']
                for s in ('c10d0', 'c5d1'))):
            passing.append(name)
    def adjacent(a, b):
        ap, bp = a.split('__'), b.split('__')
        return ap[2] == bp[2] and sum(x != y for x, y in zip(ap[0].split('-'), bp[0].split('-'), strict=True)) == 1
    eligible = [a for a in passing if any(adjacent(a, b) for b in passing)]
    chosen = ('blend_control' if application == 'tilt' else 'M1')+'__monthly'
    if eligible:
        best = max(results[a+'__c5d0']['windows'][f'train{year}']['sharpe'] for a in eligible)
        plateau = [a for a in eligible if results[a+'__c5d0']['windows'][f'train{year}']['sharpe'] >= best-.02]
        chosen = min(plateau, key=lambda a: (results[a+'__c5d0']['windows'][f'train{year}']['annual_turnover'], a))
    return dict(selected=chosen, passing=passing, neighbor_supported=eligible,
                training_start=f'{year-3}-01-01', training_end=f'{year-1}-12-31')


def walk_forward(root, a, sig, results):
    p = study.read(root/'protocol.json')
    maps = study.mappings(root, a, sig)
    replay = study.Replay(a, study.read(root/'recipe.json'), p['start'])
    selections, outputs = {}, {}
    for app in ('selection', 'trading', 'tilt'):
        selections[app] = {str(y): select_year(results, app, y) for y in (2024, 2025, 2026)}
        baseline = ('blend_control' if app == 'tilt' else 'M1')+'__monthly'
        w = np.zeros_like(maps[baseline]['weights'])
        indices, anchor, previous_choice = [], None, None
        for t in range(len(a['days'])-1):
            next_day = str(a['days'][t+1])
            if next_day < p['start']:
                continue
            year = next_day[:4]
            choice = selections[app].get(year, {}).get('selected', baseline)
            row = maps[choice]['weights'][t]
            w[t] = row
            monthly = str(a['days'][t])[:7] != next_day[:7]
            gap = np.inf if anchor is None else np.abs(row-anchor).sum()+abs(row.sum()-anchor.sum())
            risk_exit = False
            if choice.startswith('L') and app in ('trading', 'tilt') and anchor is not None:
                risk_exit = bool(np.any(sig[choice.split('__')[0]+'__exits'][t] & (anchor[:-1] > 0)))
            if (anchor is None or monthly or previous_choice != choice
                    or choice.endswith('__event') and (gap > .10+1e-12 or risk_exit)):
                indices.append(t)
                anchor = row.copy()
            previous_choice = choice
        for cost, delay in itertools.product(p['cost_bps'], p['additional_delay_sessions']):
            key = 'WF_'+app+f'__c{cost}d{delay}'
            compact, _, count = replay.run(w, indices, cost, delay)
            np.savez_compressed(root/'paths'/(key+'.npz'), **compact)
            outputs[key] = dict(fills=count, adoptions=len(indices), windows={
                name: metrics(**{k: compact[k] for k in ('nav', 'turnover', 'fees', 'exposure')},
                              days=replay.day_strings, start=start, end=end)
                for name, start, end in [('evaluation', p['evaluation_start'], p['through']),
                    *[(str(y), f'{y}-01-01', f'{y}-12-31') for y in (2024, 2025, 2026)]]})
    study.write(root/'walk_forward.json', dict(selections=selections, results=outputs))
    return selections, outputs


def returns(root, name):
    nav = np.load(root/'paths'/(name+'.npz'))['nav']
    return nav/np.r_[1_000_000, nav[:-1]]-1


def family_inference(root, results, days, p):
    names = sorted(k for k in results if k.startswith('L') and k.endswith('__c5d0'))
    mask = days >= p['evaluation_start']
    diff = np.column_stack([returns(root, k)[mask]-returns(root, results[k]['control']+'__c5d0')[mask] for k in names])
    n, count = diff.shape
    rng = np.random.default_rng(p['inference']['seed'])
    block, reps = p['inference']['block_sessions'], p['inference']['replications']
    draws = np.empty((reps, count))
    centered = diff-diff.mean(axis=0)
    for b in range(reps):
        indices = ((rng.integers(0, n, size=(n+block-1)//block)[:, None]+np.arange(block)) % n).ravel()[:n]
        draws[b] = centered[indices].mean(axis=0)
    se = draws.std(axis=0, ddof=1)
    positive = se > 1e-15
    critical = float(np.quantile(np.max(np.abs(draws[:, positive]/se[positive]), axis=1), .95))
    means = diff.mean(axis=0)
    result = {k: dict(annual_mean_difference=float(means[j]*252),
                     simultaneous_lower=float((means[j]-critical*se[j])*252),
                     simultaneous_upper=float((means[j]+critical*se[j])*252),
                     family_positive=bool(means[j]-critical*se[j] > 0)) for j, k in enumerate(names)}
    study.write(root/'inference.json', dict(contrasts=count, replications=reps, block_sessions=block,
        critical=critical, method=p['inference']['method'], results=result))
    return result


def episode_summary(root, p):
    output = {}
    for variant, assets in study.read(root/'episodes.json').items():
        rows = [dict(row, symbol=s) for s, item in assets.items() for row in item['episodes']
                if row['entry_date'] and row['entry_date'] >= p['start']]
        closed = [r for r in rows if r['gross_return'] is not None]
        output[variant] = dict(entries=len(rows), closed=len(closed),
            win_rate=float(np.mean([r['gross_return'] > .001 for r in closed])) if closed else None,
            median_gross_return=float(np.median([r['gross_return'] for r in closed])) if closed else None,
            stop_loss_rate=float(np.mean([r['gross_return'] < 0 for r in closed])) if closed else None,
            failed_range_rate=float(np.mean([r['exit_reason'] == 'failed_range' for r in closed])) if closed else None,
            median_hold_sessions=float(np.median([r['exit_signal']+1-r['fill_index'] for r in closed])) if closed else None,
            durations={str(d): sum(r['duration'] == d for r in rows) for d in (42, 63, 126, 252, 504, 756)})
    study.write(root/'episode_summary.json', output)
    return output


def graph_cases(root, dest, a):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.patches import Rectangle
    names = [s for s in ('GLD', 'USO', 'SOXX', 'XLE') if s in a['symbols']]
    dates = np.array([datetime.fromisoformat(str(d)) for d in a['days']])
    numbers = mdates.date2num(dates)
    fig, axes = plt.subplots(len(names), 1, figsize=(14, 3.6*len(names)), layout='constrained')
    for ax, s in zip(np.atleast_1d(axes), names, strict=True):
        j = a['symbols'].tolist().index(s)
        signal = lifecycle(a['close'][:, j], a['open'][:, j], a['high'][:, j], a['low'][:, j],
                           a['volume'][:, j], BreakoutSpec())
        ax.plot(dates, a['close'][:, j], color='#17324f', lw=1, label='Adjusted close')
        for episode in signal['episodes']:
            t, end = episode['fill_index'], episode['exit_signal']
            if t >= len(dates) or a['days'][t] < '2021-01-04':
                continue
            cross = episode['signal_index']-2
            start = max(0, cross-episode['duration'])
            ax.add_patch(Rectangle((numbers[start], episode['lower']), numbers[cross]-numbers[start],
                                  episode['upper']-episode['lower'], color='#0d9488', alpha=.08))
            ax.plot(dates[start:cross+1], np.full(cross-start+1, episode['upper']), color='#0d9488', lw=.8)
            finish = end+1 if end is not None else len(dates)
            ax.plot(dates[t:finish], signal['stop'][t:finish], color='#e07a22', lw=1.3)
            ax.scatter(dates[t], a['open'][t, j], marker='^', color='#059669', s=50, zorder=5)
            if end is not None and end+1 < len(dates):
                ax.scatter(dates[end+1], a['open'][end+1, j], marker='x', color='#dc2626', s=45, zorder=5)
            ax.annotate(f"{episode['duration']}d", (dates[t], a['open'][t, j]), xytext=(4, 8),
                        textcoords='offset points', fontsize=8, color='#047857')
        ax.set_xlim(datetime(2021, 1, 1), dates[-1])
        ax.set_title(s+{'GLD': ' · gold', 'USO': ' · crude-oil futures fund', 'SOXX': ' · semiconductor equities',
                       'XLE': ' · energy equities (separate from oil)'}[s], loc='left', fontweight='bold')
        ax.set_ylabel('Adjusted USD')
        ax.grid(alpha=.15)
    fig.suptitle('Adaptive range → confirmed entry → trailing exit\nGreen bands = frozen prior range; triangles = next-open entries; red crosses = next-open exits', fontsize=15)
    path = dest/'cases.png'
    fig.savefig(path, dpi=145)
    plt.close(fig)
    return path


def plot_nav(root, dest, days):
    import matplotlib.pyplot as plt
    dates = [datetime.fromisoformat(str(d)) for d in days]
    names = [('FR25__monthly__c5d0', 'FR25'), ('blend_control__event__c5d0', '80% FR25 + 20% M1'),
             ('Ladaptive-V1-H1__tilt__event__c5d0', '80% FR25 + 20% breakout'),
             ('Ladaptive-V1-H1__trading__event__c5d0', 'Standalone breakout'),
             ('URTH__c5d0', 'URTH'), ('BIL__c5d0', 'BIL')]
    fig, axes = plt.subplots(2, 1, figsize=(13, 8), layout='constrained', sharex=True)
    for key, label in names:
        nav = np.load(root/'paths'/(key+'.npz'))['nav']
        axes[0].plot(dates, nav/1e6, label=label)
        axes[1].plot(dates, nav/np.maximum.accumulate(np.r_[1e6, nav])[1:]-1)
    axes[0].axvline(datetime(2024, 1, 1), ls='--', lw=1, color='#777')
    axes[0].set_ylabel('Growth of $1')
    axes[0].legend(ncol=2, loc='upper left', fontsize=9)
    axes[0].set_title('Matched full-period portfolios · 5 bp per traded side · next-open fills', loc='left', fontweight='bold')
    axes[1].set_ylabel('Drawdown')
    for ax in axes:
        ax.grid(alpha=.15)
    fig.savefig(dest/'portfolio.png', dpi=145)
    plt.close(fig)


def report(root, dest):
    study.verify(root, 'input_manifest.json')
    study.verify(root, 'signal_manifest.json')
    # Analysis must not silently use changed signal/accounting primitives.
    for relative in ('research/range_breakout.py', 'backtest/engine.py', 'backtest/accounting.py',
                     'portfolio/proposals.py'):
        if study.digest(Path('src/systematic_trading')/relative) != study.digest(root/'source/systematic_trading'/relative):
            raise ValueError('Use the frozen source environment to analyze this study: '+relative)
    native = study.read(root/'native_verification.json')
    expected_checks = 1 if 'uso' in root.name else 3
    if len(native) != expected_checks or any(r['status'] != 'succeeded' or r['maximum_nav_error_usd'] > .011 for r in native.values()):
        raise ValueError('Independent native validation is incomplete')
    a, sig = dict(np.load(root/'inputs.npz')), dict(np.load(root/'signals.npz'))
    p, results = study.read(root/'protocol.json'), study.read(root/'metrics.json')
    if len(results) != 486:
        raise ValueError('Incomplete finite scenario grid')
    for key, row in results.items():
        if study.digest(root/'paths'/(key+'.npz')) != row['sha256']:
            raise ValueError('Scenario changed')
    days = a['days'][a['days'] >= p['start']]
    selections, wf = walk_forward(root, a, sig, results)
    inference = family_inference(root, results, days, p)
    episodes = episode_summary(root, p)
    dest.mkdir(parents=True, exist_ok=True)
    graph_cases(root, dest, a)
    plot_nav(root, dest, days)
    mask = days >= p['evaluation_start']
    bill = returns(root, 'BIL__c5d0')
    table = []
    for key, row in results.items():
        r = returns(root, key)
        excess = r[mask]-bill[mask]
        annual_excess = float(excess.mean()*252)
        vol = float(excess.std(ddof=1)*np.sqrt(252))
        m = row['windows']['evaluation']
        table.append(dict(scenario=key, **m, bil_relative_sharpe=annual_excess/vol if vol > 1e-12 else None,
                          annual_excess_vs_bil=annual_excess, **inference.get(key, {})))
    pd.DataFrame(table).to_csv(dest/'all-scenarios.csv', index=False)
    pd.DataFrame([dict(scenario=k, window=w, **m) for k, row in results.items()
                  for w, m in row['windows'].items()]).to_csv(dest/'period-metrics.csv', index=False)
    lookup = {r['scenario']: r for r in table}
    labels = [('FR25__monthly__c5d0', 'FR25 current-recipe control'),
              ('blend_control__event__c5d0', '80% FR25 / 20% M1 control'),
              ('M1__event__c5d0', 'Full-pool M1 control'),
              ('Ladaptive-V1-H1__selection__event__c5d0', 'Adaptive selection factor'),
              ('Ladaptive-V1-H1__trading__event__c5d0', 'Adaptive standalone trading'),
              ('Ladaptive-V1-H1__tilt__event__c5d0', '80% FR25 / 20% adaptive breakout'),
              ('URTH__c5d0', 'URTH buy-hold'), ('BIL__c5d0', 'BIL buy-hold')]
    def row_html(key, label):
        v = lookup[key]
        x = v['bil_relative_sharpe']
        return f'<tr><td>{label}</td><td>{v["cagr"]:.2%}</td><td>{v["sharpe"]:.3f}</td><td>{x:.3f}</td><td>{v["max_drawdown"]:.2%}</td><td>{v["annual_turnover"]:.2f}</td><td>{v["annual_cost_bps"]:.1f}</td><td>{v["average_exposure"]:.1%}</td></tr>' if x is not None else f'<tr><td>{label}</td><td>{v["cagr"]:.2%}</td><td>{v["sharpe"]:.3f}</td><td>reference</td><td>{v["max_drawdown"]:.2%}</td><td>{v["annual_turnover"]:.2f}</td><td>{v["annual_cost_bps"]:.1f}</td><td>{v["average_exposure"]:.1%}</td></tr>'
    stress = []
    for app in ('selection', 'trading', 'tilt'):
        for cost, delay in itertools.product(p['cost_bps'], p['additional_delay_sessions']):
            m = lookup[f'Ladaptive-V1-H1__{app}__event__c{cost}d{delay}']
            stress.append(f'<tr><td>{app}</td><td>{cost}</td><td>{delay}</td><td>{m["cagr"]:.2%}</td><td>{m["sharpe"]:.3f}</td><td>{m["max_drawdown"]:.2%}</td></tr>')
    chosen_rows = ''.join(f'<tr><td>{app}</td><td>{y}</td><td>{html.escape(v["selected"])}</td><td>{len(v["passing"])}</td><td>{len(v["neighbor_supported"])}</td></tr>' for app, rows in selections.items() for y, v in rows.items())
    wf_rows = ''.join(f'<tr><td>{key.removesuffix("__c5d0")}</td><td>{v["windows"]["evaluation"]["cagr"]:.2%}</td><td>{v["windows"]["evaluation"]["sharpe"]:.3f}</td><td>{v["windows"]["evaluation"]["max_drawdown"]:.2%}</td></tr>'
                      for key, v in wf.items() if key.endswith('__c5d0'))
    case_rows, cases = [], {}
    all_episodes = study.read(root/'episodes.json')['Ladaptive-V1-H1']
    for s in ('GLD', 'USO', 'SOXX', 'XLE'):
        if s not in all_episodes:
            continue
        cases[s] = [r for r in all_episodes[s]['episodes'] if r['entry_date'] and r['entry_date'] >= p['start']]
        for r in cases[s]:
            ret = f'{r["gross_return"]:.2%}' if r['gross_return'] is not None else 'open'
            case_rows.append(f'<tr><td>{s}</td><td>{r["duration"]}</td><td>{r["entry_date"]}</td><td>{r["exit_date"] or "open"}</td><td>{ret}</td><td>{r["exit_reason"]}</td></tr>')
    primary = lookup['Ladaptive-V1-H1__trading__event__c5d0']
    tilt = lookup['Ladaptive-V1-H1__tilt__event__c5d0']
    fr25 = lookup['FR25__monthly__c5d0']
    positive = sum(v['family_positive'] for v in inference.values())
    summary = dict(primary_trading=primary, primary_tilt=tilt, fr25=fr25,
                   selections=selections, walk_forward=wf, family_positive=positive, cases=cases,
                   episodes=episodes, studied_assets=len(a['symbols']), scenarios=len(results),
                   verdict='Research prototype; no promotion. Judge matched return/drawdown and cash-relative results, not zero-risk-free Sharpe alone.')
    study.write(dest/'summary.json', summary)
    study.write(root/'analysis_summary.json', summary)
    attribution = []
    classes = {s: group for group, members in study.read(root/'construction.json')['classes'].items() for s in members}
    for app in ('selection', 'trading', 'tilt'):
        path = np.load(root/'paths'/f'Ladaptive-V1-H1__{app}__event__c5d0.npz')
        pnl = path['contribution'][mask].sum(axis=0)
        for s, value in zip(a['symbols'].tolist()+['URTH'], pnl, strict=True):
            attribution.append(dict(application=app, symbol=s, asset_class=classes.get(s, 'benchmark'),
                                    net_pnl_usd=float(value), period='2024-01-01 through 2026-10-12'))
    pd.DataFrame(attribution).to_csv(dest/'constituent-attribution.csv', index=False)
    duration_rows = ''.join(f'<tr><td>{k}</td><td>{v["entries"]}</td><td>{v["closed"]}</td><td>{v["win_rate"]:.1%}</td><td>{v["median_gross_return"]:.2%}</td><td>{v["median_hold_sessions"]:.0f}</td></tr>' for k, v in episodes.items())
    limits = ''.join('<li>'+html.escape(x)+'</li>' for x in p['limitations'])
    source_text = '<a href="https://onlinelibrary.wiley.com/doi/abs/10.1111/j.1540-6261.1992.tb04681.x">Brock, Lakonishok &amp; LeBaron: trading-range rules</a>; <a href="https://www.cmegroup.com/education/courses/technical-analysis/technical-patterns-reversals">CME: price/volume confirmation</a>; <a href="https://www.uscfinvestments.com/uso">USCF: USO fund objective</a>. These motivate definitions; they do not establish profitability of this implementation.'
    content = f'''<!doctype html><html><head><meta charset="utf-8"><title>Adaptive range-breakout research</title>
<style>body{{font:16px/1.55 system-ui;color:#17324f;max-width:1250px;margin:40px auto;padding:0 24px;background:#f8fafc}}h1{{font-size:36px}}h2{{margin-top:42px}}p,li{{max-width:1050px}}table{{border-collapse:collapse;width:100%;font-size:13px;background:white}}th,td{{padding:8px 10px;border-bottom:1px solid #dbe4ed;text-align:right}}th:first-child,td:first-child{{text-align:left}}img{{width:100%;background:white}}code{{background:#e2e8f0;padding:2px 5px}}.note{{padding:18px;background:#e6f1f0;border-left:4px solid #0d9488}}.scroll{{overflow-x:auto}}</style></head><body>
<h1>Adaptive range → breakout → hold → exit</h1><p>{len(a['symbols'])} supported ETFs · {len(results)} fixed portfolio scenarios + 18 continuous walk-forward replays · audited adjusted prices / raw volume · USD research · 2021–October 12, 2026</p>
<div class="note"><strong>The factor is implemented and tested; an optimal peak exit has not been established.</strong> The primary adaptive standalone rule earned {primary['cagr']:.2%} annualized in 2024+ with {primary['max_drawdown']:.2%} maximum drawdown and {primary['average_exposure']:.1%} average exposure. Its 20% FR25 blend earned {tilt['cagr']:.2%}, compared with {fr25['cagr']:.2%} for FR25. {positive}/72 candidate/control contrasts have a positive simultaneous mean-return lower bound. No monitoring, allocation or execution authority changes.</div>
<h2>What is detected mathematically?</h2><p>For each candidate length L ∈ {{42,63,126,252,504,756}}, use only the previous L completed closes. Let x = log(adjusted close), W = q95(x)−q05(x), and b = min(63,max(10,⌊L/4⌋)). A stable range satisfies W ≤ log(1.25), |median(last b x)−median(first b x)| ≤ W/2, and recent return volatility ≤ whole-window volatility. Choose the longest qualifying complete L. This is a price regime, not evidence that fundamentals are stable.</p>
<p>Freeze U = exp(q95), D = exp(q05) and ATR20 when price first crosses U+0.5 ATR. Require three consecutive closes above that frozen threshold. The volume version also requires mean raw volume over those three closes ≥ 1.2 times its pre-breakout 63-day median. Enter at the next open, never the confirming close. Confirmation reduces noise but cannot rule out false breakouts.</p>
<p>At virtual fill E, initial stop S = max(E−2 ATRentry, U−ATRentry). Each subsequent close ratchets Sₜ = max(Sₜ₋₁, Hₜ−k ATR20,t), where H is the highest close since entry (initialized at E). Normally k=4. When close ≥ U+3 ATRentry, is within one current ATR of H, and volume ≥ 2× its prior63 median, the overheated state becomes permanent and k=2. Exit after a close below S or U−0.5 ATRentry; also exit after 21 sessions without ever gaining one entry ATR. Fill the next available open. No assumed fill at a peak or stop price. Wait 21 sessions and require a new range for another entry. Below the frozen lower band is only an oversold diagnostic, not a bottom-buy signal.</p>
<p>Selection adds the active factor's rank to the full-pool momentum rank. Standalone trading holds up to six active breakouts with inverse-volatility weights; unused slots stay cash. Tilt combines 80% of the frozen FR25 monthly target with 20% of this sleeve. Event timing uses monthly anchors plus L1 theoretical-versus-last-adopted distance &gt;0.10 including cash, with explicit breakout-exit overrides. Monthly controls defer every trade until the next monthly adoption.</p>
<h2>Chronological comparison: January 2024–October 2026</h2><p>5 bp per traded side, next-open fills. Sharpe uses zero risk-free return, matching the frozen research contract. BIL-relative Sharpe is shown alongside it because bill-heavy portfolios can otherwise look misleadingly strong. Cash earns zero; the standalone strategy's lower drawdown partly reflects lower exposure. Calmar and all periods/costs are in the downloadable scenario and period tables.</p>
<div class="scroll"><table><tr><th>Portfolio</th><th>CAGR</th><th>Sharpe, rf=0</th><th>BIL-relative</th><th>Max DD</th><th>Turnover/year</th><th>Cost bp/year</th><th>Exposure</th></tr>{''.join(row_html(k,l) for k,l in labels)}</table></div>
<img src="portfolio.png" alt="Full-period NAV and drawdown comparisons">
<h2>Gold, oil and semiconductor cases</h2><p>Every primary-rule episode in these displayed assets since 2021 is listed, including losers and missed portions of rallies. Case returns are virtual single-asset gross entry-to-exit returns, not portfolio contributions. USO is a futures fund, not spot oil. Fixed 1/2-year ranges remain controls; adaptive durations were specified before performance testing.</p><img src="cases.png" alt="Causal adaptive entries, range bands and trailing exits for gold, oil, semiconductors and energy equities">
<table><tr><th>ETF</th><th>Range sessions</th><th>Entry open</th><th>Exit open</th><th>Gross return</th><th>Exit reason</th></tr>{''.join(case_rows)}</table>
<h2>False signals and duration controls</h2><p>V1 requires volume confirmation; H1 tightens the trail after overheating. Entry counts are virtual signal episodes, not executed portfolio trades. Win rate requires gross return &gt;0.10%, a simple round-trip 5 bp diagnostic; actual portfolio costs use every realized fill. Neither count nor win rate is a strategy gate.</p>
<table><tr><th>Variant</th><th>Entries</th><th>Closed</th><th>Win rate</th><th>Median gross return</th><th>Median hold sessions</th></tr>{duration_rows}</table>
<h2>Costs and additional execution delay</h2><table><tr><th>Use</th><th>Cost bp/side</th><th>Extra sessions</th><th>CAGR</th><th>Sharpe</th><th>Max DD</th></tr>{''.join(stress)}</table>
<h2>Walk-forward decisions</h2><p>Each annual selection uses only the preceding three calendar years. The registered Sharpe, return/drawdown, cost/delay and neighboring-variant gates apply. The portfolio is replayed continuously through changes; NAV is never spliced. These are chronological tests on already inspected market history, not a pristine prospective holdout.</p>
<table><tr><th>Use</th><th>Test year</th><th>Selected using earlier years</th><th>Passing variants</th><th>With passing neighbor</th></tr>{chosen_rows}</table>
<p>Continuous selected portfolio, evaluated in 2024+ at 5 bp:</p><table><tr><th>Walk-forward use</th><th>CAGR</th><th>Sharpe, rf=0</th><th>Max DD</th></tr>{wf_rows}</table>
<h2>Engineering validation and disposition</h2><p>Signal tests check future-data independence, three-close confirmation, rejected one-day breaks, missing raw volume, adaptive duration, ratcheting stops, gap fills and cash-inclusive adoption. The original-pool FR25, primary trading and primary tilt replays matched independent native Windows LEAN exactly; the USO-extension primary trading replay also matched to the cent. Workers retained accepted runtime hashes and two-CPU/4-GiB isolation. This validates implementation/accounting, not the economic hypothesis.</p><p>Keep this as a research prototype. The primary standalone rule has a positive later-period result but weaker full-history results and material cost/delay sensitivity. The tilt gives up return versus FR25 and does not show a reliable increment over the construction-matched blend. Inspect missed semiconductor and gold trends before specifying a new version; do not retune this version to the illustrated peaks. A future version needs a newly registered rule and genuinely later observations.</p>
<h2>Input and interpretation limits</h2><ul>{limits}</ul><p>The USO extension preserves the original 50 histories unchanged and binds USO to a second verified published batch, truncated to the same October 12 date. It adds no new rule parameters and grants no trading admission. BWX and XOP remain held for listing identity conflicts; CPER has unsupported raw volume. DBO/BNO/USL/OILK and alternative semiconductor/gold funds need usable published inputs before a further expansion.</p>
<p>Download <a href="all-scenarios.csv">all scenarios</a>, <a href="period-metrics.csv">annual, training and full-period metrics</a>, <a href="constituent-attribution.csv">full constituent/class attribution</a> and <a href="summary.json">machine-readable summary</a>. Input/code hashes, full protocols, native parity and retained recipe are recorded in the repository study directory.</p><p>{source_text}</p></body></html>'''
    (dest/'index.html').write_text(content, encoding='utf-8')
    study.write(root/'analysis_receipt.json', dict(analysis_code_sha256=study.digest(__file__),
                protocol_sha256=study.digest(root/'protocol.json'), input_manifest_sha256=study.digest(root/'input_manifest.json'),
                scenario_count=486, walk_forward_replays=18, output_files={f.name: study.digest(f) for f in dest.iterdir() if f.is_file()}))
    print('Report', dest/'index.html', 'family-positive', positive, 'walk-forward', selections, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path('var/research/range-breakout-uso-20261018-v1'))
    parser.add_argument('--dest', type=Path, default=DEST)
    args = parser.parse_args()
    report(args.root, args.dest)
