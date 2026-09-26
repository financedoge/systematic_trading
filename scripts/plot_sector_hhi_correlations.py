"""Make HHI/derivative versus forward-return scatter plots from frozen sector data."""
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
from systematic_trading.lean.contracts import sha256,write_json
from systematic_trading.research.sector_hhi import (
    volume_hhi,causal_ema,lagged_derivatives,forward_returns,correlations,correlation_block_interval,
)

HORIZONS=(20,60,120)
FEATURES=('HHI','first_derivative','second_derivative')


def make_scatter(plt,root,dates,features,returns,target,measure,smoothing,statistics):
    titles={'SPY':'S&P 500 (SPY)','equal_weight_sectors':'Equal-weight sector basket'}
    target_title=titles.get(target,target)
    mode='Daily HHI · backward 1-session differences' if smoothing=='raw' else 'EMA(10) HHI · backward 10-session differences'
    definition='Share-volume HHI' if measure=='share_volume' else 'Dollar-volume HHI (price × volume proxy)'
    fig,axes=plt.subplots(3,3,figsize=(15,11.5),sharey='col')
    labels=['HHI level','First derivative (HHI × 10³ / session)','Second derivative (HHI × 10³ / session²)']
    scale=[1,1000,1000]
    post=np.array(dates)>='2023-01-01'
    for i,(feature,multiplier) in enumerate(zip(FEATURES,scale)):
        x=features[:,i]*multiplier
        for j,horizon in enumerate(HORIZONS):
            ax=axes[i,j];y=returns[:,j]*100
            ax.scatter(x[~post],y[~post],s=9,alpha=.23,c='#64748b',edgecolors='none',rasterized=True)
            ax.scatter(x[post],y[post],s=9,alpha=.30,c='#0891b2',edgecolors='none',rasterized=True)
            fit=np.polyfit(x,y,1)
            xx=np.linspace(min(x),max(x),100)
            ax.plot(xx,np.polyval(fit,xx),color='#1e293b',linewidth=1.3)
            order=np.argsort(x)
            bins=np.array_split(order,5)
            ax.plot([np.mean(x[b]) for b in bins],[np.mean(y[b]) for b in bins],
                    color='#d97706',marker='o',markersize=4,linewidth=1.4)
            ax.axhline(0,color='#94a3b8',linewidth=.7)
            if i: ax.axvline(0,color='#cbd5e1',linewidth=.6)
            s=statistics[feature][str(horizon)]['full']
            ax.text(.035,.97,f"Pearson r = {s['pearson']:+.3f}   Spearman ρ = {s['spearman']:+.3f}\nn = {s['n']:,}",
                    transform=ax.transAxes,va='top',fontsize=9,
                    bbox=dict(facecolor='white',edgecolor='none',alpha=.88,pad=3))
            if i==0: ax.set_title(f'Next {horizon} sessions',fontsize=12,pad=12)
            ax.set_xlabel(labels[i],fontsize=9)
            if j==0: ax.set_ylabel('Forward return (%)')
            ax.grid(alpha=.15,linewidth=.5)
            ax.tick_params(labelsize=8)
    fig.suptitle(f'Sector trading concentration → subsequent {target_title} return',
                 x=.07,y=.975,ha='left',fontsize=20,fontweight='bold')
    fig.text(.07,.935,f'{definition}  |  {mode}',fontsize=12,color='#475569')
    fig.text(.07,.905,f'11 sector ETFs · Signal dates {dates[0]}–{dates[-1]} · Same dates in all panels · USD adjusted-close returns',fontsize=10,color='#475569')
    fig.text(.07,.038,'Gray: 2019–2022   •   Teal: 2023 onward   •   Black: linear fit   •   Orange: five equal-count bin means',fontsize=10,color='#475569')
    fig.text(.07,.016,'Returns overlap, so dots are not independent. Descriptive correlation only; ETF volume is not net flow or underlying-sector turnover.',fontsize=9,color='#64748b')
    fig.subplots_adjust(left=.07,right=.975,top=.86,bottom=.10,hspace=.31,wspace=.18)
    path=root/'plots'/f'{target}__{measure}__{smoothing}'
    fig.savefig(path.with_suffix('.png'),dpi=145)
    if target in ('SPY','equal_weight_sectors'):
        fig.savefig(path.with_suffix('.svg'),dpi=145)
    plt.close(fig)
    return path.with_suffix('.png').relative_to(root).as_posix()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--plot-deps',type=Path)
    args=parser.parse_args()
    root=args.root
    if args.plot_deps: sys.path.insert(0,str(args.plot_deps))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.ticker import PercentFormatter
    for name,digest in json.loads((root/'manifest.json').read_text()).items():
        if sha256(root/name)!=digest: raise ValueError('Frozen data changed: '+name)
    protocol=json.loads((root/'protocol.json').read_text())
    data=json.loads((root/'data.json').read_text())
    sectors=list(protocol['sectors'])
    dates=np.array([r['date'] for r in data['SPY']])
    volume=np.column_stack([[r['volume'] for r in data[s]] for s in sectors])
    price=np.column_stack([[r['close'] for r in data[s]] for s in sectors])
    adjusted={s:np.array([r['adj_close'] for r in rows]) for s,rows in data.items()}
    fwd={s:np.column_stack([forward_returns(values,h) for h in HORIZONS]) for s,values in adjusted.items()}
    fwd['equal_weight_sectors']=np.mean(np.stack([fwd[s] for s in sectors]),axis=0)
    common=(dates>=protocol['start']) & np.isfinite(fwd['SPY']).all(axis=1)
    common_dates=dates[common]
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                        'axes.spines.right':False,'axes.facecolor':'#f8fafc','figure.facecolor':'#f8fafc',
                        'axes.edgecolor':'#cbd5e1','text.color':'#0f172a','xtick.color':'#475569','ytick.color':'#475569'})
    (root/'plots').mkdir(exist_ok=True)
    results,panels,gallery={},{},[]
    for measure,activity in [('share_volume',volume),('dollar_volume',volume*price)]:
        hhi=volume_hhi(activity)
        for smoothing in ('raw','smoothed'):
            values=hhi if smoothing=='raw' else causal_ema(hhi,10)
            d1,d2=lagged_derivatives(values,1 if smoothing=='raw' else 10)
            feature=np.column_stack([values,d1,d2])
            panels[f'{measure}__{smoothing}']=feature
            results.setdefault(measure,{})[smoothing]={}
            for target,returns in fwd.items():
                statistics={}
                for i,name in enumerate(FEATURES):
                    statistics[name]={}
                    for j,horizon in enumerate(HORIZONS):
                        x,y=feature[:,i][common],returns[:,j][common]
                        row={'full':correlations(x,y)}
                        for period,mask in [('pre2023',common_dates<'2023-01-01'),('post2023',common_dates>='2023-01-01')]:
                            row[period]=correlations(x[mask],y[mask])
                        row['nonoverlapping_phase0']=correlations(x[::horizon],y[::horizon])
                        if target in ('SPY','equal_weight_sectors'):
                            row['pearson_block_ci95']=correlation_block_interval(x,y)
                        statistics[name][str(horizon)]=row
                results[measure][smoothing][target]=statistics
                # Full 9-panel grids for market/basket under every definition and each sector's own return under raw share HHI.
                if target in ('SPY','equal_weight_sectors') or (measure=='share_volume' and smoothing=='raw'):
                    path=make_scatter(plt,root,common_dates,feature[common],returns[common],target,measure,smoothing,statistics)
                    gallery.append(dict(label=f'{target} · {measure.replace("_"," ")} · {smoothing}',path=path))
    # HHI timeline plus subsequent returns; latest unavailable labels are left missing.
    fig,axes=plt.subplots(4,1,figsize=(15,10),sharex=True)
    show=dates>=protocol['start']; stamps=[datetime.fromisoformat(d) for d in dates[show]]
    axes[0].plot(stamps,panels['share_volume__raw'][show,0],color='#94a3b8',linewidth=.65,alpha=.7,label='Daily HHI')
    axes[0].plot(stamps,panels['share_volume__smoothed'][show,0],color='#0284c7',linewidth=1.5,label='EMA(10) HHI')
    axes[0].axhline(1/11,color='#64748b',linestyle=':',linewidth=.8,label='Equal volume: 1/11')
    axes[0].set_ylabel('Volume HHI');axes[0].legend(frameon=False,ncol=3,loc='upper left',fontsize=9)
    for i,h in enumerate(HORIZONS,1):
        y=fwd['SPY'][show,i-1]
        axes[i].plot(stamps,y,color='#0891b2',linewidth=1)
        axes[i].axhline(0,color='#94a3b8',linewidth=.7)
        axes[i].set_ylabel(f'Next {h} sessions\nSPY return')
        axes[i].yaxis.set_major_formatter(PercentFormatter(1,decimals=0))
    for ax in axes:
        ax.grid(axis='y',alpha=.2)
        ax.axvline(datetime.fromisoformat(common_dates[-1]),color='#d97706',linestyle='--',linewidth=.8)
    axes[-1].xaxis.set_major_locator(mdates.YearLocator());axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    fig.suptitle('Sector-volume concentration and subsequent market returns',x=.08,ha='left',fontsize=20,fontweight='bold')
    fig.text(.08,.925,'11 sector ETFs · HHI = Σ(volume share²) · USD adjusted-close SPY returns',fontsize=12,color='#475569')
    fig.text(.08,.025,'Orange dashed line: final common scatter date. Missing forward returns at the right edge are not filled.\nVolume is ETF trading activity, not capital inflow. Share-volume HHI is sensitive to ETF units and splits.',fontsize=10,color='#475569')
    fig.subplots_adjust(top=.88,left=.08,right=.97,bottom=.11,hspace=.12)
    fig.savefig(root/'plots'/'timeline.png',dpi=145);fig.savefig(root/'plots'/'timeline.svg');plt.close(fig)
    # Sector-specific return correlations to the same aggregate HHI; no pooled pseudo-replication.
    fig,axes=plt.subplots(3,1,figsize=(14,8),sharex=True)
    for i,name in enumerate(FEATURES):
        matrix=np.array([[results['share_volume']['raw'][s][name][str(h)]['full']['pearson'] for s in sectors] for h in HORIZONS])
        axes[i].imshow(matrix,cmap='RdBu',vmin=-.35,vmax=.35,aspect='auto')
        for row in range(3):
            for col in range(11): axes[i].text(col,row,f'{matrix[row,col]:+.2f}',ha='center',va='center',fontsize=10)
        axes[i].set_yticks([0,1,2],['20d','60d','120d']);axes[i].set_title(name.replace('_',' '),loc='left',fontsize=12)
        axes[i].grid(False)
    axes[-1].set_xticks(range(11),sectors)
    fig.suptitle('Aggregate sector-volume HHI vs each sector’s own forward return',x=.08,ha='left',fontsize=18,fontweight='bold')
    fig.text(.08,.92,'Pearson correlations · Raw daily HHI and 1-session differences · Same common dates · Descriptive, overlapping outcomes',fontsize=10,color='#475569')
    fig.subplots_adjust(left=.08,right=.97,top=.86,bottom=.08,hspace=.4)
    fig.savefig(root/'plots'/'sector_correlations.png',dpi=145);plt.close(fig)
    write_json(root/'correlations.json',dict(common_start=str(common_dates[0]),common_end=str(common_dates[-1]),
        observations=int(common.sum()),results=results,warning=protocol['warning']))
    with (root/'observations.csv').open('w',newline='',encoding='utf-8') as f:
        columns=['date',*[f'{key}_{feature}' for key in panels for feature in FEATURES],
                 *[f'{target}_forward_{h}' for target in fwd for h in HORIZONS]]
        writer=csv.writer(f);writer.writerow(columns)
        for i,d in enumerate(dates):
            if not show[i]: continue
            vals=[d,*[v[i,j] for v in panels.values() for j in range(3)],*[v[i,j] for v in fwd.values() for j in range(3)]]
            writer.writerow(['' if isinstance(v,(float,np.floating)) and not np.isfinite(v) else v for v in vals])
    lines=['# Sector-volume HHI and forward returns','',f'Common scatter sample: {common_dates[0]}–{common_dates[-1]} ({common.sum():,} observations). Raw data ends {dates[-1]}.','',
        'HHI = sum of squared sector ETF volume shares across 11 sector SPDRs. These are ETF-volume proxies, not all constituent trading or net flows. Raw derivatives use backward 1-session differences; smoothed sensitivity uses EMA(10) and lag-10 differences. Forward return is adjusted close[t+h]/adjusted close[t]-1 in USD, not annualized. Equal-weight basket is equal capital at the signal date, held for the horizon.','',
        'All scatter panels use identical dates with observed 120-session outcomes. Later dates remain in the timeline, with unobserved outcomes missing. Orange lines connect equal-count quintile means; black lines are in-sample OLS fits, not forecast models. Gray/teal marks pre-/post-2023, not an untouched holdout.','',
        '## SPY correlations','', '| Definition | Feature | Horizon | Pearson r | Spearman rho | 95% paired-block interval for r |', '| --- | --- | ---: | ---: | ---: | --- |']
    for measure in results:
        for smoothing in results[measure]:
            for name in FEATURES:
                for h in HORIZONS:
                    item=results[measure][smoothing]['SPY'][name][str(h)];v=item['full'];ci=item['pearson_block_ci95']
                    lines.append(f'| {measure}/{smoothing} | {name} | {h} | {v["pearson"]:+.3f} | {v["spearman"]:+.3f} | [{ci[0]:+.3f}, {ci[1]:+.3f}] |')
    lines += ['', '## Interpretation limits','',
        '- Forward labels overlap. Reported n counts daily dots, not independent bets. Block intervals use 240-session circular blocks, 1,000 replicates and seed 20260926. They are exploratory and not corrected for the many comparisons.',
        '- Correlations.json includes separate pre-/post-2023 correlations and a phase-0 non-overlapping sample as diagnostics; results can depend on regimes and sampling phase.',
        '- Share-volume HHI is affected by ETF unit prices, splits and the vendor volume adjustment convention. The dollar-volume sensitivity uses provider close × volume (not dividend-adjusted close). Historical split-adjustment/vintage conventions remain uncertified.',
        '- The underlying sectors differ in ETF popularity, assets and liquidity; this is concentration in this fixed ETF basket, not the entire sector market. Historical constituents and investor subscriptions are not used.',
        '- Features at t use only observations through t. Returns are future descriptive labels, not a claim of execution at the same completed close. This is a correlation study, not a new LEAN trading backtest.', '',
        'Sources: Yahoo chart API raw responses, retrieval times, events and hashes are frozen locally. Official sector mapping: https://www.ssga.com/us/en/individual/capabilities/equities/sector-investing/select-sector-etfs . XLC began in June 2018, so use 2019 onward for the fixed eleven-sector comparison.', '',
        'Files: index.html (interactive plot selector), plots/ (PNG/SVG), observations.csv (all plotted variables and forward labels), correlations.json, data.json, raw/, provenance.json and manifest.json.', '']
    (root/'report.md').write_text('\n'.join(lines),encoding='utf-8')
    options=''.join(f'<option value="{html.escape(g["path"])}">{html.escape(g["label"])}</option>' for g in gallery)
    default='plots/SPY__share_volume__raw.png'
    page=f'''<!doctype html><html><head><meta charset="utf-8"><title>Sector HHI scatter plots</title><style>body{{font:16px system-ui;background:#f8fafc;color:#0f172a;max-width:1500px;margin:32px auto;padding:0 24px}}h1{{font-size:30px}}p{{color:#475569;line-height:1.6}}select{{padding:12px;font:inherit;min-width:440px}}img{{width:100%;height:auto}}a{{color:#0369a1}}.links{{display:flex;gap:24px}}</style></head><body><h1>Sector-volume concentration and subsequent returns</h1><p>HHI across 11 sector ETFs; first and second backward differences versus 20/60/120-session USD returns. Common signal dates: {common_dates[0]}–{common_dates[-1]}. Select SPY, the equal-weight basket, or a sector’s own return below.</p><p>Daily labels overlap: these are exploratory correlations, not independent observations or a trading backtest. Volume measures ETF activity, not net inflows.</p><label>Scatter grid: <select id="choice">{options}</select></label><img id="chart" src="{default}" alt="HHI and derivative scatter matrix"><div class="links"><a href="report.md">Methods and correlation intervals</a><a href="observations.csv">Download observations CSV</a><a href="correlations.json">All correlations JSON</a></div><h2>HHI and forward-return time series</h2><img src="plots/timeline.png" alt="HHI and subsequent SPY returns"><h2>Each sector’s own return</h2><img src="plots/sector_correlations.png" alt="Sector correlation heatmap"><script>const c=document.querySelector('#choice');c.value='{default}';c.addEventListener('change',()=>document.querySelector('#chart').src=c.value);</script></body></html>'''
    (root/'index.html').write_text(page,encoding='utf-8')
    shutil.copyfile(__file__,root/'plot_script.py')
    shutil.copyfile(Path(__file__).resolve().parents[1]/'src/systematic_trading/research/sector_hhi.py',root/'analysis_source.py')
    write_json(root/'analysis_manifest.json',{p.relative_to(root).as_posix():sha256(p) for p in root.rglob('*') if p.is_file() and p.name not in ('analysis_manifest.json',)})
    print(json.dumps(dict(start=str(common_dates[0]),end=str(common_dates[-1]),n=int(common.sum()),
        spy_raw=results['share_volume']['raw']['SPY'],spy_smoothed=results['share_volume']['smoothed']['SPY']),indent=2))


if __name__=='__main__': main()
