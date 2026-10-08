"""Presentation-only findings from a verified, completed economic experiment."""
import argparse
from html import escape
from pathlib import Path

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json, checked_files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root, args.output
    checked_files(root, 'input_manifest.json')
    checked_files(root, 'decision_manifest.json')
    assert read_json(root/'report_receipt.json')['sha256'] == sha256(root/'report.json')
    for stage in ['calculate', 'native', 'analyze', 'report']:
        assert read_json(root/f'{stage}_progress.json')['status'] == 'succeeded'
    report = read_json(root/'report.json')

    def table(headers, rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+escape(str(c))+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'

    def stats(arm, period='evaluation'):
        return report['results'][f'{arm}-{period}-cost5-delay0']

    names = report['protocol']['arms']
    arms = ['F3', 'P3', 'LT', 'LR', 'MT', 'MR', 'CT', 'CR']
    comparison = table(['Model', 'Annual return', 'Sharpe', 'Calmar', 'Worst drawdown'], [
        [names[a], f'{stats(a)["cagr"]:.2%}', f'{stats(a)["sharpe_zero_cash"]:.3f}',
         f'{stats(a)["calmar"]:.3f}', f'{stats(a)["max_drawdown"]:.2%}'] for a in arms])
    full = table(['Model', 'Annual return', 'Sharpe', 'Calmar', 'Worst drawdown'], [
        [names[a], f'{stats(a,"full")["cagr"]:.2%}', f'{stats(a,"full")["sharpe_zero_cash"]:.3f}',
         f'{stats(a,"full")["calmar"]:.3f}', f'{stats(a,"full")["max_drawdown"]:.2%}'] for a in ['P3','LR','CR']])
    forecast = table(['Features / model', 'Complete months', 'Rank correlation', 'Prediction error', 'Historical-mean error'], [
        [g, r['months'], f'{r["mean_rank_ic"]:.3f}', f'{r["mae"]:.2%}', f'{r["mean_baseline_mae"]:.2%}']
        for g, r in report['diagnostics']['forecast_summary'].items()])
    annual = table(['Model', *stats('P3')['calendar_returns']], [
        [a, *[f'{v:.2%}' for v in stats(a)['calendar_returns'].values()]] for a in ['P3','LT','LR','CT','CR']])
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Economic ETF research — findings</title><style>
body{{margin:0;background:#f3f6fa;color:#21354b;font:16px/1.65 system-ui}}main{{max-width:1150px;margin:24px auto;padding:30px;background:white}}h1{{line-height:1.2}}h2{{margin-top:2em;font-size:23px}}a{{color:#245ac3}}.notice{{padding:18px;background:#fff7db;border:1px solid #e9cc76}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:10px;border-bottom:1px solid #dbe3ed;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{background:#edf3f8}}img{{width:100%}}li{{margin:.5em 0}}code{{overflow-wrap:anywhere}}</style><main>
<p>ETF research · October 7, 2026 · Completed finite experiment</p><h1>A small economic-model gain, without enough evidence to replace F3</h1>
<p class="notice">Retain the linear models as research candidates. The decision trees failed the predeclared replacement screen. No economic model was promoted, monitored or given trading authority.</p>
<p>We tested seven leading US indicators and a separate payroll, manufacturing-output and headline/core inflation context group. Each ETF receives its own model, so the same reading can favor one asset and weaken another. Historical decisions use the available economic vintage and completed return labels only.</p>
<p><a href="assessment.html">Full comparison, uncertainty and asset sensitivities</a> · <a href="reports/F3.html">F3 report</a> · <a href="reports/CR.html">Combined linear-model report</a></p>
<h2>January 2021–October 6, 2026 evaluation</h2><p>USD accounting; 5bp trading costs; zero interest on cash. P3 adds a 45% final target cap to F3 and is the common control. All economic arms preserve P3's invested budget, cash and eligible holdings. Previously inspected history is retrospective walk-forward evidence, not an untouched holdout.</p>{comparison}
<p>The combined linear model raises Sharpe from 1.081 to 1.103 and Calmar from 0.922 to 0.974 versus P3, with about 22 basis points more annual return. Compare it with the matched leading-only linear model to isolate context: the increment is only 6 basis points of annual return and 0.009 Sharpe. Different missing-data schedules explain part of the apparent advantage over the unrestricted leading-only model.</p>
<img src="comparison.png" alt="Portfolio values and drawdowns of economic models and controls">
<h2>What survives the stronger checks</h2><ul>
<li>Both linear arms pass the predeclared cost, delay and drawdown retention screen. Neither tree beats its corresponding linear model; the combined tree also fails the delayed Sharpe comparison.</li>
<li>No mean-return contrast passes 5% significance after adjusting for all nine comparisons, under any of the three block lengths. For combined linear minus P3, six-month-block adjusted p is 0.797. Its marginal Sharpe interval is positive, but the Calmar interval includes zero; these are not family-adjusted ratio discoveries.</li>
<li>The full 2016-onward context weakens the case: combined linear improves Sharpe slightly but lowers Calmar and increases maximum drawdown versus P3. The leading-only linear model lowers both ratios in that longer history. Early years are warm-up/calibration context, not a second untouched test.</li></ul>{full}
<h2>Forecast accuracy and missing observations</h2>{forecast}
<p>Prediction error is mean absolute next-month return error across twelve ETFs. Rank correlation is the mean cross-ETF rank correlation, not a significance claim. Leading-only linear forecasts barely improve on each asset's historical-mean forecast. Adding context worsens absolute forecast error despite its small portfolio gain; the evidence does not establish a generally better return predictor.</p>
<p>Leading models were available for 66 of 70 evaluation decisions. Combined and matched controls were available for 58 and abstained for twelve consecutive decisions from November 2025 through October 2026. Missing or stale releases, including an interior missing CPI observation, remain missing. No later vintage was inserted. Combined models currently revert to P3. Current recorder capture began in October 2026; historical availability relies on the declared daily ALFRED archive assumption.</p>
<h2>Different assets can benefit</h2><p>The combined linear model changed 35 evaluation allocations. It increased EWJ in 21 decisions, SPY in 18, HYG in 13 and GLD in 11, while also reducing those assets in other decisions. This is a bidirectional allocation model, not merely an equity-cut rule. It cannot add a beneficiary excluded by the parent momentum filter; changing that constraint needs a separate experiment.</p>
<p>In the latest leading-model fit, stronger capital-goods-order growth has a positive linear conditional response for SPY and DBC, but negative responses for gold and Treasury-duration ETFs. The tree assigns a different SPY response. These are fitted conditional associations, not identified economic shocks or reliable causal signs. The complete response matrix is in the assessment.</p>
<h2>Calendar stability</h2>{annual}<p>2026 ends October 6 and is not a full year. Parent fallback protection, especially the 2022–23 low-exposure episode, remains the dominant portfolio effect.</p>
<h2>Next research and recorder work</h2><ol>
<li>Keep both linear specifications frozen for later confirmation; no threshold or model-depth search on these outcomes. Any recurring candidate observation must run through the app's complete versioned strategy service.</li>
<li>Build and expose public yield-curve, credit-spread and lending-standards recorders, with release/vintage timing and history coverage, before another economic experiment. Do not backdate later revisions or infer unpublished consensus forecasts.</li>
<li>Start prospective ETF issuer holdings, shares outstanding and NAV capture, then select one sector or physical-industry pilot with activity, growth, valuation and positioning inputs. Audit and publish the relevant ETF prices and raw activity inputs first.</li>
<li>National PMI and dated pre-release consensus remain access gaps. Regional Philadelphia surveys are not national PMI. Country-specific predictors and economic beneficiaries outside the current basket remain untested; single stocks stay outside scope.</li></ol>
<h2>Reproducibility</h2><p>All 51 portfolio replays, eleven independent LEAN accounting checks and 21 focused tests passed. All sixteen logical CPUs were used with memory-bounded native execution. Original full-period F0/F3 fills, daily values and final holdings reproduce exactly. Frozen source, data, models, target decisions, cost/delay runs and receipts are preserved with protocol <code>{sha256(root/'protocol.json')}</code>.</p>
<p>The shared detail reports add a December 31, 2020 cash anchor for chart comparison. Their calendar annualization therefore differs slightly from the study's January 4 start (combined linear: 10.98% versus 11.00%); fills, daily values, terminal value, drawdown and Sharpe agree.</p>
<p>The frozen protocol retains parent-study caveats for provenance. BIL-specific remarks describe that earlier study's input ancestry; BIL is excluded here. The old before-overlay cap limitation applies to unchanged F0/F3 references. P3 and every economic arm apply the additional final 45% target cap shown above; subsequent holding drift remains possible.</p>
<p>This findings page is a presentation supplement produced after the frozen analysis. It does not alter models, thresholds, data or statistical screens. The complete assessment retains all eleven primary portfolios, shared-format reports and decision flows.</p></main></html>'''
    (output/'findings.html').write_text(page, encoding='utf-8')
    write_json(output/'findings_receipt.json', dict(report_sha256=sha256(root/'report.json'),
        publisher_sha256=sha256(Path(__file__)), findings_sha256=sha256(output/'findings.html'),
        presentation_only=True))
    write_json(output/'artifact_manifest.json', {str(p.relative_to(output)):sha256(p)
        for p in output.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})
    print(output/'findings.html')


if __name__ == '__main__':
    main()
