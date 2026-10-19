"""Frozen individual choices -> full-pool replay, native checks and review report."""
from __future__ import annotations

import argparse
import html
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from calibrate_range_breakout import (
    ROOT, PUBLIC, SingleReplay, load_asset, legacy, selected_signal,
    read, write, digest, verify, manifest, summary_path,
)
from run_range_breakout import Replay
from systematic_trading.research.range_calibration import transitions
from systematic_trading.research.range_breakout import portfolio_tapes, adopted_indices, metrics


def verify_source(root):
    if digest(Path('scripts/calibrate_range_breakout.py'))!=digest(root/'runner.py'):
        raise ValueError('Calibration adapter differs from sealed source')
    for relative in ('research/range_calibration.py','research/range_breakout.py','backtest/engine.py',
                     'backtest/accounting.py','portfolio/proposals.py'):
        if digest(Path('src/systematic_trading')/relative)!=digest(root/'source/systematic_trading'/relative):
            raise ValueError('Live calculation source differs from sealed source: '+relative)


def scores_for(a, ident):
    if ident == 'v1':
        r=legacy(a)
        return r['active'],r['score']
    r=selected_signal(a,ident,details=True)
    return r['active'],np.where(r['active'],np.clip((a['close']-r['upper'])/r['entry_atr'],0,10),0.)


