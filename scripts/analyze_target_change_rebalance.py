"""Read sealed replays, apply the registered assessment, and render research reports."""
from datetime import UTC, datetime
from decimal import Decimal as D
import argparse
import csv
import html
import os
from pathlib import Path
import shutil
import sys

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[variable]='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import (
    checked_files, freeze_usd_bundle, read_json, run_usd_reference, verify_usd_bundle,
)
from systematic_trading.research.momentum_analysis import holm, statistics
from systematic_trading.research.target_change_rebalance import guards, select_threshold, window_metrics

ROOT=Path('var/research/target-change-rebalance-20261015-v1/run-02')
OUTPUT=Path('research/target-change-rebalance-20261015-v1')


def name(arm,policy,cost=5,delay=0):
    return f'{arm}-{policy}-c{cost}-d{delay}-n1000000'


def metrics(root,arm,policy,start='2021-01-04',end='2026-10-14',cost=5,delay=0):
    key=name(arm,policy,cost,delay)
    eco=read_json(root/'python'/(key+'.json'))
    stored=read_json(root/'metrics'/(key+'.json'))
    return window_metrics(eco,start,end,turnover_by_day=stored['turnover_by_day'])


def benchmark(root):
    parent=Path(read_json(root/'coverage.json')['parents']['F3']['root'])/'bundles/URTH'
    verify_usd_bundle(parent)
    all_sessions=read_json(parent/'sessions.json')
    sessions=[d for d in all_sessions if d>='2021-01-04']
    quotes={s:{d:q[d] for d in sessions} for s,q in read_json(parent/'quotes.json').items()}
    old=next(iter(read_json(parent/'decisions.json').values()))
    decision=dict(old,signal_session=sessions[0],known_through='2020-12-31')
    bundle=root/'bundles/URTH-context'
    freeze_usd_bundle(bundle,root,dict(benchmark='URTH_buy_hold'),{sessions[0]:decision},quotes,sessions,5)
    eco=run_usd_reference(bundle)
    write_json(root/'python/URTH-context.json',eco)
    return eco,quotes


def independent_events(root,arm,policy):
    """Check every event against the last adopted vector, without policy helpers."""
    tape=read_json(root/'targets'/(arm+'.json'))
    monthly=set(read_json(root/'monthly'/(arm+'.json')))
    switches=read_json(root/'selections.json')['switches'] if policy=='walk_forward' else {}
    mode='monthly' if policy=='walk_forward' else policy
    expected=[];anchor=None
    ledger=read_json(root/'events'/(name(arm,policy)+'.json'))['ledger']
    for (day,row),logged in zip(tape.items(),ledger,strict=True):
        mode=switches.get(day,mode)
        vector={t['symbol']:D(t['target_weight']) for t in row['targets']}
        vector['CASH']=1-sum(vector.values())
        gap=None if anchor is None else sum(abs(vector.get(s,D(0))-anchor.get(s,D(0)))
            for s in sorted(set(vector)|set(anchor)))
        crossed=mode not in ('monthly','daily') and gap is not None and gap>D(mode)
        chosen=anchor is None or day in monthly or mode=='daily' or crossed
        if chosen:
            expected.append(day);anchor=vector
        logged_gap=D(logged['distance']) if logged['distance'] is not None else None
        # Independent summation uses sorted symbols; Decimal's finite precision
        # permits last-place differences from the policy's set iteration order.
        gap_mismatch=(logged_gap is None)!=(gap is None) or (
            gap is not None and logged_gap is not None and abs(logged_gap-gap)>D('1e-24'))
        if logged['adopted']!=chosen or gap_mismatch:
            raise ValueError('Independent event check failed '+arm+'/'+policy+'/'+day)
    executed=read_json(root/'python'/(name(arm,policy)+'.json'))['decisions']
    if [d for d in expected if d<='2026-10-14'] != list(executed):
        raise ValueError('Independent event dates differ')
    intervals=np.diff([list(tape).index(d) for d in expected])
    economic=read_json(root/'python'/(name(arm,policy)+'.json'))
    sessions={r['date']:i for i,r in enumerate(economic['nav'])}
    last={};reversals=0
    for fill in economic['fills']:
        symbol=fill['symbol'];sign=1 if fill['quantity']>0 else -1;i=sessions[fill['date']]
        if symbol in last and sign!=last[symbol][1] and i-last[symbol][0]<=5:
            reversals+=1
        last[symbol]=(i,sign)
    return dict(passed=True,adoptions=len(expected),executed=len(executed),
        extra_adoptions=sum(r['primary_reason']=='threshold' for r in ledger),
        median_sessions_between_adoptions=float(np.median(intervals)),
        five_session_opposite_direction_fills=reversals,
        reversal_definition='Opposite-direction next fill in the same ETF within five sessions; may include monthly events.')


