"""Reconciled attribution, paired inference and shared reports for the frozen study."""
from collections import defaultdict
from datetime import date
import html
import math
from pathlib import Path
import re

import numpy as np

from systematic_trading.lean.contracts import sha256,write_json
from systematic_trading.research.momentum_replay import read_json,checked_files,verify_usd_bundle
from systematic_trading.research.cash_stress import RULES,COMPARISONS
from systematic_trading.research.cash_stress_study import jobs,job_name

LABELS={'R0':'Current F3','R1':'Existing cash · scheduled SPY','R2':'Existing cash · stress SPY',
    'R3':'Existing cash · confirmed SPY','L2':'Existing cash · stress bottom 3','L3':'Existing cash · confirmed bottom 3',
    'W2':'Existing cash · stress top 3','W3':'Existing cash · confirmed top 3',
    **{f'B{n}_{k}':f'{n}% reserve · {v}' for n in (10,20) for k,v in [('fixed','held'),('stress','stress SPY'),('confirm','confirmed SPY')]},
    'XRM':'Training-risk-matched URTH','RP12':'12-ETF inverse volatility','URTH':'URTH buy and hold'}
PAIRS=[(park,a,b) for park in ('ZERO','BIL') for a,b in COMPARISONS]


def pair_key(park,a,b):return park+':'+a+'-'+b


def attribution(economic,quotes,events):
    """Partition actual NAV changes into core, BIL and owned stress quantities."""
    q={s:0. for s in quotes};sleeve=[];phases=[];cycles={};active=None;phase='peaceful_waiting'
    previous_day=None;previous_nav=1e6;navs=[];cycle_pnl=defaultdict(float);cycle_min=defaultdict(float)
    for row in economic['nav']:
        day=row['date'];event=events.get(day);owner=active
        pnl=sum(q[s]*(float(quotes[s][day]['close'])-float(quotes[s][previous_day]['close'] if previous_day else quotes[s][day]['reference'])) for s in quotes)
        if event:
            for s,change in event['changes'].items():
                pnl+=float(change)*(float(quotes[s][day]['close'])-float(event['execution_prices'][s]))-float(event['fees'][s])
            q={s:float(v) for s,v in event['quantities'].items()}
            active=event['cycle'];phase=event['phase']
            owner=active if active is not None else owner
            if active is not None and event['cycle_budget_usd'] is not None:
                key=str(active)
                c=cycles.setdefault(key,dict(first_funding=day,budget=float(event['cycle_budget_usd']),
                    deployments=[],deployment_attempts=[],basket=[],spent_levels=0,exit_date=None,exit_reason=None))
                if event['new_tranches']:
                    c['deployment_attempts'].append(day);c['basket']=event['basket'];c['spent_levels']=event['levels_spent']
                    purchased=sum(max(0,float(change))*float(event['execution_prices'][s]) for s,change in event['changes'].items())
                    if purchased>.01:c['deployments'].append(day)
            if event['exit_reason'] and owner is not None and str(owner) in cycles:
                cycles[str(owner)].update(exit_date=day,exit_reason=event['exit_reason'])
        if owner is not None:
            cycle_pnl[str(owner)]+=pnl;cycle_min[str(owner)]=min(cycle_min[str(owner)],cycle_pnl[str(owner)])
        sleeve.append(pnl);phases.append(phase);navs.append(float(row['nav'])-previous_nav)
        if phase=='replenishment':phase='stress_waiting' if event['active_stress'] else 'peaceful_waiting'
        previous_day=day;previous_nav=float(row['nav'])
    for key,c in cycles.items():
        c.update(net_sleeve_pnl=cycle_pnl[key],worst_cumulative_pnl=cycle_min[key],
            worst_loss_fraction_of_locked_budget=cycle_min[key]/c['budget'],open_at_end=c['exit_date'] is None)
    return dict(stress_pnl_usd=sum(sleeve),stress_daily_pnl=sleeve,phases=phases,cycles=cycles,
        funded_cycles=len(cycles),deployed_cycles=sum(bool(c['deployments']) for c in cycles.values()),
        open_funded_cycles=sum(c['open_at_end'] for c in cycles.values()),portfolio_daily_pnl=navs)


