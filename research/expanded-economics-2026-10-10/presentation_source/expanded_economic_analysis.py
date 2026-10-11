"""Diagnostics and complete reports for the fixed expanded-universe economic test."""
from datetime import date
from decimal import Decimal as D
import html
from pathlib import Path
import re

import numpy as np

from systematic_trading.lean.contracts import write_json,sha256
from systematic_trading.research.momentum_replay import read_json,checked_files,verify_usd_bundle
from systematic_trading.research.expanded_economics import ARMS,VARIANTS,COMPARISONS,LABELS,jobs,job_name


def diagnostics(root):
    from systematic_trading.research.construction_analysis import ranks
    p=read_json(root/'protocol.json');models=read_json(root/'models.json');days=sorted(models);evaluation=[d for d in days if d>=p['evaluation_start']]
    opens={s:{v['trade_date']:float(v['open']) for v in rows} for s,rows in read_json(root/'bars.json').items()}
    availability={};records=[];latest={};groups=['context','financial','matched','augmented']
    for group in groups:
        ready=[d for d in evaluation if models[d][group]['ready']]
        availability[group]=dict(ready=len(ready),total=len(evaluation),abstained=[d for d in evaluation if d not in ready],
            first_training_rows=models[evaluation[0]][group]['training_rows'],last_training_rows=models[evaluation[-1]][group]['training_rows'])
        if ready:
            d=ready[-1];m=models[d][group];latest[group]=dict(decision=d,features=m['features'],query=m['query'],models=m['models'])
        for d,end in zip(days,days[1:]):
            m=models[d][group]
            if d<p['evaluation_start'] or not m['ready']:continue
            for subset,symbols in [('all14',sorted(opens)),('XLE_XLB',['XLE','XLB'])]:
                actual=np.array([opens[s][end]/opens[s][d]-1 for s in symbols]);means=np.array([m['models'][s]['mean_return'] for s in symbols])
                for kind in ('linear','tree'):
                    forecasts=np.array([m['models'][s][kind+'_forecast'] for s in symbols]);x,y=ranks(forecasts),ranks(actual)
                    ic=float(np.corrcoef(x,y)[0,1]) if np.std(x)>0 and np.std(y)>0 else None
                    records.append(dict(decision=d,label_end=end,group=group,kind=kind,subset=subset,
                        mae=float(np.mean(abs(forecasts-actual))),mean_baseline_mae=float(np.mean(abs(means-actual))),
                        sign_accuracy=float(np.mean((forecasts>0)==(actual>0))),rank_ic=ic))
    forecasts={}
    for g in groups:
        for kind in ('linear','tree'):
            for subset in ('all14','XLE_XLB'):
                rows=[r for r in records if (r['group'],r['kind'],r['subset'])==(g,kind,subset)];ics=[r['rank_ic'] for r in rows if r['rank_ic'] is not None]
                forecasts[g+'/'+kind+'/'+subset]=dict(months=len(rows),mae=float(np.mean([r['mae'] for r in rows])) if rows else None,
                    mean_baseline_mae=float(np.mean([r['mean_baseline_mae'] for r in rows])) if rows else None,
                    sign_accuracy=float(np.mean([r['sign_accuracy'] for r in rows])) if rows else None,rank_ic=float(np.mean(ics)) if ics else None)
    parents=read_json(root/'decisions/CP.json');original=read_json(root/'decisions/M1.json');allocation={}
    cap_dates=[d for d in days if any(D(t['target_weight'])>D('.45') for t in original[d]['targets'])]
    for arm in VARIANTS:
        rows=read_json(root/'decisions'/(arm+'.json'));changes={s:dict(increased=0,decreased=0) for s in opens};changed=0
        for day in evaluation:
            a={t['symbol']:D(t['target_weight']) for t in rows[day]['targets']};b={t['symbol']:D(t['target_weight']) for t in parents[day]['targets']}
            if sum(a.values())!=sum(b.values()) or {s for s,w in a.items() if w>0}!={s for s,w in b.items() if w>0}:raise ValueError('Selection/cash contract changed')
            changed+=any(abs(a[s]-b[s])>D('1e-12') for s in a)
            for s in a:changes[s]['increased']+=int(a[s]>b[s]+D('1e-12'));changes[s]['decreased']+=int(a[s]<b[s]-D('1e-12'))
        allocation[arm]=dict(changed_decisions=changed,assets=changes)
    for day in days:
        left,right=models[day]['matched'],models[day]['augmented']
        if any(left[k]!=right[k] for k in ('sample_sha256','ready','training_rows','last_label_end')):raise ValueError('Matched availability failed')
        if any(m['last_label_end'] and m['last_label_end']>m['known_through'] for m in models[day].values()):raise ValueError('Future label')
    return dict(availability=availability,forecast_summary=forecasts,forecast_records=records,latest_conditional_responses=latest,
        allocation=allocation,cap_bridge=dict(affected_decisions=len(cap_dates),dates=cap_dates,
            mean_target_cash_added=float(np.mean([sum(D(t['target_weight']) for t in original[d]['targets'])-sum(D(t['target_weight']) for t in parents[d]['targets']) for d in days]))))


