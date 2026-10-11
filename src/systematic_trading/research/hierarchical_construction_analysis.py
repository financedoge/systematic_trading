"""P4.16b hierarchical construction: analysis, family-adjusted tests, verdict and report.

Reads this study's own replays for the two hierarchical arms and the pinned P4.16
replays for the pooled control and the published references. Nothing here re-tunes the
rule, changes a monitored strategy, an allocation or a broker record.
"""
from pathlib import Path
import html

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.expanded_economics import job_name
from systematic_trading.research.momentum_replay import read_json, verify_usd_bundle
from systematic_trading.research.sleeve_construction_analysis import ci, num, pct, pool_vs_control, table
from systematic_trading.research.sleeve_construction_study import LABELS as SLEEVE_LABELS
from systematic_trading.research.hierarchical_construction_study import (ARMS, BOOTSTRAP_BLOCKS,
    BOOTSTRAP_REPLICATIONS, COMPARISONS, CONTROLS, CONTROL_LABELS, COST_BPS, COSTS, DELAYS, LABELS, PARENT,
    SEED, SLOTS_PER_CLASS, WINDOWS)
from systematic_trading.research.sleeve_construction_study import SLEEVES

PRIMARY = ('HIER-K2', 'POOL')
SECONDARY = ('HIER-K3', 'POOL')
K_CONTRAST = ('HIER-K3', 'HIER-K2')
# The construction-matched pooled arm is pinned in the P4.16 root, not replayed here;
# the published references are replayed in this root and checked against the parent.
PARENT_ONLY = ('POOL',)
LABELS_ALL = {**LABELS, **CONTROL_LABELS, 'POOL': SLEEVE_LABELS['POOL']}
REFERENCE_ROOT = PARENT
RULES = dict(
    supported='positive mean-return interval at a registered block with Holm p<0.05 across the registered family, '
              'AND a higher Sharpe and a higher Calmar than the control in the primary window',
    inconclusive='a positive point estimate that does not clear the family-adjusted interval, or intervals that span '
                 'zero',
    rejected='no positive family-adjusted interval and non-positive point estimates')


def jobs_for(arms):
    return [(arm, cost, delay, window) for arm in arms for cost in COSTS for delay in DELAYS for window in WINDOWS]


def load_replay(root, job):
    """Verify one replay against its bundle and recompute its statistics."""
    from systematic_trading.research.momentum_analysis import statistics
    name = job_name(job)
    path, bundle = Path(root) / 'python' / (name + '.json'), Path(root) / 'bundles' / name
    verify_usd_bundle(bundle)
    if read_json(path.with_suffix('.receipt.json')) != dict(
            sha256=sha256(path), manifest_sha256=sha256(bundle / 'manifest.json')):
        raise ValueError('Replay changed ' + name)
    economic = read_json(path)
    s = statistics(economic, read_json(bundle / 'quotes.json'))
    navs = [row['nav'] for row in economic['nav']]
    s['first_nav'], s['last_nav'] = float(navs[0]), float(navs[-1])
    s['total_return'] = s['last_nav'] / s['first_nav'] - 1
    s['calmar'] = s['cagr'] / abs(s['max_drawdown'])
    s['mean_equity_weight'] += sum(s['mean_asset_weights'].get(x, 0) for x in ('XLE', 'XLB'))
    s.pop('asset_daily_contribution')
    return s


def load_results(root, reference_root=REFERENCE_ROOT):
    results = {}
    for job in jobs_for((*ARMS, *CONTROLS)):
        results[job_name(job)] = load_replay(root, job)
    for job in jobs_for(PARENT_ONLY):
        results[job_name(job)] = load_replay(reference_root, job)
    return results


def at(results, arm, cost=COST_BPS, delay=0, window='evaluation'):
    return results[job_name((arm, cost, delay, window))]


