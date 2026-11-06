"""Inspection, paired uncertainty and evidence review for the class/volatility replay."""
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET
import csv

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.stats import rankdata

import research_class_vol_net as s
from research_cash_relative_retest import gzread, passes
from report_cash_relative_retest import money_prices, render_review, trade_lots
from report_fr25_breadth import table
from systematic_trading.research.evidence_review import assess

ERAS=('calibration','later')


def load_path(arm):
    with np.load(s.WORK/'paths'/f'{arm}_c5d0.npz') as z:return dict(z)


def load_reference(folder):
    manifest=s.read(folder/'artifact-manifest.json')
    assert s.digest(folder/'results.json')==manifest['results.json']
    return {(r['arm'],r['cost_bp'],r['delay']):r['windows'] for r in s.read(folder/'results.json')}


def book(arm,a,days,prices):
    econ=gzread(s.WORK/'detail'/f'{arm}_c5d0.json.gz')
    symbols=a['symbols'].tolist()+['URTH'];units=np.zeros(len(symbols));cash=1e6
    held=np.empty_like(prices);fills={}
    for f in econ['fills']:fills.setdefault(f['date'],[]).append(f)
    for i,day in enumerate(days):
        for f in fills.get(day,[]):
            units[symbols.index(f['symbol'])]+=f['quantity']
            cash-=f['quantity']*float(f['price'])+float(f['fee'])
        nav=cash+units@prices[i]
        assert abs(nav-float(econ['nav'][i]['nav']))<.03
        held[i]=units*prices[i]/nav
    return econ,held,fills


