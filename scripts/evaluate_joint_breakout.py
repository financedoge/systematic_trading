"""Portfolio applications, independent native replay and joint-study report."""
from __future__ import annotations
import argparse
import html
from pathlib import Path
import shutil
import numpy as np
import pandas as pd
from run_joint_breakout import (
    ROOT,PUBLIC,PARENT,asset,check,control_tape,SingleReplay,History,summary_path,
    read,write,verify,digest,manifest,transitions,
)
from run_range_breakout import Replay
from systematic_trading.research.range_joint import describe
from systematic_trading.research.range_breakout import portfolio_tapes,adopted_indices,metrics


def seal_evaluator(root):
    """Fix construction details before any 2024+ replay."""
    dest=root/'evaluation_protocol'
    if (dest/'manifest.json').exists():
        verify(dest,'manifest.json');return
    dest.mkdir(exist_ok=True)
    shutil.copyfile(__file__,dest/'runner.py')
    write(dest/'construction.json',dict(
        declaration='Before v3 OOS replay; no fitted lifecycle changes.',
        equal_budget='Each liquidity/duplicate-admitted candidate receives .98/count(admitted) budget; active sleeves use their budget, others retain cash. Positive2023-score gate removes exposure without redistributing its budget. Same denominator and gate apply to equal-budget positive126-session momentum control.',
        factor_score='Causal extension above frozen range upper divided by configured current ATR, clipped0..10; inactive0. Rank only affects inherited slot allocation.',
        timing='Portfolio controls: monthly; event=monthly plus L1 target-change>10% including cash or held-signal exit. Compare theoretical target to last adopted target. Individual2023 timing selection does not select portfolio construction.',
        retention='Reuse pinned parent52-pool input matrices and recipe. Primary paths, compact stress metrics and native accounting evidence.',
        inference='1000 paired21-session circular-block draws; max-t across52 selected-minus-buyhold and separately selected-minus-v1 mean log returns. Does not erase prior historical selection or certify full search multiplicity.'))
    manifest(dest,'manifest.json',[p for p in dest.iterdir() if p.is_file()])


def check_evaluator(root):
    verify(root/'evaluation_protocol','manifest.json')
    if digest(Path(__file__))!=digest(root/'evaluation_protocol/runner.py'):
        raise ValueError('Evaluator differs from sealed source')


