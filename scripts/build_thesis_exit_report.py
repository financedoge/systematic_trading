"""Inspectable three-arm thesis-exit study and weakest cases."""
import gzip
from io import BytesIO
import json
from pathlib import Path
import re

import numpy as np
import research_thesis_exit as study

NAMES={'control':'A: current algorithm','thesis':'B: exit when the upward thesis fails','directional':'C: also exit shallow declines'}


def summary(rows):
    lookup={(r['symbol'],r['era'],r['arm'],r['cost_bp'],r['delay']):r for r in rows};out=[]
    for era,*_ in study.ERAS:
        for cost,delay in study.FRICTIONS:
            for arm in study.model.ARMS:
                a=[r for r in rows if r['era']==era and r['arm']==arm and r['cost_bp']==cost and r['delay']==delay and r['symbol']!='BIL']
                b=[lookup[r['symbol'],era,'control',cost,delay] for r in a]
                sg=float(np.median([x['sharpe'] for x in a])-np.median([x['sharpe'] for x in b]))
                qg=float(np.quantile([x['cagr'] for x in a],.25)-np.quantile([x['cagr'] for x in b],.25))
                guard=float(np.mean([x['cagr']>=y['cagr']-.01 and x['maxdd']>=y['maxdd']-.02 for x,y in zip(a,b,strict=True)]))
                out.append(dict(era=era,cost_bp=cost,delay=delay,arm=arm,cases=len(a),enabled=sum(x['enabled'] for x in a),
                    median_sharpe=float(np.median([x['sharpe'] for x in a])),median_cagr=float(np.median([x['cagr'] for x in a])),
                    lower_quartile_cagr_gain=qg,median_sharpe_gain=sg,guard_fraction=guard,passed=sg>0 and qg>0 and guard>=.9,
                    improved=sum(x['cumulative']>y['cumulative']+1e-10 for x,y in zip(a,b,strict=True)),
                    worse=sum(x['cumulative']<y['cumulative']-1e-10 for x,y in zip(a,b,strict=True)),
                    median_annual_cost_bp=float(np.median([x['cost_bp_annual'] for x in a])),
                    median_turnover=float(np.median([x['turnover_annual'] for x in a])),
                    yearly={year:float(np.median([x['yearly'][year] for x in a])) for year in a[0]['yearly']}))
    return out


