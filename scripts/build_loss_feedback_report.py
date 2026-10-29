"""Compact mathematical report, all ETF charts and weakest-case figures."""
import gzip
from io import BytesIO
import json
import re

import numpy as np

import research_loss_feedback as study

NAMES={'fixed':'A: existing policy','streak':'B: streak feedback','severity':'C: streak + large-loss / stop warnings'}


def summary(rows,ports):
    results=[];lookup={(r['symbol'],r['era'],r['arm'],r['cost_bp'],r['delay']):r for r in rows}
    for era,*_ in study.ERAS:
        for cost,delay in study.FRICTIONS:
            for arm in study.model.ARMS:
                a=[r for r in rows if r['era']==era and r['arm']==arm and r['cost_bp']==cost and r['delay']==delay and r['symbol']!='BIL']
                comparisons=[]
                for reference in ('fixed','streak'):
                    b=[lookup[r['symbol'],era,reference,cost,delay] for r in a]
                    guard=float(np.mean([x['cagr']>=y['cagr']-.01 and x['maxdd']>=y['maxdd']-.02 for x,y in zip(a,b,strict=True)]))
                    sg=float(np.median([r['sharpe'] for r in a])-np.median([r['sharpe'] for r in b]))
                    qg=float(np.quantile([r['cagr'] for r in a],.25)-np.quantile([r['cagr'] for r in b],.25))
                    comparisons.append(dict(reference=reference,median_sharpe_gain=sg,lower_quartile_cagr_gain=qg,guard_fraction=guard,
                        improves_return=sum(x['cumulative']>y['cumulative']+1e-10 for x,y in zip(a,b,strict=True)),
                        passed=sg>0 and qg>0 and guard>=.9))
                results.append(dict(era=era,cost_bp=cost,delay=delay,arm=arm,cases=len(a),
                    median_sharpe=float(np.median([r['sharpe'] for r in a])),median_cagr=float(np.median([r['cagr'] for r in a])),
                    median_pause_fraction=float(np.median([r['pause_sessions']/r['sessions'] for r in a])),comparisons=comparisons))
    pi={(r['era'],r['scenario'],r['cost_bp'],r['delay']):r for r in ports};gates=[]
    for r in ports:
        if not r['scenario'].startswith('severity_'):continue
        for name in (r['scenario'].replace('severity_','fixed_'),r['scenario'].replace('severity_','streak_')):
            b=pi[r['era'],name,r['cost_bp'],r['delay']]
            gates.append(dict(era=r['era'],scenario=r['scenario'],reference=name,cost_bp=r['cost_bp'],delay=r['delay'],
                passed=r['sharpe']>b['sharpe'] and r['cagr']>=b['cagr']-.01 and r['max_drawdown']>=b['max_drawdown']))
    return dict(asset_comparisons=results,portfolio_gates=gates)


