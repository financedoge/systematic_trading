"""Paired inference and complete static reports for the finite research batch."""
from collections import defaultdict
from datetime import date
import html
import math
from pathlib import Path

import numpy as np

from systematic_trading.lean.contracts import write_json, sha256
from systematic_trading.research.momentum_replay import read_json, checked_files
from systematic_trading.research.construction_study import ARMS, COMPARISONS, LABELS, RANK_ARMS, job_name


def ratio_metrics(returns, mask):
    """Batched daily ratios; empty/all-cash ratios remain undefined."""
    n=mask.sum(axis=1)
    mean=np.sum(np.where(mask,returns,0),axis=1)/n
    variance=np.sum(np.where(mask,(returns-mean[:,None,:])**2,0),axis=1)/(n-1)
    vol=np.sqrt(variance)
    sharpe=np.divide(mean*np.sqrt(252),vol,out=np.full_like(mean,np.nan),where=vol>1e-15)
    wealth=np.cumprod(np.where(mask,1+returns,1),axis=1)
    peak=np.maximum.accumulate(np.maximum(wealth,1),axis=1)
    dd=np.min(wealth/peak-1,axis=1)
    cagr=wealth[:,-1,:]**(252/n)-1
    calmar=np.divide(cagr,np.abs(dd),out=np.full_like(cagr,np.nan),where=np.abs(dd)>1e-15)
    return np.stack([sharpe,calmar],axis=-1)


def bootstrap_ratios(dates, candidate, control, *, block=6, replications=20000, seed=2026100702):
    """Joint circular calendar-month resampling retains each month's daily path.

    Calendar gaps stay empty; no zero-return observations enter moments.
    CAGR here uses 252 sessions/year, explicitly distinct from report calendar CAGR.
    """
    months=sorted({d[:7] for d in dates});group=defaultdict(list)
    for i,d in enumerate(dates):
        group[d[:7]].append(i)
    width=max(map(len,group.values()))
    values=np.zeros((len(months),width,2));valid=np.zeros_like(values,dtype=bool)
    paired=np.column_stack([candidate,control])
    if len(paired)!=len(dates) or not np.isfinite(paired).all() or np.any(paired<=-1):
        raise ValueError('Complete aligned unlevered paired returns are required')
    for j,month in enumerate(months):
        indices=group[month];values[j,:len(indices),:]=paired[indices];valid[j,:len(indices),:]=True
    rng=np.random.default_rng(seed);draws=[]
    for offset in range(0,replications,100):
        size=min(100,replications-offset)
        starts=rng.integers(0,len(months),size=(size,math.ceil(len(months)/block)))
        idx=((starts[:,:,None]+np.arange(block))%len(months)).reshape(size,-1)[:,:len(months)]
        m=ratio_metrics(values[idx].reshape(size,-1,2),valid[idx].reshape(size,-1,2))
        draws.append(m[:,0,:]-m[:,1,:])
    draws=np.concatenate(draws);answer={}
    observed=ratio_metrics(paired[None,:,:],np.ones_like(paired[None,:,:],dtype=bool))[0]
    for i,name in enumerate(['sharpe','calmar_252']):
        finite=draws[np.isfinite(draws[:,i]),i]
        point=observed[0,i]-observed[1,i]
        answer[name]=dict(difference=float(point) if np.isfinite(point) else None,
            ci95=np.quantile(finite,[.025,.975]).tolist() if len(finite) else None,
            valid_draws=len(finite),replications=replications)
    return answer


def inference_job(job):
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    root,kind,block,index=job;root=Path(root);p=read_json(root/'protocol.json')
    if read_json(root/'statistics_receipt.json')['sha256']!=sha256(root/'statistics.json'):
        raise ValueError('Changed summary input')
    results=read_json(root/'statistics.json')
    def primary(key):return results[job_name((key,5,0,'evaluation'))]
    if kind=='means':
        months=sorted(primary('F0')['monthly'])
        matrix=np.array([[primary(a)['monthly'][m]-primary(b)['monthly'][m] for a,b in COMPARISONS] for m in months])
        return kind,str(block),paired_bootstrap(matrix,block=block,replications=p['bootstrap_replications'],seed=p['seed'])
    a,b=COMPARISONS[index];left,right=primary(a),primary(b)
    if left['dates']!=right['dates']:
        raise ValueError('Paired daily calendars differ')
    value=bootstrap_ratios(left['dates'],left['daily_returns'],right['daily_returns'],block=block,
        replications=p['bootstrap_replications'],seed=p['seed'])
    return f'{a}-{b}',str(block),value


