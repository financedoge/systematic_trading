"""Inspectable multiscale/HMM comparisons, causal daily levels and probability paths."""
from collections import Counter
import csv
import json
from pathlib import Path
import sys

import numpy as np

import research_multiscale_modes as study

FOCUS=('GLD','CORN','EWA','TLT','MCHI','IAT','SLV','SOXX')


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


def chart_data(f,sim,control,first):
    lo=int(np.flatnonzero(f.days>=np.datetime64(first))[0]);start=max(252,lo-252)
    round_=lambda a:np.round(a[start:],6)
    trade=[dict(entry=str(f.days[e['entry_index']]),exit=str(f.days[e['exit_index']]) if e['exit_index'] is not None else None,
        entry_index=e['entry_index']-start,exit_index=e['exit_index']-start if e['exit_index'] is not None else None,
        entry_price=e['entry'],exit_price=e['exit_price'],reason=e['exit_reason']) for e in sim['episodes'] if e['exit_index'] is None or e['exit_index']>=start]
    nav=np.full(len(f.days),np.nan);base=nav.copy();bh=nav.copy()
    nav[lo-1:]=100*sim['nav'][lo-1:]/sim['nav'][lo-1];base[lo-1:]=100*control['nav'][lo-1:]/control['nav'][lo-1];bh[lo-1:]=100*f.close[lo-1:]/f.close[lo-1]
    out=dict(days=f.days[start:].astype(str),close=round_(f.close),nav=round_(nav),baseline=round_(base),buyhold=round_(bh),
        state=sim['state'][start:],context=sim['context'][start:],lower=round_(sim['lower']),upper=round_(sim['upper']),
        slow_lower=round_(sim['slow_lower']),slow_upper=round_(sim['slow_upper']),stop=round_(sim['stop']),
        fast_length=sim['fast_length'][start:],slow_length=sim['slow_length'][start:],activity=round_(f.activity),volatility=round_(f.volatility),
        trades=trade,evaluation_start=first,parameters=sim['parameters'])
    for key in ('fast_probability','slow_probability'):
        if key in sim:out[key]=round_(sim[key])
    return out


def static_figure(symbol,c,path):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as dates
    day=np.array(c['days'],dtype='datetime64[D]');has_hmm='fast_probability' in c
    fig,axes=plt.subplots(4 if has_hmm else 3,1,figsize=(14,11 if has_hmm else 9),layout='constrained',sharex=True,
        height_ratios=[2,1,1,1] if has_hmm else [2,1,1])
    ax=axes[0];state=c['context'];colors={-1:'#f8dddd',0:'#f8edcf',1:'#def0e5',2:'#edf0f3'}
    bounds=np.r_[0,np.flatnonzero(state[1:]!=state[:-1])+1,len(day)-1]
    for a,b in zip(bounds[:-1],bounds[1:],strict=True):ax.axvspan(day[a],day[b],color=colors[int(state[a])],lw=0)
    ax.plot(day,c['close'],color='#163c56',lw=1.1,label='Adjusted close')
    ax.plot(day,c['lower'],color='#398986',lw=.65,label='Fast corridor');ax.plot(day,c['upper'],color='#398986',lw=.65)
    ax.plot(day,c['slow_lower'],color='#b38e48',lw=.7,alpha=.8,label='Slow corridor');ax.plot(day,c['slow_upper'],color='#b38e48',lw=.7,alpha=.8)
    if np.isfinite(np.asarray(c['stop'],float)).any():
        ax.plot(day,c['stop'],color='#b94752',lw=1,label='Adopted close-test protection')
    for t in c['trades']:
        if t['entry_index']>=0:ax.scatter(day[t['entry_index']],t['entry_price'],marker='^',s=35,color='#087e5e',zorder=5)
        if t['exit_index'] is not None:ax.scatter(day[t['exit_index']],t['exit_price'],marker='v',s=35,color='#b03c48',zorder=5)
    ax.legend(fontsize=8,ncol=3,loc='upper left');ax.set_ylabel('Adjusted USD')
    ax=axes[1]
    for k,color,label in (('nav','#168675','New strategy'),('baseline','#8266a0','Previous mode union'),('buyhold','#8093a3','Buy and hold')):
        ax.plot(day,c[k],color=color,label=label,lw=1.2)
    ax.legend(fontsize=8,ncol=3,loc='upper left');ax.set_ylabel('Net value from 100')
    axes[2].step(day,c['fast_length'],color='#288783',label='Fast analysis window',lw=.8)
    axes[2].step(day,c['slow_length'],color='#a78946',label='Slow analysis window',lw=.8)
    axes[2].legend(fontsize=8,ncol=2,loc='upper left');axes[2].set_ylabel('Sessions')
    if has_hmm:
        axes[2].set_title('Auxiliary corridor windows; HMM observes all declared horizons',fontsize=9,loc='left')
        for key,color,label in (('fast_probability','#268b71','Fast up'),('slow_probability','#665291','Slow down')):
            axes[3].plot(day,np.asarray(c[key])[:,2 if key.startswith('fast') else 0],color=color,label=label,lw=.9)
        axes[3].set_ylim(-.02,1.02);axes[3].set_ylabel('Filtered probability');axes[3].legend(fontsize=8,ncol=2,loc='upper left')
    for ax in axes:
        ax.axvline(np.datetime64(c['evaluation_start']),color='#526472',ls='--',lw=.8);ax.grid(alpha=.12)
        ax.xaxis.set_major_locator(dates.YearLocator());ax.xaxis.set_major_formatter(dates.DateFormatter('%Y'))
    protection='with protection' if np.isfinite(np.asarray(c['stop'],float)).any() else 'directional exit only; no stop-loss'
    fig.suptitle(f"{symbol} | {c['parameters']['label']} | {protection} | 5 bp, next open\nBackground = slow context; triangles = actual fills. Before dashed line: training context.",fontsize=11)
    fig.savefig(path,dpi=135);plt.close(fig)


