"""Analysis and presentation for the P4.17e daily, threshold-triggered tilt."""
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research.sleeve_construction_analysis import table
from systematic_trading.research.alpha101_tilt_replay_analysis import declared_funding, metrics_from
from systematic_trading.research import alpha101_tilt_daily_study as study

ROOT = study.DEFAULT_ROOT
INITIAL_CAPITAL = declared_funding(study)      # the study's declared $1,000,000 funding anchor
SEED = 2026101108


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


def contrasts(results, base):
    """Each arm against its own untouched base, Holm-adjusted within the base's registered family."""
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    tilt_arms = [arm for arm in study.arms() if study.plan(arm)['base'] == base and arm != base]
    pairs = [(arm, base) for arm in tilt_arms]
    months = sorted(at(results, base)['monthly'])
    matrix = np.array([[at(results, a)['monthly'].get(m, 0.0) - at(results, b)['monthly'].get(m, 0.0)
                        for a, b in pairs] for m in months], dtype=float)
    out = {}
    for block in (3, 6, 12):
        rows = paired_bootstrap(matrix, block=block, replications=10_000, seed=SEED)
        out[str(block)] = [dict(pair=f'{a}-{b}', **study.plan(a), **row)
                           for (a, b), row in zip(pairs, rows, strict=True)]
    return out


def summarize(root=ROOT):
    root = Path(root)
    results = load_all(root)
    gate = read_json(root / 'gate.json')
    diagnostics = read_json(root / 'decision_diagnostics.json')
    metrics = {arm: {k: v for k, v in at(results, arm).items() if k not in ('nav', 'monthly', 'daily')}
               for arm in study.arms()}
    boot = {base: contrasts(results, base) for base in study.BASES}
    passing = {base: [arm for arm in study.arms()
                      if study.plan(arm)['base'] == base and gate['arms'][arm]['verdict']['status'] == 'pass']
               for base in study.BASES}
    best = {}
    for base in study.BASES:
        tilt_arms = [arm for arm in study.arms() if study.plan(arm)['base'] == base and arm != base]
        best[base] = dict(cagr=max(tilt_arms, key=lambda arm: metrics[arm]['cagr']),
                          sharpe=max(tilt_arms, key=lambda arm: metrics[arm]['sharpe_zero_cash']),
                          calmar=max(tilt_arms, key=lambda arm: metrics[arm]['calmar']),
                          max_drawdown=max(tilt_arms, key=lambda arm: metrics[arm]['max_drawdown']))
    payload = dict(
        version=study.STUDY, protocol=read_json(root / 'protocol.json'), gate=gate, metrics=metrics,
        diagnostics=diagnostics, contrasts=boot, gate_passing=passing, in_sample_best=best,
        promotion_eligible=False,
        statement='Daily threshold-triggered tilting is measured as a frequency/cost frontier: the '
                  'threshold buys back cost by trading less, and the best arm by any metric remains an '
                  'in-sample maximum on an inspected window.')
    write_json(root / 'statistics.json', {name: {k: v for k, v in row.items() if k not in ('monthly', 'daily')}
                                          for name, row in results.items()})
    write_json(root / 'analysis.json', payload)
    return payload


