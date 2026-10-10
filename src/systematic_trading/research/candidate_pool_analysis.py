"""Matched accounting, selection attribution and full SOTA-format study reports."""
from collections import Counter
from datetime import date
from pathlib import Path
import html
import math

import numpy as np

from systematic_trading.lean.contracts import write_json,sha256
from systematic_trading.research.momentum_replay import read_json,checked_files,verify_usd_bundle
from systematic_trading.research.candidate_pool_study import ARMS,COMPARISONS,jobs,job_name
from systematic_trading.research.candidate_pool import POLICIES

LABELS={f'{m}_{n}':f'{m} · {n} candidates' for m in POLICIES for n in (12,14)} | dict(F3='Frozen current F3',RP12='Inverse volatility · 12',RP14='Inverse volatility · 14',URTH='URTH buy and hold')


def return_metrics(dates, returns):
    values=np.array(returns);nav=np.cumprod(1+values);peak=np.maximum.accumulate(np.maximum(nav,1))
    years=(date.fromisoformat(dates[-1])-date.fromisoformat(dates[0])).days/365.25
    dd=float(np.min(nav/peak-1));cagr=float(nav[-1]**(1/years)-1)
    return dict(cagr=cagr,sharpe_zero_cash=float(np.mean(values)/np.std(values,ddof=1)*math.sqrt(252)),max_drawdown=dd,calmar=cagr/abs(dd))


def summarize(root):
    from systematic_trading.research.momentum_analysis import statistics
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json');checked_files(root,'model_manifest.json')
    results={};parity={};selection=read_json(root/'selection.json');diagnostics={}
    for job in jobs():
        name=job_name(job);path=root/'python'/(name+'.json');bundle=root/'bundles'/name
        verify_usd_bundle(bundle)
        if read_json(path.with_suffix('.receipt.json'))!=dict(sha256=sha256(path),manifest_sha256=sha256(bundle/'manifest.json')):
            raise ValueError('Replay receipt mismatch')
        economic=read_json(path);stats=statistics(economic,read_json(bundle/'quotes.json'))
        stats['calmar']=stats['cagr']/abs(stats['max_drawdown'])
        # Shared historical helper's equity subset predates these sector ETFs.
        stats['mean_equity_weight']+=sum(stats['mean_asset_weights'].get(s,0) for s in ('XLE','XLB'))
        if job==('F3',5,0,'full'):
            prior=read_json(root/'baseline_economic.json')
            if any(prior[k]!=economic[k] for k in ('nav','fills','decisions','final_positions')):
                raise ValueError('Frozen legacy F3 failed exact economic reproduction')
            parity[name]=True
        results[name]=stats
        arm,cost,delay,window=job
        if cost==5 and delay==0 and arm.startswith('M'):
            rows={d:v[arm] for d,v in selection.items() if d>=stats['dates'][0]}
            by_asset={};held_counts=Counter();positions=Counter();fills={}
            for f in economic['fills']:fills.setdefault(f['date'],[]).append(f)
            for day in stats['dates']:
                for f in fills.get(day,[]):positions[f['symbol']]+=f['quantity']
                held_counts.update([s for s,q in positions.items() if q>0])
            for s in stats['mean_asset_weights']:
                selected=sum(s in v['selected'] for v in rows.values())
                by_asset[s]=dict(eligible=sum(s in v['eligible'] for v in rows.values()),selected=selected,
                    final_selected=sum(s in v['final_selected'] for v in rows.values()),held_sessions=held_counts[s],
                    selected_fraction=selected/len(rows),mean_target_weight=float(np.mean([float(v['final_weights'][s]) for v in rows.values()])),
                    mean_held_weight=stats['mean_asset_weights'][s],pnl_usd=stats['asset_pnl_usd'].get(s,0))
            displacement=Counter()
            if arm.endswith('_14'):
                original=arm.replace('_14','_12')
                for day,v in rows.items():displacement.update(set(selection[day][original]['selected'])-set(v['selected']))
            diagnostics[arm+'-'+window]=dict(decisions=len(rows),sessions=len(stats['dates']),
                fallback_months=sum(v['fallback'] for v in rows.values()),assets=by_asset,displaced_original_selections=dict(displacement))
    # Descriptive calibration and leave-year-out sensitivity; no new candidate search.
    context={}
    for arm in ARMS:
        s=results[job_name((arm,5,0,'full'))];pairs=list(zip(s['dates'],s['daily_returns']))
        context[arm]={}
        for label,predicate in [('2016_2020',lambda d:d<'2021'),('exclude_2020',lambda d:not d.startswith('2020')),('exclude_2022',lambda d:not d.startswith('2022'))]:
            chosen=[(d,v) for d,v in pairs if predicate(d)]
            v=return_metrics([d for d,_ in chosen],[v for _,v in chosen])
            if label.startswith('exclude'):
                v.pop('cagr');v.pop('calmar') # elapsed-calendar CAGR after omitted years would mislead
            context[arm][label]=v
    write_json(root/'statistics.json',results);write_json(root/'statistics_receipt.json',dict(sha256=sha256(root/'statistics.json')))
    write_json(root/'selection_summary.json',diagnostics);write_json(root/'context_metrics.json',context);write_json(root/'control_parity.json',parity)