def figure(c,symbol,arm,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    days=np.array(c['days'],dtype='datetime64[D]');a=c['arms'][arm]
    fig,axes=plt.subplots(5,1,figsize=(13,11),sharex=True,layout='constrained',height_ratios=[2,.6,.8,.4,1.1])
    axes[0].plot(days,c['close'],color='#173d54',label='Adjusted close')
    axes[0].plot(days,np.asarray(a['stop'],float),color='#bd5260',label='Adopted protection')
    tau=c['calibration']['winner_sigma']
    for e in a['trades']:
        x=np.datetime64(e['entry_date']);y=np.datetime64(e['exit_date']) if e['exit_date'] else days[-1]
        axes[0].axvspan(x,y,color='#008675',alpha=.08);axes[0].scatter(x,e['entry'],color='#008675',marker='^',s=32)
        if e['exit_date']:axes[0].scatter(y,e['exit_price'],color='#bd5260',marker='v',s=32)
        if arm=='severity' and tau is not None:
            floor=e['entry']*(1-max(tau,.001))*1.0005/.9995
            axes[0].plot([x,y],[floor,floor],color='#8656ad',ls=':',lw=1.2)
    axes[0].legend(loc='upper left',fontsize=8);axes[0].set_ylabel('Adjusted USD')
    axes[1].bar(days,np.asarray(c['volume'])/1e6,color='#9aabb6',width=1.5);axes[1].set_ylabel('Raw volume\n(millions)')
    active=days>=np.datetime64(c['evaluation_start'])
    axes[2].plot(days[active],np.asarray(c['fast_up'])[active],color='#008675',label='Fast up')
    axes[2].plot(days[active],np.asarray(c['slow_down'])[active],color='#bd5260',label='Slow down')
    axes[2].set_ylim(0,1);axes[2].set_ylabel('Probability');axes[2].legend(loc='upper left',fontsize=8)
    colors={'normal':'#cde7dc','defensive':'#f4d9a3','paused':'#edbdc5','probation':'#d9ccec'}
    for mode,color in colors.items():
        mask=(np.array(a['modes'])==mode)&active
        axes[3].fill_between(days,0,1,where=mask,step='post',color=color,label=mode)
    axes[3].set_yticks([]);axes[3].legend(ncol=4,fontsize=8,loc='center');axes[3].set_ylabel('Health')
    for name,color in [('fixed','#91a3b0'),('streak','#c78b28'),('severity','#008675')]:
        axes[4].plot(days,np.asarray(c['arms'][name]['nav'],float),color=color,label=NAMES[name])
    axes[4].set_ylabel('NAV / initial100');axes[4].legend(loc='upper left',fontsize=8)
    for ax in axes:ax.grid(alpha=.15);ax.axvline(np.datetime64(c['evaluation_start']),color='#777',ls='--',lw=.7)
    axes[4].xaxis.set_major_locator(dates.MonthLocator(interval=6));axes[4].xaxis.set_major_formatter(dates.DateFormatter('%Y-%m'))
    fig.suptitle(symbol+' | '+NAMES[arm]+'\nActual changed trades; next-open fills; purple dotted line = severity loss level',fontsize=13)
    fig.savefig(path,dpi=140);plt.close(fig)


def equations():
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    formulas=[r'\mathcal{G}=\{r_i:r_i>0,\ i\ \mathrm{closed\ in\ training}\},\quad \bar g=\frac{1}{n_g}\sum_{g\in\mathcal{G}}g',
      r'\sigma_g=\sqrt{\frac{\sum_{g\in\mathcal{G}}(g-\bar g)^2}{n_g-1}},\quad n_g\geq5,\qquad \tau=\max(\sigma_g,2f,10^{-6})',
      r'r_t^{\rm mark}=\frac{C_t}{O_e}\frac{1-f}{1+f}-1,\quad r_t^{\rm mark}<-\tau\ \Rightarrow\ \mathrm{exit\ at}\ O_{t+1+\Delta}',
      r'r_n^{\rm net}<-\tau\ \mathrm{or\ marked\ loss\ exit}\ \Rightarrow\ \mathrm{pause};\quad\mathrm{losing\ protective\ exit}\ \Rightarrow\ \mathrm{defensive}',
      r'L_n=(L_{n-1}+1)\,\mathbf{1}\{r_n^{\rm net}<0\},\quad L_n=3\Rightarrow h=0.5,\quad L_n=4\Rightarrow h=0',
      r'q_e=\frac{h_e B_{e^-}}{O_e(1+f)},\quad B_e=(1-h_e)B_{e^-},\quad N_t=B_t+q_t C_t',
      r'\ell_{t+1}=\max(\ell_t,M_t-k_t\hat\sigma_r O_e),\quad k_t=\frac{1}{2} k_t^{\rm original}\ \mathrm{in\ defensive/probation}']
    rendered=[]
    for j,formula in enumerate(formulas):
        buffer=BytesIO();mathtext.math_to_image('$'+formula+'$',buffer,prop=FontProperties(size=16),format='svg',color='#17384d')
        svg=buffer.getvalue().decode();svg=svg[svg.index('<svg'):]
        svg=re.sub(r'id="([^"]+)"',lambda m:f'id="eq{j}_{m[1]}"',svg)
        svg=re.sub(r'xlink:href="#([^"]+)"',lambda m:f'xlink:href="#eq{j}_{m[1]}"',svg)
        rendered.append('<div class="equation">'+svg+'</div>')
    study.write(study.OUT/'equations.json',formulas)
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(formulas),1,figsize=(18,6),layout='constrained')
    for ax,formula in zip(axes,formulas,strict=True):
        ax.axis('off');ax.text(.01,.3,'$'+formula+'$',fontsize=13)
    fig.savefig(study.OUT/'equation-proof.png',dpi=120,bbox_inches='tight');plt.close(fig)
    return ''.join(rendered)


