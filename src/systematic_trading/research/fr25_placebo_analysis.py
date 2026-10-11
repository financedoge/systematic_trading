"""P4.14 Part B — matched-availability placebo rank, refit and sensitivity with the frozen verdict.

Reads the frozen placebo study's own replays. Nothing here re-tunes FR25, changes a
monitored strategy, an allocation, an approval or a broker record.
"""
from decimal import Decimal as D
from pathlib import Path
import html
import math
import re

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.expanded_economics import job_name
from systematic_trading.research.fr25_placebo_study import (BASELINE_ARM, CANDIDATE, CONTROL, COST_BPS,
    DELAY, DRAWS, PARENT, PLACEBO_PERCENTILE, REFIT_ARM, SENSITIVITY_BASELINE, SEED, SENTINEL, SLOTS,
    SUB_START, TOLERANCE, VERDICT_MAPPING, RIDGE_WEIGHTS_PCT, draw_of, jobs,
    placebo_arm, refit_parity, refit_ridge, sensitivity_arms, variant_name, verify_decisions, verify_placebo)
from systematic_trading.research.momentum_replay import checked_files, read_json, verify_usd_bundle

LABELS = {
    CANDIDATE: 'FR25 · 75% M1 / 25% financial ridge',
    CONTROL: 'CP · capped M1 control',
    'M1': 'M1 · faster momentum, no final cap',
    SENTINEL: 'Identity assignment (verification arm, not a draw)',
    BASELINE_ARM: 'N6 W25 · the frozen FR25 recipe re-derived from the frozen rank tables',
    REFIT_ARM: 'Financial ridge refitted on labels completed by 2022-12-31',
}
for n in SLOTS:
    for w in RIDGE_WEIGHTS_PCT:
        LABELS[variant_name(n, w)] = f'Top-{n} slots · {100 - w}/{w} M1 / financial ridge'


def load_results(root):
    """Verify every replay against its bundle and recompute its published statistics."""
    from systematic_trading.research.momentum_analysis import statistics
    results = {}
    for job in jobs():
        name = job_name(job)
        path, bundle = root / 'python' / (name + '.json'), root / 'bundles' / name
        verify_usd_bundle(bundle)
        if read_json(path.with_suffix('.receipt.json')) != dict(
                sha256=sha256(path), manifest_sha256=sha256(bundle / 'manifest.json')):
            raise ValueError('Replay changed ' + name)
        economic = read_json(path)
        s = statistics(economic, read_json(bundle / 'quotes.json'))
        navs = [row['nav'] for row in economic['nav']]
        # Total return is measured from the first valued session, as Part A does; the
        # first session already carries the same entry cost in every arm.
        s['first_nav'], s['last_nav'] = float(navs[0]), float(navs[-1])
        s['total_return'] = s['last_nav'] / s['first_nav'] - 1
        s['calmar'] = s['cagr'] / abs(s['max_drawdown'])
        s['mean_equity_weight'] += sum(s['mean_asset_weights'].get(x, 0) for x in ('XLE', 'XLB'))
        s.pop('asset_daily_contribution')
        results[name] = s
    return results


def changed_vs_control(root, arm, tolerance='1e-12'):
    """Decisions whose target weights differ from the control's, the Part A convention."""
    decisions = read_json(Path(root) / 'decisions' / (arm + '.json'))
    control = read_json(Path(root) / 'decisions' / (CONTROL + '.json'))
    shared = sorted(set(decisions) & set(control))
    tolerance = D(tolerance)
    changed = []
    for day in shared:
        left = {t['symbol']: D(t['target_weight']) for t in decisions[day]['targets']}
        right = {t['symbol']: D(t['target_weight']) for t in control[day]['targets']}
        if any(abs(left.get(s, D(0)) - right.get(s, D(0))) > tolerance for s in set(left) | set(right)):
            changed.append(day)
    return changed


def evaluation(results, arm=CONTROL):
    return results[job_name((arm, COST_BPS, DELAY, 'evaluation'))]


def sub(results, arm):
    return results[job_name((arm, COST_BPS, DELAY, 'sub2023'))]


def log_excess(nav, control_nav):
    return math.log(float(nav)) - math.log(float(control_nav))


def log_pp(value):
    """Log excess read as a percentage-point difference."""
    return math.exp(value) - 1