def pool(root):
    check(root);check_evaluator(root);verify(root,'selection_manifest.json');verify(root,'variants_manifest.json')
    parent=PARENT/'pool';verify(parent,'input_manifest.json');verify(parent,'result_manifest.json')
    dest=root/'pool'
    if (dest/'result_manifest.json').exists():
        verify(dest,'input_manifest.json');verify(dest,'result_manifest.json');return
    a=dict(np.load(parent/'inputs.npz'));recipe=read(parent/'recipe.json');symbols=a['symbols'].tolist();days=a['days'];n,m=a['close'].shape
    choices=read(root/'selection.json')['choices'];variants=read(root/'variants.json')['variants']
    factors={name:dict(active=np.zeros((n,m),bool),score=np.zeros((n,m))) for name in ('selected','shared','v1')}
    for j,s in enumerate(symbols):
        full=asset(s);h=History.build(full);mask=(full['days']>=days[0])&(full['days']<=days[-1]);np.testing.assert_array_equal(full['days'][mask],days)
        choice=choices[s]
        tapes=dict(selected=h.signals(choice['parameters']) if choice['parameters'] else control_tape(full,s,choice['variant'],h),
            shared=h.signals(variants[s]['shared']['parameters']),v1=control_tape(full,s,'v1',h))
        for name,tape in tapes.items():
            active=tape['active'];upper=tape.get('upper')
            if upper is None and name=='selected' and choice['variant']=='v2':
                from calibrate_range_breakout import selected_signal
                ident=read(PARENT/'selection.json')['selections'][s]['id'];old=selected_signal(full,ident,details=True)
                upper=old.get('upper',full['close']);atr=old.get('entry_atr',h.arrays[11][2])
            else:
                p=choice['parameters'] if name=='selected' else variants[s]['shared']['parameters'] if name=='shared' else None
                atr=h.arrays[11][int(p[11]) if p is not None else 2]
            if upper is None:
                upper=full['close']
            score=np.where(active,np.nan_to_num(np.clip((full['close']-upper)/np.maximum(atr,1e-12),0,10)),0.)
            factors[name]['active'][:,j]=active[mask];factors[name]['score'][:,j]=score[mask]
    construction=read('var/research/range-breakout-uso-20261018-v1/construction.json')
    conflicts={frozenset((p,c)) for p,children in construction['overlap_parents'].items() for c in children}
    mappings={};start='2024-01-01'
    def register(name,w,exits=None):
        weights=np.column_stack([w,np.zeros(n)])
        risk=np.column_stack([exits,np.zeros(n,bool)]) if exits is not None else None
        for policy in ('event','monthly'):
            mappings[name+'_'+policy]=dict(weights=weights,indices=np.array(adopted_indices(weights,days.tolist(),start,policy,exits=risk)))
    for name,f in factors.items():
        tapes=portfolio_tapes(a['close'],a['admitted'],symbols,f['score'],f['active'],a['fr25'],conflicts)
        exits=np.vstack([np.zeros((1,m),bool),f['active'][:-1]&~f['active'][1:]])
        for app in ('selection','trading','tilt'):
            register(name+'_'+app,tapes[app],exits if app!='selection' else None)
    for name in ('M1','blend_control'):
        register(name,tapes[name])
    budgets=np.divide(.98*a['admitted'],a['admitted'].sum(axis=1)[:,None],out=np.zeros((n,m)),where=a['admitted'].sum(axis=1)[:,None]>0)
    momentum=np.zeros((n,m),bool);momentum[126:]=a['close'][126:]>a['close'][:-126]
    gate=np.array([choices[s]['validation_score']>0 for s in symbols])
    for name,active in (('selected',factors['selected']['active']),('momentum',momentum)):
        exits=np.vstack([np.zeros((1,m),bool),active[:-1]&~active[1:]])
        register('equal_'+name,budgets*active,exits)
        register('equal_gated_'+name,budgets*active*gate,exits)
    for name,w in (('FR25',a['fr25']),('equal_weight',budgets)):
        weights=np.column_stack([w,np.zeros(n)])
        mappings[name]=dict(weights=weights,indices=np.array(adopted_indices(weights,days.tolist(),start,'monthly')))
    for name,j in (('URTH',m),('BIL',symbols.index('BIL'))):
        weights=np.zeros((n,m+1));weights[:,j]=.98
        mappings[name]=dict(weights=weights,indices=np.array([int(np.flatnonzero(days>=start)[0])-1]))
    dest.mkdir(exist_ok=True)
    np.savez_compressed(dest/'mappings.npz',**{name+'__'+k:v for name,row in mappings.items() for k,v in row.items()})
    write(dest/'receipt.json',dict(parent=str(parent.resolve()),input_sha256=digest(parent/'input_manifest.json'),
        selection_sha256=digest(root/'selection.json'),gate=[s for s,g in zip(symbols,gate,strict=True) if g],
        evaluation_protocol_sha256=digest(root/'evaluation_protocol/manifest.json')))
    manifest(dest,'input_manifest.json',[p for p in dest.iterdir() if p.is_file()])
    runner=Replay(a,recipe,start);results={};(dest/'paths').mkdir(exist_ok=True)
    for name,row in mappings.items():
        for cost in (5,10,20):
            for delay in (0,1):
                path,_,fills=runner.run(row['weights'],row['indices'],cost,delay);key=f'{name}_c{cost}d{delay}'
                results[key]=dict(metrics=summary_path(path,runner),fills=fills,years={str(y):metrics(
                    **{k:path[k] for k in ('nav','turnover','fees','exposure')},days=runner.day_strings,
                    start=f'{y}-01-01',end=f'{y}-12-31') for y in range(2024,2027)})
                if cost==5 and delay==0:
                    np.savez_compressed(dest/'paths'/f'{name}.npz',**path)
        write(dest/'metrics.json',results)
        print(name,results[name+'_c5d0']['metrics'],flush=True)
    manifest(dest,'result_manifest.json',[dest/'metrics.json',*sorted((dest/'paths').glob('*.npz'))])


