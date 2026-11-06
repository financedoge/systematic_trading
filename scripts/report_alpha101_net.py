"""Dated portfolio, cost, chronology and weakest-ETF review for six alpha retests."""
from datetime import date
from pathlib import Path
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import rankdata

import research_alpha101_net as s
from research_cash_relative_retest import gzread
from report_cash_relative_retest import money_prices, trade_lots, render_review, pct, num


def path(arm,cost=5,delay=0):
    return dict(np.load(s.WORK/'paths'/f'{arm}_c{cost}d{delay}.npz'))


def book(arm,a):
    economic=gzread(s.WORK/'detail'/f'{arm}_c5d0.json.gz')
    days=a['days'][a['days']>=s.START];symbols=a['symbols'].tolist()+['URTH']
    closes=money_prices(np.column_stack([a['close'],a['urth_close']]))[-len(days):]
    fills={}
    for f in economic['fills']:fills.setdefault(f['date'],[]).append(f)
    units=np.zeros(len(symbols));cash=1e6;held=[];error=0
    for t,d in enumerate(days):
        for f in fills.get(d,[]):
            units[symbols.index(f['symbol'])]+=f['quantity']
            cash-=f['quantity']*float(f['price'])+float(f['fee'])
        nav=cash+units@closes[t];error=max(error,abs(nav-float(economic['nav'][t]['nav'])))
        held.append(units*closes[t]/nav)
    if error>.03:raise ValueError('Independent cash/share ledger mismatch')
    return economic,np.array(held),error


