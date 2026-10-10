"""Render the frozen IC follow-up, without fitting or changing a strategy."""
from datetime import date
from pathlib import Path
import html
import json
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json

ROOT = Path('var/research/full-pool-signal-diagnostics-20261010-v1')
OUT = Path('research/full-pool-signal-diagnostics-2026-10-10')
NAMES = dict(CR='Context ridge',FR='Financial ridge',AR='Combined ridge',
             CT='Context tree',FT='Financial tree',AT='Combined tree')
ORDER = ('CR','FR','AR','CT','FT','AT')


def number(x, digits=3):
    return 'n/a' if x is None else f'{x:.{digits}f}'


def signed(x, scale=1, digits=3):
    return 'n/a' if x is None else f'{scale*x:+.{digits}f}'


def interval(row):
    return '['+', '.join(number(v) for v in row['ci95'])+']'


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in headers)+\
        '</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+\
        '</tbody></table></div>'


def plot(data):
    forecast, portfolios = data['forecast'],data['portfolio']
    colors = ['#235b80','#bd6634','#397b65']
    fig, axes = plt.subplots(2,2,figsize=(14,9),layout='constrained')
    fig.set_facecolor('#fcfaf5')
    for ax in axes.flat:
        ax.set_facecolor('#fcfaf5')
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.16)
    x=np.arange(6)
    for i,(key,label) in enumerate([('mean_ic','Historical mean'),('increment_ic','Macro increment'),('total_ic','Total forecast')]):
        vals=[forecast['summary'][a][key] for a in ORDER]
        axes[0,0].bar(x+(i-1)*.24,vals,.24,color=colors[i],label=label)
    axes[0,0].set_xticks(x,[a for a in ORDER])
    axes[0,0].set_title('Full-pool rank information coefficient')
    axes[0,0].set_ylabel('Mean monthly Spearman correlation')
    axes[0,0].legend(frameon=False,fontsize=8)
    years=list(portfolios['comparisons']['CR']['years'])
    x=np.arange(len(years))
    for i,arm in enumerate(('CR','FR','AR')):
        vals=[portfolios['comparisons'][arm]['years'][y]['delta']*100 for y in years]
        axes[0,1].bar(x+(i-1)*.24,vals,.24,color=colors[i],label=NAMES[arm])
    axes[0,1].set_xticks(x,[y+('*' if y=='2026' else '') for y in years])
    axes[0,1].set_title('Actual net calendar return change vs cap control')
    axes[0,1].set_ylabel('Percentage points; 2026 through October 8')
    axes[0,1].legend(frameon=False,fontsize=8)
    base=Path(data['protocol']['parent'])
    econ={a:read_json(base/'python'/f'{a}-cost5-delay0-evaluation.json') for a in ('CP','CR','FR','AR')}
    nav={a:np.array([float(r['nav']) for r in e['nav']]) for a,e in econ.items()}
    dates=[date.fromisoformat(r['date']) for r in econ['CP']['nav']]
    for i,arm in enumerate(('CR','FR','AR')):
        axes[1,0].plot(dates,100*(nav[arm]/nav['CP']-1),color=colors[i],label=NAMES[arm])
    axes[1,0].set_title('Relative wealth accumulated vs cap control')
    axes[1,0].set_ylabel('Portfolio NAV / control NAV − 1 (%)')
    axes[1,0].legend(frameon=False,fontsize=8)
    ix=[i for i,d in enumerate(dates) if date(2025,3,1)<=d<=date(2025,6,30)]
    for arm,color in [('CP','#75726a'),*zip(('CR','FR','AR'),colors,strict=True)]:
        dd=nav[arm]/np.maximum.accumulate(np.r_[1e6,nav[arm]])[1:]-1
        axes[1,1].plot([dates[i] for i in ix],dd[ix]*100,color=color,label='Cap control' if arm=='CP' else NAMES[arm])
    axes[1,1].set_title('The drawdown that offset context ridge’s return gain')
    axes[1,1].set_ylabel('Drawdown from own running peak (%)')
    axes[1,1].xaxis.set_major_locator(mdates.MonthLocator())
    axes[1,1].xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    axes[1,1].legend(frameon=False,fontsize=8)
    fig.suptitle('Predictive signal survives; portfolio contribution is small and uneven',fontsize=17,color='#1d3342')
    fig.savefig(OUT/'diagnostics.png',dpi=160)
    plt.close(fig)


