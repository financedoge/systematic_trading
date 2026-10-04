"""Build the review package from verified results; never choose new parameters."""
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
import shutil

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.momentum_replay import read_json, checked_files, verify_usd_bundle

ROOT=Path('var/research/momentum-20261001-v1b')
OUT=Path('research/momentum-experiments-2026-10-01')

LABELS={'parent-M':'Current parent, monthly','parent-W':'Current parent, weekly',
 'A1':'1-week momentum','A2':'2-week momentum','A3':'1-month momentum',
 'A4':'Month 2 only','A5':'Months 2–3','A6':'Short blend S','A7':'Older blend L','A8':'50/50 S/L',
 'B1':'More short when trend up','B2':'More short when trend down',
 'B3':'More short when right-skewed','B4':'More short when left-skewed',
 'C0':'Flexible breadth, immediate','C1':'Fast entry, slow exit','C2':'Slow entry, fast exit',
 'risk-M':'Monthly inverse volatility','urth':'URTH buy and hold'}


def label(key):
    return LABELS.get(key,LABELS.get(key.split('-')[0],key))


def pct(v):return f'{100*v:.2f}%'
def bp(v):return f'{10000*v:+.1f}'


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    p=read_json(ROOT/'protocol.json');s=read_json(ROOT/'statistics.json');pairs=read_json(ROOT/'paired_results.json')
    checked_files(ROOT,'input_manifest.json');checked_files(ROOT,'feature_manifest.json');checked_files(ROOT,'source_manifest.json')
    native={};failures=[]
    for path in (ROOT/'native').glob('*/run.json'):
        r=read_json(path)
        if r['status']!='succeeded':failures.append(dict(path=str(path.resolve()),error=r.get('error')));continue
        checked_files(path.parent,'artifact_manifest.json')
        parity=read_json(path.parent/'parity.json')
        if not parity['passed'] or parity['differences']:raise ValueError('Failed native parity')
        key=path.parent.name.split('-retry')[0]
        verify_usd_bundle(ROOT/'bundles'/key)
        if r['manifest_sha256']!=sha256(ROOT/'bundles'/key/'manifest.json'):raise ValueError('Changed native bundle')
        native[key]=dict(run=str(path.resolve()),receipt_sha256=sha256(path),parity_sha256=sha256(path.parent/'parity.json'))
    if any(k+'-cost5' not in native for k in s):raise ValueError('Missing native parity')
    if len(s)!=34 or len(native)!=36:raise ValueError('Unexpected trial inventory')
    for name in ('protocol.json','paired_results.json','transfer_registration.json','usd_registration.json'):
        shutil.copyfile(ROOT/name,OUT/name)
    compact={k:{cost:{field:value for field,value in metrics.items() if field not in ('daily_returns','dates','asset_daily_contribution','complete_strategy_monthly')} for cost,metrics in costs.items()} for k,costs in s.items()}
    write_json(OUT/'summary.json',compact)
    diagnostics={};parent_decisions=read_json(ROOT/'decisions/parent-M.json')
    regimes={d[:7]:row['diagnostic']['regime'] for d,row in parent_decisions.items()}
    cells=Counter((r['trend_state'],r['skew_state']) for r in regimes.values())
    diagnostics['regime_counts']={f'{a}/{b}':n for (a,b),n in cells.items()}
    for state in ('trend_state','skew_state'):
        values=[r[state] for r in regimes.values()]
        diagnostics[state+'_transitions']=sum(a!=b for a,b in zip(values,values[1:]))
    conditional={}
    for a,b in sorted(cells):
        months=[m for m,r in regimes.items() if (r['trend_state'],r['skew_state'])==(a,b)]
        conditional[a+'/'+b]=dict(months=len(months),mean_monthly_active={key:float(np.mean([s[key]['5']['monthly'][m]-s['parent-M']['5']['monthly'][m] for m in months])) for key in ('B1-M','B2-M','B3-M','B4-M')})
    diagnostics['conditional_regime_returns']=conditional
    for key in [f'C{i}-{clock}' for clock in ('M','W') for i in range(3)]:
        d=[row['diagnostic']['membership'] for row in read_json(ROOT/'decisions'/(key+'.json')).values()]
        diagnostics[key]=dict(scheduled=len(d),selected_counts={str(k):v for k,v in Counter(row.get('selected_count') for row in d).items()},
                             floor_override_events=sum(bool(row.get('floor_overrides')) for row in d),floor_override_assets=sum(len(row.get('floor_overrides',[])) for row in d),
                             fallback_count=sum(row.get('fallback',False) for row in d),seed_count=sum(row.get('seed',False) for row in d))
    stresses={}
    for key in s:
        r=s[key]['5']
        stresses[key]={name:float(np.prod([1+v for d,v in zip(r['dates'],r['daily_returns']) if first<=d<=last])-1) for name,(first,last) in p['stresses'].items()}
    diagnostics['stress_returns']=stresses
    diagnostics['active_month_concentration']={}
    diagnostics['asset_active_arithmetic_contribution']={}
    for key in s:
        if key in ('parent-M','risk-M','urth') or key.startswith('parent-') or key.startswith('transfer-'):continue
        control='U0-M' if key=='U1-M' else 'parent-W' if key.endswith('-W') else 'parent-M'
        values={m:v-s[control]['5']['monthly'][m] for m,v in s[key]['5']['monthly'].items()}
        ordered=sorted(values.items(),key=lambda v:v[1])
        diagnostics['active_month_concentration'][key]=dict(control=control,worst_five=ordered[:5],best_five=ordered[-5:])
        allowed=set(values)
        diagnostics['asset_active_arithmetic_contribution'][key]={asset:sum(a-b for d,a,b in zip(s[key]['5']['dates'],rows,s[control]['5']['asset_daily_contribution'][asset]) if d[:7] in allowed)
            for asset,rows in s[key]['5']['asset_daily_contribution'].items()}
    diagnostics['annual_cost_breaches_25bp']={k:[y for y,v in values['5']['calendar_cost_bps'].items() if v>25] for k,values in s.items()}
    diagnostics['usd_transfers']={}
    for parent in ('activity','rolling'):
        control='parent-'+parent+'-M'
        for slot in (1,2):
            key=f'transfer-{slot}-{parent}'
            diagnostics['usd_transfers'][key]={cost:float(12*np.mean([v-s[control][cost]['monthly'][m] for m,v in s[key][cost]['monthly'].items()])) for cost in ('5','10','20')}
    write_json(OUT/'diagnostics.json',diagnostics)
    primary=pairs['6']
    keys=[r['id'] for r in p['recipes'] if r['id'].endswith('-M') and r['recipe'][0] in 'ABC']
    fig,(ax,costax)=plt.subplots(1,2,figsize=(13,8),gridspec_kw={'width_ratios':[2.8,1.2]})
    values=[primary[k[:-2]+'-parent-M']['mean_annual']*100 for k in keys]
    intervals=np.array([primary[k[:-2]+'-parent-M']['ci95'] for k in keys])*100
    ypos=np.arange(len(keys))
    ax.errorbar(values,ypos,xerr=np.array([np.array(values)-intervals[:,0],intervals[:,1]-np.array(values)]),fmt='o',color='#19566c',ecolor='#8fa9b4',capsize=3)
    ax.axvline(0,color='#333333',lw=.8);ax.set_yticks(ypos,[label(k) for k in keys]);ax.invert_yaxis()
    ax.set_xlabel('Annualized paired net return difference (percentage points)')
    ax.set_title('Monthly variants vs current parent\n129 months; marginal 95% block-bootstrap intervals',loc='left',fontsize=11)
    costax.barh(ypos,[s[k]['5']['annual_cost_bps'] for k in keys],color='#66999b');costax.invert_yaxis()
    costax.set_yticks(ypos,[]);costax.axvline(25,color='#b75342',ls='--',label='25 bp allowance')
    costax.set_xlabel('Average annual trading cost (bp)');costax.set_title('5 bp per traded dollar',fontsize=11)
    costax.legend(loc='lower right',fontsize=8)
    fig.suptitle('Momentum research: return and turnover trade-offs',fontsize=16,x=.05,ha='left')
    fig.text(.05,.015,'2016-01–2026-09 · USD adjusted units · retrospective replay · no promotion · family correction reported separately',fontsize=9,color='#555555')
    fig.tight_layout(rect=(0,.045,1,.95));fig.savefig(OUT/'monthly-comparisons.png',dpi=180);plt.close(fig)
    # Separate scale and date range prevent the USD result being compared with 129-month variants.
    fig,ax=plt.subplots(figsize=(8,3.6))
    names=['U0-parent-M','U1-parent-M','U1-U0-M'];means=np.array([primary[k]['mean_annual'] for k in names])*10000
    limits=np.array([primary[k]['ci95'] for k in names])*10000
    ax.errorbar(means,np.arange(3),xerr=np.array([means-limits[:,0],limits[:,1]-means]),fmt='o',color='#19566c',capsize=4)
    ax.set_yticks(np.arange(3),['Price model vs parent','Price + USD model vs parent','USD increment (U1 − U0)']);ax.invert_yaxis();ax.axvline(0,color='#333333',lw=.8)
    ax.set_xlabel('Annualized paired net return difference (bp)');ax.set_title('USD ablation: April 2024–September 2026\n30 matched months; marginal 95% intervals',loc='left')
    fig.tight_layout();fig.savefig(OUT/'usd-ablation.png',dpi=180);plt.close(fig)
    lines=['# Momentum research results — 2026-10-01','',
        '**Decision for review: retain the current strategies. No candidate clears the registered evidence standard for promotion.**', '',
        'The short/older-window and regime-gating variants lost return against the current monthly parent. Membership buffers saved costs but also lost return. The USD feature has a small positive increment with wide uncertainty; it remains a research question.', '',
        '## Scope and evidence','',
        '- **102 Python replays:** 34 complete strategy/control portfolios × 5/10/20 bp per traded dollar. This comprises 24 additional SOTA recipes, two parent clocks, two benchmarks, two other-parent controls and four USD transfers.',
        '- **36 native LEAN parity checks passed:** all 34 portfolios at 5 bp, plus monthly parent and weekly one-week momentum at 20 bp. The remaining cost-stress runs use the same Python accounting contract; native parity is not claimed for every cost cell.',
        '- All three monthly parent target schedules reproduce the monitored service exactly: 129 decisions per parent, zero weight difference. USD cash, integer adjusted units, prior-close sizing and next-session-open fills are declared explicitly. USD results are not the monitored CNH-accounting return series.',
        '- Used all 16 logical CPUs for independent Python jobs, with one numerical thread per worker. The 26-portfolio initial Python batch completed in 67.2 seconds. Native jobs used three 4 GiB containers × five CPUs within Docker’s 15.4 GiB memory limit. The service reserve remains available.',
        '- The frozen family has 58 comparisons, including USD and six transfer slots. Primary inference uses 20,000 joint six-month calendar-block bootstrap draws; three/twelve-month sensitivities are retained. Holm correction includes unused/selected transfer slots as p=1. Transfer results are descriptive because selection used this same history.',
        '- The 2016–2026 history and 2023 split have been examined previously. These are retrospective causal replays on audited revised price vintages, not untouched validation or fully certified historical availability.', '',
        '## 1. Main comparisons','',
        'Net USD results, January 2016–September 2026. “Paired difference” is 12 × mean monthly candidate-minus-parent return; CAGR is a separate compounded measure. The cost column includes initial deployment. A negative drawdown is a loss from the previous peak.', '',
        '| Monthly recipe | Net CAGR | Max drawdown | Paired difference / year | Cost bp/year | Holm p |',
        '|---|---:|---:|---:|---:|---:|']
    r=s['parent-M']['5'];lines.append(f'| Current parent | {pct(r["cagr"])} | {pct(r["max_drawdown"])} | — | {r["annual_cost_bps"]:.1f} | — |')
    for key in keys:
        r=s[key]['5'];pair=primary[key[:-2]+'-parent-M']
        lines.append(f'| {key}: {label(key)} | {pct(r["cagr"])} | {pct(r["max_drawdown"])} | {bp(pair["mean_annual"])} bp | {r["annual_cost_bps"]:.1f} | {pair["holm_p"]:.3f} |')
    lines += ['', '![Monthly return and cost comparisons](momentum-experiments-2026-10-01/monthly-comparisons.png)','',
        'The current pool blends 63/126/252-session momentum. The new horizon rules replace only its trend component; the existing 20/60 relative tilt, tree and adaptive exposure layer remain. These results do not support replacing that component with the tested rules at this stage; they do not establish that short-term information is universally useless.', '',
        'Descriptive split of annualized paired mean returns; both periods were previously inspected:', '',
        '| Monthly recipe | 2016–2022 (84 months) | 2023–Sep 2026 (45 months) |','|---|---:|---:|']
    for key in keys:
        values={m:v-s['parent-M']['5']['monthly'][m] for m,v in s[key]['5']['monthly'].items()}
        early=12*np.mean([v for m,v in values.items() if m<'2023-01']);late=12*np.mean([v for m,v in values.items() if m>='2023-01'])
        lines.append(f'| {key} | {bp(early)} bp | {bp(late)} bp |')
    lines += ['',
        '## 2. Weekly trading and cost stress','',
        '| Weekly recipe | Net CAGR at 5 bp | Max drawdown | Paired bp/year vs weekly parent | Cost bp/year | Net CAGR at 20 bp |','|---|---:|---:|---:|---:|---:|']
    for key in ['parent-W','A1-W','A2-W','A7-W','A8-W','C0-W','C1-W','C2-W']:
        r=s[key]['5'];delta='—' if key=='parent-W' else bp(primary[key[:-2]+'-parent-W']['mean_annual'])
        lines.append(f'| {key}: {label(key)} | {pct(r["cagr"])} | {pct(r["max_drawdown"])} | {delta} | {r["annual_cost_bps"]:.1f} | {pct(s[key]["20"]["cagr"])} |')
    lines += ['',f'The unchanged weekly parent lost {abs(primary["parent-W-M"]["mean_annual"])*10000:.1f} bp/year in paired mean return relative to monthly rebalancing. Its annual cost rose from {s["parent-M"]["5"]["annual_cost_bps"]:.1f} to {s["parent-W"]["5"]["annual_cost_bps"]:.1f} bp. The 25 bp/year figure is treated as the proposed cost allowance, not a fixed fee subtraction or an agreed return hurdle.', '',
        '| Monthly recipe | CAGR at 5 bp | CAGR at 10 bp | CAGR at 20 bp | 20 bp paired difference / year |','|---|---:|---:|---:|---:|']
    for key in ['parent-M','A1-M','A2-M','A7-M','A8-M','C0-M','C1-M','C2-M']:
        delta=12*np.mean([v-s['parent-M']['20']['monthly'][m] for m,v in s[key]['20']['monthly'].items()])
        lines.append(f'| {key} | {pct(s[key]["5"]["cagr"])} | {pct(s[key]["10"]["cagr"])} | {pct(s[key]["20"]["cagr"])} | {bp(delta)} bp |')
    lines += ['', '## 3. Membership symmetry and market states','',
        f'C1 (fast entry, slow exit) reduced annual cost to **{s["C1-M"]["5"]["annual_cost_bps"]:.1f} bp**, with net CAGR {pct(s["C1-M"]["5"]["cagr"])}. C2 (slow entry, fast exit) cost {s["C2-M"]["5"]["annual_cost_bps"]:.1f} bp/year and returned {pct(s["C2-M"]["5"]["cagr"])} CAGR. Neither beats the original parent.',
        f'C1 minus the breadth-only C0 control was {bp(primary["C1-C0-M"]["mean_annual"])} bp/year; C2 minus C0 was {bp(primary["C2-C0-M"]["mean_annual"])} bp/year. Both Holm p-values are 1.000. The timing direction is not resolved by this evidence.', '',
        '| Policy | Selected-count distribution at scheduled decisions | Minimum-six override assets | Neutral fallback decisions |','|---|---|---:|---:|']
    for key in ['C0-M','C1-M','C2-M','C1-W','C2-W']:
        r=diagnostics[key];counts=', '.join(f'{k}: {v}' for k,v in sorted(r['selected_counts'].items()) if k!='None')
        lines.append(f'| {key} | {counts} | {r["floor_override_assets"]} | {r["fallback_count"]} |')
    lines += ['', 'Counts include four/five eligible-asset exceptions. “Neutral fallback” means the inherited pool filter lets the full inverse-volatility basket through when fewer than four pass; it does not move to cash. Slow-entry delays are sometimes overridden by the minimum-six rule. Held counts also include residual integer-unit positions, so they differ from selected counts.', '',
        'The trend/skew hypothesis must keep the two measures separate:', '',
        '| Trailing equity trend | Left skew | Neutral skew | Right skew |','|---|---:|---:|---:|']
    for trend in ['up','down']:lines.append(f'| {trend} | {cells[(trend,"left")]} | {cells[(trend,"neutral")]} | {cells[(trend,"right")]} |')
    lines += ['',f'These are 129 monthly decisions. There were {diagnostics["trend_state_transitions"]} trend-state changes and {diagnostics["skew_state_transitions"]} skew-state changes. Upward trend coincided with left skew in 42 months and right skew in only 11. All four dynamic gates underperformed the parent; conditional cell results are descriptive and saved in the diagnostics.',
        f'The dynamic-versus-static comparison also matters: B3 exceeded the 50/50 blend by {bp(primary["B3-A8"]["mean_annual"])} bp/year (Holm p={primary["B3-A8"]["holm_p"]:.3f}), but trailed the older blend by {abs(primary["B3-A7"]["mean_annual"])*10000:.1f} bp/year. All twelve gate-versus-static comparisons are retained in the ledger.', '',
        '## 4. USD data and predictive test','',
        'Downloaded the Fed’s revised daily broad-dollar history (5,410 dated rows, including source-missing values) and **92 ALFRED snapshots** for monthly decisions from March 2019 through October 2026. The new broad index began in February 2019. Every 21/63-observation USD change uses one complete vintage, so rebasing and historical revisions are not spliced across snapshots. Missing source values remain missing; valid-observation horizons and maximum span/staleness checks are explicit.',
        'The snapshots passed identity, date order, positivity, coverage, staleness and level-jump checks, then were published with hash-verified analytical readback. A conservative prior-calendar-day vintage makes them available before the signal close. ALFRED supplies daily vintage evidence; independent intraday dissemination timestamps remain uncertified.',
        'U0 uses short/older momentum and volatility. U1 adds 21/63-observation broad-dollar changes with separate shrunken coefficients per ETF. Both use the same expanding ridge model, fixed penalty, training-only standardization and bounded allocation tilt. They require 60 completed monthly labels with a strict fit-close embargo. Before eligibility, both portfolios follow the unchanged parent.', '',
        '**Matched evaluation: April 2024–September 2026, 30 months.**', '',
        '| Comparison | Annualized paired difference | Marginal 95% interval | Raw p | Holm p |','|---|---:|---:|---:|---:|']
    for key in ['U0-parent-M','U1-parent-M','U1-U0-M']:
        r=primary[key];lines.append(f'| {key} | {bp(r["mean_annual"])} bp | [{bp(r["ci95"][0])}, {bp(r["ci95"][1])}] bp | {r["p"]:.3f} | {r["holm_p"]:.3f} |')
    lines += ['', '![USD predictive ablation](momentum-experiments-2026-10-01/usd-ablation.png)','',
        'The USD-specific result is **U1 minus U0**. U1 beating the parent alone would mix the price-model effect with USD information. The USD increment’s interval spans zero; 30 months has limited power and this history is reused. Best/worst active months and asset contributions are saved in diagnostics without removing them from the primary result.', '',
        '| Parent | U0 minus parent | U1 minus parent | USD increment U1 minus U0 |','|---|---:|---:|---:|']
    lines.append(f'| SOTA | {bp(primary["U0-parent-M"]["mean_annual"])} bp | {bp(primary["U1-parent-M"]["mean_annual"])} bp | {bp(primary["U1-U0-M"]["mean_annual"])} bp |')
    for parent in ('activity','rolling'):
        u0=diagnostics['usd_transfers']['transfer-2-'+parent]['5'];u1=diagnostics['usd_transfers']['transfer-1-'+parent]['5']
        lines.append(f'| {parent} | {bp(u0)} bp | {bp(u1)} bp | {bp(u1-u0)} bp |')
    lines += ['', 'Transfers preserve both recipes and fitted predictions. They are selected, correlated robustness checks on the same 30 months; no independent confirmatory p-value is claimed. The two within-transfer USD differences above are descriptive subtractions, not additional family-controlled tests.', '',
        '| Bootstrap block | USD increment bp/year | Marginal 95% interval | Holm p |','|---|---:|---:|---:|']
    for block in ['6','3','12']:
        r=pairs[block]['U1-U0-M'];lines.append(f'| {block} months | {bp(r["mean_annual"])} | [{bp(r["ci95"][0])}, {bp(r["ci95"][1])}] | {r["holm_p"]:.3f} |')
    lines += ['', 'Latest standardized USD coefficients (next-month relative return, bp per one training-standard-deviation predictor move; explanatory model diagnostics, not current trade advice):', '',
        '| ETF | USD21 coefficient | USD63 coefficient |','|---|---:|---:|']
    last=read_json(ROOT/'U1-M-models.json')['2026-09-01']
    for asset,m in last['models'].items():lines.append(f'| {asset} | {bp(m["coefficients"][3])} | {bp(m["coefficients"][4])} |')
    lines += ['', 'Full historical CNH translation remains unavailable for this new study: the older USD/CNH/CNY legacy input is explicitly uncertified and was excluded. This does not change the user’s accepted unhedged exposure. Broad-dollar prediction and USD/CNH translation remain different questions.', '',
        '## 5. Benchmarks, risk and limits','',
        '| Portfolio | CAGR | Volatility | Sharpe (zero cash return) | Max drawdown |','|---|---:|---:|---:|---:|']
    for key in ['parent-M','risk-M','urth']:
        r=s[key]['5'];lines.append(f'| {label(key)} | {pct(r["cagr"])} | {pct(r["volatility"])} | {r["sharpe_zero_cash"]:.3f} | {pct(r["max_drawdown"])} |')
    lines += ['', 'Fixed calendar stresses (net USD holding-period returns):', '',
        '| Portfolio | 2018 | Feb–Apr 2020 | 2022 |','|---|---:|---:|---:|']
    for key in ['parent-M','A1-M','A7-M','C1-M','C2-M','risk-M','urth']:
        r=stresses[key];lines.append(f'| {key} | {pct(r["2018"])} | {pct(r["covid"])} | {pct(r["2022"])} |')
    lines += ['',
        f'**Inherited risk-contract issue:** the 45% setting constrains the inverse-volatility base before pool reallocation; it is not a final portfolio cap. The unchanged monthly parent reached {pct(s["parent-M"]["5"]["maximum_weight"])} held weight, with {s["parent-M"]["5"]["days_weight_above_45"]} sessions above 45%. The weekly parent reached {pct(s["parent-W"]["5"]["maximum_weight"])}. No cap was weakened for these tests. A final-weight cap requires a separately versioned control and review; these replays must not be described as satisfying a hard 45% portfolio limit.',
        'Parent features deliberately retain their audited split-adjusted price/source-volume basis, so frozen models keep their original meaning. The activity parents are legacy price×volume proxies, not measured ETF flows or audited raw traded-dollar activity. Raw ETF fields were available and checked; no new raw activity feature was introduced.',
        'Daily NAV/cash reconcile to integer fills and fees. Asset PnL sums reconcile to terminal NAV. Full daily exposures, asset contributions, annual costs, holdings counts, stress periods and all comparison signs are retained. Cents rounding, instant settlement, zero cash interest, no spread/market-impact model and whole adjusted units limit economic realism. Fixed-bp costs are scenarios; no capacity claim follows.',
        'Percentile intervals are marginal; centered two-sided bootstrap p-values and Holm correction are reported separately. They need not be exact duals in a skewed finite sample. Circular blocks assume a useful degree of stationarity; no guaranteed coverage or complete accounting of unknown earlier research trials is claimed.', '',
        '## 6. Review decision and next work','',
        '1. Keep the monitored strategies and current monthly horizon blend. Do not combine losing variants or widen the parameter search on this evidence.',
        '2. Retain both membership directions as documented cost/return trade-offs. C1 comes closest to the proposed annual cost allowance, but has lower net return here. A cost-only mandate would need an explicit objective.',
        '3. Retain the USD pair for discussion. Its consistent small increment is encouraging enough to preserve the hypothesis, but falls short of the family-adjusted evidence standard. Any new forward observation starts at a new dated freeze; no prospective performance is claimed in this report.',
        '4. Resolve the final-weight risk contract before promotion work, and define an economic improvement hurdle separately from the 25 bp/year cost allowance. Obtain audited historical USD/CNH if a full historical CNH bridge is needed.',
        '5. No new combined model, learned regime selector, paper promotion or extra parameter grid was launched. Broker/execution settings and monitored definitions remain unchanged.', '',
        '## 7. Reproduction and retained failures','',
        f'Full local artifact root: `{ROOT.resolve()}`. Price batch: `{read_json(ROOT/"data_receipt.json")["batch"]}`. USD batch: `{read_json(ROOT/"usd_registration.json")["usd_batch"]}`.',
        'Files include immutable input/model/source hashes, daily features, complete decisions/rationales, targets, fills, daily NAV/cash, final holdings, fitted USD model coefficients, all cost runs and native receipts. Summary JSON and the registered protocol are next to this report’s charts.',
        'Engineering failures were retained: an interrupted initial input preparation; a native adapter import that pulled unavailable database dependencies into the isolated container; one later native parent-weekly run that stalled and was stopped. The corrected adapter and the identical weekly bundle replay passed parity. None of these retries changed a recipe or count as fresh statistical evidence.',
        'A selection-script error initially omitted U0/U1 despite their now-published prerequisite. The prior empty selection and a correction note are preserved. Applying the original frozen rule selected U1 and U0; no criterion or model parameter was changed. Transfers are descriptive regardless of that correction.',
        'Validation: 48 relevant tests passed, one PostgreSQL-dependent integration test skipped; focused checks cover causal prefixes, exact horizons, mirrored gates, membership counters/floors, holiday clocks, USD vintage identity, training embargo, heterogeneous coefficients, sizing/fees and multiple-testing calculations.', '',
        'Commands (use a fresh input/output root for a new immutable study; do not overwrite this run):', '', '```powershell',
        '.venv/Scripts/python.exe scripts/prepare_momentum_research.py --root <fresh-root>',
        '.venv/Scripts/python.exe scripts/run_momentum_research.py --root <fresh-root> --stage features --workers 16',
        '.venv/Scripts/python.exe scripts/run_momentum_research.py --root <fresh-root> --stage python --workers 16',
        '.venv/Scripts/python.exe scripts/collect_usd_index.py',
        '.venv/Scripts/python.exe scripts/publish_usd_index.py --root <fresh-usd-batch>',
        '.venv/Scripts/python.exe scripts/run_usd_momentum_research.py --root <fresh-root>',
        '.venv/Scripts/python.exe scripts/analyze_momentum_research.py --root <fresh-root>',
        '.venv/Scripts/python.exe scripts/run_momentum_research.py --root <fresh-root> --stage transfer --workers 16',
        '.venv/Scripts/python.exe scripts/run_usd_momentum_transfers.py --root <fresh-root>',
        '.venv/Scripts/python.exe scripts/run_momentum_research.py --root <fresh-root> --stage native --workers 3',
        '.venv/Scripts/python.exe scripts/analyze_momentum_research.py --root <fresh-root>', '```','',
        'Data sources: [Fed H.10 history and release policy](https://www.federalreserve.gov/releases/h10/about.htm), [Fed methodology/rebasing changes](https://www.federalreserve.gov/releases/h10/h10_technical_qa.htm), [ALFRED vintage history](https://alfred.stlouisfed.org/series?seid=DTWEXBGS), [vintage-date definition](https://fred.stlouisfed.org/docs/api/fred/series_vintagedates.html). Earlier paper sources and firsthand notes remain in the [reference library](references/README.md).']
    Path('research/momentum-results-2026-10-01.md').write_text('\n'.join(lines)+'\n',encoding='utf8')
    write_json(OUT/'verification.json',dict(created_at=datetime.now(UTC).isoformat(),python_replays=102,portfolios=34,native_passed=len(native),
        native=native,failed_native_attempts=failures,baseline=read_json(ROOT/'baseline_parity.json'),transfer_parents=read_json(ROOT/'transfer_parent_target_parity.json'),
        protocol_sha256=sha256(ROOT/'protocol.json'),analysis_code={str(f):sha256(f) for f in [Path(__file__),Path('scripts/analyze_momentum_research.py'),Path('src/systematic_trading/research/momentum_analysis.py')]},
        results_sha256=sha256(ROOT/'statistics.json'),paired_results_sha256=sha256(ROOT/'paired_results.json'),promotion_eligible=False))
    print('Report written; verified',len(native),'native checks and',len(s)*3,'Python replays.')


if __name__=='__main__':build()
