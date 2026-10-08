"""Predeclared diagnostics, paired inference and full economic research reports."""
from datetime import date
import html
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json, checked_files
from systematic_trading.research.economic_response_study import ARMS, LABELS, VARIANTS, COMPARISONS, job_name


def inference_job(job):
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    from systematic_trading.research.construction_analysis import bootstrap_ratios
    root,kind,block,index=job;root=Path(root);p=read_json(root/'protocol.json')
    if read_json(root/'statistics_receipt.json')['sha256'] != sha256(root/'statistics.json'):
        raise ValueError('Changed statistics')
    results=read_json(root/'statistics.json')
    def primary(arm):return results[job_name((arm,5,0,'evaluation'))]
    if kind=='means':
        months=sorted(primary('P3')['monthly'])
        matrix=np.array([[primary(a)['monthly'][m]-primary(b)['monthly'][m] for a,b in COMPARISONS] for m in months])
        return kind,str(block),paired_bootstrap(matrix,block=block,replications=p['bootstrap_replications'],seed=p['seed'])
    a,b=COMPARISONS[index];left,right=primary(a),primary(b)
    if left['dates'] != right['dates']:raise ValueError('Paired calendars differ')
    return f'{a}-{b}',str(block),bootstrap_ratios(left['dates'],left['daily_returns'],right['daily_returns'],
        block=block,replications=p['bootstrap_replications'],seed=p['seed'])


def diagnostics(root):
    from systematic_trading.research.construction_analysis import ranks
    p=read_json(root/'protocol.json');models=read_json(root/'models.json');features=read_json(root/'features.json')
    opens={s:{r['trade_date']:float(r['open']) for r in rows} for s,rows in read_json(root/'bars.json').items()}
    days=sorted(models);evaluation=[d for d in days if d>=p['evaluation_start']]
    records=[];availability={};latest={}
    for group in ['leading','matched','combined']:
        available=[d for d in evaluation if models[d][group]['ready']]
        availability[group]=dict(evaluation_decisions=len(evaluation),ready=len(available),abstained=len(evaluation)-len(available),
            abstention_dates=[d for d in evaluation if not models[d][group]['ready']],
            training_rows_first=models[evaluation[0]][group]['training_rows'],training_rows_last=models[evaluation[-1]][group]['training_rows'])
        if available:
            day=available[-1];latest[group]=dict(decision=day,models=models[day][group]['models'],features=models[day][group]['features'],
                feature_quartiles=models[day][group]['feature_quartiles'],query=models[day][group]['query'])
        for day,end in zip(days,days[1:]):
            fitted=models[day][group]
            if day<p['evaluation_start'] or not fitted['ready']:continue
            symbols=sorted(opens);actual=np.array([opens[s][end]/opens[s][day]-1 for s in symbols])
            means=np.array([fitted['models'][s]['mean_return'] for s in symbols])
            for kind in ['tree','linear']:
                forecasts=np.array([fitted['models'][s][kind+'_forecast'] for s in symbols])
                x,y=ranks(forecasts),ranks(actual)
                ic=float(np.corrcoef(x,y)[0,1]) if np.std(x)>0 and np.std(y)>0 else None
                records.append(dict(day=day,label_end=end,group=group,kind=kind,assets=len(symbols),rank_ic=ic,
                    mean_absolute_error=float(np.mean(np.abs(forecasts-actual))),
                    mean_baseline_error=float(np.mean(np.abs(means-actual))),
                    positive_sign_accuracy=float(np.mean((forecasts>0)==(actual>0)))))
    forecast_summary={}
    for group in availability:
        for kind in ['tree','linear']:
            rows=[r for r in records if (r['group'],r['kind'])==(group,kind)]
            ics=[r['rank_ic'] for r in rows if r['rank_ic'] is not None]
            forecast_summary[group+'/'+kind]=dict(months=len(rows),mean_rank_ic=float(np.mean(ics)) if ics else None,
                mae=float(np.mean([r['mean_absolute_error'] for r in rows])) if rows else None,
                mean_baseline_mae=float(np.mean([r['mean_baseline_error'] for r in rows])) if rows else None,
                positive_sign_accuracy=float(np.mean([r['positive_sign_accuracy'] for r in rows])) if rows else None)
    parent=read_json(root/'decisions/P3.json');allocation={}
    for arm in VARIANTS:
        candidate=read_json(root/'decisions'/(arm+'.json'));benefit={s:0 for s in opens};reduce={s:0 for s in opens}
        changed=0
        for day in evaluation:
            a={t['symbol']:float(t['target_weight']) for t in candidate[day]['targets']}
            b={t['symbol']:float(t['target_weight']) for t in parent[day]['targets']}
            changed+=any(abs(a[s]-b[s])>1e-12 for s in a)
            for s in a:benefit[s]+=int(a[s]>b[s]+1e-12);reduce[s]+=int(a[s]<b[s]-1e-12)
        allocation[arm]=dict(changed_decisions=changed,increased=benefit,decreased=reduce)
    return dict(availability=availability,forecast_summary=forecast_summary,forecast_records=records,
        latest_conditional_responses=latest,allocation=allocation,
        leading_ready=sum(r['leading_ready'] for r in features.values()),
        combined_ready=sum(r['leading_ready'] and r['context_ready'] for r in features.values()))


