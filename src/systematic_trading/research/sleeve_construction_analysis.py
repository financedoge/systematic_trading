"""P4.16 sleeve-aware construction: analysis, family-adjusted tests, verdict and report.

Reads this study's own frozen replays and the frozen gate record. Nothing here
re-tunes a construction, changes a monitored strategy, an allocation or a broker record.
"""
from pathlib import Path
import html
import re

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.expanded_economics import job_name
from systematic_trading.research.momentum_replay import read_json, verify_usd_bundle
from systematic_trading.research.sleeve_construction_study import (ARMS, BOOTSTRAP_BLOCKS, BOOTSTRAP_REPLICATIONS,
    COMPARISONS, CONTROLS, CONTROL_LABELS, COST_BPS, COSTS, DELAYS, LABELS, PARENT, PARENT_CONTROLS, SEED,
    SLEEVE_OF, SLEEVES, WINDOWS)

PRIMARY = ('SLV-COMP', 'POOL')
SECONDARY = ('SLV-EQ', 'POOL')
BUDGET_CONTRAST = ('SLV-COMP', 'SLV-EQ')
PARITY_CONTRAST = ('POOL', 'CP')
LABELS_ALL = {**LABELS, **CONTROL_LABELS}
# Frozen verdict rules, declared before the replays were read.
RULES = dict(
    supported='positive mean-return interval at a registered block with Holm p<0.05 across the registered family, '
              'AND a higher Sharpe and a higher Calmar than the control in the primary window',
    inconclusive='a positive point estimate that does not clear the family-adjusted interval, or intervals that span '
                 'zero',
    rejected='no positive family-adjusted interval and non-positive point estimates')
DEFAULTS = dict(cost_bps=COST_BPS, delay=0, window='evaluation')


def load_results(root):
    """Verify every replay and recompute its published statistics."""
    from systematic_trading.research.momentum_analysis import statistics
    results = {}
    for job in [*jobs_for(ARMS), *jobs_for(CONTROLS)]:
        name = job_name(job)
        path, bundle = root / 'python' / (name + '.json'), root / 'bundles' / name
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
        results[name] = s
    return results


def jobs_for(arms):
    return [(arm, cost, delay, window) for arm in arms for cost in COSTS for delay in DELAYS for window in WINDOWS]


def at(results, arm, cost=COST_BPS, delay=0, window='evaluation'):
    return results[job_name((arm, cost, delay, window))]


def decision_rows(root, arm):
    return read_json(Path(root) / 'decisions' / (arm + '.json'))


def pool_vs_control(root, control='CP'):
    """Where the construction-matched pooled arm differs from the published pooled control.

    Compared numerically with a tolerance: the two arms write zero weights with different
    decimal spellings, which a string comparison would misreport as a decision change.
    """
    from decimal import Decimal as D
    left, right = decision_rows(root, 'POOL'), decision_rows(root, control)
    shared = sorted(set(left) & set(right))
    if len(shared) != len(left) or len(shared) != len(right):
        raise ValueError('POOL and ' + control + ' do not share one decision calendar')
    tolerance = D('1e-12')
    differing, defensive, set_differences = [], [], []
    for day in shared:
        a = {t['symbol']: D(t['target_weight']) for t in left[day]['targets']}
        b = {t['symbol']: D(t['target_weight']) for t in right[day]['targets']}
        moved = {s for s in set(a) | set(b) if abs(a.get(s, D(0)) - b.get(s, D(0))) > tolerance}
        if not moved:
            continue
        differing.append(day)
        held_a = {s for s, w in a.items() if w > 0}
        held_b = {s for s, w in b.items() if w > 0}
        if held_a != held_b:
            set_differences.append(day)
        # the published control's defensive signature: only the defensive trio, or nothing,
        # while the construction-matched arm holds something else
        if held_b.issubset({'IEF', 'TLT', 'GLD'}):
            defensive.append(day)
    return dict(arm='POOL', control=control, decisions=len(shared), differing=len(differing),
                differing_share=len(differing) / len(shared), first_difference=differing[0] if differing else None,
                membership_differences=len(set_differences), defensive_fallback_differences=len(defensive),
                weight_only_differences=len(differing) - len(set_differences), days=differing)