def summarize(root):
    from systematic_trading.research.momentum_analysis import statistics
    from systematic_trading.research.candidate_pool_analysis import return_metrics
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json');checked_files(root,'feature_manifest.json')
    results={};parity={};context={}
    for job in jobs():
        name=job_name(job);file=root/'python'/(name+'.json');bundle=root/'bundles'/name;verify_usd_bundle(bundle)
        if read_json(file.with_suffix('.receipt.json'))!=dict(sha256=sha256(file),manifest_sha256=sha256(bundle/'manifest.json')):raise ValueError('Changed replay '+name)
        economic=read_json(file);s=statistics(economic,read_json(bundle/'quotes.json'));s['calmar']=s['cagr']/abs(s['max_drawdown'])
        s['mean_equity_weight']+=sum(s['mean_asset_weights'].get(x,0) for x in ('XLE','XLB'))
        s.pop('asset_daily_contribution');results[name]=s
        arm,cost,delay,window=job
        if cost==5 and delay==0 and window=='full':
            old=root/'original_economics'/(arm+'.json')
            if old.exists():
                before=read_json(old)
                if any(before[k]!=economic[k] for k in ('nav','fills','final_positions')):raise ValueError('Exact control parity failed')
                parity[arm]=dict(exact=True,sha256=sha256(old))
            context[arm]={}
            for label,predicate in [('2016_2020',lambda d:d<'2021'),('exclude_2020',lambda d:not d.startswith('2020')),('exclude_2022',lambda d:not d.startswith('2022'))]:
                pairs=[(d,v) for d,v in zip(s['dates'],s['daily_returns']) if predicate(d)];v=return_metrics([d for d,_ in pairs],[x for _,x in pairs])
                if label.startswith('exclude'):v.pop('cagr');v.pop('calmar')
                context[arm][label]=v
    write_json(root/'statistics.json',results);write_json(root/'statistics_receipt.json',dict(sha256=sha256(root/'statistics.json')))
    write_json(root/'diagnostics.json',diagnostics(root));write_json(root/'control_parity.json',parity);write_json(root/'context.json',context)


def inference_job(job):
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    from systematic_trading.research.construction_analysis import bootstrap_ratios
    root,kind,block,index=job;root=Path(root);p=read_json(root/'protocol.json')
    if read_json(root/'statistics_receipt.json')['sha256']!=sha256(root/'statistics.json'):raise ValueError('Changed inference input')
    results=read_json(root/'statistics.json')
    def r(a):return results[job_name((a,5,0,'evaluation'))]
    if kind=='means':
        months=sorted(r('CP')['monthly']);matrix=np.array([[r(a)['monthly'][m]-r(b)['monthly'][m] for a,b in COMPARISONS] for m in months])
        return 'means',str(block),paired_bootstrap(matrix,block=block,replications=p['bootstrap_replications'],seed=p['seed'])
    a,b=COMPARISONS[index];left,right=r(a),r(b)
    if left['dates']!=right['dates']:raise ValueError('Paired dates differ')
    return a+'-'+b,str(block),bootstrap_ratios(left['dates'],left['daily_returns'],right['daily_returns'],block=block,
        replications=p['bootstrap_replications'],seed=p['seed'])


