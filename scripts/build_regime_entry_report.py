"""Three inspectable comparisons, mathematical definitions and every ETF."""
import gzip
from io import BytesIO
import json
from pathlib import Path
import re
import numpy as np
import research_regime_entry as study

NAMES={'control':'A: fixed policy / original detector','hmm':'B: refitted constrained HMM','guarded':'C: HMM / cautious entry'}


def summary(rows):
    lookup={(r['symbol'],r['era'],r['arm'],r['cost_bp'],r['delay']):r for r in rows};out=[]
    for era,*_ in study.ERAS:
        for cost,delay in study.FRICTIONS:
            for arm in study.model.ARMS:
                a=[r for r in rows if r['era']==era and r['arm']==arm and r['cost_bp']==cost and r['delay']==delay and r['symbol']!='BIL']
                b=[lookup[r['symbol'],era,'control',cost,delay] for r in a]
                sg=float(np.median([x['sharpe'] for x in a])-np.median([x['sharpe'] for x in b]));qg=float(np.quantile([x['cagr'] for x in a],.25)-np.quantile([x['cagr'] for x in b],.25))
                guard=float(np.mean([x['cagr']>=y['cagr']-.01 and x['maxdd']>=y['maxdd']-.02 for x,y in zip(a,b)]))
                out.append(dict(era=era,cost_bp=cost,delay=delay,arm=arm,cases=len(a),enabled=sum(x['enabled'] for x in a),
                    median_sharpe=float(np.median([x['sharpe'] for x in a])),median_cagr=float(np.median([x['cagr'] for x in a])),
                    lower_quartile_cagr_gain=qg,median_sharpe_gain=sg,guard_fraction=guard,passed=sg>0 and qg>0 and guard>=.9,
                    improved=sum(x['cumulative']>y['cumulative']+1e-10 for x,y in zip(a,b)),worse=sum(x['cumulative']<y['cumulative']-1e-10 for x,y in zip(a,b)),
                    median_annual_cost_bp=float(np.median([x['cost_bp_annual'] for x in a])),median_turnover=float(np.median([x['turnover_annual'] for x in a])),
                    **{'median_'+k:float(np.median([x[k] for x in a if x[k] is not None])) for k in ('correlation','beta','alpha_annual','ic5','exposure')},
                    yearly={year:float(np.median([x['yearly'][year] for x in a])) for year in a[0]['yearly']}))
    return out


