"""All-candidate selection attribution, paired uncertainty and complete reports."""
from pathlib import Path
import html
import re

import numpy as np

from systematic_trading.lean.contracts import sha256,write_json
from systematic_trading.research.momentum_replay import read_json,checked_files,verify_usd_bundle
from systematic_trading.research.selection_blend import ARMS,CONTROLS,VARIANTS,MAIN,MEAN,BLENDS,COMPARISONS,RATIO_COMPARISONS
from systematic_trading.research.expanded_economics import job_name
from systematic_trading.research.selection_blend_study import jobs

LABELS=dict(M1='Unchanged M1/14',CP='M1/14 + final 45% cap',CR='Context ridge sizing only',
    FR='Financial ridge sizing only',F3='Funded F3 reference',RP14='14-ETF inverse volatility',URTH='URTH buy and hold',
    NX='Original selection; remove XGBoost tilt',CEQNX='Equal context blend; remove XGBoost tilt',
    FEQNX='Equal financial blend; remove XGBoost tilt',CEQG='Equal context blend; match CP gross',FEQG='Equal financial blend; match CP gross')
for a,v in {**MAIN,**MEAN}.items():
    m,x,r=BLENDS[v['blend']]
    total=m+x+r
    mix='/'.join(f'{100*w/total:g}' for w in (m,x,r))
    LABELS[a]=f'{mix} M/X/R'+(' · '+v['group'] if v['group'] else '')+(' mean-only' if v.get('mean_only') else '')


def selection_diagnostics(root):
    from systematic_trading.research.full_pool_diagnostics import rank_ic,average
    selection=read_json(root/'selection.json')
    p=read_json(root/'protocol.json')
    bars=read_json(root/'bars.json')
    symbols=sorted(bars)
    opens={s:{r['trade_date']:float(r['open']) for r in rows} for s,rows in bars.items()}
    days=sorted(selection)
    evaluation=[d for d in days if d>=p['evaluation_start']]
    result={}
    for a in VARIANTS:
        rows=[]
        for day in evaluation:
            raw=selection[day][a]
            actual=set(raw['selected'])
            parent=set(raw['parent_selected'])
            previous=days[days.index(day)-1] if days.index(day) else None
            churn=len(actual^set(selection[previous][a]['selected']))/2 if previous else 0
            row=dict(day=day,changed=actual!=parent,added=sorted(actual-parent),removed=sorted(parent-actual),
                gross=float(raw['gross']),parent_gross=float(raw['parent_gross']),churn=churn,
                abstained=raw['abstained'],fallback=raw['fallback'],matched_gross=raw['gross_control'],
                selected=sorted(actual))
            i=days.index(day)
            if i<len(days)-1:
                end=days[i+1]
                realized={s:opens[s][end]/opens[s][day]-1 for s in symbols}
                table=raw['rank_table']
                row.update(label_end=end,return_new_minus_removed=(average([realized[s] for s in actual-parent])-
                    average([realized[s] for s in parent-actual])) if actual-parent and parent-actual else None,
                    return_selected_minus_parent=(average([realized[s] for s in actual])-
                    average([realized[s] for s in parent])) if actual and parent else None,
                    combined_ic=rank_ic([float(table[s]['combined']) for s in symbols],[realized[s] for s in symbols]) if table else None,
                    momentum_ic=rank_ic([float(table[s]['momentum']) for s in symbols],[realized[s] for s in symbols]) if table else None,
                    xgb_ic=rank_ic([float(table[s]['xgb']) for s in symbols],[realized[s] for s in symbols]) if table else None,
                    ridge_ic=rank_ic([float(table[s]['ridge']) for s in symbols],[realized[s] for s in symbols])
                        if table and all(table[s]['ridge'] is not None for s in symbols) else None)
            rows.append(row)
        completed=[r for r in rows if 'label_end' in r]
        switches=[r for r in completed if r['return_new_minus_removed'] is not None]
        result[a]=dict(rows=rows,decisions=len(rows),changed_decisions=sum(r['changed'] for r in rows),
            mean_replacements=float(np.mean([len(r['added']) for r in rows])),
            mean_churn=float(np.mean([r['churn'] for r in rows])),
            abstained=sum(r['abstained'] for r in rows),fallback=sum(r['fallback'] for r in rows),
            positive_switch_months=sum(r['return_new_minus_removed']>0 for r in switches),switch_months=len(switches),
            mean_new_minus_removed=average([r['return_new_minus_removed'] for r in switches]),
            mean_selected_minus_parent=average([r['return_selected_minus_parent'] for r in completed]),
            combined_ic=average([r['combined_ic'] for r in completed]),
            xgb_ic=average([r['xgb_ic'] for r in completed]),
            ridge_ic=average([r['ridge_ic'] for r in completed]),
            mean_target_gross_delta=float(np.mean([r['gross']-r['parent_gross'] for r in rows])),
            infeasible_gross_matches=sum(bool(r['matched_gross']) and not r['matched_gross']['matched'] for r in rows),
            asset_months={s:sum(s in r['selected'] for r in rows) for s in symbols},
            added_months={s:sum(s in r['added'] for r in rows) for s in symbols},
            removed_months={s:sum(s in r['removed'] for r in rows) for s in symbols})
    return result


