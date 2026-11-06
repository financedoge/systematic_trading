"""Summarize the locked stability search and paired regime-gap uncertainty."""
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np

import research_etf_stability as s
from report_cash_relative_retest import render_review
from report_fr25_breadth import table
from research_cash_relative_retest import passes
from systematic_trading.research.evidence_review import assess

NAMES={'selected':'Monthly Alpha54','original':'Original14 FR25 6/4','expanded':'Expanded FR25 6/4'}
ARMS=('original','expanded','selected')


def bootstrap(days):
    draws={}
    for era,(start,end) in s.ERAS.items():
        ix=np.flatnonzero((days>=start)&(days<=end))
        rng=np.random.default_rng(20261103+int(era=='OOS'))
        n=len(ix)
        blocks=(rng.integers(0,n,(4000,(n+20)//21,1))+np.arange(21))%n
        draws[era]=ix[blocks.reshape(4000,-1)[:,:n]]
    out={}
    gaps={}
    for arm in ARMS:
        with np.load(s.WORK/'paths'/f'{arm}_c5d0.npz') as p:
            nav=np.r_[1e6,p['nav']]
        ret=nav[1:]/nav[:-1]-1
        estimates={}
        for era,draw in draws.items():
            r=ret[draw]
            std=r.std(axis=1,ddof=1)
            sr=np.divide(r.mean(axis=1)*np.sqrt(252),std,out=np.zeros_like(std),where=std>1e-12)
            estimates[era]=np.column_stack([sr,np.expm1(np.log1p(r).mean(axis=1)*252)])
        gaps[arm]=estimates['OOS']-estimates['IS']
        out[arm]=dict(signed_gap_95=np.quantile(gaps[arm],[.025,.975],axis=0).tolist())
    for arm in ('original','expanded'):
        diff=np.abs(gaps['selected'])-np.abs(gaps[arm])
        out[arm]['selected_minus_reference_absolute_gap_95']=np.quantile(diff,[.025,.975],axis=0).tolist()
    s.write(s.OUT/'uncertainty.json',dict(columns=['Sharpe','CAGR'],draws=4000,block_sessions=21,intervals=out))
    return out


def confirm_archived_inspections(selection,attribution):
    # These particular inspected books are identical down to all per-ETF daily P&L.
    if selection['spec']!=[0,4,0,'monthly']:
        raise ValueError('Fresh inspection charts are required for a different selection')
    rel=(s.ALPHA_WORK/'paths/alpha54-monthly_c5d0.npz').relative_to(s.REPO).as_posix()
    original=s.read(s.ALPHA/'result-manifest.json')[rel]
    new=s.digest(s.WORK/'paths/selected_c5d0.npz')
    assert new==original
    receipts=[]
    manifest=s.read(s.ALPHA/'artifact-manifest.json')
    for row in s.read(s.ALPHA/'weakest.json'):
        era={'calibration':'IS','later':'OOS'}[row['window']]
        values=attribution['selected'][era]['by_symbol']
        weakest=min((k for k in values if k not in ('BIL','URTH')),key=lambda k:(values[k],k))
        assert weakest==row['symbol'] and abs(values[weakest]-row['net_contribution'])<1e-10
        stem=f"weakest-{row['window']}-{weakest}"
        files=[stem+'.png',stem+'-daily.csv',stem+'-trades.csv']
        for f in files:assert s.digest(s.ALPHA/f)==manifest[f]
        receipts.append(dict(era=era,symbol=weakest,net_contribution=values[weakest],files=files))
    s.write(s.OUT/'weakest-inspections.json',dict(primary_daily_path_sha256=new,parent=s.ALPHA.name,inspections=receipts))
    return receipts


def report():
    protocol=s.validate()
    selected=s.read(s.OUT/'selection.json')
    results=s.read(s.OUT/'results.json')
    attribution=s.read(s.OUT/'attribution.json')
    withheld=s.read(s.OUT/'withholding.json')
    metrics={a:v['5-0'] for a,v in results.items()}
    days=s.breadth.input_arrays()['days']
    uncertainty=bootstrap(days[days>=s.parent.START])
    inspections=confirm_archived_inspections(selected,attribution)
    def gap(arm,key):
        return abs(metrics[arm]['OOS'][key]-metrics[arm]['IS'][key])
    stable=(selected['qualified'] and all(gap('selected',k)<gap(a,k) for k in ('cagr','sharpe') for a in ('original','expanded'))
            and all(withheld['selected'][era]['top_three']['cagr']>0 for era in s.ERAS))
    counts={arm:{era:sum(passes(results['selected'][f'{c}-{d}'][era],results[arm][f'{c}-{d}'][era])
                for c,d in s.COSTS) for era in s.ERAS} for arm in ('original','expanded','unranked','momentum-monthly')}
    main_table=table(['Recipe','IS CAGR','OOS CAGR','Gap (pp)','IS Sharpe','OOS Sharpe','Gap','IS / OOS max DD'],
        [[NAMES[a],f"{metrics[a]['IS']['cagr']:.2%}",f"{metrics[a]['OOS']['cagr']:.2%}",f"{gap(a,'cagr')*100:.2f}",
          f"{metrics[a]['IS']['sharpe']:.3f}",f"{metrics[a]['OOS']['sharpe']:.3f}",f"{gap(a,'sharpe'):.3f}",
          ' / '.join(f"{metrics[a][e]['max_drawdown']:.2%}" for e in s.ERAS)] for a in ARMS])
    concentration=table(['Portfolio','Era','Largest three contributors (pp of starting NAV)','Share of net gain','Share of positive contributions','CAGR after exclusion','Sharpe after exclusion'],
        [[NAMES[a],e,', '.join(f"{sym} {100*attribution[a][e]['by_symbol'][sym]:.2f}" for sym in attribution[a][e]['top']),
          f"{attribution[a][e]['share_of_net']:.1%}",f"{attribution[a][e]['share_of_positive']:.1%}",
          f"{withheld[a][e]['top_three']['cagr']:.2%}",f"{withheld[a][e]['top_three']['sharpe']:.3f}"] for a in ARMS for e in s.ERAS])
    sensitivity=table(['Portfolio','Era','Baseline CAGR','Top 1 removed','Top 3 removed','IS top 3 removed','SOXX & XLK removed','Also remove EWY & EWT'],
        [[NAMES[a],e,f"{metrics[a][e]['cagr']:.2%}",*[f"{withheld[a][e][k]['cagr']:.2%}" for k in
          ('top_one','top_three','training_top_three','direct_tech','tech_and_regional')]] for a in ARMS for e in s.ERAS])
    annual=table(['Year','Original 6/4 CAGR / Sharpe','Expanded 6/4 CAGR / Sharpe','Alpha54 CAGR / Sharpe'],
        [[y,*[f"{metrics[a][str(y)]['cagr']:.2%} / {metrics[a][str(y)]['sharpe']:.3f}" for a in ARMS]] for y in range(2021,2027)])
    costs=table(['Cost bp','Extra sessions','Era','CAGR','Sharpe','Max DD','Annual turnover','Actual fees USD'],
        [[c,d,e,f"{m['cagr']:.2%}",f"{m['sharpe']:.3f}",f"{m['max_drawdown']:.2%}",f"{m['annual_turnover']:.2f}",f"{m['fees_usd']:,.0f}"]
         for c,d in s.COSTS for e in s.ERAS for m in [results['selected'][f'{c}-{d}'][e]]])
    controls=table(['Control','IS CAGR / Sharpe','OOS CAGR / Sharpe'],[
        [a,*[f"{metrics[a][e]['cagr']:.2%} / {metrics[a][e]['sharpe']:.3f}" for e in s.ERAS]]
        for a in ('alternate','unranked','momentum-monthly','cash','BIL_buyhold','URTH_buyhold','pool_buyhold')])
    interval_table=table(['Portfolio','Later minus IS Sharpe, 95% interval','Later minus IS CAGR, 95% interval (pp)'],[
        [NAMES[a],' to '.join(f'{r[0]:.2f}' for r in uncertainty[a]['signed_gap_95']),
         ' to '.join(f'{r[1]*100:.1f}' for r in uncertainty[a]['signed_gap_95'])] for a in ARMS])
    weak='\n\n'.join(f"{r['era']} · {r['symbol']} contributed {100*r['net_contribution']:.2f} pp. "+
        ' · '.join(f"[{label}](../{s.ALPHA.name}/{f})" for label,f in zip(('Inspection chart','Daily prices, volume, states and fills','FIFO trade outcomes'),r['files'],strict=True)) for r in inspections)
    body=f"""# ETF winner dependence and historical stability

The two FR25 6/4 portfolios derived more than half their later gains from three ETFs. The cash-withholding replays still produced positive later returns. The training stability rule selected standalone monthly Alpha54. Its gaps in CAGR and Sharpe were smaller than both 6/4 books and its return stayed positive after withholding the largest three winners in each era. Its earlier 19.33% drawdown and lower later return matter when comparing portfolio quality.

{main_table}

IS is January 4, 2021–December 31, 2024. The later chronological window runs January 2, 2025–October 30, 2026. All returns include actual whole-unit rebalances at 5 bp per traded notional and next-open execution. Sharpe uses zero as the reference rate and CAGR uses 252 sessions per year. Earlier studies inspected both periods and Alpha54 before this comparison.

## How much depended on a few ETFs?

{concentration}

{sensitivity}

Contribution is actual net ETF P&L divided by the portfolio's opening NAV in each era. The share of positive contributions uses the sum over all positive ETF contributions before offsetting losses. The exclusion replays place the named ETFs' target weights in zero-interest cash on the entire calendar, keep the unperturbed adoption dates and other target weights, and recalculate units, costs and NAV. The later window inherits the counterfactual book's positions. The ex-post leaders are a deliberate stress. The IS-leaders column freezes the names before the later window. [Per-ETF attribution](attribution.json) · [Full cash-withholding results](withholding.json).

SOXX and XLK proxy direct semiconductor and technology-fund exposure. The regional extension removes whole Korea and Taiwan funds, including their nontechnology holdings. Broad equities can retain indirect exposure to AI. These calculations can measure portfolio dependence on named funds. Attributing common market moves to AI would require additional evidence. The future frequency of this regime remains unknown.

## How the candidate was selected

Each sleeve produces its daily prior-close target on the same 52 supported histories. FR25 combines momentum and financial ranks and retains the existing six-name selection, four-qualifier fallback, downstream risk overlays and final cap. Standalone Alpha54 uses the published adjusted-price formula, ranks eligible risky ETFs and sizes its top six by inverse volatility. The third sleeve applies inverse 63-session volatility to the full eligible risky pool. Target weights are averaged before trading so offsetting changes net within one book. All 15 combinations in 25-point steps were tested with monthly and monthly-plus-0.40 target-change timing. The event compares current theoretical and last adopted targets including cash. [Parent Alpha54 definition and formula](../{s.ALPHA.name}/protocol.json) · [FR25 and inverse-volatility controls](../{s.parent.OUT.name}/protocol.json).

The 2021–2022 and 2023–2024 halves were ranked on four criteria. Higher weaker-half CAGR and Sharpe reward positive performance across both halves. Smaller half-to-half changes in CAGR and Sharpe reward consistency. The rule chose the eligible candidate with the best worst rank across these criteria, breaking ties by the frozen rule. Each half had to be profitable. Training CAGR had to reach {selected['return_floor']:.2%}, and drawdown could exceed expanded 6/4 by at most 2 points. Removing the candidate's three biggest training winners or imposing 20 bp and an extra session both had to leave positive training CAGR. {selected['eligible_candidates']} of 30 candidates qualified.

Monthly Alpha54 earned {selected['selected_metrics']['first']['cagr']:.2%} CAGR with {selected['selected_metrics']['first']['sharpe']:.3f} Sharpe in the first half and {selected['selected_metrics']['second']['cagr']:.2%} with {selected['selected_metrics']['second']['sharpe']:.3f} in the second. Selection used data through {selected['max_price_date']}. This is additional diagnostic evidence on a previously retained recipe. [Frozen protocol](protocol.json) · [Training search](training.json) · [Sealed choice](selection.json).

For perspective, the earlier 42/33 breadth winner had still closer point estimates (3.22% vs 5.09% CAGR and 0.876 vs 1.271 Sharpe). Its 3.22% IS CAGR falls below this study's return floor. The floor states the return trade-off explicitly. [Breadth comparison](../{s.breadth.OUT.name}/index.html).

## Years, frictions and uncertainty

{annual}

{costs}

{controls}

The alternate timing row uses the same selected Alpha54 weights with monthly-plus-0.40 adoption. The separate portfolio performance guard requires higher Sharpe, CAGR loss at most 0.5 pp and drawdown worsening at most 2 pp. Alpha54 passed against expanded 6/4 in {counts['expanded']['IS']}/6 training and {counts['expanded']['OOS']}/6 later settings, and against original 6/4 in {counts['original']['IS']}/6 and {counts['original']['OOS']}/6. [All 66 base and friction cases](results.json).

{interval_table}

The intervals resample paired dates across portfolios within each era using 21-session circular blocks, 4,000 draws. Both reference comparisons' intervals for the difference in absolute gaps include zero for both metrics. The observed stability ranking could plausibly reverse. The intervals condition on the chosen candidate and observed regimes. The full strategy-search history is larger than these 30 trials. [Bootstrap results](uncertainty.json). Repeatability still needs a rule frozen before new observations arrive.

## Weakest risky ETF inspections

The selected monthly portfolio exactly reproduces the archived Alpha54 daily NAV, turnover, fees, exposure and every symbol's daily contribution, verified by the hash of the complete primary path. The original dated inspection charts and trade files therefore apply directly. The criterion is lowest net contribution divided by era-opening NAV in each era, excluding BIL, the benchmark and cash. Protection comes from selection, the target cap and cash allocation. Exits occur at adopted rebalances.

{weak}

## Evidence

The parent price batch is {protocol['price_pin']['batch']}. Candidate targets and published input hashes were checked before the search. Historical membership and publication availability remain reconstructed. The replay models zero cash interest and fixed trading frictions. [Inspection verification](weakest-inspections.json) · [Independent native checks](native-validation.json) · [Evidence review](assessment.json).
"""
    (s.OUT/'results.md').write_text(body,encoding='utf8')
    css='body{font:16px/1.55 system-ui;max-width:1180px;margin:auto;padding:2rem;color:#203747}td,th{padding:.45rem;border-bottom:1px solid #d7e1e4;text-align:left}table{border-collapse:collapse}a{color:#08667a}'
    (s.OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>ETF winner dependence and stability</title><style>'+css+'</style>'+render_review(body),encoding='utf8')
    s.write(s.OUT/'summary.json',dict(stability_checks_pass=stable,guard_counts=counts,selected=selected['id'],
        gaps={a:{k:gap(a,k) for k in ('cagr','sharpe')} for a in ARMS},weakest=inspections))


def close():
    choice=s.read(s.OUT/'selection.json')
    summary=s.read(s.OUT/'summary.json')
    native=s.read(s.OUT/'native-validation.json')
    assert len(native['cases'])==3 and all(r['status']=='succeeded' and r['max_nav_error_usd']<=.01 for r in native['cases'])
    dossier=s.read(s.parent.OUT/'dossier.json')
    p=s.validate()
    dossier.update(study_id=s.OUT.name,candidate_id=choice['id'],preregistered_net_rule=p['objective']+' '+p['eligibility'],
        net_verdict='not_established',operator_disposition='Operator requested this robustness comparison. Results ready for discussion.',
        prospective_plan_or_gap='A genuinely subsequent, pre-frozen evaluation is outstanding. Parent performances and both eras have previously been inspected.')
    dossier['sample'].update(recipe_frozen_at=p['frozen_at'],trial_count=30,
        prior_search_and_multiplicity='Fifteen allocation combinations and two timings, built from previously inspected sleeves. Older FR25, Alpha101 and construction searches materially expand total multiplicity.',
        label_boundary_and_overlap='The selection engine and stress inputs end December 31, 2024. Winner weights and timing sealed before the later replay. Bootstrap resamples 21-session daily blocks.')
    dossier['inputs']['limitations_and_missing_policy']='Two frozen full-pool parents have identical audited price/volume arrays and pin, with BWX/XOP held on identity. Incomplete vintage or membership availability remains disclosed.'
    dossier['decay']=[dict(signal='Selected monthly Alpha54',status='unidentifiable',horizons=[1,5,10,21],half_life_sessions=None,
        method_uncertainty_and_caveats='Identical selection signal and primary daily path as retained Alpha54. Parent horizon-dependent rank-IC evidence does not establish an exponential half-life.',
        cadence_and_delay_interpretation='Replayed monthly and target-change adoption with 5/10/20 bp and zero/one extra session. Annual, two-half, cross-era gap and winner-exclusion behavior are reported.')]
    dossier['coverage_gaps']=['Reused evaluation and historically selected sleeves. Prospective transfer remains untested.',
        'Named ETF removals do not identify AI causality or a no-AI market path. Exposure can overlap across securities.',
        'Intervals are conditional on selected recipe. Return guards and stability checks answer separate questions.']
    refs={s.OUT/'protocol.json':['protocol','strategy_recipe'],s.ALPHA/'protocol.json':['strategy_recipe'],
          s.parent.OUT/'input-verification.json':['published_input_verification'],s.OUT/'selection.json':['selection'],
          s.OUT/'training.json':['selection'],s.OUT/'results.json':['net_results','matched_controls','cost_delay','chronology'],
          s.OUT/'withholding.json':['matched_controls'],s.OUT/'uncertainty.json':['uncertainty'],
          s.ALPHA/'signal-diagnostics.json':['decay_stability'],s.OUT/'weakest-inspections.json':['weakest_inspections'],
          s.OUT/'native-validation.json':['independent_validation']}
    for row in summary['weakest']:
        refs[s.ALPHA/row['files'][0]]=['weakest_inspections']
    dossier['artifacts']=[dict(path=f.relative_to(s.REPO).as_posix(),sha256=s.digest(f),roles=roles) for f,roles in refs.items()]
    s.write(s.OUT/'dossier.json',dossier)
    review=assess(dossier,s.REPO,s.REPO/'config/research-evidence-policy-v1.json')
    assert not review['integrity_and_claim_issues']
    s.write(s.OUT/'assessment.json',review)
    suite=next(iter(ET.parse(s.REPO/'var/maintenance/etf-stability-20261103/tests.xml').getroot()))
    assert int(suite.attrib['errors'])==int(suite.attrib['failures'])==0
    s.write(s.OUT/'acceptance.json',dict(tests=int(suite.attrib['tests']),native=native['cases'],status=review['status'],
        training_hash=choice['grid_sha256'],selected_path_sha256=s.digest(s.WORK/'paths/selected_c5d0.npz'),
        research_runner_sha256=p['code_sha256'],reporter_sha256=s.digest(Path(__file__)),
        assessment_sha256=s.digest(s.OUT/'assessment.json')))
    s.write(s.WORK/'summary.json',summary)
    s.write(s.OUT/'retention.json',dict(retain='Frozen rule, source pins, IS search, era results, exclusion replays, reviews and referenced Alpha54 charts.',
        after_discussion='Queue paths, detail, schedules and native validation working folders for guarded retirement after operator disposition. Shared published histories and active dependencies remain protected.'))
    s.write(s.OUT/'artifact-manifest.json',{f.name:s.digest(f) for f in s.OUT.iterdir() if f.is_file() and f.name!='artifact-manifest.json'})


if __name__=='__main__':
    import sys
    close() if sys.argv[1:]==['close'] else report()
