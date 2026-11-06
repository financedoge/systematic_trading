"""Inspect the locked FR25 breadth experiment and its portfolio accounting."""
from datetime import date
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import research_fr25_breadth as study
from report_cash_relative_retest import money_prices, render_review, trade_lots
from research_cash_relative_retest import passes
from systematic_trading.research.evidence_review import assess

OUT, WORK = study.OUT, study.WORK
ERAS = ('calibration','later')


def path(arm):
    with np.load(WORK/'paths'/f'{arm}_c5d0.npz') as saved:
        return dict(saved)


def table(columns, records):
    return '\n'.join(['| '+' | '.join(columns)+' |','| '+' | '.join(['---']*len(columns))+' |',
                      *['| '+' | '.join(map(str,row))+' |' for row in records]])


def exposure_mix(a, days, arm):
    econ=study.gzread(WORK/'detail'/f'{arm}_c5d0.json.gz')
    symbols=a['symbols'].tolist()+['URTH']
    bil=symbols.index('BIL')
    prices=money_prices(a['close'][np.searchsorted(a['days'],days),bil])
    units=np.zeros(len(symbols))
    fills={}
    for fill in econ['fills']:
        fills.setdefault(fill['date'],[]).append(fill)
    daily=[]
    for i,row in enumerate(econ['nav']):
        for fill in fills.get(row['date'],[]):
            units[symbols.index(fill['symbol'])]+=fill['quantity']
        nav=float(row['nav'])
        cash=float(row['cash'])/nav
        bill=units[bil]*prices[i]/nav
        daily.append((cash,bill,1-cash-bill,np.count_nonzero(units)-int(units[bil]>0)))
    mix={}
    for era in ERAS:
        start,end=study.parent.WINDOWS[era]
        means=np.asarray(daily)[(days>=start)&(days<=end)].mean(axis=0)
        mix[era]=dict(zip(('cash','bil','risky','risky_names'),means.tolist(),strict=True))
    return mix