def summarize(root):
    from systematic_trading.research.momentum_analysis import statistics
    from systematic_trading.research.candidate_pool_analysis import return_metrics
    checked_files(root,'decision_manifest.json')
    receipt=read_json(root/'data_receipt.json')
    prior=read_json(Path(receipt['economic'])/'statistics.json')
    result,parity,context={},{},{}
    for job in jobs():
        name=job_name(job)
        path=root/'python'/(name+'.json')
        bundle=root/'bundles'/name
        verify_usd_bundle(bundle)
        if read_json(path.with_suffix('.receipt.json'))!=dict(sha256=sha256(path),manifest_sha256=sha256(bundle/'manifest.json')):
            raise ValueError('Replay changed '+name)
        economic=read_json(path)
        s=statistics(economic,read_json(bundle/'quotes.json'))
        s['calmar']=s['cagr']/abs(s['max_drawdown'])
        s['mean_equity_weight']+=sum(s['mean_asset_weights'].get(x,0) for x in ('XLE','XLB'))
        s.pop('asset_daily_contribution')
        result[name]=s
        arm,cost,delay,window=job
        if arm in CONTROLS and name in prior:
            # URTH delayed evaluation intentionally shifts first investment by one day here.
            if arm!='URTH' or delay==0:
                for k in ('cagr','volatility','sharpe_zero_cash','terminal_nav','max_drawdown'):
                    if abs(s[k]-prior[name][k])>1e-12:
                        raise ValueError('Frozen control failed '+name+' '+k)
                parity[name]=True
        if cost==5 and delay==0:
            context[name]={}
            for label,predicate in [('2021_2023',lambda d:'2021'<=d<'2024'),('2024_end',lambda d:d>='2024'),
                                    ('2016_2020',lambda d:d<'2021')]:
                pairs=[(d,r) for d,r in zip(s['dates'],s['daily_returns'],strict=True) if predicate(d)]
                if pairs:
                    context[name][label]=return_metrics([d for d,_ in pairs],[r for _,r in pairs])
    write_json(root/'statistics.json',result)
    write_json(root/'statistics_receipt.json',dict(sha256=sha256(root/'statistics.json')))
    write_json(root/'selection_diagnostics.json',selection_diagnostics(root))
    write_json(root/'context.json',context)
    write_json(root/'control_parity.json',parity)


def inference_job(job):
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    from systematic_trading.research.construction_analysis import bootstrap_ratios
    root,kind,block,index=job
    root=Path(root)
    if sha256(root/'statistics.json')!=read_json(root/'statistics_receipt.json')['sha256']:
        raise ValueError('Inference input changed')
    result=read_json(root/'statistics.json')
    p=read_json(root/'protocol.json')
    def r(a):
        return result[job_name((a,5,0,'evaluation'))]
    if kind=='means':
        months=sorted(r('CP')['monthly'])
        matrix=np.array([[r(a)['monthly'][m]-r(b)['monthly'][m] for a,b in COMPARISONS] for m in months])
        return kind,str(block),paired_bootstrap(matrix,block=block,replications=p['bootstrap_replications'],seed=p['seed'])
    a,b=RATIO_COMPARISONS[index]
    return a+'-'+b,str(block),bootstrap_ratios(r(a)['dates'],r(a)['daily_returns'],r(b)['daily_returns'],
        block=block,replications=p['bootstrap_replications'],seed=p['seed'])


