"""Full-pool mode-switch results, parameter blocks and causal state inspection."""
from collections import Counter
import csv
import json
from pathlib import Path

import numpy as np

import research_trend_modes as study

OUT=study.OUT


def summarize(rows,baseline,portfolios):
    old={(r['symbol'],r['domain'],r['era'],r['cost_bp'],r['delay']):r for r in baseline if r['variant']=='baseline'}
    families=[]
    for era,*_ in study.ERAS:
        for variant in study.VARIANTS:
            for cost,delay in study.FRICTIONS:
                all_=[r for r in rows if r['era']==era and r['variant']==variant and r['cost_bp']==cost and r['delay']==delay and r['symbol']!='BIL']
                rr=[r for r in all_ if r['training_evidence']]
                bb=[old[r['symbol'],r['domain'],era,cost,delay] for r in rr]
                dc=np.array([r['cagr']-b['cagr'] for r,b in zip(rr,bb,strict=True)])
                dd=np.array([r['maxdd']-b['maxdd'] for r,b in zip(rr,bb,strict=True)])
                ds=np.array([r['sharpe']-b['sharpe'] for r,b in zip(rr,bb,strict=True)])
                gain=float(np.median([r['sharpe'] for r in rr])-np.median([b['sharpe'] for b in bb])) if rr else None
                qgain=float(np.quantile([r['cagr'] for r in rr],.25)-np.quantile([b['cagr'] for b in bb],.25)) if rr else None
                guard=float(np.mean((dc>=-.01)&(dd>=-.02))) if rr else 0.
                families.append(dict(era=era,variant=variant,cost_bp=cost,delay=delay,cases=len(all_),eligible=len(rr),
                    positive=sum(r['cumulative']>0 for r in all_),negative=sum(r['cumulative']<0 for r in all_),
                    median_cagr=float(np.median([r['cagr'] for r in all_])),median_sharpe=float(np.median([r['sharpe'] for r in all_])),
                    improved=int((dc>1e-10).sum()),worsened=int((dc< -1e-10).sum()),median_paired_cagr=float(np.median(dc)) if rr else None,
                    median_paired_sharpe=float(np.median(ds)) if rr else None,median_sharpe_gain=gain,lower_quartile_cagr_gain=qgain,
                    guard_fraction=guard,passed=bool(rr and gain>0 and qgain>0 and guard>=.9)))
    index={(r['era'],r['scenario'],r['cost_bp'],r['delay']):r for r in portfolios};gates=[]
    for r in portfolios:
        if not r['scenario'].startswith('selected_'):continue
        reference='FR25' if r['era']=='late' else 'momentum_'+r['scenario'].rsplit('_',1)[1]
        checks=[]
        for name in (r['scenario'].replace('selected_','baseline_'),reference):
            b=index[r['era'],name,r['cost_bp'],r['delay']]
            c=dict(reference=name,sharpe=r['sharpe']>b['sharpe']+1e-10,cagr=r['cagr']>=b['cagr']-.01,drawdown=r['max_drawdown']>=b['max_drawdown']-1e-12)
            c['passed']=c['sharpe'] and c['cagr'] and c['drawdown'];checks.append(c)
        gates.append(dict(era=r['era'],scenario=r['scenario'],cost_bp=r['cost_bp'],delay=r['delay'],comparisons=checks,passed=all(c['passed'] for c in checks)))
    return dict(families=families,portfolio_gates=gates)