def main():
    fits=study.verified();oldfits=study.parent.verified()
    rows=json.loads((study.OUT/'asset-results.json').read_text());ports=json.loads((study.OUT/'portfolio-results.json').read_text())
    primary=[r for r in rows if r['cost_bp']==5 and r['delay']==0];choices=json.loads((study.OUT/'selected-parameters.json').read_text())
    summary=summarize(rows,ports)
    summary['chosen_families']={era:dict(Counter(r['parameters']['label'] for r in choices if r['era']==era and r['variant']=='selected')) for era,*_ in study.ERAS}
    reuse='--reuse-charts' in sys.argv
    charts=json.loads((study.OUT/'chart-data.json').read_text()) if reuse else {}
    for symbol in ([] if reuse else sorted(fits)):
        full=study.model.Features.build(study.study.load_asset(symbol))
        for era,_,first,last in study.ERAS:
            if not fits[symbol][era]['available']:continue
            f=full.truncated(last);f.hmm_models=fits[symbol][era]['hmms'];control=study.union_control(f,oldfits[symbol],era)
            variants=['selected']+(['hmm_volume','hmm_stress_volume'] if era=='late' and symbol in FOCUS else [])
            for variant in variants:
                p=fits[symbol][era]['selected'][variant]['parameters'];sim=study.model.simulate(f,study.model.classify(f,p))
                c=chart_data(f,sim,control,first);key=symbol+'_'+era+'_'+variant;charts[key]=c
                if era=='late' and symbol in FOCUS and (variant=='selected' or (symbol=='GLD' and variant=='hmm_stress_volume')):
                    static_figure(symbol,c,study.OUT/(key+'.png'))
        print('Chart',symbol,flush=True)
    study.write(study.OUT/'summary.json',summary);study.write(study.OUT/'chart-data.json',charts)
    fields=('symbol','era','variant','cumulative','cagr','sharpe','calmar','maxdd','alpha','exposure','completed_trades','training_evidence')
    with (study.OUT/'full-etf-table.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=[*fields,'ic21']);writer.writeheader();writer.writerows({**{k:r[k] for k in fields},'ic21':r['ic21']['ic']} for r in primary)
    stresskeys=('symbol','era','variant','cost_bp','delay','cumulative','cagr','sharpe','maxdd','turnover_annual','cost_bp_annual')
    payload=dict(rows=primary,choices=choices,charts=charts,summary=summary,portfolios=ports,
        stress=[{k:r[k] for k in stresskeys} for r in rows],details=json.loads((study.OUT/'diagnostics.json').read_text()),
        case_audit=json.loads((study.OUT/'parent-case-audit.json').read_text()),validation=json.loads((study.OUT/'validation.json').read_text()),
        native=json.loads((study.OUT/'native-checks.json').read_text()) if (study.OUT/'native-checks.json').exists() else [])
    template=study.ROOT/'scripts/assets/multiscale-modes-review.html'
    html=template.read_text(encoding='utf-8').replace('__DATE_CONTROLS__',(study.ROOT/'scripts/assets/chart-date-controls.js').read_text(encoding='utf-8')).replace('__REPORT_DATA__',json.dumps(study.clean(payload),separators=(',',':'),allow_nan=False).replace('</','<\\/'))
    (study.OUT/'index.html').write_text(html,encoding='utf-8')
    study.write(study.OUT/'manifest.json',dict(files={p.name:study.study.digest(p) for p in study.OUT.iterdir() if p.is_file() and p.name!='manifest.json'},
        report_code={str(p.relative_to(study.ROOT)).replace(chr(92),'/'):study.study.digest(p) for p in
                     (Path(__file__),template,study.ROOT/'scripts/assets/chart-date-controls.js',study.ROOT/'scripts/validate_multiscale_modes.py',study.ROOT/'scripts/analyze_mode_case_failures.py')}))
    print(json.dumps(dict(primary_rows=len(primary),charts=len(charts),portfolio_passes=sum(x['passed'] for x in summary['portfolio_gates']),chosen=summary['chosen_families']),indent=2))


if __name__=='__main__':main()