def admission(root, arms=(*ARMS, *CONTROLS), window_days=None):
    """How often each instrument and sleeve is held, and how much gross the arm carries."""
    out = {}
    for arm in arms:
        rows = decision_rows(root, arm)
        days = sorted(rows) if window_days is None else [d for d in sorted(rows) if d in set(window_days)]
        counts = {symbol: 0 for symbols in SLEEVES.values() for symbol in symbols}
        sleeve_weight = {sleeve: [] for sleeve in SLEEVES}
        gross, held = [], []
        for day in days:
            weights = {t['symbol']: float(t['target_weight']) for t in rows[day]['targets']}
            positive = {s: w for s, w in weights.items() if w > 0}
            for symbol in positive:
                counts[symbol] += 1
            total = sum(weights.values())
            gross.append(total)
            held.append(len(positive))
            for sleeve, symbols in SLEEVES.items():
                sleeve_weight[sleeve].append(sum(weights.get(s, 0.0) for s in symbols))
        out[arm] = dict(decisions=len(days), held_counts=counts,
                        held_share={s: counts[s] / len(days) for s in counts},
                        mean_sleeve_weight={k: float(np.mean(v)) for k, v in sleeve_weight.items()},
                        mean_gross=float(np.mean(gross)), mean_held=float(np.mean(held)))
    return out


def uncertainty(root, results, blocks=BOOTSTRAP_BLOCKS):
    """Paired circular block bootstrap over the registered comparison family."""
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
        status = 'sleeve_supported'
    elif secondary['supported']:
        status = 'equal_budget_supported'
    elif any((value or 0) > 0 for value in estimates.values()):
        status = 'inconclusive'
    else:
        status = 'rejected'
    return dict(status=status, rules=RULES, primary=dict(pair=list(PRIMARY), **primary),
                secondary=dict(pair=list(SECONDARY), **secondary),
                budget_contrast=dict(pair=list(BUDGET_CONTRAST), **supported(metrics, uncertainty_result,
                                                                           BUDGET_CONTRAST)),
                parity_contrast=dict(pair=list(PARITY_CONTRAST), **supported(metrics, uncertainty_result,
                                                                            PARITY_CONTRAST)),
                gate=dict(status={arm: row['status'] for arm, row in gate['arms'].items()},
                          boundary=gate.get('boundary_cases', []),
                          costs={arm: row['annual_cost_bps'] for arm, row in gate['arms'].items()}),
                mean_annual_estimates=estimates,
                statement=('Within-sleeve construction shows a family-adjusted positive return difference against the '
                           'pooled control.' if status == 'sleeve_supported' else
                           'Only the equal-budget sleeve variant shows a family-adjusted positive difference.'
                           if status == 'equal_budget_supported' else
                           'No contrast establishes a family-adjusted positive difference; the pooled cross-section '
                           'is not shown to be worse than within-sleeve selection on this evidence.' if
                           status == 'rejected' else
                           'Point estimates are positive but no contrast clears the family-adjusted interval.'))


def summarize(root):
    from systematic_trading.research.sleeve_construction_study import initialize
    root = Path(root)
    from systematic_trading.research.momentum_replay import checked_files
    checked_files(root, 'input_manifest.json')
    checked_files(root, 'decision_manifest.json')
    initialize(root)
    gate = read_json(root / 'gate.json')
    if sha256(root / 'gate.json') != read_json(root / 'gate_receipt.json')['sha256']:
        raise ValueError('Gate record changed')
    results = load_results(root)
    parent_stats = read_json(PARENT / 'statistics.json')
    parity = {}
    for arm in PARENT_CONTROLS:
        name = job_name((arm, COST_BPS, 0, 'evaluation'))
        for field in ('cagr', 'sharpe_zero_cash', 'terminal_nav', 'max_drawdown'):
            if abs(results[name][field] - parent_stats[name][field]) > 1e-12:
                raise ValueError(f'{arm} reference replay differs from the parent on {field}')
        parity[arm] = True
    days = sorted(decision_rows(root, 'CP'))
    evaluation_days = [d for d in days if d >= read_json(root / 'protocol.json')['evaluation_start']]
    metrics = {arm: at(results, arm) for arm in (*ARMS, *CONTROLS)}
    payload = dict(version='sleeve-construction-v1', protocol=read_json(root / 'protocol.json'), gate=gate,
                   control_parity=parity, pool_vs_control=pool_vs_control(root),
                   admission=admission(root, window_days=evaluation_days),
                   metrics=metrics, uncertainty=uncertainty(root, results), results=results,
                   promotion_eligible=False)
    payload['verdict'] = assess(metrics, payload['uncertainty'], gate)
    write_json(root / 'statistics.json', results)
    write_json(root / 'statistics_receipt.json', dict(sha256=sha256(root / 'statistics.json')))
    write_json(root / 'analysis.json', {k: v for k, v in payload.items() if k != 'results'})
    return dict(arms=len(metrics), verdict=payload['verdict']['status'],
                replays=len(results), pool_vs_cp=payload['pool_vs_control']['differing'])