def retention_checks(arm,results,p):
    def r(a,c=5,d=0):return results[job_name((a,c,d,'evaluation'))]
    s=p['screen'];a=r(arm);base=r('CP')
    checks=dict(sharpe_gain=a['sharpe_zero_cash']-base['sharpe_zero_cash']>=s['min_sharpe_gain'],calmar_gain=a['calmar']-base['calmar']>=s['min_calmar_gain'],
        cagr_budget=all(a['cagr']>=r(b)['cagr']-s['max_cagr_sacrifice'] for b in ('CP','M1')),
        drawdown_budget=all(a['max_drawdown']>=r(b)['max_drawdown']-s['max_drawdown_worsening'] for b in ('CP','M1')),
        cost_delay=all(r(arm,c,d)['sharpe_zero_cash']>r('CP',c,d)['sharpe_zero_cash'] and r(arm,c,d)['calmar']>r('CP',c,d)['calmar']
            and r(arm,c,d)['cagr']>=r('M1',c,d)['cagr']-s['max_cagr_sacrifice'] for c,d in ((10,0),(20,0),(5,1))))
    extra={'CR':[],'CT':['CR'],'FR':[],'FT':['FR'],'MR':[],'AR':['MR'],'AT':['AR','MR']}[arm]
    for b in extra:checks['above_'+b]=all(a[m]>r(b)[m] for m in ('sharpe_zero_cash','calmar'))
    return checks


def finalize(root):
    p=read_json(root/'protocol.json');r=read_json(root/'statistics.json');u={};native={};screens={}
    for key,block,value in read_json(root/'inference.json'):u.setdefault(key,{})[block]=value
    for a in ARMS:
        path=root/'native'/job_name((a,5,0,'full'));checked_files(path,'artifact_manifest.json')
        if read_json(path/'run.json')['status']!='succeeded' or not read_json(path/'parity.json')['passed']:raise ValueError('Native validation missing '+a)
        native[a]=dict(run_sha256=sha256(path/'run.json'),parity_sha256=sha256(path/'parity.json'))
    for a in VARIANTS:
        checks=retention_checks(a,r,p);i=COMPARISONS.index((a,'CP'))
        significant=all(u['means'][str(b)][i]['holm_p']<.05 and u['means'][str(b)][i]['ci95'][0]>0 for b in p['bootstrap_blocks'])
        screens[a]=dict(checks=checks,retain_for_observation=all(checks.values()),family_return_evidence=significant,
            robust_superiority=all(checks.values()) and significant)
    report=dict(protocol=p,results=r,uncertainty=u,screens=screens,native=native,diagnostics=read_json(root/'diagnostics.json'),
        context=read_json(root/'context.json'),control_parity=read_json(root/'control_parity.json'),promotion_eligible=False)
    write_json(root/'report.json',report)
    write_json(root/'report_receipt.json',dict(sha256=sha256(root/'report.json'),statistics_sha256=sha256(root/'statistics.json'),
        decisions_sha256=sha256(root/'decision_manifest.json'),input_sha256=sha256(root/'input_manifest.json')))
    return dict(replays=len(r),native=len(native),retained=[a for a,v in screens.items() if v['retain_for_observation']],
        robust=[a for a,v in screens.items() if v['robust_superiority']],metrics={a:{k:r[job_name((a,5,0,'evaluation'))][k] for k in ('cagr','sharpe_zero_cash','max_drawdown','calmar')} for a in ARMS})


