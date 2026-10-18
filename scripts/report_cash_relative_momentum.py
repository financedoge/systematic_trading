"""Build the cash-relative study review from verified frozen artifacts."""
import argparse
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from run_class_volatility_screen import digest, read, verify, write

LABELS = {
    'pooled_remove_bill_risk': 'Pooled / remove BIL',
    'pooled_cash_relative_risk': 'Pooled / cash-relative',
    'class_remove_bill_risk': 'Class-first / remove BIL',
    'class_cash_relative_risk': 'Class-first / cash-relative',
}


def publish(root, dest):
    for name in ('input_manifest.json', 'result_manifest.json', 'diagnostic_manifest.json'):
        verify(root, name)
    p, a, d = read(root/'protocol.json'), read(root/'analysis.json'), read(root/'diagnostics.json')
    acceptance = read(root/'acceptance.json')
    assert acceptance['analysis_sha256'] == digest(root/'analysis.json')
    assert acceptance['diagnostics_sha256'] == digest(root/'diagnostics.json')
    tests = Path('var/research/cash-relative-momentum-tests.xml')
    suite = ET.parse(tests).getroot().find('testsuite')
    assert suite is not None and suite.attrib['failures'] == suite.attrib['errors'] == '0'
    passed = int(suite.attrib['tests'])-int(suite.attrib['skipped'])
    arms, results = p['arms'], a['results']
    diagnostic_summary, paired = {}, {}
    for window, horizons in d['diagnostics'].items():
        diagnostic_summary[window] = {}
        for horizon, arm_rows in horizons.items():
            diagnostic_summary[window][horizon] = {}
            for arm, rows in arm_rows.items():
                means = {}
                for field in ('mapping_ic', 'signal_ic', 'static_excess_contribution'):
                    values = [row[field] for row in rows if row[field] is not None]
                    means[field] = dict(count=len(values), mean=float(np.mean(values)) if values else None)
                groups = {}
                for group in p['classes']:
                    values = [row['class_conditioning'][group]['ic'] for row in rows
                              if row['class_conditioning'][group]['ic'] is not None]
                    groups[group] = dict(valid_months=len(values), status='sufficient_descriptive_coverage' if len(values) >= 12 else 'insufficient',
                        mean_ic=float(np.mean(values)) if len(values) >= 12 else None)
                diagnostic_summary[window][horizon][arm] = dict(means=means, class_conditioning=groups)
        paired[window] = {key: dict(observations=len(rows), mean_bps=10000*float(np.mean([r['value'] for r in rows])),
            intervals={block: {kind: ([10000*x for x in value] if isinstance(value, list) else value)
                        for kind, value in interval.items()}
                       for block, interval in d['paired_intervals'][window][key].items()})
            for key, rows in d['paired_static_excess_contribution'][window].items()}
    compact_results = {key: dict(arm=r['arm'], policy=r['policy'], gate=r['gate'],
        windows={w: {k: v for k, v in values.items() if k not in ('observations', 'constituents', 'by_symbol')}
                 for w, values in r['windows'].items()}, calibration_ic_intervals=r['calibration_ic_intervals'])
                       for key, r in results.items()}
    write(dest/'summary.json', dict(protocol_sha256=digest(root/'protocol.json'), analysis_sha256=digest(root/'analysis.json'),
        results=compact_results, diagnostics=diagnostic_summary, paired_static_excess_contribution=paired,
        acceptance=acceptance, prospective=p['registration']['prospective'], limitations=p['limitations']))
    write(dest/'attribution.json', {key: {w: r['windows'][w]['constituents'] for w in ('calibration', 'later')}
                                  for key, r in results.items()})
    shutil.copyfile(root/'protocol.json', dest/'protocol.json')
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
                         'axes.spines.right': False})
    fig, axes = plt.subplots(1, 2, figsize=(13, 5), layout='constrained')
    costs = [results[arm+'-monthly']['gate']['annual_cost_bps'] for arm in arms]
    colors = ['#94a3b8', '#2563eb', '#94a3b8', '#0f766e']
    axes[0].barh(range(4), costs, color=colors, height=.6)
    axes[0].set_yticks(range(4), [LABELS[arm] for arm in arms])
    axes[0].invert_yaxis()
    axes[0].axvline(44, color='#b91c1c', linestyle='--', label='44 bp ceiling')
    axes[0].set_xlim(0, 65)
    for i, cost in enumerate(costs):
        axes[0].text(cost+.7, i, f'{cost:.2f}', va='center')
    axes[0].set_xlabel('Monthly mappings: implied annual cost, bp (red line = 44 bp ceiling)')
    axes[0].set_title('Every mapping still fails the cost gate', weight='bold', loc='left')
    labels = []
    for i, (window, shape) in enumerate([(w, s) for w in ('calibration', 'later') for s in ('pooled', 'class')]):
        stat = paired[window][shape+'-21']
        mean = stat['mean_bps']
        low, high = stat['intervals']['6']['family_95_bonferroni']
        axes[1].errorbar(mean, i, xerr=[[mean-low], [high-mean]], fmt='o', capsize=4,
                         color='#2563eb' if shape == 'pooled' else '#0f766e')
        labels.append(('2021–24' if window == 'calibration' else '2025+')+' / '+shape)
    axes[1].axvline(0, color='#94a3b8')
    axes[1].set_yticks(range(4), labels)
    axes[1].invert_yaxis()
    axes[1].set_xlabel('Candidate − removal-only: 21-session static excess payoff, bp')
    axes[1].set_title('Later improvement is not net portfolio evidence', weight='bold', loc='left')
    fig.suptitle('Cash-relative momentum · 0 of 16 mappings admitted', fontsize=17, weight='bold')
    fig.supxlabel('Payoff intervals: 95% Bonferroni family bounds, 6-month blocks. Static, before costs; no portfolio replay.', fontsize=9)
    fig.savefig(dest/'screen.png', dpi=160)
    plt.close(fig)

    monthly_rows, grid_rows, contribution_rows = [], [], []
    for arm in arms:
        item = results[arm+'-monthly']
        g = item['gate']
        monthly_rows.append(f"| {LABELS[arm]} | {g['annual_cost_bps']:.2f} | {g['candidate_ic']:+.5f} | {g['ic_margin']:.2f}x | {item['windows']['later']['ic']:+.5f} |")
        grid_rows.append('| '+LABELS[arm]+' | '+' | '.join(f"{results[arm+'-'+n]['gate']['annual_cost_bps']:.2f}" for n in p['policies'])+' |')
    for window in ('calibration', 'later'):
        for shape in ('pooled', 'class'):
            stat = paired[window][shape+'-21']
            low, high = stat['intervals']['6']['family_95_bonferroni']
            contribution_rows.append(f"| {window} | {shape} | {stat['observations']} | {stat['mean_bps']:+.2f} | [{low:+.2f}, {high:+.2f}] |")
    decay_rows = []
    for horizon in ('1', '5', '10', '21'):
        values = [paired[window][shape+'-'+horizon]['mean_bps'] for window in ('calibration', 'later') for shape in ('pooled', 'class')]
        decay_rows.append('| '+horizon+' | '+' | '.join(f'{v:+.2f}' for v in values)+' |')
    group_rows = []
    for group in p['classes']:
        cells = []
        for window in ('calibration', 'later'):
            for shape in ('pooled', 'class'):
                stat = diagnostic_summary[window]['21'][shape+'_cash_relative_risk']['class_conditioning'][group]
                cells.append(str(stat['valid_months'])+(' / '+f"{stat['mean_ic']:+.4f}" if stat['mean_ic'] is not None else ' / insufficient'))
        group_rows.append('| '+group+' | '+' | '.join(cells)+' |')
    text = """# Cash-relative momentum — October 17, 2026

**All 16 mappings fail the unchanged cost gate.** The class-first cash-relative
monthly rule clears the heuristic information margin at **3.59x**, but its implied
annual cost is **45.66 bp**, above the frozen **44 bp** ceiling. It is a near miss,
not an admitted strategy. No portfolio replay, monitoring or trading change follows.

![Cost admission and paired static excess payoff](../research/cash-relative-momentum-20261017-v1/screen.png)

## Hypothesis and matched controls

The previous normalized rule gave BIL a high score because positive carry was
divided by very low volatility. This follow-up asks whether comparing each risky
ETF's momentum with bill carry adds information **beyond simply removing BIL**.
The user requested continuation after that result. The hypothesis is informed by
inspected historical evidence; it is not an untouched out-of-sample discovery.

- Control: exclude BIL from position selection; retain `126-session return / 63-session volatility`.
- Candidate: exclude BIL; rank `(ETF 126-session return − BIL 126-session return) / ETF 63-session volatility`.
- Both retain the positive **raw** momentum gate. The candidate also requires
  positive excess momentum. A negative ETF return cannot qualify merely because
  BIL performed worse. Unsupported reference history stops the calculation.
- Run each with pooled six-name and class-first three-class/two-name selection,
  using monthly and 0.10/0.40/0.80 target-change adoption. All sizing, class/overlap
  rules, liquidity, duplicate handling, 45% cap and unfilled-slot cash are inherited.
- All 50 supported histories remain inputs: 49 can compete for positions and BIL
  supplies the reference. BIL receives zero target by design. Unused budgets stay
  literal cash; BIL's return is not assumed to be paid on that cash.

The 52-candidate first wave, BWX/CPER exclusions and published price batch are
unchanged. The actual published histories were re-read and hash-checked before
freezing; they reproduce the parent pool exactly. Inputs end October 12, 2026;
signals use only prior sessions. Adjusted prices supply returns, audited raw
prices/volume supply liquidity. The two normalized parent strategies also
reproduce all **1,450 daily targets each** exactly under the inherited code.

## Primary screen

The 2021–2024 calibration gate is unchanged: 44 bp annual implied cost and a 3x
candidate IC/breakeven margin. The label remains 21-session adjusted open-to-open
return over the same full admissible pool, including zero-weight BIL. No switch
to a more favorable latent-score IC or reduced cost threshold is permitted.

| Monthly mapping | Implied annual cost, bp | Calibration mapping IC | IC margin | 2025+ mapping IC |
| --- | ---: | ---: | ---: | ---: |
"""+'\n'.join(monthly_rows)+"""

The cash-relative class rule's margin is a useful improvement over its removal-only
control, but its cost is **1.66 bp above the ceiling**, and all calibration mapping
IC family intervals still include zero. Clearing the heuristic margin is not
statistical confirmation. Removing BIL alone also fails. The prior low-cost bill
concentration was therefore not a free source of affordable risky-asset selection.

| Mapping | Monthly | Threshold 0.10 | Threshold 0.40 | Threshold 0.80 |
| --- | ---: | ---: | ---: | ---: |
"""+'\n'.join(grid_rows)+"""

Every dynamic variant fails; the cheapest is 108.46 bp annually. All policies
still adopt at monthly anchors, so monthly IC is shared within each arm. These
are security-target-change costs, including initial establishment, not measured
fill turnover or realized fees. No conclusions about net Sharpe, drawdown or
execution-delay performance are inferred from these rejected screens.

## Incremental payoff and horizon diagnostics

Subtracting the same future BIL return from every ETF return leaves cross-sectional
ranks unchanged. The implementation verifies that identity. Excess-return rank IC
is therefore not counted as a second discovery. Selection-score IC is reported
separately and never substitutes for the final-weight mapping gate.

The independently registered payoff diagnostic is the static sum of target
weights times ETF forward returns **in excess of BIL**, candidate minus the matched
removal-only control. It is a BIL-financed, zero-cost forward contribution, not
account PnL, actual idle-cash return or a path-dependent portfolio backtest.

| Window | Construction | Monthly observations | Mean 21-session incremental payoff, bp | 95% family interval, 6-month blocks |
| --- | --- | ---: | ---: | --- |
"""+'\n'.join(contribution_rows)+"""

The pooled later-period contrast is positive under the registered family interval,
but it is already-inspected, before-cost evidence. Its candidate also averages
95.45% invested versus 83.33% for the removal-only control; exposure differs by
12.12 percentage points. The interval cannot establish exposure-matched alpha.
The class-first contrast's interval includes zero in both periods. Neither later
diagnostic can rescue the calibration gate failure.

All four horizons were declared before results; 21 sessions remains primary.
The entries below are per-horizon static payoff differences, **not annualized**.
All eight contrasts and 3/6/12-month-block intervals are retained in the summary.

| Horizon, sessions | Calibration pooled, bp | Calibration class, bp | Later pooled, bp | Later class, bp |
| --- | ---: | ---: | ---: | ---: |
"""+'\n'.join(decay_rows)+"""

The early versus later horizon pattern is descriptive. No best holding period,
exit threshold or delayed-entry rule is selected from it.

## Comparable-class coverage

The inherited primary classes are conditioning groups, not proof of homogeneous
economic payoffs. A valid within-class observation needs at least three admissible
risky names and nonconstant weights/returns; a class summary needs twelve valid
months. Most classes cannot support it. For the cash-relative class-first rule,
only **two of 23 non-bill classes** have sufficient calibration coverage and only
**one** has sufficient later coverage. No broad peer-relative alpha claim follows.

Entries below are valid months / mean mapping IC; insufficient means unavailable,
not zero information. This is the primary 21-session horizon for the two candidates.

| Class | Calibration pooled | Calibration class-first | Later pooled | Later class-first |
| --- | --- | --- | --- | --- |
"""+'\n'.join(group_rows)+f"""

## Verification, evidence and next boundary

**{passed} focused tests passed**, including cash-reference failure, subtraction
before risk division, preserved absolute gates, matched-control equivalence,
common-return rank invariance, label boundaries, static payoff arithmetic and the
prospective calendar. Ruff passes. Independent checks reproduce **5,800 target
vectors, 165,674 member scores, 16 adoption policies, 5,698 adoptions, 128 turnover
windows, 1,108 forward rows, 26,592 class rows and 554 paired payoff observations**.
All target turnover attribution reconciles. The frozen parent helper is unchanged;
both original normalized controls reproduce exactly. No app calculation source or
operational process was changed.

The [registration](../research/cash-relative-momentum-20261017-v1/registration.json)
was frozen before results; the [full protocol](../research/cash-relative-momentum-20261017-v1/protocol.json),
[compact summary and all diagnostic intervals](../research/cash-relative-momentum-20261017-v1/summary.json),
[all-policy constituent attribution](../research/cash-relative-momentum-20261017-v1/attribution.json)
and [hash receipt](../research/cash-relative-momentum-20261017-v1/receipt.json) are retained.
Large immutable inputs, targets, event ledgers and diagnostics live in
`var/research/cash-relative-momentum-20261017-v1/`.

The registered prospective design reserves 126 application-calendar decision
sessions from **October 19, 2026 through April 20, 2027**, with final 21-session
labels due **May 19, 2027**, subject to actual session/publication availability.
It is **inactive**, because no mapping passed. It contains no future evidence,
does not constitute a powered alpha test by itself and creates no agent schedule,
automation, app monitoring or execution authority. Any later eligible strategy
must be frozen and calculated through the app's services before observation.

**Decision:** reject this declared family at the gate and review the near miss.
The binding issue for class-first cash-relative selection is cost, with weak
statistical and peer-coverage support still unresolved. The next useful decision
is whether to register an explicit turnover/cost mechanism with the signal fixed;
do not lower the ceiling, pick a favorable horizon or retune this grid after seeing
the result. Actual turnover, net Sharpe, return/drawdown guards, 5/10/20 bp costs,
execution delays, exposure-matched controls, original FR25/URTH benchmarks and
native parity remain mandatory before any surviving future mapping qualifies.

Current-survivor membership, historical mandates/classifications and historical
publication vintages remain uncertified. No provider archive, new online price,
FX or macro input was used. No strategy, funding, broker or live-routing setting
changed. The earlier expanded-FR25 and class/volatility rejections remain intact.
"""
    findings = Path('docs/cash-relative-momentum-findings.md')
    findings.write_text(text, encoding='utf-8')
    write(dest/'receipt.json', dict(acceptance, registration_sha256=digest(dest/'registration.json'),
        protocol_sha256=digest(dest/'protocol.json'), diagnostic_manifest_sha256=digest(root/'diagnostic_manifest.json'),
        artifacts={name: digest(dest/name) for name in ('registration.json', 'protocol.json', 'summary.json', 'attribution.json', 'screen.png')},
        findings_sha256=digest(findings), test_receipt_sha256=digest(tests), passed_tests=passed,
        report_generator_sha256=digest(Path(__file__))))
    print('Cash-relative findings, chart, attribution and receipts published')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path('var/research/cash-relative-momentum-20261017-v1'))
    parser.add_argument('--destination', type=Path, default=Path('research/cash-relative-momentum-20261017-v1'))
    args = parser.parse_args()
    publish(args.root, args.destination)
