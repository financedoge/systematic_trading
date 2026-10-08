# Leading economic ETF response experiment

This finite experiment continues the recorder-first work in
[Economic Data](economic-vintage-recorder.md). It does not change a monitored
recipe or authorize orders. The user asked for ex-ante predictions, nonlinear
effects, both beneficiaries and losers, and leading indicators rather than GDP.

## Frozen question and inputs

Test whether seven leading US indicators improve the defensive ETF strategy's
Sharpe and Calmar through per-ETF models. Test payrolls, manufacturing output and
headline/core CPI as a separate context addition. The Philadelphia surveys are
regional forward expectations, not national PMI. No licensed PMI or dated
consensus forecasts are assumed available.

The price reader uses the published audited catalog, with verified hashes and
dividend/split-adjusted prices for returns. The economic reader verifies the
published eleven-series vintage panel, batch
`25088ea74e961b25e43a998035743d1483fe9b2e800d5253b1da3d9073f72460`.
Every decision uses the archive before the completed prior trading close, with
an extra calendar-day vintage lag. Historical availability is an explicit
ALFRED daily-archive assumption. First capture by this app remains October 2026.
Provider auditing does not certify historical dissemination or every input class.

Recorders already provide the inputs for this experiment. Future national PMI,
consensus, credit/lending, country and sector indicators need their own recorder
and availability contract before use. GDP, new instruments and single stocks
are outside this batch.

## Models and allocation

- Per ETF: expanding original-vintage monthly rows, starting in 2016; at least
  36 complete return labels. A label runs between consecutive scheduled
  rebalance opens and enters training only once its endpoint is before the
  prior-close cutoff. Missing economic months do not stretch label horizons.
- Tree: depth two, minimum twelve observations per leaf. Ridge: alpha one and
  training-only standardization. Paired models use identical rows and labels.
- Leading models use seven leading features. Matched-leading and combined
  models use the identical leading-plus-context-ready rows and decisions; only
  their feature columns differ. Combined has thirteen features. Missing or
  stale data cause abstention to the parent, never imputation or vintage repair.
- P3 is the defensive/cash parent with a final 45% per-ETF target cap; removed
  capital stays cash. F0 and original F3 remain unchanged historical references.
- Economic multipliers are 1.10 for a forecast increment above 25 bp with a
  positive absolute forecast, 0.90 below minus 25 bp, otherwise one. The increment
  is relative to that ETF's own training-sample mean return. Normalize within
  P3's positive positions while preserving its exact gross budget and 45% caps.
  No ineligible ETF is added; cash is not spent to manufacture beneficiaries.
- Tree/ridge conditional responses compare training-feature upper/lower
  quartiles at a fixed query. These are descriptive model associations, not
  identified causal shock effects.

## Finite comparisons and evidence

Eleven primary arms: F0, F3, P3, six economic models/controls, risk parity and
URTH. Fifty-one total replays cover 5/10/20 bp costs, one extra execution session,
and causal 2016-onward context. Evaluation restarts each arm with USD 1m in
January 2021, through October 6, 2026. Previously inspected history is explicitly
retrospective; no untouched holdout claim is made.

Nine paired contrasts are fixed before outcomes. Joint calendar-month bootstrap
uses 20,000 resamples and 3/6/12-month block lengths. Mean-return tests receive
Holm correction; ratio intervals are marginal. Retention screens require both
Sharpe and Calmar improvement against the declared parent/linear/sample controls,
cost tolerance, drawdown tolerance and delayed-execution comparisons. Passing
is only a reason to gather more evidence, never automatic promotion.

Use sixteen worker processes on this host, with one math thread per process.
Native LEAN accounting checks run on memory-bounded lanes sharing the sixteen
CPU budget. All eleven primary native ledgers must match their Python oracle.
Unchanged full-period F0/F3 economics must also reproduce the frozen parent.

Frozen source, inputs, models, decisions, fills, held weights and receipts live
under `var/research/economic-response-20261007-v2/`. Protocol SHA-256:
`bd405774bb76310d0b8ddb9e2926435740a7088ba87f1dd80a224d09ed11165c`.
The prior v1 attempt is retained: a strict sum check found a `1e-28` Decimal
rounding difference before portfolio replays. Canonical 24-decimal weights plus
an exact residual repaired arithmetic only; no model/data/threshold search.
All 51 replays, eleven primary native checks, 30 inference jobs and report
generation completed. Twenty-one focused tests passed. Unchanged full F0/F3
fills, daily NAV and final holdings reproduce the parent exactly.

## Completed result

The [findings](../research/economic-response-2026-10-07/findings.html) and
[complete assessment](../research/economic-response-2026-10-07/assessment.html)
include all eleven shared-format reports and complete decision flows.

| Evaluation arm | CAGR | Sharpe | Calmar | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: |
| Original F3 | 10.740% | 1.0765 | 0.9185 | -11.693% |
| Capped control P3 | 10.778% | 1.0811 | 0.9220 | -11.690% |
| Leading tree LT | 10.972% | 1.0841 | 0.9298 | -11.800% |
| Leading ridge LR | 10.995% | 1.0896 | 0.9702 | -11.333% |
| Matched leading ridge MR | 10.938% | 1.0941 | 0.9651 | -11.333% |
| Combined tree CT | 10.793% | 1.0813 | 0.9487 | -11.377% |
| Combined ridge CR | 11.000% | 1.1027 | 0.9740 | -11.293% |

LR and CR pass the finite retention screen; trees fail their linear-model
comparisons, and CT also fails delayed Sharpe. No paired mean-return comparison
passes 5% Holm under 3/6/12-month blocks. CR versus P3 has a positive marginal
Sharpe interval but a Calmar interval crossing zero; these are not familywise
ratio discoveries. On full 2016-onward context, CR Calmar is 0.5977 versus P3
0.6059, and LR lowers both ratios. Retain linear models for further research,
not promotion or new monitored membership.

Leading models are ready on 66/70 evaluation decisions; combined and matched
models on 58/70, abstaining November 2025–October 2026. CR's context-only
increment over MR is about 6bp CAGR and 0.0085 Sharpe. Leading ridge has slightly
lower forecast MAE than the mean-return baseline; combined ridge has higher
MAE despite a modest portfolio improvement. Record these negative diagnostics.

The findings supplement was produced after analysis and records its publisher
and frozen-report hashes; it does not modify the frozen v2 source or evidence.
Shared detail reports include a December 31 cash anchor, producing slightly
different calendar CAGR (CR 10.98% versus study 11.00%) with identical economics.
Inherited protocol caveats concerning BIL refer to the parent study; BIL is not
an economic experiment asset. The inherited cap caveat applies to unchanged
F0/F3; P3 and macro arms have the additional final 45% cap.
Next: release-aware public yield/credit/lending recorders and prospective issuer
holdings/shares/NAV coverage before broader country/sector experiments. No
further tuning on this batch and no assertion that US factors identify each
country's own economic sensitivities.