def inference_job(job):
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    from systematic_trading.research.construction_analysis import bootstrap_ratios
    root,kind,block,index=job;root=Path(root);p=read_json(root/'protocol.json')
    if read_json(root/'statistics_receipt.json')['sha256']!=sha256(root/'statistics.json'):raise ValueError('Changed statistics')
    results=read_json(root/'statistics.json')
    def r(arm):return results[job_name((arm,5,0,'evaluation'))]
    if kind=='means':
        months=sorted(r('M0_12')['monthly'])
        matrix=np.array([[r(a)['monthly'][m]-r(b)['monthly'][m] for a,b in COMPARISONS] for m in months])
        return 'means',str(block),paired_bootstrap(matrix,block=block,replications=p['bootstrap_replications'],seed=p['seed'])
    a,b=COMPARISONS[index];left,right=r(a),r(b)
    if left['dates']!=right['dates']:raise ValueError('Unmatched calendars')
    return a+'-'+b,str(block),bootstrap_ratios(left['dates'],left['daily_returns'],right['daily_returns'],block=block,replications=p['bootstrap_replications'],seed=p['seed'])


def finalize(root,values):
    p=read_json(root/'protocol.json');r=read_json(root/'statistics.json');uncertainty={};checks={};native={}
    for key,block,value in values:uncertainty.setdefault(key,{})[block]=value
    for arm in ARMS:
        name=job_name((arm,5,0,'full'));path=root/'native'/name
        checked_files(path,'artifact_manifest.json');receipt=read_json(path/'run.json')
        if receipt['status']!='succeeded' or not read_json(path/'parity.json')['passed']:raise ValueError('Native validation missing '+arm)
        native[arm]=dict(run_sha256=sha256(path/'run.json'),parity_sha256=sha256(path/'parity.json'))
    for i,(a,b) in enumerate(COMPARISONS):
        left,right=(r[job_name((s,5,0,'evaluation'))] for s in (a,b));screen=p['retention_screen']
        row=dict(sharpe=left['sharpe_zero_cash']-right['sharpe_zero_cash']>=screen['min_sharpe_gain'],
            calmar=left['calmar']-right['calmar']>=screen['min_calmar_gain'],
            cagr=left['cagr']>=right['cagr']-screen['max_cagr_sacrifice'],
            drawdown=left['max_drawdown']>=right['max_drawdown']-screen['max_drawdown_worsening'])
        row['cost_delay']=all(r[job_name((a,c,d,'evaluation'))]['sharpe_zero_cash']>r[job_name((b,c,d,'evaluation'))]['sharpe_zero_cash']
            and r[job_name((a,c,d,'evaluation'))]['calmar']>r[job_name((b,c,d,'evaluation'))]['calmar'] for c,d in ((10,0),(20,0),(5,1)))
        row['family_uncertainty']=all(uncertainty['means'][str(block)][i]['holm_p']<.05 and uncertainty['means'][str(block)][i]['ci95'][0]>0 for block in p['bootstrap_blocks'])
        row['retain_for_further_validation']=all(row.values());checks[a+'-'+b]=row
    report=dict(protocol=p,results=r,uncertainty=uncertainty,checks=checks,selection=read_json(root/'selection_summary.json'),
        context=read_json(root/'context_metrics.json'),control_parity=read_json(root/'control_parity.json'),native=native,promotion_eligible=False)
    write_json(root/'report.json',report)
    return dict(checks=checks,metrics={w:{s:{k:r[job_name((s,5,0,w))][k] for k in ('cagr','sharpe_zero_cash','max_drawdown','calmar')} for s in ARMS} for w in ('full','evaluation')})