def finalize(root, inference):
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json')
    p=read_json(root/'protocol.json');results=read_json(root/'statistics.json');group={}
    for kind,block,value in inference:group.setdefault(kind,{})[block]=value
    screens={}
    for arm in ['LT','LR','CT','CR']:
        def result(a,c=5,d=0):return results[job_name((a,c,d,'evaluation'))]
        controls={'LT':['P3','LR'],'LR':['P3'],'CT':['P3','MT','CR'],'CR':['P3','MR']}[arm]
        checks={f'{metric}_above_{control}':result(arm)[metric] is not None and result(arm)[metric]>result(control)[metric]
            for metric in ['sharpe_zero_cash','calmar'] for control in controls}
        checks.update(cost20_cagr=result(arm,20)['cagr']>=result('P3',20)['cagr']-.005,
            primary_drawdown=result(arm)['max_drawdown']>=result('P3')['max_drawdown']-.005,
            delayed_sharpe=result(arm,5,1)['sharpe_zero_cash']>result('P3',5,1)['sharpe_zero_cash'],
            delayed_calmar=result(arm,5,1)['calmar']>result('P3',5,1)['calmar'])
        screens[arm]=dict(checks=checks,passed=all(checks.values()),decision='retain for further evidence' if all(checks.values()) else 'reject as replacement')
    # Exact unchanged controls must still match the previously frozen full-period study.
    parent=Path(read_json(root/'data_receipt.json')['parent']);parity={}
    for arm in ['F0','F3']:
        original=parent/'python'/f'{arm}-cost5-delay0.json'
        if not original.exists():
            matches=list((parent/'python').glob(f'{arm}*cost5*delay0*.json'))
            matches=[f for f in matches if not f.name.endswith('.receipt.json')]
            if len(matches)!=1:raise ValueError('Cannot identify exact parent replay for parity')
            original=matches[0]
        before=read_json(original);after=read_json(root/'python'/(job_name((arm,5,0,'full'))+'.json'))
        for field in ['fills','nav','final_positions']:
            if before[field]!=after[field]:raise ValueError('Unchanged baseline replay differs: '+arm+'/'+field)
        parity[arm]=dict(exact=True,parent=str(original),sha256=sha256(original))
    report=dict(protocol=p,results=results,inference=group,screens=screens,diagnostics=diagnostics(root),
        baseline_parity=parity,promotion_eligible=False)
    write_json(root/'report.json',report)
    write_json(root/'report_receipt.json',dict(sha256=sha256(root/'report.json'),input_manifest_sha256=sha256(root/'input_manifest.json'),
        decision_manifest_sha256=sha256(root/'decision_manifest.json'),statistics_sha256=sha256(root/'statistics.json')))
    return dict(screens=screens,primary={a:{k:results[job_name((a,5,0,'evaluation'))][k] for k in ['cagr','sharpe_zero_cash','calmar','max_drawdown']} for a in ARMS})