def refresh_attribution(root):
    """Rebuild descriptive ownership diagnostics without changing any replay or inference input."""
    saved=read_json(root/'attribution.json');stats=read_json(root/'statistics.json')
    for name in saved['arms']:
        d=attribution(read_json(root/'python'/(name+'.json')),read_json(root/'bundles'/name/'quotes.json'),read_json(root/'events'/(name+'.json')))
        d['bil_pnl_usd']=stats[name]['asset_pnl_usd'].get('BIL',0)
        d['core_pnl_usd']=stats[name]['terminal_nav']-1e6-d['stress_pnl_usd']-d['bil_pnl_usd']
        saved['arms'][name]=d
    write_json(root/'attribution.json',saved)


def summarize(root):
    from systematic_trading.research.momentum_analysis import statistics
    checked_files(root,'input_manifest.json');results={};detail={}
    all_jobs=jobs()+[('XRM',p,c,d,'evaluation') for p in ('ZERO','BIL') for c,d in ((5,0),(10,0),(20,0),(5,1))]
    for job in all_jobs:
        name=job_name(job);path=root/'python'/(name+'.json');bundle=root/'bundles'/name
        verify_usd_bundle(bundle);event_path=root/'events'/(name+'.json')
        expected=dict(sha256=sha256(path),manifest_sha256=sha256(bundle/'manifest.json'),events_sha256=sha256(event_path),dynamic_frozen_parity=True)
        if read_json(path.with_suffix('.receipt.json'))!=expected:raise ValueError('Changed cash replay: '+name)
        e=read_json(path);quotes=read_json(bundle/'quotes.json');s=statistics(e,quotes)
        if job==('R0','ZERO',5,0,'full'):
            prior=read_json(root/'baseline_economic.json')
            if any(e[k]!=prior[k] for k in ('nav','fills','final_positions')):raise ValueError('F3 changed')
        s['calmar']=s['cagr']/abs(s['max_drawdown']);daily=np.array(s['daily_returns'])
        s['expected_shortfall_5pct']=float(np.sort(daily)[:max(1,math.ceil(.05*len(daily)))].mean())
        cash=np.array([float(quotes['BIL'][d]['close'])/float(quotes['BIL'][d]['reference'])-1 for d in s['dates']])
        excess=daily-cash;s['sharpe_excess_bil']=float(excess.mean()/excess.std(ddof=1)*np.sqrt(252))
        wealth=np.cumprod(1+daily);under=wealth<np.maximum.accumulate(np.maximum(wealth,1))-1e-12
        run=0;longest=0
        for v in under:run=run+1 if v else 0;longest=max(longest,run)
        s.update(longest_drawdown_sessions=longest,unrecovered_sessions=run)
        if job[2:4]==(5,0):
            d=attribution(e,quotes,read_json(event_path));d['bil_pnl_usd']=s['asset_pnl_usd'].get('BIL',0)
            d['core_pnl_usd']=s['terminal_nav']-1e6-d['stress_pnl_usd']-d['bil_pnl_usd']
            detail[name]=d
        # Keep inference inputs compact; full asset attribution is reproducible from fills.
        s.pop('asset_daily_contribution');results[name]=s
    phases={}
    for window in ('full','evaluation'):
        for park,a,b in PAIRS:
            left,right=(detail[job_name((x,park,5,0,window))] for x in (a,b));totals=defaultdict(float)
            for phase,x,y in zip(left['phases'],left['portfolio_daily_pnl'],right['portfolio_daily_pnl'],strict=True):totals[phase]+=x-y
            expected=results[job_name((a,park,5,0,window))]['terminal_nav']-results[job_name((b,park,5,0,window))]['terminal_nav']
            if abs(sum(totals.values())-expected)>.02:raise ValueError('Phase PnL failed reconciliation')
            phases[pair_key(park,a,b)+'-'+window]=dict(phases=dict(totals),terminal_difference=expected)
    # Delete one complete observed market episode at a time, preserving daily pairs.
    signals=read_json(root/'signals.json');market=[];opened=None
    for day,v in sorted(signals.items()):
        if v['active'] and opened is None:opened=day
        elif opened and not v['active']:market.append((opened,day));opened=None
    if opened:market.append((opened,read_json(root/'protocol.json')['end']))
    sensitivity={}
    for park,a,b in PAIRS:
        left,right=(results[job_name((x,park,5,0,'evaluation'))] for x in (a,b));rows=[]
        for start,end in market:
            if end<'2021-01-04':continue
            mask=np.array([not start<=d<=end for d in left['dates']]);x=np.array(left['daily_returns'])[mask];y=np.array(right['daily_returns'])[mask]
            rows.append(dict(excluded_start=start,excluded_end=end,sessions=int(mask.sum()),
                mean_daily_difference_annualized=float((x-y).mean()*252),
                sharpe_difference=float(x.mean()/x.std(ddof=1)*np.sqrt(252)-y.mean()/y.std(ddof=1)*np.sqrt(252))))
        sensitivity[pair_key(park,a,b)]=rows
    write_json(root/'statistics.json',results);write_json(root/'statistics_receipt.json',dict(sha256=sha256(root/'statistics.json')))
    write_json(root/'attribution.json',dict(arms=detail,paired_phases=phases,market_episodes=market,leave_episode_out=sensitivity))


