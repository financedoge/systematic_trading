"""Predeclared diagnostics, inference and complete financial challenger reports."""
from datetime import date
import html
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json, checked_files
from systematic_trading.research.economic_financial_study import ARMS, LABELS, VARIANTS, COMPARISONS, job_name


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
    for group in ['financial','matched','augmented']:
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
        financial_ready=sum(r['financial_ready'] for r in features.values()),
        augmented_ready=sum(r['financial_ready'] and r['leading_ready'] and r['context_ready'] for r in features.values()))


def finalize(root, inference):
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json')
    p=read_json(root/'protocol.json');results=read_json(root/'statistics.json');group={}
    for kind,block,value in inference:group.setdefault(kind,{})[block]=value
    screens={}
    for arm in ['FR','FT','AR','AT']:
        def result(a,c=5,d=0):return results[job_name((a,c,d,'evaluation'))]
        controls={'FR':['P3','CR'],'FT':['P3','CR','FR'],'AR':['P3','CR','MR'],'AT':['P3','CR','MR','AR']}[arm]
        checks={f'{metric}_above_{control}':result(arm)[metric] is not None and result(arm)[metric]>result(control)[metric]
            for metric in ['sharpe_zero_cash','calmar'] for control in controls}
        checks.update(cost20_cagr=result(arm,20)['cagr']>=result('CR',20)['cagr']-.005,
            primary_drawdown=result(arm)['max_drawdown']>=result('CR')['max_drawdown']-.005,
            delayed_sharpe=result(arm,5,1)['sharpe_zero_cash']>result('CR',5,1)['sharpe_zero_cash'],
            delayed_calmar=result(arm,5,1)['calmar']>result('CR',5,1)['calmar'])
        screens[arm]=dict(checks=checks,passed=all(checks.values()),decision='retain for further evidence' if all(checks.values()) else 'reject as replacement')
    # Exact unchanged controls must still match the previously frozen full-period study.
    parent=Path(read_json(root/'data_receipt.json')['parent']);parity={}
    for arm in ['F0','F3','P3','CR']:
        original=parent/'python'/(job_name((arm,5,0,'full'))+'.json')
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
    from systematic_trading.research.economic_response_analysis import flow_svg as parent_flow
    if arm not in VARIANTS:
        return parent_flow(arm)
    group,kind = VARIANTS[arm]
    steps = ['Verify pinned audited adjusted prices, exact economic vintages and frozen source/model hashes',
        'Monthly signal at completed prior close; never read the decision open while fitting',
        '63-session inverse volatility → positive 252-session momentum → price/volume top 6',
        'Fewer than four qualify: eligible IEF/TLT/GLD incoming weights only; remaining capital cash',
        'Existing XGBoost → relative momentum → adaptive trend → activity lag-20 → USD model',
        'Preserve fallback membership and reduced gross; P3 final targets capped at 45%, excess cash',
        f'{group}: verify exact published vintages; unavailable features abstain to P3',
        'Per-ETF expanding model; minimum 36 completed monthly labels; training-only preprocessing',
        'Ridge alpha 1' if kind=='linear' else 'Decision tree: depth 2, minimum 12 rows per leaf',
        'Increment above +25bp with positive forecast: factor 1.10; below -25bp: 0.90; otherwise 1',
        'Normalize inside positive parent positions; preserve exact gross and cash; cap each target at 45%',
        'Prior-close sizing → next open; whole adjusted units; sell before buy; 5bp primary costs',
        'Daily holdings, cash and NAV reconciled from simulated fills; cash earns zero; no order authority']
    height = 72*len(steps)+20
    extra = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1100 {height}">'
    for i,text in enumerate(steps):
        y=10+72*i
        extra+=f'<rect x="10" y="{y}" width="1080" height="56" rx="8" fill="#edf5f8"/><text x="25" y="{y+33}" font-family="sans-serif" font-size="13">{html.escape(text)}</text>'
    return extra+'</svg>'