def finalize(root):
    p=read_json(root/'protocol.json')
    results=read_json(root/'statistics.json')
    uncertainty={}
    for key,block,value in read_json(root/'inference.json'):
        uncertainty.setdefault(key,{})[block]=value
    def r(a,c=5,d=0):
        return results[job_name((a,c,d,'evaluation'))]
    screens={}
    for a in MAIN:
        v,b=r(a),r('CP')
        s=p['screen']
        checks=dict(sharpe_gain=v['sharpe_zero_cash']-b['sharpe_zero_cash']>=s['min_sharpe_gain'],
            calmar_gain=v['calmar']-b['calmar']>=s['min_calmar_gain'],
            cagr_budget=all(v['cagr']>=r(x)['cagr']-s['max_cagr_sacrifice'] for x in ('CP','M1')),
            drawdown_budget=all(v['max_drawdown']>=r(x)['max_drawdown']-s['max_drawdown_worsening'] for x in ('CP','M1')),
            costs_and_delay=all(r(a,c,d)['sharpe_zero_cash']>r('CP',c,d)['sharpe_zero_cash']
                and r(a,c,d)['calmar']>r('CP',c,d)['calmar']
                and r(a,c,d)['cagr']>=r('M1',c,d)['cagr']-s['max_cagr_sacrifice'] for c,d in ((10,0),(20,0),(5,1))))
        if MAIN[a]['group']:
            checks['above_mean_only']=all(v[k]>r(a+'M')[k] for k in ('sharpe_zero_cash','calmar'))
        ix=COMPARISONS.index((a,'CP'))
        robust=all(uncertainty['means'][str(b)][ix]['holm_p']<.05 and uncertainty['means'][str(b)][ix]['ci95'][0]>0 for b in p['bootstrap_blocks'])
        screens[a]=dict(checks=checks,passes_recipe_screen=all(checks.values()),family_return_evidence=robust,
                        robust_superiority=all(checks.values()) and robust)
    report=dict(protocol=p,results=results,uncertainty=uncertainty,screens=screens,
        selection=read_json(root/'selection_diagnostics.json'),context=read_json(root/'context.json'),
        control_parity=read_json(root/'control_parity.json'),promotion_eligible=False)
    write_json(root/'report.json',report)
    write_json(root/'report_receipt.json',dict(sha256=sha256(root/'report.json'),statistics_sha256=sha256(root/'statistics.json'),
        input_sha256=sha256(root/'input_manifest.json'),decisions_sha256=sha256(root/'decision_manifest.json')))
    return dict(replays=len(results),controls=len(report['control_parity']),
        retained=[a for a,s in screens.items() if s['passes_recipe_screen']],robust=[a for a,s in screens.items() if s['robust_superiority']])


def flow(arm):
    if arm in CONTROLS:
        from systematic_trading.research.expanded_economic_analysis import flow as old_flow
        return old_flow(arm)
    recipe=VARIANTS[arm]
    steps=['Verify pinned audited adjusted prices, audited raw activity and original model/feature hashes',
        'Prior-close information only; monthly frozen causal XGBoost and expanding economic ridge forecasts',
        '63-session inverse-volatility budgets, incoming45 cap and2% cash floor',
        'Full14 candidates; rank M1 momentum/activity, XGBoost and ridge forecasts with midranks',
        LABELS[arm]+'; unavailable required ridge => original M1 selection',
        'Positive126 momentum eligibility; combined-score top6, minimum4; alphabetic ties',
        'Fewer than4 eligible => eligible IEF/TLT/GLD incoming budgets only, residual cash protected',
        'XGBoost weight tilt removed' if recipe.get('remove_xgb') else 'Existing XGBoost weight tilt retained to isolate changed selection',
        'Existing relative momentum → adaptive trend → audited raw activity lag20 → USD ridge',
        'Final45% cap; excess remains cash; no economic sizing overlay']
    if recipe.get('match_gross'):
        steps+=['Match CP target gross proportionally within existing positive targets and45cap; disclose insufficient capacity']
    steps+=['Next-open whole adjusted units, sale-before-buy;5bp primary costs, zero-interest USD cash',
            'Daily NAV, target/held weights, attribution and matched benchmarks; no execution authority']
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {len(steps)*57+10}">'
    for i,line in enumerate(steps):
        svg+=f'<rect x="5" y="{i*57+5}" width="1190" height="48" rx="8" fill="#e8f0f2"/><text x="16" y="{i*57+34}" font-family="sans-serif" font-size="12">{i+1}. {html.escape(line)}</text>'
    return svg+'</svg>'