def flow_svg(arm):
    steps=['Verify pinned audited adjusted ETF histories, original economic vintages and source/model hashes',
        'Monthly signal at the completed prior close; no current decision-open input',
        'Parent: 63-session inverse volatility → positive 252-session momentum → price/volume top 6',
        'Fewer than four qualify: qualifying IEF/TLT/GLD incoming weights only; remaining capital cash' if arm!='F0' else 'F0 legacy fallback: original incoming basket',
        'Existing XGBoost tilt → relative momentum → adaptive trend → activity lag-20 → USD model',
        'Preserve fallback membership and reduced budget through parent overlays']
    if arm not in ['F0','F3']:steps+=['P3: cap final ETF targets at 45%; excess stays cash']
    if arm in VARIANTS:
        group,kind=VARIANTS[arm]
        steps += [f'{group} features; require original-vintage freshness and complete windows, otherwise abstain to P3',
            'Fit separate models per ETF: expanding history, minimum 36 completed monthly labels; training-only preprocessing',
            f'{kind}: '+('depth 2, minimum 12 rows per leaf' if kind=='tree' else 'standardized ridge, alpha 1'),
            'Increment above +25bp and forecast positive: factor 1.10; below -25bp: 0.90; otherwise 1.00',
            'Normalize within existing positive targets; retain P3 gross and cash; enforce 45% final target cap']
    steps+=['Prior-close sizing → next-session open fills; whole adjusted units; sell before buy; 5bp primary costs',
        'Daily holdings, cash and NAV from reconciled fill ledger; cash interest zero; no order authority']
    if arm in ['RP','URTH']:
        steps=['Verify the identical published adjusted-price batch and evaluation calendar',
            'Monthly inverse volatility, base cap 45%, reserve 2%' if arm=='RP' else 'Buy and hold URTH from the evaluation start',
            'Prior-close sizing, next-session open fills, whole adjusted units and 5bp costs',
            'Reconcile daily holdings, cash and NAV; research reference only']
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 {72*len(steps)+20}" role="img" aria-label="Complete economic strategy decision flow">'
    for i,text in enumerate(steps):
        y=10+72*i;svg+=f'<rect x="10" y="{y}" width="1080" height="56" rx="8" fill="#edf5f8" stroke="#a5bdcb"/><text x="25" y="{y+33}" font-family="sans-serif" font-size="13">{i+1}. {html.escape(text)}</text>'
    return svg+'</svg>'