def build_artifacts(root, output):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data,render_backtest_report_html
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json')
    if read_json(root/'report_receipt.json')['sha256']!=sha256(root/'report.json'):
        raise ValueError('Changed report')
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
            extra_benchmarks=[dict(id=k,name=LABELS[k]+' · USD',nav_series=results[k]['nav_series']) for k in ['F3','P3','CR','RP','URTH'] if k!=arm],
            market_prices={s:{d:float(v['close']) for d,v in rows.items()} for s,rows in quotes[arm].items()},
            market_fx_rates={r['date']:1. for r in economics[arm]['nav']})
        data.update(title=LABELS[arm]+' · financial conditions research',accountingCurrency='USD',database='Pinned published prices and economic vintages',
            allocationSource='Complete simulated ledger; evaluation starts in cash.',splitLabel='Previously inspected calendar boundary',
            sampleLabels={'in_sample':'2021–2022 retrospective','out_of_sample':'2023 onward retrospective'},
            decisionDiagrams=[dict(title='Complete parent and economic decision flow',svg=flow_svg(arm))],
            strategyDefinition=dict(id=arm,name=LABELS[arm],protocol_version=p['version'],features=p['feature_rule'],model=p['model_rule']),
            warnings=[*warnings,*p['limitations'],'Research comparison; monitoring membership is managed separately in the app.'])
        (detail/(arm+'.html')).write_text(render_backtest_report_html(data),encoding='utf-8')
    fig,axes=plt.subplots(2,1,figsize=(13,8),sharex=True)
    for arm in ['P3','CR','FR','FT','AR','AT']:
        nav=np.array([float(r['nav'])/1e6 for r in economics[arm]['nav']]);days=[date.fromisoformat(r['date']) for r in economics[arm]['nav']]
        axes[0].plot(days,nav,label=arm);axes[1].plot(days,nav/np.maximum.accumulate(np.maximum(nav,1))-1,label=arm)
    axes[0].legend(ncol=6);axes[0].set_ylabel('Value / initial USD capital');axes[1].set_ylabel('Drawdown')
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Financial conditions · retrospective 2021–6 Oct 2026 · 5bp costs · zero cash interest')
    fig.tight_layout();fig.savefig(output/'comparison.png',dpi=150);plt.close(fig)
    def table(headers,rows):
        return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'
    rows=[]
    for arm in ARMS:
        r=report['results'][job_name((arm,5,0,'evaluation'))]
        rows.append([f'<a href="reports/{arm}.html">{arm} · {html.escape(LABELS[arm])}</a>',f'{r["cagr"]:.2%}',f'{r["sharpe_zero_cash"]:.3f}',
            f'{r["calmar"]:.3f}',f'{r["max_drawdown"]:.2%}',f'{r["annual_turnover"]:.2f}',f'{r["mean_gross"]:.1%}'])
    main=table(['Arm / complete report','CAGR','Sharpe','Calmar','Max drawdown','Turnover/year','Mean invested'],rows)
    availability=table(['Group','Ready / evaluation decisions','Training rows first / last'],[[g,f'{r["ready"]} / {r["evaluation_decisions"]}',f'{r["training_rows_first"]} / {r["training_rows_last"]}'] for g,r in report['diagnostics']['availability'].items()])
    uncertainty=table(['Contrast','Annualized mean difference','Holm p, six-month blocks','Sharpe difference 95% interval'],[
        [a+' − '+b,f'{report["inference"]["means"]["6"][i]["mean_annual"]:.2%}',f'{report["inference"]["means"]["6"][i]["holm_p"]:.3f}',html.escape(str(report['inference'][a+'-'+b]['6']['sharpe']['ci95']))] for i,(a,b) in enumerate(COMPARISONS)])
    robustness=table(['Arm','20bp CAGR','20bp Sharpe','Delayed Sharpe','Delayed Calmar','Screen'],[
        [a,f'{report["results"][job_name((a,20,0,"evaluation"))]["cagr"]:.2%}',f'{report["results"][job_name((a,20,0,"evaluation"))]["sharpe_zero_cash"]:.3f}',f'{report["results"][job_name((a,5,1,"evaluation"))]["sharpe_zero_cash"]:.3f}',f'{report["results"][job_name((a,5,1,"evaluation"))]["calmar"]:.3f}',r['decision']] for a,r in report['screens'].items()])
    responses=''
    for g,latest in report['diagnostics']['latest_conditional_responses'].items():
        responses+=f'<h3>{html.escape(g)} · {latest["decision"]}</h3>'+table(['ETF',*latest['features']],[[s,*[f'{m["sensitivities"][f]["tree"]*10000:+.0f} / {m["sensitivities"][f]["linear"]*10000:+.0f}' for f in latest['features']]] for s,m in latest['models'].items()])
    allocation=table(['Arm','Decisions changed','Increased weight: ETF / months','Decreased weight: ETF / months'],[[a,str(r['changed_decisions']),', '.join(s+': '+str(n) for s,n in r['increased'].items() if n),', '.join(s+': '+str(n) for s,n in r['decreased'].items() if n)] for a,r in report['diagnostics']['allocation'].items()])
    verdict='; '.join(a+': '+r['decision'] for a,r in report['screens'].items())
    body=f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Financial conditions and ETF combinations</title>