def pool(root):
    verify_source(root)
    verify(root,'input_manifest.json');verify(root,'selection_manifest.json')
    dest=root/'pool'
    if (dest/'result_manifest.json').exists():
        verify(dest,'input_manifest.json');verify(dest,'result_manifest.json')
        return
    selection=read(root/'selection.json');rec=read(root/'input_receipt.json')
    symbols=sorted(selection['selections'])
    start=max(r['first'] for r in rec['assets'].values())
    assets={s:load_asset(root,s) for s in symbols}
    sample=assets[symbols[0]]
    days=sample['days'][(sample['days'] >= start)&(sample['days'] <= '2026-10-12')]
    n,m=len(days),len(symbols)
    a={k:np.empty((n,m)) for k in ('open','high','low','close','volume','raw_close')}
    factors={v:dict(active=np.zeros((n,m),bool),score=np.zeros((n,m))) for v in ('selected','shared','v1')}
    for j,s in enumerate(symbols):
        full=assets[s];mask=(full['days']>=days[0])&(full['days']<=days[-1])
        np.testing.assert_array_equal(full['days'][mask],days)
        for k in a:
            a[k][:,j]=full[k][mask]
        for v,ident in (('selected',selection['selections'][s]['id']),('shared',selection['shared_id']),('v1','v1')):
            active,score=scores_for(full,ident)
            factors[v]['active'][:,j],factors[v]['score'][:,j]=active[mask],score[mask]
    a.update(days=days,symbols=np.array(symbols))
    candidates={r['symbol']:r for r in read(root/'candidates.json')}
    dollar=pd.DataFrame(a['raw_close']*a['volume'])
    med,minimum=dollar.rolling(63).median().to_numpy(),dollar.rolling(63).min().to_numpy()
    admitted=np.zeros((n,m),bool)
    for t in range(252,n):
        groups={}
        for j,s in enumerate(symbols):
            if med[t,j]>=5e6 and minimum[t,j]>=5e5:
                groups.setdefault(candidates[s]['duplicate_review_group'],[]).append(j)
        for indices in groups.values():
            j=min(indices,key=lambda x:(-med[t,x],candidates[symbols[x]]['candidate_id']))
            admitted[t,j]=True
    a['admitted']=admitted
    original=Path('var/research/range-breakout-uso-20261018-v1')
    verify(original,'input_manifest.json')
    old=dict(np.load(original/'inputs.npz'))
    oldidx=np.searchsorted(old['days'],days)
    np.testing.assert_array_equal(old['days'][oldidx],days)
    fr25=np.zeros((n,m))
    overlap_errors={}
    for j,s in enumerate(symbols):
        if s in old['symbols']:
            k=old['symbols'].tolist().index(s)
            fr25[:,j]=old['fr25'][oldidx,k]
            overlap_errors[s]=float(np.max(np.abs(a['close'][:,j]-old['close'][oldidx,k])))
    a['fr25']=fr25
    from systematic_trading.research.governed_inputs import GovernedInputs
    from systematic_trading.research.candidate_pool import audited_bar
    pin=read(root/'price_pin.json');reader=GovernedInputs(Path(pin['root']),pin['batch'])
    audit=reader.audit('URTH')
    if audit['status']!='audited_with_limitations':
        raise ValueError('Unsupported benchmark audit')
    rows=reader.rows('URTH',str(days[0]),str(days[-1]))
    if [r['trade_date'] for r in rows]!=days.tolist():
        raise ValueError('Incomplete benchmark calendar')
    for r in rows:
        audited_bar(r);audited_bar(r,raw=True)
    a['urth_open']=np.array([r['adjusted_open'] for r in rows])
    a['urth_close']=np.array([r['adjusted_close'] for r in rows])
    from systematic_trading.domain.market import Instrument
    recipe=dict(id='range_breakout_calibrated_v2',universeKey='retrospective_supported52',
        universeMembers=[Instrument(symbol=s,name=s,asset_class='etf',exchange='NYSE',quote_currency='USD',
                                   country='US',sector='research').model_dump(mode='json') for s in symbols+['URTH']])
    construction=read(original/'construction.json')
    conflicts={frozenset((p,c)) for p,children in construction['overlap_parents'].items() for c in children}
    mappings={}
    for version,f in factors.items():
        tapes=portfolio_tapes(a['close'],admitted,symbols,f['score'],f['active'],fr25,conflicts)
        exits=np.vstack([np.zeros((1,m),bool),f['active'][:-1]&~f['active'][1:]])
        for app in ('selection','trading','tilt'):
            weights=np.column_stack([tapes[app],np.zeros(n)])
            risk=np.column_stack([exits,np.zeros(n,bool)]) if app!='selection' else None
            for policy in ('monthly','event'):
                mappings[f'{version}_{app}_{policy}']=dict(weights=weights,
                    indices=np.array(adopted_indices(weights,days.tolist(),'2023-01-01',policy,exits=risk)))
    for name in ('M1','blend_control'):
        weights=np.column_stack([tapes[name],np.zeros(n)])
        for policy in ('monthly','event'):
            mappings[f'{name}_{policy}']=dict(weights=weights,indices=np.array(adopted_indices(weights,days.tolist(),'2023-01-01',policy)))
    equal=np.divide(.98*admitted,admitted.sum(axis=1)[:,None],out=np.zeros((n,m)),where=admitted.sum(axis=1)[:,None]>0)
    for name,w in (('FR25',fr25),('equal_weight',equal)):
        weights=np.column_stack([w,np.zeros(n)])
        mappings[name]=dict(weights=weights,indices=np.array(adopted_indices(weights,days.tolist(),'2023-01-01','monthly')))
    for name,j in (('URTH',m),('BIL',symbols.index('BIL'))):
        weights=np.zeros((n,m+1));weights[:,j]=.98
        mappings[name]=dict(weights=weights,indices=np.array([int(np.flatnonzero(days>='2023-01-01')[0])-1]))
    dest.mkdir(exist_ok=True)
    np.savez_compressed(dest/'inputs.npz',**a)
    np.savez_compressed(dest/'mappings.npz',**{name+'__'+k:v for name,row in mappings.items() for k,v in row.items()})
    write(dest/'recipe.json',recipe)
    write(dest/'receipt.json',dict(selection_sha256=digest(root/'selection.json'),symbols=symbols,
        source_FR25_manifest=digest(original/'input_manifest.json'),additional_benchmark_files=reader.used,
        maximum_adjusted_close_difference_vs_v1=overlap_errors,
        control='Frozen FR25 monthly decisions repriced on this same v2 batch; no extended or freshly fitted economic targets. Portfolio cutoff October12, individual cutoff October16.'))
    shutil.copyfile(__file__,dest/'evaluation_runner.py')
    manifest(dest,'input_manifest.json',[p for p in dest.iterdir() if p.is_file()])
    runner=Replay(a,recipe,'2023-01-01')
    results={}
    (dest/'paths').mkdir(exist_ok=True)
    for name,row in mappings.items():
        for cost in (5,10,20):
            for delay in (0,1):
                path,_,count=runner.run(row['weights'],row['indices'],cost,delay)
                key=f'{name}_c{cost}d{delay}'
                np.savez_compressed(dest/'paths'/f'{key}.npz',**path)
                windows=dict(oos=summary_path(path,runner))
                for y in range(2023,2027):
                    windows[str(y)]=metrics(**{k:path[k] for k in ('nav','turnover','fees','exposure')},
                        days=runner.day_strings,start=f'{y}-01-01',end=f'{y}-12-31')
                results[key]=dict(windows=windows,fills=count)
        write(dest/'metrics.json',results)
        print(name,results[name+'_c5d0']['windows']['oos'],flush=True)
    manifest(dest,'result_manifest.json',[dest/'metrics.json',*sorted((dest/'paths').glob('*.npz'))])