def placebo_rank(root, results):
    """Locate FR25's evaluation-window excess inside the 200 declared draws."""
    control = evaluation(results, CONTROL)
    cp_total = control['total_return']
    observed = log_excess(evaluation(results, CANDIDATE)['terminal_nav'], control['terminal_nav'])
    changes = {draw: len(changed_vs_control(root, placebo_arm(draw))) for draw in range(1, DRAWS + 1)}
    rows, values = [], []
    for draw in range(1, DRAWS + 1):
        arm = placebo_arm(draw)
        s = evaluation(results, arm)
        value = log_excess(s['terminal_nav'], control['terminal_nav'])
        rows.append(dict(draw=draw, arm=arm, terminal_nav=s['terminal_nav'], total_return=s['total_return'],
                         log_excess=value, excess_pp=s['total_return'] - cp_total,
                         cagr=s['cagr'], sharpe=s['sharpe_zero_cash'], calmar=s['calmar'],
                         max_drawdown=s['max_drawdown'], annual_turnover=s['annual_turnover'],
                         mean_gross=s['mean_gross'], changed_selections=changes[draw]))
        values.append(value)
    rows.sort(key=lambda r: -r['log_excess'])
    for index, row in enumerate(rows, start=1):
        row['rank'] = index
    values = np.array(sorted(values))
    q90 = float(np.percentile(values, 100 * PLACEBO_PERCENTILE))
    below = int(sum(1 for v in values if v < observed - 1e-12))
    equal = int(sum(1 for v in values if abs(v - observed) <= 1e-12))
    counts, edges = np.histogram(values, bins=24)
    return dict(version='fr25-placebo-partb-v1', draws=DRAWS, seed=SEED,
        statistic='log(terminal NAV of the draw) - log(terminal NAV of CP), fresh-cash evaluation replay',
        excess_definition='percentage-point difference of total returns, the Part A convention; the log form is '
                          'the ranked statistic',
        observed_log_excess=observed,
        observed_excess_pp=evaluation(results, CANDIDATE)['total_return'] - cp_total,
        observed_changed_selections=len(changed_vs_control(root, CANDIDATE)),
        observed_rank=int(below + equal + 1), draws_below=below, draws_equal=equal,
        percentile=(below + 0.5 * equal) / len(values), q90=q90, required_percentile=PLACEBO_PERCENTILE,
        placebo_check_passes=bool(observed > q90),
        summary=dict(mean=float(values.mean()), sd=float(values.std(ddof=1)), minimum=float(values.min()),
                     maximum=float(values.max()), median=float(np.median(values)),
                     p05=float(np.percentile(values, 5)), p25=float(np.percentile(values, 25)),
                     p75=float(np.percentile(values, 75)), p95=float(np.percentile(values, 95)),
                     share_positive=float((values > 0).mean()),
                     draws_beating_fr25=int(sum(1 for v in values if v > observed + 1e-12))),
        histogram=dict(counts=[int(c) for c in counts], edges=[float(e) for e in edges]),
        draws_sorted=rows)


def root_protocol(root):
    return read_json(Path(root) / 'protocol.json')


def sensitivity_surface(root, results):
    rows = []
    control = evaluation(results, CONTROL)
    cp_total = control['total_return']
    diagnostics = read_json(root / 'decision_diagnostics.json')
    for n in SLOTS:
        for w in RIDGE_WEIGHTS_PCT:
            baseline = (n, w) == SENSITIVITY_BASELINE
            arm = CANDIDATE if baseline else variant_name(n, w)
            source = CANDIDATE if baseline else (BASELINE_ARM if arm == BASELINE_ARM else arm)
            s = evaluation(results, arm)
            rows.append(dict(slots=n, ridge_weight_pct=w, arm=arm, baseline=baseline,
                cagr=s['cagr'], sharpe=s['sharpe_zero_cash'], calmar=s['calmar'],
                max_drawdown=s['max_drawdown'], annual_turnover=s['annual_turnover'], mean_gross=s['mean_gross'],
                log_excess=log_excess(s['terminal_nav'], control['terminal_nav']),
                excess_pp=s['total_return'] - cp_total,
                changed_selections=len(changed_vs_control(root, arm)),
                added_names=sum(int(v['changes']) for v in diagnostics[source].values())))
    return dict(reference=dict(arm=CONTROL, cagr=control['cagr'], sharpe=control['sharpe_zero_cash'],
                               calmar=control['calmar'], max_drawdown=control['max_drawdown'],
                               annual_turnover=control['annual_turnover'], mean_gross=control['mean_gross']),
                cells=rows,
                note='The same axes the parent study already varied. A surface, not a search, and not '
                     'out-of-sample evidence.')


def refit_comparison(root, results):
    rows = {}
    for arm in (CONTROL, CANDIDATE, REFIT_ARM):
        s = sub(results, arm)
        rows[arm] = dict(arm=arm, cagr=s['cagr'], sharpe=s['sharpe_zero_cash'], calmar=s['calmar'],
                         max_drawdown=s['max_drawdown'], annual_turnover=s['annual_turnover'],
                         mean_gross=s['mean_gross'], terminal_nav=s['terminal_nav'],
                         total_return=s['total_return'])
    cp_total = rows[CONTROL]['total_return']
    for arm, row in rows.items():
        row['log_excess'] = math.log(row['terminal_nav']) - math.log(rows[CONTROL]['terminal_nav'])
        row['excess_pp'] = row['total_return'] - cp_total
    diagnostics = read_json(root / 'decision_diagnostics.json')
    days = sorted(diagnostics[REFIT_ARM])
    changed, rank_correlations, forecast_gaps = [], [], []
    for day in days:
        left = diagnostics[REFIT_ARM][day]
        right = diagnostics[CANDIDATE][day]
        if left['selected'] != right['selected']:
            changed.append(dict(day=day, refit=left['selected'], fr25=right['selected']))
        left_table, right_table = left['rank_table'], right['rank_table']
        if not left_table or not right_table:
            continue
        symbols = sorted(left_table)
        a = np.array([float(left_table[s]['ridge']) for s in symbols])
        b = np.array([float(right_table[s]['ridge']) for s in symbols])
        rank_correlations.append(float(np.corrcoef(a, b)[0, 1]))
        forecast_gaps.append(float(np.mean(np.abs(a - b))))
    return dict(window_start=SUB_START, decisions=len(days), arms=rows,
                sample=refit_ridge(days[0])['refit'] if days else None,
                changed_selections=len(changed), changes=changed,
                mean_ridge_rank_correlation_between_refit_and_fr25=float(np.mean(rank_correlations))
                    if rank_correlations else None,
                mean_absolute_ridge_rank_gap=float(np.mean(forecast_gaps)) if forecast_gaps else None,
                note='Fresh, identical cash start on the first 2023 decision for all three arms, so the '
                     'comparison is like-for-like rather than a continuation of a path the refit could not '
                     'have traded.')