def reference_parity(root, results, reference_root=REFERENCE_ROOT):
    """Every pooled reference must reproduce the parent's published statistics."""
    published = read_json(Path(reference_root) / 'statistics.json')
    out = {}
    for arm in (*CONTROLS, *PARENT_ONLY):
        name = job_name((arm, COST_BPS, 0, 'evaluation'))
        for field in ('cagr', 'sharpe_zero_cash', 'terminal_nav', 'max_drawdown'):
            if abs(results[name][field] - published[name][field]) > 1e-12:
                raise ValueError(f'{arm} reference replay differs from the parent on {field}')
        out[arm] = True
    return out


def chosen_classes(root, arm, window_days=None):
    """Which classes the rule actually bought, evidenced by the frozen holdings."""
    rows = read_json(Path(root) / 'decisions' / (arm + '.json'))
    days = sorted(rows) if window_days is None else [d for d in sorted(rows) if d in set(window_days)]
    counts = {sleeve: 0 for sleeve in SLEEVES}
    cash_only, held_counts, class_counts = 0, {}, []
    for day in days:
        weights = {t['symbol']: float(t['target_weight']) for t in rows[day]['targets']}
        held = {s for s, w in weights.items() if w > 0}
        if not held:
            cash_only += 1
        present = 0
        for sleeve, symbols in SLEEVES.items():
            if held & set(symbols):
                counts[sleeve] += 1
                present += 1
        class_counts.append(present)
        for symbol in held:
            held_counts[symbol] = held_counts.get(symbol, 0) + 1
    return dict(arm=arm, decisions=len(days), chosen_counts=counts,
                chosen_share={s: counts[s] / len(days) for s in counts},
                cash_only_days=cash_only, held_counts=held_counts,
                mean_classes=float(np.mean(class_counts)))


def uncertainty(root, results, blocks=BOOTSTRAP_BLOCKS):
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    months = sorted(at(results, ARMS[0])['monthly'])
    matrix = np.array([[at(results, a)['monthly'][m] - at(results, b)['monthly'][m] for a, b in COMPARISONS]
                       for m in months], dtype=float)
    out = {}
    for block in blocks:
        rows = paired_bootstrap(matrix, block=block, replications=BOOTSTRAP_REPLICATIONS, seed=SEED)
        out[str(block)] = [dict(comparison=f'{a}-{b}', **row) for (a, b), row in zip(COMPARISONS, rows, strict=True)]
    return out


def contrast(uncertainty_result, pair, block):
    name = f'{pair[0]}-{pair[1]}'
    return next(row for row in uncertainty_result[str(block)] if row['comparison'] == name)


def supported(metrics, uncertainty_result, pair):
    candidate, control = pair
    better_risk = (metrics[candidate]['sharpe_zero_cash'] > metrics[control]['sharpe_zero_cash']
                   and metrics[candidate]['calmar'] > metrics[control]['calmar'])
    positive = [block for block in BOOTSTRAP_BLOCKS
                if (contrast(uncertainty_result, pair, block)['ci95'] or [None])[0] is not None
                and contrast(uncertainty_result, pair, block)['ci95'][0] > 0
                and contrast(uncertainty_result, pair, block)['holm_p'] < .05]
    return dict(better_risk=bool(better_risk), positive_blocks=[int(b) for b in positive],
                supported=bool(better_risk and positive))


def assess(metrics, uncertainty_result, gate):
    primary = supported(metrics, uncertainty_result, PRIMARY)
    secondary = supported(metrics, uncertainty_result, SECONDARY)
    estimates = {f'{a}-{b}': contrast(uncertainty_result, (a, b), 6)['mean_annual'] for a, b in COMPARISONS}
    if primary['supported']:
        status = 'hierarchical_supported'
    elif secondary['supported']:
        status = 'three_class_supported'
    elif any((value or 0) > 0 for value in estimates.values()):
        status = 'inconclusive'
    else:
        status = 'rejected'
    return dict(status=status, rules=RULES, primary=dict(pair=list(PRIMARY), **primary),
                secondary=dict(pair=list(SECONDARY), **secondary),
                k_contrast=dict(pair=list(K_CONTRAST), **supported(metrics, uncertainty_result, K_CONTRAST)),
                gate=dict(status={arm: row['status'] for arm, row in gate['arms'].items()},
                          boundary=gate.get('boundary_cases', []),
                          costs={arm: row['annual_cost_bps'] for arm, row in gate['arms'].items()}),
                mean_annual_estimates=estimates,
                statement=('Qualifying classes and selecting inside the top two shows a family-adjusted positive '
                           'return difference against the pooled control.' if status == 'hierarchical_supported' else
                           'Only the three-class variant shows a family-adjusted positive difference.'
                           if status == 'three_class_supported' else
                           'No contrast establishes a family-adjusted positive difference; dropping downtrending '
                           'classes is not shown to beat the pooled top-six on this evidence.' if
                           status == 'rejected' else
                           'Point estimates are positive but no contrast clears the family-adjusted interval.'))