def figure(c,symbol,era,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    days=np.array(c['days'],dtype='datetime64[D]');a=c['arms']['guarded'];active=days>=np.datetime64(c['evaluation_start'])
    fig,axes=plt.subplots(6,1,figsize=(14,13),sharex=True,layout='constrained',height_ratios=[2,.6,.8,.6,.6,1.2])
    axes[0].plot(days,c['close'],color='#173d54',label='Adjusted close');axes[0].plot(days,np.asarray(a['stop'],float),color='#bd5260',label='Protection')
    for e in a['trades']:
        x=np.datetime64(e['entry_date']);y=np.datetime64(e['exit_date']) if e['exit_date'] else days[-1]
        axes[0].axvspan(x,y,color='#008675',alpha=.07);axes[0].scatter(x,e['entry'],color='#008675',marker='^',s=30)
        if e['exit_date']:axes[0].scatter(y,e['exit_price'],color='#bd5260',marker='v',s=30)
    axes[0].legend(fontsize=8);axes[0].set_ylabel('Adjusted USD')
    axes[1].bar(days,np.asarray(c['volume'],float)/1e6,color='#9aabb6',width=1.5);axes[1].set_ylabel('Raw volume (m)')
    for key,label,color in [('fast_up','Up','#008675'),('neutral','Range','#b39b50'),('fast_down','Down','#bd5260')]:axes[2].plot(days,np.asarray(a[key],float),color=color,label=label)
    axes[2].set_ylabel('New fast HMM');axes[2].legend(fontsize=8,ncol=3);axes[2].set_ylim(0,1)
    for key,label,color in [('slow_up','Slow up','#008675'),('slow_down','Slow down','#bd5260')]:axes[3].plot(days[active],np.asarray(c[key])[active],color=color,label=label)
    axes[3].legend(fontsize=8,ncol=2);axes[3].set_ylim(0,1)
    for key,label,color in [('gate','Extra guard passes (up signal still required)','#008675'),('blocked','Eligible entry blocked','#bd5260')]:axes[4].plot(days,np.asarray(a[key],float),color=color,label=label)
    axes[4].legend(fontsize=8,ncol=2);axes[4].set_ylim(-.05,1.05)
    for name,color in [('control','#91a3b0'),('hmm','#c78b28'),('guarded','#008675')]:axes[5].plot(days,np.asarray(c['arms'][name]['nav'],float),color=color,label=NAMES[name])
    axes[5].legend(loc='upper left',fontsize=8);axes[5].set_ylabel('NAV / initial 100')
    for ax in axes:ax.grid(alpha=.15);ax.axvline(np.datetime64(c['evaluation_start']),color='#777',ls='--',lw=.7)
    axes[5].xaxis.set_major_locator(dates.MonthLocator(interval=6));axes[5].xaxis.set_major_formatter(dates.DateFormatter('%Y-%m'))
    fig.suptitle(f'{symbol} | {era} | C: refitted HMM and cautious entry\nRange band {c["selection"]["hmm"]["model"]["band"]}; guard {c["selection"]["guard"]}; fixed base policy in all comparisons')
    fig.savefig(path,dpi=130);plt.close(fig)


def equations():
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    formulas=[r'x_t=b^{fast}_t/\sigma_{train},\quad x_t\mid z_t=s\sim N(\mu_s,v_s),\quad b\in\{0.05,0.10\}',
        r'-2\leq\mu_D\leq-2b,\quad\mu_R=0,\quad 2b\leq\mu_U\leq2',
        r'0.000025\leq v_s\leq4,\quad v_R\leq b^2,\quad0.65\leq A_{ss}\leq0.98',
        r'p_t(s)=\frac{f_s(x_t)\sum_jp_{t-1}(j)A_{js}}{\sum_i f_i(x_t)\sum_jp_{t-1}(j)A_{ji}}',
        r'G_t=\{p^{slow}_{U,t}<0.7\}\ \mathrm{or}\ \{\mathrm{last\ closed\ trade\ lost}\}',
        r'G_t:\quad p_{U,t}\geq\max(0.8,e),\quad b^{fast}_t>0,\quad c_t\geq k+\mathbf{1}_{loss}',
        r'G_t:\quad\log(P_t/P_{a-1})\geq h\sigma_{train}+2f,\quad k\in\{2,3\},\quad h\in\{0.5,1\}',
        r'\mathrm{after\ loss}:\quad\exists u\geq t_{exit}:p_{U,u}<0.5\quad\mathrm{before\ new\ confirmation}',
        r'r^{strategy}_t=\alpha+\beta r^{ETF}_t+\epsilon_t,\quad\alpha_{annual}=252\alpha',
        r'IC_5=\mathrm{Spearman}\left(p_{U,t}-p_{D,t},\ O_{t+6+d}/O_{t+1+d}-1\right)']
    parts=[]
    for j,formula in enumerate(formulas):
        buf=BytesIO();mathtext.math_to_image('$'+formula+'$',buf,prop=FontProperties(size=15),format='svg',color='#17384d');svg=buf.getvalue().decode();svg=svg[svg.index('<svg'):]
        svg=re.sub(r'id="([^"]+)"',lambda m:f'id="eq{j}_{m[1]}"',svg);svg=re.sub(r'xlink:href="#([^"]+)"',lambda m:f'xlink:href="#eq{j}_{m[1]}"',svg)
        parts.append('<div class="equation">'+svg+'</div>')
    study.write(study.OUT/'equations.json',formulas)
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(formulas),1,figsize=(16,10),layout='constrained')
    for ax,formula in zip(axes,formulas):ax.axis('off');ax.text(.01,.3,'$'+formula+'$',fontsize=13)
    fig.savefig(study.OUT/'equation-proof.png',dpi=120,bbox_inches='tight');plt.close(fig)
    return ''.join(parts)


