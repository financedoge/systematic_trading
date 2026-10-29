"""Mathematical research report and every supported single-ETF inspection."""
import gzip
from io import BytesIO
import json
import re

import numpy as np

import research_online_policy as study

NAMES={'fixed':'A: frozen policy','bayes':'B: continuous Bayesian learning','warning':'C: warning-accelerated learning'}


def summary(rows):
    lookup={(r['symbol'],r['era'],r['arm'],r['cost_bp'],r['delay']):r for r in rows};out=[]
    for era,*_ in study.ERAS:
        for cost,delay in study.FRICTIONS:
            for arm in study.model.ARMS:
                a=[r for r in rows if r['era']==era and r['arm']==arm and r['cost_bp']==cost and r['delay']==delay and r['symbol']!='BIL']
                comparisons=[]
                for reference in ('fixed','bayes'):
                    b=[lookup[r['symbol'],era,reference,cost,delay] for r in a]
                    guard=float(np.mean([x['cagr']>=y['cagr']-.01 and x['maxdd']>=y['maxdd']-.02 for x,y in zip(a,b,strict=True)]))
                    sg=float(np.median([r['sharpe'] for r in a])-np.median([r['sharpe'] for r in b]))
                    qg=float(np.quantile([r['cagr'] for r in a],.25)-np.quantile([r['cagr'] for r in b],.25))
                    comparisons.append(dict(reference=reference,median_sharpe_gain=sg,lower_quartile_cagr_gain=qg,guard_fraction=guard,
                        improves_return=sum(x['cumulative']>y['cumulative']+1e-10 for x,y in zip(a,b,strict=True)),passed=sg>0 and qg>0 and guard>=.9))
                out.append(dict(era=era,cost_bp=cost,delay=delay,arm=arm,cases=len(a),
                    median_sharpe=float(np.median([r['sharpe'] for r in a])),median_cagr=float(np.median([r['cagr'] for r in a])),
                    median_changes=float(np.median([r['changes'] for r in a])),comparisons=comparisons))
    return out


