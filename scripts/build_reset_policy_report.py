"""Full-pool posterior reset report with explicit memory and state semantics."""
import gzip
from io import BytesIO
import json
import re
from pathlib import Path
import numpy as np
import research_reset_policy as study

NAMES={'continuous':'A: continuous learning','loss_reset':'B: reset after losses / drawdown','regime_reset':'C: also reset on confirmed HMM transition'}


def summary(rows):
    lookup={(r['symbol'],r['era'],r['arm'],r['cost_bp'],r['delay']):r for r in rows};out=[]
    for era,*_ in study.ERAS:
        for cost,delay in study.FRICTIONS:
            for arm in study.model.ARMS:
                a=[r for r in rows if r['era']==era and r['arm']==arm and r['cost_bp']==cost and r['delay']==delay and r['symbol']!='BIL']
                comparisons=[]
                for reference in ('continuous','loss_reset','frozen'):
                    b=[dict(r['frozen_metrics'],cumulative=r['frozen_cumulative']) if reference=='frozen' else lookup[r['symbol'],era,reference,cost,delay] for r in a]
                    guard=float(np.mean([x['cagr']>=y['cagr']-.01 and x['maxdd']>=y['maxdd']-.02 for x,y in zip(a,b,strict=True)]))
                    sg=float(np.median([r['sharpe'] for r in a])-np.median([r['sharpe'] for r in b]))
                    qg=float(np.quantile([r['cagr'] for r in a],.25)-np.quantile([r['cagr'] for r in b],.25))
                    comparisons.append(dict(reference=reference,median_sharpe_gain=sg,lower_quartile_cagr_gain=qg,guard_fraction=guard,
                        improves_return=sum(x['cumulative']>y['cumulative']+1e-10 for x,y in zip(a,b,strict=True)),passed=sg>0 and qg>0 and guard>=.9))
                out.append(dict(era=era,cost_bp=cost,delay=delay,arm=arm,cases=len(a),
                    median_sharpe=float(np.median([r['sharpe'] for r in a])),median_cagr=float(np.median([r['cagr'] for r in a])),
                    median_resets=float(np.median([r['reset_count'] for r in a])),
                    median_no_fresh_fraction=float(np.median([r['empty_evidence_sessions']/r['sessions'] for r in a])),comparisons=comparisons))
    return out