def summarize(root):
    from systematic_trading.research.hierarchical_construction_study import initialize
    from systematic_trading.research.momentum_replay import checked_files
    root = Path(root)
    checked_files(root, 'input_manifest.json')
    checked_files(root, 'decision_manifest.json')
    initialize(root)
    gate = read_json(root / 'gate.json')
    if sha256(root / 'gate.json') != read_json(root / 'gate_receipt.json')['sha256']:
        raise ValueError('Gate record changed')
    results = load_results(root)
    protocol = read_json(root / 'protocol.json')
    evaluation_days = [d for d in sorted(read_json(root / 'decisions/CP.json'))
                       if d >= protocol['evaluation_start']]
    metrics = {arm: at(results, arm) for arm in (*ARMS, *CONTROLS, *PARENT_ONLY)}
    payload = dict(version='hierarchical-construction-v1', protocol=protocol, gate=gate,
                   reference_parity=reference_parity(root, results),
                   pool_vs_control=pool_vs_control(root),
                   admission={arm: chosen_classes(root, arm, evaluation_days)
                              for arm in (*ARMS, *CONTROLS, *PARENT_ONLY)},
                   metrics=metrics, uncertainty=uncertainty(root, results), promotion_eligible=False)
    payload['verdict'] = assess(metrics, payload['uncertainty'], gate)
    write_json(root / 'statistics.json', results)
    write_json(root / 'statistics_receipt.json', dict(sha256=sha256(root / 'statistics.json')))
    write_json(root / 'analysis.json', {k: v for k, v in payload.items()})
    return dict(arms=len(metrics), verdict=payload['verdict']['status'], replays=len(results),
                cash_only={arm: payload['admission'][arm]['cash_only_days'] for arm in ARMS},
                chosen={arm: payload['admission'][arm]['chosen_counts'] for arm in ARMS})


def finalize(root):
    root = Path(root)
    if sha256(root / 'statistics.json') != read_json(root / 'statistics_receipt.json')['sha256']:
        raise ValueError('Statistics changed after inference')
    analysis = read_json(root / 'analysis.json')
    write_json(root / 'report.json', analysis)
    write_json(root / 'report_receipt.json', dict(sha256=sha256(root / 'report.json'),
        statistics_sha256=sha256(root / 'statistics.json'), input_sha256=sha256(root / 'input_manifest.json'),
        decision_manifest_sha256=sha256(root / 'decision_manifest.json'), gate_sha256=sha256(root / 'gate.json')))
    return dict(verdict=analysis['verdict']['status'], statement=analysis['verdict']['statement'])


def verify(root):
    from systematic_trading.research.hierarchical_construction_study import initialize
    from systematic_trading.research.momentum_replay import checked_files
    root = Path(root)
    checked_files(root, 'input_manifest.json')
    checked_files(root, 'decision_manifest.json')
    initialize(root)
    receipt = read_json(root / 'data_receipt.json')
    if {name: sha256(PARENT / name) for name in receipt['parent_hashes']} != receipt['parent_hashes']:
        raise ValueError('The pinned P4.16 study changed after this study was frozen')
    if {name: sha256(PARENT / 'decisions' / (name + '.json')) for name in receipt['parent_replay_hashes']} \
            != receipt['parent_replay_hashes']:
        raise ValueError('A pinned reference decision file changed')
    plans = read_json(root / 'protocol.json')['arms']
    return dict(parent_unchanged=True, top_classes={arm: plans[arm]['top_classes'] for arm in ARMS},
                slots_per_class=SLOTS_PER_CLASS, gate=read_json(root / 'gate.json')['gate_rejected'],
                pool_vs_control=pool_vs_control(root)['differing'])


