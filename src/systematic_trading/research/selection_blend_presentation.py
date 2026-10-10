"""Inspectable rank tables and the complete registered selection experiment."""
from datetime import date
import html
import json

import numpy as np

from systematic_trading.research.momentum_replay import read_json
from systematic_trading.research.selection_blend import ARMS,MAIN,VARIANTS,COMPARISONS
from systematic_trading.research.expanded_economics import job_name
from systematic_trading.research.selection_blend_analysis import LABELS


def num(x,n=3):
    return 'n/a' if x is None else f'{x:.{n}f}'


def pct(x):
    return 'n/a' if x is None else f'{x:.2%}'


def delta(x,n=3):
    return f'{x:+.{n}f}'


def ci(values):
    return '['+', '.join(num(x) for x in values)+']' if values else 'n/a'


def table(headers,rows):
    def cell(x):
        return str(x) if str(x).startswith('<a ') else html.escape(str(x))
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+cell(x)+'</th>' for x in headers)+\
        '</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+cell(x)+'</td>' for x in row)+'</tr>' for row in rows)+\
        '</tbody></table></div>'


def landing(root,output,report):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    p=report['protocol']
    def r(a,c=5,d=0,w='evaluation'):
        return report['results'][job_name((a,c,d,w))]
    ranked=sorted(MAIN,key=lambda a:-r(a)['sharpe_zero_cash'])
    best=ranked[0]
    base=r('CP')
    retained=[a for a,v in report['screens'].items() if v['passes_recipe_screen']]
    robust=[a for a,v in report['screens'].items() if v['robust_superiority']]
    names=list(MAIN)
    colors=['#496573' if a.startswith('X') else '#207b92' if a.startswith('C') else '#bc7137' for a in names]
    fig,axes=plt.subplots(2,2,figsize=(14,9),layout='constrained')
    fig.set_facecolor('#fcfaf5')
    for ax in axes.flat:
        ax.set_facecolor('#fcfaf5')
        ax.spines[['top','right']].set_visible(False)
        ax.grid(axis='y',alpha=.15)
    for ax,key,title in [(axes[0,0],'sharpe_zero_cash','Sharpe change vs the same capped M1 control'),
                         (axes[0,1],'calmar','Calmar change vs the same capped M1 control')]:
        ax.bar(names,[r(a)[key]-base[key] for a in names],color=colors)
        ax.axhline(.05,color='#826b4e',linestyle='--',label='Registered +0.05 hurdle')
        ax.axhline(0,color='#666',lw=.7)
        ax.set_title(title)
        ax.tick_params(axis='x',labelrotation=35)
        ax.legend(fontsize=8,frameon=False)
    curves=list(dict.fromkeys(['CP','CR','FR',best,'CEQ','FEQ']))
    for a in curves:
        e=read_json(root/'python'/(job_name((a,5,0,'evaluation'))+'.json'))
        values=np.array([float(v['nav'])/1e6 for v in e['nav']])
        days=[date.fromisoformat(v['date']) for v in e['nav']]
        axes[1,0].plot(days,values,label=a,lw=2 if a in ('CP',best) else 1.1)
        axes[1,1].plot(days,values/np.maximum.accumulate(np.maximum(values,1))-1,label=a,lw=2 if a in ('CP',best) else 1.1)
    axes[1,0].set_title('Fresh-cash evaluation NAV; highest observed Sharpe highlighted')
    axes[1,0].set_ylabel('Value / initial USD1m')
    axes[1,0].legend(ncol=3,fontsize=8,frameon=False)
    axes[1,1].set_title('Drawdown over the same evaluation')
    axes[1,1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1,1].legend(ncol=3,fontsize=8,frameon=False)
    fig.suptitle('Move predictive information into asset selection',fontsize=18,color='#263c47')
    fig.savefig(output/'comparison.png',dpi=150)
    plt.close(fig)
    body=f'''<header><div class="eyebrow">FULL-POOL RESEARCH · 10 OCTOBER 2026</div><h1>Which ETFs enter the portfolio?</h1>
    <p class="lead">A registered comparison of momentum, XGBoost and ridge ranks before top-six selection, with the existing portfolio machinery held fixed.</p>
    <p>Ten main blends · fourteen candidates · eight matched mean-only controls · five position/exposure controls · seven references. All 240 replays use pinned audited histories; 30 native checks validate the ledgers. No model refits or automatic strategy promotion.</p></header>
    <nav><a href="#results">Results</a><a href="#ranks">Rank table</a><a href="#mechanism">Selection effects</a><a href="#controls">Controls</a><a href="#robustness">Robustness</a><a href="#evidence">Evidence</a></nav>
    <div class="cards"><div><b>{best}</b><span>Highest observed evaluation Sharpe: {num(r(best)['sharpe_zero_cash'])}</span></div><div><b>{len(retained)} / 10</b><span>Pass the complete recipe screen</span></div><div><b>{len(robust)} / 10</b><span>Also establish adjusted return superiority</span></div></div>
    <p class="callout">Highest observed performance is a retrospective comparison, not an independently validated winner. Recipe-screen passers: {', '.join(retained) or 'none'}. Family-adjusted robust passers: {', '.join(robust) or 'none'}.</p>
    <img class="figure" src="comparison.png" alt="Sharpe and Calmar differences across every blend, plus evaluation NAV and drawdown">
    <section id="results"><h2>Every main blend, with the original sizing-only controls</h2>
    <p>USD, fresh cash on January 4, 2021 through October 8, 2026, 5bp per traded dollar, zero-interest cash. M means the current M1 score (75% momentum, 25% volume), X the causal XGBoost forecast, R the total economic ridge forecast. Inputs become comparable midranks before blending. These are selection weights, not portfolio asset weights.</p>'''
    def row(a,window='evaluation'):
        s=r(a,w=window)
        return [f'<a href="reports/{a}.html">{a}</a>',LABELS[a],pct(s['cagr']),num(s['sharpe_zero_cash']),num(s['calmar']),pct(s['max_drawdown']),
                num(s['annual_turnover'],2)+'×',pct(s['mean_gross'])]
    body+=table(['Arm / full report','M/X/R recipe','CAGR','Sharpe','Calmar','Max DD','Turnover / year','Mean invested'],
                [row(a) for a in ['M1','CP','CR','FR',*MAIN]])
    body+='''<p>Every candidate retains the positive 126-session momentum gate and chooses at most six ETFs; fewer than four eligible ETFs triggers the existing defensive fallback. No ETF is forced into the portfolio. The primary arms retain the XGBoost weight tilt, relative momentum, adaptive trend, audited raw activity and USD ridge. They add no economic sizing overlay. A final 45% cap is shared with CP.</p>
    <p><b>The useful result is selective, rather than “more predictors is always better.”</b> FR25 (75% M1 /25% financial ridge) and CR50 (50% M1 /50% context ridge) pass the practical screen. Their evaluation Sharpe gains are +0.087 and +0.065, compared with +0.002 and +0.016 from the corresponding sizing-only overlays. Neither leading blend uses XGBoost in selection; the existing downstream XGBoost tilt remains. X25 helps, but its Calmar gain misses the hurdle. X50 and the equal context blend weaken the portfolio.</p>
    <p><b>The long history changes the preference.</b> FR25 raises full-history CAGR/Sharpe from 10.65%/1.062 to 11.21%/1.109, while drawdown worsens from −19.49% to −19.83%. CR50's full-history CAGR/Sharpe are 10.55%/1.061 with −20.95% drawdown. Equal financial blending looks competitive in 2021+ but has a −30.46% full-history drawdown. FR25 is the stronger research lead; the evaluation screen alone is not enough to promote either recipe.</p></section>
    <section id="ranks"><h2>Inspect the actual fourteen-asset rank table</h2>
    <p>Select a blend and decision date. Rank 1 is highest. The combined score controls selection only after the positive-momentum eligibility gate. The displayed “held” set is the final positive target set after downstream controls.</p>
    <div class="filters"><label>Blend <select id="arm">'''
    body+=''.join(f'<option value="{a}"'+(' selected' if a=='CEQ' else '')+'>'+html.escape(a+' · '+LABELS[a])+'</option>' for a in VARIANTS if VARIANTS[a]['blend'])
    body+='</select></label><label>Decision <select id="day"></select></label></div><p id="rank-note"></p><div class="scroll"><table><thead><tr><th>ETF</th><th>M rank</th><th>X rank</th><th>R rank</th><th>Blend score</th><th>Eligible</th><th>Selected</th><th>CP selected</th></tr></thead><tbody id="rank-body"></tbody></table></div></section>'
    selection=read_json(root/'selection.json')
    compact={}
    for day,arms in selection.items():
        if day<p['evaluation_start']:
            continue
        compact[day]={}
        for a,raw in arms.items():
            if raw['rank_table'] is None:
                continue
            compact[day][a]=dict(abstained=raw['abstained'],fallback=raw['fallback'],gross=raw['gross'],
                selected=raw['selected'],parent=raw['parent_selected'],eligible=raw['eligible'],table=raw['rank_table'])
    body+='''<section id="mechanism"><h2>Did the ranking changes actually improve selection?</h2>
    <p>Compare each final positive target set with CP on the same decision. “New minus removed” compares equal-weight subsequent open-to-open returns of entering and displaced assets in changed, completed months. It is a descriptive selection diagnostic, not portfolio profit: actual weights, costs, timing and exposure differ.</p>'''
    diag=report['selection']
    body+=table(['Blend','Changed /70','Mean replacements','Winning switches','New − removed return','Combined full-pool IC','Mean target-gross change (pp)'],[
        [a,f"{diag[a]['changed_decisions']} /70",num(diag[a]['mean_replacements'],2),f"{diag[a]['positive_switch_months']}/{diag[a]['switch_months']}",
         pct(diag[a]['mean_new_minus_removed']),num(diag[a]['combined_ic']),delta(100*diag[a]['mean_target_gross_delta'])] for a in MAIN])
    body+='''<p>Selection changes can alter exposure through the unchanged adaptive-trend and cap rules. The CEQG/FEQG controls below separate this from choosing different names where the parent budget is attainable. Missing ridge inputs revert the whole selector to M1, rather than redistributing predictor weights or filling features.</p>
    <p><b>FR25 changes only 13 of 70 selections</b>, replacing one ETF each time. Eight of those entrants outperform the displaced ETF over the next rebalance-open interval; the mean advantage is 2.60 percentage points per switched pair. Its average target gross rises by only 0.040pp, while annual traded notional falls from 8.59× to 8.07×. CR50 changes 35 selections; only 17 have positive equal-weight entrant-minus-exit returns, despite better portfolio risk ratios. Membership counts, portfolio weighting and return timing therefore still interact.</p>
    <h3>Concrete successes and failures</h3><p>FR25 replaces TLT with XLE in July 2026 and HYG with EWY in August 2026. Actual net portfolio outperformance is +1.974pp and +1.670pp in those calendar months. In October 2024 it instead replaces HYG with TLT and loses −1.157pp relative to CP. These are whole-pool selection examples, not separate sector tests. The return windows for the switch diagnostic and calendar net PnL differ.</p>
    <p>FR25 adds +4.552pp net return in 2026 through October 8, versus +0.236pp in 2024 and +0.432pp in 2025; its result depends materially on recent successful decisions. CR50 adds +5.012pp in 2021 but loses −1.709pp in 2022 and −1.402pp in 2023. These outcomes warrant prospective observation and frozen robustness work, not a claim of stable superiority.</p></section>
    <section id="controls"><h2>Does macro information beat a training-mean rank?</h2>
    <p>Every ridge blend has a control using each ETF’s expanding training mean in the R column, with identical readiness. This tests whether macro forecasts add value beyond a historical-return preference.</p>'''
    body+=table(['Blend','Mean-only control','CAGR change (pp)','Sharpe change','Calmar change'],[
        [a,f'<a href="reports/{a}M.html">{a}M</a>',delta(100*(r(a)['cagr']-r(a+'M')['cagr'])),
         delta(r(a)['sharpe_zero_cash']-r(a+'M')['sharpe_zero_cash']),delta(r(a)['calmar']-r(a+'M')['calmar'])]
        for a,v in MAIN.items() if v['group']])
    body+='<h3>Move XGBoost, or use it at both stages?</h3><p>NX removes only the downstream XGBoost tilt while retaining original M1 selection. CEQNX/FEQNX combine that removal with equal blended selection. All other layers remain fixed.</p>'
    body+=table(['Arm / full report','Recipe','CAGR','Sharpe','Calmar','Max DD','Turnover / year','Mean invested'],
                [row(a) for a in ('CP','NX','CEQ','CEQNX','FEQ','FEQNX')])
    body+='<h3>Match the parent target exposure</h3><p>CEQG/FEQG proportionally rescale the selected positive weights to CP’s target gross under the same 45% cap. No excluded or zero-weight name is resurrected. Capacity exceptions remain cash and are counted.</p>'
    body+=table(['Arm / full report','Recipe','CAGR','Sharpe','Calmar','Max DD','Turnover / year','Mean invested'],[row(a) for a in ('CP','CEQ','CEQG','FEQ','FEQG')])
    body+=f"<p>Infeasible gross matches in evaluation: CEQG {diag['CEQG']['infeasible_gross_matches']}/70; FEQG {diag['FEQG']['infeasible_gross_matches']}/70. Matching target gross does not match volatility or factor exposures.</p></section>"
    body+='''<section id="robustness"><h2>Costs, chronology and uncertainty</h2><p>The complete recipe hurdle requires +0.05 Sharpe and +0.05 Calmar versus CP, no more than 0.5pp CAGR sacrifice or maximum-drawdown worsening versus CP and M1, and positive risk-ratio improvements under 10bp, 20bp and a one-session execution delay. Ridge blends must beat their paired mean-only controls on both risk ratios.</p>'''
    body+=table(['Blend','5bp Sharpe / Calmar','10bp','20bp','One-session delay','Failed checks'],[
        [a,*[num(r(a,c,d)['sharpe_zero_cash'])+' / '+num(r(a,c,d)['calmar']) for c,d in ((5,0),(10,0),(20,0),(5,1))],
         ', '.join(k for k,v in report['screens'][a]['checks'].items() if not v) or 'none'] for a in MAIN])
    body+='<h3>Annual net return difference versus CP (percentage points)</h3>'
    years=sorted(base['calendar_returns'])
    body+=table(['Blend',*years],[[a,*[delta(100*(r(a)['calendar_returns'][y]-base['calendar_returns'][y]),2) for y in years]] for a in MAIN])
    body+='<p>2026 ends October 8. Context ridge availability ends before the last twelve decisions; missing-input fallback remains in effect. These dates are already inspected, not fresh holdouts.</p><h3>Calendar-block uncertainty</h3><p>The 50-comparison return family includes every main blend, mean-only control and registered selection/sizing/exposure contrast. Holm p-values below apply jointly to that family. Sharpe/Calmar intervals are marginal. All use 10,000 circular calendar-block draws.</p>'
    body+=table(['Blend vs CP','6m Sharpe difference CI','6m Calmar difference CI','Mean-return Holm p:3m','6m','12m'],[
        [a,ci(report['uncertainty'][a+'-CP']['6']['sharpe']['ci95']),ci(report['uncertainty'][a+'-CP']['6']['calmar_252']['ci95']),
         *[num(report['uncertainty']['means'][str(b)][COMPARISONS.index((a,'CP'))]['holm_p']) for b in (3,6,12)]] for a in MAIN])
    body+='<p>Bootstrap Calmar uses 252 sessions/year, while displayed portfolio CAGR uses elapsed calendar time. Both retain within-month daily paths. Full evidence includes all 3/6/12-month intervals; none is a certificate of prospective performance.</p></section>'
    body+='<section id="evidence"><h2>Complete evidence</h2><details><summary>All 30 arms over the full 2016–2026 history</summary>'
    body+=table(['Arm / full report','Recipe','CAGR','Sharpe','Calmar','Max DD','Turnover / year','Mean invested'],[row(a,'full') for a in ARMS])
    body+='</details><details><summary>Asset admission and displacement across the full pool</summary>'
    for a in MAIN:
        body+='<h3>'+html.escape(a+' · '+LABELS[a])+'</h3>'
        body+=table(['ETF','Months held','Added vs CP','Removed vs CP'],[[s,diag[a]['asset_months'][s],diag[a]['added_months'][s],diag[a]['removed_months'][s]] for s in sorted(diag[a]['asset_months'])])
    body+='</details><details><summary>Every paired return comparison</summary>'
    body+=table(['Comparison','6m annual mean difference','6m 95% interval','6m Holm p'],[
        [a+' − '+b,pct(report['uncertainty']['means']['6'][i]['mean_annual']),ci(report['uncertainty']['means']['6'][i]['ci95']),num(report['uncertainty']['means']['6'][i]['holm_p'])]
        for i,(a,b) in enumerate(COMPARISONS)])
    body+='</details>'
    body+='<p>Audited adjusted prices support return research; raw prices and raw volume support the inherited activity signal. Models and their original economic vintages are reused with prior-close cutoffs and completed training labels. XGBoost’s relative close-return training target and ridge’s absolute open-return target remain distinct; rank normalization does not remove that difference. Missing data are never silently filled.</p>'
    body+='<p>Universe choice, M1 settings and this study’s design follow previously inspected history. Auditing does not establish historical publication availability, and current ETF membership is not a survivor-free historical universe. The experiment is exploratory and does not alter monitoring, allocations, approvals or live-disabled controls.</p>'
    body+='<p><a href="../../var/research/selection-blend-20261010-v1/protocol.json">Frozen protocol</a> · <a href="../../var/research/selection-blend-20261010-v1/report.json">All metrics, intervals and screens</a> · <a href="../../var/research/selection-blend-20261010-v1/selection.json">Every rank table and selection</a> · <a href="../../var/research/selection-blend-20261010-v1/data_receipt.json">Pinned input lineage</a> · <a href="../full-pool-signal-diagnostics-2026-10-10/index.html">Preceding signal diagnosis</a></p></section>'
    rank_json=json.dumps(compact,separators=(',',':')).replace('</','<\\/')
    script='''const snapshots=DATA;const days=Object.keys(snapshots).sort();const arm=document.getElementById('arm'),day=document.getElementById('day');
    for(const d of days){const o=document.createElement('option');o.value=d;o.textContent=d;day.appendChild(o);}
    day.value=[...days].reverse().find(d=>!snapshots[d].CEQ.abstained)||days.at(-1);
    function display(){const v=snapshots[day.value][arm.value];document.getElementById('rank-note').textContent=(v.abstained?'Required ridge unavailable: original M1 selection applies. ':'Predictors available. ')+(v.fallback?'Defensive fallback active. ':'')+'Target invested: '+(100*Number(v.gross)).toFixed(2)+'%.';
    const body=document.getElementById('rank-body');body.replaceChildren();const rows=Object.entries(v.table).sort((a,b)=>Number(b[1].combined)-Number(a[1].combined)||a[0].localeCompare(b[0]));
    for(const [s,q] of rows){const tr=document.createElement('tr');if(v.selected.includes(s))tr.className='chosen';const rank=x=>x===null?'—':(1+(1-Number(x))*6.5).toFixed(1);for(const val of [s,rank(q.momentum),rank(q.xgb),rank(q.ridge),Number(q.combined).toFixed(4),v.eligible.includes(s)?'Yes':'No',v.selected.includes(s)?'Yes':'—',v.parent.includes(s)?'Yes':'—']){const td=document.createElement('td');td.textContent=val;tr.appendChild(td);}body.appendChild(tr);}}
    arm.addEventListener('change',display);day.addEventListener('change',display);display();'''.replace('DATA',rank_json,1)
    css='''*{box-sizing:border-box}body{margin:0;background:#f3f0e8;color:#263c47;font:16px/1.6 system-ui,sans-serif}main{max-width:1320px;margin:auto;padding:44px 32px}h1{font-size:48px;line-height:1.1;margin:16px 0}h2{font-size:27px;line-height:1.25}h3{font-size:19px;margin-top:28px}.eyebrow{font-size:12px;letter-spacing:2px;font-weight:700}.lead{font-size:22px;max-width:1050px}a{color:#12617b}nav{display:flex;gap:22px;flex-wrap:wrap;margin:26px 0}.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}.cards>div{padding:20px;background:#fffdf7;border-top:3px solid #367d8f}.cards b{display:block;font-size:32px}.cards span{font-size:14px}.callout{padding:18px;background:#e8efed;border-left:4px solid #377d8c}.figure{width:100%;height:auto}section{padding:24px 28px;background:#fffdf8;margin:24px 0;border:1px solid #ddd8cb;border-radius:7px}.scroll{overflow:auto;margin:18px 0}table{border-collapse:collapse;width:100%;font-size:13px;font-variant-numeric:tabular-nums}th,td{padding:10px 11px;text-align:right;border-bottom:1px solid #deded5;white-space:nowrap}th{background:#e6eeec}td:first-child,th:first-child{text-align:left}tr:nth-child(even) td{background:#f7f6f0}.chosen td{background:#dfeee7!important}.filters{display:flex;gap:20px;flex-wrap:wrap}label{font-weight:600}select{display:block;margin-top:6px;padding:10px;border:1px solid #8ea5ac;background:white;max-width:100%;font-size:14px}details{padding:16px 0;border-top:1px solid #ccc}summary{cursor:pointer;font-weight:650}p{max-width:1160px}@media(max-width:700px){main{padding:24px 12px}h1{font-size:36px}.cards{grid-template-columns:1fr}section{padding:18px 12px}.lead{font-size:18px}}'''
    (output/'index.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Selection-stage signal blends</title><style>'+css+'</style><main>'+body+'</main><script>'+script+'</script></html>',encoding='utf8')