def ranks(values):
    order=np.argsort(values,kind='stable');result=np.empty(len(values));i=0
    while i<len(values):
        j=i+1
        while j<len(values) and values[order[j]]==values[order[i]]:j+=1
        result[order[i:j]]=(i+j-1)/2;i=j
    return result


def ranking_diagnostics(root):
    p=read_json(root/'protocol.json');forecasts=read_json(root/'forecasts.json');pv=read_json(root/'price_volume_scores.json')
    bars=read_json(root/'parent/bars.json');close={s:{r['trade_date']:float(r['close']) for r in rows} for s,rows in bars.items()}
    f3=read_json(root/'decisions/F3.json');days=sorted(f3);records=[]
    for day,next_day in zip(days,days[1:]):
        if day<p['evaluation_start']:continue
        known,end=f3[day]['known_through'],f3[next_day]['known_through']
        eligible=f3[day]['diagnostic']['eligible']
        for scope,symbols in [('all',sorted(close)),('eligible',eligible)]:
            if len(symbols)<4:continue
            actual=[close[s][end]/close[s][known]-1 for s in symbols]
            for label,score in [('xgboost',forecasts),('price_volume',pv)]:
                x,y=ranks([float(score[day][s]) for s in symbols]),ranks(actual)
                ic=float(np.corrcoef(x,y)[0,1]) if np.std(x)>0 and np.std(y)>0 else None
                records.append(dict(day=day,label_end=end,scope=scope,model=label,n=len(symbols),rank_ic=ic))
    summaries={}
    for scope in ['all','eligible']:
        for model in ['xgboost','price_volume']:
            values=[r['rank_ic'] for r in records if r['scope']==scope and r['model']==model and r['rank_ic'] is not None]
            summaries[scope+'/'+model]=dict(months=len(values),mean=float(np.mean(values)),median=float(np.median(values)),
                positive_fraction=float(np.mean(np.array(values)>0)))
    selection={}
    evaluation=[d for d in days if d>=p['evaluation_start']]
    for n in [6,8,10]:
        x=read_json(root/f'decisions/X{n}.json');other=read_json(root/f'decisions/N{n}.json')
        selection[str(n)]=dict(monthly_decisions=len(evaluation),
            months_more_eligible_than_n=sum(len(f3[d]['diagnostic']['eligible'])>n for d in evaluation),
            different_selected_sets=sum(set(x[d]['diagnostic']['selected'])!=set(other[d]['diagnostic']['selected']) for d in evaluation),
            mean_selected=float(np.mean([len(x[d]['diagnostic']['selected']) for d in evaluation])))
    return dict(summary=summaries,selection=selection,records=records,
        interpretation='Evaluation of subsequent complete-month returns only. IC is descriptive, not independent evidence or a tuned selection rule.')


def finalize(root, inference):
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json')
    p=read_json(root/'protocol.json');results=read_json(root/'statistics.json');group={}
    for kind,block,value in inference:group.setdefault(kind,{})[block]=value
    report=dict(protocol=p,calibration=read_json(root/'calibration.json'),
        baseline_parity=read_json(root/'parent/baseline_parity.json'),results=results,inference=group,
        ranking_diagnostics=ranking_diagnostics(root),promotion_eligible=False)
    write_json(root/'report.json',report)
    write_json(root/'report_receipt.json',dict(sha256=sha256(root/'report.json'),input_manifest_sha256=sha256(root/'input_manifest.json'),
        decision_manifest_sha256=sha256(root/'decision_manifest.json'),statistics_sha256=sha256(root/'statistics.json')))
    return {a:{k:results[job_name((a,5,0,'evaluation'))][k] for k in ['cagr','sharpe_zero_cash','calmar','max_drawdown','mean_gross','maximum_weight']} for a in ARMS}