def figure(c,symbol,era,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    days=np.array(c['days'],dtype='datetime64[D]');a=c['arms']['directional'];active=days>=np.datetime64(c['evaluation_start'])
    fig,axes=plt.subplots(6,1,figsize=(14,13),sharex=True,layout='constrained',height_ratios=[2,.6,.8,.6,.8,1.2])
    axes[0].plot(days,c['close'],color='#173d54',label='Adjusted close');axes[0].plot(days,np.asarray(a['stop'],float),color='#bd5260',label='Adopted stop')
    for e in a['trades']:
        x=np.datetime64(e['entry_date']);y=np.datetime64(e['exit_date']) if e['exit_date'] else days[-1]
        axes[0].axvspan(x,y,color='#008675',alpha=.07);axes[0].scatter(x,e['entry'],color='#008675',marker='^',s=30)
        if e['exit_date']:axes[0].scatter(y,e['exit_price'],color='#bd5260',marker='v',s=30)
    axes[0].legend(fontsize=8);axes[0].set_ylabel('Adjusted USD')
    axes[1].bar(days,np.asarray(c['volume'],float)/1e6,color='#9aabb6',width=1.5);axes[1].set_ylabel('Raw volume (m)')
    for key,label,color in [('fast_up','Up','#008675'),('neutral','Neutral','#b39b50'),('fast_down','Down','#bd5260')]:
        axes[2].plot(days[active],np.asarray(c[key])[active],color=color,label=label)
    axes[2].set_ylabel('Fast states');axes[2].legend(fontsize=8,ncol=3);axes[2].set_ylim(0,1)
    for key,label,color in [('slow_up','Slow up','#008675'),('slow_down','Slow down','#bd5260')]:
        axes[3].plot(days[active],np.asarray(c[key])[active],color=color,label=label)
    axes[3].legend(fontsize=8,ncol=2);axes[3].set_ylim(0,1)
    for key,label,color in [('effective_down','Effective down','#8154a5'),('exit_threshold','Down exit threshold','#bd5260'),('thesis_floor','Up-thesis floor','#c68b26')]:
        axes[4].plot(days,np.asarray(a[key],float),color=color,label=label)
    axes[4].legend(fontsize=8,ncol=3);axes[4].set_ylim(0,1)
    for name,color in [('control','#91a3b0'),('thesis','#c78b28'),('directional','#008675')]:
        axes[5].plot(days,np.asarray(c['arms'][name]['nav'],float),color=color,label=NAMES[name])
    axes[5].legend(loc='upper left',fontsize=8);axes[5].set_ylabel('NAV / initial 100')
    for ax in axes:ax.grid(alpha=.15);ax.axvline(np.datetime64(c['evaluation_start']),color='#777',ls='--',lw=.7)
    axes[5].xaxis.set_major_locator(dates.MonthLocator(interval=6));axes[5].xaxis.set_major_formatter(dates.DateFormatter('%Y-%m'))
    rule=c['selection']['arms']['directional']['rule']
    fig.suptitle(f'{symbol} | {era} | C: thesis exit + shallow decline evidence\nTraining-selected addition: {rule}; actual fills, protection and all three NAV paths')
    fig.savefig(path,dpi=130);plt.close(fig)


def equations():
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    formulas=[r'a_t=\mathbf{1}\{p^{slow}_{up,t}\geq0.7\},\quad \theta_t=\theta(1-0.5a_t),\quad k_t=k+2a_t',
        r'c_t=\left(c_{t-1}+1\right)\mathbf{1}\{p^{fast}_{up,t}<\theta_t\}',
        r'B:\quad \mathrm{exit}_t=\mathrm{parent\ exit}_t\ \mathrm{or}\ \{c_t\geq k_t,\ b^{fast}_t\leq0\}',
        r'g_t=\Phi\left(\frac{-0.02\sigma_{train}-b^{fast}_t}{\sqrt{V^{fast}_t}}\right)',
        r'\widetilde p_{down,t}=p^{HMM}_{down,t}+p^{HMM}_{neutral,t}g_t',
        r'C:\quad \mathrm{exit}_t=\mathrm{exit}_{B,t}\ \mathrm{or}\ \{\widetilde p_{down,t}\geq e_t\}',
        r'\theta\in\{0.1,0.2,0.3\},\quad k\in\{2,3\},\quad\mathrm{fill}=t+1+delay',
        r'\mathrm{training\ guards}:\quad CAGR\geq CAGR_A-0.01,\quad DD\leq DD_A+0.02,\quad Sharpe>Sharpe_A']
    parts=[]
    for j,formula in enumerate(formulas):
        b=BytesIO();mathtext.math_to_image('$'+formula+'$',b,prop=FontProperties(size=15),format='svg',color='#17384d')
        svg=b.getvalue().decode();svg=svg[svg.index('<svg'):]
        svg=re.sub(r'id="([^"]+)"',lambda m:f'id="eq{j}_{m[1]}"',svg);svg=re.sub(r'xlink:href="#([^"]+)"',lambda m:f'xlink:href="#eq{j}_{m[1]}"',svg)
        parts.append('<div class="equation">'+svg+'</div>')
    study.write(study.OUT/'equations.json',formulas)
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(formulas),1,figsize=(16,8),layout='constrained')
    for ax,formula in zip(axes,formulas,strict=True):ax.axis('off');ax.text(.01,.3,'$'+formula+'$',fontsize=13)
    fig.savefig(study.OUT/'equation-proof.png',dpi=120,bbox_inches='tight');plt.close(fig)
    return ''.join(parts)


