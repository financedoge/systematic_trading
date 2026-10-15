"""Joint selection-width/timing assessment, membership attribution and reports."""
from datetime import UTC,datetime
import argparse
import csv
import importlib.util
import os
from pathlib import Path
import shutil
import sys

for variable in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS','NUMEXPR_NUM_THREADS'):
    os.environ[variable]='1'
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))

import numpy as np
from systematic_trading.lean.contracts import sha256,write_json
from systematic_trading.research.momentum_replay import checked_files,read_json,verify_usd_bundle
from systematic_trading.research.target_change_rebalance import guards,window_metrics
from systematic_trading.research.selection_timing import select_pair,mixed_tape

ROOT=Path('var/research/selection-width-timing-20261015-v1')
OUTPUT=Path('research/selection-width-timing-20261015-v1')


def load_helper(parent):
    receipt=read_json(parent/'acceptance.json')
    path=parent/'analysis_runner.py'
    if sha256(path)!=receipt['analysis_runner_sha256']:raise ValueError('Parent analysis helper changed')
    spec=importlib.util.spec_from_file_location('prior_analysis',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def arm(parent,width):return parent+'_X'+width


def name(parent,pair,cost=5,delay=0,initial=1_000_000):
    width,n=('WF','walk_forward') if pair=='WF' else pair.split('/')
    return f'{arm(parent,width)}-{n}-c{cost}-d{delay}-n{initial}'


def membership_attribution(eco,quotes):
    positions={s:0 for s in quotes};cash=1_000_000.;last=None
    fills={}
    for f in eco['fills']:fills.setdefault(f['date'],[]).append(f)
    changes={k:0 for k in ('rank_cutoff','eligibility','fallback','width_switch','unclassified')}
    entry_exit=retained=establishment=0.
    entry_exit_usd=retained_usd=0.
    for i,r in enumerate(eco['nav']):
        day=r['date'];opening=cash+sum(q*float(quotes[s][day]['open']) for s,q in positions.items())
        before=dict(positions)
        for f in fills.get(day,[]):positions[f['symbol']]+=f['quantity']
        for f in fills.get(day,[]):
            traded=abs(f['quantity'])*float(f['price']);s=f['symbol']
            if i==0:establishment+=traded/opening
            elif before[s]==0 or positions[s]==0:entry_exit+=traded/opening;entry_exit_usd+=traded
            else:retained+=traded/opening;retained_usd+=traded
            cash-=f['quantity']*float(f['price'])+float(f['fee'])
        if abs(cash-float(r['cash']))>.02:raise ValueError('Membership ledger mismatch')
        if day not in eco['decisions']:continue
        current=eco['decisions'][day]
        if last is not None:
            previous={t['symbol'] for t in last['targets'] if float(t['target_weight'])>0}
            latest={t['symbol'] for t in current['targets'] if float(t['target_weight'])>0}
            old_obs=last.get('selection',{}).get('observation')
            new_obs=current.get('selection',{}).get('observation')
            width_changed=last.get('selection',{}).get('top_n')!=current.get('selection',{}).get('top_n')
            for symbol in previous^latest:
                if width_changed:reason='width_switch'
                elif not old_obs or not new_obs:reason='unclassified'
                elif old_obs['fallback'] or new_obs['fallback']:reason='fallback'
                elif symbol in old_obs['eligible'] and symbol in new_obs['eligible']:reason='rank_cutoff'
                else:reason='eligibility'
                changes[reason]+=1
        last=current
    return dict(establishment_turnover=establishment,entry_exit_turnover_ex_initial=entry_exit,
        retained_adjustment_turnover_ex_initial=retained,
        entry_exit_fraction_ex_initial=entry_exit/(entry_exit+retained) if entry_exit+retained else 0.,
        entry_exit_notional_usd_ex_initial=entry_exit_usd,retained_adjustment_notional_usd_ex_initial=retained_usd,
        target_membership_changes=changes,
        definition='Gross traded notional / same-day pretrade NAV. Entry/exit means actual quantity crosses zero. Target membership-change reasons are separate counts, not causal PnL attribution. Initial establishment excluded from the fraction.')


def evaluate(root,helper):
    p=read_json(root/'protocol.json');selection=read_json(root/'selections.json')
    pairs=[x+'/'+n for x in p['widths'] for n in p['thresholds']]
    full={};validation={};events={};attribution={};assessment={};liquidity={}
    raw={s:{r['trade_date']:r for r in rows} for s,rows in
        read_json(root/'workers/FR25/worker.json')['raw_bars'].items()}
    training=[{} for _ in range(4)]
    windows=[(f['train_start'],f['train_end']) for f in p['folds']]+[tuple(p['final_candidate_window'])]
    for parent in ('FR25','F3'):
        full[parent]={};validation[parent]={};events[parent]={};attribution[parent]={};liquidity[parent]={}
        quotes=read_json(root/'parents'/arm(parent,'6')/'quotes.json')
        for i,pair in enumerate([*pairs,'WF'],1):
            width,n=('WF','walk_forward') if pair=='WF' else pair.split('/')
            full[parent][pair]={};validation[parent][pair]={}
            for c,d in [(5,0),(5,1),(10,0),(10,1),(20,0),(20,1)]:
                label=name(parent,pair,c,d)
                eco=read_json(root/'python'/(label+'.json'));m=read_json(root/'metrics'/(label+'.json'))
                full[parent][pair][f'{c}-{d}']={k:m[k] for k in ('sharpe','cagr','max_drawdown','annual_turnover','decisions')}
                full[parent][pair][f'{c}-{d}'].update({k:m['statistics'][k] for k in
                    ('annual_cost_bps','mean_held_count','mean_effective_holdings','maximum_weight','total_fees_usd')})
                validation[parent][pair][f'{c}-{d}']=window_metrics(eco,'2024-01-02','2026-10-14',turnover_by_day=m['turnover_by_day'])
                if parent=='FR25' and pair!='WF' and (c,d) in ((5,0),(10,0),(5,1)):
                    for score,(start,end) in zip(training,windows,strict=True):
                        score.setdefault(pair,{})[f'{c}-{d}']=window_metrics(eco,start,end,turnover_by_day=m['turnover_by_day'])
                if (c,d)==(5,0):
                    attribution[parent][pair]=membership_attribution(eco,quotes)
                    events[parent][pair]=helper.independent_events(root,arm(parent,width),n)
                    participation=[]
                    for fill in eco['fills']:
                        bar=raw[fill['symbol']][fill['date']]
                        fraction=abs(fill['quantity'])*float(fill['price'])/(float(bar['close'])*bar['volume'])
                        participation.append(dict(date=fill['date'],symbol=fill['symbol'],fraction=fraction))
                    liquidity[parent][pair]=dict(maximum=max(participation,key=lambda r:r['fraction']),
                        p95=float(np.quantile([r['fraction'] for r in participation],.95)),
                        caveat='Ex-post simulated traded USD / audited raw daily dollar volume; not a capacity or slippage model.')
            if i%12==0:print('Joint analysis ledgers',parent,i,'/49',flush=True)
        fold_results=[]
        for f in p['folds']:
            rows={}
            for pair in ('6/monthly','WF'):
                eco=read_json(root/'python'/(name(parent,pair)+'.json'));m=read_json(root/'metrics'/(name(parent,pair)+'.json'))
                rows[pair]=window_metrics(eco,f['validate_start'],f['validate_end'],turnover_by_day=m['turnover_by_day'])
            fold_results.append(dict(start=f['validate_start'],end=f['validate_end'],metrics=rows,
                sharpe_difference=rows['WF']['sharpe']-rows['6/monthly']['sharpe']))
        checks={}
        for scenario in ('5-0','10-0','5-1','20-0','10-1','20-1'):
            candidate=validation[parent]['WF'][scenario];base=validation[parent]['6/monthly'][scenario]
            checks[scenario]=guards(candidate,base,.05 if scenario=='5-0' and parent=='FR25' else 0.) and candidate['sharpe']>base['sharpe']
        positive=sum(r['sharpe_difference']>0 for r in fold_results)
        assessment[parent]=dict(folds=fold_results,positive_folds=positive,scenario_pass=checks,
            numerical_retention_pass=checks['5-0'] and (parent=='F3' or positive>=2 and checks['10-0'] and checks['5-1']),
            audited_transfer_confirmation=False if parent=='F3' else None)
    for score,receipt in zip(training,[*selection['folds'],selection['candidate']],strict=True):
        result=select_pair(p['widths'],p['thresholds'],score)
        if any(result[k]!=receipt[k] for k in result):raise ValueError('Joint selector does not reproduce')
    for parent in ('FR25','F3'):
        tapes={x:read_json(root/'targets'/(arm(parent,x)+'.json')) for x in p['widths']}
        if mixed_tape(tapes,selection['pair_switches'])!=read_json(root/'targets'/(arm(parent,'WF')+'.json')):
            raise ValueError('Walk-forward width calendar differs')
    return dict(protocol=p,selections=selection,full_sample=full,validation=validation,events=events,
        membership_attribution=attribution,liquidity=liquidity,assessment=assessment,
        promotion_eligible=False,formal_superiority=False)


def inference(root,helper,analysis):
    pairs=list(analysis['full_sample']['FR25'])
    keys=[(parent,pair) for parent in ('FR25','F3') for pair in pairs]
    columns=[];days=None
    for parent,pair in keys:
        s=read_json(root/'metrics'/(name(parent,pair)+'.json'))['statistics']
        rows=[(d,r) for d,r in zip(s['dates'],s['daily_returns'],strict=True) if d>='2024-01-02']
        if days is None:days=[d for d,_ in rows]
        if [d for d,_ in rows]!=days:raise ValueError('Joint inference calendars differ')
        columns.append([r for _,r in rows])
    parent_root=Path(analysis['protocol']['parent_root'])
    benchmark=read_json(parent_root/'python/URTH-context.json')
    nav=[1_000_000]+[float(r['nav']) for r in benchmark['nav']]
    returns=np.array(nav[1:])/nav[:-1]-1
    selected=[(r['date'],v) for r,v in zip(benchmark['nav'],returns,strict=True) if r['date']>='2024-01-02']
    if [d for d,_ in selected]!=days:raise ValueError('URTH calendar differs')
    columns.append([r for _,r in selected])
    contrasts=[(parent+'/'+pair,i,keys.index((parent,'6/monthly'))) for i,(parent,pair) in enumerate(keys) if pair!='6/monthly']
    if len(contrasts)!=96:raise ValueError('Unexpected comparison family')
    results={}
    for block in (63,21,126):
        results[str(block)]=helper.stationary_inference(np.asarray(columns).T,contrasts,block)
        print('Joint bootstrap',block,'complete',flush=True)
    return results


def detailed_reports(root,output,analysis):
    from systematic_trading.research.tracked_runtime import report_result
    from systematic_trading.backtest.reporting import build_backtest_report_data,render_backtest_report_html
    from systematic_trading.research.strategy_catalog import StrategyDefinition
    from systematic_trading.research.target_change_reporting import variant_decision_diagrams
    from systematic_trading.research.momentum_replay import read_json
    parent_root=Path(analysis['protocol']['parent_root'])
    benchmark=report_result(read_json(parent_root/'python/URTH-context.json'),
        read_json(parent_root/'bundles/URTH-context/quotes.json'),1_000_000,'2020-12-31')
    files=[]
    for parent in ('FR25','F3'):
        quotes=read_json(root/'bundles'/name(parent,'6/monthly')/'quotes.json')
        base=report_result(read_json(root/'python'/(name(parent,'6/monthly')+'.json')),quotes,1_000_000,'2020-12-31')
        definition=read_json(root/'workers'/parent/'worker.json')['definitions'][0]
        prices={s:{'2020-12-31':float(q['2021-01-04']['reference']),**{d:float(r['close']) for d,r in q.items()}} for s,q in quotes.items()}
        for pair in dict.fromkeys(['6/monthly','WF',analysis['selections']['candidate']['selected'],'8/0.10']):
            label=name(parent,pair);eco=read_json(root/'python'/(label+'.json'))
            data=report_result(eco,quotes,1_000_000,'2020-12-31')
            report,warnings=build_backtest_report_data(result=data,result_path=root/'python'/(label+'.json'),
                split_date='2024-01-02',benchmark_name=parent+' top-six monthly',benchmark_nav_series=base['nav_series'],
                extra_benchmarks=[dict(id='urth',name='URTH buy-and-hold USD',nav_series=benchmark['nav_series'])],
                market_prices=prices,market_fx_rates={r['trade_date']:1. for r in data['nav_series']})
            report.update(title=f'{parent} · (X,n) = {pair}',accountingCurrency='USD',
                database='Pinned audited prices; exact-else-monthly macro features',
                allocationSource='Daily USD holdings reconstructed from executed whole-unit orders and audited adjusted closes. No currency conversion.',
                strategyDefinition=dict(definition,researchVariant=dict(id=label,selectionTimingPair=pair,
                    overrides='Only selection top_n and target-adoption schedule; all eligibility/fallback/sizing contracts preserved')),
                decisionDiagrams=variant_decision_diagrams(StrategyDefinition.from_dict(definition),
                    'WF' if pair=='WF' else (('14' if parent=='FR25' else '12') if pair.split('/')[0]=='all' else pair.split('/')[0]),pair),
                modelRegime='Parent model schedules; X/n research variant; explicit monthly macro carry',
                splitLabel='Chronological validation on inspected data',
                sampleLabels={'in_sample':'2021–2023 initial training','out_of_sample':'2024–2026 walk-forward evaluation'},
                warnings=warnings+analysis['protocol']['limitations']+[
                    'Finite research only, no promotion or execution authority. X is a maximum, not a minimum allocation requirement.',
                    'The shared chart includes the 2020-12-31 initial cash anchor; grid CAGR and turnover annualize from the first evaluation session, 2021-01-04. This small calendar-convention difference does not change returns or decisions.',
                    'Decision flow: audited prices → unchanged eligibility and economic/momentum rank → top X → unchanged sizing/caps → L1 latest versus adopted target including cash → monthly or n crossing → next-open whole-unit accounting → hold shares.',
                    'The decision diagram and researchVariant field specify the executable X/n override.'],
                jointResearch=dict(selections=analysis['selections'],assessment=analysis['assessment'][parent],
                    membership=analysis['membership_attribution'][parent][pair],
                    source_manifest_sha256=sha256(root/'input_manifest.json')))
            stem=parent+'-'+pair.replace('/','-')
            (output/(stem+'.html')).write_text(render_backtest_report_html(report),encoding='utf8')
            write_json(output/(stem+'.report.json'),report);files.append(stem+'.html')
    return files


def render(root,output,a):
    output.mkdir(parents=True,exist_ok=True);details=detailed_reports(root,output,a)
    selected=a['selections']['candidate']['selected']
    all_monthly=all(r['selected']=='6/monthly' for r in a['selections']['folds'])
    verdict=('The causal selector retained the current top-six monthly policy in all three folds.' if all_monthly
        else 'The selected joint walk-forward policy '+('passes' if a['assessment']['FR25']['numerical_retention_pass'] else 'does not pass')+' the registered aggregate retention criteria.')
    lines=['# Joint ETF selection width and rebalance threshold','',verdict,
        '',f'Final trailing-three-year research candidate: **(X,n) = {selected}**. This is the selected pair within the tested grid, not a global optimum or trading approval.','',
        'X = 4, 6, 8, 10, 12, all eligible (maximum 14 for FR25 and 12 for F3). '
        'n = 0.05, 0.10, 0.20, 0.40, 0.60, 0.80, 1.00, or monthly only. '
        'Cash is included in target distance. Existing eligibility gates, defensive fallback, models and sizing stay fixed. '
        'The approved previous-monthly macro fallback remains explicit.','',
        '## Causal selections','', '| Training window | Activation | (X,n) | Pairs passing performance guards |', '| --- | --- | --- | --- |']
    for r in a['selections']['folds']:
        passing=', '.join(k for k,v in r['passing'].items() if v) or 'None'
        lines.append(f"| {r['start']}–{r['end']} | {r['activation']} | {r['selected']} | {passing} |")
    lines+=['','Performance checks also require a passing adjacent grid pair before selection. '
        'An isolated passing pair is rejected by the registered stability rule. '
        'These annual decisions use only the preceding training window, but the historical sample and parent strategies were already inspected; this is not an untouched holdout.']
    lines+=['','## Validation performance: 2024-01-02 through 2026-10-14','',
        '| Parent | Policy | Net Sharpe | CAGR | Max drawdown | Annual gross turnover |',
        '| --- | --- | ---: | ---: | ---: | ---: |']
    for parent in ('FR25','F3'):
        for pair in ('6/monthly','WF'):
            m=a['validation'][parent][pair]['5-0']
            lines.append(f"| {parent} | {pair} | {m['sharpe']:.3f} | {m['cagr']:.2%} | {m['max_drawdown']:.2%} | {m['annual_turnover']:.2f}× |")
    lines+=['','F3 is a legacy-parent sensitivity comparison because its current activity overlay uses adjusted price and inherited source volume. '
        'Its 12 and all columns are identical and do not provide independent confirmation.','',
        '## Does increasing X reduce churn?','',
        'Full 2021–2026 period at 5bp per traded side. These fixed-pair comparisons are descriptive and use inspected data.','',
        '| Parent | X | n | Sharpe | CAGR | Max drawdown | Turnover/year | Mean held ETFs | Entry/exit share of trading |',
        '| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for parent in ('FR25','F3'):
        for x in a['protocol']['widths']:
            for n in ('monthly','0.10'):
                pair=x+'/'+n;m=a['full_sample'][parent][pair]['5-0'];v=a['membership_attribution'][parent][pair]
                lines.append(f"| {parent} | {x} | {n} | {m['sharpe']:.3f} | {m['cagr']:.2%} | {m['max_drawdown']:.2%} | {m['annual_turnover']:.2f}× | {m['mean_held_count']:.2f} | {v['entry_exit_fraction_ex_initial']:.1%} |")
    lines+=['','Entry/exit share excludes initial establishment and counts trades where actual units cross zero. '
        'The remainder adjusts retained ETF weights. FR25 target membership counts below distinguish rank-cutoff changes from eligibility/fallback changes; they are counts, not causal PnL attribution.','',
        '| FR25 pair | Rank-cutoff changes | Eligibility changes | Fallback changes |', '| --- | ---: | ---: | ---: |']
    for x in a['protocol']['widths']:
        pair=x+'/0.10';c=a['membership_attribution']['FR25'][pair]['target_membership_changes']
        lines.append(f"| {pair} | {c['rank_cutoff']} | {c['eligibility']} | {c['fallback']} |")
    lines+=['','## Reactivity, concentration and liquidity diagnostics','',
        '| Parent | Pair | Rebalance dates | Five-session fill reversals | Effective holdings | Maximum held weight | P95 daily-volume fraction |',
        '| --- | --- | ---: | ---: | ---: | ---: | ---: |']
    for parent in ('FR25','F3'):
        for pair in ('6/monthly','6/0.10','8/monthly','8/0.10','12/monthly','12/0.10'):
            e=a['events'][parent][pair];m=a['full_sample'][parent][pair]['5-0'];liq=a['liquidity'][parent][pair]
            lines.append(f"| {parent} | {pair} | {e['executed']} | {e['five_session_opposite_direction_fills']} | {m['mean_effective_holdings']:.2f} | {m['maximum_weight']:.1%} | {liq['p95']:.3%} |")
    lines+=['','Reversals count opposite-direction consecutive fills in the same ETF within five sessions, including monthly events. '
        'Effective holdings are the inverse concentration of invested ETF weights. The volume proxy is simulated traded USD divided by audited raw daily dollar volume, measured ex post; it is not a capacity or slippage model. '
        'All 98 base-case policies retain these diagnostics in the analysis artifact.']
    lines+=['','## Cost and delay robustness of the selected walk-forward policy','',
        '| Parent | Cost | Extra delay | Sharpe difference | CAGR difference | Drawdown difference |',
        '| --- | ---: | ---: | ---: | ---: | ---: |']
    for parent in ('FR25','F3'):
        for scenario,m in a['validation'][parent]['WF'].items():
            b=a['validation'][parent]['6/monthly'][scenario];c,d=scenario.split('-')
            lines.append(f"| {parent} | {c}bp | {d} | {m['sharpe']-b['sharpe']:+.3f} | {(m['cagr']-b['cagr'])*100:+.2f}pp | {(m['max_drawdown']-b['max_drawdown'])*100:+.2f}pp |")
    lines+=['','## Conditional uncertainty','',
        '20,000 jointly paired stationary-bootstrap replicates on the common 2024–2026 calendar, including URTH. '
        'Seed 20261015, primary mean block 63 sessions and sensitivities 21/126. '
        'Holm spans 96 contrasts. The selector is not rerun within bootstrap replicates, so inference is conditional/descriptive; no formal superiority claim.','',
        '| Parent | Mean block | WF Sharpe difference | Conditional 95% interval | Descriptive Holm p |',
        '| --- | ---: | ---: | --- | ---: |']
    for block,result in a['inference'].items():
        for r in result['contrasts']:
            if r['contrast'].endswith('/WF'):
                lo,hi=r['ci95'];lines.append(f"| {r['contrast'].split('/')[0]} | {block} | {r['sharpe_difference']:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {r['descriptive_holm_p']:.3f} |")
    lines+=['','## Verification and limits','',
        '- 576 fixed-pair scenarios plus 12 continuous walk-forward scenarios; USD100k checks use the selected pairs without retuning.',
        '- Top-six targets match all 1,453 parent daily evaluations, including the final pending date; 60 common parent economic replays match fills, cash, NAV and final positions exactly.',
        f"- {a['native_checks']} independent native LEAN/Python checks; independent adoption checks for all 98 parent/policy combinations. Monthly width/threshold switches carry the account and adopted-target state.",
        '- Whole adjusted units, zero cash interest, fixed bps transaction costs, next-open execution, and one extra session delay stress. Revised price/economic vintages and current universe membership remain retrospective limitations.',
        '- Shared SOTA-format detail reports retain constituent attribution, holdings, benchmark curves and the complete variant decision contract. No tracking, allocation, approvals or broker settings changed.',
        '- This current-universe study cannot establish behavior in the expanded ETF pool. Full-pool validation requires a separately qualified parent and preserved point-in-time/data/promotion gates.',
        '',f"[Full replay evidence]({Path(os.path.relpath(root/'analysis.json',output)).as_posix()}) · [All scenarios](grid.csv)",
        '',*['- ['+f+']('+f+')' for f in details]]
    (output/'results.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    with (output/'grid.csv').open('w',newline='',encoding='utf8') as stream:
        writer=csv.writer(stream);writer.writerow(['parent','X_n','cost_delay','sharpe','cagr','max_drawdown','annual_turnover','mean_held_count'])
        for parent,pairs in a['full_sample'].items():
            for pair,scenarios in pairs.items():
                for scenario,m in scenarios.items():writer.writerow([parent,pair,scenario,*[m[k] for k in ('sharpe','cagr','max_drawdown','annual_turnover','mean_held_count')]])
    plot(output,a)
    body='<h1>How wide should selection be, and when should it rebalance?</h1><p>'+verdict+'</p><p>Final registered selector: <b>'+selected+'</b>.</p>'
    body+='<p><a href="results.md">Complete results and limits</a> · <a href="grid.csv">All 588 scenarios</a></p>'
    body+='<img src="surface.png" alt="Joint Sharpe and turnover surface" style="width:100%"/><h2>Detailed strategy reports</h2><ul>'
    body+=''.join('<li><a href="'+f+'">'+f+'</a></li>' for f in details)+'</ul>'
    (output/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>Selection width and rebalance timing</title>'
        '<style>body{font:16px/1.6 system-ui;max-width:1350px;margin:40px auto;padding:0 24px;color:#203843;background:#faf9f5}a{color:#126e7e}</style>'+body,encoding='utf8')


def plot(output,a):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    x=a['protocol']['widths'];n=a['protocol']['thresholds']
    fig,axes=plt.subplots(2,2,figsize=(15,9),layout='constrained')
    for i,parent in enumerate(('FR25','F3')):
        for j,(metric,title) in enumerate([('sharpe','Net Sharpe'),('annual_turnover','Annual gross turnover / NAV')]):
            values=np.array([[a['full_sample'][parent][width+'/'+threshold]['5-0'][metric] for threshold in n] for width in x])
            ax=axes[i,j];im=ax.imshow(values,aspect='auto',cmap='YlGnBu' if j==0 else 'YlOrBr')
            ax.set_xticks(range(len(n)),n);ax.set_yticks(range(len(x)),x)
            ax.set_xlabel('Target-change threshold n');ax.set_ylabel('Maximum selected ETF count X');ax.set_title(parent+' · '+title)
            for r in range(len(x)):
                for c in range(len(n)):
                    midpoint=(values.max()+values.min())/2
                    ax.text(c,r,f'{values[r,c]:.2f}' if j==0 else f'{values[r,c]:.1f}',ha='center',va='center',
                        color='white' if values[r,c]>midpoint else '#203843',fontsize=10)
            fig.colorbar(im,ax=ax,shrink=.8)
    fig.suptitle('Selection width × adoption threshold — 2021–2026, 5bp costs\nFixed-pair surface is descriptive; annual causal selection determines the policy',fontsize=16)
    fig.savefig(output/'surface.png',dpi=150);plt.close(fig)


def main(root,output):
    checked_files(root,'input_manifest.json')
    for frozen in (root/'source/systematic_trading').rglob('*.py'):
        current=Path('src/systematic_trading')/frozen.relative_to(root/'source/systematic_trading')
        if sha256(current)!=sha256(frozen):raise ValueError('Active analysis dependency differs from frozen source: '+str(current))
    for parent in ('FR25','F3'):checked_files(root,'target_manifest_'+parent+'.json')
    native=read_json(root/'native_summary.json')
    if not native or any(r['status']!='succeeded' for r in native.values()):raise ValueError('Native checks incomplete')
    for label in native:checked_files(root/'native'/label,'artifact_manifest.json')
    for i,path in enumerate((root/'receipts').glob('*.json'),1):
        for relative,digest in read_json(path)['files'].items():
            if sha256(root/relative)!=digest:raise ValueError('Changed economic artifact '+relative)
        verify_usd_bundle(root/'bundles'/path.stem)
        if i%100==0:print('Verified replay bundles',i,flush=True)
    p=read_json(root/'protocol.json');helper=load_helper(Path(p['parent_root']))
    sources=root/'analysis_sources';sources.mkdir(exist_ok=True)
    shutil.copyfile(Path(__file__),sources/'runner.py')
    shutil.copyfile(Path(p['parent_root'])/'analysis_runner.py',sources/'parent_analysis.py')
    reporting=Path('src/systematic_trading/research/target_change_reporting.py')
    shutil.copyfile(reporting,sources/'target_change_reporting.py')
    analysis_inputs=[root/'protocol.json',root/'selections.json',root/'native_summary.json',root/'input_manifest.json',
        root/'target_manifest_FR25.json',root/'target_manifest_F3.json',root/'replay_validation.json',*sources.iterdir()]
    write_json(root/'analysis_input_manifest.json',{p.relative_to(root).as_posix():sha256(p) for p in analysis_inputs})
    a=evaluate(root,helper);a['inference']=inference(root,helper,a);a['native_checks']=len(native)
    a['completed_at']=datetime.now(UTC).isoformat()
    a['size_diagnostics']={}
    for parent in ('FR25','F3'):
        for pair in dict.fromkeys(['6/monthly','WF',a['selections']['candidate']['selected']]):
            s=read_json(root/'metrics'/(name(parent,pair,initial=100_000)+'.json'))
            a['size_diagnostics'][parent+'/'+pair]={k:s[k] for k in ('sharpe','cagr','max_drawdown','annual_turnover')}
    write_json(root/'analysis.json',a);shutil.copyfile(Path(__file__),root/'analysis_runner.py')
    render(root,output,a)
    write_json(root/'acceptance.json',dict(status='passed',full_size_replays=588,native_checks=len(native),
        independent_policy_checks=98,selector_reproduced=True,conditional_inference_only=True,
        analysis_sha256=sha256(root/'analysis.json'),analysis_runner_sha256=sha256(root/'analysis_runner.py'),
        analysis_input_manifest_sha256=sha256(root/'analysis_input_manifest.json'),
        selection_sha256=sha256(root/'selections.json'),candidate=a['selections']['candidate']['selected'],
        candidate_frozen_at=a['completed_at'],promotion_eligible=False))
    write_json(output/'report_manifest.json',{p.name:sha256(p) for p in sorted(output.iterdir()) if p.is_file() and p.name!='report_manifest.json'})
    print('Joint reports complete',output,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--output',type=Path,default=OUTPUT)
    args=parser.parse_args();main(args.root.resolve(),args.output.resolve())
