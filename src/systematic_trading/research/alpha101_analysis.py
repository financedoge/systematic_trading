"""Presentation for the P4.17 alpha screen: the published family table and its reasoning."""
from pathlib import Path

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research.sleeve_construction_analysis import table
from systematic_trading.research import alpha101_screen as screening

ROOT = screening.DEFAULT_ROOT
UNIT_QUIRK = {'7': 'adv20 < volume compares dollar volume to share volume; collapses to its '
                   'constant -1 branch on this data',
              '21': 'volume / adv20 compares share volume to dollar volume',
              '43': 'ts_rank(volume / adv20, 20) compares share volume to dollar volume'}
HORIZON_LABELS = {1: '1 session', 5: '5', 10: '10', 21: '21', 63: '63'}


def _gate_cell(row):
    gate = row['gate']
    if gate is None:
        reason = row['coverage']['skip_reason'] or 'no mapping could be formed'
        return 'NOT JUDGED', f'{reason} (on {row["coverage"]["skipped"]} of {row["coverage"]["decisions"]} decisions)'
    return gate['status'].upper(), '; '.join(gate['reasons'])


def _cost_rows(payload):
    rows = []
    for row in payload['rows']:
        gate = row['gate'] or {}
        status, reason = _gate_cell(row)
        rows.append([row['alpha'],
                     f"{row['coverage']['mapped']}/{row['coverage']['decisions']}",
                     f"{row['turnover']['annual']:.2f}x" if row['turnover'] else 'n/a',
                     f"{gate.get('annual_cost_bps', float('nan')):.1f}bp" if gate else 'n/a',
                     f"{gate.get('breakeven_ic', float('nan')):.4f}" if gate else 'n/a',
                     f"{row['information']['21']['mean']:+.4f}" if row['information']['21']['mean'] is not None
                     else 'n/a',
                     f"{gate.get('ic_margin', float('nan')):.2f}x" if gate else 'n/a',
                     status, reason])
    return rows


def _information_rows(payload):
    rows = []
    for row in payload['rows']:
        interval = row['primary_interval']
        cells = []
        for horizon in screening.HORIZONS:
            mean = row['information'][str(horizon)]['mean']
            cells.append('n/a' if mean is None else f'{mean:+.4f}')
        rows.append([row['alpha'], *cells,
                     'n/a' if interval is None else f"[{interval['low']:+.4f}, {interval['high']:+.4f}]",
                     'n/a' if row['dispersion']['constant'] is None
                     else ('constant' if row['dispersion']['constant'] else 'varies')])
    return rows