def figure(c,symbol,era,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    days=np.array(c['days'],dtype='datetime64[D]');a=c['arms']['regime_reset'];active=days>=np.datetime64(c['evaluation_start'])
    fig,axes=plt.subplots(5,1,figsize=(14,12),sharex=True,layout='constrained',height_ratios=[2,.6,.8,.6,1.2])
    axes[0].plot(days,c['close'],color='#173d54',label='Adjusted close');axes[0].plot(days,np.asarray(a['stop'],float),color='#bd5260',label='Adopted protection')
    for e in a['trades']:
        x=np.datetime64(e['entry_date']);y=np.datetime64(e['exit_date']) if e['exit_date'] else days[-1]
        axes[0].axvspan(x,y,color='#008675',alpha=.07);axes[0].scatter(x,e['entry'],color='#008675',marker='^',s=30)
        if e['exit_date']:axes[0].scatter(y,e['exit_price'],color='#bd5260',marker='v',s=30)
    for e in a['events']:
        if e['reset']:axes[0].axvline(np.datetime64(e['day']),color='#c68b26',lw=.7,ls=':')
    axes[0].set_ylabel('Adjusted USD');axes[0].legend(loc='upper left',fontsize=8)
    axes[1].bar(days,np.asarray(c['volume'],float)/1e6,color='#9aabb6',width=1.5);axes[1].set_ylabel('Raw volume\n(millions)')
    axes[2].plot(days[active],np.asarray(c['fast_up'])[active],color='#008675',label='Fast up')
    axes[2].plot(days[active],np.asarray(c['hmm_change'])[active],color='#bd5260',label='Filtered HMM transition probability')
    axes[2].legend(loc='upper left',fontsize=8);axes[2].set_ylim(0,1)
    axes[3].plot(days,np.asarray(a['effective_count'],float),color='#8154a5');axes[3].set_ylabel('Effective\nobservations')
    for name,color in [('continuous','#91a3b0'),('loss_reset','#c78b28'),('regime_reset','#008675')]:
        axes[4].plot(days,np.asarray(c['arms'][name]['nav'],float),color=color,label=NAMES[name])
    axes[4].legend(loc='upper left',fontsize=8);axes[4].set_ylabel('NAV / initial 100')
    for ax in axes:ax.grid(alpha=.15);ax.axvline(np.datetime64(c['evaluation_start']),color='#777',ls='--',lw=.7)
    axes[4].xaxis.set_major_locator(dates.MonthLocator(interval=6));axes[4].xaxis.set_major_formatter(dates.DateFormatter('%Y-%m'))
    fig.suptitle(f'{symbol} | {era} | Loss + confirmed-HMM posterior resets\nActual fills and stops; amber lines = full evidence reset; no health pause')
    fig.savefig(path,dpi=140);plt.close(fig)


def equations():
    from matplotlib import mathtext
    from matplotlib.font_manager import FontProperties
    formulas=[r'\rho=2^{-1/126},\quad(N,S,W)\leftarrow\rho(N,S,W),\quad N_{train}\leq4',
        r'\mathrm{reset\ at}\ r:\quad(N_j,S_j,W_j,F_j)\leftarrow(0,0,0,0)\quad\forall j',
        r'\mu_j\sim N(0,1/4),\quad p_j\sim\mathrm{Beta}(1,1),\quad \mathrm{admit\ trade}\ i\ \mathrm{only\ if}\ entry_i>r',
        r'\widehat\mu_j=\frac{S_j}{4+N_j},\quad sd_j=\frac{1}{\sqrt{4+N_j}},\quad u_j=\widehat\mu_j-0.25sd_j',
        r'\tau=\max(\sigma_{winning\ returns},2f,10^{-6}),\quad D_t=1-\frac{NAV_t}{\max_{r\leq s\leq t}NAV_s}',
        r'\mathrm{loss\ trigger}:\quad L\in\{3,4\}\ \mathrm{or}\ R< -\tau\ \mathrm{or}\ D_t\geq\max(0.10,2\tau)',
        r'J_t(i,j)=\frac{\alpha_{t-1}(i)A_{ij}\mathcal{L}_t(j)}{\sum_{a,b}\alpha_{t-1}(a)A_{ab}\mathcal{L}_t(b)},\quad q_t=1-\sum_iJ_t(i,i)',
        r'q_t\geq0.8,\quad \alpha_t(j),\alpha_{t+1}(j),\alpha_{t+2}(j)\geq0.9\quad\Rightarrow\mathrm{event\ at}\ t+2',
        r'\Delta t_{all\ resets}\geq20,\quad\Delta t_{HMM\ resets}\geq63,\quad \ell_{t+1}=\max(\ell_t,M_t-k_t\hat\sigma O_{entry})']
    rendered=[]
    for j,formula in enumerate(formulas):
        b=BytesIO();mathtext.math_to_image('$'+formula+'$',b,prop=FontProperties(size=15),format='svg',color='#17384d')
        svg=b.getvalue().decode();svg=svg[svg.index('<svg'):]
        svg=re.sub(r'id="([^"]+)"',lambda m:f'id="eq{j}_{m[1]}"',svg);svg=re.sub(r'xlink:href="#([^"]+)"',lambda m:f'xlink:href="#eq{j}_{m[1]}"',svg)
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
    charts=json.loads(gzip.decompress((study.OUT/'chart-data.json.gz').read_bytes()));rows=json.loads((study.OUT/'asset-results.json').read_text())
    s=summary(rows);study.write(study.OUT/'summary.json',s);primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0]
    weakest={era:min((r for r in primary if r['era']==era and r['arm']=='regime_reset' and r['symbol']!='BIL'),key=lambda r:(r['cumulative'],r['symbol'])) for era,*_ in study.ERAS}
    focus={('WEAT','late'),('GLD','late'),('TLT','late'),*((r['symbol'],era) for era,r in weakest.items())}
    for symbol,era in sorted(focus):figure(charts[f'{symbol}_{era}'],symbol,era,study.OUT/f'{symbol}_{era}.png')
    pct=lambda x:'—' if x is None else f'{100*x:+.2f}%'
    st=''.join(f'<tr><td>{r["era"]}</td><td>{NAMES[r["arm"]]}</td><td>{r["median_sharpe"]:.3f}</td><td>{pct(r["median_cagr"])}</td><td>{r["median_resets"]:.0f}</td><td>{pct(r["median_no_fresh_fraction"])}</td><td>{pct(r["comparisons"][0]["guard_fraction"])}</td></tr>' for r in s if r['cost_bp']==5 and r['delay']==0)
    pt=''.join(f'<tr><td>{r["symbol"]}</td><td>{r["era"]}</td><td>{NAMES[r["arm"]]}</td><td>{pct(r["cumulative"])}</td><td>{r["sharpe"]:.3f}</td><td>{pct(r["maxdd"])}</td><td>{r["reset_count"]}</td><td>{r["closed_trades"]}</td><td>{pct(r["frozen_cumulative"])}</td></tr>' for r in sorted(primary,key=lambda r:(r['era']!='late',r['symbol'],r['arm'])))
    exports=' · '.join(f'<a href="{symbol}_{era}.png">{symbol} {era} figure</a>' for symbol,era in sorted(focus))
    html='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width">