def main():
    study.verified();receipt=json.loads((study.OUT/'validation.json').read_text())
    assert study.prior.study.digest(study.OUT/'chart-data.json.gz')==receipt['chart_sha256']
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()));rows=json.loads((study.OUT/'asset-results.json').read_text())
    sums=summary(rows);study.write(study.OUT/'summary.json',sums);primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0]
    weakest={era:min((r for r in primary if r['era']==era and r['arm']=='guarded' and r['symbol']!='BIL'),key=lambda r:(r['cumulative'],r['symbol'])) for era,*_ in study.ERAS}
    focus={('INDA','late'),('WEAT','late'),('GLD','late'),('GLD','early'),('USO','late'),('TLT','late'),('MCHI','late'),*((r['symbol'],era) for era,r in weakest.items())}
    for symbol,era in sorted(focus):figure(charts[f'{symbol}_{era}'],symbol,era,study.OUT/f'{symbol}_{era}.png')
    pct=lambda x:'—' if x is None else f'{100*x:+.2f}%'
    fmt=lambda x:'—' if x is None else f'{x:.3f}'
    st=''.join(f'<tr><td>{r["era"]}</td><td>{NAMES[r["arm"]]}</td><td>{r["median_sharpe"]:.3f}</td><td>{pct(r["median_cagr"])}</td><td>{pct(r["guard_fraction"])}</td><td>{r["median_correlation"]:.3f}</td><td>{r["median_beta"]:.3f}</td><td>{pct(r["median_alpha_annual"])}</td><td>{r["median_annual_cost_bp"]:.1f}</td></tr>' for r in sums if r['cost_bp']==5 and r['delay']==0)
    lookup={(r['symbol'],r['era'],r['arm']):r for r in primary};pt=''
    for era,*_ in study.ERAS:
        for r in sorted((r for r in primary if r['era']==era and r['arm']=='guarded'),key=lambda r:r['cumulative']):
            a,b=lookup[r['symbol'],era,'control'],lookup[r['symbol'],era,'hmm']
            pt+=f'<tr><td>{r["symbol"]}</td><td>{era}</td><td>{pct(a["cumulative"])}</td><td>{pct(b["cumulative"])}</td><td>{pct(r["cumulative"])}</td><td>{r["sharpe"]:.3f}</td><td>{pct(-r["maxdd"])}</td><td>{fmt(r["ic5"])}</td><td>{r["closed_trades"]}</td><td>{r["guard"]}</td></tr>'
    exports=' · '.join(f'<a href="{symbol}_{era}.png">{symbol} {era} figure</a>' for symbol,era in sorted(focus))
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Trend detection and cautious entry</title>
<style>body{font:16px/1.5 system-ui;color:#17384d;background:#f5f8fa;max-width:1280px;margin:34px auto;padding:0 20px}h1,h2{line-height:1.2}h2{margin-top:38px}a{color:#006b70}.note{background:#fff0d7;border-left:4px solid #b47b22;padding:16px}.card{background:white;padding:18px;border:1px solid #d9e3e9;margin:14px 0}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center}button,select,input{font:inherit;padding:7px;border:1px solid #b4c5ce;border-radius:5px;background:white}button{cursor:pointer}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:7px 9px;border-bottom:1px solid #e2e8ed;text-align:right}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}#chart{width:100%;height:auto}#readout{min-height:64px}.equation{overflow:auto;padding:9px;background:white;margin:5px 0}.equation svg{max-width:100%;height:auto}small{color:#536b7b}</style>
<h1>Trend detection and cautious entry</h1><p>27 October 2026 · Full supported ETF pool · Three component comparisons</p>
<p class="note"><b>A is a matched fixed-policy control, not the previous adaptive strategy.</b> All three arms hold the original per-ETF trading policy fixed. This isolates changes to market detection and entry evidence from Bayesian shadow-policy feedback. The previous adaptive strategy is shown separately in the selected ETF's diagnostics. These repeatedly inspected periods are development evidence, not fresh validation.</p>
<h2>What changed</h2><ul><li><b>A — original detector:</b> previous training-selected thesis exit, original fast/slow filters, fixed base entry and stop policy.</li><li><b>B — refitted HMM:</b> fit distinct down/range/up slope distributions per ETF. The range distribution is centred at zero and cannot become arbitrarily broad. Every ETF uses the new HMM; other policy parameters stay as in A.</li><li><b>C — cautious entry:</b> use B, but require persistent up evidence and price progress in weak slow trends or after a loss. Losses also require a fresh reset of the fast up-state before another setup can qualify. Strong slow uptrends otherwise retain their original entry rule.</li></ul>
<p>Range here means a distribution of near-zero filtered slopes. It is not proof of a horizontal price box or profitable mean reversion. The slow context still comes from the existing local-linear filter; this experiment does not claim a learned multi-year regime or jointly fitted hierarchy. Volume is visible for inspection, not a signal in this isolated test.</p>
<div id="findings">__FINDINGS__</div>
<h2>Inspect every ETF</h2><p id="weakestNote"></p><div class="controls"><label>Era <select id="era"><option value="late">2023–2026</option><option value="early">2020–2022</option></select></label><label>ETF <select id="etf"></select></label><label>Algorithm <select id="arm"><option value="control">A · Fixed / original detector</option><option value="hmm">B · Refitted HMM</option><option value="guarded">C · HMM / cautious entry</option></select></label><button id="weakest">Weakest C</button><button id="weat">WEAT</button><button id="tlt">TLT rebounds</button></div>
<div class="controls"><label>From <input id="from" type="date"></label><label>To <input id="to" type="date"></label><button id="reset">Full context</button><button id="inda">INDA incident</button><button id="gold">GLD 2020</button></div>
<div class="card"><p id="metrics"></p><p id="dependence"></p><small id="parameters"></small><p id="readout">Hover for an exact date; click two dates to zoom.</p><svg id="chart" viewBox="0 0 1200 1290"></svg></div>
<details open><summary>Actual trades and entry context</summary><div class="scroll"><table><tr><th>Entry</th><th>Exit</th><th>Slow context at entry signal</th><th>Net return</th><th>Initial stop distance</th><th>Exit reason</th></tr><tbody id="trades"></tbody></table></div></details>
<details><summary>Fitted means, variances, transition matrix and original policy</summary><pre id="fitparameters" style="overflow:auto"></pre></details>
<details><summary>Results conditional on causal slow context</summary><table><tr><th>Context</th><th>Sessions</th><th>Exposure</th><th>Mean daily strategy</th><th>Mean daily ETF</th><th>Closed trades</th><th>Losing trades</th><th>Mean trade</th></tr><tbody id="regimes"></tbody></table><p>Daily context uses the preceding close. Trade context uses the entry signal. “Uncertain” includes neither slow up nor slow down reaching 70%; it is not a verified range label. Mean daily returns do not compound or add across regimes.</p></details>
<p>__EXPORTS__</p><h2>Pool comparison</h2><div class="scroll"><table><tr><th>Era</th><th>Algorithm</th><th>Median Sharpe</th><th>Median CAGR</th><th>Within A guards</th><th>Daily correlation</th><th>Beta</th><th>Annual intercept</th><th>Annual cost (bp)</th></tr>__SUMMARY__</table></div>
<p>All summaries are ETF medians, excluding BIL. Primary: 5 bp per side, next-open execution. Acceptance requires better median Sharpe and lower-quartile CAGR, plus at least 90% within 1 percentage point CAGR / 2 points maximum drawdown of A, in both eras and all six friction cases. Correlation is a diagnostic, not an optimization target. All costs and delays are in the results links.</p>
<details open><summary>Every ETF — worst C return first in each era</summary><div class="scroll"><table><tr><th>ETF</th><th>Era</th><th>A return</th><th>B return</th><th>C return</th><th>C Sharpe</th><th>C drawdown</th><th>C IC5</th><th>C trades</th><th>C selected guard</th></tr>__POOL__</table></div></details>
<h2>Mathematical definitions</h2>__EQUATIONS__
<p>Here b<sup>fast</sup> is the causal log-price slope, σ<sub>train</sub> the training daily return dispersion, z the fast state, A the transition matrix, e the original entry threshold, f the per-side fee, and a the first confirming close in a new flat opportunity. P<sub>a−1</sub> is that sequence's preceding close. A loss means a negative fee-adjusted completed trade. The loss flag clears after a nonlosing completed trade. The confirmation counter resets when high-up evidence breaks, while invested, or before a required post-loss reset. This can postpone buying for a long time; it contains no permanent stop-trading instruction.</p>
<p>Outside the gate conditions, C uses the original entry/rearming rule. When enabled, the gate requires up ≥ max(0.8,e), positive slope, k consecutive closes, and price progress hσ+2f; after loss it requires k+1 closes and an observed up &lt;0.5 at or after the exit close before a fresh sequence. The last requirement uses the exit-day close, already after its opening fill. Eligibility alone never cancels a pending order.</p>
<p>All arms retain the preceding training-selected thesis exit: after up probability stays below θ for k<sub>exit</sub> closes and current fast slope ≤0, sell at the next executable open. Slow-up probability ≥0.7 halves θ and adds two closes. The original down-state exit and nonloosening stop also remain; no new fixed profit target or independent hard risk cap was added. Stop = max(previous stop, peak close − distance × entry open × σ<sub>train</sub>), tested before the next-close ratchet. Initial distance and slow-up widening remain those of the original fixed base policy. The inspected trade table reports the actual initial fraction.</p>
<h2>Fitting and interpretation</h2>
<p>The HMM uses EM with two starts and 25 iterations. Directional means stay beyond ±2b, with separate variances; range mean is zero and its variance is capped at b². Transition pseudocounts are 0.1+3I and persistence is bounded at 0.65–0.98. For each ETF, fit both b candidates before the final 252 training observations, select by forward predictive slope likelihood on those 252, then refit on all training slopes. Existing Kalman filters and trading parameters already use the full training period, so this is an HMM-only holdback, not a nested holdout of the entire strategy.</p>
<p>Select C's four k/h choices over the final 756 training return sessions. Require at least three closed trades, better Sharpe, CAGR no more than 1 point worse and drawdown no more than 2 points worse than B. Choose Sharpe, then CAGR, then smaller k/h; if none pass, C is exactly B. This is in-sample trading-rule selection. No evaluation-period overrides; all 52 later / 50 earlier supported ETFs are retained. Missing earlier histories are excluded under the parent coverage contract.</p>
<p>Trading uses forward filtering, not future-smoothed state labels; <a href="https://luisdamiano.github.io/stancon18/hmm_stan_tutorial.pdf">the HMM filtering reference</a> explains this distinction. Slopes are derived from overlapping price observations and violate the simplest independent-emission idealization. Narrowing the range state does not establish improved economic regimes: judged by executable returns, IC and preservation of winners, not attractive state colours.</p>
<p>Regression uses aligned daily arithmetic returns, with a zero cash-rate reference, α annualized linearly and HAC(5) covariance. See <a href="https://www.statsmodels.org/stable/generated/statsmodels.regression.linear_model.OLSResults.html">OLS results and robust covariance documentation</a>. This descriptive intercept is not causal, risk-free-adjusted Jensen alpha or a proof of skill. ETF-specific heteroskedastic exposure, multiple trials and repeated inspection limit significance claims. IC uses overlapping five-session forward open returns, is not cost-adjusted and is reported descriptively. B and C have the same raw HMM score and therefore the same IC; their entry selection differs. A five-session IC is not a test of every possible holding horizon.</p>
<p>Adjusted prices determine returns and signals; raw audited share volume is descriptive. Published histories and hashes are pinned to the existing audited batch. Publication-vintage limitations remain. Fees 5/10/20 bp each side, with zero/one extra execution-day delay, fractional cash-funded holdings, zero-interest cash and terminal marking. Native validation concerns frozen signals under the app's whole-share/cent-price accounting, not an independent fit of this HMM. No broker, promotion or live changes.</p>
<p><a href="asset-results.json">All metrics, regimes and annual returns</a> · <a href="summary.json">Cost/delay comparisons</a> · <a href="fits.json">Training fits and selections</a> · <a href="protocol.json">Frozen protocol</a> · <a href="validation.json">Accounting checks</a> · <a href="native-checks.json">Native checks</a> · <a href="state-semantics-audit.json">State-label failure audit</a></p>
<script>const DATA = __DATA__;
__SCRIPT__</script></html>'''
    def display(x):
        if isinstance(x,float):return round(x,7)
        if isinstance(x,list):return [display(v) for v in x]
        if isinstance(x,dict):return {k:display(v) for k,v in x.items()}
        return x
    script=study.ROOT/'scripts/assets/regime-entry-script.js';findings=study.OUT/'findings.html'
    for token,value in dict(EXPORTS=exports,SUMMARY=st,POOL=pt,EQUATIONS=equations(),FINDINGS=findings.read_text(encoding='utf-8') if findings.exists() else '',
        DATA=json.dumps(display(dict(charts=charts,rows=primary,weakest=weakest)),separators=(',',':')).replace('</','<\\/'),SCRIPT=script.read_text(encoding='utf-8')).items():html=html.replace('__'+token+'__',value)
    (study.OUT/'index.html').write_text(html,encoding='utf-8');study.write(study.OUT/'weakest-cases.json',weakest)
    study.write(study.OUT/'manifest.json',dict(files={p.name:study.prior.study.digest(p) for p in study.OUT.iterdir() if p.is_file() and p.name!='manifest.json'},report_code={str(p.relative_to(study.ROOT)).replace(chr(92),'/'):study.prior.study.digest(p) for p in (Path(__file__),script,study.ROOT/'tests/regime_entry_controls.cjs',study.ROOT/'scripts/validate_regime_entry.py')}))
    print(json.dumps(dict(charts=len(charts)*3,weakest={e:r['symbol'] for e,r in weakest.items()})))


if __name__=='__main__':main()