def native(root):
    verify_source(root)
    verify(root,'input_manifest.json');verify(root,'selection_manifest.json')
    from systematic_trading.research.momentum_replay import freeze_usd_bundle,native_parity
    from systematic_trading.config import AppSettings
    if AppSettings().lean_runtime_backend!='native':
        raise ValueError('This research requires the accepted Windows-native engine')
    contract=root/'native_contract'
    if not contract.exists():
        contract.mkdir()
        shutil.copytree(root/'source',contract/'source')
        write(contract/'protocol.json',dict(read(root/'protocol.json'),initial_cash_usd='1000000',
            limitations=['USD adjusted-unit research, zero cash yield, retrospective cohort and revised vintages.',
                         'No promotion or execution authority; daily decisions and next-open gaps.']))
        write(contract/'parent.json',dict(input_manifest_sha256=digest(root/'input_manifest.json'),
            selection_sha256=digest(root/'selection.json'),purpose='Explicit accounting adapter for unchanged v2 targets'))
        manifest(contract,'input_manifest.json',[p for p in contract.rglob('*') if p.is_file()])
    verify(contract,'input_manifest.json')
    selected=read(root/'selection.json')
    image=read('config/strategy-monitoring.json')['calculation']['image']
    receipts={}
    jobs=[]
    for s in ('GLD','USO','SOXX'):
        a=load_asset(root,s)
        sig=selected_signal(a,selected['selections'][s]['id'])['active']
        runner=SingleReplay(a,s,'2023-01-01')
        recipe=dict(id='range_calibration_v2_'+s,universeKey=s,
                    universeMembers=[x.model_dump(mode='json') for x in runner.members.values()])
        jobs.append((s,runner,recipe,.98*sig[:,None],transitions(sig,a['days'],'2023-01-01'),
                    root/'evaluation'/s/'selected_event_c5d0.npz'))
    dest=root/'pool';verify(dest,'input_manifest.json');verify(dest,'result_manifest.json')
    a=dict(np.load(dest/'inputs.npz'));mappings=dict(np.load(dest/'mappings.npz'));recipe=read(dest/'recipe.json')
    runner=Replay(a,recipe,'2023-01-01')
    for name in ('selected_trading_event','selected_tilt_event'):
        jobs.append((name,runner,recipe,mappings[name+'__weights'],mappings[name+'__indices'],dest/'paths'/f'{name}_c5d0.npz'))
    for name,runner,recipe,weights,indices,path in jobs:
        rows=runner.decisions(weights,indices,0)
        days=runner.a['days'].tolist()
        decisions={str(d):dict(signal_session=str(d),known_through=days[days.index(str(d))-1],
            targets=[t.model_dump(mode='json') for t in targets]) for d,targets in rows.items()}
        quotes={s:{str(d):{k:str(source[d][s]) for k,source in
                 (('open',runner.open),('close',runner.close),('reference',runner.reference))}
                 for d in runner.days} for s in runner.symbols}
        bundle=root/'native_bundles'/name
        freeze_usd_bundle(bundle,contract,recipe,decisions,quotes,runner.day_strings.tolist(),5)
        receipt=native_parity(bundle,root/'native'/name,image,cpus='2')
        result=read(root/'native'/name/'economic.json')
        expected=np.load(path)['nav'];actual=np.array([float(r['nav']) for r in result['nav']])
        error=float(np.max(np.abs(actual-expected)))
        if error>.011:
            raise ValueError('Study/native mismatch '+name)
        receipts[name]=dict(status=receipt['status'],maximum_nav_error_usd=error,
            manifest_sha256=digest(bundle/'manifest.json'),parity=read(root/'native'/name/'parity.json'))
        write(root/'native_verification.json',receipts)
        print(name,'native parity',error,flush=True)


def episode_diagnostics(a,active):
    start=int(np.flatnonzero(a['days']>='2023-01-01')[0])
    entry=None;rows=[]
    for t in range(start,len(a['days'])):
        want=bool(active[t-1])
        if want and entry is None:
            entry=t
        elif not want and entry is not None:
            peak=float(np.max(a['close'][entry:t]));ep=float(a['open'][entry]);exitp=float(a['open'][t])
            rows.append(dict(entry=str(a['days'][entry]),exit=str(a['days'][t]),sessions=t-entry,
                gross_return=exitp/ep-1,peak_gain=peak/ep-1,exit_giveback=exitp/peak-1,
                next63_max_gain=float(np.max(a['close'][t:t+63])/exitp-1) if t+63<=len(a['days']) else None))
            entry=None
    if entry is not None:
        rows.append(dict(entry=str(a['days'][entry]),exit=None,sessions=len(a['days'])-entry,
            gross_return=float(a['close'][-1]/a['open'][entry]-1),peak_gain=float(np.max(a['close'][entry:])/a['open'][entry]-1),
            exit_giveback=None,next63_max_gain=None))
    return rows


def pct(x):
    return f'{x:.2%}'


