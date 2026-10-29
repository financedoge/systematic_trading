"""Three main algorithms, every ETF chart, explicit execution assumptions."""
import gzip
from io import BytesIO
import json
from pathlib import Path
import re
import numpy as np
import research_stop_review as study

NAMES={'baseline':'B0 · Original B','stop':'B1 · Standing stop','review':'B2 · Stop + exit review + learning'}
COLORS={'baseline':'#8b9caa','stop':'#c98a21','review':'#008675'}


def figure(c,symbol,era,path,limits=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    days=np.array(c['days'],dtype='datetime64[D]');a=c['arms']['review'];fig,axes=plt.subplots(6,1,figsize=(15,13),sharex=True,layout='constrained',height_ratios=[2.3,.6,.8,.65,.6,1.3])
    axes[0].plot(days,c['close'],color='#173d54',lw=1,label='Adjusted close')
    mask=np.ones(len(days),bool) if not limits else (days>=np.datetime64(limits[0]))&(days<=np.datetime64(limits[1]))
    axes[0].vlines(days[mask],np.asarray(c['low'])[mask],np.asarray(c['high'])[mask],color='#91a3ae',alpha=.6,lw=.8,label='Daily high / low')
    axes[0].plot(days,np.asarray(a['stop'],float),color='#b64f61',label='B2 active stop')
    for e in a['fills']:
        if limits and not limits[0]<=e['day']<=limits[1]:continue
        buy=e['side']=='buy';recovery=any(t['entry_date']==e['day'] and t.get('entry_reason')=='exit_review' for t in a['trades'])
        axes[0].scatter(np.datetime64(e['day']),e['price'],marker='^' if buy else 'v',color=('#d58b20' if recovery else '#008675') if buy else '#b64f61',s=35,zorder=5)
    axes[0].legend(fontsize=8,ncol=3);axes[0].set_ylabel('Adjusted USD')
    axes[1].bar(days,np.asarray(c['volume'])/1e6,color='#9aabb6');axes[1].set_ylabel('Raw volume (m)')
    for k,label,color in [('fast_up','Up','#008675'),('neutral','Neutral','#b09a52'),('fast_down','Down','#b64f61')]:axes[2].plot(days,c[k],label=label,color=color)
    axes[2].legend(fontsize=8,ncol=3);axes[2].set_ylim(0,1);axes[2].set_ylabel('Fast HMM')
    for k,label,color in [('slow_up','Slow up','#008675'),('slow_down','Slow down','#b64f61')]:axes[3].plot(days,c[k],label=label,color=color)
    axes[3].legend(fontsize=8,ncol=2);axes[3].set_ylim(0,1)
    for k,label,color in [('policy','Policy 0 original / 1 faster / 2 patient','#173d54'),('review_signal','Exit reversed','#d58b20'),('reset','Memory reset','#b64f61')]:axes[4].plot(days,np.asarray(a[k],float),label=label,color=color)
    axes[4].legend(fontsize=8,ncol=3);axes[4].set_ylim(-.05,2.1)
    for arm in study.model.ARMS:axes[5].plot(days,np.asarray(c['arms'][arm]['nav'],float),label=NAMES[arm],color=COLORS[arm])
    axes[5].legend(fontsize=8);axes[5].set_ylabel('NAV / initial 100')
    for ax in axes:ax.grid(alpha=.15)
    if limits:
        axes[-1].set_xlim(np.datetime64(limits[0]),np.datetime64(limits[1]))
        vals=[c[k][i] for i in np.flatnonzero(mask) for k in ('low','high')]+[a['stop'][i] for i in np.flatnonzero(mask) if a['stop'][i] is not None]
        low,high=min(vals),max(vals);axes[0].set_ylim(low-(high-low)*.06,high+(high-low)*.06)
    else:axes[-1].set_xlim(np.datetime64(c['evaluation_start']),days[-1])
    axes[-1].xaxis.set_major_locator(dates.AutoDateLocator());axes[-1].xaxis.set_major_formatter(dates.DateFormatter('%Y-%m-%d'))
    fig.suptitle(f'{symbol} | {era} | B2 standing stop, exit reassessment and policy learning\nGreen buy / red sell; orange buy reverses a prior exit. 5 bp fee/side + 5 bp stop slippage; next-open signals.')
    fig.savefig(path,dpi=120);plt.close(fig)


def equations():
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    import matplotlib.pyplot as plt
    formulas=[
      r'x_t=b^f_t/\sigma,\quad f_D=N(-a,v),\quad f_R=N(0,v_R),\quad f_U=N(a,v),\quad \log(f_U/f_D)=2ax_t/v',
      r'p_t(s)\propto f_s(x_t)\sum_j p_{t-1}(j)A_{js},\quad \mathrm{entry}=\{p_{U,t}\geq e_j,\ b^f_t>0,\ \mathrm{armed}\}',
      r'\mathrm{armed}\leftarrow 1\ \mathrm{when}\ p_{U,t}<r;\quad d_{j,t}=d^{wide}_j\ \mathrm{if}\ p^s_{U,t}\geq0.7\ \mathrm{and\ context},\ \mathrm{else}\ d^{tight}_j',
      r'R=O_{entry}\sigma,\quad S_{entry}=O_{entry}-d_{j,signal}R,\quad S_{t+1}=\max(S_t,\max(O_{entry},C_{entry},\ldots,C_t)-d_{j,t}R)',
      r'B0:\ C_t<S_t\Rightarrow\mathrm{sell\ at}\ O_{t+1+delay};\qquad B1,B2:\ L_t\leq S_t\Rightarrow F_t=\min(O_t,S_t)(1-s)',
      r'\mathrm{trade\ return}=\frac{F_{exit}(1-f)}{O_{entry}(1+f)}-1,\quad f\in\{0.0005,0.001,0.002\},\quad s=0.0005',
      r'TR_t=\max(H_t-L_t,|H_t-C_{t-1}|,|L_t-C_{t-1}|),\quad ATR_t=ATR_{t-1}+(TR_t-ATR_{t-1})/20',
      r'VP_t=\frac{\sum_{i=t-2}^{t}\mathrm{sign}(C_i-C_{i-1})V_i}{\sum_{i=t-2}^{t}V_i},\quad CL_t=\frac{C_t-L_t}{H_t-L_t}',
      r'\mathrm{recover}:\quad 1\leq t-t_x\leq10,\quad F_x(1+2f)\leq C_t\leq F_x+ATR_{signal(x)}',
      r'p_{U,t}\geq0.55,\ p_{D,t}\leq0.35,\ (b^f_t>0\ \mathrm{or}\ b^f_t>b^f_{t-1}),\ C_t>\max(C_{t-1},O_t),\ CL_t\geq0.6,\ VP_t\geq0',
      r'j\in\{0,1,2\}:\quad(\Delta_j,\lambda_j,\kappa_j)=(0,1,0),\ (-0.05,0.75,-1),\ (0.05,1.25,1)',
      r'e_j=\mathrm{clip}(e+\Delta_j,0.5,0.9),\quad q_j=\mathrm{clip}(q+\Delta_j,0.45,0.9),\quad q^a_j=\mathrm{clip}(q^a+\Delta_j,0.65,0.95)',
      r'd_j=\lambda_j d,\quad k_j=\max(1,k+\kappa_j),\quad y_{j,t}=\frac{NAV^{shadow}_{j,t}/NAV^{shadow}_{j,t-1}-1}{\sigma}',
      r'\rho=2^{-1/63},\quad n_t=\rho n_{t-1}+1,\quad s_{j,t}=\rho s_{j,t-1}+y_{j,t},\quad \mu_{j,t}=\frac{s_{j,t}}{4+n_t}',
      r'\mathrm{warning}:\quad n_t\leftarrow\sum_{i=\max(t_0+1,t-20)}^t\rho^{t-i},\quad s_{j,t}\leftarrow\sum_{i=\max(t_0+1,t-20)}^t\rho^{t-i}y_{j,i}',
      r'j^*=\arg\max_j\mu_{j,t};\quad \mathrm{switch\ if}\ \mu_{j^*,t}>\mu_{current,t}+0.02\ \mathrm{and\ flat\ with\ no\ pending\ order}',
      r'\mathrm{warning}=\mathrm{exit\ reversed}\ \vee\ \{r_{trade}<0,\ duration\leq10\}\ \vee\ \{loss\ streak\in\{3,4\}\}\ \vee\ \{r_{trade}<-\max(\tau,2f)\}',
      r'\tau=\mathrm{sd}(positive\ training\ trade\ returns)\ \mathrm{if}\ n_{wins}\geq3;\quad \tau=\sigma\sqrt{21}\ \mathrm{otherwise}',
      r'IC_5=\mathrm{Spearman}(p_{U,t}-p_{D,t},\ O_{t+6+delay}/O_{t+1+delay}-1)'
    ]
    parts=[]
    for j,formula in enumerate(formulas):
        buf=BytesIO();mathtext.math_to_image('$'+formula+'$',buf,prop=FontProperties(size=13),format='svg',color='#17384d');svg=buf.getvalue().decode();svg=svg[svg.index('<svg'):]
        svg=re.sub(r'id="([^"]+)"',lambda m:f'id="eq{j}_{m[1]}"',svg);svg=re.sub(r'xlink:href="#([^"]+)"',lambda m:f'xlink:href="#eq{j}_{m[1]}"',svg);parts.append('<div class="equation">'+svg+'</div>')
    fig,axes=plt.subplots(len(formulas),1,figsize=(22,18),layout='constrained')
    for ax,formula in zip(axes,formulas):ax.axis('off');ax.text(.01,.3,'$'+formula+'$',fontsize=12)
    fig.savefig(study.OUT/'equation-proof.png',dpi=95,bbox_inches='tight');plt.close(fig);study.write(study.OUT/'equations.json',formulas)
    return ''.join(parts)


def main():
    receipt=json.loads((study.OUT/'validation.json').read_text());assert study.prior.study.digest(study.OUT/'chart-data.json.gz')==receipt['chart_sha256']
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()));rows=json.loads((study.OUT/'asset-results.json').read_text());sums=json.loads((study.OUT/'summary.json').read_text());weakest=json.loads((study.OUT/'weakest-cases.json').read_text())
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0];lookup={(r['symbol'],r['era'],r['arm']):r for r in primary}
    pct=lambda x:'—' if x is None else f'{100*x:+.2f}%';fmt=lambda x:'—' if x is None else f'{x:.3f}'
    focus={('CPER','late'),('IWM','late'),('WEAT','late'),('GLD','late'),('TLT','late'),*((r['symbol'],e) for e,r in weakest.items())}
    for s,e in sorted(focus):figure(charts[s+'_'+e],s,e,study.OUT/f'{s}_{e}.png')
    figure(charts['CPER_late'],'CPER','late',study.OUT/'CPER-incident.png',('2025-03-04','2025-09-04'));figure(charts['IWM_late'],'IWM','late',study.OUT/'IWM-incident.png',('2024-07-01','2024-12-01'))
    table=lambda heads,body:'<div class="scroll"><table><tr>'+''.join('<th>'+h+'</th>' for h in heads)+'</tr>'+body+'</table></div>'
    st=''.join(f'<tr><td>{r["era"]}</td><td>{NAMES[r["arm"]]}</td><td>{fmt(r["median_sharpe"])}</td><td>{pct(r["median_cagr"])}</td><td>{pct(r["guard_fraction"])}</td><td>{r["improved"]}/{r["worse"]}</td><td>{r["median_annual_cost_bp"]:.1f}</td></tr>' for r in sums if r['cost_bp']==5 and r['delay']==0 and r['arm'] in NAMES)
    pt=''
    for era,*_ in study.ERAS:
        for r in sorted((r for r in primary if r['era']==era and r['arm']=='review'),key=lambda r:r['cumulative']):
            b,s=lookup[r['symbol'],era,'baseline'],lookup[r['symbol'],era,'stop']
            pt+=f'<tr><td>{r["symbol"]}</td><td>{era}</td><td>{pct(b["cumulative"])}</td><td>{pct(s["cumulative"])}</td><td>{pct(r["cumulative"])}</td><td>{fmt(r["sharpe"])}</td><td>{fmt(r["calmar"])}</td><td>{pct(-r["maxdd"])}</td><td>{fmt(r["ic5"])}</td><td>{r["closed_trades"]}</td><td>{r["recovery_wins"]}/{r["recovery_closed"]}</td></tr>'
    component_names={'recovery_fixed':'Standing stop + recovery, no learning','learning_no_reset':'Stop + recovery + learning, no warning reset','conditional_touch_close':'Low touched, same close fill — unverified execution','stop_slip20':'Standing stop, 20 bp extra slip','stop_slip50':'Standing stop, 50 bp extra slip','conservative_stop':'Standing stop at min(open, level, close)'}
    dt=''.join(f'<tr><td>{r["era"]}</td><td>{component_names[r["arm"]]}</td><td>{fmt(r["median_sharpe"])}</td><td>{pct(r["median_cagr"])}</td><td>{pct(r["guard_fraction"])}</td></tr>' for r in sums if r['cost_bp']==5 and r['delay']==0 and r['arm'] in component_names)
    stress=''.join(f'<tr><td>{r["era"]}</td><td>{r["cost_bp"]}</td><td>{r["delay"]}</td><td>{NAMES[r["arm"]]}</td><td>{fmt(r["median_sharpe"])}</td><td>{pct(r["median_cagr"])}</td><td>{pct(r["guard_fraction"])}</td><td>{"Pass" if r["passed"] else "Fail"}</td></tr>' for r in sums if r['arm'] in ('stop','review'))
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Faster stops and reviewing exits</title>
<style>body{font:16px/1.5 system-ui;color:#17384d;background:#f5f8fa;max-width:1320px;margin:34px auto;padding:0 20px}h1,h2{line-height:1.2}h2{margin-top:38px}a{color:#006b70}.note{background:#fff0d7;border-left:4px solid #b47b22;padding:16px}.card{background:white;padding:18px;border:1px solid #d9e3e9;margin:14px 0}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center}button,select,input{font:inherit;padding:7px;border:1px solid #b4c5ce;border-radius:5px;background:white}button{cursor:pointer}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:7px 9px;border-bottom:1px solid #e2e8ed;text-align:right}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}#chart{width:100%;height:auto}#readout{min-height:72px;position:sticky;top:0;background:#fff9e9;padding:10px;z-index:2}.equation{overflow:auto;padding:9px;background:white;margin:5px 0}.equation svg{max-width:100%;height:auto}small{color:#536b7b}</style>
<h1>Faster stops and reviewing exits</h1><p>27 October 2026 · B selected as research baseline · Full supported ETF pool</p>
<p class="note">Research simulations on repeatedly inspected development periods. Standing-stop prices are modeled from daily OHLC, not observed intraday executions. Same-day closing-auction results are conditional estimates. No strategy promotion or live changes.</p>
<ul><li><b>B0 — original B:</b> symmetric directional HMM, fixed trading policy, close-based protection with next-open execution.</li><li><b>B1 — standing stop:</b> retain B's stop distance and trend rules; activate protection before the next session, including gap handling. 5 bp extra stop slippage.</li><li><b>B2 — stop, exit review and learning:</b> B1 plus a near-exit price/volume recovery rule and adaptive choice among original, faster/tighter and more patient/wider policies. A reversed decision or loss warning shortens policy memory.</li></ul>
__FINDINGS__
<h2>Inspect every ETF</h2><p id="weakestNote"></p><div class="controls"><label>Era <select id="era"><option value="late">2023–2026</option><option value="early">2020–2022</option></select></label><label>ETF <select id="etf"></select></label><label>Algorithm <select id="arm"><option value="baseline">B0 · Original B</option><option value="stop">B1 · Standing stop</option><option value="review">B2 · Exit review + learning</option></select></label><button id="weakest">Weakest B2 in era</button><button id="weat">WEAT</button><button id="tlt">TLT rebounds</button></div>
<div class="controls"><label>From <input id="from" type="date"></label><label>To <input id="to" type="date"></label><button id="reset">Full evaluation</button><button id="cper">CPER · Mar–Sep 2025</button><button id="iwm">IWM · Jul–Dec 2024</button></div>
<div class="card"><p id="metrics"></p><p id="dependence"></p><p id="learning"></p><p id="window"></p><p id="readout">Hover for a date, OHLC, modeled fill and stop. Click two dates to zoom.</p><svg id="chart" viewBox="0 0 1200 1350"></svg></div>
<details open><summary>Trades overlapping the selected interval</summary><div class="scroll"><table><tr><th>Buy date</th><th>Sell date</th><th>Buy → sell price</th><th>Buy reason</th><th>Policy</th><th>Whole-trade return</th><th>Initial stop distance</th><th>Sell reason</th></tr><tbody id="trades"></tbody></table></div><p>Trade return covers its full life, even if the trade crosses a selected date boundary. The interval return above measures marked account P&amp;L strictly over your dates.</p></details>
<details><summary>Warnings, resets and policy changes in selected interval</summary><table><tr><th>Date</th><th>Reason</th><th>Evidence reset</th><th>Policy</th></tr><tbody id="events"></tbody></table></details>
<details><summary>Per-ETF training fits and explicit policy parameters</summary><pre id="fitparameters" style="overflow:auto"></pre></details><p>__EXPORTS__</p>
<h2>Pool outcomes</h2>__SUMMARY__
<p>Primary 5 bp per side, next-open signals, plus 5 bp slippage on standing stops. 51 risky ETFs in 2023–2026 and 49 in 2020–2022; BIL is displayed separately. Medians across individual ETF strategies are not a portfolio return. Guards require each ETF within 1 percentage point CAGR and 2 points maximum drawdown of B0. Acceptance requires ≥90% within guards plus higher median Sharpe and lower-quartile CAGR.</p>
<details><summary>Every cost and signal-delay comparison</summary>__STRESS__<p>An extra session delay affects trend/recovery orders. It does not delay a protective stop already resting in the market.</p></details>
<details open><summary>Full ETF table — weakest B2 first, separately for each era</summary>__POOL__</details>
<h2>What contributed, and execution sensitivity</h2><p>These diagnostics isolate components; they are not extra recommended algorithms. The same-close diagnostic uses B1's fixed policy without recovery or learning. The 20/50 bp slippage and conservative-fill diagnostics also stress B1.</p>__COMPONENTS__
<h2>Mathematical definition</h2>__EQUATIONS__
<p>O/H/L/C are dividend/split-adjusted daily prices; V is audited raw ETF share volume. σ is the frozen training daily log-return dispersion. Fast/slow levels and slopes come from the inherited causal local-linear filters. p are filtered model scores, not calibrated probabilities that a trade will profit. The symmetric HMM and its per-ETF training fits are unchanged from <a href="../entry-value-20261027-v1/index.html">the previous B</a>. This round updates trading-policy evidence, not HMM emissions, transition matrices or Kalman noise parameters.</p>
<p>The inherited trend exit is pDown ≥ q (or qᵃ in qualifying slow-up context). Thesis exit requires pUp below the selected floor for k consecutive closes and fast slope ≤0; strong slow-up halves the floor and adds two closes. The three policies change k by −1/0/+1 and change thresholds/distances exactly as above. Rearming threshold r is inherited (normally 0.5). Once a position is held, its policy remains fixed and its trailing stop cannot loosen. A context change can tighten the next session's stop; it never changes the stop already tested during today's bar.</p>
<p>A recovery requires <em>all</em> displayed conditions. It can reverse a protection, trend or thesis exit, but only after a later completed session and with no pending order or held position. It bypasses the ordinary rearm/entry threshold. ATR is measured at the exit signal's close and then frozen for that review; zero-range bars have close location 0.5. The next-open fill may gap outside the recovery band; no unmodeled limit-order guarantee is assumed.</p>
<p>Three hypothetical fixed-policy accounts include the same recovery rule and matched frictions. Their daily net returns, fully observed by the current close, update all policy estimates even when the actual account is in cash. The working Gaussian model has prior precision 4 and unit variance for normalized daily reward. Shared counts make a common 0.25 posterior-standard-deviation penalty cancel when ranking. Correlated returns and hypothetical policies do not produce calibrated confidence intervals. Policy changes require five sessions since the previous change unless a warning occurs; a warning permits reassessment but does not force a switch.</p>
<p>Training calibration replays the final 756 returns using full-training B fits. Initial evidence is discounted with half-life 63 sessions and capped at weight 20. This is fitted training calibration, not nested validation. The large-loss threshold uses dispersion of positive completed training trades (fallback shown per ETF). A warning discards older evidence and replays at most 21 completed evaluation observations with the same discount; the proper neutral prior remains. Thus it keeps recent evidence rather than becoming an empty, nontrading system. No threshold was fitted to the displayed CPER/IWM intervals.</p>
<h2>Execution and data limits</h2>
<p>The standing stop uses the pre-existing level: if low touches it, fill at min(open, stop) less slippage. This is the standard kind of daily-bar approximation described by <a href="https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/trade-fills/supported-models/equity-model">QuantConnect's equity fill model</a>. It handles opening gaps; it cannot reveal liquidity, spread, intraday jumps or the exact path through the daily bar. A stop can also be touched on the opening entry day. Scheduled opening exits execute before an intraday test, and protective exits cancel stale pending orders.</p>
<p>“Touch then sell at today's close” uses a full-bar low that may become known after a venue's auction cutoff. <a href="https://www.nyse.com/trade/auctions">NYSE auction rules</a> specify order deadlines, which differ by venue/order type. Without intraday timestamps and the relevant venue's order rules, that curve is only conditional—not an executable backtest claim. The conservative min(open, stop, close) stress is a deliberately adverse model, not a guaranteed lower bound on real fills.</p>
<p>Returns use fractional cash-funded shares, per-side fees, zero cash interest and terminal marking without forced sale. Fees and modeled stop slippage are both included in net returns. Full pool uses the pinned published audited histories through 2026-10-16 (batch 5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd); OHLC geometry and raw-volume coverage were checked. No downloaded provider archives or web prices entered this research. Audit does not establish historical publication vintages.</p>
<p>Correlation, beta and annual arithmetic regression intercept use daily strategy versus ETF returns with zero cash rate; HAC(5) t values and overlapping five-session IC are descriptive. Raw-state IC is shared across all three arms because their detector is identical. Lower correlation alone is not evidence of better trading.</p>
<p>Independent accounting reconstructs every fill, including multiple fills in one day. Native Windows LEAN checks serialize each frozen fill and close mark on an explicitly synthetic event calendar to validate ordering, fees, whole-unit sizing and NAV. These are accounting fixtures—not substituted research price histories or independent validation of intraday stop executability. No production contract is weakened.</p>
<p><a href="protocol.json">Frozen protocol</a> · <a href="fits.json">Training calibration</a> · <a href="asset-results.json">Full metrics</a> · <a href="summary.json">Pool and sensitivity results</a> · <a href="incident-audit.json">CPER/IWM daily-bar audit</a> · <a href="attribution.json">ETF changes</a> · <a href="validation.json">Accounting checks</a> · <a href="native-checks.json">Native event checks</a></p>
<script>const DATA = __DATA__;
__SCRIPT__</script></html>'''
    exports=' · '.join(f'<a href="{s}_{e}.png">{s} {e} chart</a>' for s,e in sorted(focus))+' · <a href="CPER-incident.png">CPER selected interval</a> · <a href="IWM-incident.png">IWM selected interval</a>'
    def display(x):
        if isinstance(x,float):return round(x,7)
        if isinstance(x,list):return [display(v) for v in x]
        if isinstance(x,dict):return {k:display(v) for k,v in x.items()}
        return x
    script=study.ROOT/'scripts/assets/stop-review-script.js'
    vals=dict(FINDINGS=(study.OUT/'findings.html').read_text(encoding='utf-8'),EXPORTS=exports,EQUATIONS=equations(),
        SUMMARY=table(['Era','Algorithm','Median Sharpe','Median CAGR','Within B0 guards','Better/worse ETF return','Fees + slip bp/yr'],st),
        POOL=table(['ETF','Era','B0 return','B1 return','B2 return','B2 Sharpe','B2 Calmar','B2 drawdown','Raw IC5','B2 trades','Recovery wins/closed'],pt),
        COMPONENTS=table(['Era','Diagnostic','Median Sharpe','Median CAGR','Within B0 guards'],dt),
        STRESS=table(['Era','Fee bp/side','Extra signal delay','Algorithm','Median Sharpe','Median CAGR','Within guards','Acceptance'],stress),
        DATA=json.dumps(display(dict(charts=charts,rows=primary,weakest=weakest)),separators=(',',':')).replace('</','<\\/'),SCRIPT=script.read_text(encoding='utf-8'))
    for token,value in vals.items():html=html.replace('__'+token+'__',value)
    (study.OUT/'index.html').write_text(html,encoding='utf-8')
    files=[Path(__file__),script,study.ROOT/'scripts/analyze_stop_review.py',study.ROOT/'scripts/validate_stop_review.py',study.ROOT/'tests/stop_review_controls.cjs',study.ROOT/'tests/test_stop_review_contract.py']
    study.write(study.OUT/'manifest.json',dict(files={p.name:study.prior.study.digest(p) for p in study.OUT.iterdir() if p.is_file() and p.name!='manifest.json'},report_code={p.relative_to(study.ROOT).as_posix():study.prior.study.digest(p) for p in files if p.exists()}))
    print('Built',len(charts)*3,'main chart combinations')


if __name__=='__main__':main()