def part_a_checks(root, parent=PARENT):
    """Restate the three pre-existing frozen checks from the parent's published replays."""
    from systematic_trading.research import fr25_robustness as part_a
    data = part_a.load(Path(parent))
    changes = part_a.changed_decisions(data['candidate'], data['control'])
    years = part_a.yearly_excess(data['dates'], data['nav_candidate'], data['nav_control'])
    attribution = part_a.leave_one_out(data['dates'], data['nav_candidate'], data['nav_control'], changes)
    blocks = part_a._bootstrap_by_block(data['dates'], data['nav_candidate'], data['nav_control'])
    published = Path(parent) / 'statistics.json'
    return dict(attribution=attribution, years=years, bootstrap=blocks, concentration=part_a.concentration(
        attribution, years), parent_statistics_present=published.exists())


def assess(placebo, checks):
    """Apply the frozen tolerance with both readings of its verdict sentence."""
    from systematic_trading.research import fr25_robustness as part_a
    verdict = part_a.assess(checks['attribution'], checks['years'], checks['bootstrap'],
                            placebo_percentile=placebo['q90'])
    placebo_ok = placebo['placebo_check_passes']
    declared = ('preserve' if all(verdict[k] for k in ('years_test', 'leave_one_out_test', 'interval_test'))
                and placebo_ok else
                'reject' if (checks['attribution']['total_return_difference'] <= 0
                             or not verdict['leave_one_out_test'] or not placebo_ok) else 'inconclusive')
    return dict(frozen_tolerance=verdict, placebo_test=placebo_ok, declared_mapping=declared,
                literal_mapping=verdict['status'],
                retention_verdict='not preserved' if not (placebo_ok and verdict['years_test']
                    and verdict['leave_one_out_test'] and verdict['interval_test']) else 'preserved',
                mapping=VERDICT_MAPPING,
                note='Retention requires all four frozen checks. The frozen 6-month bootstrap lower bound '
                     'failed in Part A and Part B may not rescue a failed interval test, so "preserve" is '
                     'unreachable and the retention verdict is "not preserved" under either reading.')