def artifacts(root,output):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data,render_backtest_report_html
    report=read_json(root/'report.json')
    if sha256(root/'report.json')!=read_json(root/'report_receipt.json')['sha256']:
        raise ValueError('Report changed')
    native={}
    for a in ARMS:
        path=root/'native'/job_name((a,5,0,'full'))
        checked_files(path,'artifact_manifest.json')
        if read_json(path/'run.json')['status']!='succeeded' or not read_json(path/'parity.json')['passed']:
            raise ValueError('Missing native parity '+a)
        native[a]=dict(run=sha256(path/'run.json'),parity=sha256(path/'parity.json'))
    p=report['protocol']
    output.mkdir(parents=True,exist_ok=True)
    (output/'reports').mkdir(exist_ok=True)
    economics,quotes,results={},{},{}
    for a in ARMS:
        name=job_name((a,5,0,'full'))
        economics[a]=read_json(root/'python'/(name+'.json'))
        quotes[a]=read_json(root/'bundles'/name/'quotes.json')
        results[a]=report_result(economics[a],quotes[a],p['initial_cash_usd'],'2015-12-31')
    for a in ARMS:
        data,warnings=build_backtest_report_data(result=results[a],result_path=root/'python'/(job_name((a,5,0,'full'))+'.json'),
            split_date=p['evaluation_start'],benchmark_name=LABELS['F3'],benchmark_nav_series=results['F3']['nav_series'],
            extra_benchmarks=[dict(id=b,name=LABELS[b],nav_series=results[b]['nav_series']) for b in ('M1','CP','CR','FR','RP14','URTH') if b!=a],
            market_prices={s:{d:float(q['close']) for d,q in rows.items()} for s,rows in quotes[a].items()},
            market_fx_rates={v['date']:1. for v in economics[a]['nav']})
        data.update(title=LABELS[a]+' · selection blend',accountingCurrency='USD',database='Published audited histories and pinned causal models',
            allocationSource='Simulated fills',splitLabel='Previously inspected chronological boundary',
            sampleLabels={'in_sample':'2016–2020 retrospective','out_of_sample':'2021 onward retrospective'},
            decisionDiagrams=[dict(title='Complete decision flow',svg=flow(a))],strategyDefinition=dict(id=a,protocol=p),
            warnings=[*warnings,*p['limitations'],'Primary evaluation starts with fresh cash2021. This full report carries the2016 portfolio and includes the prior-close capital anchor; calendar CAGR differs slightly.'])
        last=max(economics[a]['decisions'])
        weights={t['symbol']:float(t['target_weight']) for t in economics[a]['decisions'][last]['targets']}
        s=report['results'][job_name((a,5,0,'full'))]
        table=f'<section style="margin:24px"><h2>Targets and held weights</h2><p>Scheduled {last}; held at {p["end"]}. Historical research only.</p><table><tr><th>Asset</th><th>Target</th><th>Held</th></tr>'
        for symbol in sorted(quotes[a]):
            table+=f'<tr><td>{symbol}</td><td>{weights.get(symbol,0):.2%}</td><td>{s["last_held_weights"].get(symbol,0):.2%}</td></tr>'
        table+=f'<tr><td>Cash</td><td>{1-sum(weights.values()):.2%}</td><td>{1-sum(s["last_held_weights"].values()):.2%}</td></tr></table></section>'
        rendered=render_backtest_report_html(data).replace('</body>',table+'</body>')
        rendered=re.sub(r'(href=["\'])(/[^"\']*)',r'\1http://127.0.0.1:8000\2',rendered)
        (output/'reports'/(a+'.html')).write_text(rendered,encoding='utf8')
    from systematic_trading.research.selection_blend_presentation import landing
    landing(root,output,report)
    write_json(root/'presentation_receipt.json',dict(report_sha256=sha256(root/'report.json'),native=native,
        files={f.relative_to(output).as_posix():sha256(f) for f in output.rglob('*') if f.is_file()},
        sources={str(f):sha256(f) for f in [Path(__file__),Path(__file__).with_name('selection_blend_presentation.py')]}))
    return dict(output=str(output),reports=len(ARMS),native=len(native))