def flow(arm):
    steps=['Verify pinned audited adjusted ETF prices, exact economic vintages, source and model hashes',
        'Monthly prior-close decisions; base 63-session inverse-volatility budgets and 2% cash floor',
        '14 candidates: original 12 + XLE/XLB; 21/63/126 momentum, positive 126 gate; top six, minimum four',
        'Fewer than four: retain eligible IEF/TLT/GLD incoming weights only; residual stays cash',
        'Causal per-pool XGBoost → relative momentum → adaptive trend → audited raw activity lag20 → USD ridge']
    if arm in ['F3','CR12']:
        steps[2]='Original 12 candidates; 63/126/252 momentum, positive 252 gate; top six/minimum four'
        steps[4]='Original causal XGBoost → relative momentum → adaptive trend → legacy activity lag20 → USD ridge'
    if arm=='CP' or arm in VARIANTS:steps+=['Explicit final target cap 45%; excess becomes cash; isolate this cap with CP versus M1']
    elif arm=='CR12':steps+=['Retain the monitored recipe’s original capped-F3 parent, with 45% target cap and excess cash']
    if arm in VARIANTS:
        group,kind=VARIANTS[arm]
        steps += [f'{group}: exact prior-day economic vintages; missing inputs or fewer than 36 completed labels abstain to CP',
            'Separate per-ETF expanding model; next-rebalance open return labels must end before prior-close cutoff',
            'Ridge alpha1; training-only scaling' if kind=='linear' else 'Depth-two regression tree; minimum 12 rows per leaf',
            'Forecast increment >25bp and absolute forecast positive: ×1.10; increment <−25bp: ×0.90; otherwise unchanged',
            'Normalize within selected positive positions only; preserve exact CP gross/cash and 45% target cap']
    elif arm=='CR12':steps+=['Unchanged monitored 12-ETF leading/context ridge; availability and model contract retained']
    elif arm=='RP14':steps=steps[:2]+['Allocate across all 14 ETFs by inverse realized volatility; benchmark only, no momentum selection']
    elif arm=='URTH':steps=['Pinned audited adjusted URTH history; buy once with initial USD capital and hold']
    steps+=['Next session open; whole adjusted units; sale before buy; 5bp primary costs and zero-interest USD cash',
        'Daily NAV, held weights, matched benchmarks and complete report; finite research, no allocation authority']
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {len(steps)*57+10}">'
    for i,text in enumerate(steps):svg+=f'<rect x="5" y="{i*57+5}" width="1190" height="48" rx="8" fill="#e9f1f5"/><text x="16" y="{i*57+34}" font-family="sans-serif" font-size="12">{i+1}. {html.escape(text)}</text>'
    return svg+'</svg>'