def inspect(selected,control,arrays,days,schedules):
    symbols=arrays['symbols'].tolist()+['URTH'];bil=symbols.index('BIL')
    full=np.searchsorted(arrays['days'],days)
    prices=money_prices(np.column_stack([arrays['close'],arrays['urth_close']])[full])
    mix={};weak=[]
    for arm in (control,selected):
        economic,held,fills=book(arm,arrays,days,prices);mix[arm]={}
        values=load_path(arm);weights=schedules[arm+'_weights'];events=set(schedules[arm+'_indices'])
        adopted=np.zeros_like(held)
        for i,t in enumerate(full):adopted[i]=weights[t-1] if t-1 in events else adopted[i-1]
        lots=trade_lots(economic,dict(zip(symbols,prices[-1],strict=True)),str(days[-1]))
        assert abs(sum(r['net_pnl'] for r in lots)-(values['nav'][-1]-1e6))<.05
        for era in ERAS:
            lo,hi=s.parent.WINDOWS[era];ix=np.flatnonzero((days>=lo)&(days<=hi));fi=full[ix]
            bill=held[ix,bil].mean();gross=held[ix].sum(axis=1).mean()
            mix[arm][era]=dict(risky=float(gross-bill),bill=float(bill),cash=float(1-gross))
            if arm!=selected:continue
            opening=values['nav'][ix[0]-1] if ix[0] else 1e6
            pnl=values['contribution'][ix].sum(axis=0)/opening
            j=min((j for j,symbol in enumerate(symbols) if symbol not in ('BIL','URTH')),key=lambda j:(pnl[j],symbols[j]))
            symbol=symbols[j];stem=f'weakest-{era}-{symbol}';rows=[]
            for i,t in zip(ix,fi,strict=True):
                active=t<len(arrays['days'])-1
                rows.append(dict(date=days[i],adjusted_open=arrays['open'][t,j],adjusted_high=arrays['high'][t,j],
                    adjusted_low=arrays['low'][t,j],adjusted_close=arrays['close'][t,j],raw_close=arrays['raw_close'][t,j],
                    raw_volume=arrays['raw_volume'][t,j],admitted_at_close=bool(arrays['admitted'][t,j]),
                    momentum_126=arrays['close'][t,j]/arrays['close'][t-126,j]-1,
                    theoretical_at_close=weights[t,j] if active else None,adopted=adopted[i,j],held=held[i,j],
                    state='held' if held[i,j]>0 else 'out',pnl_usd=values['contribution'][i,j],
                    fills=' / '.join(f"{f['quantity']} @ {f['price']} fee {f['fee']}" for f in fills.get(days[i],[]) if f['symbol']==symbol)))
            with (s.OUT/(stem+'-daily.csv')).open('w',encoding='utf8',newline='') as file:
                writer=csv.DictWriter(file,fieldnames=rows[0]);writer.writeheader();writer.writerows(rows)
            relevant=[dict(r,protection='Positive momentum gate, target cap and residual cash. Next-open adoption exits.') for r in lots
                      if r['symbol']==symbol and r['entry']<=hi and r['exit']>=lo]
            s.write(s.OUT/(stem+'-lots.json'),relevant)
            fig,axes=plt.subplots(4,1,sharex=True,figsize=(12,9),layout='constrained')
            dates=[date.fromisoformat(str(d)) for d in days[ix]];trades=[f for f in economic['fills'] if f['symbol']==symbol and lo<=f['date']<=hi]
            axes[0].plot(dates,arrays['close'][fi,j],color='#29465f',label='Adjusted close')
            for buy,mark,color in [(True,'^','#128069'),(False,'v','#b44956')]:
                part=[f for f in trades if (f['quantity']>0)==buy]
                axes[0].scatter([date.fromisoformat(f['date']) for f in part],[float(f['price']) for f in part],marker=mark,color=color,label='Buy' if buy else 'Sell')
            axes[0].legend(ncol=3);axes[1].bar(dates,arrays['raw_volume'][fi,j]/1e6,color='#9faeb9');axes[1].set_ylabel('Raw volume (M)')
            axes[2].plot(dates,[100*r['theoretical_at_close'] if r['theoretical_at_close'] is not None else np.nan for r in rows],alpha=.45,label='Theoretical')
            axes[2].step(dates,100*adopted[ix,j],where='post',label='Adopted')
            axes[2].plot(dates,100*held[ix,j],label='Held');axes[2].legend(ncol=3);axes[2].set_ylabel('Weight (%)')
            axes[3].plot(dates,100*np.cumsum(values['contribution'][ix,j])/opening,color='#7e526d');axes[3].set_ylabel('Net contribution (pp)')
            fig.suptitle(f'{symbol} · {days[ix[0]]} to {days[ix[-1]]} · {100*pnl[j]:.3f} pp · {len(trades)} fills')
            fig.savefig(s.OUT/(stem+'.png'),dpi=115);plt.close(fig)
            weak.append(dict(era=era,symbol=symbol,contribution=float(pnl[j]),stem=stem))
    s.write(s.OUT/'weakest.json',weak);s.write(s.OUT/'exposure.json',mix)
    return weak,mix