def native(root):
    check(root);check_evaluator(root);verify(root,'selection_manifest.json')
    from systematic_trading.research.momentum_replay import freeze_usd_bundle,native_parity
    from systematic_trading.config import AppSettings
    if AppSettings().lean_runtime_backend!='native':
        raise ValueError('Native Windows engine required')
    image=read('config/strategy-monitoring.json')['calculation']['image'];choices=read(root/'selection.json')['choices'];jobs=[]
    for s in ('GLD','USO','SOXX'):
        a=asset(s);signal=np.load(root/'evaluation'/s/'signal.npz')['active'];runner=SingleReplay(a,s,'2024-01-01');c=choices[s]
        recipe=dict(id='range_joint_v3_'+s,universeKey=s,universeMembers=[x.model_dump(mode='json') for x in runner.members.values()])
        jobs.append((s,runner,recipe,.98*signal[:,None],transitions(signal,a['days'],'2024-01-01',c['policy']),
                     root/'evaluation'/s/f"{c['variant']}_{c['policy']}.npz"))
    parent=PARENT/'pool';a=dict(np.load(parent/'inputs.npz'));recipe=read(parent/'recipe.json');runner=Replay(a,recipe,'2024-01-01')
    dest=root/'pool';verify(dest,'input_manifest.json');verify(dest,'result_manifest.json');mappings=dict(np.load(dest/'mappings.npz'))
    for name in ('selected_trading_event','equal_selected_event'):
        jobs.append((name,runner,recipe,mappings[name+'__weights'],mappings[name+'__indices'],dest/'paths'/f'{name}.npz'))
    receipts={}
    for name,runner,recipe,weights,indices,path in jobs:
        rows=runner.decisions(weights,indices,0);days=runner.a['days'].tolist()
        decisions={str(d):dict(signal_session=str(d),known_through=days[days.index(str(d))-1],
            targets=[t.model_dump(mode='json') for t in targets]) for d,targets in rows.items()}
        quotes={s:{str(d):{k:str(source[d][s]) for k,source in (('open',runner.open),('close',runner.close),('reference',runner.reference))}
                   for d in runner.days} for s in runner.symbols}
        bundle=root/'native_bundles'/name
        freeze_usd_bundle(bundle,root,recipe,decisions,quotes,runner.day_strings.tolist(),5)
        receipt=native_parity(bundle,root/'native'/name,image,cpus='2');result=read(root/'native'/name/'economic.json')
        error=float(np.max(np.abs(np.array([float(r['nav']) for r in result['nav']])-np.load(path)['nav'])))
        if error>.011:
            raise ValueError('Native divergence '+name)
        receipts[name]=dict(status=receipt['status'],maximum_nav_error_usd=error,manifest_sha256=digest(bundle/'manifest.json'),
                            parity=read(root/'native'/name/'parity.json'))
        write(root/'native_verification.json',receipts);print(name,'native parity',error,flush=True)


