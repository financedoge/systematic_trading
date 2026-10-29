"""Signal-first research dossier plus the shared full SOTA-overlay report."""
from datetime import UTC, datetime
from decimal import Decimal
import html
import json
import shutil
import subprocess

import numpy as np

import analyze_fitted_breakout_signals as analysis
import fit_breakout_signal_audit as study
from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.backtest.reporting import build_backtest_report_data, render_backtest_report_html
from systematic_trading.research.fr25_lifecycle_monitoring import current_allocation
from systematic_trading.research.strategy_catalog import StrategyDefinition
from systematic_trading.research.strategy_diagram import label


def tab(headers, rows):
    return '<div class="table-wrap"><table class="signal-table"><thead><tr>' + ''.join('<th>' + html.escape(str(h)) + '</th>' for h in headers) + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join('<td>' + html.escape(str(c)) + '</td>' for c in row) + '</tr>' for row in rows) + '</tbody></table></div>'


def pct(value):
    return 'Unavailable' if value is None else f'{value:.2%}'


def number(value):
    return 'Unavailable' if value is None else f'{value:.3f}'


def summarize(rows, ic):
    output = []
    for era in ('early', 'late'):
        for domain in ('short', 'long'):
            selected = [r for r in rows if r['era'] == era and r['domain'] == domain and r['method'] == 'corrected_refit' and r['symbol'] != 'BIL' and r['cost_bp'] == 5 and r['delay'] == 0]
            info = [r for r in ic if r['era'] == era and r['domain'] == domain and r['method'] == 'corrected_refit' and r['symbol'] != 'BIL']
            values = [r['metrics']['21']['state']['ic'] for r in info if r['metrics']['21']['state']['ic'] is not None]
            output.append(dict(era=era, domain=domain, available=len(selected), fit_evidence=sum(bool(r['fit_evidence']) for r in selected),
                positive_return=sum(r['cagr'] > 0 for r in selected), beat_buyhold_return=sum(r['cagr'] > r['buyhold']['cagr'] + 1e-8 for r in selected),
                beat_buyhold_sharpe=sum(r['sharpe'] > r['buyhold']['sharpe'] + 1e-8 for r in selected),
                positive_alpha=sum(r['alpha'] is not None and r['alpha'] > 1e-8 for r in selected),
                significant_positive_alpha=sum(r['alpha'] is not None and r['alpha'] > 1e-8 and r['alpha_holm_p'] < .05 for r in selected),
                median_alpha=float(np.median([r['alpha'] for r in selected if r['alpha'] is not None])),
                ic_available=len(values), positive_ic=sum(v > 1e-8 for v in values), median_ic=float(np.median(values)),
                significant_positive_ic=sum(r['metrics']['21']['state']['ic'] is not None and r['metrics']['21']['state']['ic'] > 1e-8 and r['state21_holm_p'] < .05 for r in info)))
    return output


def plot_claims(rows, ic):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    with np.load(study.WORK / 'gld-nav.npz', allow_pickle=False) as source:
        paths = {k: source[k] for k in source.files}
    data = study.load_asset('GLD')
    lookup = {str(day): i for i, day in enumerate(data['days'])}
    days = paths['original_dates']
    close = np.array([data['close'][lookup[d]] for d in days])
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.4), layout='constrained')
    dates = np.array(days, dtype='datetime64[D]')
    for key, name, color in [('short_original_corrected_original', 'Original GLD short, corrected', '#267aaf'),
                              ('long_original_corrected_original', 'Original GLD long, corrected', '#ce7a27')]:
        axes[0].plot(dates, 100 * paths[key], label=name, color=color)
    axes[0].plot(dates, 100 * close / close[0], label='GLD buy-and-hold', color='#44505a')
    axes[0].set_title('The GLD result: less exposure, less return')
    axes[0].set_ylabel('Value from 100 (cash earns zero)')
    axes[0].legend(fontsize=8)
    index = {(r['symbol'], r['domain']): r for r in ic if r['era'] == 'late' and r['method'] == 'corrected_refit'}
    for domain, color in [('short', '#267aaf'), ('long', '#ce7a27')]:
        points = [r for r in rows if r['era'] == 'late' and r['method'] == 'corrected_refit' and r['domain'] == domain and r['symbol'] != 'BIL' and r['cost_bp'] == 5 and r['delay'] == 0 and r['alpha'] is not None and index[(r['symbol'], domain)]['metrics']['21']['state']['ic'] is not None]
        x = [index[(r['symbol'], domain)]['metrics']['21']['state']['ic'] for r in points]
        axes[1].scatter(x, [r['alpha'] * 100 for r in points], label=domain, c=color, s=26, alpha=.75)
        for r, value in zip(points, x, strict=True):
            if r['symbol'] == 'GLD':
                axes[1].annotate('GLD ' + domain, (value, r['alpha'] * 100), xytext=(5, 5), textcoords='offset points', fontsize=8)
    axes[1].axhline(0, color='#a0a0a0', lw=.8)
    axes[1].axvline(0, color='#a0a0a0', lw=.8)
    axes[1].set(title='Per-ETF corrected refits, 2023–2026', xlabel='21-session state rank IC', ylabel='Annual alpha over ETF beta and BIL (%)')
    axes[1].legend(fontsize=8)
    for ax in axes:
        ax.grid(alpha=.18)
    fig.savefig(study.OUTPUT / 'signal-evidence.png', dpi=160)
    plt.close(fig)