def flow_svg(arm,p):
    if arm in RANK_ARMS:
        n=arm[1:];mode='XGBoost predicted next-month relative return' if arm.startswith('X') else 'Price/volume composite'
        rank=f'Rank eligible ETFs by {mode}; select up to {n}; alphabetical ties'
        model='Apply the existing XGBoost weight tilt' if arm.startswith('P') else 'No XGBoost weight tilt after selection'
    else:
        rank='Existing price/volume rank; select up to 6 eligible ETFs';model='Existing XGBoost weight tilt'
    fallback='Keep original incoming basket' if arm in ['F0','C0','E0','E1'] else 'Only qualifying IEF/TLT/GLD incoming weights; remaining budget stays cash'
    steps=['Verify pinned adjusted prices, model/source hashes and the completed prior close',
        'Monthly signal; 63-session inverse volatility, 45% base cap, 2% minimum cash',
        'Eligibility: positive 252-session momentum; unavailable data stops calculation',rank,
        'Fewer than four qualify: '+fallback,
        'Normal selection: renormalize selected incoming weights to the original gross budget',model,
        'Relative momentum → adaptive trend → activity lag-20 → USD ridge',
        'Preserve fallback membership and declining invested budget through later layers']
    if arm=='E0':steps+=['Scale all final F0 weights by the 2016–2020 calibrated constant; residual cash']
    if arm=='E1':steps+=['Compute F3 from the same prior-close inputs; scale final F0 weights to that gross budget']
    if arm in ['C0','C3']:steps+=['Clip each final target to 45%; do not redistribute the removed weight']
    steps+=['Prior-close sizing → next-session open fills, whole adjusted units, sells before buys',
            'USD cash earns zero; 5bp primary costs; daily held weights and NAV; no broker orders']
    if arm in ['RP','URTH']:
        steps=['Verify the same pinned adjusted-price batch and exact evaluation calendar',
            'Monthly inverse-volatility weights, base cap 45%, cash reserve 2%' if arm=='RP' else 'Buy and hold URTH from the first evaluation session',
            'Prior-close sizing, next-open fills, whole adjusted units, USD cash and 5bp fees',
            'Daily NAV and holdings; research comparison only']
    height=72*len(steps)+20
    svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1080 {height}" role="img" aria-label="Full research decision flow">'
    for i,text in enumerate(steps):
        y=10+i*72
        svg+=f'<rect x="12" y="{y}" width="1056" height="56" rx="9" fill="#edf5f8" stroke="#a5bdcb"/><text x="29" y="{y+33}" font-family="sans-serif" font-size="14">{i+1}. {html.escape(text)}</text>'
    return svg+'</svg>'