def charts(rows,fits):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.dates as mdates
    import matplotlib.pyplot as plt
    cases=[('GLD','long'),('GLD','short'),('IAT','short'),('SLV','long'),('SOXX','short'),
           ('TLT','short'),('TLT','long'),('MCHI','short'),('MCHI','long')]
    worst=sorted([r for r in rows if r['era']=='late' and r['variant']=='selected' and r['symbol']!='BIL'],key=lambda r:r['cumulative'])[:2]
    cases=list(dict.fromkeys([*cases,*[(r['symbol'],r['domain']) for r in worst]]))
    result={};oldfits=study.previous.verified()
    colors={-1:'#f5d8d8',0:'#f5e9c6',1:'#d9eee5',2:'#e7eaf0'}
    labels={-1:'Down',0:'Range',1:'Up',2:'Unknown'}
    for symbol,domain in cases:
        data=study.study.load_asset(symbol);f=study.model.Features.build(data);config=fits[symbol][domain+'_late']['selected']['selected']['parameters']
        sim=study.model.simulate(f,study.model.classify(f,config));lo=int(np.flatnonzero(f.days>=np.datetime64('2023-01-03'))[0]);start=lo-1
        oldf=study.study.old.Features.build(data,study.study.old.SHORT_SPEC if domain=='short' else study.study.old.LONG_SPEC)
        old=study.previous.model.simulate(oldf,study.previous.model.prepare(oldf,oldfits[symbol][domain+'_late']['parameters'],None))
        lower,upper=np.full(len(f.days),np.nan),np.full(len(f.days),np.nan)
        for state,mode in ((-1,'down'),(0,'range'),(1,'up')):
            feature=f.cache[config[mode]['length']];mask=sim['state']==state
            if mode=='range':
                a=np.r_[np.nan,feature['box_lower'][:-1]]-config[mode]['buffer']*np.r_[np.nan,f.atr[:-1]]
                b=np.r_[np.nan,feature['box_upper'][:-1]]+config[mode]['buffer']*np.r_[np.nan,f.atr[:-1]]
            else:a,b=feature[config['method']]['lower'],feature[config['method']]['upper']
            lower[mask],upper[mask]=a[mask],b[mask]
        ep=[e for e in sim['episodes'] if e['exit_index'] is None or e['exit_index']>=lo]
        key=symbol+'_'+domain
        chart=dict(days=f.days[start:].astype(str),close=f.close[start:],lower=lower[start:],upper=upper[start:],
            state=sim['state'][start:],evidence=sim['evidence'][start:],held=sim['held'][start:],offset=start,parameters=config,
            nav=100*sim['nav'][start:]/sim['nav'][start],baseline=100*old['nav'][start:]/old['nav'][start],buyhold=100*f.close[start:]/f.close[start],
            trades=[dict(entry=str(f.days[e['entry_index']]),entry_index=e['entry_index'],entry_price=e['entry'],
                exit=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None,exit_index=e['exit_index'],exit_price=e['exit_price']) for e in ep])
        values=sim['nav'][start:]
        dd=values/np.maximum.accumulate(values)-1
        trough=int(np.argmin(dd))+start
        peak=int(np.argmax(sim['nav'][start:trough+1]))+start
        down_days=np.flatnonzero(sim['masks']['down'][peak:trough+1])+peak
        chart['drawdown_observation']=dict(peak_date=str(f.days[peak]),trough_date=str(f.days[trough]),max_drawdown=float(dd.min()),
            first_confirmed_down=str(f.days[down_days[0]]) if len(down_days) else None,
            down_evidence_sessions_retaining_up=int(np.sum(sim['masks']['down'][peak:trough+1]&(sim['state'][peak:trough+1]==study.model.UP))),
            down_evidence_sessions_overridden_by_range=int(np.sum(sim['masks']['down'][peak:trough+1]&sim['masks']['range'][peak:trough+1])))
        result[key]=chart
        fig,axes=plt.subplots(2,1,figsize=(13,8),layout='constrained',height_ratios=[1.4,1])
        ax=axes[0];days=f.days[start:];states=sim['state'][start:]
        boundaries=np.r_[0,np.flatnonzero(states[1:]!=states[:-1])+1,len(days)-1]
        for a,b in zip(boundaries[:-1],boundaries[1:],strict=True):ax.axvspan(days[a],days[b],color=colors[int(states[a])],alpha=.7,lw=0)
        ax.plot(days,f.close[start:],color='#153c55',lw=1.25,label='Adjusted close')
        for state in (-1,0,1):
            mask=states==state
            ax.plot(days,np.where(mask,lower[start:],np.nan),color='#547e8b',lw=.65,alpha=.75,label='Current-mode corridor' if state==-1 else None)
            ax.plot(days,np.where(mask,upper[start:],np.nan),color='#547e8b',lw=.65,alpha=.75)
        for e in ep:
            if e['entry_index']>=lo:ax.scatter(f.days[e['entry_index']],e['entry'],color='#087c58',marker='^',s=40,zorder=4)
            if e['exit_index'] is not None:ax.scatter(f.days[e['exit_index']],e['exit_price'],color='#b54249',marker='v',s=40,zorder=4)
        from matplotlib.patches import Patch
        handles,legend=ax.get_legend_handles_labels();handles.extend(Patch(color=colors[s],label=labels[s]) for s in (-1,0,1))
        ax.legend(handles=handles,fontsize=8,ncol=5,loc='upper left');ax.set_ylabel('Adjusted USD')
        ax.set_title('Close-time modes; actual buys ▲ / sells ▼. Corridors are indicators, not stop orders.',loc='left',fontsize=10)
        ax=axes[1]
        for k,color,label in (('nav','#168675','Mode switch'),('baseline','#8266a0','Previous fitted breakout'),('buyhold','#8093a3','Buy and hold')):
            ax.plot(days,chart[k],color=color,lw=1.4,label=label)
        ax.legend(fontsize=8,loc='upper left');ax.set_ylabel('Value from100, net costs')
        for ax in axes:
            ax.grid(alpha=.12);ax.xaxis.set_major_locator(mdates.YearLocator());ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
        fig.suptitle(f"{symbol} {domain} | {config['family'].replace('_',' ')} | independently fitted range/up/down\n2023–October16,2026 · 5bp/side · next open · hold through range",fontsize=12)
        fig.savefig(OUT/(key.lower()+'.png'),dpi=145);plt.close(fig)
    return result