def main():
    declared, fits = analysis.verified_fits()
    output, work = study.OUTPUT, study.WORK
    rows = json.loads((output / 'asset-results.json').read_text())['rows']
    ic = json.loads((output / 'information-coefficients.json').read_text())
    gld = json.loads((output / 'gld-claim-audit.json').read_text())
    cross = json.loads((output / 'cross-sectional-ic.json').read_text())
    portfolios = json.loads((output / 'portfolio-results.json').read_text())
    native = json.loads((output / 'native-checks.json').read_text())
    if len(native) != 3 or any(r['max_nav_difference'] > .011 for r in native):
        raise ValueError('Native checks incomplete')
    summary = summarize(rows, ic)
    study.write(output / 'summary.json', dict(families=summary, alpha_positive_tolerance=1e-8,
        decision='Do not use fitted lifecycle as a validated selection alpha or SOTA overlay. GLD long remains a historical risk-shaping observation.',
        portfolio_gates_passed=sum(g['passed'] for g in portfolios['gates']), portfolio_gates=len(portfolios['gates'])))
    study.write(output / 'sealed-fits.json', fits)
    plot_claims(rows, ic)
    calc = json.loads((work / 'overlay_dynamic-calculation.json').read_text())
    for p in calc['proposals']:
        for t in p['targets']:
            t.update(sleeve='fitted-lifecycle-overlay', rationale='FR25 * (0.5 + 0.25 short state + 0.25 long state); diverted weights to BIL')
            t.pop('hold_horizon_months', None)
    panel = study.frozen._load_panel()
    sessions = [r['trade_date'] for r in calc['nav_series']]
    prices = {str(s): {str(day): float(quantize_money(Decimal(str(panel['close'][i, j])))) for i, day in enumerate(panel['days']) if str(day) >= sessions[0]} for j, s in enumerate(panel['symbols'])}
    prices['URTH'] = {str(day): float(quantize_money(Decimal(str(panel['urth_close'][i])))) for i, day in enumerate(panel['days']) if str(day) >= sessions[0]}
    nav = lambda name: json.loads((work / (name + '-calculation.json')).read_text())['nav_series']
    report, warnings = build_backtest_report_data(result=calc, result_path=work / 'overlay_dynamic-calculation.json',
        split_date='2023-01-01', benchmark_nav_series=nav('FR25'), benchmark_name='FR25 · same inputs/cost/clock',
        extra_benchmarks=[dict(id='constant', name='Constant exposure control', nav_series=nav('constant_overlay_monthly')),
                          dict(id='urth', name='URTH', nav_series=nav('URTH'))], market_prices=prices, market_fx_rates={d: 1. for d in sessions})
    recipe = json.loads(study.frozen.RECIPE_PATH.read_text())
    definition = StrategyDefinition(key='fitted_lifecycle_overlay_audit_v1', name='Individually fitted breakout signals: alpha and SOTA audit',
        sleeve_name='fitted-lifecycle-overlay', state='research', universe_key='supported52', scheduler='dynamic_l1_10pct_monthly_anchor',
        universe_members=tuple(r for r in recipe['universeMembers'] if r['symbol'] != 'URTH'),
        description=declared['portfolio'])
    steps = [
        ('Pin published adjusted OHLC and audited raw volume', '52 supported ETFs; retrospective cohort; no online-provider research inputs.'),
        ('Fit each ETF independently before each evaluation era', 'Short and long domains; 241 candidates; training-only six-friction selection; no test-period tuning.'),
        ('Find the longest qualifying prior price range', 'Fitted quantile width, drift and volatility contraction; completed data only.'),
        ('Confirm a breakout and enter at the following open', 'Fitted confirmation/volume shortcut; explicit decision and filled-position states.'),
        ('Apply initial, trailing, overheat and time exits', 'Check entry-day close; ratchet from highest close; symmetric delay; cooldown also applies to re-entry.'),
        ('Use corrected fitted regimes as an FR25 risk multiplier', 'Core weight * (0.5 + 0.25 short + 0.25 long); removed exposure to BIL; retain core cash.'),
        ('Adopt monthly or at cash-inclusive target L1 change >=10%', 'Compare theoretical target with last adopted target; execute next open and stress an added session.'),
        ('Compare net outcomes with matched controls', 'FR25, momentum, constant exposure and shuffled states; no promotion or allocation authority.'),
    ]
    svg = ''.join(f'<rect x="10" y="{15+i*85}" width="880" height="70" rx="8" fill="#eef4fa"/>' + label([a, b], 25, 40+i*85) for i, (a, b) in enumerate(steps))
    current = current_allocation(calc)
    current['notes'] = 'Historical USD research snapshot through 2026-10-12. Virtual per-ETF signal states, not actual-portfolio stop orders. No current registration or execution authority.'
    report.update(title=definition.name, accountingCurrency='USD', database='Pinned published audited histories',
        modelRegime='Separately fitted short/long ETF lifecycles; corrected execution', strategyDefinition=definition.to_dict(),
        splitLabel='Inspected development boundary', sampleLabels={'in_sample': 'Initial cash anchor', 'out_of_sample': '2023–2026 inspected development'},
        currentAllocation=current, decisionDiagrams=[dict(title='Full decision flow', note='Diagnostic dynamic overlay only',
            svg='<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 700">' + svg + '</svg>')],
        monitoring=dict(lifecycle='research', method='frozen_research_replay', artifactEndDate=sessions[-1], monitoredThrough=sessions[-1],
            priceThrough=sessions[-1], revision=output.name, engine='python/native-LEAN', computedAt=datetime.now(UTC).isoformat(),
            prospectiveStart='Not activated', prospectiveObservations=0, currentSignalAvailable=False, status='historical_only'),
        warnings=[*warnings, *declared['limitations'], 'All 24 selection/overlay SOTA friction gates fail. No prospective statistical confirmation.',
            'Single-ETF diagnostics through October 16; matched portfolio comparisons stop October 12. Cash earns zero in standalone lifecycle diagnostics; portfolio vacancies/diversions earn BIL returns.',
            'Original GLD optimized fits and bounded per-ETF refits are different experiments. Portfolio selection uses the frozen causal dollar-volume mask; the earlier supplementary unfitted construction experiment did not.'])
    gld_rows = [r for r in gld if r['phase'] == 'original' and r['method'] == 'corrected_original' and r['cost_bp'] == 5 and r['delay'] == 0]
    gld_table = [[r['domain'], pct(r['cagr']), number(r['sharpe']), pct(r['maxdd']), pct(r['alpha']), number(r['p']), number(r['ic']['21']['state']['ic']), r['completed_trades']] for r in gld_rows]
    b = gld_rows[0]['buyhold']
    gld_table += [['GLD buy-hold', pct(b['cagr']), number(b['sharpe']), pct(b['maxdd']), 'Benchmark', '—', '—', '—']]
    family_table = [[r['era'], r['domain'], r['available'], r['positive_return'], r['beat_buyhold_return'], r['beat_buyhold_sharpe'],
        r['positive_alpha'], r['significant_positive_alpha'], number(r['median_ic']), r['significant_positive_ic']] for r in summary]
    ic_map = {(r['symbol'], r['domain']): r for r in ic if r['era'] == 'late' and r['method'] == 'corrected_refit'}
    primary = [r for r in rows if r['era'] == 'late' and r['method'] == 'corrected_refit' and r['symbol'] != 'BIL' and r['cost_bp'] == 5 and r['delay'] == 0]
    individual = [[r['symbol'], r['domain'], pct(r['cagr']), pct(r['buyhold']['cagr']), number(r['sharpe']), pct(r['maxdd']), pct(r['alpha']), number(r['alpha_holm_p']),
        number(ic_map[(r['symbol'], r['domain'])]['metrics']['21']['state']['ic']), number(ic_map[(r['symbol'], r['domain'])]['state21_holm_p']), r['completed_trades'], r['fit_evidence']] for r in primary]
    base = [r for r in portfolios['results'] if r['cost_bp'] == 5 and r['delay'] == 0]
    portfolio_table = lambda rr: tab(['Use/control', 'bp', 'Delay', 'CAGR', 'Sharpe', 'Max DD', 'Turnover/year', 'Cost bp/year'],
        [[r['scenario'], r['cost_bp'], r['delay'], pct(r['cagr']), number(r['sharpe']), pct(r['max_drawdown']), number(r['annual_turnover']), f"{r['annual_cost_bps']:.1f}"] for r in rr])
    section = '<section class="signal-study"><h1>Does the individually fitted breakout algorithm predict returns?</h1>'
    section += '<p><strong>GLD long-range historical risk shaping reproduces. General predictive alpha and incremental SOTA value do not.</strong> This audit separately checks the original GLD claims, corrected per-ETF fits, chronological refits, forward IC, asset selection and SOTA overlays. The earlier unfitted construction experiment is supplementary.</p>'
    section += '<h2>1. The original GLD result is real, but limited</h2>' + tab(['Corrected original rule', 'CAGR', 'Sharpe', 'Max DD', 'Annual alpha', 'Alpha p', '21-session IC', 'Closed trades'], gld_table)
    section += '<p>2023-01-03 to 2026-10-16, 5 bp/side. Alpha controls for GLD beta and BIL returns; p-values use Newey–West lag 21 and are descriptive. Long-range has only three completed trades. Its older fit-through-2015 / test-2016–2022 procedure test remains weak: corrected CAGR 0.58%, Sharpe 0.108, drawdown −22.86%. The corrected short original earns 1.08% in that earlier test. These do not establish a stable fitting procedure.</p>'
    section += '<img src="signal-evidence.png" style="max-width:100%;height:auto" alt="GLD NAV and cross-ETF IC versus alpha"/>'
    section += '<h2>2. Positive returns are common; positive alpha is not</h2>' + tab(['Test era', 'Domain', 'ETFs', 'Positive CAGR', 'Beat BH CAGR', 'Beat BH Sharpe', 'Positive alpha', 'Alpha Holm <.05', 'Median state IC21', 'Positive IC Holm <.05'], family_table)
    section += '<p>Late = 2023–2026 after fitting through 2022. Early = 2020–2022 after an independent fit through 2019. BIL is excluded from the 51-risky-ETF inference family; CPER and XLC lack 500 pre-2020 training sessions and receive no future-trained fallback. Tiny annual alpha below 1e−8 is treated as numerical zero; effectively buy-and-hold rules are not counted as positive alpha. The early long-domain IC exception does not generalize to the later era.</p>'
    section += '<p>At the late boundary, short fits have only one materially positive alpha estimate; long fits have three. None survives the 102-test ETF/domain Holm adjustment. Standalone cash earns zero; IC and actual BIL-parking portfolio comparisons provide separate evidence unaffected by presenting cash as free alpha.</p>'
    section += '<details><summary>All 102 late-period fitted ETF/domain results</summary>' + tab(['ETF', 'Domain', 'CAGR', 'BH CAGR', 'Sharpe', 'Max DD', 'Annual alpha', 'Alpha Holm p', 'State IC21', 'IC Holm p', 'Closed trades', 'Training evidence'], individual) + '</details>'
    section += '<h2>3. The cross-sectional signal does not rank ETFs reliably</h2>' + tab(['Era', 'Domain', 'Score', 'Horizon', 'Mean cross-sectional IC', 'HAC p'],
        [[r['era'], r['domain'], r['score'], r['horizon'], number(r['mean_ic']), number(r['p'])] for r in cross if r['horizon'] == 21])
    section += '<p>Time-series IC asks whether one ETF does better when its own signal is on. Cross-sectional IC asks whether stronger signals identify the better ETF at the same date. The latter is the direct test for asset selection. Extension scores add no clear later-period ranking evidence. Labels start at the next executable open; overlapping labels receive horizon-length HAC adjustment.</p>'
    section += '<h2>4. Selection and overlays do not add value to SOTA</h2>' + portfolio_table(base)
    section += '<p>The dynamic fitted overlay earns 12.34% / 1.395 Sharpe / −7.55% drawdown, versus FR25 16.51% / 1.450 / −8.65%. Constant exposure reduction earns 13.43% / 1.593 / −6.00% without reacting to breakout states. All three shuffled-state dynamic overlays beat the real overlay on Sharpe. Lower risk is therefore not evidence that breakout timing adds alpha. The fitted selection rule also trails its matched momentum-only control. All 24 predeclared selection/overlay versus SOTA friction gates fail; no cost ceiling was used.</p>'
    section += '<details><summary>All 102 portfolio cost/delay cases</summary>' + portfolio_table(portfolios['results']) + '</details>'
    section += '<h2>What to retain</h2><p>Keep the corrected lifecycle implementation and GLD result as research evidence. Do not deploy this fitted family as an ETF selector or SOTA overlay. Further testing would need a new, predeclared hypothesis about incremental prediction, chronological validation and distinct exposures; expanding the pool alone does not repair absent IC. All research periods were previously inspected, so even favorable diagnostics would require fresh evidence.</p>'
    section += '<p>Verification: 3,096 return/alpha cases, 516 IC records (three signals × three horizons each), 102 portfolio cases, all corrected paths independently reconciled to an event ledger, selected fit prefixes matched truncated training, and three native Windows LEAN portfolio cases matched to the cent. The standard full report below is the diagnostic dynamic SOTA overlay, not a monitored or approved strategy.</p></section>'
    css = '<style>.signal-study{margin:24px;padding:26px;background:#fff;color:#183149;border:1px solid #b5c7d8;border-radius:12px}.signal-study p{max-width:1150px;line-height:1.65}.signal-study h2{margin-top:28px}.table-wrap{overflow:auto}.signal-table{border-collapse:collapse;font-size:13px;min-width:800px;width:100%;text-align:right}.signal-table td,.signal-table th{padding:9px;border-bottom:1px solid #d8e1eb}.signal-table td:first-child{text-align:left}.signal-study details{margin:18px 0}</style>'
    rendered = render_backtest_report_html(report).replace('<body>', '<body>' + css + section, 1)
    checks = dict(holdings_reconcile=abs(sum(r['value_cnh'] for r in current['holdings']) - current['nav_cnh']) < .011,
        currency='Value USD' in rendered, native=len(native) == 3, full_pool=len(definition.universe_members) == 52,
        price_window=report['monitoring']['priceThrough'] == '2026-10-12', no_prospective=report['monitoring']['prospectiveObservations'] == 0)
    node = shutil.which('node')
    if not node:
        raise ValueError('Node required for shipped renderer validation')
    subprocess.run([node, str(study.ROOT / 'tests/fr25_report_checks.cjs')], input=json.dumps(dict(html=rendered, report=report)), text=True, capture_output=True, check=True)
    checks['client_renderer'] = True
    if not all(checks.values()):
        raise ValueError(checks)
    (output / 'index.html').write_text(rendered, encoding='utf-8')
    study.write(work / 'report.json', report)
    study.write(output / 'validation.json', dict(passed=True, checks=checks, runtime_publication_verified=False,
        report_builder_sha256=study.digest(study.Path(__file__))))
    study.write(output / 'manifest.json', {p.name: study.digest(p) for p in sorted(output.iterdir()) if p.is_file() and p.name != 'manifest.json'})
    print(json.dumps(summary, indent=2))
    print(output / 'index.html')


if __name__ == '__main__':
    main()