def stationary_inference(matrix,contrasts,block,reps=20000,seed=20261015):
    """Same stationary-bootstrap calendar for every policy, parent and benchmark."""
    matrix=np.asarray(matrix,dtype=float);n,m=matrix.shape
    if not np.isfinite(matrix).all():
        raise ValueError('Joint bootstrap requires complete aligned returns')
    observed=matrix.mean(0)/matrix.std(0,ddof=1)*np.sqrt(252)
    rng=np.random.default_rng(seed);samples=[]
    for offset in range(0,reps,500):
        count=min(500,reps-offset)
        starts=rng.integers(0,n,size=(count,n))
        restart=rng.random((count,n))<1/block
        idx=np.empty_like(starts);idx[:,0]=starts[:,0]
        for t in range(1,n):
            idx[:,t]=np.where(restart[:,t],starts[:,t],(idx[:,t-1]+1)%n)
        weights=np.zeros((count,n))
        np.add.at(weights,(np.repeat(np.arange(count),n),idx.ravel()),1)
        mean=weights@matrix/n
        variance=np.maximum((weights@(matrix*matrix)-n*mean*mean)/(n-1),0)
        sharpe=np.divide(mean,np.sqrt(variance),out=np.zeros_like(mean),where=variance>0)*np.sqrt(252)
        samples.append(np.column_stack([sharpe[:,a]-sharpe[:,b] for _,a,b in contrasts]))
    draws=np.concatenate(samples)
    result=[]
    for i,(label,a,b) in enumerate(contrasts):
        delta=float(observed[a]-observed[b]);sample=draws[:,i]
        result.append(dict(contrast=label,sharpe_difference=delta,
            ci95=np.quantile(sample,[.025,.975]).tolist(),
            centered_two_sided_p=float((1+np.sum(np.abs(sample-delta)>=abs(delta)))/(reps+1))))
    for row,p in zip(result,holm([r['centered_two_sided_p'] for r in result]),strict=True):
        row['descriptive_holm_p']=float(p)
    return dict(block=block,replicates=reps,seed=seed,sessions=n,contrasts=result,
        scope='2024-01-02 through 2026-10-14, same joint resampling indices',
        formal_superiority=False,selection_aware=False,
        caveat='Conditional on the realized selector calendar. Selector is not rerun inside resamples; intervals and Holm values are descriptive.')


def assess(root):
    p=read_json(root/'protocol.json');grid=p['thresholds']
    selection=read_json(root/'selections.json')
    summary={};events={};assessment={}
    for arm in ('FR25','F3'):
        summary[arm]={}
        events[arm]={}
        for policy in ['monthly','daily',*grid,'walk_forward']:
            summary[arm][policy]={f'{c}-{d}':metrics(root,arm,policy,cost=c,delay=d)
                for c in (5,10,20) for d in (0,1)}
            events[arm][policy]=independent_events(root,arm,policy)
        fold_results=[]
        for fold in p['walk_forward']['folds']:
            base=metrics(root,arm,'monthly',fold['validate_start'],fold['validate_end'])
            wf=metrics(root,arm,'walk_forward',fold['validate_start'],fold['validate_end'])
            fold_results.append(dict(start=fold['validate_start'],end=fold['validate_end'],baseline=base,
                candidate=wf,sharpe_difference=wf['sharpe']-base['sharpe']))
        aggregate={}
        for c,d in [(5,0),(10,0),(5,1),(20,0),(10,1),(20,1)]:
            base=metrics(root,arm,'monthly','2024-01-02','2026-10-14',c,d)
            wf=metrics(root,arm,'walk_forward','2024-01-02','2026-10-14',c,d)
            aggregate[f'{c}-{d}']=dict(baseline=base,candidate=wf,
                passes=guards(wf,base,.05 if (c,d)==(5,0) and arm=='FR25' else 0.)
                and wf['sharpe']>base['sharpe'])
        positive=sum(r['sharpe_difference']>0 for r in fold_results)
        passed=(aggregate['5-0']['passes'] and
            (arm=='F3' or positive>=2 and aggregate['10-0']['passes'] and aggregate['5-1']['passes']))
        assessment[arm]=dict(aggregate=aggregate,folds=fold_results,positive_folds=positive,
            numerical_retention_pass=passed,
            audited_transfer_confirmation=False if arm=='F3' else None)
    # Recompute the selector from its declared training dates, including all
    # stress guards and neighborhood constraints. Validation returns are absent.
    for receipt in [*selection['folds'],selection['candidate']]:
        training={policy:{f'{c}-{d}':metrics(root,'FR25',policy,receipt['start'],receipt['end'],c,d)
            for c,d in ((5,0),(10,0),(5,1))} for policy in ['monthly',*grid]}
        check=select_threshold(grid,training)
        if any(check[k]!=receipt[k] for k in check):
            raise ValueError('Selector receipt does not reproduce from its training window')
    return dict(protocol=p,selections=selection,full_sample=summary,events=events,assessment=assessment,
        promotion_eligible=False,formal_superiority=False)