def main():
    study.verified();receipt=json.loads((study.OUT/'validation.json').read_text())
    if study.prior.study.digest(study.OUT/'chart-data.json.gz')!=receipt['chart_sha256']:raise ValueError('Charts changed')
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()))
    rows=json.loads((study.OUT/'asset-results.json').read_text());ports=json.loads((study.OUT/'portfolio-results.json').read_text())
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0];s=summary(rows,ports);study.write(study.OUT/'summary.json',s)
    weakest={}
    for era,*_ in study.ERAS:
        weakest[era]=min((r for r in primary if r['era']==era and r['arm']=='severity' and r['symbol']!='BIL'),key=lambda r:(r['cumulative'],r['symbol']))
    focus={('WEAT','late'),('GLD','late'),*((r['symbol'],era) for era,r in weakest.items())}
    for symbol,era in sorted(focus):figure(charts[f'{symbol}_{era}'],symbol,'severity',study.OUT/f'{symbol}_{era}.png')
    pct=lambda x:'—' if x is None else f'{100*x:+.2f}%'
    primary_table=''.join(f'<tr><td>{r["era"]}</td><td>{NAMES[r["arm"]]}</td><td>{r["median_sharpe"]:.3f}</td><td>{pct(r["median_cagr"])}</td><td>{pct(r["median_pause_fraction"])}</td></tr>'
        for r in s['asset_comparisons'] if r['cost_bp']==5 and r['delay']==0)
    pool_table=''.join(f'<tr><td>{r["symbol"]}</td><td>{r["era"]}</td><td>{r["arm"]}</td><td>{pct(r["cumulative"])}</td><td>{r["sharpe"]:.3f}</td><td>{pct(r["maxdd"])}</td><td>{pct(r["exposure"])}</td><td>{r["closed_trades"]}</td></tr>'
        for r in sorted(primary,key=lambda r:(r['era']!='late',r['symbol'],r['arm'])))
    port_table=''.join(f'<tr><td>{r["era"]}</td><td>{r["scenario"]}</td><td>{pct(r["cagr"])}</td><td>{r["sharpe"]:.3f}</td><td>{pct(r["max_drawdown"])}</td><td>{r["annual_cost_bps"]:.1f}</td></tr>' for r in ports if r['cost_bp']==5 and r['delay']==0)
    exports=' · '.join(f'<a href="{symbol}_{era}.png">{symbol} {era} chart</a>' for symbol,era in sorted(focus))
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Large-loss warnings — full ETF test</title><style>body{font:16px/1.5 system-ui;color:#17384d;background:#f5f8fa;max-width:1280px;margin:34px auto;padding:0 20px}h1,h2{line-height:1.2}h2{margin-top:38px}a{color:#006b70}.note{background:#fff0d7;border-left:4px solid #b47b22;padding:16px}.card{background:white;padding:18px;border:1px solid #d9e3e9;margin:14px 0}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center}button,select,input{font:inherit;padding:7px;border:1px solid #b4c5ce;border-radius:5px;background:white}button{cursor:pointer}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:7px 9px;border-bottom:1px solid #e2e8ed;text-align:right}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}#chart{width:100%;height:auto}#readout{min-height:26px;font-variant-numeric:tabular-nums}.equation{overflow:auto;padding:9px;background:white;margin:5px 0}.equation svg{max-width:100%;height:auto}small{color:#536b7b}</style>
<h1>Large losses deserve an earlier warning</h1><p>26 October 2026 · Three fixed comparisons · 52 ETF universe · Training-only thresholds · Actual changed trades</p>
<p class="note"><b>The warning limits WEAT's damage, but this hard-pause response does not generalize.</b> WEAT changes from −32.51% to −5.36%, largely by remaining paused for925 sessions. Across the later risky pool, median Sharpe falls from0.412 to−0.102; GLD gives up substantial gains. Keep the warning as a research feature; do not promote this response.</p>
<p>First, all training thresholds were sealed. Then1,836 ETF/cost/delay cases and138 portfolio cases were evaluated. The unchanged control matches612 independent existing-simulator runs. All eras are previously inspected development evidence. Numerical results use pinned published audited prices and raw volume; no online prices were fetched.</p>
<h2>What each comparison means</h2><ul><li><b>A — existing policy:</b> the ETF's previously training-selected entry, fast trend exit and protection.</li><li><b>B — streak feedback:</b> three losses halve risk; four pause. Defensive/probation positions use half the previous protection distance and an earlier fast-down threshold. Fresh shadow evidence governs recovery.</li><li><b>C — streak plus large-loss/stop warnings:</b> B plus an exit request when net close-marked loss exceeds one training-winner sigma; a large realized/marked loss pauses immediately. An ordinary losing protective exit puts a normal strategy into defensive mode. A profitable trailing-stop exit alone does not warn.</li></ul>
<p>The loss triggering the warning remains in P&amp;L. A daily close signal fills at the next open (or one session later in the delay test), so gaps can exceed the threshold. Refit-review events are recorded; this experiment switches to predeclared defensive rules and shadow recovery, and does <b>not</b> perform online market-model refitting.</p>
<h2>Mathematical definition</h2>__EQUATIONS__
<p>Winning-trade standard deviation uses at least5 completed positive net training returns per ETF/cutoff. It is a scale comparison, not a Gaussian tail probability. When unavailable (CPER later and BIL), the sigma feature is disabled and explicitly reported; ordinary stop/streak rules remain. Training-selected outcome distributions can be optimistic. Initial account is flat for each era; all comparisons share this start, which differs from prior carried-position headline returns.</p>
<p>Paused recovery requires4 fresh reference trades entered after the pause, at least3 winners and positive sum risk-normalized and compounded net returns. Recovery uses25% entry risk;3 subsequent actual trades with at least2 winners and positive totals restore normal;2 consecutive probation losses pause again. Defensive recovery needs2 consecutive winners and positive phase totals. Cash earns0 in standalone ETF tests.</p>
<h2>Inspect any ETF</h2><p id="weakestNote"></p><div class="controls"><label>Era <select id="era"><option value="late">2023–2026</option><option value="early">2020–2022</option></select></label><label>ETF <select id="etf"></select></label><label>Policy <select id="arm"><option value="fixed">A · Existing</option><option value="streak">B · Streak</option><option value="severity">C · Large-loss / stop</option></select></label><button id="weakest">Weakest C case</button><button id="weat">WEAT</button></div>
<div class="controls"><label>From <input id="from" type="date"></label><label>To <input id="to" type="date"></label><button id="reset">Full context</button></div>
<div class="card"><p id="metrics"></p><small id="parameters"></small><p id="readout">Hover for exact dates or click two dates to inspect an interval.</p><svg id="chart" viewBox="0 0 1200 1090"></svg></div>
<details><summary>Actual trade ledger</summary><div class="scroll"><table><thead><tr><th>Entry</th><th>Exit</th><th>Health at entry</th><th>Budget fraction</th><th>Net unit return</th><th>Exit reason</th></tr></thead><tbody id="trades"></tbody></table></div></details>
<details><summary>Warnings and recovery events</summary><table><thead><tr><th>Known date</th><th>New health</th><th>Reason</th><th>Evidence</th></tr></thead><tbody id="events"></tbody></table></details>
<p>__EXPORTS__</p><h2>Pool summary</h2><table><tr><th>Era</th><th>Policy</th><th>Median Sharpe</th><th>Median CAGR</th><th>Median paused fraction</th></tr>__SUMMARY__</table>
<h2>Portfolio comparisons</h2><p>Selection: six momentum-ranked slots gated and scaled by the ETF health path; unused budget goes to BIL. Overlay: half the FR25 allocation remains, while the experimental half is multiplied by the ETF target; unused budget goes to BIL. A paused overlay therefore retains the incumbent half. Health is computed on the standalone theoretical ETF ledger, not inferred from portfolio fills. Dynamic adopts at10% cash-inclusive target distance or month end; monthly adopts at month end only. Controls use matched costs and execution delays. Dollar accounting; historical publication-vintage limitations remain.</p>
<table><tr><th>Era</th><th>Scenario</th><th>CAGR</th><th>Sharpe</th><th>Max drawdown</th><th>Annual cost bp</th></tr>__PORTS__</table>
<p>The later severity dynamic overlay raises Sharpe to1.470 and reduces drawdown to5.98%, but CAGR falls to10.93% versus13.18% for A and16.51% for FR25. That fails the declared return-preservation guard. Its higher Sharpe alone does not establish superiority.</p>
<p>A narrower positive result exists: monthly severity selection improves Sharpe/drawdown versus monthly A in both eras and all six friction settings, while staying within1 percentage point of CAGR. It does not consistently beat the streak policy or the simple momentum comparator. This deserves retention as a limited risk-allocation result, not a general ETF trading improvement.</p>
<details><summary>All ETF results: primary5bp/side, next open</summary><div class="scroll"><table><tr><th>ETF</th><th>Era</th><th>Policy</th><th>Net return</th><th>Sharpe</th><th>Max drawdown</th><th>Mean exposure</th><th>Closed trades</th></tr>__POOL__</table></div></details>
<p><a href="asset-results.json">All1,836 asset/friction cases</a> · <a href="portfolio-results.json">All138 portfolio cases</a> · <a href="calibration.json">Per-ETF training thresholds</a> · <a href="summary.json">Paired comparisons and guards</a> · <a href="protocol.json">Frozen recipe</a> · <a href="validation.json">Accounting validation</a> · <a href="native-checks.json">Independent native checks</a> · <a href="../../docs/loss-feedback-results-2026-10-26.md">Findings and next direction</a></p>
<script>const DATA = __DATA__;
__SCRIPT__</script></html>'''
    payload=dict(charts=charts,rows=primary,weakest=weakest)
    script=study.ROOT/'scripts/assets/loss-feedback-script.js'
    html=html.replace('__EQUATIONS__',equations()).replace('__EXPORTS__',exports).replace('__SUMMARY__',primary_table)
    html=html.replace('__PORTS__',port_table).replace('__POOL__',pool_table).replace('__DATA__',json.dumps(payload,separators=(',',':')).replace('</','<\\/')).replace('__SCRIPT__',script.read_text(encoding='utf-8'))
    (study.OUT/'index.html').write_text(html,encoding='utf-8');study.write(study.OUT/'weakest-cases.json',weakest)
    study.write(study.OUT/'manifest.json',dict(files={p.name:study.prior.study.digest(p) for p in study.OUT.iterdir() if p.is_file() and p.name!='manifest.json'},
        report_code={str(p.relative_to(study.ROOT)).replace(chr(92),'/'):study.prior.study.digest(p) for p in (__import__('pathlib').Path(__file__),script,
             study.ROOT/'tests/loss_feedback_controls.cjs',study.ROOT/'scripts/validate_loss_feedback.py')}))
    print(json.dumps(dict(charts=len(charts)*3,weakest={e:r['symbol'] for e,r in weakest.items()})))


if __name__=='__main__':main()