def artifacts(root, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    root, output = Path(root), Path(output)
    report = read_json(root / 'report.json')
    if sha256(root / 'report.json') != read_json(root / 'report_receipt.json')['sha256']:
        raise ValueError('Report changed')
    p, metrics, verdict = report['protocol'], report['metrics'], report['verdict']
    gate, unc, adm = report['gate'], report['uncertainty'], report['admission']
    output.mkdir(parents=True, exist_ok=True)
    (output / 'reports').mkdir(exist_ok=True)
    arms = [*ARMS, *CONTROLS, *PARENT_ONLY]
    def source_root(arm):
        return REFERENCE_ROOT if arm in PARENT_ONLY else root
    fig, axes = plt.subplots(1, 3, figsize=(17, 5), layout='constrained')
    fig.set_facecolor('#fcfaf5')
    for ax in axes:
        ax.set_facecolor('#fcfaf5')
        ax.spines[['top', 'right']].set_visible(False)
        ax.grid(alpha=.15)
    names = [LABELS_ALL[a] for a in arms]
    colors = ['#207b92' if a in ARMS else '#8a9aa1' for a in arms]
    axes[0].barh(names, [metrics[a]['sharpe_zero_cash'] for a in arms], color=colors)
    axes[0].set_title('Evaluation Sharpe, fresh cash 2021+')
    axes[1].barh(names, [metrics[a]['annual_turnover'] for a in arms], color=colors)
    axes[1].axvline(float(gate['thresholds']['max_annual_cost_bps']) / COST_BPS, color='#b0432f', linestyle=':',
                    label='gate cost ceiling')
    axes[1].set_title('Measured annual turnover (x NAV)')
    axes[1].legend(fontsize=8, frameon=False)
    width = 0.35
    positions = np.arange(len(SLEEVES))
    for offset, arm in enumerate(ARMS):
        axes[2].bar(positions + (offset - 0.5) * width,
                    [adm[arm]['chosen_share'][s] for s in SLEEVES], width, label=arm)
    axes[2].set_xticks(positions, list(SLEEVES))
    axes[2].yaxis.set_major_formatter(PercentFormatter(1))
    axes[2].set_title('How often each class was chosen')
    axes[2].legend(fontsize=8, frameon=False)
    fig.savefig(output / 'construction.png', dpi=150)
    plt.close(fig)
    rows = []
    for a, b in COMPARISONS:
        for block in BOOTSTRAP_BLOCKS:
            row = contrast(unc, (a, b), block)
            rows.append([f'{LABELS_ALL[a]} − {LABELS_ALL[b]}', f'{block}m', pct(row['mean_annual']),
                         ci(row['ci95']), num(row['holm_p'])])
    candidate, control = verdict['primary']['pair']
    body = f'''<header><div class="eyebrow">P4.16b · HIERARCHICAL CONSTRUCTION · 11 OCTOBER 2026</div>
    <h1>Stop funding an asset class that is in a downtrend.</h1>
    <p class="lead">P4.16 measured that fixed sleeve budgets hold DBC and GLD in all 70 evaluation decisions and pay
    6% over the P4.15 cost ceiling for that representation. This study tests the obvious correction: a class must
    <b>qualify</b> — at least one member above its 126-session momentum gate — before it can be chosen, the
    qualifying classes are ranked, the top two or three share the budget equally, and each picks its best two names.</p>
    <p><b>Proposed by the operator on 11 October after P4.16's outcome, so this rule is post-hoc on the inspected
    sample and is not out-of-sample evidence.</b> Two arms, both K values declared; every arm screened by the P4.15
    gate before any replay; no grid, no promotion.</p></header>
    <nav><a href="#answer">Answer</a><a href="#gate">Cost gate</a><a href="#classes">Class behaviour</a>
    <a href="#comparison">Comparison</a><a href="#method">Method</a><a href="#evidence">Evidence</a></nav>
    <div class="cards">
    <div><b>{html.escape(verdict['status'].replace('_', ' '))}</b><span>{html.escape(verdict['statement'])}</span></div>
    <div><b>{pct(metrics[candidate]['cagr'])} vs {pct(metrics[control]['cagr'])}</b><span>CAGR, {LABELS_ALL[candidate]}
    against {LABELS_ALL[control]}, evaluation window at {num(p['primary']['cost_bps'], 0)}bp.</span></div>
    <div><b>{adm[ARMS[0]]['cash_only_days'] + adm[ARMS[1]]['cash_only_days']}</b><span>All-cash decisions across the
    two arms: days when no asset class had an eligible member, held as cash instead of forced into a downtrend.</span></div>
    </div>
    <img class="figure" src="construction.png" alt="Sharpe, turnover and class-selection frequency by arm">
    <section id="answer"><h2>The answer</h2>
    <p>{html.escape(verdict['statement'])} The frozen rule: supported requires {html.escape(RULES['supported'])}</p>'''
    body += table(['Contrast', 'Risk ratios both higher?', 'Positive blocks (Holm p&lt;0.05)', 'Supported'],
        [[f'{a} − {b}', 'yes' if verdict[key]['better_risk'] else 'no',
          ', '.join(f'{blk}m' for blk in verdict[key]['positive_blocks']) or 'none',
          'yes' if verdict[key]['supported'] else 'no']
         for key, (a, b) in [('primary', PRIMARY), ('secondary', SECONDARY), ('k_contrast', K_CONTRAST)]])
    body += f'''<p>For reference, the published pooled control made the same decision as the construction-matched
    pooled arm on {report['pool_vs_control']['decisions'] - report['pool_vs_control']['differing']} of
    {report['pool_vs_control']['decisions']} days, so the pooled columns here are the same book P4.16 compared
    against.</p></section>
    <section id="gate"><h2>The P4.15 cost gate, run before any replay</h2>
    <p>Implied annual turnover from each arm's own mapping at the frozen {num(gate['cost_bps'], 0)}bp. Dropping
    classes concentrates the book into fewer names, which is a cost as well as a protection: the gate says whether
    that trade is even affordable before any portfolio result exists.</p>'''
    body += table(['Arm', 'Implied turnover', 'Implied annual cost', 'Breakeven IC', 'IC margin', 'Gate verdict',
                   'Replay'],
        [[LABELS_ALL.get(arm, arm), num(row['annual_turnover'], 2) + 'x', f"{row['annual_cost_bps']:.1f}bp",
          num(row['breakeven_ic'], 4), num(row['ic_margin'], 2) + 'x', row['status'].upper(),
          'boundary case replayed' if row.get('boundary_case') else
          ('control, always replayed' if row['control'] else
           'replayed' if row['may_replay'] else 'not replayed')]
         for arm, row in gate['arms'].items()])
    body += (f"<p>{html.escape(gate['boundary_rule'])} Dispersion recomputed here "
             f"({num(gate['sigma'], 6)} over 21 sessions) and matching the published P4.15 calibration "
             f"({num(gate['published'].get('published_sigma'), 6)}).</p></section>")
    body += '<section id="classes"><h2>What the rule actually did to the classes</h2>'
    body += ('<p>Chosen-class frequency over the evaluation window, evidenced by the frozen holdings: a class can '
             'only appear if it qualified, so an absent class is one the rule dropped rather than underweighted.</p>')
    body += table(['Class', *[LABELS_ALL[a] for a in arms]],
        [[sleeve, *[pct(adm[a]['chosen_share'][sleeve]) for a in arms]] for sleeve in SLEEVES])
    body += table(['Arm', 'Mean classes held', 'All-cash decisions', 'Mean invested', 'Mean held'],
        [[LABELS_ALL[a], num(adm[a]['mean_classes'], 2), adm[a]['cash_only_days'],
          pct(metrics[a]['mean_gross']), num(metrics[a]['mean_held_count'], 2)] for a in arms])
    body += ('<p>Instruments held per arm, evaluation window: ')
    body += '; '.join(f"{LABELS_ALL[a]} " + ', '.join(f'{s} {n}' for s, n in
                      sorted(adm[a]['held_counts'].items(), key=lambda kv: -kv[1])[:6]) for a in ARMS)
    body += '.</p></section>'
    body += '<section id="comparison"><h2>Every registered contrast, family-adjusted</h2>'
    body += table(['Arm', 'CAGR', 'Sharpe', 'Calmar', 'Max DD', 'Turnover / year', 'Cost / year', 'Mean invested'],
        [[f'<a href="reports/{a}.html">{LABELS_ALL[a]}</a>', pct(metrics[a]['cagr']),
          num(metrics[a]['sharpe_zero_cash']), num(metrics[a]['calmar']), pct(metrics[a]['max_drawdown']),
          num(metrics[a]['annual_turnover'], 2) + '×', num(metrics[a]['annual_cost_bps'], 1) + 'bp',
          pct(metrics[a]['mean_gross'])] for a in arms])
    body += ('<p>Paired circular block bootstrap over monthly differences, Holm-adjusted across the registered '
             'family. Running the same table at 10bp, 20bp and a one-session delay is in the frozen statistics.</p>')
    body += table(['Contrast', 'Block', 'Mean annual difference', '95% interval', 'Holm p'], rows)
    stats = read_json(root / 'statistics.json')
    ref_stats = read_json(REFERENCE_ROOT / 'statistics.json')
    def sharpe_at(arm, cost, delay):
        source = ref_stats if arm in PARENT_ONLY else stats
        return source[job_name((arm, cost, delay, 'evaluation'))]['sharpe_zero_cash']
    body += table(['Arm', '5bp / delay 0', '10bp', '20bp', 'One-session delay'],
        [[LABELS_ALL[a], *[num(sharpe_at(a, c, d)) for c, d in ((5, 0), (10, 0), (20, 0), (5, 1))]]
         for a in arms])
    body += '</section>'
    body += ('''<section id="method"><h2>Method</h2>
    <p>One declared rule, two declared K values, no grid. A class qualifies only if at least one member passes the
    same positive 126-session momentum gate the pooled control uses; qualifying classes are scored by the mean of
    their two best eligible members; the top K share the incoming gross equally; inside each chosen class the top two
    eligible names split that class's budget by incoming inverse-volatility weight; an unfilled slot, or a day with
    no qualifying class, is cash. The selection stage is the existing balanced-group overlay with a per-day budget
    override, so the class ranking, the weight arithmetic and the "never force an ineligible asset" contract are the
    parent primitive's own code. Everything downstream — XGBoost tilt, relative momentum, adaptive trend, audited raw
    activity, USD ridge, the final 45% cap, execution and 5bp — is unchanged from the pooled control.</p></section>''')
    body += '<section id="evidence"><h2>Verification and limits</h2>'
    body += table(['Pinned reference replay', 'Matches the P4.16 published statistics'],
        [[LABELS_ALL[a], 'yes' if flag else 'no'] for a, flag in report['reference_parity'].items()])
    body += ('<p><a href="../../var/research/hierarchical-construction-20261011-v1/protocol.json">Frozen '
             'protocol</a> · <a href="../../var/research/hierarchical-construction-20261011-v1/gate.json">Gate '
             'record</a> · <a href="../../var/research/hierarchical-construction-20261011-v1/analysis.json">'
             'Analysis and verdict</a> · '
             '<a href="../../var/research/hierarchical-construction-20261011-v1/decision_manifest.json">Decision '
             'manifest</a> · <a href="../sleeve-construction-2026-10-10/index.html">P4.16</a> · '
             '<a href="../../docs/turnover-gate.md">P4.15 thresholds</a></p>')
    body += '<ul>' + ''.join(f'<li>{html.escape(item)}</li>' for item in p['limitations']) + '</ul></section>'
    css = ('*{box-sizing:border-box}body{margin:0;background:#f3f0e8;color:#263c47;font:16px/1.6 system-ui,sans-serif}'
           'main{max-width:1320px;margin:auto;padding:44px 32px}h1{font-size:42px;line-height:1.1;margin:16px 0}'
           'h2{font-size:27px;line-height:1.25}.eyebrow{font-size:12px;letter-spacing:2px;font-weight:700}'
           '.lead{font-size:22px;max-width:1050px}a{color:#12617b}nav{display:flex;gap:22px;flex-wrap:wrap;'
           'margin:26px 0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}'
           '.cards>div{padding:20px;background:#fffdf7;border-top:3px solid #367d8f}.cards b{display:block;'
           'font-size:26px}.cards span{font-size:14px}.figure{width:100%;height:auto}'
           'section{padding:24px 28px;background:#fffdf8;margin:24px 0;border:1px solid #ddd8cb;border-radius:7px}'
           '.scroll{overflow:auto;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:13px;'
           'font-variant-numeric:tabular-nums}th,td{padding:10px 11px;text-align:right;'
           'border-bottom:1px solid #deded5;white-space:nowrap}th{background:#e6eeec}'
           'td:first-child,th:first-child{text-align:left}tr:nth-child(even) td{background:#f7f6f0}'
           'p,li{max-width:1160px}@media(max-width:700px){main{padding:24px 12px}h1{font-size:32px}'
           '.cards{grid-template-columns:1fr}section{padding:18px 12px}}')
    (output / 'index.html').write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Hierarchical construction</title><style>' + css + '</style><main>' + body
        + '</main></html>', encoding='utf8')
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data, render_backtest_report_html
    for arm in arms:
        source = source_root(arm)
        name = job_name((arm, COST_BPS, 0, 'full'))
        economic = read_json(source / 'python' / (name + '.json'))
        quotes = read_json(source / 'bundles' / name / 'quotes.json')
        result = report_result(economic, quotes, p['initial_cash_usd'], '2015-12-31')
        benchmark = 'CP' if arm != 'CP' else 'M1'
        bench_name = job_name((benchmark, COST_BPS, 0, 'full'))
        bench = report_result(read_json(REFERENCE_ROOT / 'python' / (bench_name + '.json')),
                              read_json(REFERENCE_ROOT / 'bundles' / bench_name / 'quotes.json'),
                              p['initial_cash_usd'], '2015-12-31')
        data, warnings = build_backtest_report_data(result=result, result_path=source / 'python' / (name + '.json'),
            split_date=p['evaluation_start'], benchmark_name=CONTROL_LABELS[benchmark],
            benchmark_nav_series=bench['nav_series'], extra_benchmarks=[],
            market_prices={s: {d: float(q['close']) for d, q in rows.items()} for s, rows in quotes.items()},
            market_fx_rates={v['date']: 1. for v in economic['nav']})
        data.update(title=LABELS_ALL[arm] + ' · hierarchical construction', accountingCurrency='USD',
            database='Frozen parent evidence and pinned causal models', allocationSource='Simulated fills',
            splitLabel='Previously inspected chronological boundary',
            sampleLabels={'in_sample': '2016–2020 retrospective', 'out_of_sample': '2021 onward retrospective'},
            decisionDiagrams=[dict(title='Complete decision flow',
                                   svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 60">'
                                       f'<text x="10" y="35" font-family="sans-serif" font-size="13">'
                                       f'{html.escape(LABELS_ALL[arm])}: post-hoc P4.16b arm; research only.'
                                       f'</text></svg>')],
            strategyDefinition=dict(id=arm, protocol=p),
            warnings=[*warnings, *p['limitations'],
                      'Post-hoc arm proposed after P4.16 outcomes were known. Fresh-cash research replay, not a '
                      'monitored strategy and not promotion evidence.'])
        rendered = render_backtest_report_html(data)
        import re as _re
        rendered = _re.sub(r'(href=["\'])(/[^"\']*)', r'\1http://127.0.0.1:8000\2', rendered)
        (output / 'reports' / (arm + '.html')).write_text(rendered, encoding='utf8')
    write_json(root / 'presentation_receipt.json', dict(report_sha256=sha256(root / 'report.json'),
        files={f.relative_to(output).as_posix(): sha256(f) for f in output.rglob('*') if f.is_file()},
        sources={str(Path(__file__)): sha256(Path(__file__))}))
    return dict(output=str(output), reports=len(arms))