def inference_job(job):
    from systematic_trading.research.momentum_analysis import paired_bootstrap
    from systematic_trading.research.construction_analysis import bootstrap_ratios
    root,kind,block,index=job;root=Path(root);p=read_json(root/'protocol.json')
    if read_json(root/'statistics_receipt.json')['sha256']!=sha256(root/'statistics.json'):raise ValueError('Changed statistics')
    results=read_json(root/'statistics.json')
    def r(arm,park):return results[job_name((arm,park,5,0,'evaluation'))]
    if kind=='means':
        months=sorted(r('R0','ZERO')['monthly'])
        matrix=np.array([[r(a,park)['monthly'][m]-r(b,park)['monthly'][m] for park,a,b in PAIRS] for m in months])
        return 'means',str(block),paired_bootstrap(matrix,block=block,replications=p['bootstrap_replications'],seed=p['seed'])
    park,a,b=PAIRS[index];left,right=r(a,park),r(b,park)
    if left['dates']!=right['dates']:raise ValueError('Unmatched paired calendar')
    return pair_key(park,a,b),str(block),bootstrap_ratios(left['dates'],left['daily_returns'],right['daily_returns'],
        block=block,replications=p['bootstrap_replications'],seed=p['seed'])


def effect_screen(a,b,p):
    s=p['retention_screen']
    return dict(return_effect=a['cagr']-b['cagr']>=s['min_cagr_gain'] and a['sharpe_zero_cash']-b['sharpe_zero_cash']>=s['min_sharpe_gain']
        and a['calmar']-b['calmar']>=s['min_calmar_gain'] and a['max_drawdown']>=b['max_drawdown']-s['max_drawdown_worsening'],
        protection_effect=a['max_drawdown']-b['max_drawdown']>=s['protection_min_drawdown_gain'] and a['cagr']>=b['cagr']-s['protection_max_cagr_sacrifice'])


def finalize(root,values):
    p=read_json(root/'protocol.json');r=read_json(root/'statistics.json');uncertainty={};native={};checks={}
    for key,block,value in values:uncertainty.setdefault(key,{})[block]=value
    primary=[(a,park,5,0,'full') for a in RULES for park in ('ZERO','BIL')]+[('XRM',park,5,0,'evaluation') for park in ('ZERO','BIL')]
    for job in primary:
        name=job_name(job);path=root/'native'/name;checked_files(path,'artifact_manifest.json')
        if read_json(path/'run.json')['status']!='succeeded' or not read_json(path/'parity.json')['passed']:raise ValueError('Native validation missing '+name)
        native[name]=dict(run_sha256=sha256(path/'run.json'),parity_sha256=sha256(path/'parity.json'))
    for i,(park,a,b) in enumerate(PAIRS):
        def stats(x,c=5,d=0):return r[job_name((x,park,c,d,'evaluation'))]
        row=effect_screen(stats(a),stats(b),p)
        row['return_cost_delay']=all(effect_screen(stats(a,c,d),stats(b,c,d),p)['return_effect'] for c,d in ((10,0),(20,0),(5,1)))
        row['protection_cost_delay']=all(effect_screen(stats(a,c,d),stats(b,c,d),p)['protection_effect'] for c,d in ((10,0),(20,0),(5,1)))
        row['family_uncertainty']=all(uncertainty['means'][str(block)][i]['holm_p']<.05 and uncertainty['means'][str(block)][i]['ci95'][0]>0 for block in p['bootstrap_blocks'])
        row['robust_return_evidence']=row['return_effect'] and row['return_cost_delay'] and row['family_uncertainty']
        checks[pair_key(park,a,b)]=row
    write_json(root/'report.json',dict(protocol=p,results=r,uncertainty=uncertainty,checks=checks,native=native,
        attribution=read_json(root/'attribution.json'),risk_control=read_json(root/'risk_control.json'),promotion_eligible=False))
    return dict(replays=len(r),native=len(native),robust_return_comparisons=[k for k,v in checks.items() if v['robust_return_evidence']],
        effect_screen_comparisons=[k for k,v in checks.items() if v['return_effect'] or v['protection_effect']])


