"""Analysis and presentation for the P4.17d tilt budget surface."""
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research.sleeve_construction_analysis import table
from systematic_trading.research.alpha101_tilt_replay_analysis import declared_funding, metrics_from
from systematic_trading.research import alpha101_tilt_surface_study as study

ROOT = study.DEFAULT_ROOT
INITIAL_CAPITAL = declared_funding(study)      # the study's declared $1,000,000 funding anchor


def load_all(root):
    out = {}
    for job in study.jobs():
        arm, cost, delay, window = job
        payload = read_json(Path(root) / 'python' / (study.job_name(job) + '.json'))
        nav = [dict(date=row['date'], nav=float(row['nav'])) for row in payload['nav']]
        out[study.job_name(job)] = dict(arm=arm, cost=cost, delay=delay, window=window, nav=nav,
                                        **metrics_from(nav, initial_capital=INITIAL_CAPITAL))
    return out


def at(results, arm, cost=study.COST_BPS, delay=study.DELAY, window=study.WINDOW):
    return results[study.job_name((arm, cost, delay, window))]


def realized(root):
    """Declared budget against the budget actually spent, from the tilt diagnostics."""
    diagnostics = read_json(Path(root) / 'decision_diagnostics.json')
    out = {}
    for arm, rows in diagnostics.items():
        plan = study.plan(arm)
        if plan['budget'] is None:
            out[arm] = dict(declared=None, realized=None, applied_share=0.0, scale_mean=None, ranked_mean=0.0)
            continue
        applied = [row for row in rows if row.get('applied')]
        out[arm] = dict(
            declared=plan['budget'],
            realized=plan['budget'] * (sum(row['scale'] for row in applied) / len(applied)) if applied else 0.0,
            applied_share=len(applied) / len(rows),
            scale_mean=sum(row['scale'] for row in applied) / len(applied) if applied else None,
            ranked_mean=sum(row.get('ranked', 0) for row in applied) / len(applied) if applied else 0.0,
            over_cap_days=sum(1 for row in rows if row.get('over_cap_names')))
    return out


def contrasts(results, base):
    """Paired block bootstrap of each tilt arm against its own base control, Holm within the base."""
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    pairs = [(study.tilt_arm(base, budget), base) for budget in study.BUDGETS]
    reference = at(results, base)
    months = sorted(reference['monthly'])
    matrix = np.array([[at(results, a)['monthly'].get(m, 0.0) - at(results, b)['monthly'].get(m, 0.0)
                        for a, b in pairs] for m in months], dtype=float)
    out = {}
    for block in (3, 6, 12):
        rows = paired_bootstrap(matrix, block=block, replications=10_000, seed=study_jobs_seed())
        out[str(block)] = [dict(pair=f'{a}-{b}', budget=study.plan(a)['budget'], **row)
                           for (a, b), row in zip(pairs, rows, strict=True)]
    return out


def study_jobs_seed():
    return 2026101107


def summarize(root=ROOT):
    root = Path(root)
    results = load_all(root)
    gate = read_json(root / 'gate.json')
    used = realized(root)
    metrics = {arm: {k: v for k, v in at(results, arm).items() if k not in ('nav', 'monthly', 'daily')}
               for arm in study.arms()}
    boot = {base: contrasts(results, base) for base in study.BASES}
    best = {}
    for base in study.BASES:
        tilt_arms = [study.tilt_arm(base, budget) for budget in study.BUDGETS]
        best[base] = dict(
            by_total_return=max(tilt_arms, key=lambda arm: metrics[arm]['total_return']),
            by_cagr=max(tilt_arms, key=lambda arm: metrics[arm]['cagr']),
            by_sharpe=max(tilt_arms, key=lambda arm: metrics[arm]['sharpe_zero_cash']),
            by_calmar=max(tilt_arms, key=lambda arm: metrics[arm]['calmar']),
            by_max_drawdown=max(tilt_arms, key=lambda arm: metrics[arm]['max_drawdown']))
    payload = dict(version=study.STUDY, protocol=read_json(root / 'protocol.json'), gate=gate,
                   metrics=metrics, realized=used, contrasts=boot, in_sample_best=best,
                   promotion_eligible=False,
                   statement='The surface is measured, not optimised: the best X by any metric is an '
                             'in-sample maximum on an inspected window, and the family-adjusted interval '
                             'decides whether any X is distinguishable from the untouched book.')
    write_json(root / 'statistics.json', {name: {k: v for k, v in row.items() if k not in ('monthly', 'daily')}
                                          for name, row in results.items()})
    write_json(root / 'analysis.json', payload)
    return payload


