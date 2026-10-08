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
    arms = ['F3','P3','CR','FR','FT','MR','AR','AT']
    comparison = table(['Model', 'Annual return', 'Sharpe', 'Calmar', 'Worst drawdown'], [
        [names[a], f'{stats(a)["cagr"]:.2%}', f'{stats(a)["sharpe_zero_cash"]:.3f}',
         f'{stats(a)["calmar"]:.3f}', f'{stats(a)["max_drawdown"]:.2%}'] for a in arms])
    full = table(['Model', 'Annual return', 'Sharpe', 'Calmar', 'Worst drawdown'], [
        [names[a], f'{stats(a,"full")["cagr"]:.2%}', f'{stats(a,"full")["sharpe_zero_cash"]:.3f}',
         f'{stats(a,"full")["calmar"]:.3f}', f'{stats(a,"full")["max_drawdown"]:.2%}'] for a in ['P3','CR','FR','AR']])
    forecast = table(['Features / model', 'Complete months', 'Rank correlation', 'Prediction error', 'Historical-mean error'], [
        [g, r['months'], f'{r["mean_rank_ic"]:.3f}', f'{r["mae"]:.2%}', f'{r["mean_baseline_mae"]:.2%}']
        for g, r in report['diagnostics']['forecast_summary'].items()])
    annual = table(['Model', *stats('P3')['calendar_returns']], [
        [a, *[f'{v:.2%}' for v in stats(a)['calendar_returns'].values()]] for a in ['P3','CR','FR','FT','AR','AT']])
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Financial conditions and ETF combinations — findings</title><style>
body{{margin:0;background:#f3f6fa;color:#21354b;font:16px/1.65 system-ui}}main{{max-width:1150px;margin:24px auto;padding:30px;background:white}}h1{{line-height:1.2}}h2{{margin-top:2em;font-size:23px}}a{{color:#245ac3}}.notice{{padding:18px;background:#fff7db;border:1px solid #e9cc76}}.scroll{{overflow:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:10px;border-bottom:1px solid #dbe3ed;text-align:right}}th:first-child,td:first-child{{text-align:left}}th{{background:#edf3f8}}img{{width:100%}}li{{margin:.5em 0}}code{{overflow-wrap:anywhere}}</style><main>
<p>ETF research · October 7, 2026 · Completed finite experiment</p><h1>Financial data add a small gain, without a robust replacement</h1>
<p class="notice">Retain the financial-only linear model for later research. The augmented linear model and both trees fail the predefined replacement screen. The monitored leading + payroll/inflation context linear recipe stays unchanged.</p>
<p>The new recorders now expose Treasury curve slopes, Chicago Fed credit conditions and bank lending standards in Market Data → Economic Data. All 2,112 planned snapshots are published and hash-verified, with the original 1,441 records unchanged. We tested two fixed combinations on each of the twelve existing ETFs: eight financial features alone, or added to the original thirteen leading/context features.</p>
<p><a href="assessment.html">Full assessment, uncertainty and asset responses</a> · <a href="reports/FR.html">Financial-only linear report</a> · <a href="reports/CR.html">Frozen context-linear reference</a></p>
<h2>January 2021–October 6, 2026 evaluation</h2><p>USD accounting; 5bp costs; zero cash interest. P3 is F3 with a final 45% target cap. Every challenger preserves P3's gross exposure, cash and positive positions. Historical decisions use original economic vintages and completed monthly return labels. This is retrospective walk-forward research on previously inspected history, not an untouched holdout.</p>{comparison}
<p>Financial-only ridge (FR) raises Sharpe from 1.1027 to 1.1057 and Calmar from 0.9740 to 0.9798 versus the monitored context model (CR), with roughly 10 basis points more annual return. Adding the new features to the old set (AR) raises Sharpe by only 0.0003 and fails the delayed-execution Calmar comparison. Both trees are weaker than their paired linear models.</p><img src="comparison.png" alt="Financial-condition challenger values and drawdowns">
<h2>Why this does not justify another change</h2><ul>
<li>FR passes the fixed cost, delay and drawdown retention screen, but the gain over CR is uncertain. Six-month-block 95% intervals are −0.0243 to +0.0307 for the Sharpe difference and −0.1024 to +0.0475 for the Calmar difference.</li>
<li>No mean-return contrast passes 5% Holm with three- or six-month blocks. Financial trees versus P3 pass only with twelve-month blocks (adjusted p=0.0204), while failing the stronger linear-model and delay checks. That sensitivity is not stable evidence of an improvement.</li>
<li>Over the full 2016–2026 period, FR's Sharpe and Calmar fall below CR. Worst drawdown grows from 16.83% to 17.13%. The apparent gain depends on the evaluation period.</li>
<li>Financial-only models are ready on 70/70 evaluation decisions; augmented and matched models on 58/70. The twelve unavailable decisions are the same original-context gaps. MR exactly reproduces CR, so adding the financial data does not change the combined model's sample in this study.</li>
<li>Prediction error is worse than the simple ETF-specific historical-mean forecast for every tested feature/model combination. A small portfolio gain is not proof of better general return prediction.</li></ul>{full}
<h2>Asset beneficiaries and losers</h2><p>The model does not mechanically cut equity exposure. FR changes 42 of 70 monthly allocations while preserving invested capital. Relative to P3, it increases SPY in 29 decisions, EWJ in 23 and DBC in 18; it reduces HYG in 17 and VGK in 20. The same asset can gain in one month and lose in another. Full per-ETF conditional response matrices and allocation counts are in the assessment.</p>
<p>These are conditional model associations, not identified causal effects of economic shocks. The current experiment cannot add a beneficiary that the existing eligibility filter excluded. Expanding the ETF universe will be the right point to revisit that limitation.</p>
<h2>Prediction quality</h2>{forecast}<p>October 2026 has no completed next-month label, so it is excluded from prediction-error scoring. Portfolio valuation still extends through October 6.</p>
<h2>Calendar stability</h2>{annual}<p>2026 is partial through October 6. Calendar comparisons are descriptive and are not additional parameter-selection windows.</p>
<h2>New data and remaining source work</h2><ul>
<li><a href="https://fred.stlouisfed.org/series/T10Y3M">10-year minus 3-month</a> and <a href="https://fred.stlouisfed.org/series/T10Y2Y">10-year minus 2-year Treasury yields</a>: weekday daily curves, with original missing holidays preserved. Histories begin January 3, 2006; the omitted initial January 2 holiday is disclosed as unsupported.</li>
<li><a href="https://fred.stlouisfed.org/series/NFCICREDIT">Chicago Fed credit conditions</a>: a weekly revised standardized composite, not a corporate bond spread.</li>
<li><a href="https://fred.stlouisfed.org/series/DRTSCILM">Large/medium-firm</a> and <a href="https://fred.stlouisfed.org/series/DRTSCIS">small-firm lending standards</a>: quarterly SLOOS net tightening. Quarter dates are not release timestamps; exact archive vintages control historical availability.</li>
<li>National PMI, permitted corporate-spread archives, and timestamped pre-release consensus remain separate access gaps. No subscription was assumed. Historical archive availability remains an explicit assumption; the app first captured these data in October 2026.</li></ul>
<h2>Next step after this economic checkpoint</h2><p>Keep the monitored CR specification frozen. Begin ETF-universe admission with issuer identity, holdings, shares outstanding and NAV recorders; add sector activity, growth, valuation and positioning inputs before testing narrower ETFs. Energy balances and futures positioning are possible pilots after source and release-history qualification. Publish and audit ETF adjusted prices and any required raw price/volume history first. Single stocks remain outside scope.</p>
<h2>Reproducibility</h2><p>All 51 replays, eleven native accounting checks and 27 inference jobs completed, using all sixteen logical CPUs with memory-bounded native concurrency. F0, F3, P3 and CR exactly reproduce the prior full-period fills, 2,705 daily values and final holdings. The new feature/model logic passed ex-ante, missing-data, opposite-asset-response and matched-sample tests. Frozen protocol: <code>{sha256(root/'protocol.json')}</code>.</p>
<p>Shared detail charts use a December 31, 2020 cash anchor; annualized returns differ slightly from the study's January 4 evaluation start. Fills, daily values, terminal value, drawdown and Sharpe agree. This findings page is a presentation supplement and changes no inputs, models, parameters or statistical screens.</p></main></html>'''
    (output/'findings.html').write_text(page,encoding='utf-8')
    write_json(output/'findings_receipt.json',dict(report_sha256=sha256(root/'report.json'),
        publisher_sha256=sha256(Path(__file__)),findings_sha256=sha256(output/'findings.html'),presentation_only=True))
    write_json(output/'artifact_manifest.json',{str(p.relative_to(output)):sha256(p) for p in output.rglob('*') if p.is_file() and p.name!='artifact_manifest.json'})
    print(output/'findings.html')


if __name__=='__main__':main()
