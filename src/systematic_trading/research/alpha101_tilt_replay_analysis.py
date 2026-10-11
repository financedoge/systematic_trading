"""Analysis and presentation for the P4.17c tilt replay."""
from datetime import date
from pathlib import Path
from statistics import stdev

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research.sleeve_construction_analysis import table
from systematic_trading.research import alpha101_tilt_study as study

ROOT = study.DEFAULT_ROOT
COMPARISONS = (('SOTA-TILT-53', 'SOTA'), ('SOTA-TILT-FAMILY', 'SOTA'), ('SOTA-TILT-53', 'SOTA-TILT-FAMILY'))
PRIMARY = ('SOTA-TILT-53', 'SOTA')
HEADLINE = dict(cost=5, delay=0, window='evaluation')


def load_replay(root, job):
    payload = read_json(Path(root) / 'python' / (study.job_name(job) + '.json'))
    nav = [dict(date=row['date'], nav=float(row['nav'])) for row in payload['nav']]
    return dict(nav=nav, decisions=len(payload['decisions']), fills=len(payload['fills']))


def declared_funding(module=None):
    """The engine's declared funding anchor, read from the study's own protocol.

    Every tilt study declares ``initial_cash_usd`` in ``protocol()``; reading it here keeps the
    analysis tied to the declaration instead of to a number copied into the analysis module.
    """
    return float((study if module is None else module).protocol()['initial_cash_usd'])


INITIAL_CAPITAL = declared_funding()          # the P4.17c study's own $1,000,000 declaration


def metrics_from(nav, initial_capital=INITIAL_CAPITAL):
    """Metrics for a funded account, from the funding anchor through the last end-of-day NAV.

    A replay's ``nav`` series holds end-of-day values only, so its first session's return and
    drawdown are invisible unless the funding that preceded them is included: the account is funded
    at ``initial_capital`` and ``nav[0]`` is the first end-of-day mark. The return series therefore
    runs funding -> nav[0] -> ... -> nav[-1], the drawdown peak starts at the funding amount, and
    the first funded session counts in the daily, monthly, volatility, Sharpe and total-return
    numbers. Callers must pass the study's declared funding explicitly; ``initial_capital=None``
    raises rather than silently falling back to the first NAV.
    """
    if not nav:
        raise ValueError('metrics_from needs at least one end-of-day NAV')
    if initial_capital is None:
        raise ValueError('metrics_from needs the funding anchor, not None')
    funding = float(initial_capital)
    if not funding > 0:
        raise ValueError('Funding must be positive: ' + str(initial_capital))
    dates = [row['date'] for row in nav]
    values = np.array([funding, *(float(row['nav']) for row in nav)], dtype=float)
    daily = values[1:] / values[:-1] - 1.0
    sessions = len(values) - 1
    # Funding lands at the start of the first recorded session, so the first NAV date is the funding
    # date for the annualisation.
    years = (date.fromisoformat(dates[-1]) - date.fromisoformat(dates[0])).days / 365.25
    total = values[-1] / funding - 1.0
    cagr = (values[-1] / funding) ** (1.0 / years) - 1.0 if years > 0 else None
    volatility = float(stdev(daily)) * np.sqrt(252) if sessions > 1 else None
    sharpe = float(np.mean(daily)) / float(stdev(daily)) * np.sqrt(252) if sessions > 1 and stdev(daily) else None
    peak, drawdown = funding, 0.0
    for value in values:
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1.0)
    calmar = float(cagr) / abs(drawdown) if cagr is not None and drawdown else None
    monthly = {}
    for index in range(len(nav)):
        key = dates[index][:7]
        monthly.setdefault(key, []).append(daily[index])
    monthly_returns = {key: float(np.prod([1.0 + r for r in rows]) - 1.0) for key, rows in monthly.items()}
    return dict(total_return=float(total), cagr=float(cagr) if cagr is not None else None,
                sharpe_zero_cash=None if sharpe is None else float(sharpe),
                volatility=None if volatility is None else float(volatility),
                max_drawdown=float(drawdown), calmar=calmar,
                final_nav=float(values[-1]), initial_capital=funding, sessions=sessions, years=years,
                monthly=monthly_returns, daily=list(daily))