def figure(c,symbol,era,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    days=np.array(c['days'],dtype='datetime64[D]');a=c['arms']['warning'];active=days>=np.datetime64(c['evaluation_start'])
    fig,axes=plt.subplots(5,1,figsize=(14,12),sharex=True,layout='constrained',height_ratios=[2,.6,.8,.6,1.2])
    axes[0].plot(days,c['close'],color='#173d54',label='Adjusted close')
    axes[0].plot(days,np.asarray(a['stop'],float),color='#bd5260',label='Adopted protection')
    for e in a['trades']:
        x=np.datetime64(e['entry_date']);y=np.datetime64(e['exit_date']) if e['exit_date'] else days[-1]
        axes[0].axvspan(x,y,color='#008675',alpha=.07);axes[0].scatter(x,e['entry'],color='#008675',marker='^',s=30)
        if e['exit_date']:axes[0].scatter(y,e['exit_price'],color='#bd5260',marker='v',s=30)
    for e in a['events']:
        if e['accelerated']:axes[0].axvline(np.datetime64(e['day']),color='#c68b26',lw=.7,ls=':')
    axes[0].set_ylabel('Adjusted USD');axes[0].legend(loc='upper left',fontsize=8)
    axes[1].bar(days,np.asarray(c['volume'],float)/1e6,color='#9aabb6',width=1.5);axes[1].set_ylabel('Raw volume\n(millions)')
    for key,color,label in [('fast_up','#008675','Fast up'),('slow_down','#bd5260','Slow down')]:
        axes[2].plot(days[active],np.asarray(c[key])[active],color=color,label=label)
    axes[2].plot(days,np.asarray(a['entry_threshold'],float),color='#c68b26',label='Learned entry threshold')
    axes[2].set_ylim(0,1);axes[2].legend(loc='upper left',ncol=3,fontsize=8)
    axes[3].plot(days,np.asarray(a['distance'],float),color='#8154a5');axes[3].set_ylabel('Protection\ndistance k')
    for name,color in [('fixed','#91a3b0'),('bayes','#c78b28'),('warning','#008675')]:
        axes[4].plot(days,np.asarray(c['arms'][name]['nav'],float),color=color,label=NAMES[name])
    axes[4].legend(loc='upper left',fontsize=8);axes[4].set_ylabel('NAV / initial100')
    for ax in axes:ax.grid(alpha=.15);ax.axvline(np.datetime64(c['evaluation_start']),color='#777',ls='--',lw=.7)
    axes[4].xaxis.set_major_locator(dates.MonthLocator(interval=6));axes[4].xaxis.set_major_formatter(dates.DateFormatter('%Y-%m'))
    fig.suptitle(f'{symbol} | {era} | Warning-accelerated learning\nActual fills and stops; amber vertical marks = accelerated forgetting; no health pause')
    fig.savefig(path,dpi=140);plt.close(fig)


def equations():
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    formulas=[
        r'e_j=\mathrm{clip}(e_0+d_j,0.5,0.9),\quad d_j\in\{-0.1,0,0.1\},\quad a_j\in\{0.5,1,1.5\}',
        r'x_j=\mathrm{clip}(x_0+0.2(a_j-1),0.45,0.9),\quad k_{j,t}=a_j k_{0,t}',
        r'x^{up}_j=\mathrm{clip}(0.85+0.2(a_j-1),0.65,0.95),\quad k_{0,t}=k_{wide}\ \mathrm{if\ aligned\ and\ context,\ else}\ k_{tight}',
        r'r_i=\frac{O_{exit}}{O_{entry}}\frac{1-f}{1+f}-1,\quad y_i=\mathrm{clip}\left(\frac{r_i}{\hat\sigma\sqrt{D_i}},-3,3\right)',
        r'\rho=2^{-1/126},\quad (N,S,W)\leftarrow\rho(N,S,W),\quad (N_j,S_j,W_j)\leftarrow(N_j+1,S_j+y_i,W_j+\mathbf{1}_{r_i>0})',
        r'\mu_j\mid\mathcal{D}_t\sim N\left(\frac{S_j}{4+N_j},\frac{1}{4+N_j}\right),\quad \widehat p_j=\frac{1+W_j}{2+N_j}',
        r'u_j=\frac{S_j}{4+N_j}-\frac{0.25}{\sqrt{4+N_j}},\quad j^*=\arg\max_j u_j,\quad \mathrm{switch\ if}\ u_{j^*}>u_{current}+0.05',
        r'\mathrm{warning}\Rightarrow(N,S,W)_{old}\leftarrow0.25(N,S,W)_{old},\quad \Delta t_{warnings}\geq20',
        r'\ell_{t+1}=\max(\ell_t,M_t-k_{j,t}\hat\sigma O_{entry}),\quad \mathrm{exit\ if}\ C_t<\ell_t\ \mathrm{or}\ P_t(down)\geq x_{j,t}'
    ]
    rendered=[]
    for j,formula in enumerate(formulas):
        buffer=BytesIO();mathtext.math_to_image('$'+formula+'$',buffer,prop=FontProperties(size=15),format='svg',color='#17384d')
        svg=buffer.getvalue().decode();svg=svg[svg.index('<svg'):]
        svg=re.sub(r'id="([^"]+)"',lambda m:f'id="eq{j}_{m[1]}"',svg)
        svg=re.sub(r'xlink:href="#([^"]+)"',lambda m:f'xlink:href="#eq{j}_{m[1]}"',svg)
        rendered.append('<div class="equation">'+svg+'</div>')
    study.write(study.OUT/'equations.json',formulas)
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(formulas),1,figsize=(18,9),layout='constrained')
    for ax,formula in zip(axes,formulas,strict=True):ax.axis('off');ax.text(.01,.3,'$'+formula+'$',fontsize=12)
    fig.savefig(study.OUT/'equation-proof.png',dpi=120,bbox_inches='tight');plt.close(fig)
    return ''.join(rendered)


