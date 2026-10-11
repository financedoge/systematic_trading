"""Presentation for the P4.17b tilt measurement."""
from pathlib import Path

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research.sleeve_construction_analysis import table
from systematic_trading.research import alpha101_tilt as tilt

ROOT = tilt.DEFAULT_ROOT


def _grid_rows(payload):
    rows = []
    for row in payload['rows']:
        gate = row['gate']
        books = row['books']
        rows.append([
            row['alpha'], f"{100 * row['budget']:.0f}%",
            f"{row['turnover']['incremental_annual']:.2f}x",
            f"{gate['annual_cost_bps']:.2f}bp",
            f"{gate.get('breakeven_ic', 0.0):.5f}",
            'n/a' if row['observed_ic'] is None else f"{row['observed_ic']:+.4f}",
            'n/a' if gate.get('ic_margin') is None else f"{gate['ic_margin']:,.0f}x",
            gate['status'].upper(),
            'n/a' if books['cap_binding_share'] is None else f"{100 * books['cap_binding_share']:.0f}% / {books['scale_mean']:.3f}",
        ])
    return sorted(rows, key=lambda row: (row[1], row[7] != 'PASS', row[0]))


def _summary_rows(payload):
    rows = []
    for budget in sorted({row['budget'] for row in payload['rows']}):
        subset = [row for row in payload['rows'] if row['budget'] == budget]
        passing = [row for row in subset if row['gate']['status'] == 'pass']
        costs = [row['gate']['annual_cost_bps'] for row in subset]
        headroom = payload['calibration']['headroom_bps']
        rows.append([
            f"{100 * budget:.0f}%",
            f"{len(passing)} of {len(subset)}",
            f"{min(row['turnover']['incremental_annual'] for row in subset):.2f}x"
            f" – {max(row['turnover']['incremental_annual'] for row in subset):.2f}x",
            f"{min(costs):.2f}bp – {max(costs):.2f}bp",
            f"{100 * max(costs) / headroom:.0f}% of the worst candidate's headroom used",
            f"{100 * sum(row['books']['cap_binding_share'] or 0 for row in subset) / len(subset):.0f}%",
        ])
    return rows