def report(root=ROOT, output=None):
    root = Path(root)
    payload = read_json(root / 'screen.json')
    output = Path(output or ('research/alpha101-screen-2026-10-11'))
    output.mkdir(parents=True, exist_ok=True)
    rows = payload['rows']
    passed = [row for row in rows if row['gate'] and row['gate']['status'] == 'pass']
    rejected = [row for row in rows if row['gate'] and row['gate']['status'] == 'reject']
    insufficient = [row for row in rows if not row['gate'] or row['gate']['status'] == 'insufficient']

    body = ['<section id="verdict"><h2>Verdict</h2>']
    if passed:
        body.append(f'<p class="lead">{len(passed)} of {len(rows)} registered alphas clear the P4.15 gate and '
                    f'move to the modelling stage: <strong>{", ".join(r["alpha"] for r in passed)}</strong>. '
                    f'{len(rejected)} are rejected by the cost test and {len(insufficient)} cannot be judged. '
                    'No alpha is promoted by this screen.</p>')
    else:
        body.append(f'<p class="lead"><strong>None of the {len(rows)} registered Alpha101 time-series alphas '
                    'clears the P4.15 gate</strong>, so the family is closed before any portfolio work: '
                    f'{len(rejected)} are rejected by the cost test and {len(insufficient)} cannot be judged. '
                    'This is the outcome the gate was built to produce, and it is decided by measured cost '
                    'rather than by a backtest.</p>')
    body.append('</section>')

    body.append('<section id="cost"><h2>The cost test, per alpha</h2>')
    body.append(table(['Alpha', 'Mapped decisions', 'Implied turnover', 'Annual cost', 'Breakeven IC',
                       'Observed IC (21)', 'IC margin', 'Verdict', 'Reason'], _cost_rows(payload)))
    body.append('</section>')

    body.append('<section id="information"><h2>Information and decay, per alpha</h2>')
    body.append(table(['Alpha', *[HORIZON_LABELS[h] for h in screening.HORIZONS], '95% interval (21)',
                       'Cross-section'], _information_rows(payload)))
    body.append('</section>')

    quirk = [[row['alpha'], UNIT_QUIRK[row['alpha']]] for row in rows if row['alpha'] in UNIT_QUIRK]
    body.append('<section id="units"><h2>Disclosed unit quirk in the published formulas</h2>'
                '<p>The paper defines <code>adv{d}</code> as average daily <em>dollar</em> volume while '
                '<code>volume</code> is share volume, and three registered alphas compare the two directly. '
                'Implemented verbatim, those comparisons are dominated by price level. That is a property of '
                'the published formulas, reported here rather than repaired in place; a '
                'dollar-volume-consistent variant would be a different, separately declared family.</p>')
    body.append(table(['Alpha', 'Effect'], quirk))
    body.append('</section>')

    body.append('<section id="method"><h2>Method</h2>'
                '<p>Each decision day, the alpha\'s values across the pinned fourteen-instrument universe rank '
                'the instruments; the top six take the engine\'s own incoming inverse-volatility weights, '
                'renormalised to the incoming gross, and everything else is cash. That is the pooled control\'s '
                'construction with the alpha replacing its selection score, so the measured turnover is the '
                'alpha\'s own. Turnover and the breakeven IC come from the P4.15 gate at the frozen 5bp with the '
                'published 40bp ceiling and 10% tolerance; the IC requirement is the frozen 3x margin at '
                f"the published dispersion of {payload['sigma']:.6f}. Information is the rank IC of the "
                'cross-section against forward returns at 1, 5, 10, 21 and 63 sessions, with a circular block '
                'bootstrap interval (block 6, 2,000 replications, declared seed). Values use audited bars up to '
                'the session before the decision only, and the sixteen formulas are transcribed from the pinned '
                'paper copy, checked character-for-character against a hash-pinned extraction before the screen '
                'runs.</p>'
                '<p>This screen produces no economics, no replay and no promotion: it exists because P4.17 '
                'requires per-alpha turnover and decay to be measured before any portfolio result.</p></section>')

    body.append('<section id="evidence"><h2>Verification</h2>'
                '<p><a href="../../var/research/alpha101-screen-20261011-v1/protocol.json">Frozen protocol</a> · '
                '<a href="../../var/research/alpha101-screen-20261011-v1/formulas.json">Pinned formula '
                'extraction</a> · <a href="../../var/research/alpha101-screen-20261011-v1/screen.json">Screen '
                'artifact</a> · <a href="../../var/research/alpha101-screen-20261011-v1/input_manifest.json">'
                'Input manifest</a> · <a href="../turnover-gate-2026-10-10/index.html">P4.15 gate</a> · '
                '<a href="../sleeve-construction-2026-10-10/index.html">P4.16</a></p>'
                '<ul><li>The screen re-runs to an identical artifact.</li>'
                '<li>Every formula the library implements is compared with the pinned paper extraction, and a '
                'mismatch stops the study rather than being reported.</li>'
                '<li>The pinned P4.16 inputs are re-checked by hash.</li>'
                '<li>No economics are produced, so no arm can be selected on a portfolio outcome.</li></ul>'
                '</section>')

    body.append('<section id="limits"><h2>Limits</h2><ul>'
                '<li>The mapping is one declared construction: a different slot count or weighting would change '
                'the measured turnover.</li>'
                '<li>Implied turnover is the gate\'s own mapping measure, calibrated to within 3.5% of measured '
                'traded notional on the monitored strategy and disclosed there.</li>'
                '<li>The IC series is short by construction: monthly decisions over the pinned window, so a '
                'single episode dominates any interval.</li>'
                '<li>Missing observations stay missing; an alpha is judged on the decisions where its window was '
                'available, and its coverage is reported beside its result.</li>'
                '<li>Nothing here is out-of-sample: the window was inspected by the P4.13-P4.16 studies.</li>'
                '</ul></section>')

    css = ('*{box-sizing:border-box}body{margin:0;background:#f3f0e8;color:#263c47;'
           'font:16px/1.6 system-ui,sans-serif}main{max-width:1180px;margin:0 auto;padding:40px 24px 72px}'
           'h1{font-size:30px;margin:0 0 6px}h2{font-size:21px;margin:38px 0 10px}'
           'p.lead{font-size:17px}table{border-collapse:collapse;width:100%;margin:12px 0;font-size:14px}'
           'th,td{border-bottom:1px solid #d8d2c4;padding:7px 9px;text-align:right}'
           'th:first-child,td:first-child,th:last-child,td:last-child{text-align:left}'
           'thead th{background:#e8e2d4}code{background:#e8e2d4;padding:1px 4px;border-radius:3px}'
           'a{color:#1d6b8a}')
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<title>P4.17 Alpha101 time-series screen</title><style>' + css + '</style></head><body><main>'
            '<h1>P4.17 — Alpha101 restricted time-series subset: the per-alpha screen</h1>'
            '<p>The sixteen registered pure time-series alphas, measured for turnover, cost, breakeven IC and '
            'decay <em>before</em> any portfolio result, as the plan requires.</p>'
            + ''.join(body) + '</main></body></html>')
    (output / 'index.html').write_text(html, encoding='utf-8')
    write_json(root / 'presentation_receipt.json', dict(
        report_sha256=sha256(root / 'screen.json'),
        files={path.relative_to(output).as_posix(): sha256(path) for path in output.rglob('*') if path.is_file()},
        sources={'src/systematic_trading/research/alpha101_analysis.py':
                 sha256(Path('src/systematic_trading/research/alpha101_analysis.py')),
                 'src/systematic_trading/research/alpha101.py':
                 sha256(Path('src/systematic_trading/research/alpha101.py'))}))
    return dict(output=str(output), passed=len(passed), rejected=len(rejected), insufficient=len(insufficient))


if __name__ == '__main__':
    import sys
    print(report(ROOT, sys.argv[1] if len(sys.argv) > 1 else None))
