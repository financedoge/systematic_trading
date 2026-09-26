"""Compare audited-input LEAN trials and rebuild reproducible concentration plots."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import html
import json
from pathlib import Path
import shutil
import sys

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from analyze_constituent_integration import audit_exposure
from analyze_constituent_research import information_ratio
from analyze_flow_concentration_research import metrics, return_vector, block_audit, price_benchmark
from run_constituent_research import verify_manifest
from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, verify_bundle, write_json
from systematic_trading.lean.registry import register_run
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.analytics_projection import observation
from systematic_trading.research.governed_inputs import GovernedInputs
from systematic_trading.research.sector_hhi import correlations, correlation_block_interval
from systematic_trading.storage.postgres import PostgresStore


def read(path):
    return json.loads(path.read_text(encoding='utf8'))


def qualified(row):
    return bool(row and row.get('scores') is not None and row['value_coverage']>=.95 and row['name_coverage']>=.70)


def charts(root, protocol, features, labels, plt, PercentFormatter):
    spy=read(root/'bars.json')['SPY'];index={r['trade_date']:i for i,r in enumerate(spy)}
    old=read(Path(protocol['prior_root'])/'features.json')
    old_spy=read(Path(protocol['old_snapshot'])/'bars.json')['SPY'];old_index={r['trade_date']:i for i,r in enumerate(old_spy)}
    records=[]
    for d,r in features['45'].items():
        if d<protocol['start'] or d not in index or index[d]+120>=len(spy) or not qualified(r):
            continue
        point=dict(date=d,session=index[d],**r['values'],value_coverage=r['value_coverage'],name_coverage=r['name_coverage'])
        for horizon in (20,60,120):
            point['spy_'+str(horizon)]=float(spy[index[d]+horizon]['close'])/float(spy[index[d]]['close'])-1
            forward=labels.get(d,{}).get(str(horizon),{})
            point['basket_'+str(horizon)]=forward.get('basket')
            for sector,value in forward.get('sectors',{}).items():
                point['sector_'+sector+'_'+str(horizon)]=value
        previous=old['45'].get(d)
        point['old_qualified']=qualified(previous)
        if previous and previous['values']:
            point['old_hhi_ema']=previous['values']['hhi_smoothed']
            point['old_hhi_d1']=previous['values']['hhi_velocity']
            point['old_hhi_d2']=previous['values']['hhi_acceleration']
        if d in old_index and old_index[d]+120<len(old_spy):
            for horizon in (20,60,120):
                point['old_spy_'+str(horizon)]=float(old_spy[old_index[d]+horizon]['close'])/float(old_spy[old_index[d]]['close'])-1
        records.append(point)
    if not records:
        raise ValueError('No qualified scatter observations')
    keys=sorted({k for r in records for k in r});write_json(root/'scatter_observations.json',records)
    with (root/'scatter_observations.csv').open('w',newline='',encoding='utf8') as out:
        writer=csv.DictWriter(out,fieldnames=keys);writer.writeheader();writer.writerows(records)
    panels={
        'dollar_raw':('Raw dollar-volume HHI',['dollar_hhi','dollar_d1','dollar_d2']),
        'dollar_smoothed':('EMA(10) dollar-volume HHI',['dollar_ema','dollar_ema_d1','dollar_ema_d2']),
        'shares_raw':('Raw share-volume HHI',['shares_hhi','shares_d1','shares_d2']),
        'shares_smoothed':('EMA(10) share-volume HHI',['shares_ema','shares_ema_d1','shares_ema_d2']),
    }
    diagnostics,figures={},[]
    def finite(value):
        return value is not None and np.isfinite(value)
    targets=['spy','basket']+sorted({k.rsplit('_',1)[0] for k in keys if k.startswith('sector_')})
    for target in targets:
        for variant,(title,columns) in panels.items():
            if target.startswith('sector_') and variant!='dollar_smoothed':
                continue
            points=[r for r in records if all(finite(r.get(target+'_'+str(h))) for h in (20,60,120))]
            fig,axes=plt.subplots(3,3,figsize=(14,10.5))
            name=target.replace('sector_','').replace(' ','_')+'_'+variant
            diagnostic=diagnostics[name]={}
            for i,key in enumerate(columns):
                for j,horizon in enumerate((20,60,120)):
                    ax=axes[i,j]
                    x=np.array([r[key] for r in points]);y=np.array([r[target+'_'+str(horizon)] for r in points])
                    result=correlations(x,y)
                    result['block240_ci95']=correlation_block_interval(x,y,replicates=600)
                    periods={}
                    for label,start,end in [('2016_19','2016-01-01','2019-12-31'),('2020_22','2020-01-01','2022-12-31'),('2023_plus','2023-01-01',protocol['end'])]:
                        m=np.array([start<=r['date']<=end for r in points],dtype=bool)
                        periods[label]=correlations(x[m],y[m])
                    result['periods']=periods
                    offsets=[]
                    for offset in range(horizon):
                        m=np.array([r['session']%horizon==offset for r in points],dtype=bool)
                        corr=correlations(x[m],y[m])
                        if corr['n']>=10 and corr['pearson'] is not None:
                            offsets.append(corr['pearson'])
                    result['nonoverlap_offsets']=dict(n=len(offsets),min=float(min(offsets)) if offsets else None,
                        median=float(np.median(offsets)) if offsets else None,max=float(max(offsets)) if offsets else None)
                    diagnostic[key+'_'+str(horizon)]=result
                    colors=['#2563eb' if r['date']<'2020' else '#d97706' if r['date']<'2023' else '#059669' for r in points]
                    ax.scatter(x,y,s=5,alpha=.25,c=colors,rasterized=True)
                    if len(x)>2 and np.std(x)>0:
                        line=np.quantile(x,[.01,.99]);ax.plot(line,np.polyval(np.polyfit(x,y,1),line),color='#334155',lw=1)
                    rho='n/a' if result['pearson'] is None else f"{result['pearson']:+.3f}"
                    ax.set_title(f"{['HHI level','First backward difference','Second backward difference'][i]} / next {horizon} sessions\nr = {rho} | n = {len(points):,}",fontsize=10)
                    ax.axhline(0,color='#94a3b8',lw=.7);ax.yaxis.set_major_formatter(PercentFormatter(1));ax.ticklabel_format(axis='x',style='sci',scilimits=(-3,3))
            target_title='SPY' if target=='spy' else 'fixed constituent basket' if target=='basket' else target.replace('sector_','')
            fig.suptitle(title+' vs '+target_title+' returns',fontsize=17,x=.05,ha='left')
            fig.text(.05,.936,'Audited raw stock activity | dated IVV proxy | >=95% value / >=70% names | matched dates across horizons',fontsize=9)
            actual_range=points[0]['date']+' to '+points[-1]['date'] if points else 'No complete qualified observations'
            fig.text(.05,.913,actual_range+' | Qualifying dates only | Overlapping outcomes; descriptive, reused history',fontsize=9)
            fig.tight_layout(rect=(.01,.01,1,.90));fig.savefig(root/(name+'.png'),dpi=145);fig.savefig(root/(name+'.svg'));plt.close(fig)
            figures.append(name+'.png')
    comparison={}
    paired=[r for r in records if r['old_qualified'] and 'old_hhi_ema' in r and 'old_spy_120' in r]
    for new_key,old_key in [('dollar_ema','old_hhi_ema'),('dollar_ema_d1','old_hhi_d1'),('dollar_ema_d2','old_hhi_d2')]:
        for horizon in (20,60,120):
            comparison[new_key+'_'+str(horizon)]={
                'old':correlations(np.array([r[old_key] for r in paired]),np.array([r['old_spy_'+str(horizon)] for r in paired])),
                'etf_prices_only':correlations(np.array([r[old_key] for r in paired]),np.array([r['spy_'+str(horizon)] for r in paired])),
                'both_corrected':correlations(np.array([r[new_key] for r in paired]),np.array([r['spy_'+str(horizon)] for r in paired]))}
    write_json(root/'scatter_correlations.json',diagnostics);write_json(root/'scatter_matched_comparison.json',comparison)
    return records,diagnostics,comparison,figures


def main(root):
    verify_manifest(root,'input_manifest.json')
    protocol,progress=read(root/'protocol.json'),read(root/'progress.json')
    if not progress['complete'] or set(progress['passed'])!=set(protocol['trials']):
        raise ValueError('All declared trials must complete')
    economies={}
    for name,economic_hash in progress['passed'].items():
        verify_bundle(root/'datasets'/name);receipt=read(root/'runs'/name/'run.json')
        if receipt['status']!='succeeded' or receipt['economic_sha256']!=economic_hash or not read(root/'runs'/name/'parity.json')['passed']:
            raise ValueError('Incomplete native result: '+name)
        for filename,expected in receipt['artifacts'].items():
            if sha256(root/'runs'/name/filename)!=expected:
                raise ValueError('Native artifact changed: '+name+'/'+filename)
        economies[name]=read(root/'runs'/name/'economic.json')
    features=read(root/'features.json');old_features=read(root/'old_features.json')
    vectors={n:return_vector(e['nav']) for n,e in economies.items()}
    first_signal_decision=min(d for d,r in economies['sota']['decisions'].items() if qualified(features['45'].get(r['known_through'])))
    windows={'full':(protocol['start'],protocol['end']),'2016_19':('2016-01-01','2019-12-31'),
        '2020_22':('2020-01-01','2022-12-31'),'2023_plus':('2023-01-01',protocol['end']),
        'since_first_qualified_decision':(first_signal_decision,protocol['end']),
        **{str(y):(f'{y}-01-01',f'{y}-12-31') for y in range(2016,2027)}}
    summary,exposure,activity={},{},{}
    for name,economic in economies.items():
        cfg=protocol['trials'][name];base=cfg.get('comparator','sota')
        days=np.array([r['date'] for r in economic['nav']]);base_days=[r['date'] for r in economies[base]['nav']]
        if list(days)!=base_days:
            raise ValueError('Comparator calendars differ')
        summary[name]={}
        for label,(start,end) in windows.items():
            result=metrics(economic,start,end)
            if result is None:
                continue
            baseline=metrics(economies[base],start,end);mask=(days>=start)&(days<=end)
            summary[name][label]=dict(**result,**information_ratio((vectors[name]-vectors[base])[mask]),
                cagr_delta=result['cagr']-baseline['cagr'],sharpe_delta=result['sharpe']-baseline['sharpe'],comparator=base)
        fs=old_features if cfg.get('feature_set')=='old' else features
        quotes=read(root/'datasets'/base/'quotes.json')
        exposure[name]=audit_exposure(economic,economies[base],quotes,fs,cfg.get('constituent'))
        if exposure[name]['max_active_weight']>.03000001 or exposure[name]['max_target_gross_difference']>1e-8:
            raise ValueError('Risk bounds failed: '+name)
        lag=str((cfg.get('constituent') or {}).get('holdings_lag_days',45))
        monthly=[dict(date=d,qualified=qualified(fs[lag].get(r['known_through'])),
            value_coverage=(fs[lag].get(r['known_through']) or {}).get('value_coverage'),
            snapshot=(fs[lag].get(r['known_through']) or {}).get('snapshot')) for d,r in economic['decisions'].items()]
        activity[name]=dict(decisions=len(monthly),qualified=sum(r['qualified'] for r in monthly),records=monthly)
    candidates=[n for n,cfg in protocol['trials'].items() if n!='sota' and not cfg.get('stress') and not cfg.get('fixed_model') and cfg.get('feature_set')!='old']
    days=np.array([r['date'] for r in economies['sota']['nav']]);uncertainty={}
    for label in ('full','2016_19','2020_22','2023_plus','since_first_qualified_decision'):
        start,end=windows[label];mask=(days>=start)&(days<=end)
        matrix=np.column_stack([vectors[n]-vectors['sota'] for n in candidates])[mask]
        uncertainty[label]={str(block):block_audit(matrix,candidates,block=block) for block in (63,126)}
    pairs={'early_vs_late':('early_signed','late_signed'),'early_vs_price':('early_signed','early_price'),
        'late_vs_price':('late_signed','late_price'),'joint_vs_price_tree':('tree_joint','tree_price'),
        'corrected_stock_features':('early_signed','early_signed_old_features')}
    contrasts={}
    for label in ('full','2016_19','2020_22','2023_plus','since_first_qualified_decision'):
        start,end=windows[label];mask=(days>=start)&(days<=end)
        matrix=np.column_stack([vectors[a]-vectors[b] for a,b in pairs.values()])[mask]
        bootstrap=block_audit(matrix,list(pairs),block=63)
        contrasts[label]={name:dict(**information_ratio(matrix[:,i]),cagr_delta=summary[a][label]['cagr']-summary[b][label]['cagr'],
            bootstrap=bootstrap['trials'][name]) for i,(name,(a,b)) in enumerate(pairs.items())}
    fixed_names=[n for n in economies if n.startswith('fixed_') and n!='fixed_sota']
    fixed_matrix=np.column_stack([vectors[n]-vectors['fixed_sota'] for n in fixed_names])
    uncertainty['actual_frozen_model']=block_audit(fixed_matrix,fixed_names,block=63)
    fixed_active=vectors['fixed_early_signed']-vectors['fixed_early_price']
    contrasts['actual_frozen_model']={'signed_vs_price':dict(**information_ratio(fixed_active),bootstrap=block_audit(fixed_active[:,None],['signed_vs_price'])['trials']['signed_vs_price'])}
    prior=Path(protocol['prior_root']);verify_manifest(prior,'analysis_manifest.json');old_summary=read(prior/'summary.json')
    attribution={n:dict(old=old_summary[n]['full'],audited=summary[n]['full']) for n in summary if n in old_summary}
    old_bars=read(Path(protocol['old_snapshot'])/'bars.json');bars=read(root/'bars.json');differences=[]
    for symbol,rows in bars.items():
        old={r['trade_date']:r for r in old_bars[symbol]}
        for left,right in zip(rows,rows[1:]):
            a,b=left['trade_date'],right['trade_date']
            if a in old and b in old:
                new_return=float(right['close'])/float(left['close'])-1;old_return=float(old[b]['close'])/float(old[a]['close'])-1
                differences.append(dict(symbol=symbol,date=b,new_return=new_return,old_return=old_return,difference=new_return-old_return))
    differences=sorted(differences,key=lambda r:abs(r['difference']),reverse=True)
    governed=GovernedInputs(Path(protocol['governed_root']),protocol['batch']);benchmarks={}
    for symbol in ('SPY','URTH','AOR'):
        rows=governed.rows(symbol,protocol['warmup_start'],protocol['end'])
        context=[dict(trade_date=r['trade_date'],open=r['adjusted_open'],close=r['adjusted_close']) for r in rows]
        economic=price_benchmark(context,read(root/'fx.json'),list(days))
        benchmarks[symbol]=metrics(economic,*windows['full']) if economic else None
    for filename,value in [('summary',summary),('exposure_audit',exposure),('signal_activity',activity),('uncertainty',uncertainty),
        ('contrasts',contrasts),('old_vs_audited',attribution),('etf_return_corrections',differences[:100]),('benchmarks',benchmarks),('benchmark_input_hashes',governed.used)]:
        write_json(root/(filename+'.json'),value)
    sys.path.insert(0,'D:/systematic_trading_data/lean/research/plot_dependencies')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False})
    records,diagnostics,paired,figures=charts(root,protocol,features,read(root/'labels.json'),plt,PercentFormatter)
    fig,axes=plt.subplots(2,2,figsize=(16,10));stamps=[datetime.fromisoformat(d) for d in days]
    for name in ('sota','early_signed','early_price','tree_joint','flow20'):
        axes[0,0].plot(stamps,np.cumprod(1+vectors[name]),label=name,lw=1)
    axes[0,0].set_title('Net growth of initial capital');axes[0,0].legend(fontsize=8,frameon=False)
    for name in ('early_signed','early_price','late_concentration','tree_joint','flow20'):
        axes[0,1].plot(stamps,np.cumprod(1+vectors[name])/np.cumprod(1+vectors['sota'])-1,label=name,lw=1)
    axes[0,1].set_title('Relative wealth versus audited baseline');axes[0,1].yaxis.set_major_formatter(PercentFormatter(1));axes[0,1].legend(fontsize=8,frameon=False)
    vals=[summary[n]['full']['information_ratio'] or 0 for n in candidates]
    axes[1,0].barh(candidates,vals,color=['#059669' if v>0 else '#d97706' for v in vals]);axes[1,0].axvline(0,color='#64748b',lw=.8)
    axes[1,0].set_title('Active information ratio, matched baseline')
    for label,series in [('Audited raw activity',features),('Previous mixed sources',old_features)]:
        rows=activity['sota']['records'];keys=list(economies['sota']['decisions'].values())
        axes[1,1].plot([datetime.fromisoformat(r['date']) for r in rows],[(series['45'].get(r['known_through']) or {}).get('value_coverage',np.nan) for r in keys],label=label)
    axes[1,1].axhline(.95,color='#64748b',ls='--');axes[1,1].set_title('Coverage under the unchanged 95% rule');axes[1,1].yaxis.set_major_formatter(PercentFormatter(1));axes[1,1].legend(fontsize=8,frameon=False)
    fig.suptitle('Audited histories: strategy rerun',x=.05,ha='left',fontsize=20)
    fig.text(.05,.935,'2016-01-04 to 2026-09-24 | Native LEAN | Annual causal tree fits | Net CNH adjusted units | Reused research sample',fontsize=10)
    fig.tight_layout(rect=(.01,.01,1,.91));fig.savefig(root/'strategy_results.png',dpi=155);fig.savefig(root/'strategy_results.svg');plt.close(fig)
    figures.insert(0,'strategy_results.png')
    lines=['# Audited-input rerun','',protocol['limitations'],'',
        '| Strategy | CAGR | Sharpe | Max drawdown | IR vs matched baseline | Changed decisions |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for name in protocol['trials']:
        r=summary[name]['full'];ir='n/a' if r['information_ratio'] is None else f"{r['information_ratio']:+.3f}"
        lines.append(f"| {name} | {r['cagr']:.2%} | {r['sharpe']:.3f} | {r['max_drawdown']:.2%} | {ir} | {exposure[name]['changed_decisions']} |")
    lines+=['','## Coverage and controls','',f"Audited stock features qualify {activity['sota']['qualified']} of {activity['sota']['decisions']} monthly dates; previous features qualify {activity['early_signed_old_features']['qualified']}. Unqualified signals stay neutral.",
        '',f"The first qualified monthly decision is {first_signal_decision}. The since_first_qualified_decision slice is a descriptive coverage-based window added during review, not an additional untouched test or a parameter choice. Scatter dataset: {len(records)} common 120-session-complete signal dates. Stock-basket/sector panels additionally require all selected constituent endpoint prices; no survivor reweighting.",
        '', 'Strategy Sharpe uses a zero hurdle. Long runs reconstruct the recipe with annual causal fits; fixed_* runs use the actual deployed frozen model only after 2023. External benchmarks are analytical friction-matched buy-and-hold context, not additional native runs.',
        '', 'The ETF flow variants retain the original adjusted-price/source-volume activity convention. Stock dollar activity uses governed reconstructed raw prices and raw volume. Share-volume HHI remains sensitive to nominal share units and splits.',
        '', 'Old comparison metrics: old_vs_audited.json. Matched scatter changes: scatter_matched_comparison.json. Uncertainty includes 63/126-session paired blocks and max-t across declared long-run candidates; research selection and uncertain historical vintages remain.', '']
    (root/'report.md').write_text('\n'.join(lines),encoding='utf8')
    gallery='<!doctype html><meta charset="utf-8"><title>Audited strategy and HHI research</title><style>body{font:16px system-ui;margin:32px auto;max-width:1400px;color:#1e293b}img{max-width:100%;border:1px solid #ddd}a{color:#2456a6}section{margin:40px 0}nav{display:flex;gap:16px;flex-wrap:wrap}</style><h1>Audited strategy and HHI research</h1><p>2016–2026 · pinned governed inputs · original parameter choices · research only</p><p>HHI panels use the same signal dates across 20/60/120 sessions; missing future constituent prices remain missing. IVV is an S&amp;P 500 proxy, not a full-market census.</p><nav>'+''.join(f'<a href="#{html.escape(n)}">{html.escape(n[:-4])}</a>' for n in figures)+'</nav>'+''.join(f'<section id="{html.escape(n)}"><h2>{html.escape(n[:-4].replace("_"," "))}</h2><a href="{html.escape(n[:-4])}.svg">Download SVG</a><img src="{html.escape(n)}" alt="{html.escape(n[:-4])}"></section>' for n in figures)
    (root/'charts.html').write_text(gallery,encoding='utf8');shutil.copyfile(__file__,root/'analysis_source.py')
    names=['summary.json','exposure_audit.json','signal_activity.json','uncertainty.json','contrasts.json','old_vs_audited.json','etf_return_corrections.json','benchmarks.json','benchmark_input_hashes.json','scatter_observations.json','scatter_observations.csv','scatter_correlations.json','scatter_matched_comparison.json','report.md','charts.html','analysis_source.py',*figures,*[n[:-4]+'.svg' for n in figures]]
    names.append('coverage_decomposition.json')
    manifest={n:sha256(root/n) for n in names};write_json(root/'analysis_manifest.json',manifest)
    store=AnalyticsStore.from_settings(AppSettings());store.client.timeout_seconds=120
    observations=[observation(n+'/'+w,'research_constituent_backtest',n,dict(period=w,**r)) for n,windows in summary.items() for w,r in windows.items()]
    observations += [observation(w+'/'+n,'research_constituent_contrast',n,dict(period=w,**r)) for w,series in contrasts.items() for n,r in series.items()]
    observations += [observation(r['date'],'research_governed_scatter','IVV_cohort',r,r['date']) for r in records]
    docs=[dict(point_key=n,media_type='text/markdown' if n.endswith('.md') else 'application/json',payload=(root/n).read_text(encoding='utf8')) for n in names if n.endswith(('.json','.md')) and n!='scatter_observations.json']
    version=digest(encode(manifest));destination='constituent-research/'+root.name+'/results'
    store.publish(destination,version,observations,docs,provenance=dict(governed_batch=protocol['batch'],all_native_parity_passed=True,research_only=True,analysis_manifest=manifest))
    write_json(root/'results_clickhouse_receipt.json',dict(source_id=destination,version=version,observations=len(observations),documents=len(docs),verification='Exact payload SHA256 readback'))
    registry=PostgresStore.from_settings(AppSettings())
    write_json(root/'registry_receipt.json',{n:register_run(registry,root/'runs'/n) for n in economies})
    print((root/'report.md').read_text(encoding='utf8'),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--root',type=Path,required=True)
    main(parser.parse_args().root)