def inspect_weakest(a, days, selection, observations):
    values=path('winner')
    economic=study.gzread(WORK/'detail/winner_c5d0.json.gz')
    symbols=a['symbols'].tolist()+['URTH']
    pos=np.zeros(len(symbols))
    cash=1e6
    full_indices=np.searchsorted(a['days'],days)
    prices=money_prices(np.column_stack((a['close'],a['urth_close']))[full_indices])
    held=np.empty_like(prices)
    fills={}
    for fill in economic['fills']:
        fills.setdefault(fill['date'],[]).append(fill)
    for i,day in enumerate(days):
        for fill in fills.get(day,[]):
            units=fill['quantity']
            pos[symbols.index(fill['symbol'])]+=units
            cash-=units*float(fill['price'])+float(fill['fee'])
        nav=cash+pos@prices[i]
        if abs(nav-values['nav'][i])>.01:
            raise ValueError('Cash/share reconciliation failed')
        held[i]=pos*prices[i]/nav
    lots=trade_lots(economic,dict(zip(symbols,prices[-1],strict=True)),str(days[-1]))
    if abs(sum(r['net_pnl'] for r in lots)-(values['nav'][-1]-1e6))>.01:
        raise ValueError('FIFO reconciliation failed')
    schedules=dict(np.load(WORK/'schedules.npz'))
    events=set(schedules['winner_indices'])
    targets=schedules['winner_weights']
    adopted=np.zeros_like(held)
    defensive=np.zeros(len(days),dtype=bool)
    for i,t in enumerate(full_indices):
        if t-1 in events:
            adopted[i]=targets[t-1]
            defensive[i]=observations[days[i]]['qualified']<selection['n']
        else:
            adopted[i]=adopted[i-1]
            defensive[i]=defensive[i-1]
    outcomes=[]
    attribution={}
    for era in ERAS:
        start,end=study.parent.WINDOWS[era]
        idx=np.flatnonzero((days>=start)&(days<=end))
        opening=values['nav'][idx[0]-1] if idx[0] else 1e6
        contribution=values['contribution'][idx].sum(axis=0)/opening
        assert abs(contribution.sum()-(values['nav'][idx[-1]]/opening-1))<1e-8
        attribution[era]=dict(zip(symbols,contribution.tolist(),strict=True))
        j=min((k for k,s in enumerate(symbols) if s not in ('BIL','URTH')),key=lambda k:(contribution[k],symbols[k]))
        symbol=symbols[j]
        stem=f'weakest-{era}-{symbol}'
        period_fills=[f for f in economic['fills'] if f['symbol']==symbol and start<=f['date']<=end]
        rows=[]
        for i in idx:
            t=full_indices[i]
            next_obs=observations.get(str(a['days'][t+1])) if t+1<len(a['days']) else None
            rows.append(dict(date=str(days[i]),adjusted_open=a['open'][t,j],adjusted_high=a['high'][t,j],
                adjusted_low=a['low'][t,j],adjusted_close=a['close'][t,j],raw_volume=a['raw_volume'][t,j],
                raw_close=a['raw_close'][t,j],theoretical_at_close=targets[t,j] if next_obs else None,
                qualifiers_at_close=next_obs['qualified'] if next_obs else None,adopted_weight=adopted[i,j],
                held_weight=held[i,j],adopted_defensive=bool(defensive[i]),net_pnl_usd=values['contribution'][i,j],
                fills=' / '.join(f"{f['quantity']} @ {f['price']} fee {f['fee']}" for f in fills.get(days[i],[]) if f['symbol']==symbol)))
        with (OUT/(stem+'-daily.csv')).open('w',encoding='utf8',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        overlap=[dict(r,protection='Monthly breadth decision and final target cap. Open lots marked at study end.')
                 for r in lots if r['symbol']==symbol and r['entry']<=end and r['exit']>=start]
        study.write(OUT/(stem+'-trades.json'),overlap)
        plot_dates=[date.fromisoformat(str(d)) for d in days[idx]]
        fig,axes=plt.subplots(4,1,sharex=True,figsize=(12,9),layout='constrained',
                             gridspec_kw={'height_ratios':[2,1,1,1]})
        axes[0].plot(plot_dates,a['close'][full_indices[idx],j],color='#284664',label='Adjusted close')
        for buy,marker,color in [(True,'^','#15816c'),(False,'v','#ba4b50')]:
            side=[f for f in period_fills if (f['quantity']>0)==buy]
            axes[0].scatter([date.fromisoformat(f['date']) for f in side],[float(f['price']) for f in side],
                            marker=marker,color=color,label='Buy' if buy else 'Sell')
        axes[0].legend(ncol=3)
        axes[1].bar(plot_dates,a['raw_volume'][full_indices[idx],j]/1e6,color='#9babb8')
        axes[1].set_ylabel('Raw volume (M)')
        axes[2].plot(plot_dates,[100*r['theoretical_at_close'] if r['theoretical_at_close'] is not None else np.nan for r in rows],alpha=.45,label='Theoretical')
        axes[2].step(plot_dates,100*adopted[idx,j],where='post',label='Adopted')
        axes[2].plot(plot_dates,100*held[idx,j],label='Held')
        axes[2].legend(ncol=3)
        axes[2].set_ylabel('Weight (%)')
        axes[3].plot(plot_dates,100*np.cumsum(values['contribution'][idx,j])/opening,color='#8a4c71')
        axes[3].fill_between(plot_dates,0,1,where=defensive[idx],transform=axes[3].get_xaxis_transform(),
                             color='#e9b86e',alpha=.28,label='Defensive allocation')
        axes[3].legend()
        axes[3].set_ylabel('Contribution (pp)')
        fig.suptitle(f"{symbol} · {days[idx[0]]} to {days[idx[-1]]} · {100*contribution[j]:.2f} pp · {len(period_fills)} fills")
        fig.savefig(OUT/(stem+'.png'),dpi=115)
        plt.close(fig)
        outcomes.append(dict(era=era,symbol=symbol,contribution=float(contribution[j]),chart=stem+'.png',fills=len(period_fills)))
    study.write(OUT/'attribution.json',attribution)
    study.write(OUT/'weakest.json',outcomes)
    return outcomes


def uncertainty(days):
    output=[]
    for era in ERAS:
        start,end=study.parent.WINDOWS[era]
        idx=np.flatnonzero((days>=start)&(days<=end))
        rng=np.random.default_rng(20261103)
        n=len(idx)
        draw=((rng.integers(0,n,(4000,(n+20)//21,1))+np.arange(21))%n).reshape(4000,-1)[:,:n]
        estimates={}
        for arm in ('winner','scaled','legacy'):
            nav=np.r_[1e6,path(arm)['nav']]
            samples=(nav[1:]/nav[:-1]-1)[idx][draw]
            sd=samples.std(axis=1,ddof=1)
            estimates[arm]=np.divide(samples.mean(axis=1)*np.sqrt(252),sd,out=np.zeros_like(sd),where=sd>1e-12)
        for arm in ('winner','scaled'):
            output.append(dict(era=era,arm=arm,control='legacy',conditional_95=np.quantile(
                estimates[arm]-estimates['legacy'],[.025,.975]).tolist()))
    study.write(OUT/'uncertainty.json',output)
    return output


def main():
    protocol=study.validate()
    sel=study.read(OUT/'selection.json')
    grid=study.gzread(OUT/'training-grid.json.gz')
    results=study.read(OUT/'results.json')
    assert len(grid)==52**2 and len(results)==48
    primary={(r['arm'],r['cost_bp'],r['delay']):r['windows'] for r in results}
    benchmarks={(r['arm'],r['cost_bp'],r['delay']):r['windows'] for r in study.read(study.parent.OUT/'results.json')}
    a=study.input_arrays()
    days=a['days'][a['days']>=study.parent.START]
    obs={r['session']:r for r in study.read(OUT/'breadth-observations.json')}
    monthly=a['days'][study.monthly_indices(a['days'])+1]
    weak=inspect_weakest(a,days,sel,obs)
    intervals=uncertainty(days)
    names={'legacy':'Expanded 6 / 4','scaled':'Expanded 6 / 15','winner':f"IS choice {sel['m']} / {sel['n']}",
           'admitted':'6 / 28.57% of admitted','width_only':f"Width alone {sel['m']} / 4",
           'breadth_only':f"Breadth alone 6 / {sel['n']}",'winner_event':'IS pair, dynamic 0.40',
           'scaled_event':'6 / 15, dynamic 0.40'}
    thresholds={'legacy':4,'scaled':15,'winner':sel['n'],'width_only':4,'breadth_only':sel['n']}
    recipes=dict(base_definition='../expanded-fr25-net-20261102-v1/definitions.json#expanded',
        decision_clock='Prior completed close for next open',compare='qualifying_count < minimum_count',
        minimum_count='ceil(numerator * denominator_pool_count / denominator)',
        qualifying_count='Admitted candidates with strictly positive 126-session momentum, counted before top M',
        fallback='Original FR25 defensive_cash and downstream sizing stack',
        policies=dict(legacy=dict(max_selected=6,minimum_count=4),
            scaled=dict(max_selected=6,numerator=4,denominator=14,denominator_pool='supported'),
            admitted=dict(max_selected=6,numerator=4,denominator=14,denominator_pool='admitted_before_momentum'),
            winner=dict(max_selected=sel['m'],numerator=sel['n'],denominator=52,denominator_pool='supported',
                        selected_on='monthly IS, 2021-2024',selection_sha256=study.digest(OUT/'selection.json'))))
    assert study.required_count(4,14,52)==thresholds['scaled']
    study.write(OUT/'recipes.json',recipes)
    fallback={}
    for era in ERAS:
        start,end=study.parent.WINDOWS[era]
        decision_days=[str(d) for d in monthly if start<=d<=end]
        fallback[era]={'months':len(decision_days)}
        for arm in ['legacy','scaled','winner','admitted','width_only','breadth_only']:
            fallback[era][arm]=[d for d in decision_days if obs[d]['qualified']<
                (study.required_count(4,14,obs[d]['admitted']) if arm=='admitted' else thresholds[arm])]
    study.write(OUT/'fallback.json',fallback)
    navs={arm:np.r_[1e6,path(arm)['nav']] for arm in ('legacy','scaled')}
    months=np.array([d[:7] for d in days])
    changed=[]
    for d in sorted(set(fallback['calibration']['scaled'])-set(fallback['calibration']['legacy'])):
        positions=np.flatnonzero(months==d[:7])
        changed.append(dict(month=d[:7],qualifiers=obs[d]['qualified'],**{
            arm+'_return':float(nav[positions[-1]+1]/nav[positions[0]]-1) for arm,nav in navs.items()}))
    study.write(OUT/'extra-defensive-months-is.json',changed)
    mix={k:exposure_mix(a,days,k) for k in ('winner','scaled','legacy')}
    study.write(OUT/'exposure.json',mix)
    mix_table=table(['Policy','Period','Risky ETFs','BIL','Cash','Average risky ETF count'],
        [[names[k],era,f"{r['risky']:.1%}",f"{r['bil']:.1%}",f"{r['cash']:.1%}",f"{r['risky_names']:.1f}"]
         for k in ('legacy','scaled','winner') for era,r in mix[k].items()])
    def numbers(x):
        return [f"{x['cumulative']:.2%}",f"{x['cagr']:.2%}",f"{x['sharpe']:.3f}",f"{x['max_drawdown']:.2%}",
                f"{x['annual_turnover']:.2f}",f"{x['fees_usd']:,.0f}"]
    columns=['Policy','Period','Net return','CAGR','Sharpe','Max DD','Turnover/yr','Fees USD']
    main_table=table(columns+['Average ETF exposure','Defensive months'],[[names[k],era,*numbers(primary[k,5,0][era]),
        f"{primary[k,5,0][era]['mean_exposure']:.1%}",
        f"{len(fallback[era][k])} / {fallback[era]['months']}"] for era in ERAS for k in ('legacy','scaled','winner')])
    extra=table(columns,[[names[k],era,*numbers(primary[k,5,0][era])] for k in ('admitted','breadth_only','width_only','scaled_event','winner_event') for era in ERAS])
    refs=table(columns,[[k,era,*numbers(benchmarks[k,5,0][era])] for k in ('original-monthly','m1-monthly','momentum-monthly',
        'unranked-monthly','cash','BIL_buyhold','URTH_buyhold','pool_buyhold') for era in ERAS])
    surface=np.empty((52,52))
    for row in grid:
        surface[row['n']-1,row['m']-1]=row['prefix']['2024']['sharpe']
    near_paths=len({row['is_path'] for row in grid if row['prefix']['2024']['sharpe']>=sel['net_is']['sharpe']-.05})
    neighbors=[row['prefix']['2024']['sharpe'] for row in grid if abs(row['m']-sel['m'])+abs(row['n']-sel['n'])==1]
    training_qualifiers=[obs[d]['qualified'] for d in monthly if d<=study.CUTOFF]
    normal_count=sum(q>=sel['n'] for q in training_qualifiers)
    width_bound=sum(q>=sel['n'] and q>sel['m'] for q in training_qualifiers)
    original_tape=study.gzread(study.parent.WORK/'targets/original.json.gz')
    original_fallback={era:[str(d) for d in monthly if study.parent.WINDOWS[era][0]<=d<=study.parent.WINDOWS[era][1]
                            and original_tape[d]['selection']['fallback']] for era in ERAS}
    overlap=len(set(original_fallback['calibration']) & set(fallback['calibration']['scaled']))
    fig,ax=plt.subplots(figsize=(9,6),layout='constrained')
    pixels=ax.imshow(surface,origin='lower',extent=(.5,52.5,.5,52.5),aspect='auto',cmap='viridis')
    fig.colorbar(pixels,ax=ax,label='IS net Sharpe')
    for m,n,marker,label in [(6,4,'o','Legacy'),(6,15,'s','Proportional'),(sel['m'],sel['n'],'*','IS maximum')]:
        ax.scatter(m,n,s=110,marker=marker,facecolor='none',edgecolor='white',label=label)
    ax.set(xlabel='M · maximum ranked ETFs',ylabel='N · minimum qualifiers',title='Expanded FR25 · monthly IS selection, 2021–2024')
    ax.legend(facecolor='#606870',labelcolor='white')
    fig.savefig(OUT/'is-surface.png',dpi=125)
    plt.close(fig)
    stress=table(['Cost (bp)','Extra sessions','Period','Net return','CAGR','Sharpe','Max DD','Turnover/yr','Fees USD'],
        [[c,d,era,*numbers(primary['winner',c,d][era])] for c,d in protocol['frictions'] for era in ERAS])
    guards={k:{era:sum(passes(primary[k,c,d][era],primary['legacy',c,d][era]) for c,d in protocol['frictions'])
               for era in ERAS} for k in ('scaled','winner')}
    annual=table(['Calendar year','Legacy return / Sharpe','Scaled return / Sharpe','Selected return / Sharpe'],
        [[year,*[f"{primary[k,5,0][str(year)]['cumulative']:.2%} / {primary[k,5,0][str(year)]['sharpe']:.3f}"
                  for k in ('legacy','scaled','winner')]] for year in range(2021,2027)])
    ci=table(['Policy vs legacy','Period','Paired 95% interval, Sharpe difference'],[
        [names[r['arm']],r['era'],' to '.join(f'{v:.3f}' for v in r['conditional_95'])] for r in intervals])
    monthly_counts=np.array([obs[d]['admitted'] for d in monthly])
    weak_text='\n\n'.join(f"### {r['symbol']} in {r['era']}\n\n![Dated inspection]({r['chart']})\n\n"
        f"[Daily state and fills]({r['chart'][:-4]}-daily.csv) · [FIFO trade outcomes]({r['chart'][:-4]}-trades.json)" for r in weak)
    body=f"""# Expanded FR25 selection width and defensive breadth

Monthly trading on the 52 supported ETFs. The highest 2021–2024 net Sharpe on the declared grid was **{sel['net_is']['sharpe']:.3f} at M={sel['m']}, N={sel['n']}** ({sel['n']/52:.2%} breadth). The chosen pair was sealed before its later replay. Both historical periods had been inspected in the earlier study.

{main_table}

The original 14-ETF FR25 on the same warmup appears in the benchmark table. Its defensive rule fired on {len(original_fallback['calibration'])} training months, with {overlap} of those dates in common with the expanded proportional rule. Compare the 6/4 and 6/15 rows to isolate the switch to proportional breadth with width held constant. Compare the selected pair separately to measure the effect of searching across widths and thresholds.

The 28.57% threshold restored the training fallback frequency. Sharpe fell from 0.462 to 0.347 and drawdown deepened from 18.30% to 21.03%. In the later period both six-slot rules passed the breadth gate on every monthly date and adopted identical targets. Their primary return difference is about 0.0012 percentage points. Inherited positions, starting capital and whole-unit rounding matter at that precision, including when counting strict Sharpe guard passes.

In two of the seven extra defensive training months, May 2022 and November 2023, the legacy book returned 3.60% and 5.32% respectively, against −0.75% and 0.55% for the proportional book. These are whole-calendar-month returns including entry and exit effects at the boundary. [All seven months](extra-defensive-months-is.json).

{mix_table}

The 42/33 choice improves training Sharpe mainly by reducing portfolio risk. Its training CAGR falls from 6.07% for 6/4 to 3.22%, outside the 0.5-point return guard. Later it averages 36.0% in risky ETFs, 26.1% in BIL and 37.9% in cash. Cash earns zero and BIL earns its audited ETF return. With the same 33-qualifier gate, the six-slot control earns 73.71% later against 9.46% for the 42-slot selection. Both enter defensive mode in eight of 22 later months. This comparison isolates width while keeping fallback dates fixed.

## What the rule counts

First count admitted ETFs with positive 126-session momentum. With fewer than N qualifiers, keep only qualifying IEF, TLT and GLD at their incoming weights, carry their cash budget through the later overlays and hold residual cash. With at least N, take the highest-ranked M qualifiers, or all qualifiers when fewer than M are available. Apply the original FR25 sizing, USD and activity overlays and final 45% cap. BIL participates under the original expanded recipe. Each monthly decision uses the prior close and fills at the next open in the primary 5 bp case.

The primary denominator is the full supported cohort. Four out of 14 gives a 28.57% rule. At 52 funds it requires ceil(52 × 4/14) = 15. The alternative denominator uses the {monthly_counts.min()}–{monthly_counts.max()} funds passing that day's admission checks before the momentum gate. Its threshold varies by decision. [All qualified counts and admission counts](breadth-observations.json) · [Exact fallback dates](fallback.json).

## The IS search

All 2,704 integer pairs were evaluated from January 4, 2021 through December 31, 2024 at 5 bp with monthly execution. They gave {sel['distinct_paths']} distinct target paths. {len(sel['tied_pairs'])} pairs tied at the maximum to 12 decimal places. {sel['within_005_sharpe']} pairs were within 0.05 Sharpe of it. Ties favor breadth closest to 15, then width closest to six. IS prefix winners through 2021, 2022, 2023 and 2024 were {', '.join(str(tuple(v)) for _,v in sorted(sel['prefix_winners'].items()))}.

The near-maximum set contains {near_paths} distinct IS target paths. Moving M or N by one while holding the other fixed gives neighboring IS Sharpes from {min(neighbors):.3f} to {max(neighbors):.3f}.

Of the {normal_count} training months that passed the selected breadth threshold, the width cap excluded a qualifying ETF in only {width_bound}. This limits how precisely these dates distinguish a specific large M from nearby widths.

![IS selection surface](is-surface.png)

[Frozen selection](selection.json) · [Complete compressed IS grid and prefix results](training-grid.json.gz) · [Research recipes](recipes.json) · [Protocol](protocol.json).

## Attribution to width, breadth and timing

{extra}

The dynamic variant adopts on the monthly anchor or when the L1 distance from the last adopted target, including cash, exceeds 0.40. The chosen monthly pair also receives the same 5/10/20 bp and zero/one additional session stress cases. Across these six cases, the 6/15 rule passes the legacy comparison {guards['scaled']['calibration']}/6 in IS and {guards['scaled']['later']}/6 later. The selected pair passes {guards['winner']['calibration']}/6 and {guards['winner']['later']}/6, respectively. Each pass requires higher Sharpe, CAGR loss at most 0.5 percentage points and drawdown worsening at most 2 points.

{stress}

{annual}

{ci}

Intervals use 4,000 paired circular 21-session block draws and are conditional on the chosen comparison. Searching 2,704 pairs on four years can inflate the best IS Sharpe. The 2025–October 2026 results measure transfer to a previously inspected period, with positions carried across the boundary. Fresh validation requires observations collected after this rule freeze.

## Same-price and friction benchmarks

{refs}

These controls use the hash-bound parent study's identical price batch, USD accounting, dates and frictions. The original14 FR25, expanded M1, momentum and unranked controls retain their specified constructions. [Parent study](../expanded-fr25-net-20261102-v1/index.html) · [All new cost/delay and annual metrics](results.json).

## Weakest held-risk contributions

The criterion is lowest actual net contribution divided by era-opening NAV for the selected monthly book, excluding BIL, cash and URTH. Daily files include adjusted OHLC, raw price and volume, current theoretical target, adopted and held weights, breadth state and fills. Protection comes from portfolio allocation and the final cap. The strategy has no intraday stop. FIFO outcomes include partial exits and final marks. [All ETF contributions](attribution.json).

{weak_text}

## Evidence

The retained batch is {protocol['price_pin']['batch']}. Historical membership and first availability remain reconstructed. Whole adjusted units and fixed trading frictions omit measured spreads and impact. The full six-case legacy NAV paths reproduce the parent, and the selected full replay reproduces its sealed IS Sharpe. [Independent native accounting](native-validation.json) · [Evidence assessment](assessment.json).
"""
    (OUT/'results.md').write_text(body,encoding='utf8')
    style='body{max-width:1140px;margin:auto;padding:2rem;font:16px/1.55 system-ui;color:#203544}table{border-collapse:collapse;width:100%}td,th{padding:.45rem;text-align:left;border-bottom:1px solid #ccd8dc}img{max-width:100%}a{color:#086a80}'
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>FR25 breadth study</title><style>'+style+'</style>'+render_review(body),encoding='utf8')
    study.write(OUT/'summary.json',dict(m=sel['m'],n=sel['n'],guard_counts=guards,weakest=weak,
        winner=primary['winner',5,0],scaled=primary['scaled',5,0],legacy=primary['legacy',5,0]))


def close():
    from xml.etree import ElementTree as ET
    p=study.validate()
    sel=study.read(OUT/'selection.json')
    summary=study.read(OUT/'summary.json')
    native=study.read(OUT/'native-validation.json')
    assert len(native['cases'])==3 and all(r['status']=='succeeded' and r['max_nav_error_usd']<=.01 for r in native['cases'])
    # Inherit the exact publication limitations and provenance of the unchanged rank signal.
    dossier=study.read(study.parent.OUT/'dossier.json')
    dossier.update(study_id=OUT.name,candidate_id=f"expanded-monthly-M{sel['m']}-N{sel['n']}",
        preregistered_net_rule=p['selection'],net_verdict='guarded_advantage' if all(v==6 for v in summary['guard_counts']['winner'].values()) else 'not_established',
        operator_disposition='Operator requested this comparison. Results ready for discussion.',
        prospective_plan_or_gap='Both eras were inspected previously. Fresh validation needs a prior freeze and later captured observations.')
    dossier['sample'].update(recipe_frozen_at=p['frozen_at'],trial_count=sel['trials'],
        prior_search_and_multiplicity='All 2704 monthly M,N pairs competed on IS net Sharpe. Prefix winners and distinct paths are disclosed. Intervals condition on selection. Prior universe and recipe searches add unknown multiplicity.',
        label_boundary_and_overlap='Search engine values only 2021–2024. Training ranks use causal frozen model and prior-close data. Parameters sealed before OOS target replay. Continuous positions cross the window boundary.')
    dossier['decay'][0]['cadence_and_delay_interpretation']='Upstream ranking model and history are shared with the parent. New width/breadth rules are checked with monthly and 0.40 dynamic timing, annual stability and six cost/delay scenarios.'
    dossier['coverage_gaps'].append('Selection uncertainty across all 2704 trials is uncorrected. Conditional bootstrap intervals do not adjust the search.')
    roles={OUT/'protocol.json':['protocol','strategy_recipe'],OUT/'recipes.json':['strategy_recipe'],study.parent.OUT/'definitions.json':['strategy_recipe'],
        study.parent.OUT/'input-verification.json':['published_input_verification'],OUT/'selection.json':['selection'],
        OUT/'training-grid.json.gz':['selection'],OUT/'results.json':['net_results','chronology','cost_delay'],
        study.parent.OUT/'results.json':['matched_controls'],OUT/'results.md':['matched_controls','weakest_inspections'],
        OUT/'uncertainty.json':['uncertainty'],study.parent.OUT/'signal-diagnostics.json':['decay_stability'],
        OUT/'native-validation.json':['independent_validation']}
    for row in summary['weakest']:
        roles[OUT/row['chart']]=['weakest_inspections']
    dossier['artifacts']=[dict(path=f.relative_to(study.REPO).as_posix(),sha256=study.digest(f),roles=r) for f,r in roles.items()]
    study.write(OUT/'dossier.json',dossier)
    assessment=assess(dossier,study.REPO,study.REPO/'config/research-evidence-policy-v1.json')
    assert not assessment['integrity_and_claim_issues']
    study.write(OUT/'assessment.json',assessment)
    tests=next(iter(ET.parse(study.REPO/'var/maintenance/fr25-breadth-20261103/tests.xml').getroot()))
    assert int(tests.attrib['failures'])==int(tests.attrib['errors'])==0
    study.write(OUT/'acceptance.json',dict(tests=int(tests.attrib['tests']),native=native['cases'],
        original_training_monthly_target_matches=48,full_legacy_nav_matches=6,locked_is_sharpe_matches=True,
        training_bank_receipt=study.read(WORK/'bank-receipt.json'),selection_sha256=study.digest(OUT/'selection.json'),
        parent_protocol_sha256=p['parent_protocol_sha256'],status=assessment['status']))
    study.write(OUT/'retention.json',dict(retain='Study protocol, runner, compact training grid, selection, results, weakest inspections, validation and evidence review.',
        after_discussion='Classify training-bank.npz, schedules.npz, detail, paths and native-contract/bundles/output folders for guarded retirement. Parent inputs are shared with this active review.',
        deletion_performed=False))
    study.write(WORK/'summary.json',summary)
    study.write(OUT/'artifact-manifest.json',{f.name:study.digest(f) for f in OUT.iterdir() if f.is_file() and f.name!='artifact-manifest.json'})


if __name__=='__main__':
    import sys
    close() if sys.argv[1:]==['close'] else main()