def artifacts(root,output):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data,render_backtest_report_html
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    checked_files(root,'input_manifest.json');checked_files(root,'decision_manifest.json');checked_files(root,'model_manifest.json')
    report=read_json(root/'report.json');p=report['protocol'];output.mkdir(parents=True,exist_ok=True);(output/'reports').mkdir(exist_ok=True)
    economics={};quotes={};results={}
    for arm in ARMS:
        name=job_name((arm,5,0,'full'));economics[arm]=read_json(root/'python'/(name+'.json'));quotes[arm]=read_json(root/'bundles'/name/'quotes.json')
        results[arm]=report_result(economics[arm],quotes[arm],p['initial_cash_usd'],'2015-12-31')
    for arm in ARMS:
        data,warnings=build_backtest_report_data(result=results[arm],result_path=root/'python'/(job_name((arm,5,0,'full'))+'.json'),
            split_date=p['evaluation_start'],benchmark_name=LABELS['F3'],benchmark_nav_series=results['F3']['nav_series'],
            extra_benchmarks=[dict(id=s,name=LABELS[s],nav_series=results[s]['nav_series']) for s in ('M0_12','M0_14','RP12','URTH') if s!=arm],
            market_prices={s:{d:float(q['close']) for d,q in rows.items()} for s,rows in quotes[arm].items()},
            market_fx_rates={r['date']:1. for r in economics[arm]['nav']})
        flow=['Pinned audited histories; hash and common-calendar verification; exclude XOP',
              'Monthly decisions use completed prior close; 63-session inverse-volatility incoming weights, 2% cash floor']
        if arm.startswith('M'):
            flow += [f'{arm[-2:]} candidates; no mandatory asset; '+POLICIES[arm.split('_')[0]],
                'Momentum rank blend 20/35/45%; final score 75% momentum + 25% volume; top six eligible ETFs',
                'Fewer than four qualifiers: only qualified IEF/TLT/GLD incoming weights, protected residual cash',
                'Monthly one-year XGBoost refit for this pool; labels end strictly before fit close; existing tilt/caps',
                'Existing relative momentum and adaptive trend overlays; rejected candidates stay at zero',
                'Lag-20 activity: audited raw dollar turnover; adjusted direction; unchanged tilt parameters',
                'USD broad-index U1 ridge: causal 60-month per-pool refit from audited snapshots; no final 45% cap']
        elif arm=='F3':
            flow += ['Exact frozen current F3 targets: original 12, positive 252-session gate, top six price/volume ranks',
                'Defensive cash fallback → rolling XGBoost → relative momentum → adaptive trend → legacy activity → USD U1',
                'Legacy source-volume/adjusted-price activity retained only as benchmark; no final 45% cap']
        elif arm=='URTH':flow=['Pinned audited adjusted URTH prices; buy once, no rebalance']
        else:flow+=['Price-only inverse volatility across all candidate assets; no momentum selection (separate control)']
        flow+=['Next session open, whole adjusted units, 5bp costs; daily held weights and USD NAV from fills',
               'Full benchmark report; no monitoring, promotion, broker orders or execution authority']
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {len(flow)*58+10}">'
        for i,line in enumerate(flow):svg+=f'<rect x="5" y="{i*58+5}" width="1190" height="49" rx="8" fill="#e9f1f5"/><text x="18" y="{i*58+35}" font-family="sans-serif" font-size="12">{i+1}. {html.escape(line)}</text>'
        svg+='</svg>'
        last_day=max(economics[arm]['decisions']);last_targets=economics[arm]['decisions'][last_day]['targets']
        data.update(title=LABELS[arm]+' · candidate-pool study',accountingCurrency='USD',database='Published audited histories',allocationSource='Simulated fills',
            splitLabel='Previously inspected chronological boundary',sampleLabels={'in_sample':'2016–2020 retrospective','out_of_sample':'2021 onward retrospective'},
            decisionDiagrams=[dict(title='Complete decision flow',svg=svg)],strategyDefinition=dict(id=arm,protocol=p),
            warnings=[*warnings,*p['limitations'],'Chart includes initial capital on 2015-12-31; table calendar CAGR starts at first simulated session 2016-01-04. Evaluation table replays from fresh cash on 2021-01-04.'])
        rendered=render_backtest_report_html(data)
        table='<section style="margin:24px"><h2>Last scheduled target and latest simulated held weights</h2><p>Target session '+last_day+'; held weights at '+p['end']+'. No new mid-month indicative target is implied.</p><table><tr><th>Asset</th><th>Scheduled target</th><th>Held</th></tr>'
        stats=report['results'][job_name((arm,5,0,'full'))];target_map={t['symbol']:float(t['target_weight']) for t in last_targets}
        for s in sorted(quotes[arm]):table+=f'<tr><td>{s}</td><td>{target_map.get(s,0):.2%}</td><td>{stats["last_held_weights"].get(s,0):.2%}</td></tr>'
        table+=f'<tr><td>Cash</td><td>{1-sum(target_map.values()):.2%}</td><td>{1-sum(stats["last_held_weights"].values()):.2%}</td></tr></table></section>'
        (output/'reports'/(arm+'.html')).write_text(rendered.replace('</body>',table+'</body>'),encoding='utf8')
    fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
    colors={'M0_12':'#36454f','M0_14':'#16856b','M1_14':'#c3761c','M2_14':'#7d5fb0','M3_14':'#3478ba','F3':'#9b9b9b'}
    for arm,color in colors.items():
        v=np.array([float(r['nav'])/1e6 for r in economics[arm]['nav']]);days=[date.fromisoformat(r['date']) for r in economics[arm]['nav']]
        axes[0].plot(days,v,label=LABELS[arm],color=color,linestyle='--' if arm=='F3' else '-');axes[1].plot(days,v/np.maximum.accumulate(np.maximum(v,1))-1,color=color)
    axes[0].legend(ncol=3);axes[0].set_ylabel('Value / initial USD');axes[1].set_ylabel('Drawdown');axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Candidate-pool expansion and momentum · top six · USD · 5bp · retrospective');fig.tight_layout();fig.savefig(output/'comparison.png',dpi=150);plt.close(fig)
    body='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Candidate pool and momentum</title><style>body{font:16px system-ui;max-width:1250px;margin:32px auto;padding:0 20px;color:#233748;background:#f6f8fa}table{border-collapse:collapse;width:100%;background:white}th,td{padding:9px;text-align:right;border-bottom:1px solid #ddd}td:first-child,th:first-child{text-align:left}img{width:100%}li{margin:10px 0}a{color:#17549d}code{overflow-wrap:anywhere}.scroll{overflow:auto}</style></head><body><h1>Candidate pool and momentum</h1>'
    body+='<p>XLE and XLB compete for six slots; neither receives a mandatory allocation. Four momentum policies × two pools. XOP remains excluded.</p><p><strong>Correction:</strong> The earlier inverse-volatility comparison allocated across all 14 assets. It did not answer this selection question.</p>'
    body+='<p>Audited raw activity is used consistently in all eight new arms. Frozen F3 is a separate legacy reference; M0_12 versus F3 measures that bridge. Pool effects are measured between matched 12/14 arms.</p>'
    body+='<p><strong>Finding:</strong> Expanding the pool under the existing rule weakens Sharpe in both windows. Faster 21/63/126-session momentum is the most promising of these three alternatives on the expanded pool: 2021+ CAGR 11.91%, Sharpe 1.104, drawdown −8.31%. Higher-cost and delayed tests retain that advantage over M0_14, but paired confidence intervals include zero. Full-history drawdown is −19.48%, versus −16.42% for M0_12. No variant establishes a robust replacement; keep M1_14 as a research lead only.</p>'
    body+='<ul>'+''.join(f'<li><strong>{m}</strong>: {html.escape(label)}</li>' for m,label in POLICIES.items())+'</ul>'
    for window,label in [('evaluation','Primary chronological evaluation: 2021-01-04–2026-10-08'),('full','Full historical context: 2016-01-04–2026-10-08')]:
        body+=f'<h2>{label}</h2><p>5bp per traded dollar, USD, zero-interest cash. Previously inspected history; not an untouched holdout.</p><div class="scroll"><table><tr><th>Complete report</th><th>CAGR</th><th>Sharpe (zero RF)</th><th>Max drawdown</th><th>Calmar</th><th>Turnover/year</th></tr>'
        for arm in ARMS:
            s=report['results'][job_name((arm,5,0,window))]
            body+=f'<tr><td><a href="reports/{arm}.html">{LABELS[arm]}</a></td><td>{s["cagr"]:.2%}</td><td>{s["sharpe_zero_cash"]:.3f}</td><td>{s["max_drawdown"]:.2%}</td><td>{s["calmar"]:.3f}</td><td>{s["annual_turnover"]:.2f}×</td></tr>'
        body+='</table></div>'
    body+='<img src="comparison.png" alt="Portfolio growth and drawdowns"><h2>How often the additions win a slot</h2><p>Monthly selections from the full study; held weight averages include every session, including days with zero holdings.</p><table><tr><th>Policy</th><th>ETF</th><th>Eligible months</th><th>Selected months</th><th>Selection rate</th><th>Mean held weight</th><th>Held sessions</th></tr>'
    for m in POLICIES:
        sel=report['selection'][m+'_14-full']
        for symbol in ['XLE','XLB']:
            s=sel['assets'][symbol]
            body+=f'<tr><td>{m}</td><td>{symbol}</td><td>{s["eligible"]}/{sel["decisions"]}</td><td>{s["selected"]}/{sel["decisions"]}</td><td>{s["selected_fraction"]:.1%}</td><td>{s["mean_held_weight"]:.2%}</td><td>{s["held_sessions"]}/{sel["sessions"]}</td></tr>'
    body+='</table><h2>Paired comparisons and uncertainty</h2><p>Primary 2021+ period; 10,000 joint circular monthly block draws. Mean return change is annualized monthly arithmetic difference, not CAGR. Holm p-values cover all 11 comparisons. Ratio intervals are marginal.</p>'
    for block in p['bootstrap_blocks']:
        body+=f'<h3>{block}-month blocks</h3><div class="scroll"><table><tr><th>Candidate − control</th><th>Mean return change (95% CI)</th><th>Holm p</th><th>Sharpe change (95% CI)</th><th>Calmar change (95% CI)</th></tr>'
        for i,(a,b) in enumerate(COMPARISONS):
            mean=report['uncertainty']['means'][str(block)][i];ratio=report['uncertainty'][a+'-'+b][str(block)];s=ratio['sharpe'];c=ratio['calmar_252']
            body+=f'<tr><td>{a} − {b}</td><td>{mean["mean_annual"]:.2%} ({mean["ci95"][0]:.2%}, {mean["ci95"][1]:.2%})</td><td>{mean["holm_p"]:.3f}</td><td>{s["difference"]:.3f} ({s["ci95"][0]:.3f}, {s["ci95"][1]:.3f})</td><td>{c["difference"]:.3f} ({c["ci95"][0]:.3f}, {c["ci95"][1]:.3f})</td></tr>'
        body+='</table></div>'
    body+='<h2>Retention assessment</h2><p>The protocol declares the effect-size screen: Sharpe +0.05, Calmar +0.05, CAGR sacrifice ≤0.5pp and drawdown worsening ≤1pp. The conservative assessment below also requires positive Sharpe/Calmar differences at 10/20bp and one-session delay, and positive family-adjusted mean-return evidence at every block length. No comparison passes all checks; this does not prove that its economic effect is zero.</p><table><tr><th>Comparison</th><th>Failed checks</th><th>Pass all checks</th></tr>'
    for key,v in report['checks'].items():body+=f'<tr><td>{key}</td><td>{html.escape(", ".join(k for k,x in v.items() if not x and k!="retain_for_further_validation") or "none")}</td><td>{v["retain_for_further_validation"]}</td></tr>'
    body+='</table><h2>Costs and delayed execution: 2021+</h2><table><tr><th>Arm</th><th>10bp CAGR / Sharpe</th><th>20bp CAGR / Sharpe</th><th>1-session delay CAGR / Sharpe</th></tr>'
    for arm in ARMS:
        if arm=='URTH':continue
        body+='<tr><td>'+arm+'</td>'
        for cost,delay in [(10,0),(20,0),(5,1)]:
            s=report['results'][job_name((arm,cost,delay,'evaluation'))];body+=f'<td>{s["cagr"]:.2%} / {s["sharpe_zero_cash"]:.3f}</td>'
        body+='</tr>'
    body+='</table><h2>Annual returns</h2><div class="scroll"><table><tr><th>Arm</th>'+''.join('<th>'+y+'</th>' for y in report['results'][job_name(('F3',5,0,'full'))]['calendar_returns'])+'</tr>'
    for arm in ARMS:body+='<tr><td>'+arm+'</td>'+''.join(f'<td>{v:.1%}</td>' for v in report['results'][job_name((arm,5,0,'full'))]['calendar_returns'].values())+'</tr>'
    body+='</table></div><p>2026 is year-to-date through October 8.</p><h2>Calibration and stress sensitivity</h2><p>2016–2020 is descriptive calibration; no parameters were selected from it. Excluding a calendar year recomputes return-series diagnostics only, not an investable counterfactual.</p><table><tr><th>Arm</th><th>2016–2020 CAGR / Sharpe</th><th>Sharpe excluding 2020</th><th>Sharpe excluding 2022</th><th>Maximum held asset weight</th><th>Mean cash</th></tr>'
    for arm in ARMS:
        context=report['context'][arm];s=report['results'][job_name((arm,5,0,'full'))];cal=context['2016_2020']
        body+=f'<tr><td>{arm}</td><td>{cal["cagr"]:.2%} / {cal["sharpe_zero_cash"]:.3f}</td><td>{context["exclude_2020"]["sharpe_zero_cash"]:.3f}</td><td>{context["exclude_2022"]["sharpe_zero_cash"]:.3f}</td><td>{s["maximum_weight"]:.2%}</td><td>{s["mean_cash_weight"]:.2%}</td></tr>'
    body+='</table><h2>Evidence and limitations</h2><p>94 accounting replays; 12 native LEAN checks; exact frozen F3 reproduction. Training inputs, monthly models, target decisions, quotes, fills and reports are hash-verified. All new targets respect the selection set. Research only.</p><ul>'+''.join('<li>'+html.escape(s)+'</li>' for s in p['limitations'])+'</ul>'
    body+='<p>Protocol SHA-256: <code>'+sha256(root/'protocol.json')+'</code></p></body></html>'
    (output/'index.html').write_text(body,encoding='utf8')
    (output/'presentation_source').mkdir(exist_ok=True);(output/'presentation_source'/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    write_json(output/'receipt.json',dict(study=str(root.resolve()),protocol_sha256=sha256(root/'protocol.json'),report_sha256=sha256(root/'report.json'),
        files={f.relative_to(output).as_posix():sha256(f) for f in output.rglob('*') if f.is_file() and f.name!='receipt.json'}))
    return str((output/'index.html').resolve())
