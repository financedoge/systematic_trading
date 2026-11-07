"""Dated review, weakest-ETF inspection and frozen-weight winner-dependence check.

Declared before performance: drop the largest contributor from the primary
portfolio, replace its frozen weights with cash, never rerank or renormalize.
This is a retrospective attribution sensitivity, not a candidate strategy.
"""
from collections import defaultdict
from datetime import date
import html
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import backtest_p421_alpha33 as b
import research_p421_alpha33 as s
from research_cash_relative_retest import clean, gzread, gzwrite, metric
from report_cash_relative_retest import money_prices, trade_lots, render_review


def pct(value):
    return f'{100*value:.2f}%'


def main():
    a,schedules,recipe,engine=b.inputs()
    p=s.protocol()
    cases=s.read(s.OUT/'results.json')['cases']
    lookup={(r['arm'],r['cost_bps'],r['delay']):r for r in cases}
    symbols=a['symbols'].tolist()+['URTH']
    days=engine.day_strings
    indexes=np.flatnonzero(a['days']>=s.START)
    dates=[date.fromisoformat(str(d)) for d in days]
    primary='constituent33-monthly'
    cache={arm:dict(np.load(s.WORK/'paths'/f'{arm}_c5d0.npz')) for arm,c,d in lookup if c==5 and d==0}
    economic=gzread(s.WORK/'paths'/f'{primary}_c5d0.json.gz')
    closes=money_prices(np.column_stack([a['close'],a['urth_close']]))[indexes]
    lots=trade_lots(economic,dict(zip(symbols,closes[-1],strict=True)),s.END)
    byday=defaultdict(list)
    for f in economic['fills']:
        byday[f['date']].append(f)
    q=np.zeros(len(symbols));cash=1e6;held=[];book_error=0.
    for i,day in enumerate(days):
        for f in byday[str(day)]:
            q[symbols.index(f['symbol'])]+=f['quantity']
            cash-=f['quantity']*float(f['price'])+float(f['fee'])
        nav=cash+q@closes[i]
        book_error=max(book_error,abs(nav-float(economic['nav'][i]['nav'])))
        held.append(q*closes[i]/nav)
    held=np.array(held)
    if book_error>.03:
        raise ValueError('Inspection book mismatch')
    ledgers=gzread(s.WORK/'adoptions.json.gz')[primary]
    latest={}
    adopted=[]
    for r in ledgers:
        if r['adopted']:
            latest=r['latest']
        adopted.append([float(latest.get(symbol,0)) for symbol in symbols])
    adopted=np.array(adopted)
    theoretical=schedules[primary+'_weights'][indexes-1]
    weak,attribution=[],{}
    windows=dict(full=(s.START,s.END),march=(s.START,'2025-03-31'),april=('2025-04-01','2025-04-30'),may=('2025-05-01',s.END))
    for window,(start,end) in windows.items():
        ix=np.flatnonzero((days>=start)&(days<=end))
        opening=cache[primary]['nav'][ix[0]-1] if ix[0] else 1e6
        values=cache[primary]['contribution'][ix].sum(axis=0)
        table=sorted([dict(symbol=symbol,net_pnl=float(values[j]),net_contribution=float(values[j]/opening),
            mean_held_weight=float(held[ix,j].mean())) for j,symbol in enumerate(symbols)],key=lambda r:(r['net_contribution'],r['symbol']))
        if abs(sum(r['net_contribution'] for r in table)-lookup[primary,5,0]['windows'][window]['cumulative'])>1e-7:
            raise ValueError('Attribution does not reconcile')
        attribution[window]=table
        risky=[r for r in table if r['symbol'] not in ('BIL','URTH') and r['mean_held_weight']>0]
        if not risky:
            weak.append(dict(window=window,status='all_cash_no_risky_ETF'))
            continue
        worst=risky[0];symbol=worst['symbol'];j=symbols.index(symbol)
        stem=f'weakest-{window}-{symbol}'
        fig,axes=plt.subplots(4,1,figsize=(13,10),sharex=True,gridspec_kw={'height_ratios':[3,1,1.5,1.5]})
        dt=np.array(dates,dtype=object)[ix]
        axes[0].plot(dt,closes[ix,j],color='#234f84',label='Adjusted close')
        for f in economic['fills']:
            if f['symbol']==symbol and start<=f['date']<=end:
                x=date.fromisoformat(f['date']);price=float(f['price']);buy=f['quantity']>0
                axes[0].scatter(x,price,marker='^' if buy else 'v',color='#16806a' if buy else '#b03d40',s=70,zorder=3)
                axes[0].annotate(f"{f['date']} {'buy' if buy else 'sell'} {abs(f['quantity'])}", (x,price),xytext=(5,7 if buy else -20),textcoords='offset points',fontsize=8)
        axes[0].set_title(f"{symbol} — {window} weakest held ETF by net contribution: {100*worst['net_contribution']:.2f} pp\nConstituent Alpha33 / frozen monthly primary; 5 bp, next open; no stop/protection")
        axes[0].set_ylabel('Adjusted USD')
        axes[1].bar(dt,a['raw_volume'][indexes[ix],j]/1e6,color='#8a9cac')
        axes[1].set_ylabel('Raw volume\n(m shares)')
        axes[2].plot(dt,theoretical[ix,j]*100,label='Theoretical (previous close)',alpha=.75)
        axes[2].step(dt,adopted[ix,j]*100,where='post',label='Last adopted')
        axes[2].plot(dt,held[ix,j]*100,label='Actual close holdings',ls=':')
        axes[2].set_ylabel('Weight %');axes[2].legend(fontsize=8,ncol=3)
        axes[3].plot(dt,np.cumsum(cache[primary]['contribution'][ix,j])/opening*100,color='#b03d40')
        axes[3].axhline(0,color='#999',lw=.7);axes[3].set_ylabel('Net contribution\npercentage points')
        for ax in axes:
            ax.grid(alpha=.2)
        fig.autofmt_xdate();fig.tight_layout();fig.savefig(s.OUT/(stem+'.png'),dpi=135);plt.close(fig)
        detail=[dict(date=str(days[i]),adjusted_close=float(closes[i,j]),raw_volume=float(a['raw_volume'][indexes[i],j]),
            theoretical_weight=float(theoretical[i,j]),adopted_weight=float(adopted[i,j]),held_weight=float(held[i,j]),
            contribution_usd=float(cache[primary]['contribution'][i,j]),fills=[f for f in byday[str(days[i])] if f['symbol']==symbol],
            protection='None; adopted allocation exits only') for i in ix]
        s.write(s.OUT/(stem+'-detail.json'),clean(dict(daily=detail,trades=[r for r in lots if r['symbol']==symbol and r['entry']<=end and r['exit']>=start],
            trade_scope='FIFO lots overlapping window, open lots marked at final study close; lot P&L is not window contribution.')))
        weak.append(dict(window=window,**worst,chart=stem+'.png',details=stem+'-detail.json'))
    s.write(s.OUT/'attribution.json',clean(attribution))
    s.write(s.OUT/'weakest.json',clean(weak))
    # Ex-post sensitivity explicitly keeps the remaining frozen target weights unchanged.
    winner=max(attribution['full'],key=lambda r:r['net_contribution'])
    w=schedules[primary+'_weights'].copy()
    w[:,symbols.index(winner['symbol'])]=0
    compact,book,_=engine.run(w,schedules[primary+'_indices'],5,0,detailed=True)
    diagnostic=metric(days,compact['nav'],s.START,s.END,fees=compact['fees'],turnover=compact['turnover'],exposure=compact['exposure'])
    gzwrite(s.WORK/'winner-excluded.json.gz',book)
    s.write(s.OUT/'winner-dependence.json',clean(dict(largest_contributor=winner,unchanged_other_weights=True,replacement='cash',
        metrics=diagnostic,interpretation='Ex-post sensitivity, not causal theme attribution, optimization or an eligible strategy candidate.')))
    individual=[]
    for j,symbol in enumerate(a['symbols']):
        for window,(start,end) in windows.items():
            ix=np.flatnonzero((a['days']>=start)&(a['days']<=end))
            value=float(a['close'][ix[-1],j]/(a['open'][ix[0],j]*1.0005)-1)
            individual.append(dict(symbol=symbol,window=window,net_fractional_buyhold_return=value,entry_cost_bps=5,terminal_liquidation=False))
    s.write(s.OUT/'individual-buyhold.json',individual)
    fig,ax=plt.subplots(figsize=(12,5))
    main=['constituent33-monthly','etf33-monthly','momentum126-monthly']
    for arm in main:
        ax.plot(dates,(cache[arm]['nav']/1e6-1)*100,label=arm)
    ax.axhline(0,color='#999',lw=.8);ax.set_ylabel('Net cumulative return %');ax.legend();ax.grid(alpha=.2)
    ax.set_title('Frozen monthly comparison — March 3 to May 30, 2025; 5 bp, next open')
    fig.autofmt_xdate();fig.tight_layout();fig.savefig(s.OUT/'comparison.png',dpi=135);plt.close(fig)
    table=['| Model / control | Net return | Annualized Sharpe | Max drawdown | Fees USD | Mean invested |','| --- | ---: | ---: | ---: | ---: | ---: |']
    for arm in main+['unranked-monthly','covered-buyhold','full-pool-buyhold','FR25-reference','URTH','BIL','cash']:
        m=lookup[arm,5,0]['windows']['full']
        table.append(f"| {arm} | {pct(m['cumulative'])} | {m['sharpe']:.3f} | {pct(m['max_drawdown'])} | {m['fees_usd']:,.2f} | {pct(m['mean_exposure'])} |")
    months=['| Month | Constituent33 return / Sharpe | ETF33 return / Sharpe | Momentum return / Sharpe |','| --- | ---: | ---: | ---: |']
    for month in ('march','april','may'):
        values=[lookup[arm,5,0]['windows'][month] for arm in main]
        months.append('| '+month+' | '+' | '.join(f"{pct(m['cumulative'])} / {m['sharpe']:.3f}" for m in values)+' |')
    timing=['| Timing (fixed before results) | Constituent33 return / Sharpe / turnover | ETF33 return / Sharpe / turnover | Momentum return / Sharpe / turnover |','| --- | ---: | ---: | ---: |']
    for policy in p['policies']:
        values=[lookup[name+'-'+policy,5,0]['windows']['full'] for name in ('constituent33','etf33','momentum126')]
        timing.append('| '+policy+' | '+' | '.join(f"{pct(m['cumulative'])} / {m['sharpe']:.3f} / {m['annual_turnover']:.1f}x" for m in values)+' |')
    stress=['| Cost bp | Extra session | Primary return | Sharpe | Drawdown |','| ---: | ---: | ---: | ---: | ---: |']
    for c in p['costs_bps']:
        for d in p['delays']:
            m=lookup[primary,c,d]['windows']['full']
            stress.append(f"| {c} | {d} | {pct(m['cumulative'])} | {m['sharpe']:.3f} | {pct(m['max_drawdown'])} |")
    cov=s.read(s.OUT/'coverage.json')
    covtable=['| Fund with public holdings | Eligible sessions (including final diagnostic close) | Initial equity-value coverage | Minimum coverage |','| --- | ---: | ---: | ---: |']
    for symbol in p['public_funds']:
        row=cov['funds'].get(symbol,{})
        covtable.append(f"| {symbol} | {row.get('eligible_sessions',0)} | {pct(row.get('initial_value_coverage',0))} | {pct(row.get('minimum_value_coverage',0))} |")
    weaktext=[]
    for row in weak:
        if 'chart' in row:
            weaktext.append(f"### {row['window']}: {row['symbol']} ({100*row['net_contribution']:.2f} pp)\n\n![Dated price, volume, states, fills and contribution]({row['chart']})\n\n[Exact observations and FIFO outcomes]({row['details']}).")
    native=s.read(s.OUT/'native-validation.json')
    body=f'''# P4.21 — constituent Alpha33 feasibility pilot

Completed {len(cases)} new net backtests plus one frozen-weight winner-dependence replay. March 3–May 30, 2025; no parameter selection, training fit or claimed pristine OOS result. The monthly case remains the primary test regardless of sensitivity results. No strategy was promoted or given execution authority.

## Main comparison

{chr(10).join(table)}

![Matched monthly net paths](comparison.png)

The same daily coverage and liquidity mask governs the three models and unranked control. Holdings coverage can change by day; see [every eligibility change](coverage.json). All controls use the same audited ETF quotes and accounting, except FR25's frozen signal generation comes from its original published inputs. FR25 is an empirical reference, not a matched constituent-alpha ablation. Cash earns zero; BIL/URTH controls have a 98% initial allocation. Buy-and-hold controls enter once and drift, with no terminal liquidation.

## What was tested

Public December 31, 2024 SEC holdings, filed before the first signal → dated permanent security identity → separately audited stock open/close → rank(open/close − 1) across unique observed constituents → filed-value weighted ETF score, only with at least 95% equity value and 70% position coverage → same eligible ETF pool → top six and 63-return inverse volatility → 98% budget, 45% cap → frozen rebalance policy → next-open whole adjusted-unit fills and fees.

Higher Alpha33 selects stocks whose open was high relative to the close, an intraday reversal hypothesis. ETF33 applies the same formula directly to each ETF. Momentum uses 126-session return; unranked removes the score ranking. Missing positions stay in the coverage denominator. Fewer than six eligible names or all equal ranked scores produces cash. No stops, protective exits, leverage, fitting or rule changes follow from these results. Full decision and source rules: [frozen protocol](protocol.json).

## Chronology and timing

{chr(10).join(months)}

{chr(10).join(timing)}

Turnover is annualized gross traded notional / opening NAV. Annualized Sharpe and turnover over this short window are descriptive, not forecasts. Target-change threshold is strict L1 >0.40 including cash versus the last adopted target, plus monthly reset; actual holdings drift is not a trigger. Daily is a fixed-interval sensitivity, not a post-result recommendation.

{chr(10).join(stress)}

[Every cost, delay, control and monthly metric](results.json) includes actual fees, exposure, turnover, return and drawdown. No annual cost ceiling is imposed.

## Winner dependence

Largest primary contributor: {winner['symbol']}, {100*winner['net_contribution']:.2f} percentage points. Replacing only that asset's frozen weights with cash, without reranking or reallocating, gives {pct(diagnostic['cumulative'])} net return, Sharpe {diagnostic['sharpe']:.3f} and drawdown {pct(diagnostic['max_drawdown'])}. This is an ex-post sensitivity, not a new strategy or a causal claim about a market theme. [Full attribution](attribution.json), [winner diagnostic](winner-dependence.json) and [individual same-window buy-and-hold references](individual-buyhold.json) are retained.

## Coverage and evidence limits

Screened all {cov['full_candidate_count']} supported-pool candidates; {cov['supported_price_count']} have qualified complete ETF prices. Only 16 had the selected public holdings quarter. Initial eligible allocation pool: {', '.join(cov['initial_eligible'])}. Daily eligible counts range from {cov['minimum_daily_eligible']} to {cov['maximum_daily_eligible']}. This cannot establish superiority over the full 52-candidate pool.

{chr(10).join(covtable)}

{chr(10).join('- '+x for x in p['limitations'])}

WRDS extracts remain saved locally with exact SQL, parameters, types, timestamps and hashes. Backtesting reads a new immutable native publication after field/date qualification; it never reads provider archives as strategy inputs. Original volume/full-history audit verdicts were preserved. The projection supports open/close only and is research-only. Public filing dates are evidenced; price vintage dissemination remains unknown. [Publication receipt](publication.json).

## Weakest held risky ETF

Criterion fixed before results: lowest net contribution divided by opening portfolio NAV, excluding cash references and assets never held in the window. This contribution criterion includes allocation and costs; it is not the asset's standalone return. Every monthly window is shown. FIFO lots overlapping a window may span other months and therefore do not sum to that month's contribution.

{chr(10).join(weaktext)}

## Validation

Independent native LEAN verified {len(native['cases'])} cases: primary constituent, matched ETF control and dynamic stressed/delayed constituent. Maximum daily NAV difference was ${max(x['max_nav_error_usd'] for x in native['cases']):.2f}. The separate inspection book reconciled within ${book_error:.4f}. Native replay validates orders, fills, cash and NAV from frozen targets, not the economic hypothesis. [Native validation](native-validation.json).
'''
    (s.OUT/'report.md').write_text(body,encoding='utf8')
    style='body{font:16px/1.55 system-ui,sans-serif;max-width:1200px;margin:40px auto;padding:0 24px;color:#213047;background:#f8fafc}h1,h2,h3{line-height:1.2}h2{margin-top:40px}table{width:100%;border-collapse:collapse;font-size:14px;background:white}th,td{padding:9px;border-bottom:1px solid #dbe2eb;text-align:left}th{background:#e8eef6}img{max-width:100%;height:auto}a{color:#245b97}p{max-width:1120px}'
    rendered=render_review('\n\n'.join(block for block in body.split('\n\n') if block.strip()))
    (s.OUT/'index.html').write_text('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+html.escape(p['id'])+'</title><style>'+style+'</style></head><body>'+rendered+'</body></html>',encoding='utf8')
    s.write(s.OUT/'report-checks.json',dict(inspection_book_max_error=book_error,attribution_reconciled=True,
        report_runner_sha256=s.digest(Path(__file__)),weakest_windows=len(weak),winner_diagnostic_is_not_selection=True))
    print('Report and weakest-ETF inspections ready',flush=True)


if __name__=='__main__':
    main()