def render():
    data=read_json(ROOT/'analysis.json')
    receipt=read_json(ROOT/'analysis_receipt.json')
    if receipt['analysis']!=sha256(ROOT/'analysis.json') or receipt['protocol']!=sha256(ROOT/'protocol.json'):
        raise ValueError('Diagnostic analysis changed')
    OUT.mkdir(parents=True,exist_ok=True)
    f,p=data['forecast'],data['portfolio']
    plot(data)
    body='''<header><div class="eyebrow">RESEARCH FOLLOW-UP · 10 OCTOBER 2026</div>
    <h1>A useful forecast can still make a weak portfolio overlay.</h1>
    <p class="lead">The full-pool ridge signals deserve further research. The previous test rejected a particular sizing recipe under its fixed hurdle; it did not establish that economic information has no value.</p>
    <p>All 14 ETFs remain candidates. No mandatory assets, no XLE/XLB-only tests. This report diagnoses the frozen 2021–October 8, 2026 evaluation, using the same audited input pins, models, decisions and net trade ledgers.</p></header>
    <nav><a href="#signal">Signal</a><a href="#transfer">Portfolio use</a><a href="#outcomes">Contributions</a><a href="#episodes">Success & failure</a><a href="#evidence">Evidence</a></nav>
    <div class="cards"><div><b>0.115–0.119</b><span>Full-pool ridge forecast IC</span></div><div><b>40 / 70</b><span>Context ridge decisions that changed weights</span></div><div><b>+0.167pp</b><span>Context ridge net CAGR vs cap control</span></div></div>
    <img class="figure" src="diagnostics.png" alt="Full-pool forecast IC, calendar contribution, relative NAV and 2025 drawdown comparisons">
    <section id="signal"><h2>1. The positive IC is meaningful evidence, with uncertainty</h2>
    <p>Rank IC is the cross-sectional Spearman correlation between a forecast and the next rebalance-open return across all 14 ETFs, averaged across completed months. The total forecast equals each ETF’s training mean plus its predicted macro increment. The table separates these pieces; ICs themselves are not additive.</p>'''
    body+=table(['Model','Months','Total IC','Mean-only IC','Macro increment IC','Partial rank IC*','Total IC 95% interval†'],[
        [NAMES[a],f['summary'][a]['months'],*[number(f['summary'][a][k]) for k in ('total_ic','mean_ic','increment_ic','partial_ic')],
         interval(f['inference']['6'][a+'/total_ic'])] for a in ORDER])
    body+='''<p class="note">* Correlation of rank residuals after controlling for ETF training means and the existing M1 selector score; descriptive, not a new trading model. † Marginal circular six-month-block intervals, 10,000 draws. Calendar blocks retain unavailable months; ETF rows are not independent samples.</p>
    <p>All three ridge total-IC intervals remain positive with 3-, 6- and 12-month blocks. Financial and combined macro-increment intervals also remain positive individually. However, the paired improvement over the mean-only forecast is uncertain, and none of the 12 registered incremental-IC contrasts passes 5% Holm adjustment. Positive evidence and proven incremental superiority are different claims.</p>
    <p>The ridge full-pool MAEs are 4.08%, 3.94% and 4.57%, compared with 3.71%, 3.78% and 3.71% for their matched training-mean baselines. This indicates worse return-magnitude accuracy; it does not negate better ranking. No two-ETF error statistic is used to judge the pool.</p></section>
    <section id="transfer"><h2>2. Much of the signal cannot change this portfolio</h2>
    <p>The tested overlay preserves the momentum-selected members and the exact cash budget. It applies ×1.10 when the macro increment exceeds +25bp and the total forecast is positive; ×0.90 below −25bp; otherwise ×1.00. It then normalizes back to the same gross exposure, subject to the 45% cap. It never ranks all forecasts to choose the portfolio.</p>
    <div class="flow">14 forecasts → existing M1 selection → increment thresholds → same cash budget → capped weights → realized returns and costs</div>'''
    body+=table(['Model','Ready / decisions','Changed','Mean capital shifted*','Shift when changed','All-pool IC†','Held-set IC†','Top 6 forecasts held‡'],[
        [NAMES[a],f"{f['summary'][a]['ready_decisions']} / 70",f['summary'][a]['changed_decisions'],
         number(100*f['summary'][a]['mean_active_share'],2)+'%',number(100*f['summary'][a]['mean_active_share_when_changed'],2)+'%',
         number(f['summary'][a]['all14_ic_on_selected_months']),number(f['summary'][a]['selected_total_ic']),
         number(f['summary'][a]['top6_forecasts_held'],2)+' / 6'] for a in ORDER])
    body+='''<p class="note">* Half the sum of absolute weight changes, averaged over all 70 decisions. † Compared on identical months with at least three positive parent targets: 50 context/combined and 61 financial months. This is a diagnostic of selection within the full pool, not a separate candidate universe. ‡ Mean over model-ready decisions, including cash months.</p>
    <p>For context ridge, 12 decisions abstain because required features are unavailable. Of the 58 ready decisions, six are all cash, two have one holding, and ten give all held assets the same multiplier. Normalization cancels the latter changes. Only 40 decisions move weights, shifting 3.04% of capital on average when they do.</p>
    <p>Financial ridge’s total IC falls from 0.130 across all 14 to 0.049 among the held assets on the same months. Context falls from 0.138 to 0.108. Excluded assets can be ranked correctly without producing a trade. Moreover, cash is fixed, so an accurate broad risk warning cannot reduce total exposure through this overlay.</p>
    <p>These mechanisms are measurable constraints on signal use. They do not show that removing the constraints would improve performance. Forecasting skill and the amount translated into active weights are distinct, as discussed by <a href="https://rpc.cfainstitute.org/research/financial-analysts-journal/2002/portfolio-constraints-and-the-fundamental-law-of-active-management">Clarke, de Silva and Thorley (2002)</a>.</p></section>
    <section id="outcomes"><h2>3. There are positive contributions, but the risk-ratio gains are small</h2>
    <p>Changes below are relative to CP, the same M1/14 portfolio with the explicit final cap. Costs are 5bp per traded dollar, cash interest is zero, and evaluation starts with fresh USD 1 million. The unchanged M1 reference remains in the original full reports.</p>'''
    body+=table(['Model','CAGR change (pp)','Sharpe change','Calmar change','Volatility change (pp)','Worst DD change (pp)','Annual cost change (bp)'],[
        [NAMES[a],signed(p['comparisons'][a]['deltas']['cagr'],100),signed(p['comparisons'][a]['deltas']['sharpe_zero_cash']),
         signed(sum(p['comparisons'][a]['ratio_decomposition'][k] for k in ('calmar_cagr_effect','calmar_drawdown_effect'))),
         signed(p['comparisons'][a]['deltas']['volatility'],100),signed(p['comparisons'][a]['deltas']['max_drawdown'],100),
         signed(p['comparisons'][a]['deltas']['annual_cost_bps'])] for a in ORDER])
    body+='''<p>Context ridge’s +0.0162 Sharpe consists of +0.0137 from higher average return and +0.0025 from slightly lower volatility. Financial ridge earns more, but higher volatility offsets most of that Sharpe benefit (+0.0099 − 0.0082 ≈ +0.0017). These are exact arithmetic decompositions, not causal estimates.</p>
    <p>For context ridge, the higher CAGR would add +0.0202 Calmar if maximum drawdown stayed fixed. The worse drawdown subtracts −0.0192, leaving only +0.0010. Annualized trading cost changes are near zero or favorable: cost drag is not the main explanation for the weak gains.</p>
    <p>The original +0.05 Sharpe and +0.05 Calmar hurdle was not met. That remains a failed recipe screen. Context ridge’s 12-month-block Sharpe-difference interval was positive, while the six-month interval included zero; Calmar and the original family-adjusted portfolio-return tests did not establish robust superiority.</p></section>
    <section id="episodes"><h2>4. Where steering helped, and where it hurt</h2>
    <p>Actual net calendar return changes, in percentage points:</p>'''
    years=list(p['comparisons']['CR']['years'])
    body+=table(['Year','Context ridge','Financial ridge','Combined ridge'],[[y+(' to Oct 8' if y=='2026' else ''),
        *[signed(p['comparisons'][a]['years'][y]['delta'],100) for a in ('CR','FR','AR')]] for y in years])
    body+='''<p><b>Context worked best in 2024:</b> +0.625pp net annual return, with weights changed in all 12 months. It was slightly negative in 2023. Financial ridge helped most in 2022 (+0.943pp), but gave back −0.644pp in 2025. This is uneven historical performance, not an established regime switch.</p>
    <p><b>April 2022 was a successful context decision.</b> It cut SPY by 2.55 percentage points of portfolio weight. SPY then lost 9.10% over the next rebalance-open interval. That underweight alone added about 23.2bp to the gross target-weight comparison. Across all assets, the decision added 23.8bp gross over that interval; actual calendar-April net outperformance was 28.1bp. The windows and accounting differ, so these are not interchangeable figures.</p>
    <p><b>April 2025 was the damaging reversal.</b> Context raised XLE by 1.32pp and cut GLD by 1.37pp; their next rebalance-open returns were −14.61% and +3.07%. The whole portfolio lost 27.7bp relative to CP in calendar April. This is attribution within the 14-candidate portfolio, not a sector-only test.</p>
    <p>During CP’s actual worst peak-to-trough interval, March 19–April 8, 2025, context’s XLE contribution was −23.9bp relative to CP, partly offset by MCHI (+12.0bp), GLD (+3.1bp) and other holdings. The reconciled total was −11.1bp. Maximum drawdown worsened from −8.308% to −8.419%; CP recovered June 12 and context June 24. A few badly timed weight changes can therefore erase most of the Calmar benefit from years of small gains.</p>
    <p>Predeclared, ex-ante descriptive splits also disagree across models. Context’s gross target-weight benefit averaged +2.06bp per completed month after a positive trailing 63-session SPY return, versus −0.92bp after a nonpositive return. Financial ridge showed the opposite sign (+3.43bp after down trends, −0.41bp after up trends). No new regime-gated strategy is inferred from these inspected samples.</p></section>
    <section><h2>Research disposition</h2><p><b>Retain the ridge signals as research leads; retain the failed disposition of the existing sizing recipes.</b> Context has the clearest portfolio contribution. Financial has encouraging forecast evidence but poorer translation into held-asset rankings. Combined does not establish an advantage over context, and trees have weaker full-pool IC.</p>
    <p>The next useful test is a separately frozen full-pool comparison of how economic ranks enter candidate selection or sizing, with a historical-mean-only control and the same cash/risk budget. Compare a bounded rank-based use of information with the existing threshold overlay, using new prospective evidence where possible. Do not force ETFs into the portfolio, remove gates because of these retrospective splits, or add an open-ended parameter search.</p>
    <p>Monitored M1/14 and CR12, funded F3, execution approvals and paper/live controls are unchanged.</p></section>
    <section id="evidence"><h2>All-model evidence and reproducibility</h2>'''
    for arm in ORDER:
        s,c=f['summary'][arm],p['comparisons'][arm]
        body+=f'<details><summary>{NAMES[arm]} — uncertainty, conditions, months and assets</summary>'
        body+=table(['Block months','Total IC interval','Increment IC interval','Increment Holm p','Total − mean IC interval','Improvement Holm p'],[
            [b,interval(v[arm+'/total_ic']),interval(v[arm+'/increment_ic']),number(v[arm+'/increment_ic']['holm_p']),
             interval(v[arm+'/total_minus_mean_ic']),number(v[arm+'/total_minus_mean_ic']['holm_p'])] for b,v in sorted(f['inference'].items(),key=lambda x:int(x[0]))])
        rows=[]
        for split,values in s['conditions'].items():
            for label,r in values.items():
                rows.append([split,label,r['months'],r['ready'],r['changed'],number(r['total_ic']),number(r['increment_ic']),number(r['mean_gross_steering_bps'],2)])
        body+=table(['Split','Condition','Months','Ready','Changed','Total IC','Increment IC','Gross steering (bp/month)'],rows)
        body+='<p>Gross steering is the sum of active target weights × next rebalance-open returns. These diagnostic contributions omit costs, rounding and interim drift; actual net outcomes below use the full ledger.</p>'
        body+=table(['Best/worst months','Month','CP return','Candidate return','Net difference (bp)'],[
            [label,r['month'],number(100*r['parent'],2)+'%',number(100*r['candidate'],2)+'%',signed(r['delta'],1e4,2)]
            for label in ('best_months','worst_months') for r in c[label]])
        body+=table(['Asset','Net PnL difference (USD)','Common worst-DD contribution (bp)'],[
            [asset,signed(c['asset_pnl_difference_usd'][asset],digits=2),signed(c['parent_peak_trough_asset_contributions'][asset],1e4,2)]
            for asset in sorted(c['asset_pnl_difference_usd'])])
        body+=f"<p>Net terminal wealth difference: ${c['deltas']['terminal_nav']:,.2f}; gross asset PnL difference: ${c['gross_asset_pnl_difference_usd']:,.2f}; extra fees: ${c['deltas']['total_fees_usd']:,.2f}. Dollar differences reconcile exactly and include the effect of different accumulated NAV. They are not independent asset alpha estimates.</p>"
        body+=f"<p>Own worst drawdown: {html.escape(json.dumps(c['worst_drawdown']))}. Positive gross steering in {s['positive_steering_changed_months']}/{s['changed_complete_months']} changed, completed decisions; {s['positive_ic_negative_steering']} changed months had positive total IC but negative gross steering.</p></details>"
    body+='''<p>This is a diagnostic follow-up on previously inspected history and retrospectively selected M1. The 58–69 complete model months overlap and assets are dependent. Marginal IC intervals are not adjusted discovery claims. The registered Holm family includes six macro-increment ICs and six total-minus-mean differences; MR exactly duplicates CR and is excluded. Availability gaps remain missing. Historical economic-vintage availability assumptions are inherited; audited prices do not establish historical publication timestamps. No prices were fetched for this study.</p>
    <p>Raw activity stays on the parent’s audited basis; forecast labels and return accounting use the pinned dividend/split-adjusted prices. All calculations preserve the October 8 common cutoff. October 2026 has a decision but no complete next-rebalance label.</p>
    <p><a href="../../var/research/full-pool-signal-diagnostics-20261010-v1/protocol.json">Frozen diagnostic protocol</a> · <a href="../../var/research/full-pool-signal-diagnostics-20261010-v1/analysis.json">Complete machine-readable analysis</a> · <a href="../../var/research/full-pool-signal-diagnostics-20261010-v1/analysis_receipt.json">Hashes and source receipt</a> · <a href="../expanded-economics-2026-10-10/index.html">Original study and 13 full shared strategy reports</a></p>'''
    body+=f"<p class='note'>Diagnostic protocol SHA-256: {sha256(ROOT/'protocol.json')}. Verified {sum(data['verified_files'].values()):,} parent manifest entries, seven evaluation replay bundles and all seven NAV/cash/asset ledgers. Price batch 4bfdef171ba1d180f2191c589d269a9ad42e2f497b9f069b80e1e9043668f3fd; economic batch 9fb6784447635430354fa0547e8787f37d0e7c69d60a62053a65b0279ff8b8b4.</p></section>"
    css='''*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:#f4f1e9;color:#24343d;font:16px/1.6 system-ui,sans-serif}main{max-width:1260px;margin:auto;padding:48px 38px}header{max-width:1000px}h1{font-size:46px;line-height:1.13;letter-spacing:-1.4px;margin:14px 0 22px}h2{font-size:26px;line-height:1.25;margin:0 0 16px}p{max-width:1080px}.eyebrow{font-size:12px;font-weight:700;letter-spacing:2px;color:#586c74}.lead{font-size:21px;line-height:1.5}.note{font-size:13px;color:#657078;overflow-wrap:anywhere}a{color:#175677}nav{display:flex;gap:22px;flex-wrap:wrap;margin:28px 0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:30px 0}.cards>div{background:#fffdf8;border-top:3px solid #3b7485;padding:20px}.cards b{display:block;font-size:29px}.cards span{font-size:14px}.figure{width:100%;height:auto;border:1px solid #ddd8ca;margin-bottom:32px}section{background:#fffdf8;padding:28px;margin:22px 0;border:1px solid #e1dccf;border-radius:8px}.scroll{overflow:auto;margin:20px 0}table{border-collapse:collapse;width:100%;font-size:14px;font-variant-numeric:tabular-nums}th,td{text-align:right;padding:11px 12px;border-bottom:1px solid #e4e2db;white-space:nowrap}th{background:#eaf0ef;color:#294f5f}th:first-child,td:first-child{text-align:left}tr:nth-child(even) td{background:#f8f7f2}.flow{background:#eaf0ef;color:#244d60;padding:18px;border-left:4px solid #3d7d88}details{border-top:1px solid #d8d7ce;padding:18px 0}summary{cursor:pointer;font-weight:650;font-size:17px}details p{font-size:14px}@media(max-width:700px){main{padding:26px 14px}h1{font-size:34px}.cards{grid-template-columns:1fr}section{padding:20px 14px}.lead{font-size:18px}}'''
    (OUT/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Full-pool signal diagnostics</title><style>'+css+'</style><main>'+body+'</main></html>',encoding='utf8')
    shutil.copyfile(Path(__file__),ROOT/'render_source.py')
    write_json(ROOT/'presentation_receipt.json',dict(analysis_sha256=sha256(ROOT/'analysis.json'),
        renderer_sha256=sha256(Path(__file__)),files={f.name:sha256(f) for f in OUT.iterdir() if f.is_file()}))
    print(OUT/'index.html')


if __name__=='__main__':
    render()