def load_all(root):
    out = {}
    for job in study.jobs():
        arm, cost, delay, window = job
        replay = load_replay(root, job)
        out[study.job_name(job)] = dict(arm=arm, cost=cost, delay=delay, window=window, **replay,
                                        **metrics_from(replay['nav'], initial_capital=INITIAL_CAPITAL))
    return out


def at(results, arm, cost=HEADLINE['cost'], delay=HEADLINE['delay'], window=HEADLINE['window']):
    return results[study.job_name((arm, cost, delay, window))]


def uncertainty(results, blocks=study.BOOTSTRAP_BLOCKS):
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    reference = at(results, study.ARMS[0])
    months = sorted(reference['monthly'])
    matrix = np.array([[at(results, a)['monthly'].get(m, 0.0) - at(results, b)['monthly'].get(m, 0.0)
                        for a, b in COMPARISONS] for m in months], dtype=float)
    out = {}
    for block in blocks:
        rows = paired_bootstrap(matrix, block=block, replications=study.BOOTSTRAP_REPLICATIONS, seed=study.SEED)
        out[str(block)] = [dict(comparison=f'{a}-{b}', **row) for (a, b), row in zip(COMPARISONS, rows, strict=True)]
    return out


def contrast(boot, pair, block=6):
    return next(row for row in boot[str(block)] if row['comparison'] == f'{pair[0]}-{pair[1]}')


def summarize(root, output=None):
    """Write statistics.json and analysis.json: the arms, their contrasts and the verdict."""
    root = Path(root)
    results = load_all(root)
    boot = uncertainty(results)
    gate = read_json(root / 'gate.json')
    metrics = {arm: {k: v for k, v in at(results, arm).items()
                     if k not in ('nav', 'monthly', 'daily')} for arm in study.ARMS}
    primary = contrast(boot, PRIMARY)
    secondary = contrast(boot, ('SOTA-TILT-FAMILY', 'SOTA'))
    candidate = metrics[PRIMARY[0]]['sharpe_zero_cash'] > metrics[PRIMARY[1]]['sharpe_zero_cash']
    supported = bool(candidate and primary['holm_p'] < 0.05 and primary['mean_annual'] > 0)
    statement = (
        f'{PRIMARY[0]} changes the annualised return by {primary["mean_annual"]:+.2%} against the untouched '
        f'SOTA with Holm p = {primary["holm_p"]:.3f} over {len(COMPARISONS)} contrasts'
        + ('; the family-adjusted interval excludes zero' if primary['holm_p'] < 0.05
           else '; the family-adjusted interval spans zero, so the difference is not established'))
    payload = dict(version=study.STUDY, protocol=read_json(root / 'protocol.json'), gate=gate, metrics=metrics,
                   contrasts={block: rows for block, rows in boot.items()},
                   primary_contrast=primary, secondary_contrast=secondary,
                   verdict=dict(status='supported' if supported else 'inconclusive', statement=statement,
                                family=len(COMPARISONS), block=6),
                   headline=HEADLINE, promotion_eligible=False)
    write_json(root / 'statistics.json', {name: {k: v for k, v in row.items() if k not in ('monthly', 'daily')}
                                          for name, row in results.items()})
    write_json(root / 'analysis.json', payload)
    return payload