def report(root=ROOT, output=None):
    root = Path(root)
    payload = read_json(root / 'tilt.json')
    output = Path(output or 'research/alpha101-tilt-2026-10-11')
    output.mkdir(parents=True, exist_ok=True)
    calibration = payload['calibration']
    headroom = calibration['headroom_bps']
    counts = {}
    for budget in sorted({row['budget'] for row in payload['rows']}):
        subset = [row for row in payload['rows'] if row['budget'] == budget]
        counts[budget] = sum(1 for row in subset if row['gate']['status'] == 'pass')

    body = ['<section id="verdict"><h2>Verdict</h2>',
            f'<p class="lead">Tilting the existing book works where choosing it did not. At a '
            f'<strong>5% budget, {counts[0.05]} alphas clear the P4.15 '
            f'gate</strong>, for an incremental cost of <strong>0.00–0.48bp</strong> against the '
            f'<strong>{headroom:.2f}bp</strong> of headroom the monitored book leaves. The breakeven IC falls '
            f'from 0.006–0.012 for the rejected top-six mappings to <strong>0.00000–0.00008</strong>, so the '
            f'IC bar the operator expected to be low is low — as a consequence of the cheaper mapping, not of '
            f'a relaxed gate. At a 20% budget cost becomes binding again and only {counts[0.20]} of 16 clear, '
            f'so the cost/alpha balance sits at <strong>5–10%</strong>. No economics were produced: nothing is '
            f'replayed until a candidate clears, and this is a measurement, not a promotion.</p></section>']

    body.append('<section id="summary"><h2>The cost/alpha balance by budget</h2>')
    body.append(table(['Budget X', 'Alphas passing', 'Incremental turnover', 'Incremental cost',
                       'Cost against headroom', 'Decisions with the cap binding'], _summary_rows(payload)))
    body.append('<p>The headroom is the published ceiling of 44.0bp minus the monitored book\'s own measured '
                f'drag of {calibration["monitored_drag_bps"]:.2f}bp, i.e. {headroom:.2f}bp. The tilt is '
                'NAV-neutral, so gross exposure and cash are unchanged and the only new cost is the tilt\'s own '
                'trading.</p></section>')

    body.append('<section id="grid"><h2>The full grid, every declared candidate</h2>')
    body.append(table(['Alpha', 'X', 'Incremental turnover', 'Incremental cost', 'Breakeven IC',
                       'Observed IC (21)', 'IC margin', 'Verdict', 'Cap binding / mean scale'],
                      _grid_rows(payload)))
    body.append('<p>Every one of the sixteen registered alphas is reported at every budget; nothing is dropped '
                'after the fact and X is never chosen from the outcome. The three rejected alphas carry '
                '<em>negative</em> information — alpha 101 most clearly, at −0.0749 with an interval excluding '
                'zero — so a long tilt of them points the wrong way, which is why they fail the IC test rather '
                'than the cost test.</p></section>')

    body.append('<section id="method"><h2>Method</h2>'
                '<p>The base book is the pinned capped pooled control\'s own decisions: real membership, real '
                'weights, unchanged. The held names carrying an alpha value are ranked; each gets a linear rank '
                'score in [−1, +1] with zero mean; total overweight equals total underweight equals X/2 of NAV; '
                'and one per-decision shrink factor scales the whole tilt so no name breaches the 45% cap or '
                'goes negative. The incremental traded notional is the difference between the tilted and '
                'untilted books on the gate\'s own implied-turnover measure; the breakeven IC is taken at that '
                'incremental turnover at the published dispersion; and the observed IC is the frozen P4.17 '
                'screen\'s 21-session rank IC, so the information measurement is not re-fitted here. The gate\'s '
                'frozen 3× margin is applied unchanged.</p></section>')

    body.append('<section id="evidence"><h2>Verification</h2>'
                '<p><a href="../../var/research/alpha101-tilt-20261011-v1/protocol.json">Frozen protocol</a> · '
                '<a href="../../var/research/alpha101-tilt-20261011-v1/tilt.json">Tilt artifact</a> · '
                '<a href="../../var/research/alpha101-tilt-20261011-v1/input_manifest.json">Input manifest</a> · '
                '<a href="../alpha101-screen-2026-10-11/index.html">P4.17 screen</a> · '
                '<a href="../turnover-gate-2026-10-10/index.html">P4.15 gate</a></p>'
                '<ul><li>The measurement re-runs to an identical artifact.</li>'
                '<li>The pinned control decisions, the frozen P4.17 screen and the published P4.15 calibration '
                'are re-checked by hash.</li>'
                '<li>The monitored drag is asserted against the published 40.4bp, so a wrong arm or artifact '
                'stops the study rather than silently changing the headroom.</li></ul></section>')

    body.append('<section id="limits"><h2>Limits</h2><ul>'
                '<li>The observed ICs come from the same inspected window as the P4.17 screen; they are not '
                'out-of-sample evidence.</li>'
                '<li>A passing tilt is a <em>candidate</em>: it still needs a replay against the matched untilted '
                'book, family adjustment across the grid, and decay monitoring before any promotion.</li>'
                '<li>The tilt interacts with the existing overlays (model tilt, relative momentum, USD ridge, '
                'activity concentration, the final cap) only through the weights it receives; that interaction '
                'is a replay question, not a measurement one.</li>'
                '<li>Re-tilting happens at the existing monthly decision only; a daily tilt would cost multiples '
                'of this and is not measured here.</li>'
                '<li>Nothing here changes membership, the 45% cap, the cash reserve or the monitored book.</li>'
                '</ul></section>')

    css = ('*{box-sizing:border-box}body{margin:0;background:#f3f0e8;color:#263c47;'
           'font:16px/1.6 system-ui,sans-serif}main{max-width:1240px;margin:0 auto;padding:40px 24px 72px}'
           'h1{font-size:30px;margin:0 0 6px}h2{font-size:21px;margin:38px 0 10px}p.lead{font-size:17px}'
           'table{border-collapse:collapse;width:100%;margin:12px 0;font-size:13.5px}'
           'th,td{border-bottom:1px solid #d8d2c4;padding:6px 8px;text-align:right}'
           'th:first-child,td:first-child,th:last-child,td:last-child{text-align:left}'
           'thead th{background:#e8e2d4}code{background:#e8e2d4;padding:1px 4px;border-radius:3px}a{color:#1d6b8a}')
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>P4.17b Alpha101 tactical tilt</title><style>' + css + '</style></head><body><main>'
            '<h1>P4.17b — Alpha101 as a tactical tilt on the existing book</h1>'
            '<p>Overweight and underweight the holdings we already have, set aside X% to do it, and measure the '
            'cost/alpha balance before any replay.</p>' + ''.join(body) + '</main></body></html>')
    (output / 'index.html').write_text(html, encoding='utf-8')
    write_json(root / 'presentation_receipt.json', dict(
        tilt_sha256=sha256(root / 'tilt.json'),
        files={path.relative_to(output).as_posix(): sha256(path) for path in output.rglob('*') if path.is_file()},
        sources={'src/systematic_trading/research/alpha101_tilt_analysis.py':
                 sha256(Path('src/systematic_trading/research/alpha101_tilt_analysis.py'))}))
    return dict(output=str(output), passing={f'X={100 * budget:.0f}%': count
                                             for budget, count in counts.items()})


if __name__ == '__main__':
    import sys
    print(report(ROOT, sys.argv[1] if len(sys.argv) > 1 else None))
