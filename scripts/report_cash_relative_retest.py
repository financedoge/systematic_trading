"""Compact, inspectable review of the frozen cash-relative net experiment."""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import html
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

import research_cash_relative_retest as s


def path(key):
    with np.load(s.WORK/'paths'/f'{key}.npz', allow_pickle=False) as z:
        return dict(z)


def money_prices(values):
    values=np.asarray(values)
    return np.array([float(Decimal(str(x)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP))
                     for x in values.ravel()]).reshape(values.shape)


def uncertainty(rows, days):
    results = []
    for window in ('calibration', 'later'):
        a,b = s.WINDOWS[window]
        ix = np.flatnonzero((days >= a)&(days <= b))
        rng = np.random.default_rng(20261031)
        # Identical date draws preserve dependence across all eight contrasts.
        draw = np.concatenate([(rng.integers(0, len(ix), (2000, 1))+np.arange(21))%len(ix)
                               for _ in range((len(ix)+20)//21)], axis=1)[:, :len(ix)]
        for row in rows:
            arm = row['arm']
            if row['cost_bp'] != 5 or row['delay'] != 0 or '_cash_relative_' not in arm:
                continue
            control = arm.replace('_cash_relative_', '_remove_bill_')
            returns = []
            for key in (arm, control):
                nav = np.r_[1e6, path(key+'_c5d0')['nav']]
                returns.append((nav[1:]/nav[:-1]-1)[ix])
            estimates = []
            for r in returns:
                x = r[draw]
                estimates.append(np.column_stack((x.mean(axis=1)/x.std(axis=1, ddof=1)*np.sqrt(252),
                                                   np.exp(np.log1p(x).mean(axis=1)*252)-1)))
            dif = estimates[0]-estimates[1]
            results.append(dict(arm=arm, window=window, columns=['Sharpe', 'CAGR'],
                 difference_95=np.quantile(dif,[.025,.975],axis=0).tolist(),
                 family_95=np.quantile(dif,[.025/8,1-.025/8],axis=0).tolist()))
    return results


def portfolio_book(key, arrays):
    economic = s.gzread(s.WORK/'detail'/f'{key}.json.gz')
    days = arrays['days'][arrays['days'] >= s.START]
    symbols = arrays['symbols'].tolist()+['URTH']
    closes = money_prices(np.column_stack((arrays['close'],arrays['urth_close']))[-len(days):])
    by = {}
    for f in economic['fills']:
        by.setdefault(f['date'], []).append(f)
    q = np.zeros(len(symbols)); cash = 1e6; holdings = []; max_error = 0.
    for t,d in enumerate(days):
        for f in by.get(str(d),[]):
            j = symbols.index(f['symbol']); quantity = f['quantity']
            q[j] += quantity
            cash -= quantity*float(f['price'])+float(f['fee'])
        nav = cash+q@closes[t]
        max_error = max(max_error, abs(nav-float(economic['nav'][t]['nav'])))
        holdings.append(q*closes[t]/nav)
    if max_error > .03:
        raise ValueError('Independent book reconciliation failed')
    return economic, np.array(holdings), max_error


def trade_lots(economic, closing, end):
    queues, lots = {}, []
    for f in economic['fills']:
        symbol, q, price, fee = f['symbol'], f['quantity'], float(f['price']), float(f['fee'])
        queue = queues.setdefault(symbol, [])
        if q > 0:
            queue.append(dict(day=f['date'], quantity=q, price=price, fee_per_unit=fee/q))
        else:
            remaining = -q
            while remaining:
                if not queue:
                    raise ValueError('Sale without available lot')
                lot = queue[0]; n = min(remaining, lot['quantity'])
                pnl = n*(price-lot['price']-lot['fee_per_unit']-fee/(-q))
                lots.append(dict(symbol=symbol, entry=lot['day'], exit=f['date'], quantity=n,
                    entry_price=lot['price'], exit_price=price, net_pnl=pnl,
                    net_return=pnl/(n*(lot['price']+lot['fee_per_unit'])), status='closed',
                    protection='None; selection/adoption exits only'))
                lot['quantity'] -= n; remaining -= n
                if not lot['quantity']:
                    queue.pop(0)
    for symbol, queue in queues.items():
        for lot in queue:
            pnl = lot['quantity']*(closing[symbol]-lot['price']-lot['fee_per_unit'])
            lots.append(dict(symbol=symbol, entry=lot['day'], exit=end, quantity=lot['quantity'],
                entry_price=lot['price'], exit_price=closing[symbol], net_pnl=pnl,
                net_return=pnl/(lot['quantity']*(lot['price']+lot['fee_per_unit'])), status='open marked',
                protection='None; no terminal liquidation or exit fee'))
    return lots


def pct(x):
    return '—' if x is None else f'{100*x:.2f}%'


def num(x):
    return '—' if x is None else f'{x:.3f}'


def render_review(text):
    """Render this report's fixed headings/paragraphs/tables without dependencies."""
    def inline(value):
        value=html.escape(value)
        value=re.sub(r'!\[([^]]*)\]\(([^)]+)\)',r'<img alt="\1" src="\2">',value)
        value=re.sub(r'\[([^]]*)\]\(([^)]+)\)',r'<a href="\2">\1</a>',value)
        return re.sub(r'\*\*(.*?)\*\*',r'<strong>\1</strong>',value)
    blocks=[]
    for block in text.strip().split('\n\n'):
        lines=block.strip().splitlines()
        if lines[0].startswith('|'):
            table='<table>'
            for i,line in enumerate(lines):
                if i==1:continue
                tag='th' if i==0 else 'td'
                table+='<tr>'+''.join(f'<{tag}>'+inline(c.strip())+f'</{tag}>' for c in line.strip('|').split('|'))+'</tr>'
            blocks.append(table+'</table>')
        elif lines[0].startswith('#'):
            level=len(lines[0])-len(lines[0].lstrip('#'))
            blocks.append(f'<h{level}>'+inline(lines[0].lstrip('# '))+f'</h{level}>')
        elif lines[0].startswith('- '):
            blocks.append('<ul>'+''.join('<li>'+inline(x[2:])+'</li>' for x in lines)+'</ul>')
        else:
            blocks.append('<p>'+inline(' '.join(lines))+'</p>')
    return '\n'.join(blocks)


def main():
    protocol = s.validate(); rows = s.read(s.OUT/'results.json')
    chosen = s.read(s.OUT/'selection.json')['selected']
    control = chosen.replace('_cash_relative_', '_remove_bill_')
    with np.load(s.WORK/'inputs.npz') as z:
        arrays = dict(z)
    with np.load(s.WORK/'schedules.npz') as z:
        schedules = dict(z)
    days = arrays['days'][arrays['days'] >= s.START]
    symbols = arrays['symbols'].tolist()+['URTH']
    main_arms = [(chosen, 'Cash-relative · class/monthly'), (control, 'Removal-only · class/monthly'),
                 ('FR25_frozen', 'FR25 · frozen common-input control')]
    books = {arm: portfolio_book(arm+'_c5d0',arrays) for arm,_ in main_arms}
    summary, attribution, weak = [], {}, []
    for window in ('calibration','later'):
        a,b = s.WINDOWS[window];ix = np.flatnonzero((days>=a)&(days<=b))
        for arm,label in main_arms:
            values = path(arm+'_c5d0');opening = values['nav'][ix[0]-1] if ix[0] else 1e6
            table = [dict(symbol=symbol, net_pnl=float(values['contribution'][ix,j].sum()),
                          net_contribution=float(values['contribution'][ix,j].sum()/opening),
                          mean_held_weight=float(books[arm][1][ix,j].mean())) for j,symbol in enumerate(symbols)]
            table.sort(key=lambda r:(r['net_contribution'],r['symbol']))
            attribution[arm+'-'+window] = table
            if abs(sum(r['net_contribution'] for r in table)-s.metric(days,values['nav'],a,b)['cumulative']) > 1e-7:
                raise ValueError('Constituent contribution does not reconcile')
            if arm == chosen:
                worst = next(r for r in table if r['symbol'] not in ('BIL','URTH'))
                weak.append(dict(window=window, **worst))
        summary.append(dict(window=window, weakest=weak[-1], selected=chosen))
    s.write(s.OUT/'attribution.json', attribution)
    s.write(s.OUT/'weakest.json', weak)
    intervals = uncertainty(rows,days);s.write(s.OUT/'uncertainty.json',intervals)
    # Every declared arm and friction is assessed; no best-later policy choice.
    comparisons = []
    for r in rows:
        if '_cash_relative_' not in r['arm']:
            continue
        for benchmark in (r['arm'].replace('_cash_relative_', '_remove_bill_'), 'FR25_frozen'):
            base = next(x for x in rows if x['arm']==benchmark and x['cost_bp']==r['cost_bp'] and x['delay']==r['delay'])
            for window in ('calibration','later'):
                x,y = r['windows'][window],base['windows'][window]
                comparisons.append(dict(arm=r['arm'],benchmark=benchmark,cost_bp=r['cost_bp'],delay=r['delay'],window=window,
                    passes=s.passes(x,y), sharpe_change=x['sharpe']-y['sharpe'],cagr_change=x['cagr']-y['cagr'],
                    drawdown_change=x['max_drawdown']-y['max_drawdown']))
    s.write(s.OUT/'comparisons.json',comparisons)
    monitors = s.gzread(s.WORK/'monitored.json.gz'); monitor_rows = []
    for doc in monitors:
        d=np.array([r['trade_date'] for r in doc['nav_series']]);n=np.array([float(r['nav_cnh']) for r in doc['nav_series']])
        expected=days[(days>='2025-01-01')&(days<=s.END)]
        if list(d[(d>='2025-01-01')&(d<=s.END)]) != list(expected):
            raise ValueError('Monitored context lacks exact comparison calendar: '+doc['strategy_id'])
        monitor_rows.append(dict(strategy_id=doc['strategy_id'],name=doc['name'],
            metrics=s.metric(d,n,'2025-01-01',s.END),serving_version=doc['serving_version'],
            batch=doc['input_provenance'].get('batch'),scope=protocol['monitored_references']))
    s.write(s.OUT/'monitored-context.json',monitor_rows)
    # Stability is visible in annual results and annual winner diagnostics; these
    # do not alter the frozen calibration-selected policy or manufacture OOS.
    stability = [dict(year=str(y),selection=s.select(rows,str(y))) for y in range(2021,2027)]
    s.write(s.OUT/'annual-policy-diagnostics.json',stability)
    closes=money_prices(np.column_stack((arrays['close'],arrays['urth_close']))[-1])
    lots=trade_lots(books[chosen][0],dict(zip(symbols,closes)),s.END)
    if abs(sum(r['net_pnl'] for r in lots)-(path(chosen+'_c5d0')['nav'][-1]-1e6))>.05:
        raise ValueError('FIFO trade outcomes do not reconcile')
    s.write(s.OUT/'trade-outcomes.json',lots)
    with (s.OUT/'trade-outcomes.csv').open('w',newline='',encoding='utf8') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(lots[0]));writer.writeheader();writer.writerows(lots)
    date_values=[date.fromisoformat(d) for d in days]
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.facecolor':'white'})
    fig,axs=plt.subplots(2,2,figsize=(14,8),layout='constrained')
    colors=['#086f80','#b56a1d','#634aa5']
    for col,window in enumerate(('calibration','later')):
        a,b=s.WINDOWS[window];ix=np.flatnonzero((days>=a)&(days<=b));dates=np.array(date_values)[ix]
        for (arm,label),color in zip(main_arms,colors):
            nav=path(arm+'_c5d0')['nav'];base=nav[ix[0]-1] if ix[0] else 1e6
            axs[0,col].plot(dates,100*(nav[ix]/base-1),label=label,color=color)
            trace=np.r_[base,nav[ix]];dd=trace/np.maximum.accumulate(trace)-1
            axs[1,col].plot(dates,100*dd[1:],color=color)
        axs[0,col].set_title(window.title()+f' · {days[ix[0]]} to {days[ix[-1]]}')
        axs[0,col].set_ylabel('Net cumulative return (%)');axs[1,col].set_ylabel('Drawdown (%)')
        axs[0,col].legend(fontsize=8,loc='upper left')
    for ax in axs.flat:ax.grid(alpha=.18)
    fig.suptitle('Bill-relative ranking adds value versus removal-only; FR25 retains the risk advantage\nUSD · 5 bp per side · next-open fills · inspected development history',fontsize=14)
    fig.savefig(s.OUT/'comparison.png',dpi=140);plt.close(fig)
    # Weak constituent charts include complete dates, raw activity, target and
    # held states, actual fills and contribution. All trade outcomes remain linked.
    for item in weak:
        symbol,window=item['symbol'],item['window'];j=symbols.index(symbol)
        a,b=s.WINDOWS[window];ix=np.flatnonzero((days>=a)&(days<=b));dates=np.array(date_values)[ix]
        full_ix=np.flatnonzero(arrays['days']>=s.START)[ix]
        fig,axes=plt.subplots(5,1,figsize=(14,12),sharex=True,layout='constrained',gridspec_kw={'height_ratios':[2,1,1,1.2,1.2]})
        axes[0].plot(dates,arrays['close'][full_ix,j],color='#293d59',label='Adjusted close')
        economic,held,_=books[chosen]
        fills=[f for f in economic['fills'] if f['symbol']==symbol and a<=f['date']<=b]
        for buy,color,marker in [(True,'#00816a','^'),(False,'#bf4550','v')]:
            f=[r for r in fills if (r['quantity']>0)==buy]
            axes[0].scatter([date.fromisoformat(r['date']) for r in f],[float(r['price']) for r in f],
                            color=color,marker=marker,s=45,label='Buy fills' if buy else 'Sell fills',zorder=3)
        axes[0].set_ylabel('Adjusted USD');axes[0].legend(loc='upper left',ncol=3)
        axes[1].plot(dates,arrays['raw_close'][full_ix,j],color='#72604e');axes[1].set_ylabel('Audited raw\nclose (USD)')
        axes[2].bar(dates,arrays['raw_volume'][full_ix,j]/1e6,width=2,color='#9faebb');axes[2].set_ylabel('Raw volume\n(million)')
        adopted=np.zeros(len(arrays['days']));last=0.
        event=set(schedules[chosen+'_indices'].tolist())
        for t in range(len(adopted)):
            if t-1 in event:last=schedules[chosen+'_weights'][t-1,j]
            adopted[t]=last
        axes[3].step(dates,100*adopted[full_ix],where='post',color=colors[0],label='Adopted target')
        axes[3].plot(dates,100*held[ix,j],color='#111111',alpha=.65,label='Held weight')
        axes[3].set_ylabel('Portfolio weight (%)');axes[3].legend(loc='upper left',ncol=2)
        for (arm,label),color in zip(main_arms,colors):
            values=path(arm+'_c5d0');base=values['nav'][ix[0]-1] if ix[0] else 1e6
            axes[4].plot(dates,100*np.cumsum(values['contribution'][ix,j])/base,label=label,color=color)
        axes[4].set_ylabel('Net contribution\n(pp of opening NAV)');axes[4].legend(fontsize=8,loc='best')
        for ax in axes:ax.grid(alpha=.18)
        fig.suptitle(f'{symbol} · weakest actual risky-ETF contribution · {window}\n{days[ix[0]]} to {days[ix[-1]]} · {100*item["net_contribution"]:.2f} pp · {len(fills)} fills · no stop/protection in this recipe',fontsize=14)
        fig.savefig(s.OUT/f'weakest-{window}-{symbol}.png',dpi=130);plt.close(fig)
    table=['| Policy | Period | Return | CAGR | Sharpe | Max DD | Calmar | Turnover/yr |',
           '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for window in ('calibration','later'):
        for arm,label in main_arms:
            r=next(r for r in rows if r['arm']==arm and r['cost_bp']==5 and r['delay']==0)['windows'][window]
            table.append(f'| {label} | {window} | {pct(r["cumulative"])} | {pct(r["cagr"])} | {num(r["sharpe"])} | {pct(r["max_drawdown"])} | {num(r["calmar"])} | {num(r["annual_turnover"])} |')
    selected_intervals=[x for x in intervals if x['arm']==chosen]
    selected_guards=[r for r in comparisons if r['arm']==chosen]
    counts={window:{bench:sum(r['passes'] for r in selected_guards if r['window']==window and r['benchmark']==bench)
                   for bench in (control,'FR25_frozen')} for window in ('calibration','later')}
    s.write(s.OUT/'review-summary.json',dict(selected=chosen,guard_counts=counts,weakest=weak,
        selected_intervals=selected_intervals,maximum_book_error_usd=max(x[2] for x in books.values()),
        cases=len(rows),reporter_sha256=s.digest(Path(__file__))))
    body=f'''# Cash-relative momentum net retest — October 31, 2026

The withheld experiment is complete: cash-relative ranking improves the matched
removal-only control, but does not establish a replacement for FR25. Retain it as
research evidence; no monitoring, promotion, funding or execution changed.

The training-selected policy is **class-first / monthly**. Selection used only
2021–2024, with the predeclared return/drawdown guards; later performance did not
choose the policy. All 16 arms and all six frictions were replayed without a cost
or IC veto. The dynamic 0.10 arm has stronger later performance but weaker earlier
performance; choosing it now would be retrospective tuning.

![Net returns and drawdowns](comparison.png)

{chr(10).join(table)}

The selected candidate passes the matched-control guards in {counts['calibration'][control]}/6
calibration and {counts['later'][control]}/6 later settings. Against frozen FR25 it passes
{counts['calibration']['FR25_frozen']}/6 and {counts['later']['FR25_frozen']}/6 respectively.
Sharpe uses zero cash rate; Calmar is annualized return divided by drawdown magnitude.
Annualization uses 252 sessions. BIL's very high zero-rate Sharpe mostly reflects
bill carry and low volatility; it is neither free arbitrage nor a risk-matched ranking.

## What is being compared

Let r_i be 126-session adjusted return and sigma_i the 63-session annualized
sample volatility. The control ranks r_i/sigma_i with r_i > 0. The candidate ranks
(r_i-r_BIL)/sigma_i and requires both r_i > 0 and r_i-r_BIL > 0. BIL has zero target
in both; unused slots remain literal, zero-interest cash. Class construction takes
three classes and up to two funds per class, with frozen overlap exclusions,
inverse-volatility sizing, 98% maximum gross and 45% name cap.

Daily audited history → prior-session liquidity/duplicate eligibility → fixed
126/63 score → pooled six slots or three-by-two classes → capped theoretical
weights plus cash → monthly adoption or strict L1 target-change > 0.10/0.40/0.80
versus last adopted target → next-open execution → actual fills/cash/held weights/NAV.
No stop-loss, trailing protection or learned exit exists in this recipe.

The historical 52-candidate batch supports 50 complete histories, including BIL
as reference. BWX and CPER remain excluded under the original published identity/
raw-activity contract. All supported risky names participate; this closes the
frozen experiment, not a new expanded-universe test. Audited adjusted prices supply
returns; audited raw close and volume supply liquidity and inspection context.
The original published pool and all 5,698 adoption decisions reproduce; Decimal
distance sums tolerate only 1e-24 rounding, with exact targets/states/decisions.

Primary USD1m accounts start January 4, 2021 and continue through October 12, 2026.
The later window starts January 2, 2025 and retains the pre-existing book. Each
window includes its prior-close NAV. Costs are 5/10/20 bp on actual traded notional;
delay is zero/one additional session. Delayed targets are sized at the close before
execution. Prices use the shared engine's cent rounding and adjusted synthetic
whole units, not broker raw shares.
No terminal liquidation, spread, impact, tax, FX conversion or cash interest.

## Weakest ETF inspection

Criterion: lowest **actual net contribution / opening portfolio NAV**, excluding
cash/BIL/URTH, under the training-selected policy at 5 bp and no extra delay.
This portfolio-specific criterion avoids inventing a standalone ETF return when
allocation capital changes. FIFO trade outcomes reconcile to total net PnL.

'''
    for w in weak:
        body+=f'### {w["window"].title()}: {w["symbol"]}, {100*w["net_contribution"]:.2f} percentage points\n\n'
        body+=f'![{w["symbol"]} dated inspection](weakest-{w["window"]}-{w["symbol"]}.png)\n\n'
    body+='''[All dated trade outcomes](trade-outcomes.csv) · [All constituent attribution](attribution.json).
Charts show adjusted prices and actual fill markers, raw price/volume, adopted
and held weights, net contributions and explicit absence of protection. Discuss
visual observations as hypotheses for a newly declared test, not silent tuning.

## Uncertainty and chronology

Eight paired contrasts use 2,000 circular 21-session block resamples with identical
date draws, seed 20261031. Both unadjusted and Bonferroni family intervals are
reported. These are conditional development diagnostics, not selection-adjusted
discovery tests or an untouched holdout. The reserved prospective design was never
activated; elapsed calendar time cannot create prospective evidence.

'''
    for interval in selected_intervals:
        low,high=interval['family_95']
        body+=f'- {interval["window"]}: family-adjusted Sharpe difference [{low[0]:.3f}, {high[0]:.3f}]; CAGR difference [{100*low[1]:.2f}, {100*high[1]:.2f}] pp.\n'
    body+='\n[All annual and friction metrics](results.json) · [All uncertainty intervals](uncertainty.json) · [Annual policy diagnostics](annual-policy-diagnostics.json). Annual winners are descriptive and never replace the frozen policy.\n\n'
    body+='''The family-adjusted intervals include zero in both periods. In 2022 and
2023, subtracting bill return actually hurt this monthly policy; the benefit is
concentrated in 2024–2026. Later average risky exposure is 77.99% versus 77.04%
for removal-only, so average exposure alone does not explain the gain; this is
still not a matched-risk experiment. FR25 averages 97.91% exposure later and is
only 32.72% invested in 2022, when its return is +3.28% versus −4.67% for the
selected candidate. Its advantage depends partly on that defensive behavior,
not a universal law about financial-condition models.

Actual selected-policy annual turnover is 9.15x in calibration and 7.76x later,
equivalent to approximately 45.75 and 38.78 bp/year at the 5 bp assumption.
Actual fees total $20,520.91 and $10,279.48, versus $20,387.92 and $11,382.49 for
removal-only. These measured net outcomes replace the old 44 bp rejection.
The 0.10 dynamic candidate improves later Sharpe to 1.902 but earlier Sharpe is
only 0.349; later turnover is 48.94x and fees $65,192.98. Its apparent later
advantage cannot be used to change the training-selected policy.

The original fixed 1/5/10/21-session signal and payoff diagnostics remain
[available in the historical summary](../cash-relative-momentum-20261017-v1/summary.json).
They are explanatory evidence, not substitutes for these net portfolio results.

'''
    body+='## Current monitored strategies: context only\n\nThe app reports below are USD at their published 5 bp/no-extra-delay convention, rebased on the same January 2, 2025–October 12, 2026 dates. They use their own verified publication vintages, model warmups and inherited holdings. They are not matched same-input causal controls. The frozen FR25 replay above retains its original common-window refit.\n\n| App strategy | Net return | Sharpe | Max DD | Calmar |\n| --- | ---: | ---: | ---: | ---: |\n'
    for row in monitor_rows:
        m=row['metrics'];body+=f'| {row["name"]} | {pct(m["cumulative"])} | {num(m["sharpe"])} | {pct(m["max_drawdown"])} | {num(m["calmar"])} |\n'
    body+='''
## Evidence and handoff

[Frozen protocol](protocol.json) · [Input/adoption verification](input-validation.json) ·
[Independent native accounting](native-validation.json) · [Monitored context provenance](monitored-context.json).
Native LEAN verifies orders/fills/cash/NAV for three declared accounting cases;
it does not independently infer the selection policy. Focused tests verify window
anchors, cash metrics, training-only selection, adoption equality and delayed fills.

Current-cohort survivorship, retrospective taxonomy and historical publication
availability remain limitations. The result warrants discussing why bill-relative
ranking helps and where the extra risk comes from. No new parameter search or
monitoring is implied. Stop here for operator discussion. The next queued item is
the separate full-supported-pool study of the six cost-excluded Alpha101 signals.
'''
    (s.OUT/'results.md').write_text(body,encoding='utf8')
    rendered=render_review(body)
    fills=books[chosen][0]['fills']
    weak_symbols={w['symbol'] for w in weak}
    trade_table='<details><summary>Exact weakest-ETF fills · selected policy</summary><table><tr><th>Date</th><th>ETF</th><th>Quantity</th><th>Adjusted price</th><th>Fee</th></tr>'
    for f in fills:
        if f['symbol'] in weak_symbols:
            trade_table+='<tr>'+''.join('<td>'+html.escape(str(f[k]))+'</td>' for k in ('date','symbol','quantity','price','fee'))+'</tr>'
    trade_table+='</table></details>'
    page='<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Cash-relative net retest</title><style>body{max-width:1180px;margin:36px auto;padding:0 24px;font:17px/1.6 system-ui;color:#203046;background:#f8fafc}h1,h2,h3{line-height:1.25}h2{margin-top:42px}img{width:100%;background:white;border:1px solid #d9e2ec;border-radius:8px}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:9px;border-bottom:1px solid #d9e2ec;text-align:right}th:first-child,td:first-child{text-align:left}a{color:#086f80}details{margin:30px 0;padding:18px;background:white}p{max-width:1050px}</style>'+rendered+trade_table+'</html>'
    (s.OUT/'index.html').write_text(page,encoding='utf8')
    print('Report and weakest charts ready',chosen,weak,flush=True)


if __name__=='__main__':
    main()