def report(root=ROOT, output=None):
    root = Path(root)
    payload = read_json(root / 'analysis.json')
    output = Path(output or 'research/alpha101-tilt-daily-2026-10-11')
    output.mkdir(parents=True, exist_ok=True)
    metrics, gate, diag = payload['metrics'], payload['gate'], payload['diagnostics']

    rows = []
    for base in study.BASES:
        for arm in [arm for arm in study.arms() if study.plan(arm)['base'] == base]:
            plan = study.plan(arm)
            stats = diag[arm]
            x = '—' if plan['budget'] is None else f"{100 * plan['budget']:.0f}%"
            theta = ('—' if plan['threshold'] is None else
                     ('daily' if plan['threshold'] == 0 else f"{100 * plan['threshold']:.0f}%"))
            if plan['mode'] == 'monthly':
                theta = 'monthly'
            trades = stats['trades']
            per_year = trades / (metrics[arm]['years'] or 1)
            rows.append([base, x, theta, f'{trades:,}', f'{per_year:.1f}',
                         f"{metrics[arm]['total_return']:.1%}", f"{metrics[arm]['cagr']:.2%}",
                         f"{metrics[arm]['sharpe_zero_cash']:.3f}", f"{metrics[arm]['calmar']:.3f}",
                         f"{metrics[arm]['max_drawdown']:.2%}",
                         f"{gate['arms'][arm]['implied']['annual_turnover']:.2f}x",
                         f"{gate['arms'][arm]['verdict']['annual_cost_bps']:.1f}bp",
                         gate['arms'][arm]['verdict']['status'].upper()])

    body = ['<section id="verdict"><h2>Verdict</h2>', f'<p class="lead">{payload["statement"]}</p>']
    for base in study.BASES:
        passing = payload['gate_passing'][base]
        best = payload['in_sample_best'][base]
        body.append(
            f'<p><b>{study.BASES[base]["label"]}.</b> {len(passing)} of its tilt arms clear the 44.0bp '
            f'ceiling. In sample the best CAGR comes from <b>{study.plan(best["cagr"])["label"].split("+")[-1].strip()}</b>, '
            f'the best Sharpe from <b>{study.plan(best["sharpe"])["label"].split("+")[-1].strip()}</b>, the best '
            f'Calmar from <b>{study.plan(best["calmar"])["label"].split("+")[-1].strip()}</b> and the shallowest '
            f'drawdown from <b>{study.plan(best["max_drawdown"])["label"].split("+")[-1].strip()}</b>. Those are '
            f'maxima of a searched surface, not an optimum.</p>')
    body.append('</section>')

    body.append('<section id="frontier"><h2>The frequency / cost frontier</h2>')
    body.append(table(['Base', 'X', 'Threshold', 'Re-tilts', 'Per year', 'Total return', 'CAGR', 'Sharpe',
                       'Calmar', 'Max drawdown', 'Implied turnover', 'Annual cost', 'Gate'], rows))
    body.append('<p>Threshold "daily" re-tilts every session, "50%" waits until half the budget has moved '
                'and "100%" until a whole budget has moved; a strategy rebalance always re-derives the tilt. '
                'The monthly row is the P4.17d arm, carried in as the frequency reference. Cost is what the '
                'threshold buys back.</p></section>')

    for base in study.BASES:
        body.append(f'<section id="contrast-{base.lower()}"><h2>{study.BASES[base]["label"]}: contrasts '
                    'against its own untouched book</h2>')
        rows = []
        for block in ('6', '12'):
            for row in payload['contrasts'][base][block]:
                if row['mode'] == 'monthly':
                    label = f"{100 * row['budget']:.0f}% / monthly"
                elif row['threshold'] == 0:
                    label = f"{100 * row['budget']:.0f}% / daily"
                else:
                    label = f"{100 * row['budget']:.0f}% / threshold {100 * row['threshold']:.0f}%"
                rows.append([label, f'{block}m', f"{row['mean_annual']:+.2%}",
                             f"[{row['ci95'][0]:+.2%}, {row['ci95'][1]:+.2%}]", f"{row['holm_p']:.3f}"])
        body.append(table(['X / threshold', 'Block', 'Mean annual difference', '95% interval', 'Holm p'], rows))
        body.append('</section>')

    body.append('<section id="method"><h2>Method</h2>'
                '<p>Every session, the names the base book holds are ranked by the equal-weight mean of all '
                'sixteen registered alphas\' rank scores, computed from audited bars strictly before that '
                'session. The desired tilt is NAV-neutral — total overweight equals total underweight equals '
                'X/2 of NAV — and one shrink factor keeps every name inside the 45% cap and above zero. The arm '
                're-tilts when the L1 distance between the desired and the currently held tilt reaches '
                'threshold x X, and always on a strategy rebalance date. Decisions are frozen per arm and '
                'replayed from fresh cash at 5/10/20bp with zero and one-session delay.</p></section>')

    body.append('<section id="evidence"><h2>Verification</h2>'
                '<p><a href="../../var/research/alpha101-tilt-daily-20261011-v1/protocol.json">Frozen protocol</a>'
                ' · <a href="../../var/research/alpha101-tilt-daily-20261011-v1/gate.json">Gate record</a> · '
                '<a href="../../var/research/alpha101-tilt-daily-20261011-v1/analysis.json">Analysis</a> · '
                '<a href="../alpha101-tilt-surface-2026-10-11/index.html">P4.17d surface</a> · '
                '<a href="../alpha101-tilt-replay-2026-10-11/index.html">P4.17c</a></p>'
                '<ul><li>Every daily row is checked against the zero floor and the 45% cap in the run that '
                'produces it.</li><li>Both base books are re-checked by hash against their frozen roots.</li>'
                '<li>Completed economics are never overwritten.</li></ul></section>')

    body.append('<section id="limits"><h2>Limits</h2><ul>'
                '<li><b>One inspected window</b>, 2021-01-04 to 2026-10-01; nothing here is out-of-sample.</li>'
                '<li><b>The best arm is in-sample.</b> Reporting the maximum is not choosing it.</li>'
                '<li><b>The book is held between strategy decisions</b>, so the daily flow is the tilt; a book '
                'that also rebalanced daily would trade more.</li>'
                '<li><b>Costs are the parents\' 5/10/20bp</b> with zero and one-session delay.</li>'
                '<li><b>No promotion</b>: the cap, the cash reserve, the ceiling and the IC margin are '
                'unchanged.</li>'
                '</ul></section>')

    css = ('*{box-sizing:border-box}body{margin:0;background:#f3f0e8;color:#263c47;'
           'font:16px/1.6 system-ui,sans-serif}main{max-width:1320px;margin:0 auto;padding:40px 24px 72px}'
           'h1{font-size:30px;margin:0 0 6px}h2{font-size:21px;margin:38px 0 10px}p.lead{font-size:17px}'
           'table{border-collapse:collapse;width:100%;margin:12px 0;font-size:12.5px}'
           'th,td{border-bottom:1px solid #d8d2c4;padding:5px 7px;text-align:right}'
           'th:first-child,td:first-child,th:last-child,td:last-child{text-align:left}'
           'thead th{background:#e8e2d4}a{color:#1d6b8a}')
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>P4.17e daily threshold-triggered tilt</title><style>' + css + '</style></head><body><main>'
            '<h1>P4.17e — the daily, threshold-triggered Alpha101 tilt</h1>'
            '<p>Monitor every session, re-tilt X% when the signal moves far enough, and use the threshold to '
            'decide how much frequency the cost ceiling can carry.</p>' + ''.join(body) + '</main></body></html>')
    (output / 'index.html').write_text(html, encoding='utf-8')
    write_json(root / 'presentation_receipt.json', dict(
        analysis_sha256=sha256(root / 'analysis.json'),
        files={path.relative_to(output).as_posix(): sha256(path) for path in output.rglob('*') if path.is_file()}))
    return dict(output=str(output), bases=len(study.BASES), arms=len(study.arms()),
                gate_passing={base: len(payload['gate_passing'][base]) for base in study.BASES})