def artifacts(root,output):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data,render_backtest_report_html
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json');report=read_json(root/'report.json')
    if sha256(root/'report.json')!=read_json(root/'report_receipt.json')['sha256']:raise ValueError('Changed report')
    p=report['protocol'];r=report['results'];diag=report['diagnostics'];output.mkdir(parents=True,exist_ok=True);(output/'reports').mkdir(exist_ok=True)
    economics={};quotes={};results={}
    for a in ARMS:
        name=job_name((a,5,0,'full'));economics[a]=read_json(root/'python'/(name+'.json'));quotes[a]=read_json(root/'bundles'/name/'quotes.json')
        results[a]=report_result(economics[a],quotes[a],p['initial_cash_usd'],'2015-12-31')
    for a in ARMS:
        data,warnings=build_backtest_report_data(result=results[a],result_path=root/'python'/(job_name((a,5,0,'full'))+'.json'),split_date=p['evaluation_start'],
            benchmark_name=LABELS['F3'],benchmark_nav_series=results['F3']['nav_series'],
            extra_benchmarks=[dict(id=b,name=LABELS[b],nav_series=results[b]['nav_series']) for b in ('M1','CP','CR12','RP14','URTH') if b!=a],
            market_prices={s:{d:float(q['close']) for d,q in rows.items()} for s,rows in quotes[a].items()},market_fx_rates={v['date']:1. for v in economics[a]['nav']})
        data.update(title=LABELS[a]+' · expanded economics',accountingCurrency='USD',database='Published audited histories and pinned economic vintages',allocationSource='Simulated fills',
            splitLabel='Previously inspected chronological boundary',sampleLabels={'in_sample':'2016–2020 retrospective','out_of_sample':'2021 onward retrospective'},
            decisionDiagrams=[dict(title='Complete decision flow',svg=flow(a))],strategyDefinition=dict(id=a,protocol=p),
            warnings=[*warnings,*p['limitations'],'Full report carries the original 2016 portfolio; primary evaluation tables use a separate fresh-cash 2021 replay. Chart includes the prior-close capital anchor; calendar CAGR conventions differ slightly.'])
        last=max(economics[a]['decisions']);weights={t['symbol']:float(t['target_weight']) for t in economics[a]['decisions'][last]['targets']};s=r[job_name((a,5,0,'full'))]
        table=f'<section style="margin:24px"><h2>Last scheduled targets and held weights</h2><p>Target session {last}; holdings at {p["end"]}. Finite historical study; no new indicative or monitored allocation.</p><table><tr><th>Asset</th><th>Target</th><th>Held</th></tr>'
        for symbol in sorted(quotes[a]):table+=f'<tr><td>{symbol}</td><td>{weights.get(symbol,0):.2%}</td><td>{s["last_held_weights"].get(symbol,0):.2%}</td></tr>'
        table+=f'<tr><td>Cash</td><td>{1-sum(weights.values()):.2%}</td><td>{1-sum(s["last_held_weights"].values()):.2%}</td></tr></table></section>'
        rendered=render_backtest_report_html(data).replace('</body>',table+'</body>');rendered=re.sub(r'(href=["\'])(/[^"\']*)',r'\1http://127.0.0.1:8000\2',rendered)
        (output/'reports'/(a+'.html')).write_text(rendered,encoding='utf8')
    fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
    for a,color in [('M1','#334955'),('CP','#899a9f'),('CR','#287c9b'),('FR','#b87525'),('AR','#31886e'),('F3','#9460a6')]:
        v=np.array([float(x['nav'])/1e6 for x in economics[a]['nav']]);days=[date.fromisoformat(x['date']) for x in economics[a]['nav']]
        axes[0].plot(days,v,label=a+' · '+LABELS[a],color=color);axes[1].plot(days,v/np.maximum.accumulate(np.maximum(v,1))-1,color=color)
    axes[0].legend(ncol=2,fontsize=9);axes[0].set_ylabel('Value / initial USD');axes[1].set_ylabel('Drawdown');axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Economic information on M1/14 · USD · 5bp · retrospective');fig.tight_layout();fig.savefig(output/'comparison.png',dpi=150);plt.close(fig)
    body='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Economic signals on M1/14</title><style>body{font:16px system-ui;max-width:1300px;margin:32px auto;padding:0 20px;color:#233748;background:#f6f8fa}table{border-collapse:collapse;width:100%;background:white}th,td{padding:8px;text-align:right;border-bottom:1px solid #ddd}td:first-child,th:first-child{text-align:left}img{width:100%}li{margin:9px 0}a{color:#17549d}code{overflow-wrap:anywhere}.scroll{overflow:auto}</style></head><body><h1>Economic signals on M1/14</h1>'
    body+='<p>Fixed faster momentum on 14 candidates; no forced holdings. Economic context (13 features), financial conditions (8), and both combined (21). Ridge and depth-two trees reuse the prior model capacity. All economic arms tilt the same explicitly capped M1 parent; CP − M1 separates the cap effect.</p>'
    retained=[a for a,v in report['screens'].items() if v['retain_for_observation']];robust=[a for a,v in report['screens'].items() if v['robust_superiority']]
    body+='<p><strong>Predeclared result:</strong> '+('Retain for observation: '+', '.join(retained)+'. ' if retained else 'No economic variant clears the retention screen. ')+('Robust superiority: '+', '.join(robust)+'.' if robust else 'No variant establishes robust superiority over the matched control.')+' Monitored definitions, funded F3 and execution authority remain unchanged.</p>'
    body+=f'<p><strong>Cap bridge:</strong> {diag["cap_bridge"]["affected_decisions"]} of 130 monthly targets change; mean added target cash is {diag["cap_bridge"]["mean_target_cash_added"]:.2%} of NAV. Model arms preserve CP’s cash exactly. Rejecting an ETF remains binding even when its economic forecast is positive.</p>'
    for window,label in [('evaluation','Primary evaluation: 2021-01-04–2026-10-08'),('full','Full context: 2016-01-04–2026-10-08')]:
        body+=f'<h2>{label}</h2><p>USD; 5bp per traded dollar; zero-interest cash; previously inspected history.</p><div class="scroll"><table><tr><th>Complete report</th><th>CAGR</th><th>Sharpe</th><th>Max drawdown</th><th>Calmar</th><th>Turnover/year</th><th>Mean cash</th></tr>'
        for a in ['F3','CR12','M1','CP',*VARIANTS,'RP14','URTH']:
            s=r[job_name((a,5,0,window))];body+=f'<tr><td><a href="reports/{a}.html">{a} · {LABELS[a]}</a></td><td>{s["cagr"]:.2%}</td><td>{s["sharpe_zero_cash"]:.3f}</td><td>{s["max_drawdown"]:.2%}</td><td>{s["calmar"]:.3f}</td><td>{s["annual_turnover"]:.2f}×</td><td>{s["mean_cash_weight"]:.2%}</td></tr>'
        body+='</table></div>'
    body+='<img src="comparison.png" alt="Portfolio growth and drawdowns"><h2>Information availability and completed labels</h2><table><tr><th>Feature group</th><th>Ready evaluation decisions</th><th>First / last training rows</th><th>Abstention dates</th></tr>'
    for g,v in diag['availability'].items():body+=f'<tr><td>{g}</td><td>{v["ready"]}/{v["total"]}</td><td>{v["first_training_rows"]} / {v["last_training_rows"]}</td><td>{", ".join(v["abstained"]) or "none"}</td></tr>'
    body+='</table><p>MR and AR have identical training rows and decision availability. Missing observations remain missing; old decisions are not repaired using new captures.</p><h2>Forecast usefulness</h2><p>Completed evaluation months only. MAE is next-month adjusted open-to-open return error; lower is better. The comparator predicts each ETF’s own training-sample mean. ETF rows share monthly economic shocks and are not independent observations.</p><table><tr><th>Group / model / subset</th><th>Months</th><th>Model MAE</th><th>Training-mean MAE</th><th>Sign accuracy</th><th>Mean rank IC</th></tr>'
    for key,v in diag['forecast_summary'].items():
        body+=f'<tr><td>{key}</td><td>{v["months"]}</td><td>{v["mae"]:.2%}</td><td>{v["mean_baseline_mae"]:.2%}</td><td>{v["sign_accuracy"]:.1%}</td><td>{v["rank_ic"]:.3f}</td></tr>'
    body+='</table><h2>Where economic models change allocations</h2><p>Counts cover the 70 evaluation decisions, relative to CP; a selected asset can receive a higher or lower weight. XLE/XLB remain candidates throughout.</p><table><tr><th>Arm</th><th>Changed decisions</th><th>XLE increased / reduced</th><th>XLB increased / reduced</th></tr>'
    for a,v in diag['allocation'].items():body+=f'<tr><td>{a}</td><td>{v["changed_decisions"]}/70</td><td>{v["assets"]["XLE"]["increased"]} / {v["assets"]["XLE"]["decreased"]}</td><td>{v["assets"]["XLB"]["increased"]} / {v["assets"]["XLB"]["decreased"]}</td></tr>'
    body+='</table><h2>Conditional responses for the added ETFs</h2><p>Last ready model per group. Difference in forecast when one feature moves from its training 25th to 75th percentile, holding the other query values fixed. These are model associations, not identified economic shocks.</p>'
    for group,entry in diag['latest_conditional_responses'].items():
        body+=f'<details><summary>{group} · model {entry["decision"]}</summary><table><tr><th>Feature</th><th>XLE ridge / tree</th><th>XLB ridge / tree</th></tr>'
        for feature in entry['features']:
            body+='<tr><td>'+html.escape(feature)+'</td>'
            for symbol in ('XLE','XLB'):
                v=entry['models'][symbol]['sensitivities'][feature];body+=f'<td>{v["linear"]:+.2%} / {v["tree"]:+.2%}</td>'
            body+='</tr>'
        body+='</table></details>'
    body+='<h2>Paired uncertainty</h2><p>10,000 joint circular month-block draws. Holm adjustment covers all 18 declared comparisons per block length. Annualized arithmetic mean difference is not CAGR; Sharpe and Calmar intervals are marginal, with bootstrap Calmar annualized at 252 sessions.</p>'
    for block in p['bootstrap_blocks']:
        body+=f'<details {"open" if block==6 else ""}><summary>{block}-month blocks</summary><table><tr><th>Pair</th><th>Annual mean difference (95% CI)</th><th>Holm p</th><th>Sharpe difference (95% CI)</th><th>Calmar difference (95% CI)</th></tr>'
        for i,(a,b) in enumerate(COMPARISONS):
            m=report['uncertainty']['means'][str(block)][i];ratio=report['uncertainty'][a+'-'+b][str(block)];s=ratio['sharpe'];c=ratio['calmar_252']
            body+=f'<tr><td>{a} − {b}</td><td>{m["mean_annual"]:+.2%} ({m["ci95"][0]:+.2%}, {m["ci95"][1]:+.2%})</td><td>{m["holm_p"]:.3f}</td><td>{s["difference"]:+.3f} ({s["ci95"][0]:+.3f}, {s["ci95"][1]:+.3f})</td><td>{c["difference"]:+.3f} ({c["ci95"][0]:+.3f}, {c["ci95"][1]:+.3f})</td></tr>'
        body+='</table></details>'
    body+='<h2>Predeclared retention assessment</h2><p>'+html.escape(p['assessment'])+'</p><table><tr><th>Arm</th><th>Failed checks</th><th>Retain for observation</th><th>Family return evidence</th></tr>'
    for a,v in report['screens'].items():body+=f'<tr><td>{a}</td><td>{", ".join(k for k,x in v["checks"].items() if not x) or "none"}</td><td>{v["retain_for_observation"]}</td><td>{v["family_return_evidence"]}</td></tr>'
    body+='</table><h2>Costs and execution delay · 2021+</h2><table><tr><th>Arm</th><th>10bp CAGR / Sharpe</th><th>20bp CAGR / Sharpe</th><th>One-session delay CAGR / Sharpe</th></tr>'
    for a in ARMS:
        body+='<tr><td>'+a+'</td>'
        for c,d in ((10,0),(20,0),(5,1)):
            s=r[job_name((a,c,d,'evaluation'))];body+=f'<td>{s["cagr"]:.2%} / {s["sharpe_zero_cash"]:.3f}</td>'
        body+='</tr>'
    body+='</table><h2>Historical stability and concentration</h2><p>Year omissions are descriptive return-series sensitivities; no elapsed-calendar CAGR is computed across the gaps.</p><table><tr><th>Arm</th><th>2016–2020 CAGR / Sharpe</th><th>Sharpe excluding 2020</th><th>Sharpe excluding 2022</th><th>Maximum held ETF weight</th></tr>'
    for a in ARMS:
        ctx=report['context'][a];s=r[job_name((a,5,0,'full'))];cal=ctx['2016_2020']
        body+=f'<tr><td>{a}</td><td>{cal["cagr"]:.2%} / {cal["sharpe_zero_cash"]:.3f}</td><td>{ctx["exclude_2020"]["sharpe_zero_cash"]:.3f}</td><td>{ctx["exclude_2022"]["sharpe_zero_cash"]:.3f}</td><td>{s["maximum_weight"]:.2%}</td></tr>'
    body+='</table><h2>Annual returns</h2><p>2026 is year-to-date through October 8.</p><div class="scroll"><table><tr><th>Arm</th>'+''.join('<th>'+y+'</th>' for y in r[job_name(('M1',5,0,'full'))]['calendar_returns'])+'</tr>'
    for a in ARMS:body+='<tr><td>'+a+'</td>'+''.join(f'<td>{v:.1%}</td>' for v in r[job_name((a,5,0,'full'))]['calendar_returns'].values())+'</tr>'
    body+='</table></div><h2>Evidence and limitations</h2><p>104 accounting replays, 13 independent native checks, 520 monthly group-model evaluations, 57 inference jobs. Insufficient-history evaluations abstain without fitting. Exact M1/F3/CR12/RP14/URTH control reproduction; all 130 original economic feature states reproduced from pinned published snapshots.</p><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in p['limitations'])+'</ul>'
    body+='<p>Protocol SHA-256: <code>'+sha256(root/'protocol.json')+'</code></p></body></html>'
    (output/'index.html').write_text(body,encoding='utf8');(output/'presentation_source').mkdir(exist_ok=True)
    (output/'presentation_source'/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    write_json(root/'presentation_receipt.json',dict(report_sha256=sha256(root/'report.json'),analysis_sha256=sha256(Path(__file__)),
        outputs={f.relative_to(output).as_posix():sha256(f) for f in output.rglob('*') if f.is_file()}))
    return dict(index=str(output/'index.html'),complete_reports=len(ARMS))
