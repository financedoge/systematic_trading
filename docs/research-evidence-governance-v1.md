# P4.20 — Research evidence and decay review v1

Effective November 1, 2026. **Governance item complete; stop for discussion.**
The operator retained Alpha54/the completed six-signal experiment as research
evidence. This policy replaces P4.20's proposed universal minimum half-life and
sub-period IC admission rule. It does not revise old experiments, select a new
winner, change monitoring membership, designate SOTA or authorize trading.

## What the gate means

An evidence review must answer three different questions. Keeping them separate
allows an informative negative experiment to be complete without promoting it.

| Question | Required output | What it does not establish |
| --- | --- | --- |
| Can we inspect and interpret the evidence? | Versioned protocol/recipe, verified published inputs, sample-use declaration, complete net comparisons, decay/stability assessment and dated weakest-ETF inspections | Statistical truth, profitability or untouched OOS status merely because the files exist |
| What does the frozen experiment support? | Original study-specific net-performance verdict, uncertainty, costs/delay and chronological/asset dependence | A universal best strategy or a new winner selected on the evaluation period |
| May the application or operator change its state? | Separate app-owned recipe/calculation validation, and the existing promotion, paper, risk, capital, approval and rollback requirements | An evidence-validator result is never monitoring, promotion, allocation or execution permission |

The versioned policy is [research-evidence-policy-v1.json](../config/research-evidence-policy-v1.json).
The [validator](../src/systematic_trading/research/evidence_review.py) and
[CLI](../scripts/review_research_evidence.py) validate a hash-bound dossier.
They are a read-only governance workflow, not a newly installed runtime interlock.
Existing lifecycle, allocation, approval, reconciliation and broker checks remain
the application's authority. A new signal/recipe review must attach this assessment
before the operator considers registration or promotion; an old monitored recipe
is not silently unregistered because its historical dossier predates this policy.

## Declare how each period may be used

Before calculating results, fix the hypothesis, supported universe, price/activity
basis, candidate/trial family, horizons and label availability, mapping, training
selection, primary cost/delay case, fixed and dynamic timing, net guardrails and
uncertainty method. Record the actual freeze time: a protocol written today for
historical data must not be backdated to the historical boundary.

Use a disjoint calibration interval to select the policy. Keep subsequent data
for evaluating that fixed choice. A predeclared test can fail to support the
claim; this does not entitle us to switch to the best later-performing variant
and call its later record untouched. A new choice, threshold, ranking, feature,
allocation or stopped-search decision informed by that evaluation must disclose
the reuse. The old evaluation becomes development evidence for the new decision.
Do not hide prior unsuccessful trials or assume that 24 current variants are the
entire lifetime search family when earlier related studies exist.

The dossier distinguishes **retrospective development**, **untouched holdout** and
**prospective** claims. Unknown or previously inspected evaluation data cannot
support an untouched claim. A prospective claim additionally needs an earlier
recipe freeze, later captured observations and point-in-time input/universe
evidence. Chronologically causal calculations on revised prices are useful
research; an audit alone does not certify historical publication availability.
Train/test labels and embargo/purge choices must match the longest forward label
and information overlap. Record purging or a justified boundary treatment rather
than assuming a calendar split removes leakage.