<title>Resetting Bayesian policy memory</title><style>body{font:16px/1.5 system-ui;color:#17384d;background:#f5f8fa;max-width:1280px;margin:34px auto;padding:0 20px}h1,h2{line-height:1.2}h2{margin-top:38px}a{color:#006b70}.note{background:#fff0d7;border-left:4px solid #b47b22;padding:16px}.card{background:white;padding:18px;border:1px solid #d9e3e9;margin:14px 0}.controls{display:flex;flex-wrap:wrap;gap:12px;align-items:center}button,select,input{font:inherit;padding:7px;border:1px solid #b4c5ce;border-radius:5px;background:white}button{cursor:pointer}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:7px 9px;border-bottom:1px solid #e2e8ed;text-align:right}th:first-child,td:first-child{text-align:left}.scroll{overflow:auto}#chart{width:100%;height:auto}#readout{min-height:48px}.equation{overflow:auto;padding:9px;background:white;margin:5px 0}.equation svg{max-width:100%;height:auto}small{color:#536b7b}</style>
<h1>Discard old policy evidence after a warning</h1><p>26 October 2026 · Full supported ETF pool · Single-ETF algorithms only · No portfolio or overlay test</p>
<p class="note"><b>The previous learner did not carry three years of undiminished Bayesian evidence.</b> Training contributes at most 4 effective trades per policy (median 2.49), decays with a 126-session half-life, and previous warning acceleration removed 75% of older evidence. Median selected-policy evidence immediately after those updates was 0.59 trades. The market filters themselves still retained their original fitted parameters. This experiment isolates a full reset of policy evidence.</p>
<h2>Three comparisons</h2><ul><li><b>A — continuous learning:</b> exact ordinary Bayesian learner from the preceding report; no warning acceleration.</li><li><b>B — reset after losses/drawdown:</b> A with hard posterior resets after a 3rd/4th consecutive actual loss, a large marked/realized loss, or sufficiently large account drawdown.</li><li><b>C — also reset on a confirmed HMM transition:</b> B plus a high filtered transition probability, confirmed by 3 successive high-confidence closes in the destination state.</li></ul>
<p>On reset, all nine policies lose their accumulated payoff/win statistics and fresh-trade counts. Proper neutral priors remain. Only trades entered after the reset close can supply new evidence; straddling trade returns are discarded. The current policy remains the operational fallback until new evidence supports a change. Existing positions, adopted stops and queued orders are preserved. This resets beliefs, not risk limits or all market-model parameters; it does not impose a health pause.</p>
<p><b>A normal HMM state switch is not proof that the statistical regime has structurally changed.</b> We calculate the filtered joint probability of a state transition, rather than confusing a high up/down posterior with a probability of change. Even this measures movement within the existing fitted HMM, not whether its parameters have become obsolete. This distinction is part of the hypothesis being tested.</p>
<h2>Inspect every ETF</h2><p id="weakestNote"></p><div class="controls"><label>Era <select id="era"><option value="late">2023–2026</option><option value="early">2020–2022</option></select></label><label>ETF <select id="etf"></select></label><label>Algorithm <select id="arm"><option value="continuous">A · Continuous learning</option><option value="loss_reset">B · Loss/drawdown reset</option><option value="regime_reset">C · Also HMM reset</option></select></label><button id="weakest">Weakest C case</button><button id="weat">WEAT</button></div>
<div class="controls"><label>From <input id="from" type="date"></label><label>To <input id="to" type="date"></label><button id="reset">Full context</button></div>
<div class="card"><p id="metrics"></p><small id="parameters"></small><p id="readout">Hover for exact date, evidence count and learned parameters; click two dates for an interval.</p><svg id="chart" viewBox="0 0 1200 1140"></svg></div>
<details><summary>Actual parameter values</summary><table><tr><th>ID</th><th>Up entry</th><th>Down exit</th><th>Down exit in slow up</th><th>Distance normal</th><th>Distance slow up</th></tr><tbody id="grid"></tbody></table><p>Confidence thresholds and volatility-scaled distances use the same 9 candidate tuples as the preceding study. The search space is not expanded after inspecting results.</p></details>
<details><summary>Actual trades</summary><table><tr><th>Entry</th><th>Exit</th><th>Entry policy</th><th>Exit policy</th><th>Net return</th><th>Exit reason</th></tr><tbody id="trades"></tbody></table></details>
<details><summary>Warnings, resets and parameter changes</summary><div class="scroll"><table><tr><th>Known date</th><th>Policy change</th><th>Reason</th><th>Full reset?</th><th>Payoff mean</th><th>Win estimate</th><th>Evidence count</th></tr><tbody id="events"></tbody></table></div><p>Evidence count immediately after reset is zero. A warning during cooldown is recorded without erasing evidence. The 20-session shared cooldown and 63-session HMM cooldown avoid repeated resets on adjacent days. No old trade is retrospectively split into a new-regime winner.</p></details>
<p>__EXPORTS__</p><h2>Full-pool results</h2><table><tr><th>Era</th><th>Algorithm</th><th>Median Sharpe</th><th>Median CAGR</th><th>Median resets</th><th>No fresh trade fraction</th><th>Within A guards</th></tr>__SUMMARY__</table>
<p>Primary 5 bp per side, next open;51 risky ETFs later / 49 earlier. No-fresh fraction means sessions before any new qualifying shadow trade has closed since start/reset. At initial startup, training evidence can still exist; after a reset, such sessions have no learned payoff evidence. This is a learning delay, not a trading pause. Acceptance requires median Sharpe/lower-quartile CAGR improvement and 90% of ETFs within 1 pp CAGR / 2 pp DD of A; also compare the original frozen policy. No evaluation-based per-ETF algorithm choice.</p>
<div id="findings">__FINDINGS__</div>
<details><summary>Every ETF result</summary><div class="scroll"><table><tr><th>ETF</th><th>Era</th><th>Algorithm</th><th>Net return</th><th>Sharpe</th><th>Drawdown</th><th>Resets</th><th>Closed trades</th><th>Frozen return</th></tr>__POOL__</table></div></details>
<h2>Mathematical rules</h2>__EQUATIONS__
<p>The payoff posterior remains the preceding study's discounted Normal model: normalized net ROI divided by training daily volatility and square root of holding sessions, clipped to ±3 for learning only. Prior mean 0, precision 4; win probability uses Beta(1,1) plus weighted wins/losses. Selection maximizes posterior mean − 0.25 posterior SD with a 0.05 switch margin and at least one newly completed qualifying shadow trade. Each policy is separate; correlated candidate outcomes are not pooled into common confidence. These are working Bayesian estimates, not calibrated statistical guarantees.</p>
<p>Large-loss threshold tau uses the training winner-return sample SD with at least 5 winners; unavailable sigma disables that trigger. The drawdown threshold becomes 10% when sigma is unavailable, otherwise max(10%,2tau). Drawdown peak and loss streak restart at a reset. Ordinary losing-stop exits alone do not reset; this is a deliberately narrower warning set than the previous 75% forgetting study. A warning is not itself an emergency liquidation signal.</p>
<p>The HMM transition detector uses the same ETF-specific fast-slope HMM even where the selected trading policy uses Gaussian slope probabilities. A transition probability≥0.8 followed by the same destination state's posterior≥0.9 for three closes triggers only on the third close. Filtering uses no future observations or smoothing. The frozen market model, training volatility and bounded policy grid retain historical information; only payoff evidence is erased. Full HMM refitting, a structural change-point model, daily marked rewards, re-entry redesign and hard risk caps are separate future tests.</p>
<p>All 1,836 cases use pinned audited adjusted prices and audited raw volume for chart context only. Initial funds/flat start match the previous study. Fees 5/10/20 bp per side, next open / extra 1 session delay, fractional cash-funded units, idle cash 0, terminal marked holdings. Existing stops never loosen; pending orders bind. Both chronological eras have already been inspected and are development evidence, not an untouched prospective test. Price auditing does not prove historical publication availability.</p>
<p><a href="https://arxiv.org/abs/0710.3742">Bayesian online change-point detection</a> models uncertainty about when generative parameters change; that is a different object from the HMM state-transition probability used here. <a href="https://arxiv.org/abs/2305.10718">Discounted Bayesian learning</a> provides background for downweighting stale evidence. Neither paper establishes that these ETF reset rules improve trading.</p>
<p><a href="asset-results.json">All results and yearly returns</a> · <a href="summary.json">All cost/delay comparisons</a> · <a href="protocol.json">Frozen recipe</a> · <a href="validation.json">Accounting checks</a> · <a href="native-checks.json">Native single-ETF checks</a> · <a href="../../docs/reset-policy-results-2026-10-26.md">Findings and next direction</a></p>
<script>const DATA = __DATA__;
__SCRIPT__</script></html>'''
    def display(obj):
        if isinstance(obj,float):return round(obj,7)
        if isinstance(obj,list):return [display(x) for x in obj]
        if isinstance(obj,dict):return {k:display(v) for k,v in obj.items()}
        return obj
    script=study.ROOT/'scripts/assets/reset-policy-script.js';finding=study.OUT/'findings.html'
    for token,value in dict(EXPORTS=exports,SUMMARY=st,POOL=pt,EQUATIONS=equations(),
        FINDINGS=finding.read_text(encoding='utf-8') if finding.exists() else '<p>See the tables for measured outcomes; case analysis is being completed.</p>',
        DATA=json.dumps(display(dict(charts=charts,rows=primary,weakest=weakest)),separators=(',',':')).replace('</','<\\/'),SCRIPT=script.read_text(encoding='utf-8')).items():html=html.replace('__'+token+'__',value)
    (study.OUT/'index.html').write_text(html,encoding='utf-8');study.write(study.OUT/'weakest-cases.json',weakest)
    study.write(study.OUT/'manifest.json',dict(files={p.name:study.prior.study.digest(p) for p in study.OUT.iterdir() if p.is_file() and p.name!='manifest.json'},
        report_code={str(p.relative_to(study.ROOT)).replace(chr(92),'/'):study.prior.study.digest(p) for p in (Path(__file__),script,study.ROOT/'tests/reset_policy_controls.cjs',study.ROOT/'scripts/validate_reset_policy.py')}))
    print(json.dumps(dict(charts=len(charts)*3,weakest={e:r['symbol'] for e,r in weakest.items()})))


if __name__=='__main__':main()
