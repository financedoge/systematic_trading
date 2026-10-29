"""Inspectable multiscale/HMM comparisons, causal daily levels and probability paths."""
import csv
import gzip
import json
from pathlib import Path
import sys

import numpy as np

import research_latent_slope as study

NAMES={'slope':'A · Continuous slopes, uniform exits','switch':'B · Fast HMM, uniform exits','context':'C · Fast HMM, trend-aware exits'}

FOCUS=('GLD','CORN','EWA','TLT','MCHI','IAT','SLV','SOXX')


def weakest_training_choice(rows,era):
    return min((r for r in rows if r['era']==era and r['variant']=='selected'
                and r['symbol']!='BIL' and r['cost_bp']==5 and r['delay']==0),
               key=lambda r:(r['cumulative'],r['symbol']))


def pack_charts(charts):
    """Share identical price/filter arrays; keep model-specific paths intact."""
    shared_fields=('days','close','volume','baseline','buyhold','slow_up','slow_down',
        'slow_slope','fast_slope','slow_lo','slow_hi','fast_lo','fast_hi',
        'slow_level','fast_level','context','old_trades','evaluation_start')
    bases,paths={},{}
    for key,c in charts.items():
        base=key.rsplit('_',1)[0]
        shared={k:c[k] for k in shared_fields}
        if base in bases and bases[base]!=shared:raise ValueError('Shared chart paths differ')
        bases[base]=shared
        paths[key]={k:v for k,v in c.items() if k not in shared_fields}
    return bases,paths


def summarize(rows,ports):
    lookup={(r['symbol'],r['era'],r['variant'],r['cost_bp'],r['delay']):r for r in rows}
    families=[]
    for era,*_ in study.ERAS:
        for variant in study.VARIANTS:
            for cost,delay in study.FRICTIONS:
                rr=[r for r in rows if r['era']==era and r['variant']==variant and r['cost_bp']==cost and r['delay']==delay and r['symbol']!='BIL']
                eligible=[r for r in rr if r['training_evidence']]
                old=[lookup[r['symbol'],era,'baseline',cost,delay] for r in eligible]
                gain=np.array([r['cagr']-b['cagr'] for r,b in zip(eligible,old,strict=True)])
                dd=np.array([r['maxdd']-b['maxdd'] for r,b in zip(eligible,old,strict=True)])
                sharpe=float(np.median([r['sharpe'] for r in eligible])-np.median([r['sharpe'] for r in old])) if old else None
                qgain=float(np.quantile([r['cagr'] for r in eligible],.25)-np.quantile([r['cagr'] for r in old],.25)) if old else None
                guard=float(np.mean((gain>=-.01)&(dd>=-.02))) if len(old) else 0.
                families.append(dict(era=era,variant=variant,cost_bp=cost,delay=delay,cases=len(rr),eligible=len(eligible),
                    positive=sum(r['cumulative']>0 for r in rr),negative=sum(r['cumulative']<0 for r in rr),
                    median_cagr=float(np.median([r['cagr'] for r in rr])),median_sharpe=float(np.median([r['sharpe'] for r in rr])),
                    improves_cagr=sum(r['cagr']>lookup[r['symbol'],era,'baseline',cost,delay]['cagr']+1e-10 for r in rr),
                    median_sharpe_gain=sharpe,lower_quartile_cagr_gain=qgain,guard_fraction=guard,
                    passed=bool(old and sharpe>0 and qgain>0 and guard>=.9)))
    ix={(r['era'],r['scenario'],r['cost_bp'],r['delay']):r for r in ports};gates=[]
    for r in ports:
        if not r['scenario'].startswith('selected_'):continue
        names=[r['scenario'].replace('selected_','baseline_'),'FR25' if r['era']=='late' else 'momentum_'+r['scenario'].rsplit('_',1)[1]]
        checks=[]
        for name in names:
            b=ix[r['era'],name,r['cost_bp'],r['delay']]
            checks.append(dict(reference=name,passed=r['sharpe']>b['sharpe']+1e-10 and r['cagr']>=b['cagr']-.01 and r['max_drawdown']>=b['max_drawdown']-1e-12))
        gates.append(dict(era=r['era'],scenario=r['scenario'],cost_bp=r['cost_bp'],delay=r['delay'],comparisons=checks,passed=all(x['passed'] for x in checks)))
    return dict(families=families,portfolio_gates=gates)