def uncertainty(rows,days):
    out=[]
    for window in ('calibration','later'):
        a,b=s.WINDOWS[window];ix=np.flatnonzero((days>=a)&(days<=b));rng=np.random.default_rng(20261031)
        draw=np.concatenate([(rng.integers(0,len(ix),(4000,1))+np.arange(21))%len(ix)
                             for _ in range((len(ix)+20)//21)],axis=1)[:,:len(ix)]
        controls={}
        for row in rows:
            if not row['arm'].startswith('alpha') or row['cost_bp']!=5 or row['delay']!=0:continue
            policy=row['arm'].split('-')[1];control='momentum-'+policy;est=[]
            for arm in (row['arm'],control):
                if arm in controls:result=controls[arm]
                else:
                    nav=np.r_[1e6,path(arm)['nav']];r=(nav[1:]/nav[:-1]-1)[ix][draw]
                    std=r.std(axis=1,ddof=1)
                    result=np.column_stack([np.divide(r.mean(axis=1)*np.sqrt(252),std,out=np.zeros(len(r)),where=std>1e-12),
                                            np.exp(np.log1p(r).mean(axis=1)*252)-1])
                    if arm==control:controls[arm]=result
                est.append(result)
            diff=est[0]-est[1]
            out.append(dict(arm=row['arm'],control=control,window=window,columns=['Sharpe','CAGR'],
                ordinary_95=np.quantile(diff,[.025,.975],axis=0).tolist(),
                family_95=np.quantile(diff,[.025/24,1-.025/24],axis=0).tolist()))
    return out


def diagnostics(a,signals):
    out=[];days=a['days'];cube=signals['alpha']
    for j,alpha in enumerate(s.ALPHAS):
        for window in ('calibration','later'):
            start,end=s.WINDOWS[window]
            times=np.flatnonzero((days>=start)&(days<=end));coverage=[];ties=[]
            for t in times:
                mask=a['admitted'][t]&np.isfinite(cube[t,:,j]);v=cube[t,mask,j]
                coverage.append(len(v));ties.append(1-len(np.unique(np.round(v,12)))/len(v) if len(v) else 0)
            for h in (1,5,10,21):
                ic=[]
                for t in times:
                    if t+1+h>=len(days) or days[t+1+h]>end:continue
                    mask=a['admitted'][t]&np.isfinite(cube[t,:,j])
                    if mask.sum()<6:continue
                    x=cube[t,mask,j];y=a['open'][t+1+h,mask]/a['open'][t+1,mask]-1
                    if np.std(x)<1e-12 or np.std(y)<1e-12:continue
                    ic.append(float(np.corrcoef(rankdata(x),rankdata(y))[0,1]))
                out.append(dict(alpha=alpha,window=window,horizon=h,mean_ic=float(np.mean(ic)) if ic else None,
                    dates=len(ic),mean_eligible=float(np.mean(coverage)),mean_tied_fraction=float(np.mean(ties)),
                    note='Next-open to future-open gross labels, overlapping daily diagnostics, not a net-performance gate.'))
    return out


def write_csv(file,rows):
    with file.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def main():
    protocol=s.validate();rows=s.read(s.OUT/'results.json');selection=s.read(s.OUT/'selection.json')
    a=dict(np.load(s.WORK/'inputs.npz'));signals=dict(np.load(s.WORK/'signals.npz'));schedules=dict(np.load(s.WORK/'schedules.npz'))
    days=a['days'][a['days']>=s.START];symbols=a['symbols'].tolist()+['URTH'];chosen=selection['selected']
    control='momentum-'+chosen.split('-')[1];unranked='unranked-'+chosen.split('-')[1]
    main_arms=[(chosen,chosen),(control,'126-session momentum'),('FR25','FR25 incumbent')]
    cache={r['arm']:path(r['arm']) for r in rows if r['cost_bp']==5 and r['delay']==0}
    books={arm:book(arm,a) for arm,_ in main_arms};lookup={(r['arm'],r['cost_bp'],r['delay']):r for r in rows}
    comparisons=[]
    for r in rows:
        if not r['arm'].startswith('alpha'):continue
        policy=r['arm'].split('-')[1]
        for benchmark in ('momentum-'+policy,'unranked-'+policy,'FR25','cash','BIL_buyhold','URTH_buyhold','pool_buyhold'):
            base=lookup[benchmark,r['cost_bp'],r['delay']]
            for window in ('calibration','later'):
                x,y=r['windows'][window],base['windows'][window]
                comparisons.append(dict(arm=r['arm'],benchmark=benchmark,window=window,cost_bp=r['cost_bp'],delay=r['delay'],
                    passes=s.passes(x,y),sharpe_change=x['sharpe']-y['sharpe'],cagr_change=x['cagr']-y['cagr'],
                    drawdown_change=x['max_drawdown']-y['max_drawdown']))
    s.write(s.OUT/'comparisons.json',comparisons)
    intervals=uncertainty(rows,days);s.write(s.OUT/'uncertainty.json',intervals)
    diag=diagnostics(a,signals);s.write(s.OUT/'signal-diagnostics.json',diag)
    # Training-prefix policy ranks document instability, without changing final policy.
    stability=[]
    for y in range(2021,2025):
        for alpha in s.ALPHAS:
            stats={p:s.metric(days,cache[f'alpha{alpha}-{p}']['nav'],s.START,f'{y}-12-31') for p in s.POLICIES}
            winner=sorted(stats,key=lambda p:(-stats[p]['sharpe'],p))[0]
            stability.append(dict(alpha=alpha,training_end=f'{y}-12-31',policy=winner,metrics=stats))
    s.write(s.OUT/'training-stability.json',stability)
    attribution={};weak=[];individual=[]
    for window in ('calibration','later'):
        start,end=s.WINDOWS[window];ix=np.flatnonzero((days>=start)&(days<=end))
        for arm,_ in main_arms:
            values=cache[arm];opening=values['nav'][ix[0]-1] if ix[0] else 1e6
            table=[dict(symbol=symbol,net_pnl=float(values['contribution'][ix,j].sum()),
                net_contribution=float(values['contribution'][ix,j].sum()/opening),mean_held_weight=float(books[arm][1][ix,j].mean())) for j,symbol in enumerate(symbols)]
            table.sort(key=lambda r:(r['net_contribution'],r['symbol']));attribution[arm+'-'+window]=table
            assert abs(sum(r['net_contribution'] for r in table)-s.metric(days,values['nav'],start,end)['cumulative'])<1e-7
            if arm==chosen:weak.append(dict(window=window,**next(r for r in table if r['symbol'] not in ('BIL','URTH'))))
        fi=np.flatnonzero((a['days']>=start)&(a['days']<=end))
        for j,symbol in enumerate(a['symbols']):
            # Fresh same-era fractional buy-and-hold reference; entry fee, no hypothetical exit fee.
            nav=a['close'][fi,j]/a['open'][fi[0],j]/1.0005*1e6
            individual.append(dict(symbol=str(symbol),window=window,**s.metric(a['days'][fi],nav,start,end)))
    s.write(s.OUT/'attribution.json',attribution);s.write(s.OUT/'weakest.json',weak);s.write(s.OUT/'individual-buyhold.json',individual)
    closing=money_prices(np.r_[a['close'][-1],a['urth_close'][-1]])
    lots=trade_lots(books[chosen][0],dict(zip(symbols,closing)),s.END)
    assert abs(sum(r['net_pnl'] for r in lots)-(cache[chosen]['nav'][-1]-1e6))<.05
    s.write(s.OUT/'trade-outcomes.json',lots);write_csv(s.OUT/'trade-outcomes.csv',lots)
    dates=np.array([date.fromisoformat(d) for d in days]);colors=['#087f8c','#bd762b','#7149a3']
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
    fig,axes=plt.subplots(2,2,figsize=(14,8),layout='constrained')
    for col,window in enumerate(('calibration','later')):
        start,end=s.WINDOWS[window];ix=np.flatnonzero((days>=start)&(days<=end))
        for (arm,label),color in zip(main_arms,colors):
            nav=cache[arm]['nav'];opening=nav[ix[0]-1] if ix[0] else 1e6;trace=np.r_[opening,nav[ix]]
            axes[0,col].plot(dates[ix],100*(nav[ix]/opening-1),color=color,label=label)
            axes[1,col].plot(dates[ix],100*(trace/np.maximum.accumulate(trace)-1)[1:],color=color)
        axes[0,col].set_title(f'{window.title()} · {days[ix[0]]} to {days[ix[-1]]}');axes[0,col].legend(fontsize=8)
        axes[0,col].set_ylabel('Net return (%)');axes[1,col].set_ylabel('Drawdown (%)')
    for ax in axes.flat:ax.grid(alpha=.2)
    fig.suptitle('Standalone Alpha101 · training-selected policy and matched net references\nUSD · 5 bp per side · next-open fills · retrospective development evidence')
    fig.savefig(s.OUT/'comparison.png',dpi=140);plt.close(fig)
    for item in weak:
        symbol,window=item['symbol'],item['window'];j=symbols.index(symbol);start,end=s.WINDOWS[window]
        ix=np.flatnonzero((days>=start)&(days<=end));fi=np.flatnonzero(a['days']>=s.START)[ix]
        economic,held,_=books[chosen];fills=[f for f in economic['fills'] if f['symbol']==symbol and start<=f['date']<=end]
        fig,axes=plt.subplots(5,1,figsize=(14,12),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[2,1,1,1.3,1.2]})
        axes[0].plot(dates[ix],a['close'][fi,j],color='#293d59',label='Adjusted close')
        for buy,color,marker in [(True,'#00816a','^'),(False,'#c44550','v')]:
            f=[r for r in fills if (r['quantity']>0)==buy]
            axes[0].scatter([date.fromisoformat(r['date']) for r in f],[float(r['price']) for r in f],color=color,marker=marker,s=30,label='Buy fill' if buy else 'Sell fill',zorder=3)
        axes[0].set_ylabel('Adjusted USD');axes[0].legend(ncol=3)
        axes[1].plot(dates[ix],a['raw_close'][fi,j],color='#72604e');axes[1].set_ylabel('Audited raw\nclose USD')
        axes[2].bar(dates[ix],a['raw_volume'][fi,j]/1e6,width=2,color='#9faebb');axes[2].set_ylabel('Raw volume\nmillion')
        adopted=np.zeros(len(a['days']));last=0;events=set(schedules[chosen+'_indices'])
        for t in range(len(adopted)):
            if t-1 in events:last=schedules[chosen+'_weights'][t-1,j]
            adopted[t]=last
        axes[3].plot(dates[ix],100*schedules[chosen+'_weights'][fi,j],color='#a8b9c3',alpha=.5,label='Theoretical at close')
        axes[3].step(dates[ix],100*adopted[fi],where='post',color=colors[0],label='Adopted target')
        axes[3].plot(dates[ix],100*held[ix,j],color='#222222',alpha=.65,label='Held weight');axes[3].set_ylabel('Weight (%)');axes[3].legend(ncol=3,fontsize=8)
        for (arm,label),color in zip(main_arms,colors):
            v=cache[arm];base=v['nav'][ix[0]-1] if ix[0] else 1e6
            axes[4].plot(dates[ix],100*np.cumsum(v['contribution'][ix,j])/base,label=label,color=color)
        axes[4].set_ylabel('Net contribution\npp of opening NAV');axes[4].legend(fontsize=8)
        for ax in axes:ax.grid(alpha=.2)
        fig.suptitle(f'{symbol} · weakest risky contribution · {window}\n{days[ix[0]]} to {days[ix[-1]]} · {100*item["net_contribution"]:.2f} pp · {len(fills)} fills · no stop/protection')
        fig.savefig(s.OUT/f'weakest-{window}-{symbol}.png',dpi=130);plt.close(fig)
        traces=[]
        alpha_index=s.ALPHAS.index(chosen.split('-')[0][5:])
        for k,t in enumerate(fi):
            trades=[f for f in fills if f['date']==str(a['days'][t])]
            traces.append(dict(date=str(a['days'][t]),adjusted_open=a['open'][t,j],adjusted_high=a['high'][t,j],adjusted_low=a['low'][t,j],adjusted_close=a['close'][t,j],
                raw_close=a['raw_close'][t,j],raw_volume=a['raw_volume'][t,j],score=signals['alpha'][t,j,alpha_index],
                theoretical_at_close=schedules[chosen+'_weights'][t,j],adopted=adopted[t],held=held[ix[k],j],
                state='held' if held[ix[k],j]>0 else 'cash for this ETF',protection='none',
                fills='; '.join(f'{f["quantity"]}@{f["price"]} fee {f["fee"]}' for f in trades),
                net_contribution_usd=cache[chosen]['contribution'][ix[k],j]))
        write_csv(s.OUT/f'weakest-{window}-{symbol}-daily.csv',traces)
        write_csv(s.OUT/f'weakest-{window}-{symbol}-trades.csv',[r for r in lots if r['symbol']==symbol and r['entry']<=end and r['exit']>=start])
    def hits(arm,benchmark,window):
        return sum(r['passes'] for r in comparisons if r['arm']==arm and r['benchmark']==benchmark and r['window']==window)
    counts={w:{b:hits(chosen,b,w) for b in (control,unranked,'FR25','cash','BIL_buyhold','URTH_buyhold','pool_buyhold')} for w in ('calibration','later')}
    main_table=['| Policy | Period | Net return | CAGR | Sharpe | Max DD | Calmar | Turnover/yr | Fees USD |','| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for w in ('calibration','later'):
        for arm,label in main_arms:
            m=lookup[arm,5,0]['windows'][w]
            main_table.append(f'| {label} | {w} | {pct(m["cumulative"])} | {pct(m["cagr"])} | {num(m["sharpe"])} | {pct(m["max_drawdown"])} | {num(m["calmar"])} | {num(m["annual_turnover"])} | {m["fees_usd"]:,.0f} |')
    family=['| Signal | Training-selected timing | Training return / Sharpe | Later return / Sharpe / DD | Momentum guards early/later | Unranked guards early/later | FR25 guards early/later |','| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for alpha,arm in selection['per_alpha'].items():
        p=arm.split('-')[1];early=lookup[arm,5,0]['windows']['calibration'];late=lookup[arm,5,0]['windows']['later']
        cells=[f'{hits(arm,b,"calibration")}/6 ; {hits(arm,b,"later")}/6' for b in ('momentum-'+p,'unranked-'+p,'FR25')]
        family.append(f'| {alpha} | {p} | {pct(early["cumulative"])} / {num(early["sharpe"])} | {pct(late["cumulative"])} / {num(late["sharpe"])} / {pct(late["max_drawdown"])} | '+' | '.join(cells)+' |')
    guard_table=['| Reference | Calibration passed | Later passed |','| --- | ---: | ---: |']
    for b in (control,unranked,'FR25'):guard_table.append(f'| {b} | {counts["calibration"][b]}/6 | {counts["later"][b]}/6 |')
    benchmarks=['| Reference | Training return / Sharpe / DD | Later return / Sharpe / DD |','| --- | ---: | ---: |']
    for b in (unranked,'cash','BIL_buyhold','URTH_buyhold','pool_buyhold'):
        cells=[]
        for w in ('calibration','later'):
            m=lookup[b,5,0]['windows'][w];cells.append(f'{pct(m["cumulative"])} / {num(m["sharpe"])} / {pct(m["max_drawdown"])}')
        benchmarks.append('| '+b+' | '+' | '.join(cells)+' |')
    annual=['| Year | Selected return / Sharpe | Momentum return / Sharpe | FR25 return / Sharpe |','| --- | ---: | ---: | ---: |']
    for y in range(2021,2027):
        cells=[]
        for arm,_ in main_arms:
            m=lookup[arm,5,0]['windows'][str(y)];cells.append(f'{pct(m["cumulative"])} / {num(m["sharpe"])}')
        annual.append(f'| {y} | '+' | '.join(cells)+' |')
    stress=['| Fee bp | Extra sessions | Training return / Sharpe / DD | Later return / Sharpe / DD |','| --- | ---: | ---: | ---: |']
    for c,d in protocol['frictions']:
        cells=[]
        for w in ('calibration','later'):
            m=lookup[chosen,c,d]['windows'][w];cells.append(f'{pct(m["cumulative"])} / {num(m["sharpe"])} / {pct(m["max_drawdown"])}')
        stress.append(f'| {c} | {d} | '+' | '.join(cells)+' |')
    selected_intervals=[r for r in intervals if r['arm']==chosen]
    timing=['| Alpha54 timing | Training return / Sharpe | Later return / Sharpe | Training / later turnover per year |','| --- | ---: | ---: | ---: |']
    for policy in s.POLICIES:
        arm=chosen.split('-')[0]+'-'+policy
        early=lookup[arm,5,0]['windows']['calibration'];late=lookup[arm,5,0]['windows']['later']
        timing.append(f'| {policy} | {pct(early["cumulative"])} / {num(early["sharpe"])} | {pct(late["cumulative"])} / {num(late["sharpe"])} | {num(early["annual_turnover"])} / {num(late["annual_turnover"])} |')
    ic_table=['| Signal | Training / later 21-session IC | Training / later tied-score fraction | Training-prefix winning policies 2021/22/23/24 |','| --- | ---: | ---: | --- |']
    for alpha in s.ALPHAS:
        d=[next(x for x in diag if x['alpha']==alpha and x['window']==w and x['horizon']==21) for w in ('calibration','later')]
        policies=[r['policy'] for r in stability if r['alpha']==alpha]
        ic_table.append(f'| {alpha} | {num(d[0]["mean_ic"])} / {num(d[1]["mean_ic"])} | {pct(d[0]["mean_tied_fraction"])} / {pct(d[1]["mean_tied_fraction"])} | '+', '.join(policies)+' |')
    ci=['| Period | Family-adjusted Sharpe difference | Family-adjusted CAGR difference |','| --- | ---: | ---: |']
    for r in selected_intervals:
        x=r['family_95'];ci.append(f'| {r["window"]} | {x[0][0]:.3f} to {x[1][0]:.3f} | {pct(x[0][1])} to {pct(x[1][1])} |')
    weak_text=[]
    for r in weak:
        stem=f'weakest-{r["window"]}-{r["symbol"]}'
        weak_text.append(f'### {r["window"].title()}: {r["symbol"]}, {100*r["net_contribution"]:.2f} pp\n\n![Dated {r["symbol"]} inspection]({stem}.png)\n\n[Every dated observation and fill]({stem}-daily.csv) · [FIFO outcomes overlapping this era]({stem}-trades.csv). The trade file marks open lots at October 30 and includes complete cross-era lots; its summed P&L is not the era contribution.')
    leaders={}
    for w in ('calibration','later'):
        table=attribution['FR25-'+w];leaders[w]=dict(best=table[-3:][::-1],worst=table[:3])
    s.write(s.OUT/'incumbent-dependence.json',leaders)
    verdict=('The training-selected candidate does not robustly improve both matched simple controls across the two eras. '
             'Retain the completed experiment as evidence; no standalone candidate is established for promotion.')
    body=f'''# Six standalone Alpha101 net retests — October 31, 2026

{verdict}

**Completed: {len(rows)} net cases, six formulas, four timing policies and six friction settings.** All formerly cost-excluded formulas received full portfolio replays. The globally training-selected policy is **{chosen}**. Each formula also has its own training-selected timing below. No later winner changes those selections. This is a new full-pool experiment, not an exact reproduction of the old 14-ETF cost screen.

## Main comparison

{chr(10).join(main_table)}

![Selected policy, matching momentum and incumbent](comparison.png)

## All six signals

{chr(10).join(family)}

Each guard requires strictly higher net Sharpe, CAGR no more than 0.5 percentage points lower and drawdown no more than 2 points worse. A count spans 5/10/20 bp and zero/one extra execution session. Counts are sensitivity evidence, not six independent discoveries. No annual cost ceiling or IC veto was applied.

## Full decision flow and definitions

Published audited batch and identity checks → complete supported price/raw-volume calendar → completed-close 253-session warmup and prior-63-session liquidity/duplicate admission → original Alpha101 score for each eligible risky ETF → highest six scores → inverse 63-return sample volatility weights with 98% budget and 45% final name cap → compare theoretical target with last adopted target including cash → monthly/event adoption → next open plus declared delay → whole adjusted-unit fills, actual fees, daily NAV and contribution accounting.

Selected score: {protocol['formulas'][chosen.split('-')[0][5:]]}. The matching momentum score is C(t)/C(t−126)−1 and otherwise uses identical allocation and timing. The unranked control keeps all eligible names with the same inverse-volatility budget/cap. FR25 is the frozen app-owned empirical incumbent with financial/momentum and protection overlays; its full versioned definition and signal-input provenance are in [incumbent provenance](incumbent-provenance.json). These are three main model choices; the remaining references are controls, not post-result alternatives.

Alpha scores can be negative; only rank matters. Fewer than six valid scores or a constant cross-section produces cash. Ties follow inherited alphabetical selection, so ties in 46/49 can encode ticker ordering. Original absolute-price formulas24/46/49 are sensitive to adjusted price units across ETFs; no normalization was silently added. Formula53/54 same-close paper timing is adapted to next-open execution here. There are no stops or intraday protections in these standalone recipes; allocation exits occur only at adopted rebalances.

Dynamic thresholds are strict L1 distances greater than 0.10/0.40/0.80, including residual cash, plus the monthly anchor. They compare latest theoretical and last adopted targets. Held-position drift never triggers them. Delayed execution retains the original adopted target, resized at the close immediately before execution.

## Costs, execution delay and controls

{chr(10).join(stress)}

{chr(10).join(timing)}

All four timing options were evaluated for every formula and both simple controls. Monthly wins the training selection for all six formulas; this conclusion belongs to this pool, mapping and cost grid. Extra turnover was allowed and judged by its realized net outcome.

{chr(10).join(guard_table)}

{chr(10).join(benchmarks)}

Cash has zero interest and undefined Calmar at zero drawdown. Reported Sharpe uses zero as its reference rate, so BIL's small-volatility Sharpe is not directly comparable risk exposure. BIL is the investable cash reference. Buy-and-hold portfolios buy initially and drift thereafter; their later window inherits positions. [Individual ETF buy-and-hold references](individual-buyhold.json) instead start fresh each era, use fractional units and one 5 bp entry fee, and are explicitly descriptive. [All 222 case metrics](results.json) include actual fees, turnover, exposure and annual outcomes; [every guarded comparison](comparisons.json) is retained. The matched-control rules govern this test; additional guard calculations against cash/buy-and-hold are descriptive and not a new acceptance requirement.

## Chronological robustness and uncertainty

{chr(10).join(annual)}

{chr(10).join(ci)}

{chr(10).join(ic_table)}

Intervals are paired circular 21-session block bootstraps, 4,000 draws, seed20261031, Bonferroni-adjusted across24 alpha/timing contrasts against matching momentum. Tail estimates are approximate; related formulas and repeatedly inspected histories limit discovery claims. [All intervals](uncertainty.json), [training-prefix policy stability](training-stability.json), and [1/5/10/21-session rank IC, coverage and ties](signal-diagnostics.json) are diagnostics. The primary IC horizon was21; no horizon was selected by its result. Later history is chronological holdout from this selection, not untouched or prospective evidence.

FR25 is not a universal truth benchmark: DBC/SPY/XLE contribute 9.96/9.67/7.42 points in calibration; EWY/GLD/XLE contribute14.78/10.47/7.75 points later. Those later three account for about60% of its net gain. Its asset contribution extremes in each era are in [incumbent dependence](incumbent-dependence.json), and annual results above expose period dependence. Its saved signal decisions use their own audited batch/model warmup; all portfolios are replayed on the same study prices, costs and dates, but FR25 is not a pure alpha ablation. [Full portfolio attribution](attribution.json) reconciles to NAV in every era.

## Weakest risky ETF inspections

The declared criterion is **lowest actual net contribution divided by opening portfolio NAV**, at5bp/next-open under the training-selected policy, excluding BIL, cash and URTH. This explicit portfolio criterion accounts for changing allocations; it is not a standalone ETF return. Both eras include every dated state/fill and price/volume context. No protective stop exists in this recipe. Visual observations will become hypotheses for a subsequent declared test, never retrospective tuning.

{(chr(10)*2).join(weak_text)}

[All FIFO trade outcomes](trade-outcomes.csv) include partial exits, allocated entry/exit fees and open-lot marks. Total marked FIFO P&L reconciles to full portfolio net P&L. Era-specific contributions use actual held units and daily changes, including positions inherited from the earlier era.

## Evidence and limits

The frozen input batch is {protocol['price_pin']['batch']}. The full configured/admitted union contains {protocol['candidate_count']} candidates: {protocol['supported_count']} supported histories, including BIL, with BWX/XOP identity holds preserved. Common audited support begins {protocol['common_start']}; evaluation begins January4,2021 and ends October30,2026. No provider download or online price was used. Prices are dividend/split-adjusted; activity uses audited raw share volume and raw traded price. Unsupported observations remain missing; no fill/splice or FX input.

This is current-cohort retrospective research. Price auditing does not certify historical dissemination or historical membership; reconstructed raw prices are not tape-certified. Whole adjusted units are synthetic research accounting; fees do not model spreads, impact, taxes or broker lots. The original frozen screen and its verdicts remain historical evidence. The old cost exclusion is now superseded by actual net replay evidence for these six signals, without automatic monitoring or allocation.

[Frozen protocol and hashes](protocol.json) · [Native independent accounting checks](native-validation.json) · [Acceptance receipt](acceptance.json). Native LEAN verifies orders/fills/cash/NAV on frozen targets; it does not independently infer the alpha policy. Unit tests separately cover formulas, causal suffixes, missing activity, selection leakage, caps, adoption and accounting boundaries.

**Stop for operator discussion.** Cash-relative remains retained research evidence. No promotion, monitoring, funding, broker or app-calculation change was made. P4.20 decay governance and the remaining research queue have not been started in this item.
'''
    (s.OUT/'results.md').write_text(body,encoding='utf8')
    html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Alpha101 full-pool net research</title><style>body{font:16px/1.65 system-ui;color:#193044;max-width:1200px;margin:auto;padding:32px;background:#f7fafb}h1,h2,h3{line-height:1.25;color:#103c53}h2{margin-top:2em}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:10px;border-bottom:1px solid #dce6eb;text-align:left}th{background:#e8f1f4}img{width:100%;height:auto;border:1px solid #dce6eb;background:white}a{color:#006b83}p{max-width:1100px}strong{color:#005b70}</style></head><body>'+render_review(body)+'</body></html>'
    (s.OUT/'index.html').write_text(html,encoding='utf8')
    s.write(s.OUT/'review-summary.json',dict(selected=chosen,per_alpha=selection['per_alpha'],guard_counts=counts,weakest=weak,
        selected_intervals=selected_intervals,book_error_usd=max(v[2] for v in books.values()),cases=len(rows),verdict=verdict,
        reporter_sha256=s.digest(Path(__file__))))
    print(s.read(s.OUT/'review-summary.json'),flush=True)


if __name__=='__main__':main()