These rules respond to adaptive holdout reuse and selection bias. Adaptive reuse
can overfit a holdout, and investment backtests can remain overfit despite a
simple holdout split. Those findings motivate honest sample labels and trial
accounting; they do not prove that any particular FR25 or momentum result is luck.
[Dwork et al., holdout reuse](https://arxiv.org/abs/1506.02629),
[pinned local v2 and provenance](../research/references/supplemental/README.md),
[Bailey et al., backtest overfitting](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf).
No specific paper's test statistic is adopted as a universal project hurdle.

## Decay evidence without a proxy veto

Require the economic role of each incremental signal, its direction and mapping,
decision cutoff, earliest executable fill, forward labels, eligible pool,
missingness/dispersion/ties, horizon curve and sub-period stability. State whether
IC is cross-sectional ranking, market timing or an unsuitable measure for the
signal's purpose. A sizing/protection feature may need marginal net portfolio
effects rather than a raw-score ranking test. A `not_applicable` IC/half-life
assessment needs an explicit rationale and suitable alternative evidence.

Half-life means the lifetime of a specified statistic under a specified model.
It is not automatically the profitable holding period. Report the fitting model,
usable observations, overlap-aware uncertainty, fit adequacy and sensitivity to
the supported horizon grid. Separate these states:

| State | Meaning |
| --- | --- |
| Estimated | A finite positive estimate, its assumptions and uncertainty are supported |
| Right censored | The declared observation window cannot locate the decay boundary; state the measured bound and supporting evidence |
| Unidentifiable | The shape or signal semantics do not support the proposed lifetime model |
| Insufficient | Coverage or uncertainty work is missing; record the concrete gap |
| Not applicable | Explain why a lifetime/IC statistic is unsuitable and link the alternative stability assessment |

Null never means infinite lifetime, healthy alpha or failed profitability. The
existing P4.13 `half_life_sessions` can be null for several reasons and its app
coverage explicitly omits some forecasts/overlays. A base-momentum diagnostic
cannot certify FR25's financial forecast or an Alpha101 tilt. Preserve those
historical numerical reports; use the explicit v1 states for new review dossiers.

No universal minimum half-life, positive-IC requirement, IC/breakeven margin or
annual trading-cost ceiling controls admission to research replay. Short-lived
signals may justify frequent trading after costs; a long-lived signal may have
no useful portfolio effect. Require a fixed-interval control and predeclared
dynamic alternatives. Target-change triggers compare latest theoretical and last
adopted weights, including cash; holdings drift is separate trading maintenance.

Net replay remains the evidence for profitability: study-specific net Sharpe,
return/drawdown guardrails, actual turnover and fees, cost/execution-delay stress,
chronological stability, cash, asset buy-and-hold and simple matched controls.
Use the full supported pool, and analyze constituent dependence. FR25 is an
empirical incumbent, with its own vintage, universe, exposure and model limits.
Do not introduce new numerical guardrails after seeing the result.

## Worked review: retain Alpha54 without changing the verdict

[Dossier](../research/research-evidence-governance-20261101-v1/alpha54-dossier.json) ·
[Assessment](../research/research-evidence-governance-20261101-v1/alpha54-assessment-v2.json) ·
[Original illustrated study](../research/alpha101-net-20261031-v1/index.html).

Alpha54/monthly was selected by calibration Sharpe. The later winner did not
replace it. Both periods were previously inspected development history. The
operator's concern that FR25/126-session momentum may benefit from luck or
particular regimes is retained as a hypothesis; no probability of luck has been
estimated by this governance item, and no frozen numerical verdict changed.

| Alpha54/monthly, 5 bp and next open | Calibration | Later |
| --- | ---: | ---: |
| Dates | 2021-01-04–2024-12-31 | 2025-01-02–2026-10-30 |
| Cumulative net return | 33.37% | 26.90% |
| Annualized return | 7.49% | 13.97% |
| Net Sharpe | 0.679 | 1.569 |

The intervals have different lengths. Lower cumulative later return therefore
does not establish deterioration; annualized return and Sharpe are higher later.
Neither higher nor lower later performance alone proves robustness or luck.
Calibration Sharpe is also selection-sensitive: being below FR25's 0.721 is an
observed comparison, not a proof of statistical inferiority.

Existing Alpha54 mean IC at1/5/10/21 sessions is
−0.000252/0.011574/0.006817/0.008922 in calibration and
0.021001/0.005240/0.007366/0.004960 later. These are non-monotone curves with
different endpoint-supported samples. They do not establish one exponential
half-life. The dossier records it as **unidentifiable**, and separately identifies
missing dedicated decay-curve uncertainty/annual incremental stability before a
new monitored-recipe proposal. Portfolio bootstrap uncertainty does not supply
IC-curve uncertainty. No new fitting or numerical study was run here.

Assessment: **research evidence reviewable; retain for research**. The original
net verdict remains **guarded advantage not established**. A missing diagnostic
study does not prevent closing a completed retrospective experiment. Any future
new monitored recipe still needs explicit coverage resolution and a complete
application-owned calculator/report. No operational authority is granted.

The previous round's weakest risky contributions remain
[EWY in calibration](../research/alpha101-net-20261031-v1/weakest-calibration-EWY.png)
and [XLC later](../research/alpha101-net-20261031-v1/weakest-later-XLC.png).
Their exact dates, price/volume, theoretical/adopted/held states, fills, absence of
stops and FIFO outcomes remain in the original report. This governance item adds
no new strategy results requiring a replacement weakest-ETF selection.

## Review workflow and machine contract

The [JSON schema](../research/research-evidence-governance-20261101-v1/dossier.schema.json)
specifies required declarations. The policy enumerates evidence roles; one
comprehensive artifact may cover several roles. Every reference is workspace
relative and SHA-256-bound. Missing/changed files, absent roles, contradictory
sample claims, invalid dates and malformed estimates fail the review. Unknown
fields cannot smuggle an authorization into the dossier.

```powershell
.\.venv\Scripts\python.exe scripts/review_research_evidence.py `
  research/research-evidence-governance-20261101-v1/alpha54-dossier.json `
  --output research/research-evidence-governance-20261101-v1/alpha54-assessment-v2.json
```

The command is deterministic and read only except its named assessment file.
An identical rerun is idempotent; a changed assessment needs a new output version.
It verifies referenced bytes and declared consistency, not the truth of every
annotation or the adequacy of a statistical design. Human review remains required.
It does not calculate trading signals or schedule recurring work.

For a new monitored recipe, attach app strategy-definition/calculation evidence
and resolve incremental-signal coverage gaps. For promotion review, additionally
attach paper evidence, risk/capital limits, rollback and operator approval, with
prospective and point-in-time limitations resolved. Even a complete assessment
returns all authority flags false. Existing independent controls make any actual
state change. Passing this checklist is never a new route around those controls.

## Closure and storage

The operator has closed cash-relative and Alpha101 as retained research evidence.
Their [cash-relative closure](../research/cash-relative-net-20261031-v1/closure-20261101.json)
and [Alpha101 closure](../research/alpha101-net-20261031-v1/closure-20261101.json)
preserve the original artifact-manifest hashes and identify retained compact
findings plus disposable generated folders. The original reports/manifests remain
unchanged. Top-level working protocol/summary copies satisfy the existing guarded
retirement planner; these are small prerequisites, not full backups.

Thirteen generated folders are classified, including path arrays, detailed
scenario ledgers and duplicate native bundles/source copies. Classification does
not delete them. Normal stopped-startup housekeeping must recheck active/promotion,
current/rollback, canonical and operational dependencies, locks, path containment
and file identity, then emit append-only retirement outcomes. Exact reproduction
of intentionally retired exploratory outputs is not promised; a later rerun on
a new audited batch is new evidence. Reports, inspection charts and concise
validation summaries remain available.

## Completion and next discussion

P4.20's versioned policy, executable evidence review, regression tests, worked
Alpha54 assessment and closure classifications are complete. No new market data,
backtest, strategy registration, app refresh or broker action was requested here.
P4.21 remains blocked on constituent/holdings and historical-membership coverage.
The next unblocked research item is the previously withheld **expanded-pool FR25
net replay**, followed by the separate class/volatility construction replay.
Stop for operator discussion before starting either. A future prospective design
for retained Alpha54 or cash-relative would be a new separately declared item.
