"""Readable formulas, every ETF chart, and focused failure inspection."""
import gzip
from io import BytesIO
import json
from pathlib import Path
import re
import numpy as np
import research_entry_value as study
import build_regime_entry_report as template
template.study=study
NAMES={'control':'A: original detector / fixed policy','hmm':'B: symmetric directional HMM','value':'C: B plus online entry value'}


def figure(c,symbol,era,path,limits=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    days=np.array(c['days'],dtype='datetime64[D]');a=c['arms']['value'];active=days>=np.datetime64(c['evaluation_start'])
    fig,axes=plt.subplots(7,1,figsize=(14,15),sharex=True,layout='constrained',height_ratios=[2,.5,.8,.6,.9,.5,1.4])
    axes[0].plot(days,c['close'],color='#173d54',label='Adjusted close');axes[0].plot(days,np.asarray(a['stop'],float),color='#bd5260',label='Protection')
    for e in a['trades']:
        x=np.datetime64(e['entry_date']);y=np.datetime64(e['exit_date']) if e['exit_date'] else days[-1]
        axes[0].axvspan(x,y,color='#008675',alpha=.07);axes[0].scatter(x,e['entry'],color='#008675',marker='^',s=30)
        if e['exit_date']:axes[0].scatter(y,e['exit_price'],color='#bd5260',marker='v',s=30)
    axes[0].legend(fontsize=8);axes[0].set_ylabel('Adjusted USD')
    axes[1].bar(days,np.asarray(c['volume'],float)/1e6,color='#9aabb6',width=1.5);axes[1].set_ylabel('Raw volume (m)')
    for key,label,color in [('fast_up','Up','#008675'),('neutral','Range','#b39b50'),('fast_down','Down','#bd5260')]:axes[2].plot(days,np.asarray(a[key],float),color=color,label=label)
    axes[2].set_ylabel('Fast HMM');axes[2].legend(fontsize=8,ncol=3);axes[2].set_ylim(0,1)
    for key,label,color in [('slow_up','Slow up','#008675'),('slow_down','Slow down','#bd5260')]:axes[3].plot(days[active],np.asarray(c[key])[active],color=color,label=label)
    axes[3].legend(fontsize=8,ncol=2);axes[3].set_ylim(0,1)
    for key,label,color in [('predicted_return','Forecast return','#008675'),('predicted_downside','Forecast sampled adverse movement','#bd5260'),('utility','Entry utility after cost / risk penalty','#294eab')]:axes[4].plot(days,100*np.asarray(a[key],float),color=color,label=label)
    axes[4].axhline(0,color='#888',lw=.6);axes[4].legend(fontsize=8,ncol=2);axes[4].set_ylabel('Log return (%)')
    for key,label,color in [('gate','Gate passes (up signal still required)','#008675'),('blocked','Funded eligible entry rejected','#bd5260')]:axes[5].plot(days,np.asarray(a[key],float),color=color,label=label)
    axes[5].legend(fontsize=8,ncol=2);axes[5].set_ylim(-.05,1.05)
    for name,color in [('control','#91a3b0'),('hmm','#c78b28'),('value','#008675')]:axes[6].plot(days,np.asarray(c['arms'][name]['nav'],float),color=color,label=NAMES[name])
    axes[6].legend(loc='upper left',fontsize=8);axes[6].set_ylabel('NAV / initial 100')
    for ax in axes:ax.grid(alpha=.15);ax.axvline(np.datetime64(c['evaluation_start']),color='#777',ls='--',lw=.7)
    axes[6].xaxis.set_major_locator(dates.MonthLocator(interval=6));axes[6].xaxis.set_major_formatter(dates.DateFormatter('%Y-%m'))
    q=c['selection'];fig.suptitle(f'{symbol} | {era} | C: symmetric HMM and online entry value\n{q["forecast"]["kind"]} forecast; memory half-life {q["forecast"]["memory"]} sessions; horizon {q["horizon"]} sessions; risk penalty 0.25')
    if limits:
        axes[-1].set_xlim(np.datetime64(limits[0]),np.datetime64(limits[1]))
        axes[-1].xaxis.set_major_locator(dates.AutoDateLocator())
        axes[-1].xaxis.set_major_formatter(dates.DateFormatter('%Y-%m-%d'))
    fig.savefig(path,dpi=130);plt.close(fig)


def equations():
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    import matplotlib.pyplot as plt
    formulas=[r'x_t=b^{fast}_t/\sigma,\quad f_D=N(-a,v),\quad f_R=N(0,v_R),\quad f_U=N(a,v)',
        r'0.2\leq a\leq2,\quad0.01\leq v\leq4,\quad0.000025\leq v_R\leq0.01,\quad\log\frac{f_U(x)}{f_D(x)}=\frac{2ax}{v}',
        r'p_t(s)=\frac{f_s(x_t)\sum_jp_{t-1}(j)A_{js}}{\sum_k f_k(x_t)\sum_jp_{t-1}(j)A_{jk}},\quad 0.65\leq A_{ss}\leq0.98',
        r'H=\operatorname{clip}\left(\operatorname{round}\left(1/(1-A^{prefix}_{UU})\right),5,21\right)',
        r'R_i=\log(O_{i+H+1}/O_{i+1}),\quad D_i=\max\left(0,-\min_{P\in\mathcal{P}_i}\log(P/O_{i+1})\right)',
        r'\mathcal{P}_i=\{O_{i+1},\ldots,O_{i+H+1},C_{i+1},\ldots,C_{i+H}\},\quad Y_i=(R_i,D_i)/(\sigma\sqrt{H})',
        r'\phi_t=(1,p_U-p_D,p_R,b_f/\sigma,b_s/\sigma,(\log C-\ell_f)/\sigma,(\log C-\ell_s)/\sigma,p^s_U-p^s_D,p_Up^s_D,\log(V/\overline{V}))',
        r'\overline{V}_t=\overline{V}_{t-1}+\frac{2}{64}(V_t-\overline{V}_{t-1}),\quad \rho=2^{-1/L},\quad L\in\{63,252\}',
        r'i=t-H-1:\quad S_t=\rho S_{t-1}+\phi_i\phi_i^T/H,\quad B_t=\rho B_{t-1}+\phi_iY_i/H',
        r'\widehat{Y}_t=\phi_t^T(4I+S_t)^{-1}B_t,\quad (\widehat{R}_t,\widehat{D}_t)=\sigma\sqrt{H}\,\widehat{Y}_t,\quad\widehat{D}_t\leftarrow\max(0,\widehat{D}_t)',
        r'U_t=\widehat{R}_t-\log\left(\frac{1+f}{1-f}\right)-0.25\widehat{D}_t,\quad \mathrm{enter}_C=\mathrm{eligible}_B\ \mathrm{and}\ U_t>0',
        r'\mathrm{validation\ loss}=\frac{\operatorname{MSE}(\widehat{R},R)+0.5\operatorname{MSE}(\widehat{D},D)}{\sigma_{prefix}^2H}']
    parts=[]
    for j,formula in enumerate(formulas):
        buf=BytesIO();mathtext.math_to_image('$'+formula+'$',buf,prop=FontProperties(size=14),format='svg',color='#17384d');svg=buf.getvalue().decode();svg=svg[svg.index('<svg'):]
        svg=re.sub(r'id="([^"]+)"',lambda m:f'id="eq{j}_{m[1]}"',svg);svg=re.sub(r'xlink:href="#([^"]+)"',lambda m:f'xlink:href="#eq{j}_{m[1]}"',svg)
        parts.append('<div class="equation">'+svg+'</div>')
    study.write(study.OUT/'equations.json',formulas)
    fig,axes=plt.subplots(len(formulas),1,figsize=(20,13),layout='constrained')
    for ax,formula in zip(axes,formulas):ax.axis('off');ax.text(.01,.3,'$'+formula+'$',fontsize=12)
    fig.savefig(study.OUT/'equation-proof.png',dpi=110,bbox_inches='tight');plt.close(fig)
    return ''.join(parts)


def main():
    study.verified();receipt=json.loads((study.OUT/'validation.json').read_text())
    assert study.prior.study.digest(study.OUT/'chart-data.json.gz')==receipt['chart_sha256']
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()));rows=json.loads((study.OUT/'asset-results.json').read_text())
    sums=template.summary(rows);study.write(study.OUT/'summary.json',sums);primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0]
    weakest={era:min((r for r in primary if r['era']==era and r['arm']=='value' and r['symbol']!='BIL'),key=lambda r:(r['cumulative'],r['symbol'])) for era,*_ in study.ERAS}
    focus={('INDA','late'),('WEAT','late'),('GLD','late'),('GLD','early'),('TLT','late'),('MCHI','late'),('ITA','early'),*((r['symbol'],era) for era,r in weakest.items())}
    for symbol,era in sorted(focus):figure(charts[f'{symbol}_{era}'],symbol,era,study.OUT/f'{symbol}_{era}.png')
    figure(charts['CPER_late'],'CPER','late',study.OUT/'CPER-incident.png',('2025-06-15','2025-08-15'))
    figure(charts['IWM_early'],'IWM','early',study.OUT/'IWM-incident.png',('2020-10-01','2021-06-30'))
    pct=lambda x:'—' if x is None else f'{100*x:+.2f}%'
    fmt=lambda x:'—' if x is None else f'{x:.3f}'
    st=''.join(f'<tr><td>{r["era"]}</td><td>{NAMES[r["arm"]]}</td><td>{r["median_sharpe"]:.3f}</td><td>{pct(r["median_cagr"])}</td><td>{pct(r["guard_fraction"])}</td><td>{r["median_correlation"]:.3f}</td><td>{r["median_beta"]:.3f}</td><td>{r["median_annual_cost_bp"]:.1f}</td></tr>' for r in sums if r['cost_bp']==5 and r['delay']==0)
    lookup={(r['symbol'],r['era'],r['arm']):r for r in primary};pt=''
    for era,*_ in study.ERAS:
        for r in sorted((r for r in primary if r['era']==era and r['arm']=='value'),key=lambda r:r['cumulative']):
            a,b=lookup[r['symbol'],era,'control'],lookup[r['symbol'],era,'hmm'];q=charts[f'{r["symbol"]}_{era}']['selection']
            pt+=f'<tr><td>{r["symbol"]}</td><td>{era}</td><td>{pct(a["cumulative"])}</td><td>{pct(b["cumulative"])}</td><td>{pct(r["cumulative"])}</td><td>{fmt(r["sharpe"])}</td><td>{fmt(r["calmar"])}</td><td>{pct(-r["maxdd"])}</td><td>{fmt(r["forecast"]["ic"])}</td><td>{r["closed_trades"]}</td><td>{q["forecast"]["kind"]} / {q["forecast"]["memory"]} / H{q["horizon"]}</td></tr>'
    exports=' · '.join(f'<a href="{s}_{e}.png">{s} {e} figure</a>' for s,e in sorted(focus))
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Directional states and online entry value</title>
<style>body{font:16px/1.5 system-ui;color:#17384d;background:#f5f8fa;max-width:1280px;margin:34px auto;padding:0 20px}h1,h2{line-height:1.2}h2{margin-top:38px}a{color:#006b70}.note{background:#fff0d7;border-left:4px solid #b47b22;padding:16px}.card{background:white;padding:18px;border:1px solid #d9e3e9;margin:14px 0}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center}button,select,input{font:inherit;padding:7px;border:1px solid #b4c5ce;border-radius:5px;background:white}button{cursor:pointer}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:7px 9px;border-bottom:1px solid #e2e8ed;text-align:right}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}#chart{width:100%;height:auto}#readout{min-height:64px}.equation{overflow:auto;padding:9px;background:white;margin:5px 0}.equation svg{max-width:100%;height:auto}small{color:#536b7b}</style>
<h1>Directional states and online entry value</h1><p>27 October 2026 · Full supported ETF pool · Three comparisons</p>
<p class="note">These periods have been inspected repeatedly: results are development evidence, not fresh out-of-sample validation. A is the fixed-policy component control. The actual preceding adaptive incumbent is separately reported in each ETF's diagnostics. No portfolio overlay or live changes.</p>
<ul><li><b>A — original detector:</b> existing per-ETF fast/slow filters, fixed base policy and selected thesis exit.</li><li><b>B — symmetric directional HMM:</b> down/up distributions have opposite means and equal variances. This removes the broad-down-tail defect. States still describe filtered slopes, not guaranteed profitable trends.</li><li><b>C — online entry value:</b> B can buy only when predicted executable return exceeds costs plus 25% of predicted adverse movement. Forecasts learn from all matured hypothetical outcomes, including while cash. There is no permanent pause and no extra price-rise confirmation.</li></ul>
<div id="findings">__FINDINGS__</div>
<h2>Inspect every ETF</h2><p id="weakestNote"></p><div class="controls"><label>Era <select id="era"><option value="late">2023–2026</option><option value="early">2020–2022</option></select></label><label>ETF <select id="etf"></select></label><label>Algorithm <select id="arm"><option value="control">A · Original detector</option><option value="hmm">B · Symmetric HMM</option><option value="value">C · HMM + entry value</option></select></label><button id="weakest">Weakest C</button><button id="weat">WEAT</button><button id="tlt">TLT rebounds</button></div>
<div class="controls"><label>From <input id="from" type="date"></label><label>To <input id="to" type="date"></label><button id="reset">Full context</button><button id="inda">INDA incident</button><button id="gold">GLD 2020</button><button id="cper">CPER July 2025</button><button id="iwm">IWM 2021</button></div>
<div class="card"><p id="metrics"></p><p id="dependence"></p><p id="forecast"></p><small id="parameters"></small><p id="readout">Hover for an exact date; click two dates to zoom.</p><svg id="chart" viewBox="0 0 1200 1490"></svg></div>
<details open><summary>Actual trades and entry context</summary><div class="scroll"><table><tr><th>Entry</th><th>Exit</th><th>Slow context</th><th>Net return</th><th>Initial stop distance</th><th>Exit reason</th></tr><tbody id="trades"></tbody></table></div></details>
<details><summary>Fitted distributions, transition matrix, policy and forecast selection</summary><pre id="fitparameters" style="overflow:auto"></pre></details>
<details><summary>Results conditional on causal slow context</summary><table><tr><th>Context</th><th>Sessions</th><th>Exposure</th><th>Mean daily strategy</th><th>Mean daily ETF</th><th>Closed</th><th>Losing</th><th>Mean trade</th></tr><tbody id="regimes"></tbody></table><p>Daily context uses the prior close; trade context uses the entry signal. “Uncertain” is neither slow up nor slow down above 70%, not verified range-bound truth. Conditional daily averages do not compound or add across contexts.</p></details><p>__EXPORTS__</p>
<h2>Pool comparison</h2><div class="scroll"><table><tr><th>Era</th><th>Algorithm</th><th>Median Sharpe</th><th>Median CAGR</th><th>Within A guards</th><th>Correlation</th><th>Beta</th><th>Cost bp/year</th></tr>__SUMMARY__</table></div>
<p>ETF medians excluding BIL; 5 bp per side, next-open execution. Acceptance in each era/friction case requires improved median Sharpe and lower-quartile CAGR, plus ≥90% of ETFs within 1 percentage point CAGR / 2 points maximum drawdown of A. All six friction cases per era are retained. Lower exposure or correlation alone is not success.</p>
<details open><summary>Full pool — worst C return first in each era</summary><div class="scroll"><table><tr><th>ETF</th><th>Era</th><th>A return</th><th>B return</th><th>C return</th><th>C Sharpe</th><th>C Calmar</th><th>C drawdown</th><th>Forecast IC</th><th>C trades</th><th>Model / memory / horizon</th></tr>__POOL__</table></div></details>
<h2>Exact model</h2>__EQUATIONS__
<p>C and O denote adjusted closes and opens; V is audited raw ETF share volume. b and ℓ are slope and log-price level from the fast (f) or slow (s) causal local-linear filter. σ is training daily log-return dispersion. p are filtered state scores. f in the utility formula is the per-side fee. Features involving slopes, price deviations and volume are clipped to [−3,3]. The 63-session volume EMA is a volume baseline, not a fixed trend-identification window.</p>
<p>The symmetric emissions force up-versus-down evidence to rise with slope, unlike the previous unequal-variance model. A persistent state prior can still temporarily oppose a modest new slope. Neutral variance is bounded; this is neither proof of a horizontal price box nor a learned multi-year regime. The slow context remains the existing Kalman filter. This round does not add a third HMM.</p>
<p>The forecast label for a decision at close i starts at the next open and ends H sessions later at an open. Its adverse movement samples opens and intervening closes, excluding the exit-day close. It does not measure intraday worst loss. At close t only label i=t−H−1 can newly enter the update; incomplete outcomes are not filled with zero. Both targets update while invested and while cash. Only C uses these forecasts to trade; their common diagnostic curves remain visible when inspecting A or B.</p>
<p>Before the final 252 training sessions, refit both Kalman filters and the HMM using only that prefix. Derive H from its up-state persistence, constrained to 5–21 sessions, and freeze it. Forward-predict the final 252 training sessions, scoring only outcomes matured by the training cutoff. Select among full features versus intercept-only, each with memory half-life 63 or 252 sessions, by the displayed validation loss. Ties prefer intercept then longer memory. The risk penalty 0.25 and ridge precision 4I are predeclared constants, not tuned on evaluation returns.</p>
<p>Then fit the final symmetric HMM on all training slopes under the existing full-training Kalman parameters, and replay training to initialize the selected forecasting model. This initialization is fitted training calibration; only the preceding prefix-based forecast selection is chronological. Thereafter forecasts update causally. The original trading thresholds and thesis rule remain inherited training fits. This is not nested validation of the whole strategy.</p>
<p>The ridge equations give discounted posterior means under a Gaussian working likelihood. With overlapping outcomes and estimated states, they do not supply calibrated posterior confidence intervals. Weight 1/H tempers overlapping observations without claiming to remove their dependence. See <a href="https://www.statsmodels.org/stable/examples/notebooks/generated/recursive_ls.html">recursive regression and coefficient stability</a> for the general updating concept; its expanding regression differs from our explicitly discounted equations. HMM trading uses filtering, not future smoothing; see the <a href="https://luisdamiano.github.io/stancon18/hmm_stan_tutorial.pdf">HMM filtering reference</a>.</p>
<h2>Execution, exits and limitations</h2>
<p>All arms retain the original entry threshold, up&lt;0.5 rearming, selected thesis invalidation, down-state exit and nonloosening stop. Thesis invalidation requires up score below its selected floor for its selected count and current slope ≤0; strong slow-up context halves the floor and adds two closes. Protection is tested at close before ratcheting: next stop = max(previous stop, peak close − distance × entry open × training σ). Initial stop distance and optional widening come from the original fixed policy. No new independent hard-risk boundary or forecast exit is added. Pending target changes bind; loss and profit exits fill at the next executable open, so stops are not guaranteed fill prices.</p>
<p>Fees are 5/10/20 bp each side, with zero or one extra execution-day delay. The gate uses the exact roundtrip log fee. Delay stress retains the next-open-trained forecast and tests its staleness. Fractional cash-funded shares, zero cash interest, terminal positions marked without forced sale. Native checks separately compare whole-share/cent-price application accounting for frozen signals; they do not independently fit the HMM.</p>
<p>Returns and signals use adjusted prices from the pinned published audited histories; raw share volume enters the full forecast. No provider archives or web prices. Historical publication-vintage limitations remain. Correlation, beta and annualized OLS intercept use daily arithmetic returns with zero cash rate; HAC(5) t values are descriptive, not risk-free-adjusted or causal alpha. Raw HMM IC uses five-session executable open returns; forecast IC uses its selected H-session log return. Both overlap and are not significance claims. B and C share raw-state IC; entry selection differs.</p>
<p><a href="asset-results.json">Full metrics and annual returns</a> · <a href="summary.json">Cost/delay comparisons</a> · <a href="fits.json">Training fits</a> · <a href="protocol.json">Frozen protocol</a> · <a href="validation.json">Accounting checks</a> · <a href="native-checks.json">Native checks</a> · <a href="failure-audit.json">Forecast and failure diagnostics</a></p>
<script>const DATA = __DATA__;
__SCRIPT__</script></html>'''
    def display(x):
        if isinstance(x,float):return round(x,7)
        if isinstance(x,list):return [display(v) for v in x]
        if isinstance(x,dict):return {k:display(v) for k,v in x.items()}
        return x
    script=study.ROOT/'scripts/assets/entry-value-script.js';findings=study.OUT/'findings.html'
    for token,value in dict(EXPORTS=exports,SUMMARY=st,POOL=pt,EQUATIONS=equations(),FINDINGS=findings.read_text(encoding='utf-8') if findings.exists() else '',
        DATA=json.dumps(display(dict(charts=charts,rows=primary,weakest=weakest)),separators=(',',':')).replace('</','<\\/'),SCRIPT=script.read_text(encoding='utf-8')).items():html=html.replace('__'+token+'__',value)
    (study.OUT/'index.html').write_text(html,encoding='utf-8');study.write(study.OUT/'weakest-cases.json',weakest)
    study.write(study.OUT/'manifest.json',dict(files={p.name:study.prior.study.digest(p) for p in study.OUT.iterdir() if p.is_file() and p.name!='manifest.json'},report_code={str(p.relative_to(study.ROOT)).replace(chr(92),'/'):study.prior.study.digest(p) for p in (Path(__file__),script,study.ROOT/'scripts/build_regime_entry_report.py',study.ROOT/'tests/entry_value_controls.cjs',study.ROOT/'tests/test_entry_value_contract.py',study.ROOT/'scripts/validate_entry_value.py',study.ROOT/'scripts/analyze_entry_value.py')}))
    print(json.dumps(dict(charts=len(charts)*3,weakest={e:r['symbol'] for e,r in weakest.items()})))


if __name__=='__main__':main()
