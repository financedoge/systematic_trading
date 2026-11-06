"""Dated expanded FR25 evidence, net uncertainty and weakest-ETF review."""
from datetime import date
from pathlib import Path
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import rankdata

import research_expanded_fr25_net as s
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


def write_csv(file,rows):
    with file.open('w',newline='',encoding='utf8') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)


def draws(n,count,rng):
    return np.concatenate([(rng.integers(0,n,(count,1))+np.arange(21))%n
        for _ in range((n+20)//21)],axis=1)[:,:n]


def uncertainty(rows,days):
    output=[]
    for window in ('calibration','later'):
        start,end=s.WINDOWS[window];ix=np.flatnonzero((days>=start)&(days<=end))
        draw=draws(len(ix),4000,np.random.default_rng(20261102));estimates={}
        for policy in s.POLICIES:
            for model in ('expanded','original','m1','momentum','unranked'):
                arm=model+'-'+policy;nav=np.r_[1e6,path(arm)['nav']]
                r=(nav[1:]/nav[:-1]-1)[ix][draw];std=r.std(axis=1,ddof=1)
                estimates[arm]=np.column_stack([np.divide(r.mean(axis=1)*np.sqrt(252),std,
                    out=np.zeros(len(r)),where=std>1e-12),np.exp(np.log1p(r).mean(axis=1)*252)-1])
            for control in ('original','m1','momentum','unranked'):
                arm='expanded-'+policy;base=control+'-'+policy;diff=estimates[arm]-estimates[base]
                output.append(dict(arm=arm,control=base,window=window,columns=['Sharpe','CAGR'],
                    ordinary_95=np.quantile(diff,[.025,.975],axis=0).tolist(),
                    family_95=np.quantile(diff,[.025/16,1-.025/16],axis=0).tolist()))
    return output


def diagnostics(a,signals):
    output=[];days=a['days'];score=signals['score'];symbols=a['symbols'].tolist()
    for window in ('calibration','later'):
        start,end=s.WINDOWS[window]
        for h in (1,5,10,21,63):
            ic=[];dates=[]
            for t in np.flatnonzero((days>=start)&(days<=end)):
                if t+1+h>=len(days) or days[t+1+h]>end:continue
                mask=a['admitted'][t]&np.isfinite(score[t]);mask[symbols.index('BIL')]=False
                x=score[t,mask];y=a['open'][t+1+h,mask]/a['open'][t+1,mask]-1
                if len(x)<6 or np.std(x)<1e-12 or np.std(y)<1e-12:continue
                ic.append(float(np.corrcoef(rankdata(x),rankdata(y))[0,1]));dates.append(str(days[t]))
            v=np.array(ic);draw=draws(len(v),1000,np.random.default_rng(20261102))
            output.append(dict(window=window,horizon=h,dates=len(v),mean_ic=float(v.mean()),
                block_95=np.quantile(v[draw].mean(axis=1),[.025,.975]).tolist(),
                annual={str(y):float(np.mean([x for d,x in zip(dates,ic) if d.startswith(str(y))]))
                    for y in range(2021,2027) if any(d.startswith(str(y)) for d in dates)},
                half_life_sessions=None,status='unidentifiable',
                caveat='Return-horizon rank IC does not identify an exponential signal half-life; overlapping labels, reused history and changing cross-section. 21-session blocks may understate dependence for63-session labels. No net-profitability veto.'))
    return output


def main():
    protocol=s.validate();rows=s.read(s.OUT/'results.json');selection=s.read(s.OUT/'selection.json')
    a=dict(np.load(s.WORK/'inputs.npz'));signals=dict(np.load(s.WORK/'signals.npz'));schedules=dict(np.load(s.WORK/'schedules.npz'))
    target_tape=s.gzread(s.WORK/'targets/expanded.json.gz')
    by_known={r['known_through']:r for r in target_tape.values()}
    days=a['days'][a['days']>=s.START];symbols=a['symbols'].tolist()+['URTH'];chosen=selection['selected']
    control='momentum-'+chosen.split('-')[1];unranked='unranked-'+chosen.split('-')[1]
    policy=chosen.split('-')[1]
    main_arms=[(chosen,'Expanded FR25'),('original-'+policy,'Original14 FR25'),('m1-'+policy,'Expanded M1')]
    cache={r['arm']:path(r['arm']) for r in rows if r['cost_bp']==5 and r['delay']==0}
    books={arm:book(arm,a) for arm,_ in main_arms};lookup={(r['arm'],r['cost_bp'],r['delay']):r for r in rows}
    comparisons=[]
    for r in rows:
        if not r['arm'].startswith('expanded-'):continue
        policy=r['arm'].split('-')[1]
        for benchmark in ('original-'+policy,'m1-'+policy,'momentum-'+policy,'unranked-'+policy,'cash','BIL_buyhold','URTH_buyhold','pool_buyhold'):
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
        stats={p:s.metric(days,cache['expanded-'+p]['nav'],s.START,f'{y}-12-31') for p in s.POLICIES}
        winner=sorted(stats,key=lambda p:(-stats[p]['sharpe'],p))[0]
        stability.append(dict(training_end=f'{y}-12-31',policy=winner,metrics=stats))
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
    fig.suptitle('Expanded FR25 · training-selected timing and matched net references\nUSD · 5 bp per side · next-open fills · retrospective development evidence')
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
        theoretical=np.array([schedules[chosen+'_weights'][t,j] if str(a['days'][t]) in by_known else np.nan for t in fi])
        axes[3].plot(dates[ix],100*theoretical,color='#a8b9c3',alpha=.5,label='Theoretical at close')
        axes[3].step(dates[ix],100*adopted[fi],where='post',color=colors[0],label='Adopted target')
        axes[3].plot(dates[ix],100*held[ix,j],color='#222222',alpha=.65,label='Held weight');axes[3].set_ylabel('Weight (%)');axes[3].legend(ncol=3,fontsize=8)
        for (arm,label),color in zip(main_arms,colors):
            v=cache[arm];base=v['nav'][ix[0]-1] if ix[0] else 1e6
            axes[4].plot(dates[ix],100*np.cumsum(v['contribution'][ix,j])/base,label=label,color=color)
        axes[4].set_ylabel('Net contribution\npp of opening NAV');axes[4].legend(fontsize=8)
        for ax in axes:ax.grid(alpha=.2)
        fig.suptitle(f'{symbol} · weakest risky contribution · {window}\n{days[ix[0]]} to {days[ix[-1]]} · {100*item["net_contribution"]:.2f} pp · {len(fills)} fills · allocation protections; no stop')
        fig.savefig(s.OUT/f'weakest-{window}-{symbol}.png',dpi=130);plt.close(fig)
        traces=[]
        for k,t in enumerate(fi):
            trades=[f for f in fills if f['date']==str(a['days'][t])]
            state=by_known.get(str(a['days'][t]))
            traces.append(dict(date=str(a['days'][t]),adjusted_open=a['open'][t,j],adjusted_high=a['high'][t,j],adjusted_low=a['low'][t,j],adjusted_close=a['close'][t,j],
                raw_close=a['raw_close'][t,j],raw_volume=a['raw_volume'][t,j],score=signals['score'][t,j],
                theoretical_at_close=theoretical[k],adopted=adopted[t],held=held[ix[k],j],
                eligible=None if state is None else symbol in state['selection']['eligible'],
                defensive_fallback=None if state is None else state['selection']['fallback'],
                financial_ready=None if state is None else state['financial_ready'],
                financial_source=None if state is None else state['financial_known_through'],
                state='held' if held[ix[k],j]>0 else 'cash for this ETF',protection='No stop; positive126 eligibility, defensive cash fallback, final45% target cap',
                fills='; '.join(f'{f["quantity"]}@{f["price"]} fee {f["fee"]}' for f in trades),
                net_contribution_usd=cache[chosen]['contribution'][ix[k],j]))
        write_csv(s.OUT/f'weakest-{window}-{symbol}-daily.csv',traces)
        write_csv(s.OUT/f'weakest-{window}-{symbol}-trades.csv',[r for r in lots if r['symbol']==symbol and r['entry']<=end and r['exit']>=start])
    policy=chosen.split('-')[1]
    references=['original-'+policy,'m1-'+policy,control,unranked,'cash','BIL_buyhold','URTH_buyhold','pool_buyhold']
    counts={w:{b:sum(r['passes'] for r in comparisons if r['arm']==chosen and r['benchmark']==b and r['window']==w)
        for b in references} for w in ('calibration','later')}
    established=all(counts[w][b]==6 for w in counts for b in references[:4])
    verdict=('A guarded retrospective advantage appears across the declared cases; fresh validation remains necessary.' if established else
        'Expanded FR25 does not establish robust net superiority over the matched controls across both eras. Retain the completed numerical study as research evidence; no recipe is promoted.')
    def table(headers,records):
        return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',
            *['| '+' | '.join(map(str,row))+' |' for row in records]])
    def stats(arm,w,c=5,d=0):
        m=lookup[arm,c,d]['windows'][w]
        return [pct(m['cumulative']),pct(m['cagr']),num(m['sharpe']),pct(m['max_drawdown']),num(m['annual_turnover']),f'{m["fees_usd"]:,.0f}']
    main_table=table(['Recipe','Period','Net return','CAGR','Sharpe','Max DD','Turnover/yr','Fees USD'],
        [[label,w,*stats(arm,w)] for w in counts for arm,label in main_arms])
    timing=table(['Expanded timing','Training return / Sharpe','Later return / Sharpe','Training / later turnover'],[
        [p,' / '.join(stats('expanded-'+p,'calibration')[::2][:2]),' / '.join(stats('expanded-'+p,'later')[::2][:2]),
         stats('expanded-'+p,'calibration')[4]+' / '+stats('expanded-'+p,'later')[4]] for p in s.POLICIES])
    guard_table=table(['Control','Training guard passes','Later guard passes'],[[b,str(counts['calibration'][b])+'/6',str(counts['later'][b])+'/6'] for b in references])
    control_table=table(['Reference','Period','Net return','CAGR','Sharpe','Max DD','Turnover/yr','Fees USD'],[[b,w,*stats(b,w)] for b in references[2:] for w in counts])
    annual=table(['Year','Expanded return / Sharpe','Original14 return / Sharpe','M1 return / Sharpe'],
        [[str(y),*[' / '.join(stats(arm,str(y))[::2][:2]) for arm,_ in main_arms]] for y in range(2021,2027)])
    stress=table(['Cost bp','Extra delay','Period','Net return','CAGR','Sharpe','Max DD','Turnover/yr','Fees USD'],
        [[c,d,w,*stats(chosen,w,c,d)] for c,d in protocol['frictions'] for w in counts])
    selected_intervals=[r for r in intervals if r['arm']==chosen]
    ci=table(['Period','Control','Family95% Sharpe difference','Family95% CAGR difference'],[
        [r['window'],r['control'],f'{r["family_95"][0][0]:.3f} to {r["family_95"][1][0]:.3f}',
         pct(r['family_95'][0][1])+' to '+pct(r['family_95'][1][1])] for r in selected_intervals])
    decay_table=table(['Period','Forward sessions','Rank IC','Block95% interval'],[
        [r['window'],r['horizon'],num(r['mean_ic']),' to '.join(num(v) for v in r['block_95'])] for r in diag])
    tape=s.gzread(s.WORK/'targets/expanded.json.gz')
    macro={w:dict(days=sum(start<=d<=end for d in tape),financial_ready=sum(r['financial_ready'] for d,r in tape.items() if start<=d<=end),
        financial_carried=sum(r['financial_known_through']!=r['known_through'] for d,r in tape.items() if start<=d<=end),
        usd_carried=sum(r['usd_known_through']!=r['known_through'] for d,r in tape.items() if start<=d<=end and r['known_through']>='2024-03-28'))
        for w,(start,end) in s.WINDOWS.items() if w in counts}
    s.write(s.OUT/'macro-coverage.json',macro)
    dollars=a['raw_close']*a['raw_volume']
    import pandas as pd
    med=pd.DataFrame(dollars).rolling(63).median().to_numpy()
    participation=[]
    for f in books[chosen][0]['fills']:
        t=int(np.searchsorted(a['days'],f['date']))-1;j=symbols.index(f['symbol'])
        participation.append(dict(date=f['date'],symbol=f['symbol'],fraction=abs(f['quantity'])*float(f['price'])/med[t,j]))
    liquidity=dict(max_fraction=max(r['fraction'] for r in participation),above_half_percent=[r for r in participation if r['fraction']>.005],
        basis='Actual adjusted-unit notional / prior63-session median audited raw-dollar volume; diagnostic only, not measured market impact.')
    s.write(s.OUT/'liquidity.json',liquidity)
    weak_text=[]
    for r in weak:
        stem=f'weakest-{r["window"]}-{r["symbol"]}'
        weak_text.append(f'### {r["window"]}: {r["symbol"]}, {100*r["net_contribution"]:.2f} pp\n\n![Dated inspection]({stem}.png)\n\n[Daily prices, raw volume, weights, states and fills]({stem}-daily.csv) · [FIFO outcomes]({stem}-trades.csv). Whole cross-era lots and final open marks are included; their sum is not the era contribution.')
    independence=table(['Model','Training-selected timing'],list(selection['per_model'].items()))
    body=f'''# Expanded-pool FR25 net replay — November 2, 2026

{verdict}

**Completed {len(rows)} cost/delay cases. Training-selected expanded policy: {chosen}.** {protocol['supported_count']} supported histories from {protocol['candidate_count']} candidates. Both eras are previously inspected historical evidence. The later period cannot select or rescue a recipe.

## Main comparison

All three recipes below use the expanded recipe's training-selected timing to isolate recipe differences. Net USD1m replay,5bp per traded notional, next-open fills. Original14 is freshly refitted on the same warmup; it is distinct from the app's longer-warmup incumbent evidence.

{main_table}

![Net portfolio and drawdown comparison](comparison.png)

## Decision flow and mathematical definitions

Published audited price/raw-volume and macro vintages → complete common calendar from {protocol['common_start']} → prior253 observations and raw-dollar/duplicate admission → M1 or FR25 ranks → positive126-session gate → top6/minimum4, otherwise qualifying IEF/TLT/GLD weights plus cash → original inverse-volatility base and rolling-XGBoost/relative/adaptive/activity/USD sizing → final45% target cap, excess cash → monthly or target-change adoption → delayed next-open whole adjusted-unit fills → fees and daily net NAV.

M1 combines 75% momentum and25% volume score. Momentum combines ranked21/63/126-session returns with20%/35%/45% weights. FR25 combines75% M1 midrank and25% financial total-return forecast midrank. The financial forecast is a per-ETF standardized expanding ridge (alpha1, minimum36 completed monthly labels) on eight features from five published financial series. Missing financial inputs revert the whole selector to M1. XGBoost has zero selector weight and retains its downstream sizing role. [Exact versioned definitions](definitions.json) retain every overlay parameter.

Original14 and expanded FR25 share the same common price warmup and model fitting schedule. Expanded M1 changes only the financial selector and retains every downstream layer and the final cap. Expanded BIL can compete, preserving the original expansion recipe. Simple momentum ranks126-session returns; it and the unranked inverse63-vol control exclude BIL from risky ranks and share98% budget/final45% cap/admission. Admission never forces allocation. Cash, BIL, URTH and full risky-pool initial equal-weight buy-and-hold remain references.

Dynamic adoption uses strict L1 target distance >0.10/0.40/0.80 versus the last adopted target, including cash, plus monthly first-session adoption. Actual held drift does not trigger it. Models refit monthly. Financial forecasts retain the causal monthly source date. USD uses an exact published snapshot where available, otherwise the previous month with a35-day limit. These explicit carries do not invent daily macro data. [Macro readiness and carry counts](macro-coverage.json).

## Timing, costs and execution delay

{timing}

{stress}

The selected policy maximizes2021–2024 primary net Sharpe only. Guards require strictly higher Sharpe, CAGR loss no more than0.5pp and drawdown worsening no more than2pp. Six cases span5/10/20bp and zero/one extra session; they are sensitivity cases, not independent discoveries. No cost ceiling or IC veto applies.

{guard_table}

{control_table}

Independently training-selected controls below are additional diagnostics; the main comparison remains matched timing. Their complete six-case metrics are retained in [all results](results.json).

{independence}

## Chronological stability and uncertainty

{annual}

Training-prefix policy choices for2021/22/23/24: {', '.join(r['policy'] for r in stability)}. [Full prefix metrics](training-stability.json). [All constituent attribution](attribution.json) exposes both recipes' asset dependence. [Every ETF fresh-era buyhold reference](individual-buyhold.json) uses fractional units and one5bp entry fee, unlike the whole-unit portfolio replay.

{ci}

Paired circular21-session bootstrap,4000 draws, seed20261102. Family intervals cover16 declared expanded-policy/control contrasts using Bonferroni tails. They are approximate: dependence, regimes, small tail samples and the much larger prior strategy search remain. They do not restore an untouched holdout or implement Dwork et al.'s formal reusable-holdout method.

{decay_table}

Forward next-open gross rank IC is a diagnostic. Horizons1/5/10/21/63 were declared before results and labels end inside each era.1000 block draws estimate uncertainty;21-session blocks can understate63-session label dependence. No exponential half-life is identified from these return-horizon curves. Annual net contrasts and cost/delay behavior remain the portfolio evidence. [Full diagnostics](signal-diagnostics.json).

## Weakest risky ETF inspections

Criterion: lowest actual net contribution divided by era-opening portfolio NAV, under the selected expanded policy at5bp/next-open, excluding BIL/URTH/cash. This measures actual portfolio damage with changing allocations, rather than standalone ETF return. Charts include dated adjusted prices, audited raw volume, fills, theoretical/adopted/held weights and contributions. Protection is allocation-based positive-momentum eligibility, defensive cash fallback and a45% target cap; there is no intraday stop. Held weights can drift. [All FIFO outcomes](trade-outcomes.csv) reconcile to full net P&L.

{(chr(10)*2).join(weak_text)}

Visual observations are hypotheses for a future declared test, never silent retrospective tuning. Largest selected-book order was {100*liquidity['max_fraction']:.3f}% of prior median raw-dollar volume; {len(liquidity['above_half_percent'])} orders exceeded the0.5% diagnostic. [Participation details](liquidity.json). Dollar activity does not certify spreads or execution impact.

## Evidence and limits

Pinned price batch: {protocol['price_pin']['batch']}. BWX/XOP retain identity holds. Adjusted return prices and audited raw activity have verified publication hashes. Historical membership and price-publication availability remain reconstructed; archived macro availability and first-seen limitations are retained. Zero cash interest, no FX/taxes/measured spread/impact; whole adjusted units are synthetic research accounting. No inputs were acquired directly from online prices.

[Frozen protocol](protocol.json) · [Input verification](input-verification.json) · [Monthly policy parity](monthly-target-parity.json) · [Native LEAN accounting checks](native-validation.json) · [Evidence dossier](dossier.json) · [P4.20 assessment](assessment.json) · [Acceptance receipt](acceptance.json).

Native LEAN checks orders/fills/cash/NAV on frozen targets, not independent policy inference. Shared-policy parity and tests separately address recipe preservation, causal histories, adoption and selection. Reused chronological evidence is not prospective validation. Formal paper/monitoring/promotion evidence and operator approval would still be required for those stages.

**Stop for discussion after this item.** Next is the class/volatility-construction net replay. No monitoring, funding, promotion or broker action has been taken.
'''
    (s.OUT/'results.md').write_text(body,encoding='utf8')
    html='<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Expanded FR25 net replay</title><style>body{font:16px/1.65 system-ui;color:#193044;max-width:1200px;margin:auto;padding:32px;background:#f7fafb}h1,h2,h3{line-height:1.25;color:#103c53}h2{margin-top:2em}table{border-collapse:collapse;width:100%;font-size:14px;background:white}th,td{padding:10px;border-bottom:1px solid #dce6eb;text-align:left}th{background:#e8f1f4}img{width:100%;height:auto;border:1px solid #dce6eb;background:white}a{color:#006b83}p{max-width:1100px}</style></head><body>'+render_review(body)+'</body></html>'
    (s.OUT/'index.html').write_text(html,encoding='utf8')
    s.write(s.OUT/'review-summary.json',dict(selected=chosen,per_model=selection['per_model'],guard_counts=counts,weakest=weak,
        selected_intervals=selected_intervals,book_error_usd=max(v[2] for v in books.values()),cases=len(rows),verdict=verdict,
        reporter_sha256=s.digest(Path(__file__))))
    print(s.read(s.OUT/'review-summary.json'),flush=True)


if __name__=='__main__':main()