def summarize(root):
    from systematic_trading.research.fr25_placebo_study import initialize
    root = Path(root)
    checked_files(root, 'input_manifest.json')
    checked_files(root, 'decision_manifest.json')
    initialize(root)
    bridges = verify_decisions(root)
    randomisation = verify_placebo(root)
    refit_days = sorted(read_json(root / 'decision_diagnostics.json')[REFIT_ARM])
    parity = [refit_parity(day) for day in (refit_days[0], refit_days[len(refit_days) // 2], refit_days[-1])]
    if not all(row['full_sample_matches'] for row in parity):
        raise ValueError('Refit machinery does not reproduce the frozen forecasts')
    if not all(row['subset_sample_equals_full'] or row['subset_changes_the_forecast'] for row in parity):
        raise ValueError('Refit sample does not explain its forecasts')
    if not any(row['subset_changes_the_forecast'] for row in parity):
        raise ValueError('The data-through-2022 subset never changes a forecast')
    results = load_results(root)
    parent_stats = read_json(PARENT / 'statistics.json')
    control_parity = {}
    for arm in (CANDIDATE, CONTROL, 'M1'):
        name = job_name((arm, COST_BPS, DELAY, 'evaluation'))
        if name not in parent_stats:
            raise ValueError('Parent reference replay missing: ' + name)
        for key in ('cagr', 'sharpe_zero_cash', 'terminal_nav', 'max_drawdown'):
            if abs(results[name][key] - parent_stats[name][key]) > 1e-12:
                raise ValueError(f'{arm} evaluation replay differs from the parent on {key}')
        control_parity[arm] = True
    placebo = placebo_rank(root, results)
    if placebo['observed_changed_selections'] != 13:
        raise ValueError('FR25 changed-selection count differs from the published Part A finding')
    payload = dict(version='fr25-placebo-partb-v1', protocol=root_protocol(root), bridges=bridges,
        randomisation=randomisation, refit_parity=parity, control_parity=control_parity,
        placebo=placebo, sensitivity=sensitivity_surface(root, results),
        refit=refit_comparison(root, results), results=results, promotion_eligible=False)
    payload['checks'] = part_a_checks(root)
    payload['verdict'] = assess(placebo, payload['checks'])
    write_json(root / 'analysis.json', {k: v for k, v in payload.items() if k != 'results'})
    write_json(root / 'statistics.json', results)
    write_json(root / 'statistics_receipt.json', dict(sha256=sha256(root / 'statistics.json')))
    return dict(replays=len(results), percentile=placebo['percentile'], q90=placebo['q90'],
                observed=placebo['observed_log_excess'], placebo_passes=placebo['placebo_check_passes'],
                verdict=payload['verdict']['declared_mapping'])


def finalize(root):
    root = Path(root)
    if sha256(root / 'statistics.json') != read_json(root / 'statistics_receipt.json')['sha256']:
        raise ValueError('Statistics changed after inference')
    analysis = read_json(root / 'analysis.json')
    write_json(root / 'report.json', analysis)
    write_json(root / 'report_receipt.json', dict(sha256=sha256(root / 'report.json'),
        statistics_sha256=sha256(root / 'statistics.json'), input_sha256=sha256(root / 'input_manifest.json'),
        decision_manifest_sha256=sha256(root / 'decision_manifest.json'),
        placebo_sha256=sha256(root / 'placebo.json')))
    return dict(percentile=analysis['placebo']['percentile'], verdict=analysis['verdict']['declared_mapping'],
                retention=analysis['verdict']['retention_verdict'])


def verify(root):
    """Every bridge and invariant, recomputed from the frozen evidence."""
    from systematic_trading.research.fr25_placebo_study import initialize
    root = Path(root)
    checked_files(root, 'input_manifest.json')
    checked_files(root, 'decision_manifest.json')
    initialize(root)
    receipt = read_json(root / 'data_receipt.json')
    live = {name: sha256(Path(p)) for name, p in
            [(name, PARENT / name) for name in receipt['parent_hashes']]}
    if live != receipt['parent_hashes']:
        raise ValueError('The pinned parent study changed after this study was frozen')
    parity = [refit_parity(day) for day in (SUB_START, '2024-01-02', '2026-10-01')]
    if not all(row['full_sample_matches'] for row in parity):
        raise ValueError('Refit machinery does not reproduce the frozen forecasts')
    return dict(parent_unchanged=True, bridges=verify_decisions(root), randomisation=verify_placebo(root),
                refit_parity=parity)


def num(x, n=3):
    return 'n/a' if x is None else f'{x:.{n}f}'


def pct(x, n=2):
    return 'n/a' if x is None else f'{x:.{n}%}'


def delta(x, n=2):
    return 'n/a' if x is None else f'{x:+.{n}f}'


def table(headers, rows):
    def cell(x):
        return str(x) if str(x).startswith('<a ') else html.escape(str(x))
    return ('<div class="scroll"><table><thead><tr>' + ''.join('<th>' + cell(x) + '</th>' for x in headers)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + cell(x) + '</td>' for x in row)
            + '</tr>' for row in rows) + '</tbody></table></div>')


def flow(steps):
    svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {len(steps) * 57 + 10}">'
    for i, line in enumerate(steps):
        svg += (f'<rect x="5" y="{i * 57 + 5}" width="1190" height="48" rx="8" fill="#e8f0f2"/>'
                f'<text x="16" y="{i * 57 + 34}" font-family="sans-serif" font-size="12">{i + 1}. '
                f'{html.escape(line)}</text>')
    return svg + '</svg>'


def decision_steps():
    return [
        'Verify the pinned parent selection-blend protocol, input manifest and decision manifest by hash',
        'Recompute every FR25 decision in this root and require exact equality with the parent decisions',
        'Permute the frozen financial-ridge forecast values across the available symbols: SeedSequence([seed, draw, decision ordinal])',
        'Inject the permuted assignment as models[symbol][linear_forecast] plus ready and let SelectionBlend re-rank it',
        'Require the realised ridge rank to equal the permuted frozen ridge rank exactly: one respect differs, the assignment',
        'Eligibility, abstention, top-six selection, defensive fallback and every downstream sizing overlay are the engine’s own',
        'Freeze targets; replay each draw with the shared reference engine at 5bp, zero delay, fresh cash on the evaluation start',
        'Locate the observed FR25 excess over CP in the 200-draw distribution at the predeclared 90th percentile',
        'Refit the ridge on labels completed by 2022-12-31, replay 2023 onward against identical fresh-cash FR25 and CP arms',
        'Vary slots 4/5/6/7 and ridge weights 10/25/40 percent as a surface on the same frozen rank tables',
        'Report the four frozen checks and the verdict; retain every draw, including the ones that beat FR25',
    ]


def artifacts(root, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root, output = Path(root), Path(output)
    report = read_json(root / 'report.json')
    if sha256(root / 'report.json') != read_json(root / 'report_receipt.json')['sha256']:
        raise ValueError('Report changed')
    p, placebo, verdict = report['protocol'], report['placebo'], report['verdict']
    checks = report['checks']
    sensitivity, refit = report['sensitivity'], report['refit']
    output.mkdir(parents=True, exist_ok=True)
    (output / 'reports').mkdir(exist_ok=True)
    ranked = placebo['draws_sorted']
    best, worst = ranked[0], ranked[-1]
    figure_arms = [(CONTROL, 'CP'), (CANDIDATE, 'FR25'), (best['arm'], f"best draw #{best['draw']}"),
                   (worst['arm'], f"worst draw #{worst['draw']}")]
    fig, axes = plt.subplots(1, 2, figsize=(15, 5.2), layout='constrained')
    fig.set_facecolor('#fcfaf5')
    for ax in axes:
        ax.set_facecolor('#fcfaf5')
        ax.spines[['top', 'right']].set_visible(False)
    ax = axes[0]
    edges = np.array(placebo['histogram']['edges'])
    counts = np.array(placebo['histogram']['counts'])
    ax.bar(edges[:-1] * 100, counts, width=np.diff(edges) * 100 * 0.92, align='edge', color='#7fa8b4')
    ax.axvline(placebo['q90'] * 100, color='#826b4e', linestyle='--', label='90th percentile')
    ax.axvline(placebo['observed_log_excess'] * 100, color='#b0432f', lw=2.4, label='observed FR25')
    ax.set_xlabel('log excess over CP, percentage points')
    ax.set_ylabel('draws')
    ax.set_title(f"Placebo distribution, {placebo['draws']} declared draws")
    ax.legend(fontsize=8, frameon=False)
    from systematic_trading.research.tracked_runtime import report_result
    ax = axes[1]
    for arm, label in figure_arms:
        name = job_name((arm, COST_BPS, DELAY, 'evaluation'))
        economic = read_json(root / 'python' / (name + '.json'))
        quotes = read_json(root / 'bundles' / name / 'quotes.json')
        series = report_result(economic, quotes, p['initial_cash_usd'], '2020-12-31')['nav_series']
        values = np.array([float(r['nav_cnh']) for r in series])
        days = [r['trade_date'] for r in series]
        ax.plot(days, values / 1e6, label=f'{label} · {pct(values[-1] / 1e6 - 1)}',
                lw=2.2 if arm in (CANDIDATE, CONTROL) else 1.2)
    ax.set_title('Fresh-cash evaluation NAV')
    ax.set_ylabel('value / initial USD 1m')
    ax.legend(fontsize=8, frameon=False)
    fig.savefig(output / 'placebo.png', dpi=150)
    plt.close(fig)
    rows = []
    for row in ranked:
        rows.append([row['rank'], f"#{row['draw']}", num(row['log_excess'] * 100), delta(100 * row['excess_pp']) + 'pp',
                     pct(row['total_return']), num(row['sharpe']), num(row['calmar']), pct(row['max_drawdown']),
                     row['changed_selections']])
    draw_headers = ['Rank', 'Draw', 'Log excess (pp)', 'Excess vs CP (pp)', 'Total return', 'Sharpe', 'Calmar',
                    'Max DD', 'Decisions differing from CP']
    cells = sensitivity['cells']
    base = sensitivity['reference']
    summary = placebo['summary']
    body = f'''<header><div class="eyebrow">P4.14 PART B · FR25 ROBUSTNESS · 10 OCTOBER 2026</div>
    <h1>Does the financial ridge contribute anything a coin toss would not?</h1>
    <p class="lead">200 declared placebo draws permute the frozen financial-ridge assignment across the fourteen
    candidates and are replayed through the engine’s own selection, eligibility and sizing contracts. Plus a
    data-through-2022 refit and the top-N / ridge-weight sensitivity surface.</p>
    <p>Every draw is retained, including the ones that beat FR25. Research only: no monitored strategy, allocation,
    approval or broker record was changed by this study.</p></header>
    <nav><a href="#verdict">Verdict</a><a href="#placebo">Placebo</a><a href="#refit">Refit</a>
    <a href="#sensitivity">Sensitivity</a><a href="#method">Method</a><a href="#evidence">Evidence</a></nav>
    <div class="cards">
    <div><b>{num(placebo['percentile'] * 100, 2)}th</b><span>FR25 percentile in the placebo distribution
    (needs above {num(placebo['required_percentile'] * 100, 0)}). Beaten by {summary['draws_beating_fr25']} of
    {placebo['draws']} random assignments.</span></div>
    <div><b>{'pass' if placebo['placebo_check_passes'] else 'fail'}</b><span>Frozen placebo check:
    {delta(100 * placebo['observed_excess_pp'])}pp observed excess over CP, against a
    {pct(summary['share_positive'])} chance that a random assignment is merely positive.</span></div>
    <div><b>{verdict['retention_verdict']}</b><span>Frozen retention verdict. Reachable verdicts are
    {verdict['declared_mapping']} under the declared mapping and {verdict['literal_mapping']} under the plan’s
    literal sentence.</span></div></div>
    <p class="callout">{html.escape(verdict['note'])}</p>
    <img class="figure" src="placebo.png" alt="Placebo distribution of the FR25 excess and the evaluation NAV paths">
    <section id="verdict"><h2>The four frozen checks</h2>
    <p>The retention tolerance was frozen in the plan before any Part A statistic was computed. Three checks come
    from the published selection-blend replays; the fourth is this study’s. All four are required for retention.</p>'''
    frozen = verdict['frozen_tolerance']
    interval = checks['bootstrap'][str(TOLERANCE['block_for_lower_bound'])]
    body += table(['Frozen check', 'Result', 'Evidence'], [
        ['Excess over CP positive in at least two-thirds of complete calendar years',
         ('pass' if frozen['years_test'] else 'fail'),
         f"{frozen['positive_complete_years']} of {frozen['complete_years']} complete years"],
        ['Positive after dropping any single changed selection',
         ('pass' if frozen['leave_one_out_test'] else 'fail'),
         f"worst single tile {delta(min(r['log_difference'] for r in checks['attribution']['contributions']) * 100)}pp"],
        [f"Positive 95% bootstrap lower bound at the {TOLERANCE['block_for_lower_bound']}-month block",
         ('pass' if frozen['interval_test'] else 'fail'),
         f"[{num(interval['ci95'][0] * 100)}, {num(interval['ci95'][1] * 100)}] percentage points"],
        [f"Above the {num(placebo['required_percentile'] * 100, 0)}th percentile of the matched-availability "
         f"placebo distribution",
         ('pass' if placebo['placebo_check_passes'] else 'fail'),
         f"percentile {num(placebo['percentile'] * 100, 2)}, 90th percentile "
         f"{num(placebo['q90'] * 100, 3)}pp"]])
    body += f'''<p><b>What a passing placebo could and could not have done.</b> The plan says Part B can only move
    the verdict between <i>preserve</i> and <i>inconclusive</i>, and cannot rescue a failed year or interval test.
    The interval test already failed in Part A, so retention was already out of reach before this study ran; the
    placebo cannot restore it. It is still decisive for a different question — whether the ridge rank assignment
    carries information at all, as opposed to any permutation of it doing as well.</p>
    <p><b>The verdict mapping is reported twice because the plan is ambiguous.</b> {html.escape(VERDICT_MAPPING['alternative_reading'])}
    The declared mapping treats a failed placebo as a rejection of the mechanism rather than as noise-limited
    inference, because a placebo failure is positive evidence that the assignment is uninformative.</p></section>
    <section id="placebo"><h2>The placebo distribution</h2>
    <p>At each of the {placebo['draws']} draws the frozen financial-ridge forecast values were permuted across the
    fourteen available symbols, injected through the engine’s own ranking, and replayed. FR25 scored
    {pct(frozen['checks']['total_return_difference'])} over CP on the published evidence; the draws span
    {pct(log_pp(summary['minimum']))} to {pct(log_pp(summary['maximum']))}, median
    {pct(log_pp(summary['median']))}.</p>'''
    body += table(['Distribution', 'log excess over CP (pp)', 'ratio equivalent'], [
        ['FR25 observed', num(placebo['observed_log_excess'] * 100, 3), pct(log_pp(placebo['observed_log_excess']))],
        ['Median draw', num(summary['median'] * 100, 3), pct(log_pp(summary['median']))],
        ['Mean draw', num(summary['mean'] * 100, 3), pct(log_pp(summary['mean']))],
        ['Best draw', num(summary['maximum'] * 100, 3), pct(log_pp(summary['maximum']))],
        ['Worst draw', num(summary['minimum'] * 100, 3), pct(log_pp(summary['minimum']))],
        ['90th percentile', num(placebo['q90'] * 100, 3), pct(log_pp(placebo['q90']))],
        ['Share of draws above zero', pct(summary['share_positive']), '—']])
    body += (f'''<p>The ranked statistic is the log excess, which telescopes exactly; the ratio-equivalent column is
    exp(log) − 1. The arithmetic difference of total returns, the convention Part A reports as
    {delta(100 * placebo['observed_excess_pp'])}pp, is the "Excess vs CP" column of the draw table
    below.</p>''')
    beats = [row for row in ranked if row['log_excess'] > placebo['observed_log_excess'] + 1e-12]
    fr25_changes = placebo['observed_changed_selections']
    body += ('<h3>Strongest and weakest random assignments</h3><p>Every draw is kept as evidence. A draw that '
             'beats FR25 is not an error: it is the measurement. All 200 replays, with their bundles, quotes and '
             'fills, remain in the evidence root; full reports are published here for the strongest and weakest '
             'draws.</p>')
    if beats:
        body += (f"<p>The {len(beats)} draws above FR25 differ from CP on "
                 f"{num(float(np.mean([row['changed_selections'] for row in beats])), 1)} of 70 decisions on "
                 f"average, against FR25's {fr25_changes}, and the weakest draws differ on "
                 f"{num(float(np.mean([row['changed_selections'] for row in ranked[-len(beats):]])), 1)}. The "
                 f"positive tail of this distribution comes from aggressively re-ordered selection rather than from "
                 f"better ridge information, which is why beating it is a weak claim and why a passing placebo does "
                 f"not by itself establish superiority.</p>")
    body += table(draw_headers, rows[:8] + rows[-8:])
    body += f'<details><summary>All {placebo["draws"]} draws</summary>'
    body += table(draw_headers, rows)
    body += '</details></section>'
    body += f'''<section id="refit"><h2>Was the edge fitted on the full sample?</h2>
    <p>The financial ridge was refitted using only the {refit['sample']['rows']} training labels completed by
    {refit['sample']['cutoff']} (the last of which ends {refit['sample']['last_label_end']}) and replayed from
    {refit['window_start']}. This is not a re-fit of the whole recipe: only the ridge training sample changed. All
    three arms start from identical fresh cash on {refit['window_start']} with the same engine, costs and
    windows.</p>'''
    body += table(['Arm', 'CAGR', 'Sharpe', 'Calmar', 'Max DD', 'Excess vs CP (pp)', 'Log excess (pp)',
                   'Changed selections'],
        [[f'<a href="reports/{a}.html">{LABELS[a]}</a>' + (' <b>(reference)</b>' if a == REFIT_ARM else ''),
          pct(r['cagr']), num(r['sharpe']), num(r['calmar']), pct(r['max_drawdown']),
          delta(100 * r['excess_pp']) + 'pp',
          num(r['log_excess'] * 100, 3), refit['changed_selections'] if a == REFIT_ARM else '']
         for a, r in refit['arms'].items()])
    body += (f"<p>The refit changes {refit['changed_selections']} of {refit['decisions']} selections against FR25, "
             f"with a mean ridge-rank correlation of "
             f"{num(refit['mean_ridge_rank_correlation_between_refit_and_fr25'])} and a mean absolute rank gap of "
             f"{num(refit['mean_absolute_ridge_rank_gap'])}. It keeps "
             f"{delta(100 * refit['arms'][REFIT_ARM]['excess_pp'])}pp of FR25's "
             f"{delta(100 * refit['arms'][CANDIDATE]['excess_pp'])}pp excess over CP on this window and has a lower "
             f"maximum drawdown ({pct(refit['arms'][REFIT_ARM]['max_drawdown'])} against "
             f"{pct(refit['arms'][CANDIDATE]['max_drawdown'])}), so a ridge that never saw a post-2022 label still "
             f"beats CP, but full-sample fitting accounts for the rest. {html.escape(refit['note'])}</p></section>")
    body += ('''<section id="sensitivity"><h2>Slots and ridge weight</h2>
    <p>FR25 selects six assets with 25% of the blended rank coming from the financial ridge. These are the two
    axes the parent study already varied. The surface is reported as a whole: it is not a search, the best cell is
    not a discovery, and none of it is out-of-sample evidence.</p>''')
    body += table(['Slots', 'Ridge weight'] + [f'{w}%' for w in RIDGE_WEIGHTS_PCT],
        [[f'Top {n}', 'CAGR excess vs CP'] + [delta(100 * next(c['excess_pp'] for c in cells
            if c['slots'] == n and c['ridge_weight_pct'] == w), 2) + 'pp' for w in RIDGE_WEIGHTS_PCT]
         for n in SLOTS])
    body += table(['Slots', 'Ridge weight'] + [f'{w}%' for w in RIDGE_WEIGHTS_PCT],
        [[f'Top {n}', 'Sharpe excess vs CP'] + [delta(next(c['sharpe'] for c in cells if c['slots'] == n
            and c['ridge_weight_pct'] == w) - base['sharpe']) for w in RIDGE_WEIGHTS_PCT] for n in SLOTS])
    body += table(['Configuration', 'Arm', 'CAGR', 'Sharpe', 'Calmar', 'Max DD', 'Turnover / year',
                   'Mean invested', 'Excess vs CP (pp)', 'Decisions differing from CP'],
        [[f"Top {c['slots']} · {c['ridge_weight_pct']}%", ('FR25 (frozen baseline)' if c['baseline']
          else f'<a href="reports/{c["arm"]}.html">{c["arm"]}</a>'), pct(c['cagr']), num(c['sharpe']),
          num(c['calmar']), pct(c['max_drawdown']), num(c['annual_turnover'], 2) + '×', pct(c['mean_gross']),
          delta(100 * c['excess_pp']) + 'pp', c['changed_selections']] for c in cells])
    body += f"<p>Reference: the capped M1 control returned {pct(base['cagr'])} CAGR with Sharpe {num(base['sharpe'])} "\
            f"and Calmar {num(base['calmar'])} over the same window.</p></section>"
    body += f'''<section id="method"><h2>Complete decision flow</h2>
    <p>A placebo must differ from FR25 in exactly one respect, so the perturbation is applied inside the engine
    rather than re-implemented beside it.</p>
    {flow(decision_steps())}
    <p>Randomisation: {html.escape(p['placebo']['randomisation'])} {html.escape(p['placebo']['generator'])}</p>
    <p>Injection: {html.escape(p['placebo']['injection'])} {html.escape(p['placebo']['availability'])}</p>
    <p>Sentinel: {html.escape(p['placebo']['sentinel'])}</p></section>'''
    body += ('<section id="evidence"><h2>Verification and evidence</h2>')
    body += table(['Bridge', 'Shared decisions', 'Result'], [
        [f'{a} re-derived in this root', v['shared_decisions'],
         'exact match with the parent' if v['matches_frozen_parent'] else 'MISMATCH']
        for a, v in report['bridges'].items()])
    body += table(['Control replay', 'Matches the parent published replay'],
        [[a, 'yes' if v else 'no'] for a, v in report['control_parity'].items()])
    body += table(['Refit machinery check', 'Frozen training rows', 'Data-through-2022 rows',
                   'Worst difference from the frozen forecast'],
        [[row['day'], row['rows'], row['subset_rows'], num(row['worst_absolute_difference'], 12)]
         for row in report['refit_parity']])
    body += (f"<p>Refitting on the parent's own frozen training rows reproduces the published forecasts exactly, "
             f"which is what makes the data-through-2022 refit a re-fit rather than an approximation. "
             f"{report['randomisation']['draws_checked']} recorded injections were recomputed from the declared "
             f"seed and re-checked against the frozen marginal; "
             f"{report['randomisation']['abstained_days']} abstained decision was left untouched.</p>")
    body += ('<p>Every replay is a fresh-cash evaluation run at 5bp with zero delay and zero-interest cash. The '
             'reference engine is the same one the parent study validated against native LEAN runs; this study adds '
             'no new model fit, no new data and no new price basis.</p>')
    body += ('<p><a href="../../var/research/fr25-placebo-20261010-v1/protocol.json">Frozen Part B protocol</a> · '
             '<a href="../../var/research/fr25-placebo-20261010-v1/analysis.json">Analysis and verdict</a> · '
             '<a href="../../var/research/fr25-placebo-20261010-v1/placebo.json">Every draw, permutation and '
             'injection</a> · <a href="../../var/research/fr25-placebo-20261010-v1/decision_manifest.json">'
             'Decision manifest</a> · <a href="../../var/research/fr25-placebo-20261010-v1/data_receipt.json">'
             'Pinned parent lineage</a> · <a href="../selection-blend-2026-10-10/index.html">Parent selection '
             'study</a></p>')
    body += '''<p><b>Limitations.</b> The evaluation window was already inspected when FR25 was chosen, so nothing
    here is out-of-sample evidence. A permutation destroys the assignment of ridge information but keeps its
    availability, its marginal distribution and the health of the downstream sizing chain, so this is a test of the
    ridge’s ranking information rather than of the ridge family as a whole. The sensitivity surface re-uses axes
    the parent study already varied and cannot be presented as a fresh result. The refit compares a 2023-onward
    fresh-cash path and does not re-fit the momentum or XGBoost stages. A reject is a research finding: it does not
    by itself deallocate, and switching remains an operator decision through the existing allocation workflow.</p>
    </section>'''
    css = ('*{box-sizing:border-box}body{margin:0;background:#f3f0e8;color:#263c47;font:16px/1.6 system-ui,sans-serif}'
           'main{max-width:1320px;margin:auto;padding:44px 32px}h1{font-size:44px;line-height:1.1;margin:16px 0}'
           'h2{font-size:27px;line-height:1.25}h3{font-size:19px;margin-top:28px}.eyebrow{font-size:12px;'
           'letter-spacing:2px;font-weight:700}.lead{font-size:22px;max-width:1050px}a{color:#12617b}'
           'nav{display:flex;gap:22px;flex-wrap:wrap;margin:26px 0}.cards{display:grid;'
           'grid-template-columns:repeat(3,1fr);gap:16px}.cards>div{padding:20px;background:#fffdf7;'
           'border-top:3px solid #367d8f}.cards b{display:block;font-size:30px}.cards span{font-size:14px}'
           '.callout{padding:18px;background:#e8efed;border-left:4px solid #377d8c}.figure{width:100%;height:auto}'
           'section{padding:24px 28px;background:#fffdf8;margin:24px 0;border:1px solid #ddd8cb;border-radius:7px}'
           '.scroll{overflow:auto;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:13px;'
           'font-variant-numeric:tabular-nums}th,td{padding:10px 11px;text-align:right;'
           'border-bottom:1px solid #deded5;white-space:nowrap}th{background:#e6eeec}'
           'td:first-child,th:first-child{text-align:left}tr:nth-child(even) td{background:#f7f6f0}'
           'details{padding:16px 0;border-top:1px solid #ccc}summary{cursor:pointer;font-weight:650}'
           'p{max-width:1160px}@media(max-width:700px){main{padding:24px 12px}h1{font-size:34px}'
           '.cards{grid-template-columns:1fr}section{padding:18px 12px}.lead{font-size:18px}}')
    (output / 'index.html').write_text(
        '<!doctype html><html lang="en"><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>FR25 placebo, refit and sensitivity</title><style>' + css + '</style><main>' + body
        + '</main></html>', encoding='utf8')
    featured = [CONTROL, CANDIDATE, best['arm'], worst['arm'], REFIT_ARM,
                *[variant_name(n, w) for n, w in sensitivity_arms()]]
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data, render_backtest_report_html
    for arm in featured:
        window = 'sub2023' if arm == REFIT_ARM else 'evaluation'
        name = job_name((arm, COST_BPS, DELAY, window))
        economic = read_json(root / 'python' / (name + '.json'))
        quotes = read_json(root / 'bundles' / name / 'quotes.json')
        anchor = '2022-12-30' if window == 'sub2023' else '2020-12-31'
        result = report_result(economic, quotes, p['initial_cash_usd'], anchor)
        benchmark = CANDIDATE if arm != CANDIDATE else CONTROL
        bench_name = job_name((benchmark, COST_BPS, DELAY, window))
        bench = report_result(read_json(root / 'python' / (bench_name + '.json')),
                              read_json(root / 'bundles' / bench_name / 'quotes.json'),
                              p['initial_cash_usd'], anchor)
        data, warnings = build_backtest_report_data(result=result, result_path=root / 'python' / (name + '.json'),
            split_date=SUB_START if window == 'sub2023' else p['evaluation_start'],
            benchmark_name=LABELS.get(benchmark, benchmark), benchmark_nav_series=bench['nav_series'],
            extra_benchmarks=[], market_prices={s: {d: float(q['close']) for d, q in rows.items()}
                                                for s, rows in quotes.items()},
            market_fx_rates={v['date']: 1. for v in economic['nav']})
        title = LABELS.get(arm, arm) if not draw_of(arm) else (f'Placebo draw #{draw_of(arm)} · '
                                                               f'{"best" if arm == best["arm"] else "worst"} of '
                                                               f'{placebo["draws"]}')
        data.update(title=title + ' · FR25 Part B', accountingCurrency='USD',
            database='Frozen selection-blend evidence and pinned causal models',
            allocationSource='Simulated fills', splitLabel='Previously inspected chronological boundary',
            sampleLabels={'in_sample': 'pre-2021 retrospective', 'out_of_sample': '2021 onward retrospective'},
            decisionDiagrams=[dict(title='Complete decision flow', svg=flow(decision_steps()))],
            strategyDefinition=dict(id=arm, protocol=p),
            warnings=[*warnings, *p.get('limitations', []),
                      'This is a fresh-cash evaluation replay of a frozen research arm, not a monitored strategy '
                      'and not promotion evidence.'])
        rendered = render_backtest_report_html(data)
        rendered = re.sub(r'(href=["\'])(/[^"\']*)', r'\1http://127.0.0.1:8000\2', rendered)
        (output / 'reports' / (arm + '.html')).write_text(rendered, encoding='utf8')
    write_json(root / 'presentation_receipt.json', dict(report_sha256=sha256(root / 'report.json'),
        files={f.relative_to(output).as_posix(): sha256(f) for f in output.rglob('*') if f.is_file()},
        sources={str(Path(__file__)): sha256(Path(__file__))}))
    return dict(output=str(output), featured=len(featured))
