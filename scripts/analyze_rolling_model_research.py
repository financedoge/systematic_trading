"""Verify, report and optionally archive the complete fixed rolling-model study."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import html
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from analyze_flow_concentration_research import metrics, return_vector, block_audit, price_benchmark, exposure_stats
from run_rolling_model_research import read, verify_files, trial_matrix
from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, verify_bundle, write_json
from systematic_trading.lean.registry import register_run
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.analytics_projection import observation
from systematic_trading.storage.postgres import PostgresStore


def paired_stats(candidate, baseline, start, end):
    dates = [r['date'] for r in baseline['nav']]
    if [r['date'] for r in candidate['nav']] != dates:
        raise ValueError('Paired comparison dates differ')
    mask = np.array([start <= d <= end for d in dates])
    active = (return_vector(candidate['nav'])-return_vector(baseline['nav']))[mask]
    vol = np.std(active, ddof=1)*np.sqrt(252) if len(active) > 1 else 0
    return dict(information_ratio=float(active.mean()*252/vol) if vol > 1e-14 else 0.,
                annual_active_return=float(active.mean()*252) if len(active) else 0.,
                tracking_error=float(vol))


def decision_changes(candidate, baseline):
    differences = []
    for day, row in candidate['decisions'].items():
        original = baseline['decisions'][day]
        a = {t['symbol']: float(t['target_weight']) for t in row['targets']}
        b = {t['symbol']: float(t['target_weight']) for t in original['targets']}
        differences.append(sum(abs(a.get(s, 0)-b.get(s, 0)) for s in a.keys() | b.keys()))
    return dict(months=len(differences), changed=sum(d > 1e-8 for d in differences),
                mean_one_way_active_weight=float(np.mean(differences)/2),
                max_one_way_active_weight=float(max(differences, default=0)/2))


def summarize(root):
    verify_files(root, 'inputs.json')
    verify_files(root, 'models.json')
    protocol, progress, trials = [read(root/(n+'.json')) for n in ('protocol', 'progress', 'trials')]
    if not progress['complete'] or set(progress['passed']) != set(trial_matrix(protocol)) or trials != trial_matrix(protocol):
        raise ValueError('Every declared trial must finish before final analysis')
    windows = {'full': (protocol['long_start'], protocol['end']),
               '2016_19': ('2016-01-01', '2019-12-31'), '2020_22': ('2020-01-01', '2022-12-31'),
               '2023_plus': ('2023-01-01', protocol['end']),
               **{str(y): (f'{y}-01-01', f'{y}-12-31') for y in range(2016, 2027)}}
    economies, results = {}, {}
    for name, cfg in trials.items():
        bundle, output = root/'datasets'/name, root/'runs'/name
        verify_bundle(bundle)
        receipt, parity = read(output/'run.json'), read(output/'parity.json')
        if receipt['status'] != 'succeeded' or not parity['passed'] or sha256(bundle/'manifest.json') != receipt['manifest_sha256']:
            raise ValueError('Invalid native receipt: '+name)
        for relative, expected in receipt['artifacts'].items():
            if sha256(output/relative) != expected:
                raise ValueError('Native output changed: '+name+'/'+relative)
        economy = economies[name] = read(output/'economic.json')
        quotes = read(bundle/'quotes.json')
        results[name] = dict(windows={w: m for w, bounds in windows.items() if (m := metrics(economy, *bounds))},
                             exposure=exposure_stats(economy, quotes), engine_seconds=receipt['elapsed_seconds'],
                             parity_passed=True, economic_sha256=receipt['economic_sha256'])
    for name, cfg in trials.items():
        comparator = cfg.get('comparator', 'long_sota' if cfg.get('long') else 'sota')
        base = economies[comparator]
        results[name]['comparator'] = comparator
        results[name]['decision_changes'] = decision_changes(economies[name], base)
        results[name]['vs_sota'] = {}
        for w, m in results[name]['windows'].items():
            b = results[comparator]['windows'][w]
            results[name]['vs_sota'][w] = dict(cagr_delta=m['cagr']-b['cagr'],
                sharpe_delta=m['sharpe']-b['sharpe'], drawdown_delta=m['max_drawdown']-b['max_drawdown'],
                **paired_stats(economies[name], base, *windows[w]))
    primary = [f'{f}_{y}y' for f in protocol['families'] for y in protocol['window_years']]
    inference = {}
    for label, prefix, base in [('post2023', '', 'sota'), ('long', 'long_', 'long_sota')]:
        difference = np.column_stack([return_vector(economies[prefix+n]['nav'])-return_vector(economies[base]['nav']) for n in primary])
        inference[label] = {str(block): block_audit(difference, primary, replicates=5000, block=block, seed=protocol['seed'])
                            for block in (63, 126)}
    fx, urth = read(root/'fx.json'), read(root/'urth.json')
    external = {}
    for key in ('sota', 'long_sota'):
        dates = [r['date'] for r in economies[key]['nav']]
        economic = price_benchmark(urth, fx, dates)
        external[key] = {w: metrics(economic, *b) for w, b in windows.items()} if economic else {'unavailable': 'Missing audited dates'}
    fits = {}
    for name in primary:
        schedule = read(root/'models'/(name+'.json'))
        values = list(schedule.values())
        fits[name] = dict(fits=len(values), samples_min=min(v['training_samples'] for v in values),
            samples_max=max(v['training_samples'] for v in values), months_min=min(v['training_months'] for v in values),
            months_max=max(v['training_months'] for v in values), first_fit=min(schedule), last_fit=max(schedule),
            native_prediction_max_error=max(v['details'].get('native_prediction_max_error', 0) for v in values))
    # The declared frozen-family and no-tree controls distinguish rolling value
    # from merely replacing (or removing) the deployed tree.
    contrasts = {}
    for group, pairs in {
        'rolling_vs_frozen_family': [(n, n.split('_')[0]+'_frozen') for n in primary if not n.startswith('tree_')],
        'rolling_vs_no_tree': [(n, 'no_tree') for n in primary],
    }.items():
        difference = np.column_stack([return_vector(economies[n]['nav'])-return_vector(economies[b]['nav']) for n, b in pairs])
        contrasts[group] = dict(pairs={n: dict(comparator=b,
            cagr_delta=results[n]['windows']['full']['cagr']-results[b]['windows']['full']['cagr'],
            **paired_stats(economies[n], economies[b], protocol['start'], protocol['end'])) for n, b in pairs},
            inference={str(block): block_audit(difference, [n for n, b in pairs], replicates=5000,
                block=block, seed=protocol['seed']) for block in (63, 126)})
    summary = dict(protocol=protocol, trials=results, inference=inference, urth=external, fits=fits,
                   contrasts=contrasts, primary=primary, complete=True, promotion_eligible=False)
    write_json(root/'summary.json', summary)
    fields = ['trial', 'window', 'cagr', 'sharpe', 'max_drawdown', 'annual_traded_notional_over_nav',
              'fee_cnh', 'cagr_delta', 'information_ratio', 'drawdown_delta']
    with (root/'metrics.csv').open('w', encoding='utf8', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=fields)
        writer.writeheader()
        for name, result in results.items():
            for window, m in result['windows'].items():
                row = dict(trial=name, window=window, **m, **result['vs_sota'][window])
                writer.writerow({k: row[k] for k in fields})
    return summary, economies


def charts(root, summary, economies):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    colors = {'tree': '#138a72', 'forest': '#3973b9', 'xgboost': '#b155a6'}
    names = summary['primary']
    dates = [datetime.fromisoformat(r['date']) for r in economies['sota']['nav']]
    fig, axes = plt.subplots(2, 1, figsize=(12, 9), sharex=True)
    baseline = np.array([float(r['nav']) for r in economies['sota']['nav']])
    axes[0].plot(dates, baseline/1e6, color='#172b46', lw=2.5, label='Frozen SOTA')
    for name in names:
        values = np.array([float(r['nav']) for r in economies[name]['nav']])
        kw = dict(color=colors[name.split('_')[0]], ls='-' if '1y' in name else '--', label=name.replace('_', ' '))
        axes[0].plot(dates, values/1e6, **kw)
        axes[1].plot(dates, values/baseline-1, **kw)
    axes[0].set_title('Rolling training versus the frozen tree | 2023–2026', loc='left', weight='bold', fontsize=17)
    axes[0].set_ylabel('Portfolio value / initial capital')
    axes[0].legend(ncol=3, frameon=False)
    axes[1].set_ylabel('Relative wealth versus frozen SOTA')
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].axhline(0, color='#7c899b', lw=.7)
    for ax in axes:
        ax.grid(alpha=.2)
    fig.text(.08, .01, 'Audited revised prices; legacy FX uncertified. Monthly next-open simulation, 5 bps fees. Exploratory reused history.', fontsize=9)
    fig.tight_layout(rect=(0, .03, 1, 1))
    fig.savefig(root/'performance.png', dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    years = [str(y) for y in range(2016, 2027)]
    grid = np.array([[summary['trials']['long_'+n]['vs_sota'][y]['cagr_delta']*100 for y in years] for n in names])
    limit = max(.1, float(np.max(np.abs(grid))))
    plot = axes[0].imshow(grid, cmap='RdYlGn', vmin=-limit, vmax=limit, aspect='auto')
    axes[0].set_xticks(range(len(years)), [y[2:] for y in years])
    axes[0].set_yticks(range(len(names)), [n.replace('_', ' ') for n in names])
    axes[0].set_title('Annualized return difference, percentage points\nLong runs versus tracked SOTA reconstruction')
    for i in range(len(names)):
        for j in range(len(years)):
            axes[0].text(j, i, f'{grid[i,j]:+.1f}', ha='center', va='center', fontsize=8)
    fig.colorbar(plot, ax=axes[0], shrink=.6)
    audit = summary['inference']['post2023']['63']['trials']
    values = np.array([audit[n]['annual_arithmetic_excess'] for n in names])*100
    bounds = np.array([audit[n]['ci95'] for n in names])*100
    axes[1].errorbar(values, np.arange(len(names)), xerr=np.array([values-bounds[:, 0], bounds[:, 1]-values]), fmt='o', color='#3973b9', capsize=4)
    axes[1].set_yticks(range(len(names)), [n.replace('_', ' ') for n in names])
    axes[1].axvline(0, color='#7c899b', lw=.8)
    axes[1].set_title('2023+ active return: paired 95% interval\n63-session blocks, 5,000 resamples')
    axes[1].set_xlabel('Annual arithmetic excess return, percentage points')
    fig.tight_layout()
    fig.savefig(root/'robustness.png', dpi=170)
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    control = summary['contrasts']['rolling_vs_frozen_family']
    control_names = list(control['pairs'])
    for name in control_names:
        family = name.split('_')[0]
        values = np.array([float(r['nav']) for r in economies[name]['nav']])
        frozen = np.array([float(r['nav']) for r in economies[family+'_frozen']['nav']])
        axes[0].plot(dates, values/frozen-1, color=colors[family], ls='-' if '1y' in name else '--', label=name.replace('_', ' '))
    axes[0].axhline(0, color='#7c899b', lw=.8)
    axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].legend(frameon=False)
    axes[0].set_title('Rolling versus the same frozen model family')
    axes[0].set_ylabel('Relative wealth')
    audit = control['inference']['63']['trials']
    values = np.array([audit[n]['annual_arithmetic_excess'] for n in control_names])*100
    bounds = np.array([audit[n]['ci95'] for n in control_names])*100
    axes[1].errorbar(values, np.arange(len(control_names)), xerr=np.array([values-bounds[:, 0], bounds[:, 1]-values]),
                     fmt='o', color='#3973b9', capsize=4)
    axes[1].set_yticks(range(len(control_names)), [n.replace('_', ' ') for n in control_names])
    axes[1].axvline(0, color='#7c899b', lw=.8)
    axes[1].set_title('Increment from rolling: paired 95% interval')
    axes[1].set_xlabel('Annual arithmetic excess return, percentage points')
    fig.tight_layout()
    fig.savefig(root/'rolling_increment.png', dpi=170)
    plt.close(fig)


def report(root, summary):
    trials, primary = summary['trials'], summary['primary']
    best = max(primary, key=lambda n: trials[n]['windows']['full']['cagr'])
    best_cagr = trials[best]['windows']['full']['cagr']
    base_cagr = trials['sota']['windows']['full']['cagr']
    lines = ['# Rolling tree, forest and XGBoost research', '',
        'All 41 predeclared native LEAN runs passed Python parity. No model has been promoted.', '',
        f"Best primary historical result: **{best.replace('_', ' ')}**, {best_cagr:.2%} CAGR versus {base_cagr:.2%} for frozen SOTA ({(best_cagr-base_cagr)*100:+.3f} percentage points annually).",
        '',
        'The one-year ensembles are the strongest candidates in this experiment. Separate frozen-ensemble and tree-free controls below distinguish changing the model from the value of rolling refits. The longer history, period differences and reused sample limit the conclusion; retain SOTA pending prospective evidence.', '',
        '## Main comparison: January 3, 2023–September 24, 2026', '',
        '| Model | CAGR | Sharpe | Max drawdown | CAGR vs SOTA | Active IR | Adjusted p |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name in ['sota', *primary, 'forest_frozen', 'xgboost_frozen', 'no_tree', 'risk_parity']:
        m, delta = trials[name]['windows']['full'], trials[name]['vs_sota']['full']
        audit = summary['inference']['post2023']['63']['trials'].get(name)
        p = f"{audit['max_t_family_adjusted_p']:.3f}" if audit else '—'
        lines.append(f"| {name} | {m['cagr']:.2%} | {m['sharpe']:.3f} | {m['max_drawdown']:.2%} | {delta['cagr_delta']*100:+.3f} pp | {delta['information_ratio']:+.3f} | {p} |")
    external = summary['urth']['sota'].get('full')
    if external:
        lines += ['', f"Audited URTH buy-and-hold context: CAGR {external['cagr']:.2%}, Sharpe {external['sharpe']:.3f}, max drawdown {external['max_drawdown']:.2%}. Same initial capital/currency and entry fee; separate deterministic benchmark accounting."]
    lines += ['', '## Robustness of all six rolling models', '',
              '| Model | Long CAGR delta | 2020 delta | 2022 delta | High-cost delta | Delay delta | Seed CAGR range |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name in primary:
        long = trials['long_'+name]['vs_sota']
        seed_values = [trials[n]['windows']['full']['cagr'] for n in trials if n == name or n.startswith(name+'_seed')]
        lines.append(f"| {name} | {long['full']['cagr_delta']*100:+.3f} pp | {long['2020']['cagr_delta']*100:+.3f} pp | {long['2022']['cagr_delta']*100:+.3f} pp | {trials[name+'__cost45bps']['vs_sota']['full']['cagr_delta']*100:+.3f} pp | {trials[name+'__delay1']['vs_sota']['full']['cagr_delta']*100:+.3f} pp | {min(seed_values):.2%}–{max(seed_values):.2%} |")
    lines += ['', '## Does rolling add value beyond changing the model?', '',
              '| Rolling model | Frozen-family comparator | CAGR delta | Active IR | Annual active-return 95% interval | Adjusted p |',
              '| --- | --- | ---: | ---: | ---: | ---: |']
    contrast = summary['contrasts']['rolling_vs_frozen_family']
    for name, pair in contrast['pairs'].items():
        audit = contrast['inference']['63']['trials'][name]
        lo, hi = audit['ci95']
        lines.append(f"| {name} | {pair['comparator']} | {pair['cagr_delta']*100:+.3f} pp | {pair['information_ratio']:+.3f} | {lo*100:+.3f} to {hi*100:+.3f} pp | {audit['max_t_family_adjusted_p']:.3f} |")
    lines += ['', 'These controls were declared before the runs. The four rolling-versus-frozen-family contrasts use their own max-t adjustment. The complete JSON also includes paired comparisons against tree-free SOTA. A gain versus the deployed tree alone does not establish that periodic refitting is responsible.']
    lines += ['', '## Method and interpretation', '',
        '- One- and two-calendar-year training windows; monthly fresh fits. Feature histories may reach before the training window for warmup. Labels ending at the fit close are embargoed; all retained outcomes end earlier.',
        '- Identical 26 features and next-month relative-return labels. Only the tree ranking overlay changes; pool selection, risk parity, relative momentum, adaptive trend and execution rules remain fixed.',
        '- Depth 3/minimum leaf 25 for CART. Forest: 100 depth-3 trees. XGBoost: 100 depth-3 rounds, learning rate 0.03, minimum child weight 25, regularization 10. All settings and seeds fixed before results.',
        '- Each primary run starts with fresh CNH 1,000,000 in January 2023. Long runs start separately in 2016; the comparator uses annual causal fits before 2023 and the deployed frozen tree thereafter.',
        '- Base fees 5 bps/no slippage. Cost stress uses 25 bps fees plus 20 bps slippage for both sides of the comparison. Delay stress moves every execution one session. Seed checks use 17 and 97.',
        '- Annual turnover is absolute traded notional divided by prior NAV, annualized; Sharpe uses a zero hurdle. Calendar 2026 is partial and annualized. Metrics CSV includes every year, fees, turnover and paired IR.',
        '- The six primary candidates share max-t multiple-comparison adjustment. Confidence intervals use paired 63- and 126-session blocks; these do not make previously inspected historical data an untouched holdout.',
        '- This tests periodic model replacement inside the current bounded tilt. It does not test replacing the complete allocation strategy with unconstrained machine learning.',
        '', '### Training sample sizes', '']
    for name, fit in summary['fits'].items():
        lines.append(f"- {name}: {fit['fits']} monthly fits, {fit['samples_min']}–{fit['samples_max']} asset-months ({fit['months_min']}–{fit['months_max']} distinct months) per fit.")
    lines += ['', '### Data limitations', '', summary['protocol']['limitations'], '', summary['protocol']['etf_basis'], '',
        '## Decision flow', '',
        'Audited batch and hashes → completed prior-session features → trailing training origins → completed-label embargo → monthly fit → frozen portable model → unchanged SOTA pool and bounded tree tilt → relative/adaptive overlays → next-open simulated fills → CNH NAV and matched benchmarks.', '',
        '## Replay and evidence', '',
        '`protocol.json`, `inputs.json`, `training_records.json`, `models/`, `models.json`, `trials.json`, `datasets/`, `runs/`, `summary.json`, and `metrics.csv` retain every trial and causal fit. Provider archives are not research inputs.', '',
        'Model documentation: [scikit-learn forest](https://scikit-learn.org/1.8/modules/generated/sklearn.ensemble.RandomForestRegressor.html), [XGBoost](https://xgboost.readthedocs.io/en/stable/python/python_intro.html).', '']
    text = '\n'.join(lines)
    (root/'report.md').write_text(text, encoding='utf8')
    tables = []
    for title, first, last in [('Main results', lines.index('| Model | CAGR | Sharpe | Max drawdown | CAGR vs SOTA | Active IR | Adjusted p |'),
                               lines.index('## Robustness of all six rolling models'))]:
        rows = [line.strip('|').split('|') for line in lines[first:last] if line.startswith('|') and '---' not in line]
        tables.append('<h2>'+title+'</h2><table>'+''.join('<tr>'+''.join('<td>'+html.escape(c.strip())+'</td>' for c in r)+'</tr>' for r in rows)+'</table>')
    page = '<!doctype html><meta charset="utf-8"><title>Rolling model research</title><style>body{font:16px system-ui;max-width:1200px;margin:40px auto;padding:0 24px;color:#172b46}table{border-collapse:collapse;width:100%}td{padding:9px;border-bottom:1px solid #dfe5ec;text-align:right}td:first-child{text-align:left}tr:first-child{font-weight:bold}img{width:100%}pre{white-space:pre-wrap;font:14px/1.6 system-ui}a{color:#3973b9}</style><h1>Rolling tree, forest &amp; XGBoost</h1><p>Audited-input research · 41 native LEAN runs · no promotion</p>'+''.join(tables)+'<img src="performance.png"><img src="robustness.png"><img src="rolling_increment.png"><p><a href="metrics.csv">All trial metrics (CSV)</a> · <a href="summary.json">Full numerical evidence (JSON)</a></p><pre>'+html.escape(text)+'</pre>'
    (root/'report.html').write_text(page, encoding='utf8')


def publish(root, summary):
    settings = AppSettings()
    store = PostgresStore.from_settings(settings)
    registered = [register_run(store, root/'runs'/name) for name in summary['trials']]
    analytics = AnalyticsStore.from_settings(settings)
    analytics.client.timeout_seconds = 120
    observations = []
    for name, result in summary['trials'].items():
        for row in read(root/'runs'/name/'economic.json')['nav']:
            observations.append(observation(name+'/'+row['date'], 'rolling_model_nav', name, row, row['date']))
        for window, m in result['windows'].items():
            observations.append(observation(name+'/metrics/'+window, 'rolling_model_metrics', name,
                                dict(window=window, **m, **result['vs_sota'][window])))
    docs = [dict(point_key=name, media_type='application/json' if name.endswith('.json') else 'text/markdown',
                 payload=(root/name).read_text(encoding='utf8'))
            for name in ('protocol.json', 'summary.json', 'inputs.json', 'models.json', 'analysis_manifest.json', 'report.md')]
    version = digest(encode(read(root/'analysis_manifest.json')))
    analytics.publish('research/rolling-models-v1', version, observations, docs,
        provenance=dict(root=str(root), batch=summary['protocol']['batch'], promotion_eligible=False))
    write_json(root/'publication.json', dict(version=version, registered=registered, nav_and_metrics=len(observations), documents=len(docs)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--publish', action='store_true')
    args = parser.parse_args()
    summary, economies = summarize(args.root)
    charts(args.root, summary, economies)
    report(args.root, summary)
    output_names = ['summary.json', 'metrics.csv', 'report.md', 'report.html', 'performance.png', 'robustness.png', 'rolling_increment.png']
    write_json(args.root/'analysis_manifest.json', {n: sha256(args.root/n) for n in output_names})
    if args.publish:
        publish(args.root, summary)
    print(json.dumps(dict(complete=True, report=str(args.root/'report.html'), trials=len(summary['trials']))))