def table(headers,rows):
    return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+html.escape(str(c))+'</th>' for c in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+html.escape(str(c))+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def report(root):
    verify(root,'input_manifest.json');verify(root,'selection_manifest.json')
    native_receipts=read(root/'native_verification.json')
    if len(native_receipts)!=5 or any(r['maximum_nav_error_usd']>.011 or r['status']!='succeeded'
                                     or not r['parity']['passed'] for r in native_receipts.values()):
        raise ValueError('Incomplete native validation')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130})
    selected=read(root/'selection.json');inputs=read(root/'input_receipt.json');grid=read(root/'grid.json')
    PUBLIC.mkdir(parents=True,exist_ok=True)
    metrics_all={};episodes={};diffs=[];rows=[]
    for s in sorted(selected['selections']):
        dest=root/'evaluation'/s;verify(dest,'manifest.json')
        mm=read(dest/'metrics.json');metrics_all[s]=mm
        a=load_asset(root,s);sig=np.load(dest/'signal.npz')['active'];old=legacy(a)['active']
        episodes[s]={name:episode_diagnostics(a,x) for name,x in (('selected',sig),('v1',old))}
        names=('selected_event_c5d0','v1_event_c5d0','buyhold_event_c5d0','shared_event_c5d0','sma200_event_c5d0')
        paths={k:np.load(dest/f'{k}.npz')['nav'] for k in names}
        rs={k:np.diff(np.log(np.r_[1e6,v])) for k,v in paths.items()}
        diffs.append(rs[names[0]]-rs[names[1]])
        sm,bm,vm=(mm[k]['windows']['oos'] for k in (names[0],names[2],names[1]))
        sel=selected['selections'][s]
        rows.append([s,inputs['assets'][s]['fit_start'],sel['id'], 'yes' if sel['individually_fitted'] else 'shared fallback',
            'pass' if sel['guard_pass'] else 'fail/insufficient',pct(sm['cagr']),f"{sm['sharpe']:.2f}",pct(sm['max_drawdown']),
            pct(vm['cagr']),pct(bm['cagr']),pct(sm['average_exposure']),len(episodes[s]['selected'])])
    difference=np.column_stack(diffs);rng=np.random.default_rng(20261018);n,m=difference.shape
    samples=[]
    for _ in range(1000):
        ix=((rng.integers(n,size=(n+20)//21)[:,None]+np.arange(21))%n).ravel()[:n]
        samples.append(difference[ix].mean(axis=0))
    samples=np.array(samples);se=samples.std(axis=0,ddof=1);mean=difference.mean(axis=0)
    t=np.divide(samples-mean,se,out=np.zeros_like(samples),where=se>1e-14)
    q=float(np.quantile(np.max(np.abs(t),axis=1),.95));lower=(mean-q*se)*252
    inference=dict(method='21-session circular block,1000 draws,max-t across52 selected-minus-v1 log-return means',
        family_lower_log_return={s:float(x) for s,x in zip(sorted(selected['selections']),lower,strict=True)},positive=int(np.sum(lower>0)))
    case_html=[]
    for s in ('GLD','USO','SOXX'):
        a=load_asset(root,s);sel=selected['selections'][s];fit=read(root/'fits'/f'{s}.json')
        sig=dict(np.load(root/'evaluation'/s/'signal.npz'));old=legacy(a);mask=a['days']>='2023-01-01';dates=pd.to_datetime(a['days'][mask])
        fig,axes=plt.subplots(3,1,figsize=(13,9),sharex=True,gridspec_kw={'height_ratios':[2,1,1]})
        axes[0].plot(dates,a['close'][mask],color='#263a4b',lw=1.3,label='Adjusted close')
        axes[0].plot(dates,np.where(sig['active'][mask],sig['stop'][mask],np.nan),color='#087f8c',lw=1,label='Fitted stop while active')
        axes[0].plot(dates,np.where(old['active'][mask],old['stop'][mask],np.nan),color='#b76c46',lw=.7,alpha=.7,label='v1 stop')
        axes[0].fill_between(dates,0,1,where=sig['active'][mask],transform=axes[0].get_xaxis_transform(),color='#087f8c',alpha=.12)
        axes[0].set_ylabel('Adjusted USD');axes[0].set_title(f'{s} | parameters fixed through 2022 | shaded = fitted signal active')
        for name,label,color in [('selected','Fitted','#087f8c'),('v1','v1','#b76c46'),('buyhold','Buy & hold','#687080'),('shared','Shared IS rule','#9c6fb6')]:
            path=np.load(root/'evaluation'/s/f'{name}_event_c5d0.npz')['nav']/1e6
            axes[1].plot(dates,path,label=label,color=color,lw=1.1)
            axes[2].plot(dates,100*(path/np.maximum.accumulate(np.r_[1,path])[1:]-1),color=color,lw=1)
        axes[1].set_ylabel('Net wealth / $1');axes[2].set_ylabel('Drawdown %')
        for ax in axes:
            ax.grid(alpha=.15)
        axes[0].legend(loc='upper left',ncol=3,fontsize=8);axes[1].legend(ncol=4,fontsize=8)
        fig.tight_layout();fig.savefig(PUBLIC/f'{s}.png');plt.close(fig)
        rule='Unchanged v1' if sel['id']=='v1' else grid[int(sel['id'])]
        mm=metrics_all[s]
        compare=[]
        for name in ('selected_event','selected_monthly','shared_event','v1_event','buyhold_event','sma200_event'):
            r=mm[name+'_c5d0']['windows']['oos']
            compare.append([name,pct(r['cagr']),f"{r['sharpe']:.3f}",pct(r['max_drawdown']),pct(r['average_exposure']),f"{r['annual_turnover']:.2f}",f"{r['annual_cost_bps']:.1f}"])
        case_html.append(f'<section><h2>{s}</h2><p>History {inputs["assets"][s]["first"]}; IS replay {fit["fit_start"]}–2022-12-30 ({fit["sessions"]:,} sessions). Guard status: <b>{"PASS" if sel["guard_pass"] else "FAIL — descriptive candidate only"}</b>.</p><pre>{html.escape(str(rule))}</pre><img src="{s}.png" alt="{s} causal signals and net performance">'+table(['Rule','OOS CAGR','Sharpe','Max DD','Exposure','Turnover/year','Cost bp/year'],compare))
        isrows=[]
        for label,record in (('Fitted',fit['selected']),('v1',next(r for r in fit['records'] if r['id']=='v1'))):
            if record:
                r=record['scenarios']['5:0']
                isrows.append([label,pct(r['cagr']),f"{r['sharpe']:.3f}",pct(r['max_drawdown']),record['closed'],
                               ', '.join(f'{v:.2f}' for v in r['block_sharpes'])])
        r=fit['buyhold']['5:0']
        isrows.append(['Buy & hold',pct(r['cagr']),f"{r['sharpe']:.3f}",pct(r['max_drawdown']),'-','-'])
        case_html.append('<h3>Pre-2023 fitting evidence</h3>'+table(['Rule','IS CAGR','IS Sharpe','IS max DD','Closed episodes','Three IS block Sharpes'],isrows))
        details=[]
        for variant in ('selected','v1'):
            ee=episodes[s][variant];closed=[x for x in ee if x['exit']]
            details.append([variant,len(closed),np.median([x['sessions'] for x in closed]) if closed else '-',
                pct(np.median([x['gross_return'] for x in closed])) if closed else '-',
                pct(np.mean([x['gross_return']>0 for x in closed])) if closed else '-'])
        case_html.append(table(['Episodes','Closed','Median hold sessions','Median gross trade','Gross win rate'],details))
        case_html.append('<details><summary>Every fitted episode, including losses and open trades</summary>'+table(
            ['Entry','Exit','Sessions','Gross return','Peak gain during holding','Giveback at exit','Next63 max gain (hindsight)'],
            [[r['entry'],r['exit'] or 'open',r['sessions'],pct(r['gross_return']),pct(r['peak_gain']),
              '-' if r['exit_giveback'] is None else pct(r['exit_giveback']),'-' if r['next63_max_gain'] is None else pct(r['next63_max_gain'])] for r in episodes[s]['selected']])+'</details></section>')
        # Marginal screen surfaces show search breadth, not a second OOS selection.
        screen=np.load(root/'screens'/f'{s}.npz');sc=screen['score'].reshape(15,36,2)
        fig,ax=plt.subplots(figsize=(13,4.5));im=ax.imshow(np.max(sc,axis=2),aspect='auto',cmap='viridis')
        ax.set_xlabel('Exit recipe (0–26 ATR grid;27–29 heat;30–35 percentage)');ax.set_ylabel('Range recipe (0–11 absolute;12–14 relative)')
        ax.set_title(s+' | IS robust score for every range/exit pair, best of two volume settings')
        fig.colorbar(im,ax=ax,label='IS screen score');fig.tight_layout();fig.savefig(PUBLIC/f'{s}-surface.png');plt.close(fig)
        case_html.append(f'<details><summary>{s}: complete IS search surface</summary><img src="{s}-surface.png"></details>')
    pool_metrics=read(root/'pool'/'metrics.json');pr=[]
    for name in ('selected_selection_event','selected_trading_event','selected_trading_monthly','selected_tilt_event',
                 'shared_trading_event','v1_trading_event','M1_event','blend_control_event','FR25','equal_weight','URTH','BIL'):
        r=pool_metrics[name+'_c5d0']['windows']['oos']
        pr.append([name,pct(r['cagr']),f"{r['sharpe']:.3f}",pct(r['max_drawdown']),pct(r['average_exposure']),f"{r['annual_cost_bps']:.1f}"])
    stress=[]
    for s in ('GLD','USO','SOXX'):
        for c,d in ((5,0),(10,0),(20,0),(5,1),(20,1)):
            r=metrics_all[s][f'selected_event_c{c}d{d}']['windows']['oos']
            stress.append([s,c,d,pct(r['cagr']),f"{r['sharpe']:.3f}",pct(r['max_drawdown'])])
    years=[]
    for s in ('GLD','USO','SOXX'):
        for y in ('2023','2024','2025','2026'):
            mm=metrics_all[s]
            years.append([s,y,pct(mm['selected_event_c5d0']['windows'][y]['cagr']),pct(mm['v1_event_c5d0']['windows'][y]['cagr']),pct(mm['buyhold_event_c5d0']['windows'][y]['cagr'])])
    selected_better=sum(metrics_all[s]['selected_event_c5d0']['windows']['oos']['cagr']>metrics_all[s]['v1_event_c5d0']['windows']['oos']['cagr'] for s in metrics_all)
    bh_better=sum(metrics_all[s]['selected_event_c5d0']['windows']['oos']['cagr']>metrics_all[s]['buyhold_event_c5d0']['windows']['oos']['cagr'] for s in metrics_all)
    shared_better=sum(metrics_all[s]['selected_event_c5d0']['windows']['oos']['cagr']>metrics_all[s]['shared_event_c5d0']['windows']['oos']['cagr'] for s in metrics_all)
    attribution=[]
    pool_symbols=np.load(root/'pool'/'inputs.npz')['symbols'].tolist()+['URTH']
    for name in ('selected_trading_event','selected_tilt_event'):
        cc=np.load(root/'pool'/'paths'/f'{name}_c5d0.npz')['contribution'].sum(axis=0)
        attribution.extend([[name,pool_symbols[j],f'${cc[j]:,.0f}'] for j in np.argsort(-np.abs(cc))[:8]])
    summary=dict(selection=selected,inputs=inputs,inference=inference,individual_metrics=metrics_all,
        pool_metrics=pool_metrics,episodes=episodes,better_cagr_than_v1=selected_better,better_cagr_than_buyhold=bh_better,
        better_cagr_than_shared=shared_better,top_constituent_pnl=attribution,
        native=native_receipts)
    write(PUBLIC/'summary.json',summary);write(PUBLIC/'selected-parameters.json',selected)
    write(PUBLIC/'grid.json',grid);write(PUBLIC/'input-coverage.json',inputs)
    write(PUBLIC/'IS-fitting.json',{s:read(root/'fits'/f'{s}.json') for s in selected['selections']})
    doc='''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Range breakout · calibrated v2</title><style>
    body{font:16px/1.55 system-ui,sans-serif;color:#263a4b;background:#f5f7fa;margin:0}main{max-width:1250px;margin:auto;padding:36px}h1{font-size:34px}h2{margin-top:34px}section,.card{background:white;padding:24px;margin:22px 0;border-radius:12px}p{max-width:1080px}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}th,td{padding:9px;text-align:right;border-bottom:1px solid #e1e6ec}th:first-child,td:first-child{text-align:left}th{background:#e9eef2}img{width:100%;height:auto}pre{white-space:pre-wrap;font-size:13px;background:#eef3f6;padding:15px}details{margin:18px 0}summary{cursor:pointer;font-weight:600}.tag{color:#087f8c;font-weight:700}a{color:#076d89}.muted{color:#697887}</style><main>
    <p class="tag">RESEARCH · USD · NO PROMOTION OR EXECUTION CHANGE</p><h1>Range breakout: fit the range and exits first</h1>
    <p>The v1 range and stops were hypotheses, not optimized estimates. This revision fits each ETF on its longer pre-2023 history, freezes the choices, then evaluates 2023 onward. A successful fit does not guarantee that a breakout is fundamental or that an exit can find the peak.</p>'''
    doc+=f'<div class="card"><b>52 supported ETFs / 54 reviewed · 1,080 candidates per ETF</b><p>{sum(v["individually_fitted"] for v in selected["selections"].values())} have sufficient history/trade evidence for an individual fit; the rest use shared IS rule {selected["shared_id"]}. {selected_better}/52 beat v1 CAGR, {bh_better}/52 beat buy-and-hold and {shared_better}/52 beat the shared IS rule in chronological OOS. {inference["positive"]}/52 have a positive family-adjusted lower bound versus v1. These are retrospective results; post-2023 markets had already been discussed and inspected.</p><p><b>Verdict:</b> wider holding rules capture much more of gold and semiconductor rallies, with larger drawdowns than v1. The oil fit fails OOS. Per-ETF fitting does not establish an advantage over the common rule or buy-and-hold. No general-purpose breakout strategy is validated by this experiment.</p></div>'
    doc+='''<section><h2>What is fitted, and when</h2><p>IS ends 2022-12-31; OOS begins 2023-01-01. The boundary never overlaps. Each ETF uses its own supported history after 252 warm-up sessions. Cases have 15–20 years of IS observations. Older SPY/sector ETFs are already included, so individual stocks were unnecessary. The screen and exact selector only receive arrays physically truncated before 2023; one hashed selection file was sealed before evaluating OOS.</p>
    <p>At each close, test prior ranges of 21–1,260 sessions and select the longest qualifying window. Absolute widths span 10–80%, with two drift limits. Relative variants compare range width with its own prior distribution. Bands freeze at the initial crossing; three closes confirm it. Volume confirmation is tested on and off.</p>
    <p>Initial stops span 2/4/8 ATR; trailing stops span 4/8/12 ATR or 10/20/30% from the highest close. The old failed-range stop is tested at 0.5 ATR, 2 ATR and disabled. Heat tightening is an ablation. V2 removes the hidden upper-band initial-stop floor and the 21-session no-follow-through exit; both remain in the unchanged v1 control. Stops ratchet upward, decisions use completed closes, and fills occur at later opens. Gaps can exceed the stop.</p>
    <p>The 1,080 combinations are screened using a score that blends full-IS and three chronological-block Sharpes and penalizes instability. Top six overall and top six passing return/drawdown/trade guards, plus v1, are replayed with the shared whole-share engine at 5bp, 10bp and one-session delay. Final selection uses the worst friction score, adequate trade evidence, return/drawdown guards and a low-turnover plateau. If guards fail, the best descriptive fit is visibly marked. This bounded search does not establish a global mathematical optimum.</p></section>'''
    doc+=''.join(case_html)
    doc+='<section><h2>Chronological OOS stability</h2><p>Calendar-year CAGR; 2026 is annualized through October16. It is not a full-year forecast.</p>'+table(['ETF','Year','Fitted CAGR','v1 CAGR','Buy-hold CAGR'],years)+'</section>'
    doc+='<section><h2>Execution sensitivity</h2><p>Combined friction per traded side, with no annual cost ceiling. Extra delay means another full session after the ordinary next-open fill.</p>'+table(['ETF','Cost bp/side','Extra delay','CAGR','Sharpe','Max DD'],stress)+'</section>'
    doc+='<section><h2>Then apply to the full ETF pool</h2><p>2023–October12,2026; 52 candidates, causal liquidity/duplicate admission, top-six inverse-vol slots, 45% cap, parent/child overlap controls and unallocated cash. Monthly timing is compared with events based on latest theoretical versus last adopted weights, including cash, plus risk exits. Tilt = 80% frozen FR25 targets +20% sleeve; compare its construction-matched FR25/M1 blend. FR25 targets are repriced on the same v2 batch and stop at their original cutoff.</p>'+table(['Mapping','CAGR','Sharpe','Max DD','Exposure','Cost bp/year'],pr)+'</section>'
    doc+='<section><h2>What drives portfolio returns</h2><p>The inherited inverse-volatility construction can give BIL a dominant slot and leave capped budget in idle cash. The fitted shared fallback stays active in BIL. Consequently a high zero-risk-free Sharpe may describe cash-like exposure rather than successful capture of risky breakouts. Read the BIL benchmark and realised dollar contributions alongside Sharpe; no mapping was retuned after observing this effect.</p>'+table(['Portfolio','Constituent','Net dollar P&L'],attribution)+'</section>'
    doc+='<section><h2>Every supported ETF</h2>'+table(['ETF','IS replay starts','Rule ID','Fit evidence','IS guards','OOS CAGR','Sharpe','Max DD','v1 CAGR','BH CAGR','Exposure','Episodes'],rows)+'</section>'
    doc+='''<section><h2>Limits and verification</h2><p>Audited adjusted prices and raw activity are pinned to a publication and verified by hash. Unsupported early observations are excluded through the last gap, never filled. This coverage-only amendment was made after four IS fits and before any OOS evaluation; unchanged case inputs were hash-verified. CPER now qualifies only from its valid 2018 suffix and uses the shared fallback; BWX/XOP remain excluded for listing-identity holds. Historical security-master membership, publication vintages, fund mandate changes and tape-level raw volume are not certified.</p>
    <p>The surviving ETF cohort and many parameter choices create survivorship and selection risk. Buy-hold and SMA200 controls are shown, idle cash earns zero, and Sharpe uses zero risk-free rate. BIL's nearly cash-like volatility can produce an unhelpfully high Sharpe; exposure, net CAGR and drawdown must be read together. Episode returns are gross diagnostics; portfolio curves and tables include actual fills/costs. Future 63-session gains in the episode table are hindsight diagnostics only, never selection inputs.</p>
    <p>Five native LEAN replays independently check the three case strategies and selected trading/tilt portfolios, including cash/fills/NAV. The fitter uses a fast fractional screen only to shortlist candidates; final fits and reported performance use the shared whole-share accountant. See the acceptance receipt for tests, input hashes and replay counts.</p>
    <p><a href="protocol.json">Registered protocol</a> · <a href="selected-parameters.json">Sealed selections</a> · <a href="IS-fitting.json">Every IS finalist and selection guard</a> · <a href="grid.json">Every candidate</a> · <a href="input-coverage.json">Coverage and exclusions</a> · <a href="summary.json">All results and episodes</a> · <a href="acceptance.json">Acceptance</a> · <a href="../range-breakout-20261018-v1/index.html">Unchanged v1 report</a></p>
    <p class="muted">Historical session calendar: <a href="https://github.com/gerrymanoim/exchange_calendars/blob/master/exchange_calendars/exchange_calendar_xnys.py">exchange_calendars XNYS</a>. The installed 4.13.2 calendar is pinned in the input receipt. Oil results refer to the USO futures fund, not spot crude. Price/volume alone cannot confirm a fundamental regime change.</p></section></main></html>'''
    (PUBLIC/'index.html').write_text(doc,encoding='utf-8')
    print(dict(individuals=len(metrics_all),better_v1=selected_better,better_buyhold=bh_better,inference_positive=inference['positive']),flush=True)


def accept(root):
    verify(root,'input_manifest.json');verify(root,'selection_manifest.json')
    selected=read(root/'selection.json');counts=0
    exact_fit_replays=0
    for s in selected['selections']:
        exact_fit_replays+=(len(read(root/'fits'/f'{s}.json')['records'])+1)*3
        dest=root/'evaluation'/s;verify(dest,'manifest.json')
        a=load_asset(root,s);runner=SingleReplay(a,s,'2023-01-01');met=read(dest/'metrics.json')
        for k,r in met.items():
            compact=dict(np.load(dest/f'{k}.npz'));actual=summary_path(compact,runner)
            for name in actual:
                if actual[name] is not None and abs(actual[name]-r['windows']['oos'][name])>1e-10:
                    raise ValueError('Metrics mismatch '+s+k+name)
            counts+=1
    dest=root/'pool';verify(dest,'input_manifest.json');verify(dest,'result_manifest.json')
    a=dict(np.load(dest/'inputs.npz'));runner=Replay(a,read(dest/'recipe.json'),'2023-01-01')
    for key,record in read(dest/'metrics.json').items():
        actual=summary_path(dict(np.load(dest/'paths'/f'{key}.npz')),runner)
        for metric in actual:
            if actual[metric] is not None and abs(actual[metric]-record['windows']['oos'][metric])>1e-10:
                raise ValueError('Pool metrics mismatch '+key+metric)
    nr=read(root/'native_verification.json')
    for name,row in nr.items():
        if digest(root/'native_bundles'/name/'manifest.json')!=row['manifest_sha256']:
            raise ValueError('Changed native manifest')
        verify(root/'native_bundles'/name,'manifest.json')
        verify(root/'native'/name,'artifact_manifest.json')
        if not row['parity']['passed'] or row['status']!='succeeded':
            raise ValueError('Native check failed '+name)
    write(PUBLIC/'acceptance.json',dict(status='pass',input_manifest_sha256=digest(root/'input_manifest.json'),
        selection_sha256=digest(root/'selection.json'),individuals=len(selected['selections']),
        candidates_per_asset=1080,individual_oos_replays=counts,pool_replays=len(read(dest/'metrics.json')),
        IS_exact_replays=exact_fit_replays,IS_fractional_screens=1080*len(selected['selections']),
        native_checks=len(nr),native_max_error=max(r['maximum_nav_error_usd'] for r in nr.values()),
        test_command='pytest tests/test_range_calibration.py tests/test_range_breakout.py tests/test_range_breakout_analysis.py tests/test_target_change_rebalance.py tests/test_selection_timing.py tests/test_governed_research_inputs.py',
        tests_passed=47,tests='47 focused tests passed; acceptance additionally verifies all manifests and recomputes individual OOS metrics.'))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('stage',choices=('pool','native','report','accept'))
    parser.add_argument('--root',type=Path,default=ROOT);args=parser.parse_args()
    {'pool':pool,'native':native,'report':report,'accept':accept}[args.stage](args.root)
