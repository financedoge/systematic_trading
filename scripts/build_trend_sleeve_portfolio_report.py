"""Offline, self-contained N15 research report and all-ETF chart inspector."""
import base64
import gzip
import html
import io
import json
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import research_trend_sleeve_portfolio as s

NAMES={'equal':'N15 · equal capital','risk':'N15 · strategy risk parity','all':'Full pool · equal capital',
 'equal_dynamic':'N15 equal · dynamic','risk_dynamic':'N15 risk parity · dynamic','raw_momentum':'Raw ETF ranks · N15 equal',
 'buyhold':'Full-pool ETF buy & hold','BIL':'BIL buy & hold','FR25':'FR25 monthly targets',
 'equal_short':'21/126 ranks · N15 equal','risk_short':'21/126 ranks · N15 risk parity'}
COLORS={'equal':'#137e79','risk':'#ad6935','all':'#4b68a8','raw_momentum':'#889999','buyhold':'#b2a5c0'}
def pct(x):return '—' if x is None else f'{100*x:.2f}%'
def num(x):return '—' if x is None else f'{x:.3f}'
def table(rows,columns):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+label+'</th>' for _,label,_ in columns)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(fmt(r.get(k))))+'</td>' for k,_,fmt in columns)+'</tr>' for r in rows)+'</tbody></table></div>'
def eq(text):
    fig=plt.figure(figsize=(13,.65));fig.text(.01,.5,'$'+text+'$',fontsize=13,va='center')
    stream=io.StringIO();fig.savefig(stream,format='svg',bbox_inches='tight',pad_inches=.1);plt.close(fig)
    return '<div class="equation">'+stream.getvalue()[stream.getvalue().index('<svg'):]+'</div>'


def chart(c,key,actual=None):
    days=np.array(c['days'],dtype='datetime64[D]');fig,ax=plt.subplots(5,1,sharex=True,figsize=(13,11),gridspec_kw={'height_ratios':[3,1,1,1,2]})
    ax[0].plot(days,c['close'],lw=1,label='Adjusted close');ax[0].vlines(days,c['low'],c['high'],alpha=.25,lw=.5)
    ax[0].plot(days,c['stop'],color='#bd465c',lw=1,label='Closing stop')
    for side,color,marker in [('buy','#008776','^'),('sell','#bd465c','v')]:
        fills=[f for f in c['fills'] if f['side']==side]
        ax[0].scatter(np.array([f['day'] for f in fills],dtype='datetime64[D]'),[f['price'] for f in fills],c=color,marker=marker,s=25,label='Shadow '+side)
    if actual:
        ax[0].scatter(np.array([f['date'] for f in actual],dtype='datetime64[D]'),[f['price'] for f in actual],facecolors='none',edgecolors='#d78020',s=65,label='Actual portfolio fill')
    ax[0].legend(ncol=3,fontsize=8);ax[0].set_ylabel('Adjusted USD')
    ax[1].bar(days,np.array(c['volume'])/1e6,color='#8ba4ae');ax[1].set_ylabel('Raw volume (m)')
    for k,col in [('fast_up','#008776'),('neutral','#b79e3d'),('fast_down','#bd465c')]:ax[2].plot(days,c[k],label=k,color=col,lw=.8)
    ax[2].legend(ncol=3,fontsize=8);ax[2].set_ylabel('Fast HMM')
    for k,col in [('slow_up','#008776'),('slow_down','#bd465c')]:ax[3].plot(days,c[k],label=k,color=col,lw=.8)
    ax[3].legend(ncol=2,fontsize=8);ax[3].set_ylabel('Slow slope')
    ax[4].plot(days,c['nav'],color='#008776',label='Continuing strategy, rebased to 100')
    ax[4].plot(days,np.array(c['close'])/c['close'][0]*100,color='#91a0ae',label='Asset price, rebased before costs')
    ax[4].legend(fontsize=8);ax[4].set_ylabel('Value')
    for a in ax:a.grid(alpha=.15)
    fig.suptitle(key.replace('_',' | ')+' — matched portfolio window; 5 bp each side\nShadow account may carry a pre-window trade; portfolio fills are orange outlines.',fontsize=12)
    fig.tight_layout();fig.savefig(s.OUT/(key+'.png'),dpi=120);plt.close(fig)


