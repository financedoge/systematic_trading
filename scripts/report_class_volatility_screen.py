"""Publish the screen's compact review artifacts from verified results only."""
import argparse
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from run_class_volatility_screen import digest, read, verify, write


LABELS = dict(pooled_raw='Pooled / raw', pooled_risk='Pooled / risk-normalized',
              class_raw='Class-first / raw', class_risk='Class-first / risk-normalized')
COLORS = dict(pooled_raw='#64748b', pooled_risk='#2563eb', class_raw='#b45309', class_risk='#0f766e')


def publish(root, destination):
    verify(root, 'input_manifest.json')
    verify(root, 'result_manifest.json')
    p, a = read(root/'protocol.json'), read(root/'analysis.json')
    acceptance = read(root/'acceptance.json')
    assert acceptance['analysis_sha256'] == digest(root/'analysis.json')
    assert digest(destination/'protocol.json') == digest(root/'protocol.json')
    results = a['results']
    keys = [arm+'-'+policy for arm in p['arms'] for policy in p['policies']]
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False})
    fig = plt.figure(figsize=(14, 8.7), facecolor='white', layout='constrained')
    grid = fig.add_gridspec(2, 2, width_ratios=[1.25, 1])
    ax = fig.add_subplot(grid[:, 0])
    values = [results[k]['gate']['annual_cost_bps'] for k in keys]
    ax.barh(np.arange(16), values, color=[COLORS[results[k]['arm']] for k in keys], height=.7)
    ax.set_yticks(np.arange(16), [LABELS[results[k]['arm']]+' | '+results[k]['policy'] for k in keys], fontsize=9)
    ax.invert_yaxis()
    ax.axvline(44, color='#b91c1c', linestyle='--', label='44 bp gate')
    ax.set_xlim(0, max(values)*1.18)
    for i, value in enumerate(values):
        ax.text(value+4, i, f'{value:.1f}', va='center', fontsize=9,
                bbox=dict(facecolor='white', edgecolor='none', pad=.2))
    ax.set_xlabel('Annual implied cost (basis points at 5 bp per security side)')
    ax.set_title('14 of 16 mappings exceed the cost ceiling', loc='left', weight='bold', pad=16)
    ax.legend(frameon=False, loc='lower right')
    ic = fig.add_subplot(grid[0, 1])
    for i, arm in enumerate(p['arms']):
        item = results[arm+'-monthly']
        value = item['gate']['candidate_ic']
        low, high = item['calibration_ic_intervals']['6']['family_95_bonferroni']
        ic.errorbar(value, i, xerr=[[value-low], [high-value]], fmt='o', color=COLORS[arm], capsize=4)
    ic.axvline(0, color='#94a3b8', linewidth=1)
    ic.set_yticks(range(4), [LABELS[arm] for arm in p['arms']], fontsize=9)
    ic.invert_yaxis()
    ic.set_xlabel('Monthly mapping rank IC, 2021–2024')
    ic.set_title('Information remains unestablished', loc='left', weight='bold', pad=16)
    ic.text(.02, -.25, '95% family intervals; 6-month stationary blocks.\nAll four intervals include zero.',
            transform=ic.transAxes, fontsize=9, color='#475569')
    exposure = fig.add_subplot(grid[1, 1])
    bill = [results[arm+'-monthly']['windows']['later']['mean_adopted_bill_weight'] for arm in p['arms']]
    gross = [results[arm+'-monthly']['windows']['later']['mean_adopted_gross'] for arm in p['arms']]
    other = np.array(gross)-bill
    cash = 1-np.array(gross)
    exposure.barh(range(4), other*100, label='Other ETFs', color='#334155')
    exposure.barh(range(4), np.array(bill)*100, left=other*100, label='BIL', color='#38bdf8')
    exposure.barh(range(4), cash*100, left=np.array(gross)*100, label='Cash', color='#e2e8f0')
    exposure.set_yticks(range(4), [LABELS[arm] for arm in p['arms']], fontsize=9)
    exposure.invert_yaxis()
    exposure.set_xlim(0, 100)
    exposure.set_xlabel('Average adopted target (%) — 2025 through October 12, 2026')
    exposure.set_title('Low cost comes with defensive exposure', loc='left', weight='bold', pad=16)
    exposure.legend(ncol=3, frameon=False, bbox_to_anchor=(.5, -.2), loc='upper center', fontsize=9)
    fig.suptitle('P4.16d · Full-pool class / volatility screen: 0 of 16 pass', fontsize=17, weight='bold')
    fig.savefig(destination/'screen.png', dpi=160)
    plt.close(fig)
    compact = dict(protocol_sha256=a['protocol_sha256'], input_manifest_sha256=a['input_manifest_sha256'],
        analysis_sha256=digest(root/'analysis.json'), published_batch=a['published_batch'],
        candidates=a['candidates'], supported=a['supported'], exclusions=a['exclusions'],
        daily_sessions=a['daily_sessions'], monthly_sessions=a['monthly_sessions'],
        results={k: dict(arm=r['arm'], policy=r['policy'], gate=r['gate'],
            windows={w: {f: v for f, v in values.items() if f not in ('observations', 'constituents', 'by_symbol')}
                     for w, values in r['windows'].items()},
            calibration_ic_intervals=r['calibration_ic_intervals']) for k, r in results.items()},
        replay_candidates=a['replay_candidates'], acceptance=acceptance,
        limitations=p['limitations'])
    write(destination/'summary.json', compact)
    write(destination/'attribution.json', {k: {w: r['windows'][w]['constituents'] for w in ('calibration', 'later')}
                                         for k, r in results.items()})
    write(destination/'receipt.json', dict(acceptance, protocol_sha256=a['protocol_sha256'],
        result_manifest_sha256=digest(root/'result_manifest.json'),
        artifacts={name: digest(destination/name) for name in ('protocol.json', 'summary.json', 'attribution.json', 'screen.png')},
        report_generator_sha256=digest(Path(__file__))))
    rows = []
    for arm in p['arms']:
        r = results[arm+'-monthly']
        cal, later = r['windows']['calibration'], r['windows']['later']
        rows.append(f"| {LABELS[arm]} | {cal['annual_cost_bps']:.2f} | {r['gate']['candidate_ic']:+.5f} | {r['gate']['ic_margin']:.2f}× | {later['ic']:+.5f} | Reject |")
    grid_rows = []
    for arm in p['arms']:
        cells = [f"{results[arm+'-'+n]['gate']['annual_cost_bps']:.2f}" for n in p['policies']]
        grid_rows.append('| '+LABELS[arm]+' | '+' | '.join(cells)+' |')
    exposure_rows = []
    for arm in p['arms']:
        w = results[arm+'-monthly']['windows']['later']
        exposure_rows.append(f"| {LABELS[arm]} | {100*w['mean_adopted_gross']:.2f}% | {100*w['mean_adopted_bill_weight']:.2f}% | {100*(1-w['mean_adopted_gross']):.2f}% | {w['mean_selected']:.2f} |")
    attributes = []
    for s in sorted(results['pooled_raw-monthly']['windows']['calibration']['constituents']):
        cells = [f"{100*results[arm+'-monthly']['windows']['calibration']['constituents'][s]['mean_adopted_weight']:.2f}%" for arm in p['arms']]
        group = results['pooled_raw-monthly']['windows']['calibration']['constituents'][s]['group']
        attributes.append('| '+s+' | '+group+' | '+' | '.join(cells)+' |')
    markdown = """# Class and volatility screen — October 16, 2026

**All 16 mappings fail the frozen admission gate. No portfolio replay is warranted for this family.**
Volatility normalization reduces monthly target-change costs below the 44 bp
ceiling, but its information margins are only **1.91× pooled** and **0.55×
class-first**, below the required 3×. Class-first selection alone remains too
expensive. The dynamic thresholds are also too expensive. These findings close
this declared construction screen; they do not reject class allocation, ETF
expansion or dynamic rebalancing in general.

![Cost gate, information intervals and later defensive exposure](../research/class-volatility-screen-20261016-v1/screen.png)

## Registered question and controls

This is the next separate P4.16d design after the unchanged expanded-FR25 rejection.
The four comparisons isolate **pooled versus class-first selection** and **raw
126-session momentum versus momentum divided by 63-session annualized volatility**.
This transparent price-only family omits FR25's financial, XGBoost, activity and
USD overlays. It is not an amendment to FR25 or evidence of outperformance over SOTA.
The original 14-ETF FR25 and URTH remain required replay benchmarks if a new
qualified family is later tested. The original control's existing gate receipt is
retained, but its latent-score IC is not directly comparable to this target-weight IC.

Pooled selection chooses up to six names. Class-first selection chooses up to
three classes and two funds per class, using the actual selected members' mean
score to rank classes. Within each budget, weights are inverse-volatility;
unfilled slots and any excess above the 45% security cap remain cash. The maximum
gross is 98%. Monthly controls accompany fixed target-distance thresholds of
0.10, 0.40 and 0.80. All thresholds retain monthly adoption and compare latest
theoretical versus last adopted targets, including cash, without held-weight inputs.

There are 24 declared primary classes, 18 of them singletons in the supported
50-fund pool (16 in the full 52-candidate list). Every
fund has one class. Prior raw-dollar activity selects duplicate representatives.
Explicit broad-parent/child conflicts prevent selected overlaps such as SPY and
its sector funds, EFA and its country funds, and DBC and commodity sub-funds. The
remaining class scores are recomputed after conflicts remove members. These are
declared modelling controls, not a verified historical holdings-overlap census.
Semiconductors and energy producers remain equities; silver receives one precious
metals vote; Hong Kong remains separate from mainland China. Pure energy-futures
and chemicals exposure remain gaps.

## Inputs and causal scope

The complete accepted first wave contains 52 candidates. The same 50 supported
common-window histories reproduce exactly from the published October 12 batch
`0c3238db078c5d28201f8d8ba57e5687a793d80c3b04817d2c2d61c5f1f1b14d`.
BWX retains its listing-date hold. CPER retains the unsupported August 23, 2018
raw-volume observation. Neither is silently repaired or replaced. All original
publication audit/bar hashes and inherited manifests are verified before freezing.

Inputs start June 19, 2018. The study generates **1,450 daily target dates per
arm**, January 4, 2021–October 12, 2026, with **70 monthly anchors**. Signals and
liquidity use only observations before the proposed next-open date. Adjusted
prices supply returns; audited raw prices and volume supply liquidity. No macro,
FX, provider archive or online-price input is used. The old cutoff is intentional
for comparability and says nothing about current application freshness.

The cohort contains current surviving funds. Historical membership, mandate
and classification validity are not reconstructed; the October 13 reference
inventory is a retrospective classification assumption. Auditing revised prices
does not establish historical publication availability. These are inspected
historical diagnostics, not untouched validation or promotion evidence.

## Gate and chronological information

Calibration ends December 31, 2024. The information measure is the monthly
Spearman correlation of **final target weights, including zero allocations**,
with the following 21-session adjusted open-to-open returns across the admissible
pool. Thus it tests the composed ranking/sizing mapping, rather than claiming an
untraded raw signal's IC. Labels must finish inside the window. There are 47 valid
calibration observations and 21 later observations. Constant cross-sections never
receive the programme's default IC.

| Monthly mapping | Implied annual cost, bp | Calibration IC | IC / breakeven | 2025+ IC | Verdict |
| --- | ---: | ---: | ---: | ---: | --- |
"""+'\n'.join(rows)+"""

The cost measure sums security-target changes and initial establishment over a
fixed interval. Cash affects the adoption trigger but is not charged as a second
traded security. These are **implied mapping costs**, not realized turnover, fees,
NAV, Sharpe or drawdown. Prior calibration of the legacy mapping does not establish
turnover accuracy for these new dynamic policies.

Every policy adopts at the same monthly anchors, so its monthly information
observations are identical within an arm; timing changes the cost side of this
screen. That identity is not a claim that the policies have equal portfolio returns.
The later period and per-year diagnostics cannot rescue a calibration failure.
In particular, the normalized pooled/class mappings turn negative in the later
period, while the raw mappings improve; this is temporal instability, not a
license to switch recipes after seeing the result.

Joint stationary-bootstrap diagnostics use 20,000 draws at each of 3, 6 and 12
monthly blocks, shared across all 16 mappings. Individual and Bonferroni family
intervals are saved. Every calibration family interval spans zero. These intervals
are descriptive and conditional on this inspected cohort, not formal discovery evidence.

## Dynamic comparison

All cells below are implied annual bp at the unchanged 5 bp per traded security
side; the ceiling is 44 bp. Each dynamic rule also adopts monthly.

| Mapping | Monthly | Threshold 0.10 | Threshold 0.40 | Threshold 0.80 |
| --- | ---: | ---: | ---: | ---: |
"""+'\n'.join(grid_rows)+"""

The least expensive dynamic mapping still costs 78.84 bp annually. No threshold
survives to portfolio replay. Actual traded turnover, net Sharpe, episode drawdown,
5/10/20 bp costs, next-open versus one-additional-session delay, matched exposure,
SOTA/URTH comparisons and native parity remain required for a future surviving
mapping. They were **not run or inferred** for these gate failures.

## Why lower cost is insufficient

| Monthly mapping, later period | Mean invested | Mean BIL | Mean cash | Mean names |
| --- | ---: | ---: | ---: | ---: |
"""+'\n'.join(exposure_rows)+"""

The normalized pooled rule averages **45% BIL and 41.64% cash** in 2025–2026:
only **13.36%** is allocated to other ETFs. Dividing positive carry by very small
bill volatility elevates BIL's rank; inverse-volatility sizing reaches its cap
and leaves the excess in cash. The class-first rule limits bills to one of six
slots, but singleton classes also leave cash. Cheap trading alone therefore does
not establish better opportunity selection. Even after scaling its calibration
cost to 98% gross as a diagnostic, the class-normalized mapping costs 53.39 bp.
That scaling is not a new gate or a replay.

## Full supported-pool attribution

Average **adopted target** weights during calibration are below, including zero
weights. These are not held weights or P&L. All 16 policies' constituent weights,
selection counts and annual security-target turnover, in calibration and later
windows, are in [attribution.json](../research/class-volatility-screen-20261016-v1/attribution.json).
Per-constituent target turnover reconciles to each mapping's total.

| Fund | Primary class | Pooled raw | Pooled normalized | Class raw | Class normalized |
| --- | --- | ---: | ---: | ---: | ---: |
"""+'\n'.join(attributes)+"""

## Verification and decision

57 focused tests passed, including causal windows, missing/zero-volatility inputs,
singleton momentum gates, cash slots/caps, parent-child exclusions, duplicate
class refusal, future-label boundaries, missing-IC rejection and frozen-input
tampering. Ruff passed. Independent arithmetic acceptance checked **5,800 daily
target vectors, 179,940 member scores, 16 adoption policies, 4,485 adoptions,
128 window turnover totals and 2,144 monthly IC observations**. Target attribution
reconciles, labels remain inside each window, and all 16 gate verdicts reproduce.
Decimal summation can differ in the last context digit; independent event checks
use 1e-24 distance tolerance and verify no event is within 1e-20 of its threshold.

The protocol and results are frozen in
`var/research/class-volatility-screen-20261016-v1/`. The
[protocol](../research/class-volatility-screen-20261016-v1/protocol.json),
[compact summary](../research/class-volatility-screen-20261016-v1/summary.json)
and [hash receipt](../research/class-volatility-screen-20261016-v1/receipt.json)
are retained alongside the chart and attribution.

**Decision:** reject these 16 mappings at the pre-test and stop this item for
review. Do not retune their thresholds, horizons, class counts or volatility rule
on the inspected sample. The next research decision is whether to register a
cash-relative, peer-comparable momentum hypothesis that separates bill carry
from risky-asset selection, with an explicit horizon and prospective observation
period. That is a new hypothesis, not an automatic rescue of this family.
Historical membership/mandate evidence and P6.15 resource work remain open.
No tracked-strategy, allocation, paper policy or live-routing setting changed.
"""
    Path('docs/class-volatility-screen-findings.md').write_text(markdown, encoding='utf-8')
    print('Published compact summary, complete attribution, chart and findings')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('var/research/class-volatility-screen-20261016-v1'))
    parser.add_argument('--destination', type=Path, default=Path('research/class-volatility-screen-20261016-v1'))
    args = parser.parse_args()
    publish(args.root, args.destination)
