"""All-ETF chart report with explicit mathematical definitions."""
import gzip
from html import escape
from io import BytesIO
import json
import re
import numpy as np
import research_decision_review as study

NAMES={'baseline':'A · Standing protection','stop':'B · Independent review','review':'C · Adaptive review'}
COLORS={'baseline':'#8b9caa','stop':'#c98a21','review':'#008675'}


def figure(c,symbol,era,path,limits=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    d=np.array(c['days'],dtype='datetime64[D]');a=c['arms']['review']
    fig,ax=plt.subplots(7,1,figsize=(15,15),sharex=True,layout='constrained',height_ratios=[2.3,.6,.8,.65,.8,.8,1.4])
    mask=np.ones(len(d),bool) if not limits else (d>=np.datetime64(limits[0]))&(d<=np.datetime64(limits[1]))
    ax[0].plot(d,c['close'],color='#173d54',label='Adjusted close');ax[0].plot(d,np.array(a['stop'],float),color='#b64f61',label='C active stop')
    ax[0].vlines(d[mask],np.array(c['low'])[mask],np.array(c['high'])[mask],color='#91a3ae',lw=.7)
    for e in a['fills']:
        if limits and not limits[0]<=e['day']<=limits[1]:continue
        buy=e['side']=='buy';rec=any(t['entry_date']==e['day'] and t.get('entry_reason')=='exit_review' for t in a['trades'])
        ax[0].scatter(np.datetime64(e['day']),e['price'],marker='^' if buy else 'v',color=('#d58b20' if rec else '#008675') if buy else '#b64f61',s=34,zorder=5)
    ax[0].set_ylabel('Adjusted USD');ax[0].legend(fontsize=8,ncol=2)
    ax[1].bar(d,np.array(c['volume'])/1e6,color='#9aabb6');ax[1].set_ylabel('Volume (m)')
    for k,color in [('fast_up','#008675'),('neutral','#b09a52'),('fast_down','#b64f61')]:ax[2].plot(d,c[k],label=k,color=color)
    for k,color in [('slow_up','#008675'),('slow_down','#b64f61')]:ax[3].plot(d,c[k],label=k,color=color)
    for k,color in [('probability','#008675'),('recent_weight','#c98a21')]:ax[4].plot(d,np.array(a[k],float),label=k,color=color)
    for k,color in [('up_evidence','#008675'),('down_evidence','#b64f61')]:ax[5].plot(d,np.array(a[k],float),label=k,color=color)
    ax[5].axhline(np.log(4),ls='--',color='#777',lw=.7,label='log(4) threshold')
    for arm in study.model.ARMS:ax[6].plot(d,np.array(c['arms'][arm]['nav'],float),label=NAMES[arm],color=COLORS[arm])
    for i in range(2,7):ax[i].legend(fontsize=8,ncol=3)
    for i in (2,3,4):ax[i].set_ylim(-.02,1.02)
    for x in ax:x.grid(alpha=.15)
    if limits:
        ax[-1].set_xlim(np.datetime64(limits[0]),np.datetime64(limits[1]))
        values=[c[k][i] for i in np.flatnonzero(mask) for k in ('low','high')]+[a['stop'][i] for i in np.flatnonzero(mask) if a['stop'][i] is not None]
        lo,hi=min(values),max(values);ax[0].set_ylim(lo-(hi-lo)*.06,hi+(hi-lo)*.06)
    else:ax[-1].set_xlim(np.datetime64(c['evaluation_start']),d[-1])
    ax[-1].set_ylabel('NAV / initial100');ax[-1].xaxis.set_major_formatter(dates.DateFormatter('%Y-%m-%d'))
    fig.suptitle(f'{symbol} | {era} | C independent decision review with adaptive model weights\nGreen buys / red sells; orange recovery buys. 5 bp per side + 5 bp stop slippage; next-open decisions.')
    fig.savefig(path,dpi=110);plt.close(fig)


def equations():
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    import matplotlib.pyplot as plt
    formulas=[
      r'r_t=\log(C_t/C_{t-1}),\quad CL_t=(C_t-L_t)/(H_t-L_t),\quad VP_t=\frac{\sum_{i=t-2}^t sign(r_i)V_i}{\sum_{i=t-2}^t V_i}',
      r'TR_t=\max(H_t-L_t,|H_t-C_{t-1}|,|L_t-C_{t-1}|),\quad ATR_t=ATR_{t-1}+(TR_t-ATR_{t-1})/20',
      r'x_t=clip\left([r_t/\sigma,\ (r_t+r_{t-1}+r_{t-2})/(\sigma\sqrt{3}),\ 2CL_t-1,\ VP_t,\ \log(V_t/\bar V_{t-20:t-1}),\ (L_t-L_{t-1})/ATR_{t-1}],-4,4\right)',
      r'z_t=\log(O_{t+6}/O_{t+1})/(\sigma\sqrt{5}),\quad y_t=1[z_t>0];\quad z_t\ \mathrm{available\ at\ close}\ t+6',
      r'n_j=\sum_i1[y_i=j],\ s_j=\sum_{i:y_i=j}x_i,\ Q_j=\sum_{i:y_i=j}x_ix_i^T,\ v_j=\sum_{i:y_i=j}z_i',
      r'm_j=s_j/n_j,\ \pi_j=n_j/\sum_kn_k,\ b_j=v_j/n_j,\ \Sigma=0.5\frac{\sum_j(Q_j-n_jm_jm_j^T)}{\sum_jn_j}+0.5D_{train}+0.05I',
      r'p_{k,t}=\frac{\pi_{k,1}N(x_t;m_{k,1},\Sigma_k)}{\sum_{j=0}^1\pi_{k,j}N(x_t;m_{k,j},\Sigma_k)},\quad \mu_{k,t}=\sigma\sqrt{5}[(1-p_{k,t})b_{k,0}+p_{k,t}b_{k,1}]',
      r'p_t=\sum_kw_{k,t}p_{k,t},\quad \mu_t=\sum_kw_{k,t}\mu_{k,t},\quad \pi_t=\sum_kw_{k,t}\pi_{k,1},\quad \ell_t=clip(logit(p_t)-logit(\pi_t),-2,2)',
      r'G^+_t=\max(0,G^+_{t-1}+\ell_t-0.1),\quad G^-_t=\max(0,G^-_{t-1}-\ell_t-0.1),\quad h=\log4',
      r'\mathrm{entry\ invalid}:\ G^-_t\geq h,\ p_t<0.5,\ \mu_t<0,\ C_t<C_{t-1},\ C_t\leq Peak_{t-1}-0.5ATR_t',
      r'\mathrm{recover}:\ 1\leq t-t_x\leq20,\ G^+_t\geq h,\ p_t>0.5,\ \mu_t>2f+s,\ F_x(1+2f)\leq C_t\leq F_x+1.5ATR_{x-1}',
      r'C_t>\max(O_t,C_{t-1}),\quad CL_t\geq0.6,\quad VP_t\geq0;\quad O_{t+1+delay}\in[F_x,F_x+1.5ATR_{x-1}]',
      r'R=O_{entry}\sigma,\quad S_{entry}=O_{entry}-dR,\quad S_{t+1}=\max(S_t,Peak_t-d_tR)',
      r'L_t\leq S_t\Rightarrow F_t=\min(O_t,S_t)(1-s);\quad f\in\{0.0005,0.001,0.002\},\ s=0.0005,\ delay\in\{0,1\}',
      r'\rho=2^{-1/H};\quad (n_j,s_j,Q_j,v_j)\leftarrow\rho(n_j,s_j,Q_j,v_j)+1[y=j](1,x,xx^T,z)',
      r'a_{k,t}=y_{t-6}\log\tilde p_{k,t-6}+(1-y_{t-6})\log(1-\tilde p_{k,t-6}),\quad \tilde p=clip(p,0.01,0.99)',
      r'w_{k,t}\propto\exp[0.98\log w_{k,t-1}+clip(a_{k,t}-\bar a_t,-2,2)/5]',
      r'\mathrm{warning}:\ w_k\leftarrow\sqrt{w_k}/\sum_j\sqrt{w_j},\quad H=10\ \mathrm{for\ next21\ sessions};\quad H=63\ \mathrm{otherwise}'
    ]
    parts=[]
    for i,formula in enumerate(formulas):
        buf=BytesIO();mathtext.math_to_image('$'+formula+'$',buf,prop=FontProperties(size=13),format='svg',color='#17384d')
        svg=buf.getvalue().decode();svg=svg[svg.index('<svg'):]
        svg=re.sub(r'id="([^"]+)"',lambda m:f'id="eq{i}_{m[1]}"',svg);svg=re.sub(r'xlink:href="#([^"]+)"',lambda m:f'xlink:href="#eq{i}_{m[1]}"',svg)
        parts.append('<div class="equation">'+svg+'</div>')
    fig,axes=plt.subplots(len(formulas),1,figsize=(24,19),layout='constrained')
    for ax,formula in zip(axes,formulas):ax.axis('off');ax.text(.005,.3,'$'+formula+'$',fontsize=12)
    fig.savefig(study.OUT/'equation-proof.png',dpi=95,bbox_inches='tight');plt.close(fig);study.write(study.OUT/'equations.json',formulas)
    return ''.join(parts)


def main():
    validation=json.loads((study.OUT/'validation.json').read_text());assert validation['chart_sha256']==study.prior.study.digest(study.OUT/'chart-data.json.gz')
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()));rows=json.loads((study.OUT/'asset-results.json').read_text())
    sums=json.loads((study.OUT/'summary.json').read_text());weakest=json.loads((study.OUT/'weakest-cases.json').read_text())
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0];lookup={(r['symbol'],r['era'],r['arm']):r for r in primary}
    pct=lambda x:'—' if x is None else f'{100*x:+.2f}%';num=lambda x:'—' if x is None else f'{x:.3f}'
    def table(heads,body):return '<div class="scroll"><table><tr>'+''.join('<th>'+h+'</th>' for h in heads)+'</tr>'+''.join('<tr>'+''.join('<td>'+str(v)+'</td>' for v in row)+'</tr>' for row in body)+'</table></div>'
    summary=table(['Era','Model','Median Sharpe','Median CAGR','Preserved ETFs','Fee + slip bp/year','Pass'],[
        [r['era'],NAMES.get(r['arm'],r['arm']),num(r['median_sharpe']),pct(r['median_cagr']),pct(r['guard_fraction']),f"{r['median_annual_cost_bp']:.1f}",r['passed']]
        for r in sums if r['cost_bp']==5 and r['delay']==0 and r['arm'] in NAMES])
    pool=[]
    for era,*_ in study.ERAS:
        for c in sorted((r for r in primary if r['era']==era and r['arm']=='review'),key=lambda r:r['cumulative']):
            a,b=lookup[c['symbol'],era,'baseline'],lookup[c['symbol'],era,'stop']
            pool.append([c['symbol'],era,pct(a['cumulative']),pct(b['cumulative']),pct(c['cumulative']),num(c['sharpe']),num(c['calmar']),pct(-c['maxdd']),num(c['ic5']),num(c['forecast_ic']),f"{c['wins']}/{c['closed_trades']}"])
    focus={('CPER','late'),('IWM','late'),('GLD','late'),('WEAT','late'),('TLT','late'),('PPLT','late'),('IAT','early'),*((r['symbol'],e) for e,r in weakest.items())}
    for symbol,era in sorted(focus):figure(charts[symbol+'_'+era],symbol,era,study.OUT/f'{symbol}_{era}.png')
    for symbol,a,b in [('CPER','2025-03-04','2025-09-04'),('IWM','2024-07-01','2024-12-01')]:figure(charts[symbol+'_late'],symbol,'late',study.OUT/f'{symbol}-incident.png',(a,b))
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Independent decision review</title>
<style>body{font:16px/1.5 system-ui;color:#17384d;background:#f5f8fa;max-width:1320px;margin:32px auto;padding:0 20px}h1,h2{line-height:1.25}h2{margin-top:36px}a{color:#006b70}.note{background:#fff0d7;padding:16px;border-left:4px solid #b47b22}.card{background:white;padding:16px;margin:14px 0;border:1px solid #d9e3e9}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center;margin:10px 0}button,select,input{font:inherit;padding:7px;border:1px solid #b4c5ce;border-radius:5px;background:white}button{cursor:pointer}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:7px 9px;text-align:right;border-bottom:1px solid #e2e8ed}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}#chart{width:100%;height:auto}#readout{min-height:75px;position:sticky;top:0;background:#fff9e9;padding:10px;z-index:2}.equation{overflow:auto;padding:10px;background:white;margin:5px 0}.equation svg{max-width:100%;height:auto}pre{overflow:auto}</style>
<h1>Independent decision review</h1><p>28 October 2026 · Full ETF pool · Three comparisons</p>
<p class="note">Development evidence on repeatedly inspected periods, through 16 October 2026. Daily OHLC stop fills are modeled. No portfolio overlay, promotion or live execution changes.</p>
<ul><li><b>A — standing protection:</b> the selected B strategy from entry-value research with the previous study's standing stop. This is prior B1.</li><li><b>B — independent review:</b> A plus a separate price/volume model that can challenge a buy or reassess a sale without waiting for the HMM.</li><li><b>C — adaptive review:</b> B with a frozen established model and a recent model. Predictive evidence changes their weights; loss/reversal warnings accelerate recent learning. All three keep the same inherited stop distances.</li></ul>
__FINDINGS__
<h2>Inspect every ETF</h2><p id="weakestNote"></p>
<div class="controls"><label>Era <select id="era"><option value="late">2023–2026</option><option value="early">2020–2022</option></select></label><label>ETF <select id="etf"></select></label><label>Model <select id="arm"><option value="baseline">A · Standing protection</option><option value="stop">B · Independent review</option><option value="review">C · Adaptive review</option></select></label><button id="weakest">Weakest C in era</button><button id="weat">WEAT</button><button id="tlt">TLT rebounds</button></div>
<div class="controls"><label>From <input id="from" type="date"></label><label>To <input id="to" type="date"></label><button id="reset">Full era</button><button id="cper">CPER · Mar–Sep 2025</button><button id="iwm">IWM · Jul–Dec 2024</button></div>
<div class="card"><p id="metrics"></p><p id="dependence"></p><p id="learning"></p><p id="window"></p><p id="readout">Hover for dates and values. Click two dates to zoom.</p><svg id="chart" viewBox="0 0 1200 1550"></svg></div>
<details open><summary>Trades crossing your selected dates</summary><div class="scroll"><table><tr><th>Buy</th><th>Sell</th><th>Fill prices</th><th>Buy reason</th><th>Risk policy</th><th>Whole-trade return</th><th>Initial stop distance</th><th>Sell reason</th></tr><tbody id="trades"></tbody></table></div><p>Trade returns cover full trades. The selected-interval return above uses account NAV only between your dates.</p></details>
<details><summary>Warnings and review events</summary><table><tr><th>Date</th><th>Reason</th><th>Response</th><th>Recent-model weight</th></tr><tbody id="events"></tbody></table></details>
<details><summary>Individual ETF fit and inherited policy</summary><pre id="fitparameters"></pre></details><p>__EXPORTS__</p>
<h2>Pool results</h2>__SUMMARY__<p>Each ETF is a separate cash-funded strategy. Cross-ETF medians are not a portfolio return. 51 risky ETFs later, 49 earlier; BIL appears in charts/tables but is excluded from acceptance. Primary costs: 5 bp each side plus 5 bp stop slippage.</p>
<p>Acceptance requires higher median Sharpe and lower-quartile CAGR than A, with at least90% of ETFs within1 percentage point CAGR and2 points maximum drawdown of A, in each era/friction setting. A's own pass field is false by construction because improvement over itself is zero. The original close-stop B remains a <a href="../entry-value-20261027-v1/index.html">historical research reference</a>; A was not accepted as its universal replacement.</p>
<details open><summary>All ETFs — weakest C first, by era</summary>__POOL__</details>
<details><summary>Costs, extra signal delay, yearly stability and component diagnostics</summary>__STRESS__<p>Entry-only/exit-only disable one review component; no-warning retains ordinary recent learning. Slip50 stresses each main strategy with50 bp extra stop slippage. Signal delay changes next-open orders, not an already-standing stop. These are diagnostics, not additional proposed variants.</p>__COMPONENTS__<p>Annual returns are medians of individual ETF results:</p>__YEARLY__</details>
<h2>Mathematical specification</h2>__EQUATIONS__
<p>O/H/L/C are adjusted prices, V audited raw share volume, σ frozen training daily log-return standard deviation. Flat bars use CL=0.5. Dtrain has each feature's training variance floored at0.05 on its diagonal. Six features enter one covariance model; their signals are not multiplied as independent tests. Shared-covariance shrinkage reduces instability but does not establish calibrated probabilities.</p>
<p>Each ETF is fitted separately on at most756 matured training origins; cutoff is2019-12-31 or2022-12-30. The final origin is six sessions before cutoff. A label describes five open-to-open returns, so it is not available on its prediction date. Fixed B uses w=(1,0). Adaptive C starts w=(0.5,0.5); its recent model has identical initial moments scaled to effective sample size40, while the established model retains the full fitted history. All thresholds were frozen before evaluation; no parameter was selected against CPER or IWM.</p>
<p>At each close, score the previously stored forecasts whose label has just matured, update weights and the recent model, then forecast from today's complete bar. Even when the account holds cash, observations keep teaching the recent model. Five-session labels overlap, so the1/5 score tempering is a conservative heuristic, not proof of independent evidence. Forecast IC/Brier/log score are descriptive and use the same five-session horizon even in delayed-execution stress runs. Raw HMM IC is unchanged across arms; review-forecast IC is a separate diagnostic.</p>
<p>G+ only accumulates during the20-session post-exit watch; G− only while held. Both reset at fills. This is CUSUM-style accumulation of correlated forecast evidence. log4 is a fixed engineering threshold, not an80% confidence claim or guaranteed false-alarm rate. No full hidden-regime or Bayesian change-point model is implemented in this round.</p>
<p>A recovery requires all displayed conditions, with no position, pending order or same-day sale. A qualified recovery bypasses the HMM entry threshold. At the scheduled opening, an out-of-band price cancels the order. Ordinary entries retain the inherited rule. A review exit adds to the existing HMM/thesis exits and never disables standing protection. After a protective sale, pending exits are cancelled. A scheduled opening sale precedes the daily stop test.</p>
<p>Large loss means a completed return below the negative training dispersion of winning trades (fallback σ√21 if fewer than3 training winners), bounded below by round-trip fees. Other alarms are the3rd/4th consecutive loss, an entry-invalidation exit, or a qualified exit reversal. C tempers weights toward equal and speeds recent forgetting for21 sessions; it does not discard all data, force a model switch or widen stops. Ordinary B logs the same events but keeps its fitted model fixed. A predictive expert with a high weight is not necessarily a profitable trading strategy.</p>
<h2>Research basis and limits</h2>
<p>The sequential-review idea draws on <a href="https://doi.org/10.1093/biomet/41.1-2.100">Page's cumulative-sum work</a>; predictive competition draws on <a href="https://pubmed.ncbi.nlm.nih.gov/20607102/">Raftery, Kárný and Ettler's dynamic model averaging</a>. Our bounded implementation differs from both original statistical settings. <a href="https://arxiv.org/abs/0710.3742">Bayesian online change-point detection</a> and <a href="https://proceedings.mlr.press/v202/altamirano23a.html">robust change-point research</a> motivate future work; they have not been implemented or validated by this experiment.</p>
<p>Published audited batch5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd and verified parent input hashes. No downloaded provider archive or web prices enter this run. Auditing does not establish historical publication vintages. Training is fitted calibration and the evaluation eras have been inspected repeatedly; neither is an untouched prospective test.</p>
<p>Fractional shares, fees on each side, zero cash interest and terminal marking. A daily-bar stop fills at min(open, pre-existing stop) less slippage; today's high cannot tighten today's tested stop. Gaps, intraday jumps and liquidity may produce worse real fills. No same-close fill is claimed. Cost/turnover include both normal orders and recoveries. HAC regression intercepts and overlapping ICs remain descriptive.</p>
<p>Independent accounting reconstructs all ordered fills, including opening buys stopped the same day. Native Windows LEAN fixtures put each fill and mark on a synthetic event calendar to validate sizing, fees, ordering and NAV. They do not validate market execution or independently refit models. Browser layout is not certified; chart controls and all306 combinations are checked offline and representative scientific figures are visually inspected.</p>
<p><a href="protocol.json">Frozen protocol</a> · <a href="fits.json">Per-ETF training fits</a> · <a href="asset-results.json">All metrics</a> · <a href="summary.json">All summaries</a> · <a href="incident-audit.json">CPER/IWM evidence</a> · <a href="recovery-gate-audit.json">Recovery gates</a> · <a href="failure-trade-audit.json">Failure trade audit</a> · <a href="attribution.json">Largest ETF changes</a> · <a href="forecast-calibration.json">Forecast versus constant-prior checks</a> · <a href="validation.json">Accounting checks</a> · <a href="native-checks.json">Native fixtures</a></p>
<script>const DATA = __DATA__;
__SCRIPT__</script></html>'''
    def display(v):
        if isinstance(v,float):return round(v,8)
        if isinstance(v,list):return [display(x) for x in v]
        if isinstance(v,dict):return {k:display(x) for k,x in v.items()}
        return v
    replacements=dict(FINDINGS=(study.OUT/'findings.html').read_text(encoding='utf-8'),SUMMARY=summary,
        POOL=table(['ETF','Era','A return','B return','C return','C Sharpe','C Calmar','C maxDD','HMM IC','C forecast IC','C wins/trades'],pool),
        STRESS=table(['Era','Fee bp','Extra delay','Model','Median Sharpe','Median CAGR','Preserved','Pass'],[[r['era'],r['cost_bp'],r['delay'],NAMES[r['arm']],num(r['median_sharpe']),pct(r['median_cagr']),pct(r['guard_fraction']),r['passed']] for r in sums if r['arm'] in ('stop','review')]),
        COMPONENTS=table(['Era','Diagnostic','Sharpe','CAGR','Preserved'],[[r['era'],r['arm'],num(r['median_sharpe']),pct(r['median_cagr']),pct(r['guard_fraction'])] for r in sums if r['arm'] not in NAMES]),
        YEARLY=table(['Era','Model','Year','Median return'],[[r['era'],NAMES[r['arm']],y,pct(v)] for r in sums if r['arm'] in NAMES and r['cost_bp']==5 and r['delay']==0 for y,v in r['yearly'].items()]),
        EQUATIONS=equations(),EXPORTS=' · '.join(f'<a href="{s}_{e}.png">{s} {e}</a>' for s,e in sorted(focus))+' · <a href="CPER-incident.png">CPER selected dates</a> · <a href="IWM-incident.png">IWM selected dates</a>',
        DATA=json.dumps(display(dict(charts=charts,rows=primary,weakest=weakest)),separators=(',',':')).replace('</','<\\/'),
        SCRIPT=(study.ROOT/'scripts/assets/decision-review-script.js').read_text(encoding='utf-8'))
    for key,value in replacements.items():html=html.replace('__'+key+'__',value)
    (study.OUT/'index.html').write_text(html,encoding='utf-8');print('Built306 chart cases',flush=True)


if __name__=='__main__':main()
