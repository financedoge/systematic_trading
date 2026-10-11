"""Analysis and presentation for P4.17f: which exit rule, at which tilt size, is best net of cost."""
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research.sleeve_construction_analysis import table
from systematic_trading.research.alpha101_tilt_replay_analysis import metrics_from
from systematic_trading.research import alpha101_tilt_exit_study as study

ROOT = study.DEFAULT_ROOT
SEED = 2026101109
METRICS = ('total_return', 'cagr', 'sharpe_zero_cash', 'calmar', 'max_drawdown')


def load_all(root):
    out = {}
    for job in study.jobs():
        arm, cost, delay, window = job
        payload = read_json(Path(root) / 'python' / (study.daily.job_name(job) + '.json'))
        nav = [dict(date=row['date'], nav=float(row['nav'])) for row in payload['nav']]
        out[study.daily.job_name(job)] = dict(arm=arm, cost=cost, delay=delay, window=window, nav=nav,
                                              **metrics_from(nav))
    return out


def at(results, arm, cost=study.COST_BPS, delay=study.DELAY, window=study.WINDOW):
    return results[study.daily.job_name((arm, cost, delay, window))]


def contrasts(results, base):
    """Every arm against its own untouched control, Holm-adjusted within that book's family."""
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    tilt_arms = [arm for arm in study.arms() if study.plan(arm)['base'] == base and arm != base]
    pairs = [(arm, base) for arm in tilt_arms]
    months = sorted(at(results, base)['monthly'])
    matrix = np.array([[at(results, a)['monthly'].get(m, 0.0) - at(results, b)['monthly'].get(m, 0.0)
                        for a, b in pairs] for m in months], dtype=float)
    out = {}
    for block in (3, 6, 12):
        rows = paired_bootstrap(matrix, block=block, replications=10_000, seed=SEED)
        out[str(block)] = [dict(pair=f'{a}-{b}', **{k: study.plan(a)[k] for k in ('base', 'budget', 'rule')},
                                **row) for (a, b), row in zip(pairs, rows, strict=True)]
    return out


def summarize(root=ROOT):
    root = Path(root)
    results = load_all(root)
    costs = read_json(root / 'gate.json')['arms']
    diagnostics = read_json(root / 'decision_diagnostics.json')
    metrics = {arm: {k: v for k, v in at(results, arm).items() if k not in ('nav', 'monthly', 'daily')}
               for arm in study.arms()}
    boot = {base: contrasts(results, base) for base in study.BASES}
    optimum, significant = {}, {}
    for base in study.BASES:
        candidates = [arm for arm in study.arms() if study.plan(arm)['base'] == base and arm != base]
        optimum[base] = {metric: max(candidates, key=lambda arm: metrics[arm][metric]) for metric in METRICS}
        significant[base] = [row['pair'] for row in boot[base]['6'] if row['holm_p'] < 0.05]
    payload = dict(version=study.STUDY, protocol=read_json(root / 'protocol.json'),
                   costs=costs, metrics=metrics, diagnostics=diagnostics, contrasts=boot,
                   in_sample_optimum=optimum, family_significant=significant, promotion_eligible=False,
                   statement='Arms are ranked on outcomes net of 5/10/20bp costs with no cost filter: the '
                             'optimum below is an in-sample optimum on one inspected window, and each one is '
                             'reported beside its family-adjusted interval.')
    write_json(root / 'statistics.json', {name: {k: v for k, v in row.items() if k not in ('monthly', 'daily')}
                                          for name, row in results.items()})
    write_json(root / 'analysis.json', payload)
    return payload