<style>body{{font:15px/1.6 system-ui;color:#20354c;background:#f3f6fa;margin:0}}main{{max-width:1400px;margin:24px auto;padding:28px;background:white}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:10px;border-bottom:1px solid #dde4ed;text-align:right}}td:first-child{{text-align:left}}th{{background:#eef4f8}}.scroll{{overflow:auto}}img{{width:100%}}a{{color:#245ac3}}code{{overflow-wrap:anywhere}}.notice{{background:#fff7db;padding:16px}}</style><main>
<p>Finite ETF research · October 7, 2026 · No promotion</p><h1>Do financial conditions improve ETF predictions?</h1><p class="notice">{html.escape(verdict)}. Retrospective walk-forward evidence; the monitored CR recipe remains frozen.</p>
<p>Two fixed combinations: eight Treasury curve, credit-condition and lending-standard features alone; or added to the original thirteen leading/context features. Each ETF has its own ridge and depth-two tree. MR isolates added information by matching augmented training samples and current availability. All challengers apply directly to P3 and preserve its cash and eligible basket.</p>
<h2>Portfolio comparison</h2><p>January 2021–October 6, 2026; USD 1m; 5bp primary costs; zero cash interest. Links open complete NAV, holdings, targets, benchmark and decision-flow reports.</p>{main}<img src="comparison.png" alt="Portfolio value and drawdown of financial economic challengers">
<h2>Availability</h2>{availability}<h2>Allocation effects</h2>{allocation}<h2>Costs and delayed execution</h2>{robustness}<h2>Uncertainty</h2>{uncertainty}<p>20,000 joint resamples, with 3/6/12-month blocks. Holm correction covers all eight mean-return contrasts. Ratio intervals are marginal; none constitute independent discoveries.</p>
<h2>Asset-specific conditional responses</h2><p>Tree / ridge prediction differences in basis points when one feature moves from its training 25th to 75th percentile, holding the others fixed. Positive and negative associations are descriptive, not identified economic shocks. These are the last available model snapshots, not a claim that today's features are ready.</p>{responses}
<h2>Reproducibility and limitations</h2><p>Protocol: <code>{sha256(root/'protocol.json')}</code>. {p['budget']['replays']} replays; {p['budget']['native_checks']} native validations; all logical CPUs used.</p><ul>{''.join('<li>'+html.escape(x)+'</li>' for x in p['limitations'])}</ul></main></html>'''
    (output/'assessment.html').write_text(body,encoding='utf-8')
    write_json(output/'artifact_manifest.json',{str(f.relative_to(output)):sha256(f) for f in output.rglob('*') if f.is_file() and f.name!='artifact_manifest.json'})
    return str(output/'assessment.html')