def main():
    study.verified();receipt=json.loads((study.OUT/'validation.json').read_text())
    if study.prior.study.digest(study.OUT/'chart-data.json.gz')!=receipt['chart_sha256']:raise ValueError('Charts changed')
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()))
    rows=json.loads((study.OUT/'asset-results.json').read_text());s=summary(rows);study.write(study.OUT/'summary.json',s)
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0]
    weakest={era:min((r for r in primary if r['era']==era and r['arm']=='warning' and r['symbol']!='BIL'),key=lambda r:(r['cumulative'],r['symbol'])) for era,*_ in study.ERAS}
    focus={('WEAT','late'),('GLD','late'),('TLT','late'),*((r['symbol'],era) for era,r in weakest.items())}
    for symbol,era in sorted(focus):figure(charts[f'{symbol}_{era}'],symbol,era,study.OUT/f'{symbol}_{era}.png')
    pct=lambda x:'—' if x is None else f'{100*x:+.2f}%'
    summary_table=''.join(f'<tr><td>{r["era"]}</td><td>{NAMES[r["arm"]]}</td><td>{r["median_sharpe"]:.3f}</td><td>{pct(r["median_cagr"])}</td><td>{r["median_changes"]:.0f}</td><td>{pct(r["comparisons"][0]["guard_fraction"])}</td></tr>' for r in s if r['cost_bp']==5 and r['delay']==0)
    pool_table=''.join(f'<tr><td>{r["symbol"]}</td><td>{r["era"]}</td><td>{NAMES[r["arm"]]}</td><td>{pct(r["cumulative"])}</td><td>{r["sharpe"]:.3f}</td><td>{pct(r["maxdd"])}</td><td>{r["closed_trades"]}</td><td>{r["changes"]}</td><td>{r["cost_bp_annual"]:.1f}</td></tr>' for r in sorted(primary,key=lambda r:(r['era']!='late',r['symbol'],r['arm'])))
    exports=' · '.join(f'<a href="{symbol}_{era}.png">{symbol} {era} figure</a>' for symbol,era in sorted(focus))
    passed=sum(r['comparisons'][0]['passed'] for r in s if r['arm']=='warning')
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Continuous single-ETF policy learning</title><style>body{font:16px/1.5 system-ui;color:#17384d;background:#f5f8fa;max-width:1280px;margin:34px auto;padding:0 20px}h1,h2{line-height:1.2}h2{margin-top:38px}a{color:#006b70}.note{background:#fff0d7;border-left:4px solid #b47b22;padding:16px}.card{background:white;padding:18px;border:1px solid #d9e3e9;margin:14px 0}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center}button,select,input{font:inherit;padding:7px;border:1px solid #b4c5ce;border-radius:5px;background:white}button{cursor:pointer}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:7px 9px;border-bottom:1px solid #e2e8ed;text-align:right}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}#chart{width:100%;height:auto}#readout{min-height:48px;font-variant-numeric:tabular-nums}.equation{overflow:auto;padding:9px;background:white;margin:5px 0}.equation svg{max-width:100%;height:auto}small{color:#536b7b}</style>
<h1>Learn new trading parameters after losses</h1><p>26 October 2026 · Single ETFs only · 52 supported ETFs · Three algorithms · No portfolio or overlay experiment</p>
<p class="note"><b>Parameters now evolve; warnings no longer impose a health pause.</b> The warning-accelerated algorithm passes the declared full-pool preservation test in __PASSED__ of12 era/friction comparisons. Inspect the measured trade-offs below before treating adaptation as an improvement.</p>
<p>All initial learning states were sealed before evaluation.1,836 ETF/algorithm/cost/delay cases cover2020–2022 and2023–16 October2026. Fees5/10/20bp per side and an extra0/1session execution delay. Every case starts flat and freshly funded, matching the previous loss-feedback experiment. All histories have already been inspected: these are chronological development tests, not untouched prospective evidence.</p>
<h2>The three comparisons</h2><ul><li><b>A — frozen:</b> each ETF's previous training-selected entry, exit and protection parameters.</li><li><b>B — continuous Bayesian learning:</b> nine nearby parameter combinations run in shadow. Their completed net trade outcomes update separate discounted payoff estimates. Adopt a better-scoring combination when its advantage clears the switching margin.</li><li><b>C — warning-accelerated learning:</b> identical to B, but a streak, large loss or losing protective exit reduces the weight of old evidence. New outcomes then have more influence. Warnings do not force a policy change if the evidence still favors the current one.</li></ul>
<p><b>What learns:</b> up-entry confidence, down-exit confidence and initial/trailing protection distance. <b>What stays fixed:</b> the underlying Kalman filters, HMM emissions/transitions, fitted daily volatility scale, and trend/range probability definitions. This is Bayesian learning over a bounded policy grid, not full market-model refitting or a claim of optimal TP/SL. There is no fixed profit target: a rising protective floor or a down-trend signal realizes the gain.</p>
<p>All candidates share correlated market data. Their evidence is kept separate; nine similar winning trades are never counted as nine independent confirmations of one market hypothesis. The Normal reward model and Beta win-rate diagnostic are working approximations, not calibrated probabilities. Actual trades trigger warnings; only shadow outcomes enter the payoff posterior, avoiding double counting. Win rate alone cannot reward many small wins followed by one large loss.</p>
<h2>Inspect any ETF</h2><p id="weakestNote"></p><div class="controls"><label>Era <select id="era"><option value="late">2023–2026</option><option value="early">2020–2022</option></select></label><label>ETF <select id="etf"></select></label><label>Algorithm <select id="arm"><option value="fixed">A · Frozen</option><option value="bayes">B · Continuous learning</option><option value="warning">C · Warning-accelerated</option></select></label><button id="weakest">Weakest C case</button><button id="weat">WEAT</button></div>
<div class="controls"><label>From <input id="from" type="date"></label><label>To <input id="to" type="date"></label><button id="reset">Full context</button></div>
<div class="card"><p id="metrics"></p><small id="parameters"></small><p id="readout">Hover for exact dates and current learned parameters; click two dates to select an interval.</p><svg id="chart" viewBox="0 0 1200 1140"></svg></div>
<details><summary>Actual parameter values for this ETF (policy IDs decoded)</summary><table><tr><th>ID</th><th>Up entry</th><th>Down exit</th><th>Down exit in slow up</th><th>Distance normal</th><th>Distance in slow up</th></tr><tbody id="grid"></tbody></table><p>Distances are multiples of fitted daily return volatility times the entry price. Slow-up columns apply only when the base policy uses context. ID0 is the exact frozen policy.</p></details>
<details><summary>Actual trade ledger</summary><div class="scroll"><table><tr><th>Entry</th><th>Exit</th><th>Entry policy</th><th>Exit policy</th><th>Net return</th><th>Exit reason</th></tr><tbody id="trades"></tbody></table></div></details>
<details><summary>Warnings and dated parameter updates</summary><div class="scroll"><table><tr><th>Known date</th><th>Policy change</th><th>Reason</th><th>Accelerated?</th><th>Payoff mean</th><th>Win estimate</th><th>Effective count</th></tr><tbody id="events"></tbody></table></div><p>Updates use information through the stated close. Orders execute at a later open. Effective counts are discounted weights, not independent sample sizes. A warning inside the20-session cooldown is recorded but does not repeatedly erase evidence.</p></details>
<p>__EXPORTS__</p>
<h2>What this round found</h2><p>Ordinary learning improves later GLD from+56.69% to+88.30% and WEAT from−32.51% to−10.69%, while continuing to trade. Adding warning acceleration gives+85.34% and−18.17% respectively. Those examples support further investigation, but the full-pool result is weaker: median Sharpe falls in both eras and neither learning version passes any of the12 era/friction preservation tests.</p>
<p><b>TLT, the weakest later C case (−24.08%):</b> on22 September2023, the third actual loss accelerates forgetting and switches from policy8 to6. Entry confidence remains0.85, but normal protection shrinks from7.5 to2.5 daily-volatility units. C buys6 November and stops out10 November for+1.23%. B keeps the rebound until5 January2024 for+11.43%; A exits9 January for+11.59%. The up probability has to fall below0.5 to rearm, so C misses the continuing rise. The wider shadow policy's winner only becomes available in January, when C switches back. Completed-trade learning and re-entry design interact badly here. The July–September2024 rebound remains captured for+5.78% by both B and C.</p>
<p><b>PPLT, the weakest earlier C case (−32.56%):</b>30 closed trades,10 winners,24 parameter switches and15 accelerated updates. It remains vulnerable to repeated false rebounds; A loses26.54% and B26.42%. Winning-trade sigma is3.62%, yet some actual losses still exceed it: warning is an update request, not an immediate stop.</p>
<p><b>WEAT's unresolved first losses:</b> all three algorithms still lose6.99% on3–11 January2023 and9.01% on15–27 February. B's later improvement is therefore not evidence that adaptation solved the initial large-loss problem. C continues with15 closed trades and no health pause, compared with the previous pause-based experiment's one trade.</p>
<p><b>Next declared hypotheses:</b> separate a hard risk limit from the learning response; learn entry quality, profit giveback and re-entry separately; update on causal daily marked rewards or predictive errors so unfinished winners are not invisible; condition policy evidence on slow-market context rather than globally forgetting useful history after any losing stop. Retain A and ordinary B as controls. These are proposals for the next experiment, not changes silently fitted to these outcomes. Single-ETF work remains the focus.</p>
<h2>Full-pool comparison</h2><table><tr><th>Era</th><th>Algorithm</th><th>Median Sharpe</th><th>Median CAGR</th><th>Median changes</th><th>Within guards vs A</th></tr>__SUMMARY__</table>
<p>Primary setting:5bp per side, next-open fills, risky ETFs only (51 later/49 earlier). Acceptance requires improved median Sharpe and lower-quartile CAGR, with at least90% of ETFs within1pp CAGR and2pp drawdown of A. Positive results on WEAT alone are insufficient; successful assets must be preserved. Cash earns0. Buy-and-hold purchases at the first evaluation open with the same entry fee and marks the terminal holding without an artificial final sale.</p>
<details><summary>All ETF results</summary><div class="scroll"><table><tr><th>ETF</th><th>Era</th><th>Algorithm</th><th>Net return</th><th>Sharpe</th><th>Drawdown</th><th>Closed trades</th><th>Changes</th><th>Cost bp/year</th></tr>__POOL__</table></div></details>
<h2>Exact learning and execution rules</h2>__EQUATIONS__
<p>The prior for each normalized payoff mean is Normal(0,1/4). Each completed shadow trade contributes one unit-variance likelihood, discounted over time. Training evidence is recency-weighted and capped at four effective trades. A candidate needs at least one newly closed evaluation trade before it can replace the baseline. D is held trading sessions, sigma is the ETF's training daily log-return standard deviation. Clipping limits posterior influence; actual P&amp;L is never clipped.</p>
<p>Warning conditions: the3rd or4th consecutive actual net loss; an actual realized loss below−tau; the first close-marked loss below−tau in a position; or a negative protective exit. Tau=max(training winner-return sample SD,2×fee,10⁻⁶), requiring at least5training winners; otherwise the sigma warning is unavailable. Accelerated forgetting multiplies old sufficient statistics by0.25 before adding newly closed trades, at most once per20sessions. The choice of126-session decay,20-session cooldown and switching margin was fixed before this evaluation. These are explicit adaptation settings, not learned market timescales.</p>
<p>Buy if armed, fast-up probability exceeds the current entry threshold, and fast slope is positive. Rearm when fast-up probability falls below0.5. Exit on the down-probability threshold or a close below the previously adopted protective floor. Price levels only tighten. A change may affect the current position's future exit decisions, but cannot alter an already queued order. The resulting hybrid path is distinct from any one candidate's shadow path. A marked-loss warning is an update request, not itself an emergency liquidation rule; it can therefore fail to prevent the first large loss.</p>
<p>Limitations: sparse completed trades can make learning slow; a positive short-trade payoff does not necessarily maximize calendar return; win probabilities are not independent of magnitude estimates; serial dependence, model misspecification and a fixed candidate grid remain. Raw audited volume is inspection context only in this experiment. Prices use the pinned dividend/split-adjusted publication; historical publication-vintage availability remains limited. No new provider prices, synthetic fills at stops, or retrospective peak exits.</p>
<p>Verification:16 focused Python tests,612 fixed-policy matches (maximum NAV error8.9×10⁻¹⁵), independent cash/share reconstruction and306 offline chart combinations. Three single-ETF native Windows LEAN executions match the application whole-unit reference exactly. Those executions use application sizing and cent-quantized prices, so they are not exact reproductions of fractional research NAV: GLD with one extra delay session changes from+114.29% to+113.17%, WEAT from−18.17% to−18.08%, TLT from−24.08% to−24.01%. Native replay validates execution of frozen signals, not the online learning logic independently. Browser layout certification is not claimed.</p>
<p>Method background: <a href="https://arxiv.org/abs/2305.10718">discounted Bayesian learning under nonstationarity</a> and <a href="https://proceedings.mlr.press/v206/liu23e.html">why old information can lose usefulness</a>. Our deterministic full-information shadow-policy learner is not either paper's Thompson-sampling algorithm; their theoretical guarantees do not transfer to this backtest.</p>
<p><a href="asset-results.json">All1,836 results, costs and yearly returns</a> · <a href="summary.json">All friction comparisons</a> · <a href="initial.json">Training learning states</a> · <a href="protocol.json">Frozen recipe</a> · <a href="validation.json">Accounting checks</a> · <a href="native-checks.json">Native execution checks</a> · <a href="../../docs/online-policy-results-2026-10-26.md">Findings and next research</a></p>
<script>const DATA = __DATA__;
__SCRIPT__</script></html>'''
    # Display rounding only; calculations and compressed audit arrays retain full precision.
    def display(obj):
        if isinstance(obj,float):return round(obj,7)
        if isinstance(obj,list):return [display(x) for x in obj]
        if isinstance(obj,dict):return {k:display(v) for k,v in obj.items()}
        return obj
    payload=display(dict(charts=charts,rows=primary,weakest=weakest))
    script=study.ROOT/'scripts/assets/online-policy-script.js'
    for token,value in dict(PASSED=str(passed),EXPORTS=exports,SUMMARY=summary_table,POOL=pool_table,EQUATIONS=equations(),
                            DATA=json.dumps(payload,separators=(',',':')).replace('</','<\\/'),SCRIPT=script.read_text(encoding='utf-8')).items():
        html=html.replace('__'+token+'__',value)
    (study.OUT/'index.html').write_text(html,encoding='utf-8');study.write(study.OUT/'weakest-cases.json',weakest)
    study.write(study.OUT/'manifest.json',dict(files={p.name:study.prior.study.digest(p) for p in study.OUT.iterdir() if p.is_file() and p.name!='manifest.json'},
        report_code={str(p.relative_to(study.ROOT)).replace(chr(92),'/'):study.prior.study.digest(p) for p in (__import__('pathlib').Path(__file__),script)}))
    print(json.dumps(dict(charts=len(charts)*3,weakest={e:r['symbol'] for e,r in weakest.items()},passing_cases=passed)))


if __name__=='__main__':main()