def chart_data(f, sim, old, first, era):
    lo=int(np.flatnonzero(f.days>=np.datetime64(first))[0])
    start=int(np.flatnonzero(f.days>=np.datetime64('2021-01-01' if era=='late' else '2020-01-01'))[0])
    def series(a, hide=True):
        a=np.asarray(a,float).copy()
        if hide:a[:lo]=np.nan
        return np.round(a[start:],7)
    nav=lambda a:100*a/a[lo-1]
    def trades(source):
        return [dict(entry=str(f.days[e['entry_index']]),exit=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None,
                     entry_index=e['entry_index']-start,exit_index=e['exit_index']-start if e['exit_index'] is not None else None,
                     entry_price=e['entry'],exit_price=e['exit_price'],reason=e['exit_reason'],
                     entry_signal=str(f.days[e['entry_signal']]),exit_signal=str(f.days[e['exit_signal']]) if e['exit_signal'] is not None else None,
                     carried=e['entry_index']<lo,
                     net_return=float((e['exit_price'] if e['exit_price'] is not None else f.close[-1])/e['entry']*(.9995 if e['exit_price'] is not None else 1)/1.0005-1))
                for e in source['episodes'] if (e['exit_index'] is None or e['exit_index']>=lo)]
    return dict(days=f.days[start:].astype(str),close=series(f.close,False),volume=series(f.volume,False),stop=series(sim['stop']),
                nav=series(nav(sim['nav'])),baseline=series(nav(old['nav'])),buyhold=series(100*f.close/f.close[lo-1]),
                fast_up=series(sim['fast_probability'][:,2]),fast_down=series(sim['fast_probability'][:,0]),
                slow_up=series(sim['slow_probability'][:,2]),slow_down=series(sim['slow_probability'][:,0]),
                slow_slope=series(10000*sim['slow_slope']),fast_slope=series(10000*sim['fast_slope']),
                slow_lo=series(10000*(sim['slow_slope']-1.96*np.sqrt(sim['slow_variance']))),
                slow_hi=series(10000*(sim['slow_slope']+1.96*np.sqrt(sim['slow_variance']))),
                fast_lo=series(10000*(sim['fast_slope']-1.96*np.sqrt(sim['fast_variance']))),
                fast_hi=series(10000*(sim['fast_slope']+1.96*np.sqrt(sim['fast_variance']))),
                slow_level=series(np.exp(sim['slow_level'])),fast_level=series(np.exp(sim['fast_level'])),
                held=series(sim['held']),desired=series(sim['desired']),context=series(sim['context']),
                trades=trades(sim),old_trades=trades(old),evaluation_start=first,parameters=sim['parameters'])