def render_details(root,output,analysis,urth,urth_quotes):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data,render_backtest_report_html
    from systematic_trading.research.strategy_catalog import StrategyDefinition
    from systematic_trading.research.target_change_reporting import variant_decision_diagrams
    benchmark_result=report_result(urth,urth_quotes,1_000_000,'2020-12-31')
    paths=[]
    for arm in ('FR25','F3'):
        base_name=name(arm,'monthly')
        quotes=read_json(root/'bundles'/base_name/'quotes.json')
        base=report_result(read_json(root/'python'/(base_name+'.json')),quotes,1_000_000,'2020-12-31')
        definition=read_json(root/'workers'/arm/'worker.json')['definitions'][0]
        prices={s:{'2020-12-31':float(q['2021-01-04']['reference']),**{d:float(r['close']) for d,r in q.items()}}
            for s,q in quotes.items()}
        for policy in dict.fromkeys(['monthly','walk_forward',analysis['selections']['candidate']['selected']]):
            key=name(arm,policy);economic=read_json(root/'python'/(key+'.json'))
            data=report_result(economic,quotes,1_000_000,'2020-12-31')
            report,warnings=build_backtest_report_data(result=data,result_path=root/'python'/(key+'.json'),
                split_date='2024-01-02',benchmark_name=arm+' monthly',benchmark_nav_series=base['nav_series'],
                extra_benchmarks=[dict(id='urth',name='URTH buy-and-hold USD',nav_series=benchmark_result['nav_series'])],
                market_prices=prices,market_fx_rates={d:1. for d in data_day_keys(data)})
            latest=read_json(root/'targets'/(arm+'.json'))
            ledger=read_json(root/'events'/(key+'.json'))['ledger']
            adopted=next(r for r in reversed(ledger) if r['adopted'])
            end=economic['nav'][-1];nav=float(end['nav'])
            report.update(title=f'{arm} · {policy} target adoption study',accountingCurrency='USD',
                database='Pinned audited continuous prices; explicit monthly macro fallback',
                allocationSource='Daily USD holdings reconstructed from executed whole-unit orders and audited adjusted closes. No currency conversion.',
                strategyDefinition=definition,decisionDiagrams=variant_decision_diagrams(StrategyDefinition.from_dict(definition),'6',policy),
                modelRegime='Frozen parent model schedules; monthly macro fallback; daily prices and activity',
                splitLabel='Chronological validation; previously inspected data',
                sampleLabels={'in_sample':'2021–2023 initial training','out_of_sample':'2024–2026 walk-forward evaluation'},
                warnings=warnings+analysis['protocol']['limitations']+[
                    'Finite research report. No tracking, funding, approval or broker authority.',
                    'The shared chart includes the 2020-12-31 initial cash anchor; grid CAGR and turnover annualize from the first evaluation session, 2021-01-04. This small calendar-convention difference does not change returns or decisions.',
                    'Decision flow: audited daily prices → parent target with explicit monthly macro carry → L1 distance including cash from last adopted target → monthly or strict threshold event → next-session whole-unit replay → hold shares.',
                    'Walk-forward policy uses FR25 annual selections and carries cash, holdings and adoption anchor across folds.'],
                researchDecisionFlow=dict(policy=policy,thresholds=analysis['selections'],latest_target=latest[max(latest)],
                    last_adopted_target=adopted,held_weights={s:q*float(quotes[s][end['date']]['close'])/nav
                    for s,q in economic['final_positions'].items()},cash_weight=float(end['cash'])/nav),
                inputReceipts=dict(input_manifest_sha256=sha256(root/'input_manifest.json'),
                    target_manifest_sha256=sha256(root/('target_manifest_'+arm+'.json'))))
            path=output/(arm+'-'+policy+'.html')
            path.write_text(render_backtest_report_html(report),encoding='utf8')
            write_json(output/(arm+'-'+policy+'.report.json'),report)
            paths.append(path.name)
    return paths