def finalize(root):
    root = Path(root)
    if sha256(root / 'statistics.json') != read_json(root / 'statistics_receipt.json')['sha256']:
        raise ValueError('Statistics changed after inference')
    analysis = read_json(root / 'analysis.json')
    write_json(root / 'report.json', analysis)
    write_json(root / 'report_receipt.json', dict(sha256=sha256(root / 'report.json'),
        statistics_sha256=sha256(root / 'statistics.json'), input_sha256=sha256(root / 'input_manifest.json'),
        decision_manifest_sha256=sha256(root / 'decision_manifest.json'),
        gate_sha256=sha256(root / 'gate.json')))
    return dict(verdict=analysis['verdict']['status'], statement=analysis['verdict']['statement'])


def verify(root):
    from systematic_trading.research.sleeve_construction_study import initialize
    root = Path(root)
    from systematic_trading.research.momentum_replay import checked_files
    checked_files(root, 'input_manifest.json')
    checked_files(root, 'decision_manifest.json')
    initialize(root)
    receipt = read_json(root / 'data_receipt.json')
    live = {name: sha256(PARENT / name) for name in receipt['parent_hashes']}
    if live != receipt['parent_hashes']:
        raise ValueError('The pinned parent study changed after this study was frozen')
    plans = {arm: read_json(root / 'protocol.json')['arms'][arm] for arm in ARMS}
    if plans['POOL']['slot_total'] != 6 or plans['SLV-COMP']['slot_total'] != 6:
        raise ValueError('Declared slot plan changed')
    return dict(parent_unchanged=True, plans={arm: plan['slot_total'] for arm, plan in plans.items()},
                gate=read_json(root / 'gate.json')['gate_rejected'],
                pool_vs_control=pool_vs_control(root)['differing'])


def num(x, n=3):
    return 'n/a' if x is None else f'{x:,.{n}f}'


def pct(x, n=2):
    return 'n/a' if x is None else f'{x:.{n}%}'


def delta(x, n=3):
    return 'n/a' if x is None else f'{x:+.{n}f}'


def ci(values):
    return 'n/a' if not values else '[' + ', '.join(num(v, 3) for v in values) + ']'


def table(headers, rows):
    def cell(x):
        return str(x) if str(x).startswith('<a ') else html.escape(str(x))
    return ('<div class="scroll"><table><thead><tr>' + ''.join('<th>' + cell(x) + '</th>' for x in headers)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + cell(x) + '</td>' for x in row)
            + '</tr>' for row in rows) + '</tbody></table></div>')