def report(root=ROOT, output=None):
    root = Path(root)
    payload = read_json(root / 'analysis.json')
    output = Path(output or 'research/alpha101-tilt-surface-2026-10-11')
    output.mkdir(parents=True, exist_ok=True)
    metrics, gate, used = payload['metrics'], payload['gate'], payload['realized']

    rows = []
    for base in study.BASES:
        for arm in (base, *[study.tilt_arm(base, budget) for budget in study.BUDGETS]):
            plan = study.plan(arm)
            x = '—' if plan['budget'] is None else f"{100 * used[arm]['declared']:.0f}%"
            effective = '—' if plan['budget'] is None else f"{100 * used[arm]['realized']:.1f}%"
            applied = '—' if plan['budget'] is None else f"{100 * used[arm]['applied_share']:.0f}%"
            rows.append([base, x, effective, applied,
                         f"{metrics[arm]['total_return']:.1%}", f"{metrics[arm]['cagr']:.2%}",
                         f"{metrics[arm]['sharpe_zero_cash']:.3f}", f"{metrics[arm]['calmar']:.3f}",
                         f"{metrics[arm]['max_drawdown']:.2%}",
                         f"{gate['arms'][arm]['implied']['annual_turnover']:.2f}x",
                         f"{gate['arms'][arm]['incremental_cost_bps']:+.2f}bp"])

    body = ['<section id="verdict"><h2>Verdict</h2>',
            f'<p class="lead">{payload["statement"]}</p>']
    for base in study.BASES:
        best = payload['in_sample_best'][base]
        body.append(f'<p><b>{study.BASES[base]["label"]}.</b> In sample the best total return and CAGR come '
                    f'from <b>{1100 * 0 + int(100 * study.plan(best["by_cagr"])["budget"])}%</b>, the best Sharpe '
                    f'from <b>{int(100 * study.plan(best["by_sharpe"])["budget"])}%</b>, the best Calmar from '
                    f'<b>{int(100 * study.plan(best["by_calmar"])["budget"])}%</b> and the shallowest drawdown '
                    f'from <b>{int(100 * study.plan(best["by_max_drawdown"])["budget"])}%</b>. Those are maxima of '
                    f'a surface searched on one inspected window, not an optimum.</p>')
    body.append('</section>')

    body.append('<section id="surface"><h2>The full surface, every declared budget</h2>')
    body.append(table(['Base', 'Declared X', 'Effective tilt', 'Decisions tilted', 'Total return', 'CAGR',
                       'Sharpe', 'Calmar', 'Max drawdown', 'Implied turnover', 'Incremental cost'], rows))
    body.append('<p>The effective tilt is the declared budget times the mean shrink factor. It falls below the '
                'declared budget as X rises, because a single shrink factor keeps every name inside the 45% cap '
                'and above zero — a six-name book can only move as much as its smallest weight before a name '
                'would go negative. That saturation is the envelope the request asked about.</p></section>')

    for base in study.BASES:
        body.append(f'<section id="contrast-{base.lower()}"><h2>{study.BASES[base]["label"]}: '
                    'contrasts against its own untouched book</h2>')
        contrast_rows = []
        for block in ('3', '6', '12'):
            for row in payload['contrasts'][base][block]:
                contrast_rows.append([f"{100 * row['budget']:.0f}%", f'{block}m',
                                      f"{row['mean_annual']:+.2%}",
                                      f"[{row['ci95'][0]:+.2%}, {row['ci95'][1]:+.2%}]",
                                      f"{row['holm_p']:.3f}"])
        body.append(table(['Declared X', 'Block', 'Mean annual difference', '95% interval',
                           'Holm p (7 contrasts)'], contrast_rows))
        body.append('</section>')

    body.append('<section id="gate"><h2>Cost, measured but not binding</h2>')
    body.append(table(['Arm', 'Implied turnover', 'Implied annual cost', 'Incremental cost', 'Gate verdict'],
                      [[arm, f"{gate['arms'][arm]['implied']['annual_turnover']:.2f}x",
                        f"{gate['arms'][arm]['verdict']['annual_cost_bps']:.1f}bp",
                        f"{gate['arms'][arm]['incremental_cost_bps']:+.2f}bp",
                        gate['arms'][arm]['verdict']['status'].upper()] for arm in study.arms()]))
    body.append(f'<p>The operator asked to search the performance surface irrespective of cost, so every arm was '
                f'replayed; the gate verdict is still recorded for each and the ceiling is '
                f'{gate["ceiling_bps"]:.1f}bp. This is a documented deviation from gate-before-replay and it '
                f'promotes nothing.</p></section>')

    body.append('<section id="method"><h2>Method</h2>'
                '<p>Two base books over the same 70 evaluation decisions, 2021-01-04 to 2026-10-01: FR25 from the '
                'frozen P4.14 Part B root, whose FR25 arm reproduces the published forecasts exactly, and the '
                'current SOTA from the frozen P4.17c root. Both are read, never recomputed — the tilt is the only '
                'thing this study changes. At each monthly decision the names the base book holds are ranked by '
                'the equal-weight mean of all sixteen registered alphas\' rank scores; total overweight equals '
                'total underweight equals X/2 of NAV; and one shrink factor keeps every name inside the 45% cap '
                'and above zero. Arms are replayed from fresh cash at 5/10/20bp with zero and one-session delay '
                'on each base\'s own audited quotes and sessions.</p></section>')

    body.append('<section id="evidence"><h2>Verification</h2>'
                '<p><a href="../../var/research/alpha101-tilt-surface-20261011-v1/protocol.json">Frozen protocol'
                '</a> · <a href="../../var/research/alpha101-tilt-surface-20261011-v1/gate.json">Gate record</a> · '
                '<a href="../../var/research/alpha101-tilt-surface-20261011-v1/analysis.json">Analysis</a> · '
                '<a href="../alpha101-tilt-replay-2026-10-11/index.html">P4.17c</a> · '
                '<a href="../alpha101-tilt-2026-10-11/index.html">P4.17b</a></p>'
                '<ul><li>Every tilted decision is checked against the zero floor and the cap in the same run that '
                'produces it.</li><li>Both base books are re-checked by hash against their frozen roots.</li>'
                '<li>Completed economics are never overwritten.</li></ul></section>')

    body.append('<section id="limits"><h2>Limits</h2><ul>'
                '<li><b>One inspected window.</b> 2021+ has been looked at by P4.13-P4.17; nothing here is '
                'out-of-sample evidence.</li>'
                '<li><b>The best X is in-sample.</b> Reporting it is not choosing it; the family-adjusted column '
                'is the evidence, and the surface is searched, not validated.</li>'
                '<li><b>The tilt is monthly</b> at the base book\'s own decisions.</li>'
                '<li><b>FR25\'s base is its published recipe replayed in the P4.14 Part B study</b>; the SOTA\'s '
                'is the P4.17c replay.</li>'
                '<li><b>No promotion.</b> The 45% cap, the cash reserve, the cost ceiling and the IC margin are '
                'unchanged, and nothing here touches monitoring or allocation.</li>'
                '</ul></section>')

    css = ('*{box-sizing:border-box}body{margin:0;background:#f3f0e8;color:#263c47;'
           'font:16px/1.6 system-ui,sans-serif}main{max-width:1280px;margin:0 auto;padding:40px 24px 72px}'
           'h1{font-size:30px;margin:0 0 6px}h2{font-size:21px;margin:38px 0 10px}p.lead{font-size:17px}'
           'table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13px}'
           'th,td{border-bottom:1px solid #d8d2c4;padding:6px 8px;text-align:right}'
           'th:first-child,td:first-child,th:last-child,td:last-child{text-align:left}'
           'thead th{background:#e8e2d4}a{color:#1d6b8a}')
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>P4.17d tilt budget surface</title><style>' + css + '</style></head><body><main>'
            '<h1>P4.17d — the Alpha101 tilt budget surface on FR25 and the SOTA</h1>'
            '<p>How far can the tilt be pushed? The declared budget runs to 150% of NAV, every arm is replayed, '
            'and the cost is measured but not binding.</p>' + ''.join(body) + '</main></body></html>')
    (output / 'index.html').write_text(html, encoding='utf-8')
    write_json(root / 'presentation_receipt.json', dict(
        analysis_sha256=sha256(root / 'analysis.json'),
        files={path.relative_to(output).as_posix(): sha256(path) for path in output.rglob('*') if path.is_file()}))
    return dict(output=str(output), bases=len(study.BASES), arms=len(study.arms()))