def report(root=ROOT, output=None):
    root = Path(root)
    payload = read_json(root / 'analysis.json')
    output = Path(output or 'research/alpha101-tilt-exit-2026-10-11')
    output.mkdir(parents=True, exist_ok=True)
    metrics, gate, diag = payload['metrics'], payload['costs'], payload['diagnostics']

    rows = []
    for base in study.BASES:
        arms = [base] + [study.arm_name(base, budget, rule) for budget in study.BUDGETS
                         for rule in study.RULES]
        for arm in arms:
            plan = study.plan(arm)
            stats = diag[arm]
            x = '—' if plan['budget'] is None else f"{100 * plan['budget']:.0f}%"
            rows.append([base, x, plan['rule'], f"{stats['entries']:,}",
                         f"{stats['exits']:,}", f"{stats['reentries']:,}",
                         f"{metrics[arm]['total_return']:.1%}", f"{metrics[arm]['cagr']:.2%}",
                         f"{metrics[arm]['sharpe_zero_cash']:.3f}", f"{metrics[arm]['calmar']:.3f}",
                         f"{metrics[arm]['max_drawdown']:.2%}",
                         f"{gate[arm]['verdict']['annual_cost_bps']:.1f}bp",
                         gate[arm]['verdict']['status'].upper()])

    body = ['<section id="verdict"><h2>Verdict</h2>', f'<p class="lead">{payload["statement"]}</p>']
    for base in study.BASES:
        pick = payload['in_sample_optimum'][base]
        significant = payload['family_significant'][base]
        body.append(
            f'<p><b>{study.BASES[base]["label"]}.</b> Best net total return and CAGR: '
            f'<b>{study.plan(pick["cagr"])["rule"]} at X = {100 * study.plan(pick["cagr"])["budget"]:.0f}%</b>. '
            f'Best Sharpe and Calmar: <b>{study.plan(pick["sharpe_zero_cash"])["rule"]} at '
            f'X = {100 * study.plan(pick["sharpe_zero_cash"])["budget"]:.0f}%</b>. Shallowest drawdown: '
            f'<b>{study.plan(pick["max_drawdown"])["rule"]} at '
            f'X = {100 * study.plan(pick["max_drawdown"])["budget"]:.0f}%</b>. '
            f'{len(significant)} of its arms differ from the untouched book at Holm p &lt; 0.05'
            + (': ' + ', '.join(significant) if significant else ' — none does, so every optimum here is a '
                                                               'selection on noise as much as on signal') +
            '.</p>')
    body.append('</section>')

    body.append('<section id="grid"><h2>Every arm, net of cost</h2>')
    body.append(table(['Base', 'X', 'Exit rule', 'Entries', 'Exits', 'Re-entries', 'Total return', 'CAGR',
                       'Sharpe', 'Calmar', 'Max drawdown', 'Annual cost', 'P4.15 verdict'], rows))
    body.append('<p>The P4.15 verdict is shown for information only; the operator\'s objective is the optimum '
                'rather than a cost budget, so nothing here was filtered on it. Returns are already after the '
                '5bp cost charged by the replay.</p></section>')

    for base in study.BASES:
        body.append(f'<section id="contrast-{base.lower()}"><h2>{study.BASES[base]["label"]}: contrasts against '
                    'its own untouched book</h2>')
        rows = []
        for block in ('6',):
            for row in payload['contrasts'][base][block]:
                rows.append([f"{row['rule']} / {100 * row['budget']:.0f}%", f'{block}m',
                             f"{row['mean_annual']:+.2%}",
                             f"[{row['ci95'][0]:+.2%}, {row['ci95'][1]:+.2%}]", f"{row['holm_p']:.3f}"])
        body.append(table(['Exit rule / X', 'Block', 'Mean annual difference', '95% interval', 'Holm p'], rows))
        body.append('</section>')

    body.append('<section id="method"><h2>Method</h2>'
                '<p>The tilt is opened at the strategy\'s own monthly decision — the tested NAV-neutral family '
                'tilt at budget X — and is then re-read every session for the declared exit condition. '
                'EXIT-FLIP closes when the desired tilt turns against the held one; EXIT-FADE when its magnitude '
                'falls below half its entry value; EXIT-NOSIG when the signal stops ranking the book; EXIT-PNL '
                'when the tilt\'s own weighted return reaches −2%; EXIT-FLIP-REENTER also re-enters inside the '
                'month when the signal re-aligns with the entry direction at entry magnitude or more; HOLD never '
                'closes. The base book, the symbol set and the gross are untouched, so the only difference '
                'between arms is the tilt and when it is on. Decisions are frozen per arm and replayed from '
                'fresh cash at 5/10/20bp with zero and one-session delay.</p></section>')

    body.append('<section id="evidence"><h2>Verification</h2>'
                '<p><a href="../../var/research/alpha101-tilt-exit-20261011-v1/protocol.json">Frozen protocol</a> · '
                '<a href="../../var/research/alpha101-tilt-exit-20261011-v1/gate.json">Cost record</a> · '
                '<a href="../../var/research/alpha101-tilt-exit-20261011-v1/analysis.json">Analysis</a> · '
                '<a href="../alpha101-tilt-daily-2026-10-11/index.html">P4.17e</a> · '
                '<a href="../alpha101-tilt-surface-2026-10-11/index.html">P4.17d</a></p>'
                '<ul><li>Every daily row is checked against the zero floor and the 45% cap in the run that '
                'produces it.</li><li>Both base books are re-checked by hash against their frozen roots.</li>'
                '<li>Completed economics are never overwritten.</li></ul></section>')

    body.append('<section id="limits"><h2>Limits</h2><ul>'
                '<li><b>In sample.</b> One inspected window; the best arm is an optimum of a searched surface '
                'and is reported with its family-adjusted interval beside it.</li>'
                '<li><b>Entries stay monthly.</b> Only exits are intra-month; re-entry is allowed only in the '
                'EXIT-FLIP-REENTER arm.</li>'
                '<li><b>The P&amp;L stop uses the tilt\'s own weighted return</b>, a declared proxy for its '
                'contribution rather than the book\'s NAV.</li>'
                '<li><b>No promotion</b>: the 45% cap, the cash reserve and the monitored books are unchanged.'
                '</li></ul></section>')

    css = ('*{box-sizing:border-box}body{margin:0;background:#f3f0e8;color:#263c47;'
           'font:16px/1.6 system-ui,sans-serif}main{max-width:1400px;margin:0 auto;padding:40px 24px 72px}'
           'h1{font-size:30px;margin:0 0 6px}h2{font-size:21px;margin:38px 0 10px}p.lead{font-size:17px}'
           'table{border-collapse:collapse;width:100%;margin:12px 0;font-size:12.5px}'
           'th,td{border-bottom:1px solid #d8d2c4;padding:5px 7px;text-align:right}'
           'th:first-child,td:first-child,th:last-child,td:last-child{text-align:left}'
           'thead th{background:#e8e2d4}a{color:#1d6b8a}')
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>P4.17f exit rules for the Alpha101 tilt</title><style>' + css + '</style></head><body><main>'
            '<h1>P4.17f — closing the tilt when the signal stops</h1>'
            '<p>Monthly entry, declared intra-month exits, ranked on net outcomes with no cost filter.</p>'
            + ''.join(body) + '</main></body></html>')
    (output / 'index.html').write_text(html, encoding='utf-8')
    write_json(root / 'presentation_receipt.json', dict(
        analysis_sha256=sha256(root / 'analysis.json'),
        files={path.relative_to(output).as_posix(): sha256(path) for path in output.rglob('*') if path.is_file()}))
    return dict(output=str(output), arms=len(study.arms()))


if __name__ == '__main__':
    import sys
    print(report(sys.argv[1] if len(sys.argv) > 1 else ROOT, sys.argv[2] if len(sys.argv) > 2 else None))
