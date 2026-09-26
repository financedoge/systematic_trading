"""Analyze every frozen ten-year LEAN trial, including coverage and matched controls."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime
from pathlib import Path
import shutil
import sys

import numpy as np

from prepare_long_constituent_features import read_json
from run_constituent_research import verify_manifest
from analyze_constituent_research import information_ratio
from analyze_constituent_integration import audit_exposure, PAIRS
from analyze_flow_concentration_research import metrics, return_vector, block_audit
from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, verify_bundle, write_json
from systematic_trading.lean.registry import register_run
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.analytics_projection import observation
from systematic_trading.research.sector_hhi import correlations
from systematic_trading.storage.postgres import PostgresStore


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--root',type=Path,required=True)
    args=p.parse_args();root=args.root
    verify_manifest(root,'input_manifest.json')
    protocol,progress=read_json(root/'protocol.json'),read_json(root/'progress.json')
    if not progress['complete']:
        raise ValueError('Every declared trial must complete before analysis')
    economies={}
    for n,h in progress['passed'].items():
        verify_bundle(root/'datasets'/n)
        receipt=read_json(root/'runs'/n/'run.json')
        if receipt['status']!='succeeded' or receipt['economic_sha256']!=h or not read_json(root/'runs'/n/'parity.json')['passed']:
            raise ValueError('Native parity/receipt failure: '+n)
        for name,expected in receipt['artifacts'].items():
            if sha256(root/'runs'/n/name)!=expected:
                raise ValueError('Changed native artifact: '+n+'/'+name)
        economies[n]=read_json(root/'runs'/n/'economic.json')
    days=np.array([r['date'] for r in economies['sota']['nav']])
    if any([r['date'] for r in e['nav']]!=list(days) for e in economies.values()):
        raise ValueError('Unmatched calendar sessions')
    vectors={n:return_vector(e['nav']) for n,e in economies.items()}
    windows=dict(full=(protocol['start'],protocol['end']),early2016_19=('2016-01-01','2019-12-31'),
        stress2020_22=('2020-01-01','2022-12-31'),reused_post2023=('2023-01-01',protocol['end']),
        **{str(y):(f'{y}-01-01',f'{y}-12-31') for y in range(2016,2027)})
    features=read_json(root/'features.json');yahoo=read_json(root/'features_yahoo_only.json')
    quotes=read_json(root/'datasets/sota/quotes.json')
    summary,exposures,activity={},{},{}
    for n,e in economies.items():
        base='sota'+('__'+n.split('__')[1] if '__' in n else '')
        summary[n]={}
        for w,(start,end) in windows.items():
            m,b=metrics(e,start,end),metrics(economies[base],start,end)
            mask=(days>=start)&(days<=end)
            summary[n][w]=dict(**m,**information_ratio((vectors[n]-vectors[base])[mask]),cagr_delta=m['cagr']-b['cagr'],
                               sharpe_delta=m['sharpe']-b['sharpe'],comparator=base)
        cfg=protocol['trials'][n.split('__')[0]]
        feature_set=yahoo if n.split('__')[0] in protocol.get('feature_sets',{}) else features
        exposures[n]=audit_exposure(e,economies[base],quotes,feature_set,cfg)
        if exposures[n]['max_active_weight']>.03000001 or exposures[n]['max_target_gross_difference']>1e-8:
            raise ValueError('Active/gross risk limits differ: '+n)
        records=[]
        for d,r in e['decisions'].items():
            spec=cfg or {}
            f=feature_set[str(spec.get('holdings_lag_days',45))].get(r['known_through'])
            qualified=bool(f and f['scores'] is not None and f['value_coverage']>=spec.get('min_value_coverage',.95) and f['name_coverage']>=.7)
            records.append(dict(date=d,known_through=r['known_through'],qualified=qualified,
                value_coverage=f['value_coverage'] if f else None,name_coverage=f['name_coverage'] if f else None,
                snapshot=f['snapshot'] if f else None))
        good=[r['date'] for r in records if r['qualified']]
        activity[n]=dict(decisions=len(records),qualified=len(good),first_qualified=good[0] if good else None,
            last_qualified=good[-1] if good else None,unqualified=[r['date'] for r in records if not r['qualified']],records=records)
    candidates=[n for n in protocol['trials'] if n!='sota']
    pairs=dict(PAIRS,yahoo90_signed_vs_price=('early_signed_yahoo90','early_price_yahoo90'))
    uncertainty,comparisons={},{}
    for w in ('full','early2016_19','stress2020_22','reused_post2023'):
        start,end=windows[w];mask=(days>=start)&(days<=end)
        matrix=np.column_stack([vectors[n]-vectors['sota'] for n in candidates])[mask]
        uncertainty[w]={str(block):block_audit(matrix,candidates,block=block) for block in (63,126)}
        matrix=np.column_stack([vectors[a]-vectors[b] for a,b in pairs.values()])[mask]
        audit=block_audit(matrix,list(pairs),block=63)
        comparisons[w]={key:dict(**information_ratio(matrix[:,i]),cagr_delta=summary[a][w]['cagr']-summary[b][w]['cagr'],
            sharpe_delta=summary[a][w]['sharpe']-summary[b][w]['sharpe'],bootstrap=audit['trials'][key]) for i,(key,(a,b)) in enumerate(pairs.items())}
    for name,data in [('summary',summary),('exposure_audit',exposures),('signal_activity',activity),('uncertainty',uncertainty),('comparisons',comparisons)]:
        write_json(root/(name+'.json'),data)
    with (root/'daily_returns.csv').open('w',newline='',encoding='utf8') as f:
        w=csv.writer(f);w.writerow(['date',*vectors]);w.writerows([d,*[v[i] for v in vectors.values()]] for i,d in enumerate(days))
    sys.path.insert(0,'D:/systematic_trading_data/lean/research/plot_dependencies')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter, MaxNLocator
    plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False})
    fig,axes=plt.subplots(2,2,figsize=(16,10))
    stamps=[datetime.fromisoformat(d) for d in days]
    for n in ('sota','early_signed','early_breadth','tree_joint'):
        axes[0,0].plot(stamps,np.cumprod(1+vectors[n]),label=n,lw=1.2)
    axes[0,0].set_title('Net wealth: same recipe with annual causal tree fits');axes[0,0].legend(frameon=False,fontsize=8)
    for n in ('late_signed','early_signed','early_breadth','selection_signed','tree_joint','early_price'):
        axes[0,1].plot(stamps,np.cumprod(1+vectors[n])/np.cumprod(1+vectors['sota'])-1,label=n,lw=1.2)
    axes[0,1].set_title('Relative wealth vs matched historical baseline');axes[0,1].yaxis.set_major_formatter(PercentFormatter(1));axes[0,1].legend(frameon=False,fontsize=8,ncol=2)
    vals=[summary[n]['full']['information_ratio'] or 0 for n in candidates]
    axes[1,0].barh(candidates,vals,color=['#0891b2' if v>0 else '#b45309' for v in vals]);axes[1,0].axvline(0,color='#64748b',lw=.8)
    axes[1,0].set_title('Full-period information ratio vs matched baseline')
    records=activity['sota']['records']
    axes[1,1].plot([datetime.fromisoformat(r['date']) for r in records],[r['value_coverage'] if r['value_coverage'] is not None else np.nan for r in records],label='Holding-value coverage')
    bad=[r for r in records if not r['qualified']]
    axes[1,1].scatter([datetime.fromisoformat(r['date']) for r in bad],[.9]*len(bad),color='#b45309',marker='x',label='Neutral / unavailable months')
    axes[1,1].axhline(.95,color='#64748b',ls='--');axes[1,1].yaxis.set_major_formatter(PercentFormatter(1));axes[1,1].set_ylim(.89,1.01)
    axes[1,1].set_title('Actual signal availability; missing dates stay neutral');axes[1,1].legend(frameon=False,fontsize=8)
    fig.suptitle('Constituent information over 10.7 years',x=.04,ha='left',fontsize=20,weight='bold')
    fig.text(.04,.935,'2016-01-04 to 2026-09-24 | Native LEAN | Public IVV proxy | Revised vintages and assumed publication lag | Research only',fontsize=10,color='#475569')
    fig.tight_layout(rect=(.02,.02,1,.91),w_pad=3,h_pad=3);fig.savefig(root/'results.png',dpi=160);plt.close(fig)
    # Long-period descriptive HHI diagnostic; overlapping horizons are not independent trials.
    spy=read_json(Path(protocol['etf_snapshot'])/'bars.json')['SPY'];index={r['trade_date']:i for i,r in enumerate(spy)}
    keys=['hhi_smoothed','hhi_velocity','hhi_acceleration'];ic={};fig,axes=plt.subplots(3,3,figsize=(14,11))
    for i,key in enumerate(keys):
        ic[key]={}
        for j,h in enumerate((20,60,120)):
            xy=[(r['values'][key],float(spy[index[d]+h]['close'])/float(spy[index[d]]['close'])-1) for d,r in features['45'].items()
                if d>=protocol['start'] and d in index and index[d]+h<len(spy) and r['scores'] is not None and r['value_coverage']>=.95 and r['name_coverage']>=.7]
            x,y=np.array(xy).T;ic[key][str(h)]=correlations(x,y)
            axes[i,j].scatter(x,y,s=4,alpha=.15,color='#2563eb');axes[i,j].axhline(0,color='#94a3b8',lw=.6)
            label={'hhi_smoothed':'Smoothed HHI','hhi_velocity':'First derivative','hhi_acceleration':'Second derivative'}[key]
            axes[i,j].set_title(f'{label} / next {h} sessions\nPearson {np.corrcoef(x,y)[0,1]:+.3f} | n={len(x)}',fontsize=10)
            axes[i,j].yaxis.set_major_formatter(PercentFormatter(1))
            axes[i,j].xaxis.set_major_locator(MaxNLocator(5))
            axes[i,j].ticklabel_format(axis='x',style='sci',scilimits=(-3,3))
    fig.suptitle('Sector activity concentration vs subsequent SPY returns',fontsize=18)
    fig.text(.05,.945,'95% coverage only | Same-index stock proxy | Smoothed HHI and backward derivatives | Overlapping outcomes: descriptive correlation',fontsize=10)
    fig.tight_layout(rect=(.02,.02,1,.925));fig.savefig(root/'hhi_scatter.png',dpi=150);plt.close(fig)
    write_json(root/'hhi_correlations.json',ic)
    lines=['# Ten-year constituent study','',f"Period: {protocol['start']} through {protocol['end']}. Native LEAN; net CNH adjusted-unit scenario, 5bps transaction cost, zero-hurdle Sharpe. Annual expanding base trees use only completed historical labels. This is a historical reconstruction of the current recipe, not the deployed frozen tree or an untouched holdout. No promotion.",'',
        f"The primary95% rule qualifies {activity['sota']['qualified']} of {activity['sota']['decisions']} monthly decisions; first {activity['sota']['first_qualified']}. Unqualified decisions: {', '.join(activity['sota']['unqualified'])}. The full test spans10.7years; do not interpret fallback months as constituent evidence.",'',
        '| Variant | CAGR | Sharpe | IR | Delta CAGR pp | Changed decisions |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for n in protocol['trials']:
        m=summary[n]['full'];ir='n/a' if m['information_ratio'] is None else f"{m['information_ratio']:+.3f}"
        lines.append(f"| {n} | {m['cagr']:.2%} | {m['sharpe']:.3f} | {ir} | {100*m['cagr_delta']:+.3f} | {exposures[n]['changed_decisions']} |")
    lines+=['','## Period consistency','','| Period | Baseline CAGR / Sharpe | Early signed | Early breadth | Joint tree |','| --- | --- | --- | --- | --- |']
    for w in ('early2016_19','stress2020_22','reused_post2023','2020','2022'):
        lines.append('| '+w+' | '+' | '.join(f"{summary[n][w]['cagr']:.2%} / {summary[n][w]['sharpe']:.3f}" for n in ('sota','early_signed','early_breadth','tree_joint'))+' |')
    lines+=['','## Direct controls','','| Comparison | Delta CAGR pp | Active IR | 95% annual active-return interval pp | Adjusted p |','| --- | ---: | ---: | --- | ---: |']
    for n,m in comparisons['full'].items():
        ir='n/a' if m['information_ratio'] is None else f"{m['information_ratio']:+.3f}";b=m['bootstrap'];lo,hi=b['ci95']
        lines.append(f"| {n} | {100*m['cagr_delta']:+.3f} | {ir} | [{100*lo:+.3f}, {100*hi:+.3f}] | {b['max_t_family_adjusted_p']:.3f} |")
    lines+=['','## Robustness','','| Scenario | Baseline CAGR / Sharpe | Early signed | Early price |','| --- | --- | --- | --- |']
    for stress in protocol['stresses']:
        lines.append('| '+stress+' | '+' | '.join(f"{summary[n+'__'+stress]['full']['cagr']:.2%} / {summary[n+'__'+stress]['full']['sharpe']:.3f}" for n in ('sota','early_signed','early_price'))+' |')
    lines+=['','## Evidence limits','',
        '- Old ITOT signal history first qualified January2023 under95%-value/70%-names/211-session rules. Earlier dates in that test were neutral fallbacks. New dated IVV holdings and archived stock histories recover substantial2016+coverage. IVV tracks the same index as SPY; this does not represent the entire US or global market.',
        '- Historical issuer publication/revision dates remain unknown;45/60calendar-day lags are assumptions. Missing holdings older than140days are rejected. Current-provider data is preferred, then Yahoo2020, then Stooq2017, with one coherent provider per stock/window. Missing stocks stay in denominators.',
        '- Stooq supplied about4.2% of holding value in2016 and3.5% in2017. Its prices are dividend/split-adjusted; activity is a mixed-convention proxy, not literal fund flows. Yahoo-only90% results deliberately use a lower coverage rule and do not independently validate the primary95% input. No primary threshold was lowered.',
        '- Base tree: same features/depth/leaf limits and allocation recipe, annual expanding fits. Labels end strictly before fit date and models are only used when available by the prior close. January fits first enter this monthly adapter in February. The frozen production tree was fitted through2022 and would leak future labels if replayed unchanged in2016.',
        f"- Joint/price residual trees first have a dated model at {exposures['tree_joint']['first_tree_decision']}; early test months without a model are baseline. Correction and3pp exposure bounds unchanged. Tree-only effective evidence is shorter than the full10.7-year backtest.",
        '- Candidate/hyperparameter selection already used previously inspected results.63/126-session paired block intervals and family max-t checks do not repair research-selection bias, unknown corporate-action vintages, delisted-history gaps or nonstationarity. Positive sample IR is not enough for promotion.',
        '- Public raw histories, exact source CSVs, download failures, signals, training labels, models and results are archived with hash verification in ClickHouse. Native LEAN receipts are research-only entries in PostgreSQL. No live strategy or approval policy changed.','',
        'Sources: [dated IVV issuer holdings](https://www.ishares.com/us/products/239726/ishares-core-sp-500-etf), [Yahoo2020 archive](https://www.kaggle.com/datasets/jacksoncrow/stock-market-dataset), [Stooq2017 archive and adjustment convention](https://www.kaggle.com/datasets/borismarjanovic/price-volume-data-for-all-us-stocks-etfs/versions/3).','']
    (root/'report.md').write_text('\n'.join(lines),encoding='utf8')
    shutil.copyfile(__file__,root/'analysis_source.py')
    names=['summary.json','exposure_audit.json','signal_activity.json','uncertainty.json','comparisons.json','hhi_correlations.json','daily_returns.csv','results.png','hhi_scatter.png','report.md','analysis_source.py']
    write_json(root/'analysis_manifest.json',{n:sha256(root/n) for n in names})
    store=AnalyticsStore.from_settings(AppSettings());store.client.timeout_seconds=120
    obs=[observation(n+'/'+w,'research_constituent_backtest',n,dict(period=w,**r)) for n,periods in summary.items() for w,r in periods.items()]
    obs += [observation(w+'/'+n,'research_constituent_contrast',n,dict(period=w,**r)) for w,pairs in comparisons.items() for n,r in pairs.items()]
    docs=[dict(point_key=n,media_type='text/markdown' if n.endswith('.md') else 'application/json',payload=(root/n).read_text(encoding='utf8')) for n in names if n.endswith(('.json','.md'))]
    version=digest(encode(read_json(root/'analysis_manifest.json')))
    store.publish('constituent-research/'+root.name+'/results',version,obs,docs,provenance=dict(research_only=True,all_native_parity_passed=True,chronological_base_tree=True))
    write_json(root/'results_clickhouse_receipt.json',dict(version=version,observations=len(obs),documents=len(docs)))
    registry=PostgresStore.from_settings(AppSettings())
    write_json(root/'registry_receipt.json',{n:register_run(registry,root/'runs'/n) for n in economies})
    print((root/'report.md').read_text(encoding='utf8'),flush=True)


if __name__=='__main__':
    main()