def main():
    fits=study.verified();rows=json.loads((OUT/'asset-results.json').read_text());ports=json.loads((OUT/'portfolio-results.json').read_text())
    baseline=json.loads((study.previous.OUT/'asset-results.json').read_text());summary=summarize(rows,baseline,ports)
    choices=json.loads((OUT/'selected-parameters.json').read_text())
    summary['chosen_families']={era:dict(Counter(r['parameters']['family'] for r in choices if r['era']==era and r['variant']=='selected')) for era,*_ in study.ERAS}
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0]
    chartdata=charts(primary,fits)
    old={(r['symbol'],r['domain'],r['era']):r for r in baseline if r['cost_bp']==5 and r['delay']==0 and r['variant']=='baseline'}
    summary['selected_diagnostics']={}
    for era,*_ in study.ERAS:
        rr=[r for r in primary if r['era']==era and r['variant']=='selected' and r['symbol']!='BIL']
        summary['selected_diagnostics'][era]=dict(cases=len(rr),
            improves_previous_cagr=sum(r['cagr']>old[r['symbol'],r['domain'],era]['cagr']+1e-10 for r in rr),
            beats_buyhold_cagr=sum(r['cagr']>r['buyhold']['cagr'] for r in rr),beats_buyhold_sharpe=sum(r['sharpe']>r['buyhold']['sharpe'] for r in rr),
            median_exposure=float(np.median([r['exposure'] for r in rr])),median_ic=float(np.median([r['ic21']['ic'] for r in rr if r['ic21']['ic'] is not None])),
            fewer_than_five_closed=sum(r['completed_trades']<5 for r in rr),
            positive_alpha=sum(r['alpha'] is not None and r['alpha']>0 for r in rr),
            positive_alpha_holm_05=sum(r['alpha'] is not None and r['alpha']>0 and r['alpha_holm_p']<.05 for r in rr),
            positive_ic_holm_05=sum(r['ic21']['ic'] is not None and r['ic21']['ic']>0 and r['ic21_holm_p']<.05 for r in rr))
    study.write(OUT/'summary.json',summary);study.write(OUT/'chart-data.json',chartdata)
    fields=('symbol','domain','era','variant','cumulative','cagr','sharpe','calmar','maxdd','alpha','exposure','completed_trades','training_evidence')
    with (OUT/'full-etf-table.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=[*fields,'ic21']);writer.writeheader()
        writer.writerows({**{k:r[k] for k in fields},'ic21':r['ic21']['ic']} for r in primary)
    stressfields=('symbol','domain','era','variant','cost_bp','delay','cumulative','cagr','sharpe','maxdd','turnover_annual','cost_bp_annual')
    payload=dict(rows=primary,baseline=[r for r in baseline if r['cost_bp']==5 and r['delay']==0 and r['variant'] in ('baseline','shared_trend')],
        stress=[{k:r[k] for k in stressfields} for r in rows],choices=choices,summary=summary,portfolios=ports,
        details=json.loads((OUT/'diagnostics.json').read_text()),charts=chartdata,validation=json.loads((OUT/'validation.json').read_text()),
        native=json.loads((OUT/'native-checks.json').read_text()) if (OUT/'native-checks.json').exists() else [])
    template=study.ROOT/'scripts/assets/trend-modes-review.html'
    html=template.read_text(encoding='utf-8').replace('__REPORT_DATA__',json.dumps(study.clean(payload),separators=(',',':'),allow_nan=False).replace('</','<\\/'))
    (OUT/'index.html').write_text(html,encoding='utf-8')
    study.write(OUT/'manifest.json',dict(files={p.name:study.study.digest(p) for p in OUT.iterdir() if p.is_file() and p.name!='manifest.json'},
        report_code={str(p.relative_to(study.ROOT)).replace(chr(92),'/'):study.study.digest(p) for p in (Path(__file__),template,study.ROOT/'scripts/validate_trend_modes.py')}))
    print(json.dumps(dict(families=[r for r in summary['families'] if r['cost_bp']==5 and r['delay']==0],chosen=summary['chosen_families'],portfolio_passes=sum(g['passed'] for g in summary['portfolio_gates'])),indent=2))


if __name__=='__main__':main()