def main():
    s.verify();rows=s.read(s.OUT/'results.json');v=s.read(s.OUT/'shadow-validation.json');audit=s.read(s.OUT/'validation.json')
    paths=json.loads(gzip.decompress((s.OUT/'paths.json.gz').read_bytes()));detail=json.loads(gzip.decompress((s.OUT/'detail.json.gz').read_bytes()))
    attrs=s.read(s.OUT/'attribution.json');weak=s.read(s.OUT/'weakest.json');matched=s.read(s.OUT/'fr25-matched.json');ics=s.read(s.OUT/'rank-ic.json')
    old=json.loads(gzip.decompress((s.ROOT/'research/stop-review-20261027-v1/chart-data.json.gz').read_bytes()));charts={}
    for key,q in old.items():
        symbol,era=key.split('_')
        if symbol=='BIL':continue
        start=v['eras'][era]['first_signal'];ix=next(i for i,d in enumerate(q['days']) if d==start);a=q['arms']['baseline']
        c={k:q[k][ix:] for k in ('days','open','high','low','close','volume','fast_up','fast_down','neutral','slow_up','slow_down')}
        c.update(nav=[x/a['nav'][ix]*100 for x in a['nav'][ix:]],stop=a['stop'][ix:],
            fills=[f for f in a['fills'] if f['day']>=start],trades=[t for t in a['trades'] if not t['exit_date'] or t['exit_date']>=start])
        charts[key]=c
    for era in ('late','early'):
        ds=np.array(paths[era+'_days'],dtype='datetime64[D]');fig,ax=plt.subplots(3,1,figsize=(13,9),sharex=True,gridspec_kw={'height_ratios':[2,1,1]})
        for arm in ('equal','risk','all','raw_momentum','buyhold'):
            key=f'{era}_{arm}_c5d0';nav=np.array(paths[key]);ax[0].plot(ds,nav*100,label=NAMES[arm],color=COLORS[arm],lw=1.5 if arm in ('equal','risk','all') else 1)
            if arm in ('equal','risk','all'):
                ax[1].plot(ds,(nav/np.maximum.accumulate(nav)-1)*100,color=COLORS[arm],label=NAMES[arm]);ax[2].plot(ds,np.array(detail[key]['cash'])*100,color=COLORS[arm])
        ax[0].set_ylabel('Portfolio value / initial 100');ax[0].legend(fontsize=8,ncol=2)
        ax[1].set_ylabel('Drawdown %');ax[2].set_ylabel('Uninvested cash %')
        for a in ax:a.grid(alpha=.2)
        fig.suptitle(f'{era.title()} chronology | N=15 | 5 bp each side | next-open execution\nMonthly allocation, daily strategy signals, no redistribution of idle sleeves')
        fig.tight_layout();fig.savefig(s.OUT/(era+'-portfolio.png'),dpi=120);plt.close(fig)
        names={next(w['symbol'] for w in weak if w['era']==era)}
        names|={attrs[f'{era}_{arm}_c5d0'][0]['symbol'] for arm in ('equal','risk','all')}
        for symbol in names:
            actual=[f for f in detail[f'{era}_equal_c5d0']['fills'] if f['symbol']==symbol]
            chart(charts[symbol+'_'+era],symbol+'_'+era,actual)
    columns=[('arm','Portfolio',lambda x:NAMES[x]),('cumulative','Net return',pct),('cagr','CAGR',pct),('sharpe','Sharpe¹',num),('calmar','Calmar',num),('max_drawdown','Max DD',pct),('average_invested','Invested',pct),('cost_bp_annual','Cost bp/year',lambda x:f'{x:.1f}')]
    body='<h1>N = 15: rolling strategy portfolios</h1><p class="subtitle">29 October 2026 · frozen single-ETF B · full supported pool · historical USD research</p>'
    body+='<div class="verdict"><b>The portfolio works mechanically, but the 63/252 ranking does not yet add reliable value.</b> Equal capital is stronger than strategy risk parity in the primary runs. Both rank-based portfolios have lower Sharpe than the unranked strategy pool in both primary eras. The earlier period loses money. Keep this as development evidence; do not adopt it as a proven improvement.</div>'
    body+='<p>Each of the 51 later / 49 earlier risky ETF strategies runs continuously. Fifteen receive capital monthly; those ETFs still follow their daily buy/sell signals. Idle sleeves keep cash. The single-ETF policy and N were not retuned. <a href="../trend-sleeve-synthesis-20261029-v1/index.html">Full underlying algorithm, fitting lineage and flowcharts</a>.</p>'
    for era in ('late','early'):
        meta=v['eras'][era]
        body+=f'<h2>{era.title()} chronology · {meta["first_fill"]} to {meta["last"]}</h2><p>Models trained through {meta["train_end"]}; first selection {meta["first_signal"]}, after 252 causal strategy-return observations. {meta["risky"]} risky ETFs supported. Initial value is marked at the preceding close; the first investment occurs at the following open.</p>'
        primary=[r for r in rows if r['era']==era and r['cost_bp']==5 and r['delay']==0]
        body+=table([r for r in primary if r['arm'] in ('equal','risk','all')],columns)
        body+=f'<img class="figure" src="{era}-portfolio.png" alt="{era} portfolio NAV drawdown and cash"/>'
        body+='<details><summary>Matched simple controls and annual returns</summary>'+table([r for r in primary if r['arm'] in ('raw_momentum','buyhold','BIL')],columns)
        yearly=[dict(arm=r['arm'],**r['yearly']) for r in primary if r['arm'] in ('equal','risk','all','raw_momentum','buyhold')]
        years=sorted(set(k for r in yearly for k in r if k!='arm'))
        body+=table(yearly,[columns[0]]+[(y,y+' (partial at edges)',pct) for y in years])+'</details>'
    body+='<p class="note">¹ Sharpe = √252 × arithmetic mean / sample standard deviation of daily net portfolio returns, with a zero cash rate. It is not a BIL-excess Sharpe. Calmar = CAGR / maximum drawdown. Drawdowns are positive loss magnitudes. Costs are 5 bp per traded side, including allocation trades; no terminal liquidation. Idle cash earns zero, while BIL is a separately invested reference. These are repeatedly inspected development periods, not fresh holdouts.</p>'
    body+='<h2>What is weakening the selector?</h2><ul><li><b>Past strategy ranks are not predicting the next month well.</b> Mean monthly cross-sectional 21-session shadow-return IC is '+', '.join(f'{e}: {np.mean([x["ic"] for x in ics if x["era"]==e]):+.3f}' for e in ('late','early'))+'. This is a descriptive, overlapping-label diagnostic of continuing virtual accounts; it is not an executable new-entry return or a significance claim.</li>'
    body+='<li><b>Fifteen selected sleeves are only about eight or nine active ETF holdings.</b> Equal capital averages 8.64 invested ETFs later and 7.99 earlier; about 42% and 46% of capital is cash. Risk parity reduces effective invested breadth to 6.76 and 6.55. ETF count also overstates economic diversification because equity markets, sectors and commodities overlap.</li><li><b>Risk parity concentrates capital without fixing the signal.</b> Its largest capital sleeve reaches 27.2% later and 25.0% earlier. Equal-risk contributions refer to a shrunk historical covariance of whole strategy accounts, including cash, and need not remain equal after daily exits.</li><li><b>Selection adds turnover.</b> Monthly N15 trades roughly 15–16 portfolio-capital equivalents per year, versus 11.6 for the unranked sleeves. The 10% dynamic trigger trades roughly 31–41, with no stable net benefit.</li><li><b>Gains are concentrated.</b> EWY contributes +6.38 percentage points of the later N15 equal-capital +18.15%; IAT subtracts 1.53 points. Earlier XLY subtracts 2.48 points and SOXX 1.48 points. These are actual portfolio P&amp;L contributions, including fees, not standalone ETF returns.</li></ul>'
    body+='<h2>Inspect ranks, allocations and contributions</h2><p>The table uses the actual historical decision date. Capital weight includes a sleeve’s cash; the intended ETF exposure is its weight times its daily signal. Portfolio attribution sums to total net return.</p><div class="controls"><label>Era <select id="pera"><option value="late">Later</option><option value="early">Earlier</option></select></label><label>Portfolio <select id="parm"><option value="equal">N15 equal capital</option><option value="risk">N15 risk parity</option><option value="all">Full pool equal</option></select></label><label>Decision <select id="pdate"></select></label></div><p id="pinfo"></p><div class="scroll"><table><thead><tr><th>Rank / ETF</th><th>63d return</th><th>63d Sharpe</th><th>252d return</th><th>252d Sharpe</th><th>Score</th><th>Capital</th><th>Intended ETF</th></tr></thead><tbody id="pranks"></tbody></table></div><details><summary>Full constituent attribution, worst first</summary><div class="scroll"><table><thead><tr><th>ETF</th><th>Net contribution</th><th>Fee / initial capital</th><th>Average held weight</th><th>Funded days</th><th>Fills</th></tr></thead><tbody id="pattrs"></tbody></table></div></details>'
    body+='<h2>Weakest cases and every ETF chart</h2><p>The weakest continuing strategy over the matched portfolio window is <b>TLT −18.56%</b> later and <b>MCHI −31.99%</b> earlier. The worst actual N15 equal-capital contributors are <b>IAT −1.53 percentage points</b> later and <b>XLY −2.48 points</b> earlier. Select either type below; they answer different questions.</p>'
    body+='<p><b>IAT:</b> the portfolio joins an existing up trade on 1 August 2024 at adjusted $45.00, then its daily exit sells on 6 August at $41.05 (about −8.9% including fees). It joins another ongoing trade on 2 December at $53.50 and sells on 12 December at $51.03. A strong trailing rank can therefore buy a mature trend at a worse price than the shadow entry. The March–April 2025 shadow loss of −15.76% is <em>not</em> taken by this N15 portfolio; IAT was unselected then.</p><p><b>XLY:</b> selection buys the existing rebound on 1 June 2022 at $74.72; the protective exit sells on 13 June at $67.07 (about −10.3% after fees). The September 2022 entry at $77.75 exits at $71.44 after the fast-down signal. These are repeated failed rebounds, compounded by delayed recognition and overnight gaps. A fixed closing-stop distance is not a maximum loss. TLT and MCHI are mostly avoided by N15, illustrating that filtering obvious laggards can help locally without making the overall ranking useful.</p>'
    body+='<div class="controls"><label>Era <select id="era"><option value="late">Later</option><option value="early">Earlier</option></select></label><label>ETF <select id="etf"></select></label><label>From <input id="from" type="date"></label><label>To <input id="to" type="date"></label><button id="full">Full window</button><button id="weakest">Weakest shadow</button><button id="worstcontributor">Worst N15 equal contributor</button></div><p id="chartmetrics"></p><p>Hover for exact daily values. Click two chart dates to select an interval. Green/red triangles are shadow fills; orange circles are actual N15 equal-capital portfolio fills (including allocation changes).</p><p id="readout" class="readout">Move over the chart for the date and daily OHLC.</p><svg id="chart" viewBox="0 0 1200 955" role="img" aria-label="ETF price, volume, states, stops, and NAV"></svg><details open><summary>Actual N15 equal-capital fills in selected interval</summary><div class="scroll"><table><thead><tr><th>Date</th><th>Side</th><th>Reason</th><th>Price</th><th>Notional / initial capital</th><th>Fee / initial capital</th></tr></thead><tbody id="actualfills"></tbody></table></div></details><details><summary>Underlying shadow trades (full trade outcome, including pre-window entry if carried)</summary><div class="scroll"><table><thead><tr><th>Entry</th><th>Exit</th><th>Entry price</th><th>Exit price</th><th>Net trade return</th><th>Reason</th><th>Initial risk distance</th></tr></thead><tbody id="trades"></tbody></table></div></details><details><summary>Frozen fitted parameters and training cutoff</summary><pre id="parameters"></pre></details>'
    body+='<details><summary>Ready-to-open static weakest charts</summary>'+''.join(f'<h3>{w["symbol"]} · {w["era"]}</h3><img class="figure" src="{w["symbol"]}_{w["era"]}.png" alt="Weakest ETF chart"/>' for w in weak)+'</details>'
    body+='<h2>Costs, delay, timing and shorter rank memory</h2><p>All primary methods were tested at 5/10/20 bp per side and zero/one extra execution session. A one-session delay changes both the ETF strategy fills and portfolio allocation fills. The earlier equal-capital return changes from −4.19% to +2.99% at 5 bp with the extra delay: timing sensitivity is material, not evidence that delay is intrinsically better.</p>'
    cols=[('era','Era',str),columns[0],('cost_bp','bp/side',str),('delay','Extra days',str),*columns[1:6],('cost_bp_annual','bp/year',lambda x:f'{x:.1f}')]
    body+='<details><summary>All primary cost/delay results</summary>'+table([r for r in rows if r['arm'] in ('equal','risk','all')],cols)+'</details>'
    body+='<details><summary>Declared 10% dynamic target-change control</summary>'+table([r for r in rows if r['arm'].endswith('_dynamic')],cols)+'</details>'
    body+='<p><b>Why the dynamic control trades so much:</b> a single equal-capital sleeve switching between ETF and cash changes the cash-inclusive L1 target by 2/15 = 13.33%, exceeding the 10% trigger even if the rank membership is unchanged. The later equal-capital arm therefore adopts 538 allocations over 680 sessions versus 33 monthly allocations. Daily strategy signals already execute; these additional events also rerank and rebudget the pool. This tests the declared threshold, not a general rejection of dynamic selection.</p>'
    body+='<p>The separately declared 21/126-day rank sensitivity improves the primary returns in both periods: equal capital +23.68% later / −2.03% earlier; risk parity +21.92% / −1.65%. It still does not beat the unranked pool’s Sharpe in either primary period. Only 5 bp / no extra delay was declared for this diagnostic; it is not a new winner or adopted base.</p>'
    body+='<details><summary>Shorter rank-memory diagnostic</summary>'+table([r for r in rows if r['arm'].endswith('_short')],cols)+'</details>'
    body+='<details><summary>FR25 comparison on exactly shared dates, through 12 October 2026</summary><p>Same audited USD panel, fees, delay and fractional cash/share ledger, replaying FR25’s frozen monthly targets. FR25 has its own universe and risk allocation and is not a rank-only ablation; this is not its live CNH account. It remains an empirical benchmark. Later-period dependence and prior research selection apply to it too.</p>'+table([r for r in matched if r['cost_bp']==5 and r['delay']==0 and r['arm'] in ('equal','risk','all','FR25','raw_momentum')],[columns[0],*columns[1:4],columns[5]])+'</details>'
    body+='<h2>Exact portfolio mathematics</h2><p>Let Vⁱₜ be continuously updated net virtual-strategy value, including cash days. All features below are known at decision close t.</p>'
    body+=eq(r'r^i_t=V^i_t/V^i_{t-1}-1,\quad R^i_{h,t}=\prod_{u=t-h+1}^{t}(1+r^i_u)-1,\quad S^i_{h,t}=\sqrt{252}\,\bar r^i_{h,t}/s^i_{h,t}')
    body+=eq(r'q^i_t=\frac{1}{4}\left[\Pi_t(R^i_{63,t})+\Pi_t(S^i_{63,t})+\Pi_t(R^i_{252,t})+\Pi_t(S^i_{252,t})\right],\quad J_t=\operatorname{Top15}_i(q^i_t)')
    body+='<p>Π(x)=(average rank(x)−1)/(M−1), ascending; combined-score ties use ticker. BIL is excluded. Require complete aligned history, at least two nonzero returns and nonzero volatility in both windows. No positive-return gate. If fewer than 15 qualify, use those available; if none, retain cash. Actual primary selections had 15 members.</p>'
    body+=eq(r'\Sigma_t=0.5\widehat\Sigma_t+0.5\operatorname{diag}(\widehat\Sigma_t)+\operatorname{diag}\left[\max(0,0.05^2-\operatorname{diag}(\widehat\Sigma_t))\right]')
    body+=eq(r'\widehat\Sigma_t=252\operatorname{Cov}(r_{t-251:t}^{J_t}),\quad x^*=\arg\min_{x_i>0}\left(\frac{1}{2} x^T\Sigma_t x-\sum_i\frac{1}{|J_t|}\log x_i\right),\quad b_i=x_i^*/\sum_j x_j^*')
    body+='<p>Equal capital uses bᵢ=1/|J|. Risk parity uses the formula above; it is full covariance equal-risk contribution, not inverse variance. Both allocate total sleeve capital of one, without leverage. A new member joins its existing shadow state and closing-stop history; its actual purchase price may differ from the shadow entry. Leaving membership liquidates actual holdings without resetting its virtual strategy.</p>'
    body+=eq(r'a_t=(b_{1,t}z_{1,t},\ldots,b_{M,t}z_{M,t},1-\sum_i b_{i,t}z_{i,t}),\quad D_t=\|a_t-a_{\rm last\ adopted}\|_1')
    body+='<p>z is the close-time desired long state. Monthly adopts at month-end; the dynamic control additionally adopts when D≥0.10. Compare with the last actually adopted theoretical target, including cash. An allocation in transit is immutable and blocks another allocation until executed; daily strategy signals still operate. Pending exits take priority at an allocation open.</p>'
    body+=eq(r'V^+=V^--c\sum_i|b_i h_i V^+-q_i^-O_i|,\quad q_i^+=b_i h_iV^+/O_i,\quad C_i^+=b_i(1-h_i)V^+')
    body+='<p>At an allocation open, h is the executable delayed shadow holding state, q the actual adjusted units, O the open, and c the per-side cost. Solve the self-financing equation and trade only the net difference. Between allocations, each sleeve buys with its own cash or sells its own shares; it is not reweighted daily. Daily P&amp;L is old units × (open−prior close) + new units × (close−open) − fees. Summing it by ETF exactly reconciles portfolio return. Frozen shadow NAV drives ranking only; its fees are not charged again to the portfolio.</p>'
    body+='<div class="flow">Audit/hash check → Replay all frozen ETF strategies → Wait 252 post-fit sessions → Month-end four-metric ranks → Top 15 → Equal capital / strategy covariance risk parity → Next-open net allocation → Daily shadow signals + retained sleeve cash → Record actual NAV, costs and attribution → Repeat</div>'
    body+='<h2>Evidence, limits and next decision</h2><p>106 portfolio scenarios, 612 exactly reproduced shadow cases. Independent cash/share ledger maximum value error '+f'{audit["independent_ledger_max_error"]:.2g}'+', contribution reconciliation error '+f'{audit["contribution_max_error"]:.2g}'+'. ERC maximum relative contribution error '+f'{audit["erc_max_error"]:.2g}'+'. See <a href="validation.json">validation</a>, <a href="native-checks.json">native accounting checks</a> and <a href="protocol.json">frozen protocol</a>.</p>'
    body+='<p>Native Windows LEAN fixtures independently compare multiasset whole-share/cent-price accounting against the app reference, using execution-open target oracles reconstructed from frozen fills. They do not independently reproduce HMM inference, ranking, optimization or fractional execution. The independent fractional ledger and causal prefix tests cover separate contracts.</p>'
    body+='<ul><li>The 252-session warmup excludes the 2020 crash and 2023 from funded portfolio performance. Models are frozen at 2019/2022 cutoffs; old parameters may age. Neither chronology is a fresh statistical holdout.</li><li>Audited adjusted OHLC and raw share volume are pinned to publication batch '+s.read(s.OUT/'protocol.json')['fr25']['batch']+'. Auditing does not prove historical publication availability or remove retrospective universe bias. No missing observations were filled. ETF listing/training coverage differs between eras.</li><li>No cash interest, taxes, FX, market impact, intraday stop or bid/ask simulation. Fixed costs are stress assumptions, not empirical execution estimates. Fractional adjusted units are research accounting; tradable raw-unit corporate actions require production implementation.</li><li>Portfolio beta and overlapping country/sector exposure remain. Fifteen ETFs do not guarantee fifteen independent risks. Equal strategy-risk budgeting depends on noisy covariance and intermittent exposure.</li><li>Training used inherited single-ETF thresholds and many prior research rounds. This run freezes them, but cannot erase their research-selection history.</li></ul>'
    body+='<p><b>Research recommendation:</b> retain equal capital as the transparent N15 reference and the full-pool sleeves as the diversification control. Do not adopt the ranking layer yet. First inspect IAT/XLY allocation timing and TLT/MCHI trade failures; then test whether rankings should forecast incremental future strategy returns rather than reward past cumulative performance. Keep N=15 fixed during that isolation. Separately test a realistic cash-yield implementation and a predeclared correlation/concentration constraint; neither improvement is established by this run. No monitoring, funding or broker settings changed.</p>'
    body+='<p><a href="results.json">All numerical results</a> · <a href="attribution.json">Full constituent attribution</a> · <a href="rank-ic.json">Monthly IC observations</a> · <a href="fr25-matched.json">Matched FR25 results</a> · <a href="qa.json">Report checks</a></p>'
    payload=dict(charts=charts,models=s.read(s.SYNTH/'selected-models.json'),weakest={w['era']:w['symbol'] for w in weak},
        portfolio={k:dict(symbols=z['symbols'],decisions=z['decisions'],ranks=z['ranks'],fills=z['fills']) for k,z in detail.items() if k.split('_')[1] in ('equal','risk','all') and k.endswith('c5d0') and 'dynamic' not in k},attribution=attrs)
    s.gzwrite(s.OUT/'report-data.json.gz',payload)
    original=(s.ROOT/'scripts/assets/trend-sleeve-synthesis.js').read_text(encoding='utf-8')
    js="const el=id=>document.getElementById(id),pct=x=>x==null?'—':(100*x).toFixed(2)+'%',num=x=>x==null?'—':x.toFixed(3);\n"+original[original.index('const symbols='):]
    js=js.replace("el('n').value='15';el('weight').value='equal';el('era').value='late';el('etf').value='CORN';rankTable();choose();", "el('era').value='late';el('etf').value=DATA.weakest.late;choose();")
    js='\n'.join(line for line in js.splitlines() if "el('n').addEventListener" not in line and "el('rankrows').addEventListener" not in line)
    js+='\n'+(s.ROOT/'scripts/assets/trend-sleeve-portfolio.js').read_text(encoding='utf-8')
    (s.OUT/'controls.js').write_text(js,encoding='utf-8')
    encoded=base64.b64encode((s.OUT/'report-data.json.gz').read_bytes()).decode()
    loader="(async()=>{try{const raw=Uint8Array.from(atob('"+encoded+"'),c=>c.charCodeAt(0));const text=await new Response(new Blob([raw]).stream().pipeThrough(new DecompressionStream('gzip'))).text();globalThis.DATA=JSON.parse(text);"+js+"}catch(e){document.getElementById('readout').textContent='Inspector could not load: '+e.message;console.error(e)}})();"
    css='body{font:16px/1.6 system-ui,sans-serif;color:#173843;background:#f4f7f8;margin:0 auto;max-width:1240px;padding:32px}h1{font-size:38px;line-height:1.15}h2{margin-top:46px}h3{margin-top:25px}.subtitle,.note{color:#56717b}.verdict{padding:22px;background:#e1eeeb;border-left:5px solid #137e79;border-radius:6px}.figure{width:100%;height:auto;background:white}.scroll{overflow:auto;max-height:530px}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:9px 11px;border-bottom:1px solid #dce6e9;white-space:nowrap;text-align:right}th:first-child,td:first-child{text-align:left}th{position:sticky;top:0;background:#e6eef1}details{margin:15px 0;background:#edf2f4;padding:12px}summary{cursor:pointer;font-weight:600}select,input,button{font:inherit;padding:7px;border:1px solid #9fb4bd;border-radius:4px;background:white}button{cursor:pointer}.controls{display:flex;gap:12px;flex-wrap:wrap;align-items:end}.controls label{display:grid;font-size:14px}.readout{position:sticky;top:0;background:#173843;color:white;padding:12px;z-index:2;font-size:14px}svg#chart{width:100%;background:white;touch-action:pan-y}pre{font-size:12px;white-space:pre-wrap}.equation{overflow:auto;background:white;padding:8px;margin:12px 0}.equation svg{max-width:100%;height:auto}.flow{padding:22px;background:#e6efee;border:1px solid #bad0ce}a{color:#096b79}.selected{background:#e3f2eb}li{margin:10px 0}'
    (s.OUT/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>N15 strategy portfolio backtest</title><style>'+css+'</style><body>'+body+'<script>'+loader+'</script></body></html>',encoding='utf-8')
    print('Report built',len(charts),'ETF charts',flush=True)


if __name__=='__main__':main()