def build_artifacts(root,output):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data,render_backtest_report_html
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    output.mkdir(parents=True,exist_ok=True)
    report=read_json(root/'report.json');p=report['protocol'];all_results={};economics={};quotes={}
    for arm in ARMS:
        name=job_name((arm,5,0,'evaluation'))
        economic=read_json(root/'python'/(name+'.json'));q=read_json(root/'bundles'/name/'quotes.json')
        all_results[arm]=report_result(economic,q,'1000000','2020-12-31');economics[arm]=economic;quotes[arm]=q
    details=output/'reports';details.mkdir(exist_ok=True)
    for arm in ARMS:
        data,warnings=build_backtest_report_data(result=all_results[arm],result_path=root/'python'/f'{arm}-evaluation-cost5-delay0.json',
            split_date='2023-01-01',benchmark_name='Current SOTA · matched USD',benchmark_nav_series=all_results['F0']['nav_series'],
            extra_benchmarks=[dict(id=k,name=LABELS[k]+' · USD',nav_series=all_results[k]['nav_series']) for k in ['F3','RP','URTH','E0'] if k!=arm],
            market_prices={s:{d:float(v['close']) for d,v in rows.items()} for s,rows in quotes[arm].items()},
            market_fx_rates={r['date']:1. for r in economics[arm]['nav']})
        data.update(title=LABELS[arm]+' · finite research',accountingCurrency='USD',database='Pinned published audited histories',
            allocationSource='Daily holdings reconstructed from the simulated fill ledger; evaluation starts in cash.',
            splitLabel='Previously inspected calendar boundary',sampleLabels={'in_sample':'2021–2022 retrospective','out_of_sample':'2023 onward retrospective'},
            decisionDiagrams=[dict(title='Complete research decision flow',svg=flow_svg(arm,p))],
            strategyDefinition=dict(id=arm,label=LABELS[arm],protocol_version=p['version'],ranking=p['ranking'],calibration=report['calibration'] if arm=='E0' else None),
            warnings=[*warnings,*p['limitations'],'Finite research report: this recipe has no monitoring or execution authority.'])
        (details/(arm+'.html')).write_text(render_backtest_report_html(data),encoding='utf8')
    fig,axes=plt.subplots(2,2,figsize=(15,9),sharex='col')
    panels=[(['F3','N6','X6','X8','X10','URTH'],'Forecast ranking versus the current integration'),
            (['F0','F3','E0','E1','C3'],'Fallback exposure and final target cap')]
    for col,(arms,title) in enumerate(panels):
        for arm in arms:
            nav=np.array([float(r['nav'])/1e6 for r in economics[arm]['nav']]);days=[date.fromisoformat(r['date']) for r in economics[arm]['nav']]
            peak=np.maximum.accumulate(np.maximum(nav,1));axes[0,col].plot(days,nav,label=arm,linewidth=1.5)
            axes[1,col].plot(days,nav/peak-1,label=arm,linewidth=1.2)
        axes[0,col].set_title(title);axes[0,col].set_ylabel('Value / initial USD capital');axes[0,col].legend(ncol=3)
        axes[1,col].set_ylabel('Drawdown');axes[1,col].yaxis.set_major_formatter(PercentFormatter(1))
        for ax in axes[:,col]:ax.grid(alpha=.2)
    fig.suptitle('2021–6 Oct 2026 · unchanged model fits · 5bp costs · zero cash interest\nRetrospective evaluation; no candidate promotion',fontsize=13)
    fig.tight_layout();fig.savefig(output/'comparison.png',dpi=150);plt.close(fig)
    rows=[]
    for arm in ARMS:
        v=report['results'][job_name((arm,5,0,'evaluation'))]
        rows.append(f'<tr><td><a href="reports/{arm}.html">{arm}</a></td><td>{html.escape(LABELS[arm])}</td><td>{v["cagr"]:.2%}</td><td>{v["sharpe_zero_cash"]:.3f}</td><td>{v["calmar"]:.3f}</td><td>{v["max_drawdown"]:.2%}</td><td>{v["mean_held_count"]:.2f}</td><td>{v["annual_turnover"]:.2f}</td></tr>')
    body='''<!doctype html><html><head><meta charset="utf-8"><title>XGBoost ranking and portfolio construction research</title><style>
    body{font:16px system-ui;background:#f5f7fa;color:#1c3045;margin:0;padding:30px;max-width:1450px}h1{font-size:28px}table{border-collapse:collapse;background:white;width:100%}th,td{padding:10px;border-bottom:1px solid #dae1e8;text-align:right}td:nth-child(2){text-align:left}img{width:100%}a{color:#17549d}li{margin:.5em 0}</style></head><body>
    <h1>XGBoost ranking and portfolio construction</h1><p>Finite research · 2021–6 October 2026 · USD · 5bp primary costs · zero cash interest. The evaluation period was previously inspected.</p>
    <p>P: price/volume ranking with XGBoost tilt (P6 = F3). N: price/volume ranking without that tilt. X: XGBoost forecast ranking without that tilt. Top N is a maximum; the same momentum eligibility and defensive fallback apply.</p>
    <table><thead><tr><th>Arm</th><th>Recipe — click code for full report</th><th>CAGR</th><th>Sharpe</th><th>Calmar</th><th>Max DD</th><th>Mean holdings</th><th>Turnover/yr</th></tr></thead><tbody>'''+''.join(rows)+'''</tbody></table><img src="comparison.png" alt="Portfolio values and drawdowns"><h2>Fixed research rules</h2><ul>'''+''.join('<li>'+html.escape(s)+'</li>' for s in p['limitations'])+'</ul></body></html>'
    (output/'index.html').write_text(body,encoding='utf8')
    write_json(output/'receipt.json',dict(study=str(root.resolve()),protocol_sha256=sha256(root/'protocol.json'),report_sha256=sha256(root/'report.json'),
        files={f.relative_to(output).as_posix():sha256(f) for f in output.rglob('*') if f.is_file() and f.name!='receipt.json'}))
    return str((output/'index.html').resolve())