def case_audit(f, sims, fitted):
    rows=[]
    for start,end in json.loads((study.OUT/'protocol.json').read_text())['illustrative_intervals']:
        ix=np.flatnonzero((f.days>=np.datetime64(start))&(f.days<=np.datetime64(end)))
        a,b=int(ix[0]),int(ix[-1]);low=int(ix[np.argmin(f.close[ix])]);after=ix[ix>=low];high=int(after[np.argmax(f.close[after])])
        r=dict(start=str(f.days[a]),end=str(f.days[b]),trough=str(f.days[low]),peak=str(f.days[high]),
               hindsight_trough_to_peak=float(f.close[high]/f.close[low]-1),variants=[])
        for name,sim in sims.items():
            if name=='selected':continue
            trades=[]
            for ep in sim['episodes']:
                entry,x=ep['entry_index'],ep['exit_index']
                last=x if x is not None else len(f.days)-1
                if entry>b or last<a:continue
                peak=entry+int(np.argmax(f.close[entry:last+1]));mark=ep['exit_price'] if x is not None else f.close[-1]
                trades.append(dict(entry=str(f.days[entry]),exit=str(f.days[x]) if x is not None else None,
                    entry_price=ep['entry'],exit_price=ep['exit_price'],peak_date=str(f.days[peak]),
                    peak_gain=float(f.close[peak]/ep['entry']-1),net_return=float(mark/ep['entry']*(.9995 if x is not None else 1)/1.0005-1),reason=ep['exit_reason']))
            r['variants'].append(dict(variant=name,interval_net_return=float(sim['nav'][b]/sim['nav'][a-1]-1),
                held_fraction=float(sim['held'][a:b+1].mean()),trades=trades))
        rows.append(r)
    primary=sims['selected'];lo=int(np.flatnonzero(f.days>=np.datetime64('2023-01-03'))[0])
    diagnostics=dict(selected_policy=primary['parameters'],evaluation_sessions=len(f.days)-lo,
        confirmed_slow_up_sessions=int(primary['aligned'][lo:].sum()),confirmed_slow_down_sessions=int(primary['counter'][lo:].sum()),
        slow_slope_bp_range=[float(primary['slow_slope'][lo:].min()*10000),float(primary['slow_slope'][lo:].max()*10000)],
        slow_down_probability_range=[float(primary['slow_probability'][lo:,0].min()),float(primary['slow_probability'][lo:,0].max())])
    return dict(intervals=rows,models=fitted,regime_diagnostics=diagnostics,
        interpretation='Extrema and peak gains are hindsight diagnostics, never signals. Interval results include carried positions; full trade outcomes may extend outside interval.')


def static_figure(c,path,title,start=None,end=None):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    days=np.array(c['days'],dtype='datetime64[D]')
    keep=np.ones(len(days),bool)
    if start:keep&=days>=np.datetime64(start)
    if end:keep&=days<=np.datetime64(end)
    fig,axes=plt.subplots(5,1,figsize=(13,11),sharex=True,layout='constrained',height_ratios=[2,.7,1,1,1])
    ax=axes[0];ax.plot(days[keep],np.asarray(c['close'])[keep],color='#163b54',label='Adjusted close')
    ax.plot(days[keep],np.asarray(c['slow_level'])[keep],color='#8266a0',lw=1,label='Slow latent price')
    ax.plot(days[keep],np.asarray(c['fast_level'])[keep],color='#168675',lw=.8,label='Fast latent price')
    ax.plot(days[keep],np.asarray(c['stop'])[keep],color='#b94752',label='Adopted close-test protection')
    for ledger,color in [('trades','#168675'),('old_trades','#8266a0')]:
        for ep in c[ledger]:
            for field,price,marker in [('entry','entry_price','^'),('exit','exit_price','v')]:
                if ep[field] and (not start or ep[field]>=start) and (not end or ep[field]<=end) and ep[field]>=c['evaluation_start']:
                    ax.scatter(np.datetime64(ep[field]),ep[price],marker=marker,color=color,s=35,zorder=5)
    ax.legend(fontsize=8);ax.set_ylabel('Adjusted USD')
    axes[1].bar(days[keep],np.asarray(c['volume'])[keep]/1e6,width=.9,color='#8c9ba7',label='Audited raw volume')
    axes[1].set_ylabel('Volume, million\nraw shares')
    for name,color in [('fast_up','#168675'),('fast_down','#bc5560'),('slow_up','#5daebe'),('slow_down','#8266a0')]:
        axes[2].plot(days[keep],np.asarray(c[name])[keep],label=name.replace('_',' '),color=color,lw=1)
    axes[2].set_ylim(0,1);axes[2].legend(fontsize=8,ncol=4);axes[2].set_ylabel('Filtered probability')
    for name,color in [('slow_slope','#8266a0'),('fast_slope','#168675')]:
        axes[3].plot(days[keep],np.asarray(c[name])[keep],label=name.replace('_',' '),color=color,lw=1)
    axes[3].fill_between(days[keep],np.asarray(c['slow_lo'],float)[keep],np.asarray(c['slow_hi'],float)[keep],color='#8266a0',alpha=.15,label='Slow 95% interval')
    axes[3].axhline(0,color='#8899aa',lw=.5);axes[3].legend(fontsize=8);axes[3].set_ylabel('Slope bp / session')
    for name,color in [('nav','#168675'),('baseline','#8266a0'),('buyhold','#8899aa')]:
        axes[4].plot(days[keep],np.asarray(c[name])[keep],label=name,color=color,lw=1)
    axes[4].legend(fontsize=8);axes[4].set_ylabel('Net value')
    for ax in axes:
        ax.grid(alpha=.15);ax.xaxis.set_major_formatter(dates.ConciseDateFormatter(ax.xaxis.get_major_locator()))
    fig.suptitle(title+'\nGreen fills: new. Purple fills: prior selected. 5 bp / side, next open.',fontsize=11)
    fig.savefig(path,dpi=140);plt.close(fig)