def artifacts(root,output):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data,render_backtest_report_html
    from systematic_trading.research.momentum_analysis import statistics
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    checked_files(root,'input_manifest.json');report=read_json(root/'report.json');p=report['protocol'];r=report['results']
    output.mkdir(parents=True,exist_ok=True);(output/'reports').mkdir(exist_ok=True)
    previous=Path(read_json(root/'data_receipt.json')['parent_study']);benchmarks={}
    checked_files(previous,'input_manifest.json');checked_files(previous,'decision_manifest.json')
    for arm in ('RP12','URTH'):
        for window in ('full','evaluation'):
            name=f'{arm}-cost5-delay0-{window}';path=previous/'python'/(name+'.json');bundle=previous/'bundles'/name
            verify_usd_bundle(bundle)
            if read_json(path.with_suffix('.receipt.json'))!=dict(sha256=sha256(path),manifest_sha256=sha256(bundle/'manifest.json')):raise ValueError('Benchmark receipt mismatch')
            econ=read_json(path);q=read_json(bundle/'quotes.json');s=statistics(econ,q);s['calmar']=s['cagr']/abs(s['max_drawdown'])
            benchmarks[arm+'-'+window]=dict(stats=s,result=report_result(econ,q,p['initial_cash_usd'],'2015-12-31' if window=='full' else '2020-12-31'))
    economics={};quotes={};results={};names=[]
    for park in ('ZERO','BIL'):
        for arm in [*RULES,'XRM']:
            window='evaluation' if arm=='XRM' else 'full';name=job_name((arm,park,5,0,window));names.append((arm,park,window,name))
            economics[name]=read_json(root/'python'/(name+'.json'));quotes[name]=read_json(root/'bundles'/name/'quotes.json')
            results[name]=report_result(economics[name],quotes[name],p['initial_cash_usd'],'2020-12-31' if window=='evaluation' else '2015-12-31')
    for arm,park,window,name in names:
        if window=='evaluation':
            bn=job_name(('R0',park,5,0,window));be=read_json(root/'python'/(bn+'.json'));bq=read_json(root/'bundles'/bn/'quotes.json')
            benchmark=report_result(be,bq,p['initial_cash_usd'],'2020-12-31')
        else:benchmark=results[job_name(('R0',park,5,0,'full'))]
        data,warnings=build_backtest_report_data(result=results[name],result_path=root/'python'/(name+'.json'),split_date=p['evaluation_start'],
            benchmark_name='Current F3 · '+park,benchmark_nav_series=benchmark['nav_series'],
            extra_benchmarks=[dict(id=b,name=LABELS[b],nav_series=benchmarks[b+'-'+window]['result']['nav_series']) for b in ('RP12','URTH')],
            market_prices={s:{d:float(v['close']) for d,v in qs.items()} for s,qs in quotes[name].items()},market_fx_rates={x['date']:1. for x in economics[name]['nav']})
        flow=['Pinned audited adjusted histories and frozen exact F3 targets; reject gaps/hash changes',
            'Parent: original 12 candidates → positive 252-day gate → top six price/volume ranks → defensive IEF/TLT/GLD cash fallback',
            'Parent: causal rolling XGBoost → relative momentum → adaptive trend → legacy activity → USD ridge; no final cap',
            'Reserve: original parent cash capped at 20% NAV, or scale parent by 90% / 80% for additional reserve',
            'Monthly prior-close SPY stress: 10/20/30% below 252-session peak; fixed peak after entry; one locked dollar budget',
            'Buy one third per breached level; optional SMA63 + positive 21-day confirmation; scheduled control buys over 3 months',
            'Basket: SPY or original-pool bottom/top 3 by 63/126/252 momentum ranks (20/35/45); freeze basket at first buy',
            'Hold sleeve quantities without top-up; parent funding priority, 2% cash floor and no added ETF exposure above 45%',
            'Exit at 95% of entry peak or 12 monthly intervals; timeout cannot re-arm before recovery; proceeds replenish cash',
            'ZERO cash or audited BIL parking capped 45%; next open, whole adjusted units, 5bp costs, actual fill attribution',
            'Daily NAV/held weights and complete benchmark report; research only, no promotion or broker authority']
        if arm in RULES:
            rule=RULES[arm]
            flow[3]=f'Funding: scale parent by {1-rule["reserve"]:.0%}; additional {rule["reserve"]:.0%} reserve' if rule['reserve'] else 'Funding: unchanged parent weights; use only existing cash above 2%, sleeve capped at 20% NAV'
            flow[9]=f'{park} residual parking'+(' above 2% cash, BIL capped at 45%' if park=='BIL' else ' earns zero interest')+'; next open, whole adjusted units, 5bp costs'
            if rule['entry']=='none':flow=flow[:4]+['No stress purchases in this control; maintain the registered parent/reserve policy at each monthly decision']+flow[9:]
            else:
                flow[6]={'market':'SPY only','losers':'Bottom 3 original-pool ETFs','winners':'Top 3 original-pool ETFs'}[rule['basket']]+'; 63/126/252 momentum ranks (20/35/45), no positive gate; freeze basket on first buy'
                if rule['entry']=='scheduled':
                    flow[4]='Start a cycle when available parent cash reaches 1% NAV; lock dollar budget; no market-stress trigger'
                    flow[5]='One third of locked budget at each of the first three monthly decisions; no stress or confirmation condition'
                    flow[8]='Exit after 12 monthly intervals; funding crowd-out may sell earlier; proceeds replenish parent cash'
                else:
                    flow[5]='Buy one third per remembered breached stage; '+('require SPY above SMA63 and positive 21-session return' if rule['entry']=='confirmed' else 'no recovery confirmation')
        if arm=='XRM':flow=['Pinned audited adjusted URTH and BIL histories','URTH weight fixed using only 2016–2020 R2/ZERO versus URTH volatility',
            f'Frozen URTH target {report["risk_control"]["weight"]:.4%}; monthly rebalance from January 2021; residual '+park,
            'Next open, whole units, 5bp costs, daily NAV and full benchmarks; research only']
        svg=f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 {len(flow)*55+10}">'
        for i,line in enumerate(flow):svg+=f'<rect x="5" y="{i*55+5}" width="1190" height="47" rx="8" fill="#e9f1f5"/><text x="16" y="{i*55+34}" font-family="sans-serif" font-size="12">{i+1}. {html.escape(line)}</text>'
        svg+='</svg>'
        data.update(title=LABELS[arm]+' · '+park,accountingCurrency='USD',database='Published audited histories',allocationSource='Simulated fills',
            splitLabel='Previously inspected chronological boundary',sampleLabels={'in_sample':'2016–2020 retrospective','out_of_sample':'2021 onward retrospective'},
            decisionDiagrams=[dict(title='Complete decision flow · enabled arm '+arm,svg=svg)],strategyDefinition=dict(id=arm,parking=park,rule=RULES.get(arm),protocol=p),
            warnings=[*warnings,*p['limitations'],'Reports show the full-history path; primary evaluation is a separate fresh-cash replay. No recurring tracked strategy is created by this research.',
                'Shared historical accounting permits same-rebalance sale proceeds; settlement timing and account-specific product permissions are not qualified by this study.'])
        last=max(economics[name]['decisions']);targets={v['symbol']:float(v['target_weight']) for v in economics[name]['decisions'][last]['targets']};s=r[name]
        table=f'<section style="margin:24px"><h2>Scheduled targets and held weights</h2><p>Last scheduled target: {last}; holdings: {p["end"]}. This is a historical study, not a current indicative allocation.</p><table><tr><th>Asset</th><th>Target</th><th>Held</th></tr>'
        for symbol in sorted(quotes[name]):table+=f'<tr><td>{symbol}</td><td>{targets.get(symbol,0):.2%}</td><td>{s["last_held_weights"].get(symbol,0):.2%}</td></tr>'
        table+=f'<tr><td>Cash</td><td>{1-sum(targets.values()):.2%}</td><td>{1-sum(s["last_held_weights"].values()):.2%}</td></tr></table></section>'
        rendered=render_backtest_report_html(data).replace('</body>',table+'</body>')
        rendered=re.sub(r'(href=["\'])(/[^"\']*)',r'\1http://127.0.0.1:8000\2',rendered)
        (output/'reports'/(arm+'-'+park+'.html')).write_text(rendered,encoding='utf8')
    fig,axes=plt.subplots(2,1,figsize=(12,8),sharex=True)
    for arm,color in [('R0','#394954'),('R1','#8c9b91'),('R2','#177d9b'),('R3','#378c69'),('L2','#c36a28'),('W2','#8b57a7')]:
        e=economics[job_name((arm,'ZERO',5,0,'full'))];v=np.array([float(x['nav'])/1e6 for x in e['nav']]);days=[date.fromisoformat(x['date']) for x in e['nav']]
        axes[0].plot(days,v,label=arm+' · '+LABELS[arm],color=color);axes[1].plot(days,v/np.maximum.accumulate(np.maximum(v,1))-1,color=color)
    axes[0].legend(ncol=2,fontsize=9);axes[0].set_ylabel('Value / initial USD');axes[1].set_ylabel('Drawdown');axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes:ax.grid(alpha=.2)
    fig.suptitle('Cash-funded stress sleeves · zero-interest residual cash · 5bp · retrospective');fig.tight_layout();fig.savefig(output/'comparison.png',dpi=150);plt.close(fig)
    body='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Cash reserve and stress buying</title><style>body{font:16px system-ui;max-width:1320px;margin:30px auto;padding:0 20px;color:#233748;background:#f6f8fa}table{border-collapse:collapse;width:100%;background:white}th,td{padding:8px;text-align:right;border-bottom:1px solid #ddd}td:first-child,th:first-child{text-align:left}img{width:100%}li{margin:8px 0}a{color:#17549d}code{overflow-wrap:anywhere}.scroll{overflow:auto}</style></head><body><h1>Cash reserve and stress buying</h1>'
    body+='<p>Separate bounded sleeve: SPY, bottom-three momentum or top-three momentum. Parent F3 selection is unchanged. Two funding sources, zero-interest cash and audited BIL parking. 232 replays, 30 native checks; no allocation or promotion change.</p>'
    body+='<p><strong>Rules:</strong> Monthly decisions, 10%/20%/30% SPY drawdown stages, equal tranches, fixed dollar cycle budget. Confirmation requires SPY above its 63-session average and a positive 21-session return. Exit at 95% recovery or twelve months. No repeated buying of a spent tranche. Bottom/top three use the original mixed-asset ETF pool and existing 63/126/252 momentum rank.</p>'
    robust=[k for k,v in report['checks'].items() if v['robust_return_evidence']]
    body+='<p><strong>Family-adjusted result:</strong> '+(html.escape(', '.join(robust)) if robust else 'No comparison establishes robust positive-return evidence under the registered screen.')+' Historical effect sizes are shown below; these are not untouched out-of-sample results.</p>'
    body+='<p><strong>Interpretation:</strong> SPY stress buying modestly improves the parent, but does not beat scheduled SPY deployment. The bottom-three basket trails SPY and the top-three basket in 2021+. Additional 10%/20% reserves cost more return than stress buying recovers under these rules. Only three monthly stress episodes occur in the full sample; existing F3 cash funds two, including just one since 2021. It funds no 2020 sleeve because the parent had already invested that cash. BIL reduces reserve drag, but is a separate parking effect.</p>'
    def get(arm,park,window='evaluation',c=5,d=0):return r[job_name((arm,park,c,d,window))]
    body+='<h2>Cost of holding an additional reserve</h2><p>CAGR difference versus the same-parking parent; the fixed reserve never buys stress. This directly measures the historical cost of waiting, across the entire cycle.</p><table><tr><th>Parking</th><th>Reserve</th><th>2016–2020 CAGR change</th><th>2021+ CAGR change</th><th>Full-period CAGR change</th></tr>'
    for park in ('ZERO','BIL'):
        for n in (10,20):
            arm=f'B{n}_fixed';vals=[]
            for a in (arm,'R0'):
                s=get(a,park,'full');rr=[v for d,v in zip(s['dates'],s['daily_returns']) if d<'2021'];years=(date(2020,12,31)-date.fromisoformat(s['dates'][0])).days/365.25;vals.append(float(np.prod(1+np.array(rr))**(1/years)-1))
            body+=f'<tr><td>{park}</td><td>{n}%</td><td>{vals[0]-vals[1]:+.2%}</td><td>{get(arm,park)["cagr"]-get("R0",park)["cagr"]:+.2%}</td><td>{get(arm,park,"full")["cagr"]-get("R0",park,"full")["cagr"]:+.2%}</td></tr>'
    body+='</table><p>The 2016–2020 column is a chronological slice, not a claim that every session was peaceful. Paired phase attribution below separates waiting and deployment.</p>'
    for window,label in [('evaluation','Primary evaluation · 2021-01-04–2026-10-08'),('full','Full context · 2016-01-04–2026-10-08')]:
        for park in ('ZERO','BIL'):
            body+=f'<h2>{label} · {park}</h2><div class="scroll"><table><tr><th>Complete report</th><th>CAGR</th><th>Sharpe / excess BIL</th><th>Max drawdown</th><th>Calmar</th><th>Daily ES5%</th><th>Mean cash / BIL</th><th>Funded / deployed cycles</th></tr>'
            for arm in [*RULES]+(['XRM'] if window=='evaluation' else []):
                s=get(arm,park,window);diag=report['attribution']['arms'][job_name((arm,park,5,0,window))]
                body+=f'<tr><td><a href="reports/{arm}-{park}.html">{arm} · {LABELS[arm]}</a></td><td>{s["cagr"]:.2%}</td><td>{s["sharpe_zero_cash"]:.3f} / {s["sharpe_excess_bil"]:.3f}</td><td>{s["max_drawdown"]:.2%}</td><td>{s["calmar"]:.3f}</td><td>{s["expected_shortfall_5pct"]:.2%}</td><td>{s["mean_cash_weight"]:.1%} / {s["mean_asset_weights"].get("BIL",0):.1%}</td><td>{diag["funded_cycles"]} / {diag["deployed_cycles"]}</td></tr>'
            for arm in ('RP12','URTH'):
                s=benchmarks[arm+'-'+window]['stats'];body+=f'<tr><td>{LABELS[arm]}</td><td>{s["cagr"]:.2%}</td><td>{s["sharpe_zero_cash"]:.3f}</td><td>{s["max_drawdown"]:.2%}</td><td>{s["calmar"]:.3f}</td><td colspan="3">Pinned matched benchmark; included in full reports</td></tr>'
            body+='</table></div>'
    body+='<img src="comparison.png" alt="Full-period portfolio values and drawdowns"><h2>Cash drag, deployment and replenishment</h2><p>2021+ paired dollar P&amp;L differences on $1m each. Disjoint phases sum exactly to terminal wealth difference; they are not additive CAGR components. Waiting losses include scaled-parent exposure, costs and parking effects.</p><table><tr><th>Pair / parking</th><th>Peaceful waiting</th><th>Stress waiting</th><th>Deployed</th><th>Exit day</th><th>Total</th></tr>'
    for park,a,b in PAIRS:
        v=report['attribution']['paired_phases'][pair_key(park,a,b)+'-evaluation'];x=v['phases'];body+=f'<tr><td>{a} − {b} / {park}</td>'+''.join(f'<td>${x.get(k,0):+,.0f}</td>' for k in ('peaceful_waiting','stress_waiting','deployed','replenishment'))+f'<td>${v["terminal_difference"]:+,.0f}</td></tr>'
    body+='</table><h2>Funded stress cycles · full history · ZERO</h2><p>Worst loss is cumulative sleeve P&amp;L divided by the locked budget, including unused capital; it is not an asset drawdown. Realized/marked P&amp;L includes allocated trading fees. Unfinished holdings remain marked through October 8.</p><table><tr><th>Arm / funding</th><th>Basket</th><th>Deployments</th><th>Spent stages</th><th>Exit</th><th>Net sleeve P&amp;L</th><th>Worst loss / budget</th></tr>'
    for arm in RULES:
        if arm=='R1':continue
        for c in report['attribution']['arms'][job_name((arm,'ZERO',5,0,'full'))]['cycles'].values():
            body+=f'<tr><td>{arm} / {c["first_funding"]}</td><td>{", ".join(c["basket"])}</td><td>{", ".join(c["deployments"]) or "none"}</td><td>{c["spent_levels"]}/3</td><td>{c["exit_date"] or "open / waiting"}</td><td>${c["net_sleeve_pnl"]:+,.0f}</td><td>{c["worst_loss_fraction_of_locked_budget"]:.2%}</td></tr>'
    body+='</table><h2>Paired uncertainty · primary 2021+ window</h2><p>10,000 joint circular monthly block draws; Holm adjustment jointly covers all 46 declared contrasts under both parking modes. Mean change is annualized arithmetic monthly difference, not CAGR. Sharpe/Calmar intervals are marginal; bootstrap Calmar uses 252 sessions/year.</p>'
    for block in p['bootstrap_blocks']:
        body+=f'<details {"open" if block==6 else ""}><summary>{block}-month blocks</summary><table><tr><th>Comparison</th><th>Mean change (95% CI)</th><th>Holm p</th><th>Sharpe change (95% CI)</th><th>Calmar change (95% CI)</th></tr>'
        for i,(park,a,b) in enumerate(PAIRS):
            mean=report['uncertainty']['means'][str(block)][i];ratio=report['uncertainty'][pair_key(park,a,b)][str(block)];s=ratio['sharpe'];c=ratio['calmar_252']
            body+=f'<tr><td>{a} − {b} / {park}</td><td>{mean["mean_annual"]:+.2%} ({mean["ci95"][0]:+.2%}, {mean["ci95"][1]:+.2%})</td><td>{mean["holm_p"]:.3f}</td><td>{s["difference"]:+.3f} ({s["ci95"][0]:+.3f}, {s["ci95"][1]:+.3f})</td><td>{c["difference"]:+.3f} ({c["ci95"][0]:+.3f}, {c["ci95"][1]:+.3f})</td></tr>'
        body+='</table></details>'
    body+='<h2>Costs and delay · 2021+</h2><table><tr><th>Arm / parking</th><th>10bp CAGR / Sharpe</th><th>20bp CAGR / Sharpe</th><th>One-session delay CAGR / Sharpe</th></tr>'
    for park in ('ZERO','BIL'):
        for arm in [*RULES,'XRM']:
            body+=f'<tr><td>{arm} / {park}</td>'
            for c,d in ((10,0),(20,0),(5,1)):
                s=get(arm,park,c=c,d=d);body+=f'<td>{s["cagr"]:.2%} / {s["sharpe_zero_cash"]:.3f}</td>'
            body+='</tr>'
    body+='</table><h2>Predeclared assessment</h2><p>'+html.escape(p['assessment'])+'</p><table><tr><th>Pair</th><th>Return effect</th><th>Protection effect</th><th>Return survives costs/delay</th><th>Protection survives</th><th>Family uncertainty</th></tr>'
    for key,v in report['checks'].items():body+='<tr><td>'+html.escape(key)+'</td>'+''.join('<td>'+str(v[k])+'</td>' for k in ('return_effect','protection_effect','return_cost_delay','protection_cost_delay','family_uncertainty'))+'</tr>'
    body+='</table><h2>Leave one market episode out</h2><p>Descriptive sensitivity only. Removed intervals create calendar gaps, so no gap-adjusted CAGR is reported.</p><table><tr><th>Pair</th><th>Omitted episode</th><th>Annualized daily mean difference</th><th>Sharpe difference</th></tr>'
    for key,rows in report['attribution']['leave_episode_out'].items():
        for v in rows:body+=f'<tr><td>{html.escape(key)}</td><td>{v["excluded_start"]}–{v["excluded_end"]}</td><td>{v["mean_daily_difference_annualized"]:+.2%}</td><td>{v["sharpe_difference"]:+.3f}</td></tr>'
    body+='</table><h2>Scope and limitations</h2><ul>'+''.join('<li>'+html.escape(v)+'</li>' for v in p['limitations'])+'</ul>'
    body+='<p>Shared historical accounting permits same-rebalance sale proceeds; settlement timing and account-specific product permissions are not qualified by this study. Independent engine parity validates the specified accounting, not those live assumptions.</p>'
    body+=f'<p>Frozen protocol SHA-256: <code>{sha256(root/"protocol.json")}</code>. Audited batch: <code>{read_json(root/"data_receipt.json")["batch"]}</code>.</p></body></html>'
    (output/'index.html').write_text(body,encoding='utf8')
    (output/'presentation_source').mkdir(exist_ok=True)
    (output/'presentation_source'/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    (output/'presentation_source'/'run_cash_stress.py').write_bytes((Path(__file__).parents[3]/'scripts/run_cash_stress.py').read_bytes())
    write_json(root/'presentation_receipt.json',dict(report_sha256=sha256(root/'report.json'),analysis_sha256=sha256(Path(__file__)),
        outputs={f.relative_to(output).as_posix():sha256(f) for f in output.rglob('*') if f.is_file()}))
    return dict(index=str(output/'index.html'),complete_reports=len(names))