def diagnostics(a,schedules,selected,days):
    intervals=[];curve=[]
    for era in ERAS:
        lo,hi=s.parent.WINDOWS[era];ix=np.flatnonzero((days>=lo)&(days<=hi));n=len(ix)
        rng=np.random.default_rng(20261103)
        draw=ix[((rng.integers(0,n,(4000,(n+20)//21,1))+np.arange(21))%n).reshape(4000,-1)[:,:n]]
        estimates={}
        for key in s.KEYS:
            nav=np.r_[1e6,load_path(key)['nav']]
            r=(nav[1:]/nav[:-1]-1)[draw];sd=r.std(axis=1,ddof=1)
            estimates[key]=np.column_stack((np.divide(r.mean(axis=1)*np.sqrt(252),sd,out=np.zeros_like(sd),where=sd>1e-12),
                                           np.expm1(np.log1p(r).mean(axis=1)*252)))
        for key in s.KEYS:
            ctl='pooled_raw-'+key.split('-')[1]
            if key==ctl:continue
            diff=estimates[key]-estimates[ctl]
            intervals.append(dict(era=era,arm=key,control=ctl,columns=['Sharpe','CAGR'],
                ordinary95=np.quantile(diff,[.025,.975],axis=0).tolist(),family95=np.quantile(diff,[.025/12,1-.025/12],axis=0).tolist()))
        for h in (1,5,10,21,63):
            samples=[]
            for t in np.flatnonzero((a['days']>=lo)&(a['days']<=hi)):
                if t+1+h>=len(a['days']) or a['days'][t+1+h]>hi:continue
                mask=a['admitted'][t]
                x=schedules[selected+'_weights'][t,:-1][mask];y=a['open'][t+1+h,mask]/a['open'][t+1,mask]-1
                if len(x)>3 and np.ptp(x)>0 and np.ptp(y)>0:
                    samples.append(float(np.corrcoef(rankdata(x),rankdata(y))[0,1]))
            curve.append(dict(era=era,horizon=h,dates=len(samples),mean_weight_ic=float(np.mean(samples)) if samples else None))
    s.write(s.OUT/'uncertainty.json',intervals);s.write(s.OUT/'weight-ic.json',curve)
    return intervals


def main():
    s.validate();choice=s.read(s.OUT/'selection.json');winner=choice['selected']
    timing=winner.split('-')[1];ctl='pooled_raw-'+timing
    batches={b:{(r['arm'],r['cost_bp'],r['delay']):r['windows'] for r in s.read(s.OUT/(b+'-results.json'))} for b in ('historical','current')}
    assert all(len(data)==96 for data in batches.values())
    current=batches['current'];a=s.load_arrays();days=a['days'][a['days']>=s.parent.START]
    with np.load(s.WORK/'current.npz') as z:schedules=dict(z)
    weak,mix=inspect(winner,ctl,a,days,schedules)
    intervals=diagnostics(a,schedules,winner,days)
    refs=load_reference(s.parent.OUT)
    alpha=load_reference(s.REPO/'research/alpha101-net-20261031-v1')
    historical_refs=load_reference(s.REPO/'research/cash-relative-net-20261031-v1')
    incumbent=s.REPO/'research/etf-stability-20261103-v1'
    manifest=s.read(incumbent/'artifact-manifest.json')
    s.checked(incumbent,{f:manifest[f] for f in ('withholding.json','attribution.json')})
    def numbers(m):
        return [f"{m['cagr']:.2%}",f"{m['sharpe']:.3f}",f"{m['max_drawdown']:.2%}"]
    header=['Recipe','IS CAGR','IS Sharpe','IS DD','Later CAGR','Later Sharpe','Later DD']
    def wide(label,windows):
        return [label,*numbers(windows['calibration']),*numbers(windows['later'])]
    monthly=table(header,[wide(arm,current[arm+'-monthly',5,0]) for arm in s.ARMS])
    historic=table(header,[wide(arm,batches['historical'][arm+'-monthly',5,0]) for arm in s.ARMS]+
        [wide(k,historical_refs[k,5,0]) for k in ('FR25_frozen','URTH_buyhold')])
    timings=table(header,[wide(key,current[key,5,0]) for key in s.KEYS])
    benchmarks=table(header,[wide(k,refs[k,5,0]) for k in ('original-monthly','expanded-monthly','momentum-monthly','unranked-monthly',
            'cash','BIL_buyhold','URTH_buyhold','pool_buyhold')]+[wide('Alpha54 monthly',alpha['alpha54-monthly',5,0])])
    stress=table(['Fee bp','Extra delay','Era','Net return','CAGR','Sharpe','DD','Calmar','Turnover/yr','Fees USD'],[
        [c,d,e,f"{m['cumulative']:.2%}",*numbers(m),f"{m['calmar']:.2f}" if m['calmar'] is not None else '—',f"{m['annual_turnover']:.2f}",f"{m['fees_usd']:,.0f}"]
        for c,d in s.COSTS for e in ERAS for m in [current[winner,c,d][e]]])
    guard={e:sum(passes(current[winner,c,d][e],current[ctl,c,d][e]) for c,d in s.COSTS) for e in ERAS}
    withheld=s.read(s.OUT/'withholding.json');attr=s.read(s.OUT/'attribution.json')
    concentration=table(['Policy','Era','Three largest risky contributors (pp)','Share of positive ETF P&L','Share of net gain','CAGR, top 1 to cash','CAGR, top 3 to cash','CAGR, IS top 3 to cash'],[
        [key,e,', '.join(f"{symbol} {100*attr[key][e]['by_symbol'][symbol]:.2f}" for symbol in attr[key][e]['top']),
         f"{attr[key][e]['share_positive']:.1%}" if attr[key][e]['share_positive'] is not None else '—',
         f"{attr[key][e]['share_net']:.1%}" if attr[key][e]['share_net'] is not None else '—',
         *[f"{withheld[key][e][k]['cagr']:.2%}" for k in ('top1','top3','is_top3')]] for key in (winner,ctl) for e in ERAS])
    allocation=table(['Policy','Era','Risky ETFs','BIL','Cash'],[[key,e,*[f'{mix[key][e][k]:.2%}' for k in ('risky','bill','cash')]] for key in (winner,ctl) for e in ERAS])
    annual=table(['Year','Selected return / Sharpe','Control return / Sharpe'],[[year,*[f"{m['cumulative']:.2%} / {m['sharpe']:.3f}"
        for k in (winner,ctl) for m in [current[k,5,0][str(year)]]]] for year in range(2021,2027)])
    ci=table(['Era','Family 95% Sharpe difference','Family 95% CAGR difference'],[[r['era'],
        ' to '.join(f'{v[0]:.2f}' for v in r['family95']),' to '.join(f'{v[1]:.1%}' for v in r['family95'])] for r in intervals if r['arm']==winner])
    diffs={}
    for t in s.TIMES:
        for c,d in s.COSTS:
            for e in ERAS:
                for left,right in [('class_raw','pooled_raw'),('class_risk','pooled_risk'),('pooled_risk','pooled_raw'),('class_risk','class_raw')]:
                    x=current[left+'-'+t,c,d][e];y=current[right+'-'+t,c,d][e]
                    diffs[f'{left} vs {right}/{t}/{c}/{d}/{e}']=dict(sharpe=x['sharpe']-y['sharpe'],cagr=x['cagr']-y['cagr'],
                        dd=x['max_drawdown']-y['max_drawdown'],passes=passes(x,y))
    s.write(s.OUT/'paired-effects.json',diffs)
    weak_md='\n\n'.join(f"### {r['era']} · {r['symbol']} ({100*r['contribution']:.3f} pp)\n\n![Dated inspection]({r['stem']}.png)\n\n[Daily states, volume and fills]({r['stem']}-daily.csv) · [FIFO outcomes]({r['stem']}-lots.json)" for r in weak)
    body=f"""# Class and volatility construction after trading costs

The training choice was **{winner}**. It earned 6.16% CAGR in training and 2.73% later. Its later Sharpe of 3.68 accompanies 12.96% average risky ETF exposure, 45.03% BIL and 42.01% cash. BIL buy-and-hold earned 3.94% later. Zero-interest cash and a zero-rate Sharpe reference matter here. The family supplies a low-risk historical allocation, with limited evidence for superior portfolio growth.

## Four monthly controls on 52 supported histories

{monthly}

Raw means the **unscaled adjusted-price return**. The risk score divides 126-session return by annualized 63-session sample volatility. Both scores require positive momentum, complete prior data and admission. Pooled selection takes up to six ETFs. Class-first selection ranks classes by the mean score of up to two eligible members, takes up to three classes, then sizes members by inverse volatility within their class budget. Overlap exclusions, empty-slot cash, 98% total budget and final 45% per-ETF cap apply. BIL competes for slots. Dividing by volatility for both ranking and sizing can favor bills. [Exact classes and overlap policy](construction.json).

With raw scores, class-first beat pooled on later CAGR and Sharpe but did so after a modest training return. With volatility-adjusted scores, class-first returned about zero later. The separate class and score comparisons depend on the other choice. [All matched effects across timing and friction](paired-effects.json).

## Selection, timing and holdings

{choice['eligible']} of 12 challengers qualified in 2021–2024. The return floor was the higher of BIL training CAGR ({choice['bill_cagr']:.2%}) and matched pooled-raw CAGR minus 0.5 pp. Drawdown could worsen by up to 2 pp. Both training halves, the top-three withholding run and the 20 bp extra-delay run had to retain positive CAGR. The tie order favored higher weaker-half Sharpe and CAGR. The decision was sealed before later performance was calculated. [Training grid](training.json) · [Selection seal](selection.json).

{allocation}

Each timing policy has a monthly anchor. Dynamic thresholds adopt when the L1 distance from the last adopted target, including cash, strictly exceeds 0.10, 0.40 or 0.80. The later period begins January 2, 2025 and ends October 30, 2026. Each strategy carries its own positions across the boundary. All use whole adjusted units and next-open or one-session-delayed fills. Later periods were already inspected in related research.

{timings}

## Dependence on winners and chronological stability

{concentration}

Positive-share denominators include BIL. For net losses the net-share cell is left blank. Exclusions keep the adoption dates and other target weights, send the removed positions to cash, and recalculate fills, fees and NAV. Each era's own leaders are retrospective stresses. Both FR25 incumbents use these same current dates, prices and costs. Their verified later top-three-withheld CAGRs were 10.63% (original14) and 18.81% (expanded). [Incumbent withholding results](../etf-stability-20261103-v1/withholding.json).

{annual}

For the selected rule, the absolute CAGR gap is {100*abs(current[winner,5,0]['later']['cagr']-current[winner,5,0]['calibration']['cagr']):.2f} pp and the Sharpe gap is {abs(current[winner,5,0]['later']['sharpe']-current[winner,5,0]['calibration']['sharpe']):.3f}. Assess these alongside cash and BIL exposure. The paired 21-session block intervals below compare the selected policy with pooled raw at matched timing, with Bonferroni adjustment for 12 contrasts and 4,000 draws. Earlier searches and regime uncertainty remain.

{ci}

## Benchmarks, costs and delay

{benchmarks}

{stress}

The selected policy passed the same-timing pooled-raw Sharpe/return/drawdown guards in {guard['calibration']}/6 training and {guard['later']}/6 later frictions. All six frictions are retained for every recipe. [Current net results](current-results.json) · [Uncertainty](uncertainty.json). The weight/forward-open-return rank correlations use 1/5/10/21/63-session endpoints inside each era. These overlapping diagnostics cannot identify a unique half-life. [Horizon results](weight-ic.json).

## Original withheld books

The 50-name October screen is a separate replay on its own published price batch and original targets. All 5,800 original daily target vectors and 4,485 adopted decisions were read from hash-verified evidence. All sixteen policies received all six cost/delay cases. Later dates end October 12 here. The current 52-name run adds supported CPER in the existing base-metals class and USO in a new commodity energy class with a DBC overlap conflict. BWX and XOP remain excluded on identity grounds. The two batches and end dates differ.

{historic}

[All original net results](historical-results.json) · [Target receipts](target-receipt.json) · [Both publication verifications](inputs.json). The earlier proxy-gate verdict remains historical evidence.

## Weakest risky ETF inspections

Lowest net contribution divided by era-opening NAV under the training-selected 5 bp, next-open policy. BIL, cash and URTH are excluded. Protection consists of positive momentum eligibility, overlap rules, the name cap and unused-slot cash. Fills occur at adopted rebalances with no intraday stop. Trade files contain full cross-era lots and mark open positions through the final date.

{weak_md}

## Evidence boundary

Prices are dividend/split-adjusted. Raw price and volume support liquidity and activity checks. Cohort membership and historical dissemination remain reconstructed, and fixed costs omit measured spreads and impact. This retrospective study grants research evidence only. [Protocol](protocol.json) · [Independent native accounting](native-validation.json) · [Dossier](dossier.json) · [Assessment](assessment.json).
"""
    (s.OUT/'results.md').write_text(body,encoding='utf8')
    css='body{font:16px/1.55 system-ui;color:#233947;max-width:1160px;padding:2rem;margin:auto}table{border-collapse:collapse}th,td{border-bottom:1px solid #d4e0e5;padding:.45rem;text-align:left}img{max-width:100%}a{color:#05657b}'
    (s.OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Class and volatility net comparison</title><style>'+css+'</style>'+render_review(body),encoding='utf8')
    s.write(s.OUT/'summary.json',dict(selected=winner,qualified=choice['qualified'],guard=guard,weakest=weak,exposure=mix,
        current_cases=len(current),historical_cases=len(batches['historical']),primary=current[winner,5,0]))


def close():
    p=s.validate();summary=s.read(s.OUT/'summary.json');choice=s.read(s.OUT/'selection.json')
    native=s.read(s.OUT/'native-validation.json')
    assert len(native['cases'])==3 and all(r['status']=='succeeded' and r['max_nav_error_usd']<=.01 for r in native['cases'])
    dossier=s.read(s.parent.OUT/'dossier.json')
    dossier.update(study_id=s.OUT.name,candidate_id=choice['selected'],preregistered_net_rule=p['select'],net_verdict='not_established',
        operator_disposition='Numerical item complete, awaiting discussion.',prospective_plan_or_gap='Previously inspected chronological evaluation. Fresh evidence requires subsequent audited observations and a prior recipe freeze.')
    dossier['sample'].update(recipe_frozen_at=p['frozen_at'],trial_count=16,prior_search_and_multiplicity='Four rules x four timings. Twelve challenger/control contrasts. Earlier exploratory searches are additional multiplicity.',
        label_boundary_and_overlap='IS-only portfolio engine stops on 2024-12-31. Rank-IC forward labels end in the reported era. Net return intervals use paired 21-session blocks.')
    dossier['decay']=[dict(signal='Daily class/volatility portfolio target mapping',status='unidentifiable',horizons=[1,5,10,21,63],half_life_sessions=None,
        method_uncertainty_and_caveats='Cross-sectional target-weight IC at overlapping open-to-open horizons does not determine an exponential half-life. No fitted decay interval.',
        cadence_and_delay_interpretation='Monthly and three target-change policies compared at six frictions, alongside chronological net results.')]
    dossier['coverage_gaps']=['Both eras previously inspected. No fresh prospective validation.','Membership availability, spreads and impact remain unresolved.',
        'Conditional intervals and 12-contrast adjustment omit lifetime multiplicity.']
    roles={'protocol.json':['protocol'],'construction.json':['strategy_recipe'],'inputs.json':['published_input_verification'],
        'selection.json':['selection'],'current-results.json':['net_results','cost_delay','chronology'],'historical-results.json':['net_results'],
        'paired-effects.json':['matched_controls'],'results.md':['matched_controls','weakest_inspections'],'uncertainty.json':['uncertainty'],
        'weight-ic.json':['decay_stability'],'native-validation.json':['independent_validation']}
    for row in summary['weakest']:roles[row['stem']+'.png']=['weakest_inspections']
    dossier['artifacts']=[dict(path=(s.OUT/n).relative_to(s.REPO).as_posix(),sha256=s.digest(s.OUT/n),roles=r) for n,r in roles.items()]
    s.write(s.OUT/'dossier.json',dossier)
    review=assess(dossier,s.REPO,s.REPO/'config/research-evidence-policy-v1.json')
    assert not review['integrity_and_claim_issues'];s.write(s.OUT/'assessment.json',review)
    suite=next(iter(ET.parse(s.REPO/'var/maintenance/class-vol-net-20261103/tests.xml').getroot()))
    assert int(suite.attrib['errors'])==int(suite.attrib['failures'])==0
    s.write(s.OUT/'acceptance.json',dict(tests=int(suite.attrib['tests']),native=native['cases'],status=review['status'],
        cases=192,selected=choice['selected'],source_sha256=p['code_sha256'],reporter_sha256=s.digest(Path(__file__)),
        assessment_sha256=s.digest(s.OUT/'assessment.json'),target_receipt_sha256=s.digest(s.OUT/'target-receipt.json')))
    s.write(s.WORK/'summary.json',summary)
    s.write(s.OUT/'retention.json',dict(retain='Protocol, class mapping, runners, compact findings, charts, trade outcomes and receipts.',
        classification='Generated schedules, paths, detail and native source/bundles/output are disposable after discussion and dependency review. Historical and current inputs are shared. Guarded cleanup must verify active dependencies and record actual retirement.',deleted=False))
    s.write(s.OUT/'artifact-manifest.json',{f.name:s.digest(f) for f in s.OUT.iterdir() if f.is_file() and f.name!='artifact-manifest.json'})


if __name__=='__main__':
    import sys
    close() if sys.argv[1:]==['close'] else main()