def report(root=ROOT, output=None):
    root = Path(root)
    payload = read_json(root / 'analysis.json')
    output = Path(output or 'research/alpha101-tilt-replay-2026-10-11')
    output.mkdir(parents=True, exist_ok=True)
    metrics, gate = payload['metrics'], payload['gate']
    arms = list(study.ARMS)
    headline = payload['headline']

    rows = [[study.LABELS[arm], f"{metrics[arm]['total_return']:.1%}", f"{metrics[arm]['cagr']:.2%}",
             f"{metrics[arm]['sharpe_zero_cash']:.3f}", f"{metrics[arm]['calmar']:.3f}",
             f"{metrics[arm]['max_drawdown']:.2%}", f"{metrics[arm]['volatility']:.2%}",
             f"{gate['arms'][arm]['implied']['annual_turnover']:.2f}x",
             f"{gate['arms'][arm]['incremental_cost_bps']:+.2f}bp"] for arm in arms]

    body = ['<section id="verdict"><h2>Verdict</h2>']
    body.append(f'<p class="lead">{payload["verdict"]["statement"]}.</p>')
    body.append('<p>Every figure below is the completed replay of the untouched SOTA and of the same SOTA with a '
                f'10% Alpha101 tilt appended last in its overlay chain, at {headline["cost"]}bp cost, zero delay '
                f'and the {headline["window"]} window, from fresh cash.</p></section>')

    body.append('<section id="headline"><h2>The four numbers the request asked for</h2>')
    body.append(table(['Arm', 'Total return', 'CAGR', 'Sharpe', 'Calmar', 'Max drawdown', 'Volatility',
                       'Implied turnover', 'Incremental cost'], rows))
    body.append('</section>')

    body.append('<section id="contrasts"><h2>Family-adjusted contrasts against the untouched SOTA</h2>')
    contrast_rows = []
    for pair in COMPARISONS:
        for block in study.BOOTSTRAP_BLOCKS:
            row = contrast({str(block): payload['contrasts'][str(block)]}, pair, block)
            bonus = f"Holm p = {row['holm_p']:.3f}"
            contrast_rows.append([f'{pair[0]} − {pair[1]}', f'{block}m', f"{row['mean_annual']:+.2%}",
                                  f"[{row['ci95'][0]:+.2%}, {row['ci95'][1]:+.2%}]", bonus])
    body.append(table(['Contrast', 'Block', 'Mean annual difference', '95% interval', 'Family-adjusted'],
                      contrast_rows))
    body.append('<p>Three contrasts are registered, so the Holm adjustment is applied across them at each block '
                'length. A raw interval is not evidence on its own; the family-adjusted column is the one that '
                'decides.</p></section>')

    body.append('<section id="gate"><h2>The gate ran first</h2>')
    body.append(table(['Arm', 'Implied turnover', 'Implied annual cost', 'Incremental cost vs SOTA',
                       'Breakeven IC', 'IC margin', 'Gate verdict'],
                      [[study.LABELS[arm], f"{gate['arms'][arm]['implied']['annual_turnover']:.2f}x",
                        f"{gate['arms'][arm]['verdict']['annual_cost_bps']:.1f}bp",
                        f"{gate['arms'][arm]['incremental_cost_bps']:+.2f}bp",
                        f"{gate['arms'][arm]['verdict']['breakeven_ic']:.4f}",
                        f"{gate['arms'][arm]['verdict']['ic_margin']:.2f}x",
                        gate['arms'][arm]['verdict']['status'].upper()] for arm in arms]))
    body.append(f'<p>Ceiling {gate["ceiling_bps"]:.1f}bp; the monitored book\'s own drag is '
                f'{gate["monitored_drag_bps"]:.2f}bp, so only the incremental cost is new. The gate prices each '
                'arm\'s own mapping at the frozen 5bp with the published thresholds.</p></section>')

    body.append('<section id="method"><h2>Method</h2>'
                '<p>The base strategy is the registered SOTA, built from its own definition and overlay chain '
                '(asset pool filter, rolling model, relative momentum, adaptive trend, audited activity, USD '
                'ridge) with a 63-session lookback, a 45% base cap and the 2% cash reserve. The tilt is appended '
                '<em>last</em>: it ranks only the names the SOTA already holds, moves total overweight equal to '
                'total underweight equal to 5% of NAV, and shrinks as a whole if any name would breach 45% or go '
                'negative. Because it is appended last it also has to satisfy the defensive fallback\'s protected '
                'cash budget — same symbol set, no additions or removals, gross unchanged — and the study raises '
                'if that contract is ever broken. Decisions are frozen per arm, then replayed from fresh cash '
                'over the parent study\'s own quotes and sessions at 5/10/20bp with zero and one-session delay. '
                'SOTA-TILT-53 uses the alpha with the strongest measured information, which was chosen after '
                'inspecting the P4.17 screen, so its number is not an unbiased estimate; SOTA-TILT-FAMILY tilts '
                'on the equal-weight mean of all sixteen alphas\' rank scores and selects nothing.</p></section>')

    body.append('<section id="evidence"><h2>Verification</h2>'
                '<p><a href="../../var/research/alpha101-tilt-replay-20261011-v1/protocol.json">Frozen protocol</a> '
                '· <a href="../../var/research/alpha101-tilt-replay-20261011-v1/gate.json">Gate record</a> · '
                '<a href="../../var/research/alpha101-tilt-replay-20261011-v1/analysis.json">Analysis</a> · '
                '<a href="../../var/research/alpha101-tilt-replay-20261011-v1/decisions/">Frozen decisions</a> · '
                '<a href="../alpha101-tilt-2026-10-11/index.html">P4.17b measurement</a> · '
                '<a href="../sleeve-construction-2026-10-10/index.html">P4.16</a></p>'
                '<ul><li>Every arm\'s decisions pass the cap, long-only, universe and protected-budget contracts '
                'in the same run that produces them.</li>'
                '<li>The gate is applied to each arm before any replay, and completed economics are never '
                'overwritten.</li>'
                '<li>The pinned parent inputs are re-checked by hash.</li></ul></section>')

    body.append('<section id="limits"><h2>Limits</h2><ul>'
                '<li><b>One window, already inspected.</b> The 2021+ window has been looked at by P4.13-P4.17, so '
                'this is not out-of-sample evidence.</li>'
                '<li><b>The single-alpha arm is selected on the screen.</b> Alpha 53 had the strongest measured '
                'information; only the family arm avoids that selection, and the family arm dilutes by averaging '
                'in three negative-information alphas and one degenerate.</li>'
                '<li><b>X is the operator\'s declared 10%</b>, not a tuned value; the P4.17b measurement covered '
                '5%, 10% and 20%.</li>'
                '<li><b>Monthly re-tilting only</b>, at the SOTA\'s own decision dates.</li>'
                '<li><b>A tilt is not a promotion.</b> Nothing here changes monitoring, allocation, the 45% cap, '
                'the cash reserve or execution authority.</li>'
                '</ul></section>')

    css = ('*{box-sizing:border-box}body{margin:0;background:#f3f0e8;color:#263c47;'
           'font:16px/1.6 system-ui,sans-serif}main{max-width:1200px;margin:0 auto;padding:40px 24px 72px}'
           'h1{font-size:30px;margin:0 0 6px}h2{font-size:21px;margin:38px 0 10px}p.lead{font-size:17px}'
           'table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13.5px}'
           'th,td{border-bottom:1px solid #d8d2c4;padding:6px 8px;text-align:right}'
           'th:first-child,td:first-child,th:last-child,td:last-child{text-align:left}'
           'thead th{background:#e8e2d4}a{color:#1d6b8a}')
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>P4.17c Alpha101 tilt replayed on the SOTA</title><style>' + css + '</style></head><body><main>'
            '<h1>P4.17c — baking the Alpha101 tilt into the current SOTA</h1>'
            '<p>A 10% NAV-neutral tilt of the tested alpha, and of the whole registered family, appended last in '
            'the SOTA\'s own overlay chain, replayed against the untouched strategy.</p>'
            + ''.join(body) + '</main></body></html>')
    (output / 'index.html').write_text(html, encoding='utf-8')
    write_json(root / 'presentation_receipt.json', dict(
        analysis_sha256=sha256(root / 'analysis.json'),
        files={path.relative_to(output).as_posix(): sha256(path) for path in output.rglob('*') if path.is_file()},
        sources={'src/systematic_trading/research/alpha101_tilt_replay_analysis.py':
                 sha256(Path('src/systematic_trading/research/alpha101_tilt_replay_analysis.py'))}))
    return dict(output=str(output), status=payload['verdict']['status'],
                primary=f"{payload['primary_contrast']['mean_annual']:+.4f}")


if __name__ == '__main__':
    import sys
    root = sys.argv[1] if len(sys.argv) > 1 else ROOT
    print(report(root, sys.argv[2] if len(sys.argv) > 2 else None))