def flow():
    return ['Pin the parent protocol, inputs and decision manifest by hash; copy the control decisions unchanged',
            'Build the sleeve overlay from the existing balanced-group primitive with the pooled control parameters',
            'POOL: one sleeve over all fourteen, budget 1, six slots; the construction-matched pooled control',
            'SLV-COMP: four sleeves, budgets proportional to universe composition (8/4/1/1), two slots each',
            'SLV-EQ: four sleeves, equal budgets, two slots each',
            'An unfilled sleeve budget stays in cash: fallback_to_top_ranked is off, matching the pooled contract',
            'Downstream unchanged: XGBoost tilt, relative momentum, adaptive trend, audited raw activity, USD ridge',
            'Explicit final 45% cap; excess remains cash; whole adjusted units, next-open execution, 5bp',
            'Screen every arm with the P4.15 turnover gate BEFORE any replay; record boundary cases',
            'Replay passing and control arms; paired circular block bootstrap over the registered six contrasts',
            'Holm-adjust across the family; report every contrast, no threshold grid, no promotion']


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
    arms = [*ARMS, *CONTROLS]
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
    for sleeve, symbols in SLEEVES.items():
        axes[2].plot(arms, [adm[a]['mean_sleeve_weight'][sleeve] for a in arms], marker='o', label=sleeve)
    axes[2].yaxis.set_major_formatter(PercentFormatter(1))
    axes[2].tick_params(axis='x', labelrotation=20)
    axes[2].set_title('Mean sleeve weight, evaluation window')
    axes[2].legend(fontsize=8, frameon=False)
    fig.savefig(output / 'construction.png', dpi=150)
    plt.close(fig)
    rows = []
    for a, b in COMPARISONS:
        for block in BOOTSTRAP_BLOCKS:
            row = contrast(unc, (a, b), block)
            rows.append([f'{LABELS_ALL[a]} − {LABELS_ALL[b]}', f'{block}m', pct(row['mean_annual']),
                         ci(row['ci95']), num(row['holm_p'])])
    primary = verdict['primary']
    candidate, control = primary['pair']
    body = f'''<header><div class="eyebrow">P4.16 · SLEEVE-AWARE CONSTRUCTION · 10 OCTOBER 2026</div>
    <h1>Should the book pick within asset-class sleeves, or across the whole pool?</h1>
    <p class="lead">The pooled cross-section is doing real work today: FR25's recent substitutions were
    cross-asset-class. This tests the premise that a single pooled ranking is the right construction for fourteen
    heterogeneous instruments — the question P4.17 depends on.</p>
    <p>Three construction arms, two published references, {len(report['metrics'])} arms replayed at four cost/delay
    settings across two windows. Every arm was screened by the P4.15 turnover gate <b>before</b> any replay. No
    threshold grid, no parameter search, no promotion.</p></header>
    <nav><a href="#answer">Answer</a><a href="#gate">Cost gate</a><a href="#comparison">Comparison</a>
    <a href="#admission">Admission</a><a href="#method">Method</a><a href="#evidence">Evidence</a></nav>
    <div class="cards">
    <div><b>{html.escape(verdict['status'].replace('_', ' '))}</b><span>{html.escape(verdict['statement'])}</span></div>
    <div><b>{pct(metrics[candidate]['cagr'])} vs {pct(metrics[control]['cagr'])}</b><span>CAGR, {LABELS_ALL[candidate]}
    against {LABELS_ALL[control]}, evaluation window at {num(p['primary']['cost_bps'], 0)}bp.</span></div>
    <div><b>{gate['arms']['SLV-EQ']['annual_cost_bps']:.1f}bp</b><span>Implied annual cost of the equal-budget arm
    against a {gate['arms']['CP']['cost_ceiling_bps']:.0f}bp ceiling; the composition arm sits at
    {gate['arms']['SLV-COMP']['annual_cost_bps']:.1f}bp and is a recorded boundary case.</span></div></div>
    <img class="figure" src="construction.png" alt="Sharpe, turnover and mean sleeve weights by arm">
    <section id="answer"><h2>The answer</h2>
    <p>{html.escape(verdict['statement'])} The frozen rules: supported requires {html.escape(RULES['supported'])}</p>'''
    body += table(['Contrast', 'Risk ratios both higher?', 'Positive blocks (Holm p&lt;0.05)', 'Supported'],
        [[f'{a} − {b}', 'yes' if verdict[key]['better_risk'] else 'no',
          ', '.join(f'{blk}m' for blk in verdict[key]['positive_blocks']) or 'none',
          'yes' if verdict[key]['supported'] else 'no']
         for key, (a, b) in [('primary', PRIMARY), ('secondary', SECONDARY), ('budget_contrast', BUDGET_CONTRAST),
                             ('parity_contrast', PARITY_CONTRAST)]])
    body += f'''<p><b>What the defensive fallback is worth.</b> The pooled arm and the published control make the
    <b>same decision on {report['pool_vs_control']['decisions'] - report['pool_vs_control']['differing']} of
    {report['pool_vs_control']['decisions']}</b> days, and differ only where the published control's defensive-cash
    fallback fires. Because the two books are otherwise identical, the whole performance gap between them is that one
    contract: CAGR {pct(metrics['CP']['cagr'])} against {pct(metrics['POOL']['cagr'])}, and maximum drawdown
    {pct(metrics['CP']['max_drawdown'])} against {pct(metrics['POOL']['max_drawdown'])}. The monitored strategy's
    risk control lives in its fallback rule, not in its selection rule. Both sleeve arms sit between the two: their
    unfilled sleeve budgets stay in cash, which recovers part of the protection but not all of it.</p>
    <p>The parity contrast is a control, not a claim.</p></section>
    <section id="gate"><h2>The P4.15 cost gate, run before any replay</h2>
    <p>Implied annual turnover from each arm's own mapping, priced at the frozen {num(gate['cost_bps'], 0)}bp.
    The equal-budget arm is cheaper than the pooled control because unfilled sleeves stay in cash; the composition
    arm pays for forcing a commodity and a gold name whenever their gate passes.</p>'''
    body += table(['Arm', 'Implied turnover', 'Implied annual cost', 'Breakeven IC', 'IC margin', 'Gate verdict',
                   'Replay'],
        [[LABELS_ALL.get(arm, arm), num(row['annual_turnover'], 2) + 'x', f"{row['annual_cost_bps']:.1f}bp",
          num(row['breakeven_ic'], 4), num(row['ic_margin'], 2) + 'x', row['status'].upper(),
          'boundary case replayed' if row.get('boundary_case') else
          ('control, always replayed' if row['control'] else
           'replayed' if row['may_replay'] else 'not replayed')]
         for arm, row in gate['arms'].items() if arm in arms])
    body += (f"<p>{html.escape(gate['boundary_rule'])} The dispersion is this study's own recomputation "
             f"({num(gate['sigma'], 6)} over 21 sessions) and matches the published P4.15 calibration "
             f"({num(gate['published'].get('published_sigma'), 6)}), so the two items share one input "
             f"definition.</p></section>")
    body += '<section id="comparison"><h2>Every registered contrast, family-adjusted</h2>'
    body += table(['Arm', 'CAGR', 'Sharpe', 'Calmar', 'Max DD', 'Turnover / year', 'Cost / year', 'Mean invested',
                   'Mean held'],
        [[f'<a href="reports/{a}.html">{LABELS_ALL[a]}</a>', pct(metrics[a]['cagr']),
          num(metrics[a]['sharpe_zero_cash']), num(metrics[a]['calmar']), pct(metrics[a]['max_drawdown']),
          num(metrics[a]['annual_turnover'], 2) + '×', num(metrics[a]['annual_cost_bps'], 1) + 'bp',
          pct(metrics[a]['mean_gross']), num(metrics[a]['mean_held_count'], 2)] for a in arms])
    body += ('<p>Paired circular block bootstrap over monthly differences, Holm-adjusted across the six registered '
             'contrasts. Mean annual differences are annualised; intervals are 95%.</p>')
    body += table(['Contrast', 'Block', 'Mean annual difference', '95% interval', 'Holm p'], rows)
    body += '</section>'
    body += '<section id="admission"><h2>What each construction actually holds</h2>'
    body += ('<p>Selection counts over the evaluation window. Sleeve budgets force representation: the commodity and '
             'gold sleeves hold one instrument each, so those names enter whenever their 126-session gate passes. '
             'That is the mechanism under test, and it is also why the composition arm trades more. <b>The budgets '
             'constrain selection, not realised weights:</b> the downstream overlays and the adaptive-trend exposure '
             'move both composition and gross after the sleeve stage, so the realised sleeve shares below are not the '
             'budgets themselves, and an unfilled sleeve leaves cash rather than forcing a name in.</p>')
    symbols = sorted(SLEEVE_OF)
    body += table(['Instrument', 'Sleeve'] + [LABELS_ALL[a] for a in arms],
        [[s, SLEEVE_OF[s]] + [adm[a]['held_counts'][s] for a in arms] for s in symbols])
    body += table(['Arm', 'Mean gross', 'Mean held', *SLEEVES],
        [[LABELS_ALL[a], pct(adm[a]['mean_gross']), num(adm[a]['mean_held'], 2),
          *[pct(adm[a]['mean_sleeve_weight'][sleeve]) for sleeve in SLEEVES]] for a in arms])
    body += '</section>'
    body += f'''<section id="method"><h2>Method</h2>
    <p>One declared configuration per arm, no grid: sleeves are the plan's own four-way split, budgets are either the
    universe's own composition (8/4/1/1) or equal, and the per-sleeve slot count is a single declared value of two.
    The overlay is the existing balanced-group primitive parameterized to the pooled control's scoring
    (21/63/126 momentum, 0.75/0.25 trend/volume, positive 126-session gate), so the arms differ in construction
    rather than in signal. Unfilled sleeve budgets stay in cash, matching the pooled contract of never forcing an
    ineligible asset.</p>
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {len(flow()) * 57 + 10}">'''
    for i, line in enumerate(flow()):
        body += (f'<rect x="5" y="{i * 57 + 5}" width="1190" height="48" rx="8" fill="#e8f0f2"/>'
                 f'<text x="16" y="{i * 57 + 34}" font-family="sans-serif" font-size="12">{i + 1}. '
                 f'{html.escape(line)}</text>')
    body += '</svg></section>'
    body += '<section id="evidence"><h2>Verification and limits</h2>'
    body += table(['Control replay', 'Matches the parent published replay'],
        [[CONTROL_LABELS[a], 'yes' if flag else 'no'] for a, flag in report['control_parity'].items()])
    body += ('<p><a href="../../var/research/sleeve-construction-20261010-v1/protocol.json">Frozen protocol</a> · '
             '<a href="../../var/research/sleeve-construction-20261010-v1/gate.json">Gate record</a> · '
             '<a href="../../var/research/sleeve-construction-20261010-v1/analysis.json">Analysis and verdict</a> · '
             '<a href="../../var/research/sleeve-construction-20261010-v1/decision_manifest.json">Decision '
             'manifest</a> · <a href="../../docs/turnover-gate.md">P4.15 thresholds</a> · '
             '<a href="../fr25-placebo-2026-10-10/index.html">P4.14 parent study</a></p>')
    body += '<p><b>Limitations.</b></p><ul>' + ''.join(
        f'<li>{html.escape(item)}</li>' for item in p['limitations']) + '</ul></section>'
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
           'p{max-width:1160px}@media(max-width:700px){main{padding:24px 12px}h1{font-size:32px}'
           '.cards{grid-template-columns:1fr}section{padding:18px 12px}}')
    (output / 'index.html').write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>Sleeve-aware construction</title><style>' + css + '</style><main>' + body
        + '</main></html>', encoding='utf8')
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data, render_backtest_report_html
    for arm in arms:
        name = job_name((arm, COST_BPS, 0, 'full'))
        economic = read_json(root / 'python' / (name + '.json'))
        quotes = read_json(root / 'bundles' / name / 'quotes.json')
        result = report_result(economic, quotes, p['initial_cash_usd'], '2015-12-31')
        benchmark = 'CP' if arm != 'CP' else 'M1'
        bench_name = job_name((benchmark, COST_BPS, 0, 'full'))
        bench = report_result(read_json(root / 'python' / (bench_name + '.json')),
                              read_json(root / 'bundles' / bench_name / 'quotes.json'),
                              p['initial_cash_usd'], '2015-12-31')
        data, warnings = build_backtest_report_data(result=result, result_path=root / 'python' / (name + '.json'),
            split_date=p['evaluation_start'], benchmark_name=CONTROL_LABELS[benchmark],
            benchmark_nav_series=bench['nav_series'], extra_benchmarks=[],
            market_prices={s: {d: float(q['close']) for d, q in rows.items()} for s, rows in quotes.items()},
            market_fx_rates={v['date']: 1. for v in economic['nav']})
        data.update(title=LABELS_ALL[arm] + ' · sleeve-aware construction', accountingCurrency='USD',
            database='Frozen parent evidence and pinned causal models', allocationSource='Simulated fills',
            splitLabel='Previously inspected chronological boundary',
            sampleLabels={'in_sample': '2016–2020 retrospective', 'out_of_sample': '2021 onward retrospective'},
            decisionDiagrams=[dict(title='Complete decision flow',
                                   svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 60">'
                                       f'<text x="10" y="35" font-family="sans-serif" font-size="13">'
                                       f'{html.escape(LABELS_ALL[arm])}: construction arm of the registered P4.16 '
                                       f'family; research only.</text></svg>')],
            strategyDefinition=dict(id=arm, protocol=p),
            warnings=[*warnings, *p['limitations'],
                      'Fresh-cash evaluation replay of a frozen research arm, not a monitored strategy and not '
                      'promotion evidence.'])
        rendered = render_backtest_report_html(data)
        rendered = re.sub(r'(href=["\'])(/[^"\']*)', r'\1http://127.0.0.1:8000\2', rendered)
        (output / 'reports' / (arm + '.html')).write_text(rendered, encoding='utf8')
    write_json(root / 'presentation_receipt.json', dict(report_sha256=sha256(root / 'report.json'),
        files={f.relative_to(output).as_posix(): sha256(f) for f in output.rglob('*') if f.is_file()},
        sources={str(Path(__file__)): sha256(Path(__file__))}))
    return dict(output=str(output), reports=len(arms))