def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(str(x))+'</th>' for x in headers)+'</tr></thead><tbody>'+''.join(
        '<tr>'+''.join('<td>'+html.escape(str(x))+'</td>' for x in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def pct(x):
    return '—' if x is None else f'{x:.2%}'


def number(x):
    return '—' if x is None else f'{x:.2f}'


def episode_rows(a,signal,policy):
    from run_joint_breakout import adopt_state
    indices,_=adopt_state(signal,a['days'],'2024-01-01',policy,0)
    change={i+1:bool(signal[i]) for i in indices};entry=None;rows=[]
    for t in range(int(np.flatnonzero(a['days']>='2024-01-01')[0]),len(a['days'])):
        want=change.get(t,entry is not None)
        if want and entry is None:
            entry=t
        elif not want and entry is not None:
            ep=a['open'][entry];peak=float(max(a['close'][entry:t]));xp=a['open'][t]
            rows.append(dict(entry=str(a['days'][entry]),exit=str(a['days'][t]),sessions=t-entry,gross_return=xp/ep-1,
                             peak_gain=peak/ep-1,giveback=xp/peak-1));entry=None
    if entry is not None:
        rows.append(dict(entry=str(a['days'][entry]),exit='open',sessions=len(a['days'])-entry,
            gross_return=float(a['close'][-1]/a['open'][entry]-1),peak_gain=float(max(a['close'][entry:])/a['open'][entry]-1),giveback=None))
    return rows


def inference(differences):
    x=np.column_stack(differences);rng=np.random.default_rng(20261018);n=len(x);samples=[]
    for _ in range(1000):
        ix=((rng.integers(n,size=(n+20)//21)[:,None]+np.arange(21))%n).ravel()[:n];samples.append(x[ix].mean(axis=0))
    samples=np.array(samples);mean=x.mean(axis=0);se=samples.std(axis=0,ddof=1)
    tt=np.divide(samples-mean,se,out=np.zeros_like(samples),where=se>1e-14);q=float(np.quantile(np.max(np.abs(tt),axis=1),.95))
    return dict(mean_annual_log_difference=(mean*252).tolist(),family_lower=((mean-q*se)*252).tolist(),
                family_upper=((mean+q*se)*252).tolist(),critical=q,positive=int(np.sum(mean-q*se>0)))


def report(root):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    check(root);check_evaluator(root);verify(root,'selection_manifest.json');verify(root,'variants_manifest.json')
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':125})
    choices=read(root/'selection.json')['choices'];variants=read(root/'variants.json')
    summary={};rows=[];deltas={'v1':[],'buyhold':[]};trials=0;case_html=[];symbols=sorted(choices);episodes={};parameters={}
    for s in symbols:
        dest=root/'evaluation'/s;verify(dest,'manifest.json');mm=read(dest/'metrics.json');summary[s]=mm
        fit=read(root/'fits'/f'{s}.json');trials+=fit.get('unique_evaluations',0);c=choices[s];sel=mm['rows'][mm['selected_key']];m=sel['metrics']
        path=np.load(dest/f"{c['variant']}_{c['policy']}.npz")['nav'];rr=np.diff(np.log(np.r_[1e6,path]))
        for ctrl in deltas:
            v=np.load(dest/f'{ctrl}_event.npz')['nav'];deltas[ctrl].append(rr-np.diff(np.log(np.r_[1e6,v])))
        bh=mm['rows']['buyhold_event_c5d0']['metrics'];raw=mm['rows'].get('raw_event_c5d0',mm['rows']['shared_event_c5d0'])['metrics']
        rows.append([s,c['variant'],c['policy'],'pass' if c['guard_pass'] else 'FAIL',number(c['validation_score']),pct(m['cagr']),
            number(m['sharpe']),number(m['calmar']),pct(m['max_drawdown']),pct(bh['cagr']),pct(raw['cagr']),pct(m['average_exposure'])])
        parameters[s]=dict(c,decoded=describe(c['parameters']) if c['parameters'] else 'Unchanged '+c['variant'])
        if s not in ('GLD','USO','SOXX'):
            continue
        a=asset(s);sig=dict(np.load(dest/'signal.npz'));mask=a['days']>='2024-01-01';dates=pd.to_datetime(a['days'][mask]);validation=read(root/'validation'/f'{s}.json')
        episodes[s]=episode_rows(a,sig['active'],c['policy']);fig,axes=plt.subplots(3,1,figsize=(13,9),sharex=True,gridspec_kw={'height_ratios':[2,1,1]})
        axes[0].plot(dates,a['close'][mask],color='#293d50',label='Adjusted close',lw=1.2)
        axes[0].plot(dates,np.where(sig['active'][mask],sig['stop'][mask],np.nan),color='#087f8c',label='Planned signal stop',lw=.9)
        axes[0].fill_between(dates,0,1,where=sig['active'][mask],transform=axes[0].get_xaxis_transform(),color='#087f8c',alpha=.13)
        axes[0].set_title(f"{s} | 2024+ | selected in 2023: {c['variant']} / {c['policy']}");axes[0].set_ylabel('Adjusted USD')
        for name,label,color in [(f"{c['variant']}_{c['policy']}",'2023 selection','#087f8c'),('raw_event','Raw IS optimum','#bb6e35'),
                                 ('buyhold_event','Buy & hold','#6c7683'),('v1_event','Original v1','#9b6bb1')]:
            if not (dest/f'{name}.npz').exists():
                continue
            nav=np.load(dest/f'{name}.npz')['nav']/1e6;axes[1].plot(dates,nav,label=label,color=color,lw=1.1)
            axes[2].plot(dates,100*(nav/np.maximum.accumulate(np.r_[1,nav])[1:]-1),color=color,lw=1)
        axes[1].set_ylabel('Net wealth / $1');axes[2].set_ylabel('Drawdown %')
        for ax in axes:
            ax.grid(alpha=.15)
        axes[0].legend(fontsize=8);axes[1].legend(ncol=4,fontsize=8);fig.tight_layout();fig.savefig(PUBLIC/f'{s}.png');plt.close(fig)
        comparison=[]
        for name in (*variants['variants'][s],'v2','v1','buyhold','sma200'):
            r=mm['rows'][name+'_event_c5d0'];z=r['metrics'];val=validation['rows'].get(name+'_event')
            isr=variants['variants'][s].get(name,{}).get('IS',{}).get('scenarios',{}).get('5:0')
            comparison.append([name,pct(isr['metrics']['cagr']) if isr else 'control',number(isr['components']['moderate']) if isr else '—',
                number(val['score']) if val else '—',pct(z['cagr']),number(z['sharpe']),number(z['calmar']),pct(z['max_drawdown']),
                pct(z['average_exposure']),pct(r['risk'][0]),pct(r['risk'][1]),number(r['components']['moderate'])])
        stress=[]
        for clock in ('event','monthly'):
            for cost in (5,10,20):
                for delay in (0,1):
                    z=mm['rows'][f"{c['variant']}_{clock}_c{cost}d{delay}"]['metrics']
                    stress.append([clock,cost,delay,pct(z['cagr']),number(z['sharpe']),pct(z['max_drawdown']),number(z['annual_cost_bps'])])
        seeds=[[r['objective'],r['seed'],r['generations'],r['evaluations'],number(r['score'])] for r in fit.get('trajectories',[])]
        years=[[y,pct(z['cagr']),number(z['sharpe']),pct(z['max_drawdown'])] for y,z in sel['years'].items()]
        ep=[[e['entry'],e['exit'],e['sessions'],pct(e['gross_return']),pct(e['peak_gain']),pct(e['giveback'])] for e in episodes[s]]
        case_html.append(f'<section><h2>{s}: {html.escape(c["variant"])} / {c["policy"]}</h2><p>IS {fit.get("fit_start")}–2022. Validation score {c["validation_score"]:.3f}; return/drawdown guards <b>{"pass" if c["guard_pass"] else "FAIL — descriptive only"}</b>. OOS CAGR {pct(m["cagr"])}, Sharpe {number(m["sharpe"])}, Calmar {number(m["calmar"])} and drawdown {pct(m["max_drawdown"])}; buy-hold CAGR {pct(bh["cagr"])}.</p><img src="{s}.png" alt="{s} signals and net performance">'+
            '<p>Variants below use event timing; the chosen clock is reported above. Utility uses regularized Calmar; reported Calmar uses actual drawdown.</p>'+
            table(['Variant','IS CAGR','IS utility','2023 worst utility','OOS CAGR','Sharpe','Calmar','Max DD','Exposure','Initial stop risk','Trail risk','OOS utility'],comparison)+
            '<details><summary>All selected parameters</summary><pre>'+html.escape(str(parameters[s]['decoded']))+'</pre></details><details><summary>Seeds, chronological returns, friction and episodes</summary>'+
            table(['Objective','Seed','Generations','Evaluations','Best screen score'],seeds)+table(['Year','CAGR','Sharpe','Max DD'],years)+
            table(['Clock','Cost bp/side','Extra delay','CAGR','Sharpe','Max DD','Cost bp/year'],stress)+
            '<p>Episode returns and peak givebacks are gross hindsight diagnostics.</p>'+table(['Entry','Exit','Sessions','Gross return','Peak gain','Exit / peak −1'],ep)+'</details></section>')
    inf={name:inference(v) for name,v in deltas.items()};pm=read(root/'pool/metrics.json');pr=[]
    for k,r in pm.items():
        if k.endswith('_c5d0'):
            z=r['metrics'];pr.append([k[:-5],pct(z['cagr']),number(z['sharpe']),number(z['calmar']),pct(z['max_drawdown']),pct(z['average_exposure']),number(z['annual_turnover']),number(z['annual_cost_bps'])])
    beats={ctrl:sum(summary[s]['rows'][summary[s]['selected_key']]['metrics']['cagr']>summary[s]['rows'][ctrl+'_event_c5d0']['metrics']['cagr'] for s in symbols) for ctrl in ('v1','v2','buyhold','shared','sma200')}
    pnl=[];pool_symbols=np.load(PARENT/'pool/inputs.npz')['symbols'].tolist()+['URTH']
    for name in ('selected_trading_event','equal_selected_event','equal_gated_selected_event','selected_tilt_event'):
        cc=np.load(root/'pool/paths'/f'{name}.npz')['contribution'].sum(axis=0)
        pnl.extend([[name,pool_symbols[j],'$'+f'{cc[j]:,.0f}'] for j in np.argsort(-np.abs(cc))[:6]])
    write(PUBLIC/'summary.json',dict(trials=trials,individuals=len(choices),choices=choices,metrics=summary,portfolio=pm,episodes=episodes,
        inference=dict(symbols=symbols,comparisons=inf),beats=beats,attribution=pnl,native=read(root/'native_verification.json')))
    write(PUBLIC/'selected-parameters.json',parameters)
    write(PUBLIC/'IS-and-validation.json',{s:dict(fit=read(root/'fits'/f'{s}.json'),validation=read(root/'validation'/f'{s}.json')) for s in symbols})
    shutil.copyfile(root/'bounds.json',PUBLIC/'bounds.json');shutil.copyfile(root/'evaluation_protocol/construction.json',PUBLIC/'construction.json')
    doc='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Range breakout · joint optimization</title><style>body{font:16px/1.55 system-ui,sans-serif;background:#f3f6f9;color:#273c50;margin:0}main{max-width:1320px;margin:auto;padding:34px}h1{font-size:35px}section,.card{background:white;padding:24px;border-radius:12px;margin:22px 0}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{padding:9px;text-align:right;border-bottom:1px solid #e0e6eb;white-space:nowrap}th:first-child,td:first-child{text-align:left}th{background:#e9f0f4}img{width:100%;height:auto}pre{white-space:pre-wrap;font-size:13px;padding:14px;background:#edf3f6}details{margin:18px 0}summary{font-weight:650;cursor:pointer}a{color:#087f8c}.tag{color:#087f8c;font-weight:700}</style><main><p class="tag">RESEARCH · AUDITED INPUTS · NO EXECUTION CHANGE</p><h1>Fit the whole breakout lifecycle</h1>'''
    doc+=f'<div class="card"><b>33 joint parameters · {trials:,} unique IS evaluations · 52 supported ETFs</b><p>Numeric fitting ends in2022. Calendar2023 selects the model variant and event/monthly clock. Choices are sealed before2024–October16,2026 evaluation. Selected rules beat v1 CAGR in {beats["v1"]}/52 ETFs, the shared rule in {beats["shared"]}/52 and buy-hold in {beats["buyhold"]}/52. Family-adjusted positive lower bounds: {inf["v1"]["positive"]}/52 versus v1; {inf["buyhold"]["positive"]}/52 versus buy-hold.</p><p>A large IS search shows fitting capacity. Judge its value from separated validation/OOS results, losses, seed dispersion, local stability and simpler controls. This finite search establishes neither a global optimum nor a deployable strategy.</p></div>'
    doc+='''<section><h2>The mathematics</h2><p>At each close, form quantile bands of prior log adjusted prices for candidate lengths L. Qualify a range when its width is small in absolute terms or relative to historical widths, first/last-block median drift is below a fitted fraction of width, and recent volatility is below a fitted multiple of whole-range volatility. Select the longest qualifying L from a fitted subset of21–1,260 sessions. Relative ranks use ranges known at the decision, with at least252 reference observations.</p><p>Freeze upper band U and prior ATR A at the initial crossing of U+bA. Require fitted consecutive closes above the boundary and optional volume confirmation against a frozen trailing-volume reference. Adopt a long target at a later open. Initial stop=entry−kA, optionally raised by a range-band floor. The trail ratchets upward from the highest close using current ATR, entry ATR or percentage distance, after an optional gain threshold. Optional volume/extension heat tightens the trail; optional failed-range and no-follow-through exits can end a trade. All components, horizons and cooldown are jointly searched.</p><pre>U = .45 × Δ capped CAGR / .10
  + .40 × Δ clipped Sharpe
  + .15 × Δ clipped [CAGR / max(.03, |max drawdown|)]
P = .20 × near-buyhold penalty + .20 × oversized-stop penalty
Variants: U, U−.5P, U−P, U−2P, chronological stability, local stability,
          pooled shared rule, 50% continuous-parameter shrinkage.</pre><p>Differences use matched buy-hold. CAGR levels are capped at ±100%, Sharpe and utility-Calmar at ±3; caps affect fitting only. Soft holding penalty rises jointly above85% exposure and85% asset-return correlation. Stop penalties rise above10% initial risk and20% peak-to-stop risk. Thresholds are declared regularization choices, not maximum losses. Planned risk uses only the evaluated period. Stops use completed closes/later opens; monthly adoption can delay exits and gaps can exceed planned risk.</p><p>Mixed integer differential evolution searches all33 dimensions jointly: three objectives × two seeds ×128 population ×30 generations. Thresholds and discrete trades make ordinary gradient descent unsuitable. Finalists use the app's whole-share accountant at5bp,10bp and one extra session. Raw selects base-friction utility; regularized variants select worst-friction utility. Nearby perturbations, chronological blocks, pooled parameters and shrinkage are explicit overfitting controls. Calendar2023 selects frozen variants and clocks, preferring return/drawdown guard passes and simpler near-ties; it does not refit lifecycle coefficients.</p></section>'''
    doc+=''.join(case_html)
    doc+='<section><h2>Full-pool applications</h2><p>2024–October12,2026. Inherited controls use top-six inverse-volatility slots,45% cap, liquidity/duplicate/overlap admission, monthly and target-change timing, and80% FR25 /20% sleeve tilt. FR25 stops at its original cutoff and is repriced on the same batch. Equal-budget sleeves allocate each admitted ETF a fixed share and leave inactive shares in cash; matched momentum uses positive126-session returns. The gated comparison admits names with positive2023 selected utility without redistributing excluded budgets. Neither construction nor portfolio timing is selected from OOS performance.</p>'+table(['Mapping','CAGR','Sharpe','Calmar','Max DD','Exposure','Turnover/year','Cost bp/year'],pr)+'<p>BIL can dominate inverse-volatility allocations and inflate zero-risk-free Sharpe. Equal-budget controls and contributions expose this effect.</p>'+table(['Portfolio','Constituent','Net dollar P&L'],pnl)+'</section>'
    doc+='<section><h2>All supported ETFs</h2>'+table(['ETF','Chosen variant','Clock','2023 guards','2023 utility','OOS CAGR','Sharpe','Calmar','Max DD','BH CAGR','Raw CAGR','Exposure'],rows)+'</section>'
    doc+='''<section><h2>Evidence and limits</h2><p>Cases have15–20 pre-2023 years after warm-up; ETF histories extend back to1993. Stocks were unnecessary to extend history, but independent boom/bust regimes remain much fewer than daily observations. All52 supported ETFs are tested; BWX/XOP retain identity holds. Unsupported early observations are excluded without filling. Inputs reuse v2's pinned audited continuous adjusted-price/raw-volume publication. Retrospective surviving-universe, identity and revised publication-vintage limitations remain.</p><p>The2024+ period was already inspected in earlier studies and motivating examples. This is chronological evaluation of a sealed run, not pristine unseen evidence. Many trials and one validation year can overfit. Paired21-session block intervals adjust across52 comparisons but not every research choice. Cash earns zero; Sharpe uses zero risk-free rate. USO is a futures fund, not spot oil. Price/volume cannot prove a fundamental change. No broker, monitoring, funding or promotion change is made.</p><p>Five Windows-native LEAN runs check the cases and two portfolio constructions against the shared accountant. JIT/Python parity and causal-prefix tests check screening. All friction metrics and primary paths are retained.</p><p><a href="protocol.json">Protocol</a> · <a href="bounds.json">33 bounds</a> · <a href="construction.json">Portfolio recipe</a> · <a href="selected-parameters.json">Chosen parameters</a> · <a href="IS-and-validation.json">IS/seed/local/2023 evidence</a> · <a href="summary.json">All OOS results</a> · <a href="acceptance.json">Verification</a> · <a href="../range-breakout-20261018-v2/index.html">v2</a></p><p>Method: <a href="https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.differential_evolution.html">SciPy differential evolution</a>. Bounds and45/40/15 weights remain declared design choices, not tuned on2024+.</p></section></main></html>'''
    (PUBLIC/'index.html').write_text(doc,encoding='utf-8');print(dict(trials=trials,beats=beats,inference={k:v['positive'] for k,v in inf.items()}),flush=True)


def accept(root):
    check(root);check_evaluator(root);verify(root,'runtime_manifest.json');verify(root,'variants_manifest.json');verify(root,'selection_manifest.json')
    choices=read(root/'selection.json')['choices'];count=0;paths=0
    for s in choices:
        dest=root/'evaluation'/s;verify(dest,'manifest.json');mm=read(dest/'metrics.json');count+=len(mm['rows']);a=asset(s);runner=SingleReplay(a,s,'2024-01-01')
        for p in dest.glob('*.npz'):
            if p.name=='signal.npz':
                continue
            actual=summary_path(dict(np.load(p)),runner);expected=mm['rows'][p.stem+'_c5d0']['metrics']
            for k,v in actual.items():
                if v is not None and abs(v-expected[k])>1e-10:
                    raise ValueError('Metric mismatch '+s+p.stem+k)
            paths+=1
    dest=root/'pool';verify(dest,'input_manifest.json');verify(dest,'result_manifest.json');parent=PARENT/'pool'
    if read(dest/'receipt.json')['input_sha256']!=digest(parent/'input_manifest.json'):
        raise ValueError('Parent pool changed')
    verify(parent,'input_manifest.json');pm=read(dest/'metrics.json');runner=Replay(dict(np.load(parent/'inputs.npz')),read(parent/'recipe.json'),'2024-01-01')
    for p in (dest/'paths').glob('*.npz'):
        actual=summary_path(dict(np.load(p)),runner);expected=pm[p.stem+'_c5d0']['metrics']
        for k,v in actual.items():
            if v is not None and abs(v-expected[k])>1e-10:
                raise ValueError('Pool metric mismatch '+p.stem+k)
    nr=read(root/'native_verification.json')
    if len(nr)!=5:
        raise ValueError('Missing native jobs')
    for name,row in nr.items():
        verify(root/'native_bundles'/name,'manifest.json');verify(root/'native'/name,'artifact_manifest.json')
        if row['status']!='succeeded' or not row['parity']['passed'] or row['maximum_nav_error_usd']>.011:
            raise ValueError('Native failure '+name)
    write(PUBLIC/'acceptance.json',dict(status='pass',input_manifest_sha256=digest(root/'input_manifest.json'),
        variants_sha256=digest(root/'variants_manifest.json'),selection_sha256=digest(root/'selection.json'),
        individuals=len(choices),oos_exact_replays=count,primary_paths_recomputed=paths,pool_replays=len(pm),
        native_checks=len(nr),native_maximum_error_usd=max(r['maximum_nav_error_usd'] for r in nr.values()),
        tests=read(root/'tests.json')))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('stage',choices=('seal_evaluator','pool','native','report','accept'));p.add_argument('--root',type=Path,default=ROOT)
    args=p.parse_args();globals()[args.stage](args.root)