def data_day_keys(data):
    return [r['trade_date'] for r in data['nav_series']]


def report(root,output,analysis,urth,urth_quotes):
    output.mkdir(parents=True,exist_ok=True)
    details=render_details(root,output,analysis,urth,urth_quotes)
    lines=['# Target-change rebalance backtest — 15 October 2026','',
        'Completed finite research. USD1m; whole adjusted units; zero cash interest; 5bp per traded side in the main comparison. '
        'Prices through 14 October 2026. Threshold is the sum of absolute latest-theoretical versus last-adopted target differences, including cash.','',
        '**Monthly macro assumption:** exact pinned daily snapshot when available, otherwise the previous completed monthly snapshot; source dates remain intact. '
        'Daily prices/activity and price-based features update normally. No trading housekeeping trigger is included.','',
        '**Decision:** '+('No extra-rebalance threshold qualified in any annual selection window; retain monthly rebalancing.'
            if all(r['selected']=='monthly' for r in analysis['selections']['folds']) else
            'The FR25 walk-forward sequence passes the numerical retention criteria.' if analysis['assessment']['FR25']['numerical_retention_pass']
            else 'The FR25 walk-forward sequence does not pass the registered retention criteria.')+' '
        +'This is inspected historical evidence, not proof of superiority or trading approval.','',
        '## Walk-forward evaluation: 2024-01-02 to 2026-10-14','',
        '| Parent | Policy | Net Sharpe | CAGR | Max drawdown | Annual turnover |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for arm in ('FR25','F3'):
        for label,k in [('Monthly','baseline'),('Selected walk-forward','candidate')]:
            m=analysis['assessment'][arm]['aggregate']['5-0'][k]
            lines.append(f"| {arm} | {label} | {m['sharpe']:.3f} | {m['cagr']:.2%} | {m['max_drawdown']:.2%} | {m['annual_turnover']:.2f}× |")
    lines+=['','F3 retains the current published adjusted-price/source-volume activity proxy. Its results are a legacy-parent sensitivity check; audited raw-activity transfer confirmation remains unavailable.','',
        '## Causal threshold selection','', '| Training window | Applied from | Selected policy |', '| --- | --- | --- |']
    for r in analysis['selections']['folds']:
        lines.append(f"| {r['start']}–{r['end']} | {r['activation']} | {r['selected']} |")
    candidate=analysis['selections']['candidate']
    lines += ['',f"Final trailing-three-year selector ({candidate['start']}–{candidate['end']}): **{candidate['selected']}**. "
        'A monthly outcome means no extra threshold qualified. This freezes a research candidate only; no prospective monitoring is started.','',
        '## Full 2021–2026 grid: descriptive, not threshold selection','',
        '| Parent | Policy | Sharpe | CAGR | Max drawdown | Turnover/year | Filled rebalance dates |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for arm,policies in analysis['full_sample'].items():
        for policy,scenarios in policies.items():
            m=scenarios['5-0'];event=analysis['events'][arm][policy]
            lines.append(f"| {arm} | {policy} | {m['sharpe']:.3f} | {m['cagr']:.2%} | {m['max_drawdown']:.2%} | {m['annual_turnover']:.2f}× | {event['executed']} |")
    lines += ['','Annual turnover is gross buys plus sells divided by each session’s pretrade NAV; '
        '5bp cost drag is charged on that actual notional. Rebalance dates include scheduled events with no required whole-unit trade.','',
        '## Why the threshold creates frequent trading','',
        '| Parent / policy | Extra threshold events | Median sessions between adoptions | Opposite-direction fills within five sessions | Annual fee drag |',
        '| --- | ---: | ---: | ---: | ---: |']
    for arm in ('FR25','F3'):
        for policy in ('monthly','0.10','0.40'):
            e=analysis['events'][arm][policy]
            s=read_json(root/'metrics'/(name(arm,policy)+'.json'))['statistics']
            lines.append(f"| {arm} / {policy} | {e['extra_adoptions']} | {e['median_sessions_between_adoptions']:.1f} | "
                f"{e['five_session_opposite_direction_fills']} | {s['annual_cost_bps']:.1f}bp |")
    lines += ['','This measures reactivity and trading churn. It does not identify the causal economic reason for every reversal. '
        'Full per-ETF PnL, mean exposures, holding spells and costs are retained in each replay’s metrics artifact.','',
        '## Macro snapshot coverage','',
        '| Parent | Daily target dates | USD active dates | USD monthly fallbacks | Maximum USD snapshot carry | Financial monthly fallbacks |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for arm,m in analysis['macro_coverage'].items():
        lines.append(f"| {arm} | {m['target_dates']} | {m['usd_active_dates']} | {m['usd_carried_dates']} | {m['usd_max_snapshot_age_days']} days | {m['financial_carried_dates']} |")
    lines += ['','## Cost and delay robustness: walk-forward evaluation','',
        '| Parent | Cost per side | Extra delay | Monthly Sharpe | Walk-forward Sharpe | CAGR difference | Drawdown difference |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for arm,a in analysis['assessment'].items():
        for scenario,r in a['aggregate'].items():
            c,d=scenario.split('-');b=r['baseline'];x=r['candidate']
            lines.append(f"| {arm} | {c}bp | {d} session | {b['sharpe']:.3f} | {x['sharpe']:.3f} | {(x['cagr']-b['cagr'])*100:+.2f}pp | {(x['max_drawdown']-b['max_drawdown'])*100:+.2f}pp |")
    lines += ['','## Conditional uncertainty','',
        '20,000 paired stationary-bootstrap replicates; seed 20261015; common 2024–2026 calendar across all policies, parents and URTH. '
        'Mean block 63 sessions, with 21/126 sensitivity. These intervals condition on the chosen annual policy calendar. '
        'The selector is not rerun within resamples, so neither the intervals nor the descriptive Holm adjustment over 18 contrasts establish formal superiority.','',
        '| Parent | Mean block | Walk-forward Sharpe difference | Conditional 95% interval | Descriptive Holm p |',
        '| --- | ---: | ---: | --- | ---: |']
    for block,inference in analysis['inference'].items():
        for r in inference['contrasts']:
            if r['contrast'].endswith('/walk_forward'):
                lo,hi=r['ci95'];lines.append(f"| {r['contrast'].split('/')[0]} | {block} | {r['sharpe_difference']:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {r['descriptive_holm_p']:.3f} |")
    lines += ['','## Evidence and limits','',
        '- All 132 full-size parent/policy/cost/delay replays retain decisions, actual fills, fees, cash, NAV and full-constituent attribution. USD100k diagnostics use the same selected rules without retuning.',
        '- Each parent matches its frozen monthly target decisions. Six independent native LEAN checks cover both monthly controls, selected walk-forward policies and the 0.10 intramonth policies. Every event is independently checked against the last logical adoption.',
        '- Monthly macro fallback assumes no newly available signal information between snapshots. Source dates and carry ages are in the target tapes; this assumption can understate responsiveness to macro releases.',
        '- Price and economic publication vintages are retrospective; current strategy and universe choices used inspected data. Adjusted units are not raw broker shares. Fixed bps costs do not establish capacity, taxes, bid-ask spreads or realized fills.',
        '- Risk, turnover, holding spells, five-session reversal counts and constituent PnL are retained. Full-pool qualification, a corrected-basis F3 comparison, prospective evidence and existing promotion gates remain separate.',
        '',f"Artifacts: [Replay evidence]({Path(os.path.relpath(root/'analysis.json',output)).as_posix()}).",'',
        'Detailed reports use the application’s shared SOTA report format:',*['- ['+p+']('+p+')' for p in details]]
    (output/'results.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    with (output/'grid.csv').open('w',newline='',encoding='utf8') as stream:
        writer=csv.writer(stream);writer.writerow(['parent','policy','cost_bps','extra_delay','sharpe','cagr','max_drawdown','annual_turnover'])
        for arm,policies in analysis['full_sample'].items():
            for policy,scenarios in policies.items():
                for scenario,m in scenarios.items():
                    writer.writerow([arm,policy,*scenario.split('-'),*[m[k] for k in ('sharpe','cagr','max_drawdown','annual_turnover')]])
    plot(root,output,analysis)
    body='<h1>Target-change rebalance study</h1><p>Daily theoretical target versus last adopted target; cash included. Monthly macro fallback is explicit.</p>'
    body+='<p><a href="results.md">Complete results</a> · <a href="grid.csv">All 132 scenarios</a></p>'
    body+='<img src="comparison.png" style="width:100%;max-width:1300px" alt="Threshold response, NAV and drawdown"/>'
    body+='<h2>Detailed strategy reports</h2><ul>'+''.join(f'<li><a href="{html.escape(p)}">{html.escape(p)}</a></li>' for p in details)+'</ul>'
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Target-change rebalance</title><style>body{font:16px/1.6 system-ui;max-width:1300px;margin:40px auto;padding:0 24px;color:#203843;background:#faf9f5}a{color:#126e7e}</style>'+body,encoding='utf8')


def plot(root,output,analysis):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    grid=analysis['protocol']['thresholds'];fig,axes=plt.subplots(2,2,figsize=(13,8),layout='constrained')
    for arm,color in [('FR25','#196e87'),('F3','#b77731')]:
        policies=analysis['full_sample'][arm];base=policies['monthly']['5-0']['sharpe']
        axes[0,0].plot([float(x) for x in grid],[policies[x]['5-0']['sharpe']-base for x in grid],marker='o',label=arm,color=color)
        axes[0,1].plot([float(x) for x in grid],[policies[x]['5-0']['annual_turnover'] for x in grid],marker='o',label=arm,color=color)
    axes[0,0].axhline(0,color='grey',lw=.8);axes[0,0].set_title('Full-sample Sharpe change vs monthly (descriptive)')
    axes[0,1].set_title('Annual traded notional / NAV')
    for ax in axes[0]:ax.set_xlabel('L1 threshold, including cash');ax.legend()
    for policy,color in [('monthly','#777777'),('0.10','#bb843b'),('walk_forward','#196e87')]:
        eco=read_json(root/'python'/(name('FR25',policy)+'.json'))
        rows=[r for r in eco['nav'] if r['date']>='2024-01-02']
        before=next(r for r in eco['nav'] if r['date']=='2023-12-29')
        nav=np.array([float(before['nav'])]+[float(r['nav']) for r in rows])
        days=[datetime.fromisoformat(r['date']) for r in rows]
        axes[1,0].plot(days,nav[1:]/nav[0],label=policy,color=color)
        axes[1,1].plot(days,(nav/np.maximum.accumulate(nav)-1)[1:],label=policy,color=color)
    axes[1,0].set_title('FR25 validation NAV, rebased at opening 2024')
    axes[1,1].set_title('FR25 validation drawdown');axes[1,1].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes.flat:
        ax.spines[['top','right']].set_visible(False);ax.grid(alpha=.15);ax.legend()
    fig.suptitle('Does reacting to target changes improve the strategy?',fontsize=17)
    fig.savefig(output/'comparison.png',dpi=160);plt.close(fig)


def main(root,output):
    checked_files(root,'input_manifest.json')
    for arm in ('FR25','F3'):checked_files(root,'target_manifest_'+arm+'.json')
    if not (root/'native_summary.json').exists():raise ValueError('Native parity must finish first')
    native=read_json(root/'native_summary.json')
    if len(native)!=4 or any(r['status']!='succeeded' for r in native.values()):raise ValueError('Incomplete native parity')
    threshold_native=read_json(root/'native_threshold_summary.json')
    if len(threshold_native)!=2 or any(r['status']!='succeeded' for r in threshold_native.values()):raise ValueError('Incomplete intramonth parity')
    native.update(threshold_native)
    for key in native:checked_files(root/'native'/key,'artifact_manifest.json')
    for p in (root/'receipts').glob('*.json'):
        verify_usd_bundle(root/'bundles'/p.stem)
        for relative,digest in read_json(p)['files'].items():
            if sha256(root/relative)!=digest:raise ValueError('Changed replay '+relative)
    analysis=assess(root);urth,quotes=benchmark(root)
    analysis['macro_coverage']={}
    analysis['liquidity']={}
    raw={s:{r['trade_date']:r for r in rows} for s,rows in read_json(root/'workers/FR25/worker.json')['raw_bars'].items()}
    for arm in ('FR25','F3'):
        tape=read_json(root/'targets'/(arm+'.json'))
        sources=[r['macro_sources'] for r in tape.values()]
        used=[r for r in sources if r['usd_used']]
        analysis['macro_coverage'][arm]=dict(target_dates=len(tape),usd_active_dates=len(used),
            usd_carried_dates=sum(r['usd_carried'] for r in used),
            usd_max_snapshot_age_days=max(r['usd_age_days'] for r in used),
            financial_carried_dates=sum(r['financial_carried'] for r in sources))
        analysis['liquidity'][arm]={}
        for policy in ['monthly','daily',*analysis['protocol']['thresholds'],'walk_forward']:
            eco=read_json(root/'python'/(name(arm,policy)+'.json'))
            participation=[]
            for fill in eco['fills']:
                bar=raw[fill['symbol']][fill['date']]
                fraction=abs(fill['quantity'])*float(fill['price'])/(float(bar['close'])*bar['volume'])
                participation.append(dict(date=fill['date'],symbol=fill['symbol'],fraction=fraction))
            analysis['liquidity'][arm][policy]=dict(maximum=max(participation,key=lambda r:r['fraction']),
                p95=float(np.quantile([r['fraction'] for r in participation],.95)),
                caveat='Ex-post simulated USD traded notional / audited raw daily dollar volume. Not a slippage or capacity model.')
    keys=[(arm,policy) for arm in ('FR25','F3') for policy in ['monthly',*analysis['protocol']['thresholds'],'walk_forward']]
    matrix=[];calendar=None
    for arm,policy in keys:
        stats=read_json(root/'metrics'/(name(arm,policy)+'.json'))['statistics']
        pairs=[(d,r) for d,r in zip(stats['dates'],stats['daily_returns'],strict=True) if d>='2024-01-02']
        if calendar is None:calendar=[d for d,_ in pairs]
        if [d for d,_ in pairs]!=calendar:raise ValueError('Misaligned bootstrap calendar')
        matrix.append([r for _,r in pairs])
    u=statistics(urth,quotes)
    upairs=[(d,r) for d,r in zip(u['dates'],u['daily_returns'],strict=True) if d>='2024-01-02']
    if [d for d,_ in upairs]!=calendar:raise ValueError('Misaligned URTH')
    matrix.append([r for _,r in upairs])
    contrasts=[(arm+'/'+policy,i,keys.index((arm,'monthly'))) for i,(arm,policy) in enumerate(keys) if policy!='monthly']
    analysis['inference']={}
    for block in (63,21,126):
        analysis['inference'][str(block)]=stationary_inference(np.asarray(matrix).T,contrasts,block)
        print('Bootstrap complete',block,flush=True)
    analysis['benchmark']=window_metrics(urth,'2021-01-04','2026-10-14')
    analysis['completed_at']=datetime.now(UTC).isoformat()
    analysis['source_manifest_sha256']=sha256(root/'input_manifest.json')
    write_json(root/'analysis.json',analysis)
    shutil.copyfile(Path(__file__),root/'analysis_runner.py')
    report(root,output,analysis,urth,quotes)
    write_json(root/'acceptance.json',dict(status='passed',native_parity=6,full_size_replays=132,
        independent_policy_checks=22,analysis_sha256=sha256(root/'analysis.json'),
        analysis_runner_sha256=sha256(root/'analysis_runner.py'),promotion_eligible=False,
        selection_sha256=sha256(root/'selections.json'),
        candidate=analysis['selections']['candidate']['selected'],candidate_frozen_at=analysis['completed_at'],
        prospective_policy='First completed session after freeze; at least 126 sessions to first review; no automation started.',
        formal_superiority=False,F3_audited_transfer_confirmation=False))
    write_json(output/'report_manifest.json',{p.name:sha256(p) for p in sorted(output.iterdir())
        if p.is_file() and p.name!='report_manifest.json'})
    print('Analysis and reports complete',output,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args();main(args.root.resolve(),args.output.resolve())