def build_artifacts(root, output):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data,render_backtest_report_html
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json')
    if read_json(root/'report_receipt.json')['sha256'] != sha256(root/'report.json'):raise ValueError('Changed report')
    report=read_json(root/'report.json');p=report['protocol'];output.mkdir(parents=True,exist_ok=True)
    results,economics,quotes={},{},{}
    for arm in ARMS:
        name=job_name((arm,5,0,'evaluation'));economics[arm]=read_json(root/'python'/(name+'.json'))
        quotes[arm]=read_json(root/'bundles'/name/'quotes.json')
        results[arm]=report_result(economics[arm],quotes[arm],'1000000','2020-12-31')
    detail=output/'reports';detail.mkdir(exist_ok=True)
    for arm in ARMS:
        name=job_name((arm,5,0,'evaluation'))
        data,warnings=build_backtest_report_data(result=results[arm],result_path=root/'python'/(name+'.json'),
            split_date='2023-01-01',benchmark_name='Current SOTA reference · USD',benchmark_nav_series=results['F0']['nav_series'],
            extra_benchmarks=[dict(id=k,name=LABELS[k]+' · USD',nav_series=results[k]['nav_series']) for k in ['F3','P3','RP','URTH'] if k!=arm],
            market_prices={s:{d:float(v['close']) for d,v in rows.items()} for s,rows in quotes[arm].items()},
            market_fx_rates={r['date']:1. for r in economics[arm]['nav']})
        data.update(title=LABELS[arm]+' · economic research',accountingCurrency='USD',database='Pinned audited prices and daily economic vintages',
            allocationSource='Daily held/target weights and NAV reconstructed from the complete simulated ledger; evaluation starts in cash.',
            splitLabel='Previously inspected calendar boundary',sampleLabels={'in_sample':'2021–2022 retrospective','out_of_sample':'2023 onward retrospective'},
            decisionDiagrams=[dict(title='Complete decision flow',svg=flow_svg(arm))],
            strategyDefinition=dict(id=arm,name=LABELS[arm],protocol_version=p['version'],features=p['feature_rule'],model=p['model_rule']),
            warnings=[*warnings,*p['limitations'],'Research only; not a monitored or execution-authorized strategy.'])
        (detail/(arm+'.html')).write_text(render_backtest_report_html(data),encoding='utf-8')
    fig,axes=plt.subplots(2,2,figsize=(15,9),sharex='col')
    for col,(arms,title) in enumerate([(['F3','P3','LT','LR','F0'],'Leading models versus both parent controls'),
                                     (['P3','MT','MR','CT','CR'],'Context addition on matched samples')]):
        for arm in arms:
            nav=np.array([float(r['nav'])/1e6 for r in economics[arm]['nav']]);days=[date.fromisoformat(r['date']) for r in economics[arm]['nav']]
            axes[0,col].plot(days,nav,label=arm);axes[1,col].plot(days,nav/np.maximum.accumulate(np.maximum(nav,1))-1,label=arm)
        axes[0,col].set_title(title);axes[0,col].legend(ncol=3);axes[0,col].set_ylabel('Value / initial USD capital')
        axes[1,col].set_ylabel('Drawdown');axes[1,col].yaxis.set_major_formatter(PercentFormatter(1))
        for ax in axes[:,col]:ax.grid(alpha=.2)
    fig.suptitle('Ex-ante economic features · retrospective 2021–6 Oct 2026 evaluation · 5bp costs · zero cash interest')
    fig.tight_layout();fig.savefig(output/'comparison.png',dpi=150);plt.close(fig)
    def table(headers,rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    rows=[]
    for arm in ARMS:
        r=report['results'][job_name((arm,5,0,'evaluation'))]
        rows.append([f'<a href="reports/{arm}.html">{arm}</a>',html.escape(LABELS[arm]),f'{r["cagr"]:.2%}',f'{r["sharpe_zero_cash"]:.3f}',
            f'{r["calmar"]:.3f}',f'{r["max_drawdown"]:.2%}',f'{r["annual_turnover"]:.2f}',f'{r["mean_gross"]:.1%}'])
    main=table(['Arm','Full report','CAGR','Sharpe','Calmar','Max drawdown','Turnover/year','Mean invested'],rows)
    verdict='; '.join(a+': '+r['decision'] for a,r in report['screens'].items())
    availability=table(['Group','Ready decisions','Abstained','Training rows at first / last evaluation'],[
        [g,str(r['ready'])+' / '+str(r['evaluation_decisions']),str(r['abstained']),str(r['training_rows_first'])+' / '+str(r['training_rows_last'])]
        for g,r in report['diagnostics']['availability'].items()])
    inference=table(['Comparison','Annualized mean difference','Holm p (6-month blocks)','Sharpe difference 95% interval'],[
        [a+' − '+b,f'{report["inference"]["means"]["6"][i]["mean_annual"]:.2%}',f'{report["inference"]["means"]["6"][i]["holm_p"]:.3f}',
         html.escape(str(report['inference'][a+'-'+b]['6']['sharpe']['ci95']))] for i,(a,b) in enumerate(COMPARISONS)])
    robustness=table(['Arm','20bp CAGR','20bp Sharpe','Delayed Sharpe','Delayed Calmar','Screen'],[
        [a,f'{report["results"][job_name((a,20,0,"evaluation"))]["cagr"]:.2%}',f'{report["results"][job_name((a,20,0,"evaluation"))]["sharpe_zero_cash"]:.3f}',
         f'{report["results"][job_name((a,5,1,"evaluation"))]["sharpe_zero_cash"]:.3f}',f'{report["results"][job_name((a,5,1,"evaluation"))]["calmar"]:.3f}',
         report['screens'][a]['decision']] for a in report['screens']])
    latest=report['diagnostics']['latest_conditional_responses']['leading']
    sensitivities=table(['ETF',*latest['features']],[[s,*[f'{m["sensitivities"][f]["tree"]*10000:+.0f} / {m["sensitivities"][f]["linear"]*10000:+.0f}' for f in latest['features']]] for s,m in latest['models'].items()])
    allocation=table(['Arm','Decisions changed','ETFs increased (decision count)','ETFs decreased (decision count)'],[
        [a,str(r['changed_decisions']),', '.join(s+': '+str(n) for s,n in r['increased'].items() if n),', '.join(s+': '+str(n) for s,n in r['decreased'].items() if n)]
        for a,r in report['diagnostics']['allocation'].items()])
    body=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Leading economic ETF research</title>
<style>body{{font:15px/1.6 system-ui;color:#20354c;background:#f3f6fa;margin:0}}main{{max-width:1400px;margin:24px auto;padding:28px;background:white}}h1{{line-height:1.2}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:10px;border-bottom:1px solid #dde4ed;text-align:right}}td:first-child,td:nth-child(2){{text-align:left}}th{{background:#eef4f8}}.scroll{{overflow:auto}}img{{width:100%}}a{{color:#245ac3}}li{{margin:.5em 0}}code{{overflow-wrap:anywhere}}.notice{{background:#fff7db;padding:16px;border:1px solid #e9cc76}}</style><main>
<p>Finite ETF research · October 7, 2026 · No promotion</p><h1>Do leading economic indicators improve the defensive ETF strategy?</h1>
<p class="notice">{html.escape(verdict)}. This is retrospective walk-forward evidence; no untouched holdout or causal-shock claim.</p>
<p>Seven leading indicators, with payrolls, manufacturing output and headline/core inflation tested as a separate context group. National PMI and consensus surprises remain unavailable. Each ETF gets its own forecast; economic beneficiaries can gain weight within the existing eligible basket.</p>
<h2>Portfolio comparison</h2><p>January 2021–October 6, 2026; USD 1m initially; 5bp primary costs. P3 is the common final-cap control. Macro models preserve its invested amount and cash, and cannot add an ineligible ETF. Click an arm for the complete shared report, including NAV, held/target weights, benchmarks and decision flow.</p>{main}<img src="comparison.png" alt="Economic model portfolio values and drawdowns">
<h2>What the economic models actually changed</h2>{allocation}<h2>Missing data and sample control</h2>{availability}<p>MT and MR use exactly the combined models’ training rows and current availability, with leading features only. Compare CT with MT and CR with MR to isolate added context. Missing CPI windows remain missing; no later vintage was inserted.</p>
<h2>Costs and execution delay</h2>{robustness}<h2>Uncertainty across the registered comparison family</h2>{inference}<p>Also evaluated 3- and 12-month blocks, 20,000 joint resamples each. Mean-return p-values use Holm correction; ratio intervals are marginal and must not be treated as nine independent discoveries.</p>
<h2>Different assets, different conditional responses</h2><p>Latest available leading-model decision: {latest['decision']}. Each cell shows tree / ridge predicted return change in basis points when one feature moves from its training 25th to 75th percentile, holding the others at the query value. Positive means a modeled beneficiary of that feature increase; negative means weaker modeled returns. These are conditional associations, not causal shock sensitivities. A zero tree response can mean both probe values remain in one leaf.</p>{sensitivities}
<h2>Frozen contract and limitations</h2><p>Protocol hash: <code>{sha256(root/'protocol.json')}</code>. {p['budget']['replays']} price/cost/delay replays; {p['budget']['native_checks']} independent native accounting checks; all {p['budget']['paired_comparisons']} contrasts retained.</p><ul>{''.join('<li>'+html.escape(v)+'</li>' for v in p['limitations'])}</ul></main></html>'''
    (output/'assessment.html').write_text(body,encoding='utf-8')
    write_json(output/'artifact_manifest.json',{str(f.relative_to(output)):sha256(f) for f in output.rglob('*') if f.is_file() and f.name!='artifact_manifest.json'})
    return str(output/'assessment.html')