def main():
    study.verified();receipt=json.loads((study.OUT/'validation.json').read_text())
    assert study.prior.study.digest(study.OUT/'chart-data.json.gz')==receipt['chart_sha256']
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()));rows=json.loads((study.OUT/'asset-results.json').read_text())
    sums=summary(rows);study.write(study.OUT/'summary.json',sums)
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0]
    weakest={era:min((r for r in primary if r['era']==era and r['arm']=='directional' and r['symbol']!='BIL'),key=lambda r:(r['cumulative'],r['symbol'])) for era,*_ in study.ERAS}
    focus={('INDA','late'),('WEAT','late'),('GLD','late'),('GLD','early'),('USO','late'),('TLT','late'),*((r['symbol'],era) for era,r in weakest.items())}
    for symbol,era in sorted(focus):figure(charts[f'{symbol}_{era}'],symbol,era,study.OUT/f'{symbol}_{era}.png')
    pct=lambda x:'—' if x is None else f'{100*x:+.2f}%'
    st=''.join(f'<tr><td>{r["era"]}</td><td>{NAMES[r["arm"]]}</td><td>{r["enabled"]}/{r["cases"]}</td><td>{r["median_sharpe"]:.3f}</td><td>{pct(r["median_cagr"])}</td><td>{pct(r["guard_fraction"])}</td><td>{r["improved"]}/{r["worse"]}</td><td>{r["median_annual_cost_bp"]:.1f}</td></tr>' for r in sums if r['cost_bp']==5 and r['delay']==0)
    lookup={(r['symbol'],r['era'],r['arm']):r for r in primary};pt=''
    for era,*_ in study.ERAS:
        for r in sorted((r for r in primary if r['era']==era and r['arm']=='directional'),key=lambda r:r['cumulative']):
            a,b=lookup[r['symbol'],era,'control'],lookup[r['symbol'],era,'thesis']
            pt+=f'<tr><td>{r["symbol"]}</td><td>{era}</td><td>{pct(a["cumulative"])}</td><td>{pct(b["cumulative"])}</td><td>{pct(r["cumulative"])}</td><td>{r["sharpe"]:.3f}</td><td>{pct(-r["maxdd"])}</td><td>{r["closed_trades"]}</td><td>{r["rule"]}</td></tr>'
    exports=' · '.join(f'<a href="{symbol}_{era}.png">{symbol} {era} figure</a>' for symbol,era in sorted(focus))
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Exit when the upward thesis fails</title><style>body{font:16px/1.5 system-ui;color:#17384d;background:#f5f8fa;max-width:1280px;margin:34px auto;padding:0 20px}h1,h2{line-height:1.2}h2{margin-top:38px}a{color:#006b70}.note{background:#fff0d7;border-left:4px solid #b47b22;padding:16px}.card{background:white;padding:18px;border:1px solid #d9e3e9;margin:14px 0}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center}button,select,input{font:inherit;padding:7px;border:1px solid #b4c5ce;border-radius:5px;background:white}button{cursor:pointer}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:7px 9px;border-bottom:1px solid #e2e8ed;text-align:right}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}#chart{width:100%;height:auto}#readout{min-height:64px}.equation{overflow:auto;padding:9px;background:white;margin:5px 0}.equation svg{max-width:100%;height:auto}small{color:#536b7b}</style>
<h1>Exit when the upward thesis fails</h1><p>27 October 2026 · Full supported ETF pool · Three single-ETF algorithms</p>
<p class="note">The INDA loss suggested that waiting for a strong down-state classification can keep a failed reversal open. This round tests loss of up-state support and resolves HMM-neutral declines using the existing continuous slope filter. All exit settings are selected per ETF from training data. These previously inspected eras remain development evidence.</p>
<h2>Three comparisons</h2><ul><li><b>A — current algorithm:</b> the preceding loss/HMM-reset strategy, reproduced exactly.</li><li><b>B — exit when the upward thesis fails:</b> add a persistent low up-state probability exit when fast slope is nonpositive. Strong slow uptrends get a lower floor and two extra confirming closes.</li><li><b>C — also exit shallow declines:</b> add the fast filter's directional evidence to HMM-neutral probability before checking the down-exit threshold. This is an exit-level correction, not a refitted HMM.</li></ul>
<p>For each ETF and era, fit B and C independently over six threshold/persistence choices. If none improve training Sharpe while preserving return/drawdown and producing at least three closed trades, disable the addition. Disabled rows retain A exactly. The existing nine-policy Bayesian learner is still active, with training seeds and shadow trades using the selected exit. B versus C therefore includes their separately selected settings and learning paths.</p>
<h2>Inspect every ETF</h2><p id="weakestNote"></p><div class="controls"><label>Era <select id="era"><option value="late">2023–2026</option><option value="early">2020–2022</option></select></label><label>ETF <select id="etf"></select></label><label>Algorithm <select id="arm"><option value="control">A · Current algorithm</option><option value="thesis">B · Upward thesis fails</option><option value="directional">C · Also shallow declines</option></select></label><button id="weakest">Weakest C case</button><button id="weat">WEAT</button></div>
<div class="controls"><label>From <input id="from" type="date"></label><label>To <input id="to" type="date"></label><button id="reset">Full context</button><button id="inda">INDA incident</button><button id="gold">GLD 2020 failure</button></div>
<div class="card"><p id="metrics"></p><small id="parameters"></small><p id="readout">Hover for the exact date and state probabilities; click two dates to select a period.</p><svg id="chart" viewBox="0 0 1200 1290"></svg></div>
<details><summary>Actual Bayesian policy grid</summary><table><tr><th>ID</th><th>Up entry</th><th>Down exit</th><th>Down exit in slow up</th><th>Distance normal</th><th>Distance slow up</th></tr><tbody id="grid"></tbody></table></details>
<details><summary>Actual trades and exit reasons</summary><table><tr><th>Entry</th><th>Exit</th><th>Entry policy</th><th>Exit policy</th><th>Net return</th><th>Exit reason</th></tr><tbody id="trades"></tbody></table></details>
<details><summary>Warnings, belief resets and policy changes</summary><div class="scroll"><table><tr><th>Known date</th><th>Policy change</th><th>Reason</th><th>Full reset?</th><th>Payoff mean</th><th>Win estimate</th><th>Evidence count</th></tr><tbody id="events"></tbody></table></div></details>
<p>__EXPORTS__</p><h2>Full-pool results</h2><div class="scroll"><table><tr><th>Era</th><th>Algorithm</th><th>Enabled / risky ETFs</th><th>Median Sharpe</th><th>Median CAGR</th><th>Within A guards</th><th>Better / worse return</th><th>Median annual cost (bp)</th></tr>__SUMMARY__</table></div>
<p>Primary: 5 bp per side, next-open fills. BIL remains visible as a cash-like ETF reference and is excluded from risky-pool summaries. A has no new addition, so its enabled count is zero. Full-pool acceptance requires improved median Sharpe and lower-quartile CAGR, with at least 90% of ETFs within 1 percentage point CAGR and 2 percentage points maximum drawdown of A. All six cost/delay cases and annual slices are in the linked summary.</p>
<div id="findings">__FINDINGS__</div>
<details open><summary>Every ETF — worst C return first in each era</summary><div class="scroll"><table><tr><th>ETF</th><th>Era</th><th>A return</th><th>B return</th><th>C return</th><th>C Sharpe</th><th>C drawdown</th><th>C trades</th><th>C training-selected exit</th></tr>__POOL__</table></div></details>
<h2>Exact mathematical rules</h2>__EQUATIONS__
<p>Here p denotes the existing filtered state probability, b the fast log-price slope, V its Kalman posterior variance, σ the training daily log-return dispersion, and Φ the standard normal CDF. The count uses each day's context-specific floor and must also have a nonpositive current fast slope. Strong slow uptrend means p(slow up) ≥ 0.7, even if the old policy did not use context for stop widths. The original down-exit threshold e varies with the selected Bayesian policy. For a Gaussian-slope trading family, C uses its existing down probability without applying the neutral correction twice.</p>
<p>The corrected down score is a heuristic combination of two estimates derived from the same prices; it is not a newly calibrated posterior or formal hypothesis-test p-value. It tests the economic meaning of neutral at the exit layer. HMM parameters, Kalman parameters and original volatility remain fixed. A separate predictive likelihood-ratio test, full market-model refitting, support-based stops and hard risk caps are not implemented in this component round.</p>
<h2>Fitting, learning and execution</h2>
<p>Training selection uses the last 756 return sessions before each era's cutoff, with a funded flat start one close earlier. Market models were fitted on the full pre-evaluation training history, including the selection segment; this is in-sample hyperparameter fitting, not nested validation. Each candidate uses the fixed original base policy for selection. Choose maximum net Sharpe subject to the displayed guards and at least three closed trades; ties prefer CAGR, then smaller floor and longer count. Six choices plus disabling the addition are frozen before fitting.</p>
<p>After selection, recompute all nine policy payoff seeds from full training shadow trades under that same exit. Existing daily forgetting, proper priors, four-trade evidence cap, hard resets, confirmation/cooldowns and fresh-outcome rules remain. Current-position exits and the shadow trades used for learning share the new rule. Actual adaptive results can therefore differ from the fixed-policy training scores. Existing initial/trailing protection is unchanged and never loosens. Re-entry still requires rearming below 0.5 and a later eligible upswing; a thesis exit below 0.3 naturally allows that rearming.</p>
<p>Decisions use completed closes and execute at the next open, with an additional-session delay sensitivity. Pending orders remain binding. Fees are 5/10/20 bp each side, with no annual cost ceiling. Fractional cash-funded adjusted units, zero-interest idle cash, terminal holdings marked. Raw volume is chart context only. Published audited histories and input hashes are pinned to the parent batch; auditing does not establish historical publication availability. No downloaded prices or portfolio overlay is used.</p>
<p><a href="asset-results.json">All results and yearly returns</a> · <a href="summary.json">All cost/delay comparisons</a> · <a href="fits.json">Every training choice and score</a> · <a href="protocol.json">Frozen recipe</a> · <a href="validation.json">Replay and accounting checks</a> · <a href="native-checks.json">Native single-ETF checks</a></p>
<script>const DATA = __DATA__;
__SCRIPT__</script></html>'''
    def display(obj):
        if isinstance(obj,float):return round(obj,7)
        if isinstance(obj,list):return [display(x) for x in obj]
        if isinstance(obj,dict):return {k:display(v) for k,v in obj.items()}
        return obj
    script=study.ROOT/'scripts/assets/thesis-exit-script.js';findings=study.OUT/'findings.html'
    for token,value in dict(EXPORTS=exports,SUMMARY=st,POOL=pt,EQUATIONS=equations(),
        FINDINGS=findings.read_text(encoding='utf-8') if findings.exists() else '<p>Case analysis is being completed.</p>',
        DATA=json.dumps(display(dict(charts=charts,rows=primary,weakest=weakest)),separators=(',',':')).replace('</','<\\/'),SCRIPT=script.read_text(encoding='utf-8')).items():html=html.replace('__'+token+'__',value)
    (study.OUT/'index.html').write_text(html,encoding='utf-8');study.write(study.OUT/'weakest-cases.json',weakest)
    study.write(study.OUT/'manifest.json',dict(files={p.name:study.prior.study.digest(p) for p in study.OUT.iterdir() if p.is_file() and p.name!='manifest.json'},
        report_code={str(p.relative_to(study.ROOT)).replace(chr(92),'/'):study.prior.study.digest(p) for p in (Path(__file__),script,study.ROOT/'tests/thesis_exit_controls.cjs',study.ROOT/'scripts/validate_thesis_exit.py')}))
    print(json.dumps(dict(charts=len(charts)*3,weakest={e:r['symbol'] for e,r in weakest.items()})))


if __name__=='__main__':main()