def main():
    fits=study.verified();oldfits=study.parent.verified()
    rows=json.loads((study.OUT/'asset-results.json').read_text());ports=json.loads((study.OUT/'portfolio-results.json').read_text())
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0]
    summary=summarize(rows,ports);reuse='--reuse-charts' in sys.argv
    cache=study.OUT/'chart-data.json.gz'
    charts=json.loads(gzip.decompress(cache.read_bytes())) if reuse and cache.exists() else json.loads((study.OUT/'chart-data.json').read_text()) if reuse else {}
    audit=json.loads((study.OUT/'tlt-case-audit.json').read_text()) if reuse else None
    if reuse:
        # Presentation-only addition from the same hash-verified input batch.
        for symbol in sorted(fits):
            full=study.model.Features.build(study.study.load_asset(symbol))
            for key,c in charts.items():
                if not key.startswith(symbol+'_') or 'volume' in c:continue
                days=np.array(c['days'],dtype='datetime64[D]');ix=np.searchsorted(full.days,days)
                np.testing.assert_array_equal(full.days[ix],days)
                c['volume']=full.volume[ix].tolist()
    for symbol in ([] if reuse else sorted(fits)):
        full=study.model.Features.build(study.study.load_asset(symbol))
        for era,_,first,last in study.ERAS:
            fit=fits[symbol][era]
            if not fit['available']:continue
            f=full.truncated(last);f.symbol=symbol;f.hmm_models=fit['hmms']
            old=study.union_control(f,oldfits[symbol],era);sims={'baseline':old}
            for variant in study.FAMILIES:
                p=fit['selected'][variant]['parameters'];sim=study.model.simulate(f,study.model.classify(f,p));sims[variant]=sim
                key=symbol+'_'+era+'_'+variant;charts[key]=chart_data(f,sim,old,first,era)
            if symbol=='TLT' and era=='late':
                sims['selected']=sims[fit['selected']['selected']['parameters']['family']]
                audit=case_audit(f,sims,fit['hmms'])
        print('Chart',symbol,flush=True)
    for symbol in ([] if reuse else ('TLT','GLD')):
        for family in study.FAMILIES:
            c=charts[symbol+'_late_'+family]
            static_figure(c,study.OUT/f'{symbol}_{family}.png',symbol+' | '+NAMES[family])
    c=charts['TLT_late_context']
    for start,end,name in ([] if reuse else [('2023-09-01','2024-03-31','2023-rebound'),('2024-06-01','2024-11-30','2024-rebound')]):
        static_figure(c,study.OUT/(name+'.png'),'TLT | '+NAMES['context'],start,end)
    details=json.loads((study.OUT/'diagnostics.json').read_text());weakest={}
    for era,*_ in study.ERAS:
        row=weakest_training_choice(primary,era)
        symbol=row['symbol'];family=fits[symbol][era]['selected']['selected']['parameters']['family']
        detail=details[symbol+'_'+era];closed=[t for t in detail['trades'] if t['exit']]
        weakest[era]=dict(symbol=symbol,family=family,cumulative=row['cumulative'],sharpe=row['sharpe'],maxdd=row['maxdd'],
            criterion='Lowest net cumulative return among risky ETFs under their training-selected policy; 5 bp/side, next open.',
            closed_trades=len(closed),losing_trades=sum(t['net_return']<0 for t in closed),
            accounting=detail['accounting'],worst_trades=sorted(closed,key=lambda t:t['net_return'])[:3])
        static_figure(charts[symbol+'_'+era+'_'+family],study.OUT/f'{symbol}_{era}_selected.png',symbol+' | '+NAMES[family]+' | weakest '+era+' case')
    static_figure(charts['WEAT_late_switch'],study.OUT/'WEAT_2023.png','WEAT | B | 2023 inspection','2023-01-01','2023-12-31')
    study.write(study.OUT/'weakest-cases.json',weakest)
    charts=study.clean(charts)
    study.write(study.OUT/'summary.json',summary);study.write(study.OUT/'tlt-case-audit.json',audit)
    cache.write_bytes(gzip.compress(json.dumps(charts,separators=(',',':'),allow_nan=False).encode(),mtime=0))
    # Retire only this builder's redundant uncompressed presentation cache.
    legacy_cache=study.OUT/'chart-data.json'
    if legacy_cache.exists():legacy_cache.unlink()
    fields=('symbol','era','variant','cumulative','cagr','sharpe','calmar','maxdd','alpha','exposure','completed_trades','training_evidence')
    with (study.OUT/'full-etf-table.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=[*fields,'ic21']);writer.writeheader();writer.writerows({**{k:r[k] for k in fields},'ic21':r['ic21']['ic']} for r in primary)
    bases,paths=pack_charts(charts)
    payload=dict(rows=primary,stress=rows,summary=summary,audit=audit,portfolios=ports,weakest=weakest,
        names=NAMES,models={s+'_'+era:fit[era]['hmms'] for s,fit in fits.items() for era,*_ in study.ERAS if fit[era]['available']},
        recommended={s+'_'+era:fit[era]['selected']['selected']['parameters']['family'] for s,fit in fits.items() for era,*_ in study.ERAS if fit[era]['available']},
        details=details,validation=json.loads((study.OUT/'validation.json').read_text()),
        native=json.loads((study.OUT/'native-checks.json').read_text()) if (study.OUT/'native-checks.json').exists() else [])
    template=study.ROOT/'scripts/assets/latent-slope-review.html'
    script=study.ROOT/'scripts/assets/latent-slope-script.js'
    html=template.read_text(encoding='utf-8').replace('__REPORT_SCRIPT__',script.read_text(encoding='utf-8'))
    payload=study.clean(payload);payload.update(chart_bases=bases,chart_paths=paths)
    html=html.replace('__REPORT_DATA__',json.dumps(payload,separators=(',',':'),allow_nan=False).replace('</','<\\/'))
    from render_latent_equations import render_equations
    html=render_equations(html,study.OUT)
    (study.OUT/'index.html').write_text(html,encoding='utf-8')
    study.write(study.OUT/'manifest.json',dict(files={p.name:study.study.digest(p) for p in study.OUT.iterdir() if p.is_file() and p.name!='manifest.json'},
        report_code={str(p.relative_to(study.ROOT)).replace(chr(92),'/'):study.study.digest(p) for p in
                     (Path(__file__),template,script,study.ROOT/'scripts/render_latent_equations.py',study.ROOT/'scripts/validate_latent_slope.py',
                      study.ROOT/'tests/latent_slope_controls.cjs',study.ROOT/'tests/test_latent_slope.py',study.ROOT/'tests/test_latent_slope_report.py')}))
    print(json.dumps(dict(charts=len(charts),primary=len(primary),portfolio_passes=sum(r['passed'] for r in summary['portfolio_gates']))))


if __name__=='__main__':main()
