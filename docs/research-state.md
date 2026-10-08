# Research State

## 2026-10-07 - Context ridge monitored; financial-condition combinations completed

On the user's explicit instruction, `research_economic_context_ridge_v1`
(Leading + payroll/inflation context · linear model) is now Monitored, generation
1. The exact economic-response v2 CR recipe is app-owned and remains frozen until
the ETF-universe revisit. Its full report is current through October 6: all 130
historical model decisions, 795 fills, 2,705 daily values and final positions
exactly match the prior study. Nine native monitored/control runs passed. Accepted
calculation revision:
`3ac2ba32ec1413383b849c589e7ccd7d593955e4adee3c7626025a57e169cc38`.
All five monitored strategies are current and allocation-ready. Monitoring did
not alter SOTA, capital, approvals or orders; allocation control revision remains
3 and the user's pending F3 handover is unchanged.

Latest economic features are incomplete, so CR correctly abstains to capped F3
and shows a yellow notice. Future decisions from October 8 require actual app
capture before the cutoff; archive restoration cannot backdate late observations.
During the first app calculation, the required October 5 vintages finished
publishing. The publication guard rejected the older calculation; the normal
retry completed on the final input subset. Both immutable attempts are retained.

Added Treasury slopes T10Y3M/T10Y2Y, Chicago Fed NFCICREDIT and SLOOS
DRTSCILM/DRTSCIS to the app recorder and Economic Data. Published all 2,112 planned
snapshots, preserving the original 1,441 entries exactly. Batch:
`9fb6784447635430354fa0547e8787f37d0e7c69d60a62053a65b0279ff8b8b4`.
The Treasury histories omit the initial January 2, 2006 holiday; it is disclosed
as unsupported, never filled. Internal gaps remain audit failures. NFCI is a
credit composite, not a corporate bond spread; corporate-spread storage rights,
national PMI and pre-release consensus remain access gaps.

The user additionally authorized combinations of the new economic inputs per
ETF. Frozen financial v1 tests eight financial features alone and all 21 original
plus financial features, each with separate per-ETF ridge and depth-two trees.
An original-context ridge matches the augmented training rows and availability.
All tilts apply to capped F3 directly and preserve its gross, cash and positive
membership. Prices remain on audited batch
`a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2`;
vintages and labels obey the declared ex-ante contract with historical archive
availability limitations. No parameter or ETF search was performed.

January 2021–October 6, 2026, 5bp costs, USD, zero-interest cash:

| Recipe | CAGR | Sharpe | Calmar | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: |
| Frozen context ridge (CR) | 11.000% | 1.1027 | 0.9740 | -11.293% |
| Financial-only ridge (FR) | 11.102% | 1.1057 | 0.9798 | -11.332% |
| Financial-only tree (FT) | 11.066% | 1.0992 | 0.9534 | -11.606% |
| Augmented ridge (AR) | 11.040% | 1.1029 | 0.9753 | -11.320% |
| Augmented tree (AT) | 10.901% | 1.0877 | 0.9527 | -11.442% |

FR passes the fixed retention screen but its six-month-block Sharpe and Calmar
difference intervals versus CR include zero. No mean contrast passes 5% Holm
with three- or six-month blocks; FT versus P3 passes only the twelve-month-block
sensitivity (p=0.0204), while FT fails its linear and delay hurdles. AR fails
delayed Calmar. Both trees fail replacement screens. Full-history FR Sharpe
1.0619/Calmar 0.5845 trail CR 1.0703/0.5977, with drawdown 17.13% versus 16.83%.
All model combinations have worse prediction MAE than the ETF-specific training
mean. Retain FR as research evidence, no additional monitoring or promotion.

Financial features are ready on 130/130 historical decisions and models on
70/70 evaluation decisions. Augmented/matched models remain ready 58/70; matched
ridge reproduces CR exactly. FR changes 42/70 allocations: it increases SPY in
29 months, EWJ in 23 and DBC in 18, while also reducing assets conditionally.
These are model associations, not identified causal shock sensitivities.

Completed 51 replays, eleven native validations and 27 inference jobs on all 16
logical CPUs, with three memory-bounded native lanes. F0/F3/P3/CR full-period
controls reproduce exactly. 121 distinct focused monitoring, recorder, model,
reporting and integration tests passed; Ruff/whitespace and browser checks passed.
Evidence: `var/research/economic-monitoring-20261007/` and
`var/research/economic-financial-20261007-v1/`. Protocol SHA-256:
`7744d4585a435d4a5781d84eab4de0f7757e75e7198e00de9f8db83d1cd7d4fd`.
[Findings](../research/economic-financial-2026-10-07/findings.html) and
[complete assessment / reports](../research/economic-financial-2026-10-07/assessment.html).

Next: admit an expanded ETF universe through issuer identity and audited price
coverage; build prospective issuer holdings, shares outstanding and NAV records,
then a sector activity/growth/valuation/positioning pilot. Energy balances and
futures positioning require separate source and release-history qualification.
Revisit economic combinations once that universe exists; single stocks remain
out of scope. The independent legacy `lean-history` archive import is still
retrying a connection timeout; accepted monitored reports and economic
publications are complete. This is a separate archive-ingestion follow-up.

## 2026-10-07 - Completed economic asset-response experiment

Completed the broader eleven-series experiment after fixing allocation
preparation and deferred approval. Seven leading indicators and separate
payroll/output/headline/core inflation context feed per-ETF shallow trees and
ridge models. Original daily economic vintages, completed training labels,
training-only transforms and matched sample/availability controls enforce the
declared ex-ante contract. All inputs use published audited price batch
`a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2`
and economic batch
`25088ea74e961b25e43a998035743d1483fe9b2e800d5253b1da3d9073f72460`.
Historical dissemination limitations remain; app first capture is October 2026.

Primary evaluation: January 2021–October 6, 2026, USD, 5bp costs, zero-interest
cash. P3 (F3 with a 45% final target cap) gives CAGR 10.778%, Sharpe 1.0811,
Calmar 0.9220 and maximum drawdown 11.690%. Leading ridge gives
10.995% / 1.0896 / 0.9702 / 11.333%; combined ridge gives
11.000% / 1.1027 / 0.9740 / 11.293%. Both pass the finite cost/delay retention
screen. Trees fail to beat their paired linear models; combined tree also fails
delayed Sharpe. Original F3 remains reported at 10.740% / 1.0765 / 0.9185.

No paired mean-return contrast passes 5% Holm for any predeclared block length.
Combined ridge versus P3 has a positive marginal Sharpe interval but a Calmar
interval crossing zero. Combined ridge versus sample-matched leading ridge
adds only about 6bp CAGR and 0.0085 Sharpe. Full 2016-onward context lowers
combined ridge Calmar (0.5977 versus P3 0.6059); leading ridge lowers both ratios.
Forecast MAE worsens with context despite its small portfolio gain. Preserve
these limitations; retain linear candidates for further evidence, no promotion.

Leading features support 66/70 evaluation decisions; combined/matched support
58/70 and abstain November 2025–October 2026. No missing CPI observation was
filled from a later vintage. Models learn different signed associations and
increase as well as decrease ETF weights, but cannot add a beneficiary excluded
by parent eligibility or spend parent cash. Country-specific fundamentals,
national PMI, consensus surprises and expanded eligibility remain untested.

All 51 price/cost/delay replays, eleven primary native checks and 30 inference
jobs completed using the 16-CPU budget. Original full F0/F3 fills, NAV and final
positions reproduce exactly. Twenty-one focused tests passed. The retained v1
attempt stopped before portfolio replays on a 1e-28 Decimal sum difference;
v2 fixes arithmetic precision only, with no model or threshold change.

[Findings](../research/economic-response-2026-10-07/findings.html),
[complete assessment and eleven reports](../research/economic-response-2026-10-07/assessment.html),
[contract](economic-response-research.md); frozen receipts under
`var/research/economic-response-20261007-v2/`. Protocol SHA-256
`bd405774bb76310d0b8ddb9e2926435740a7088ba87f1dd80a224d09ed11165c`.
No new source, monitored recipe, funding or execution authority was introduced.
The user's separately saved F3 allocation remains pending for October 7 close,
control revision 3. Next: public yield/credit/lending vintage recorders, then
prospective issuer holdings/shares/NAV and a bounded sector-fundamental pilot.
Do not tune this batch further or use manually maintained monitoring cards.

## 2026-10-07 - Leading economic panel expansion

User broadened the economic work before the three-series portfolio experiment
was frozen or run: prioritize leading indicators, exclude GDP, use ex-ante
nonlinear predictions and allow different assets to benefit or suffer. Expanded
the app recorder from three to eleven series with 1,441 verified captures (131
per series). Preserved all original 393 captures and their hashes through an
explicit additive registry migration.

Seven leading candidates: claims, permits, manufacturing hours, temporary help,
core capital-goods orders, and Philadelphia Fed future orders/employment. Four
separate context series: payrolls, manufacturing output, headline CPI and core
CPI. Regional surveys are not national PMI; a leading business-cycle measure is
not automatically predictive of asset prices. User confirmed no existing data
subscription. Continue public-source work; national PMI and pre-release consensus
remain explicit access/availability gaps, alongside upcoming credit-condition,
country and sector recorders.

Published catalog `25088ea74e961b25e43a998035743d1483fe9b2e800d5253b1da3d9073f72460`.
Readiness across 130 frozen decisions: leading group 126, context group 118,
combined group 118. Preserve unavailable readings. The conservative complete
13-month CPI window excludes ten 2026 decisions per CPI series because an
interior observation is missing; do not fill it from later history. Compare
context additions against leading models with matched training/availability
controls so differences in usable samples are not mistaken for feature value.

[Readiness report](../research/economic-leading-data-2026-10-07/assessment.html).
Frozen source, features and acceptance:
`var/research/economic-leading-panel-20261007-v2/`. The v1 attempt is retained as
incomplete after an audit adapter passed extra provenance fields to the reader;
the v2 repair did not change any source or feature formula. One transient source
404 recovered after the declared retry interval. 68 tests passed, one optional
skip; 22 real API history checks, source hashes, browser coverage and unchanged
four allocation-ready monitored strategies passed. Analytics errors cleared;
tracked revision and control revision 2 remain unchanged.

Next: implement the broader, bounded leading-only versus leading-plus-context
asset-specific tree/linear experiment on the pinned panel, with original-vintage
features, completed training labels, all-core replay, costs/delays and full shared
reports. The three-series overlay/model/study files remain an unfinished draft,
not a backtest result or registered strategy. No economic performance improvement,
promotion or funding change is claimed.

## 2026-10-07 — Economic vintage panel and revision sensitivity

The app now records ICSA (jobless claims), PERMIT (housing permits) and IPMAN
(manufacturing output), with 393 verified captures / 131 vintages per series in
**Market Data → Economic Data**. Catalog batch
`bd5668b74622858a88bdc0619ce02cc27a6f26b3d13570b55e61fea1da3c0682`
is pinned in `var/research/economic-panel-20261007-v1/input_pin.json`.

Against the frozen 130 monthly strategy decisions, five readings exceed freshness
limits (claims November 2025; permits December 2025–February 2026; manufacturing
December 2025). Preserve these as unavailable. There are 385 usable same-vintage
features; later revisions change the weakening flag in 13/129 claims, 4/127 permits
and 34/129 manufacturing measurements. Latest revised histories would therefore
change 51 flags in this fixed diagnostic. This is not a stock-return forecasting
result. No economic overlay was backtested or promoted.

Report: [economic data readiness](../research/economic-data-2026-10-07/assessment.html).
Contract: [economic vintage recorder](economic-vintage-recorder.md). The app owns
daily capture and catch-up; archive end-of-day availability and actual first capture
remain separate, with an explicit archive assumption required for historical use.
61 tests passed / one optional skip, source/API/browser acceptance passed; existing
SOTA, F3 monitoring and paper capital remain unchanged. Next freeze the small US-only
overlay, stale-data behavior and exposure/cost controls before outcome inspection.
Continue issuer holdings/shares/NAV and country/industry recorders separately.

## Treasury-bill recorder and F4 parking — 2026-10-07

Completed recorder-first BIL qualification and one predeclared F4 ablation.
Application-owned research ETF acquisition now captures issuer identity and
provider price/action evidence, audits complete coverage and revisions, verifies
ClickHouse rows/documents and commits the shared Market Data catalog. Failed
captures remain quarantined and retry after five minutes. Subsequent active-ETF
refreshes preserve the newly admitted series and its pinned storage batch.
Initial BIL coverage is 4,870 sessions, May 30, 2007–October 6, 2026; issuer
inception is May 25, 2007 and the unsupported initial days remain missing.
Published batch: `a95bf6a48a79c338b63774a87f0b4bea21a97120ddfa5d987cb5f243ae44fbe2`.
The price/action audit is single-provider reconstruction, not certification of
historical dissemination, holdings, broker eligibility or interest terms.

Frozen `bill-parking-v1` retains F1's final risky ETF weights, adds BIL only below
four positive-momentum qualifiers, caps its target at 45% and reserves at least
2% cash. BIL exits on normal monthly breadth; no ranking/model change, cap search
or F3/BIL combination. Seven primary portfolios, 25 cost/delay replays and all
seven native accounting checks passed. F0/F1/F3 decisions, fills, daily NAV and
positions exactly reproduce all 12 matched prior cost/delay controls. Used 16
Python workers and three native lanes sharing 16 CPUs.

| Full 2016–October 6, 2026 / 5bp | CAGR | Sharpe, zero reference rate | Calmar | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: |
| F0 current SOTA | 9.779% | 0.9783 | 0.4425 | 22.097% |
| F1 qualifying ETFs + cash | 9.702% | 1.0339 | 0.5715 | 16.976% |
| F4 F1 + capped BIL | 9.841% | 1.0474 | 0.5856 | 16.804% |
| F3 qualifying defensive ETFs + cash | 9.931% | 1.0581 | 0.6048 | 16.420% |

F4 adds 13.9bp annualized return versus F1 at 5bp trading costs, 9.6bp at 20bp,
and 13.9bp with one extra execution session. It passes the fixed economic screen
but remains weaker than F3 overall. Eighteen decisions form only three episodes;
the largest benefit is in 2022–23, while early 2016 slightly loses after costs.
Holm-adjusted paired mean-return p-values versus F1 are 0.093/0.251/0.396 for
3/6/12-month blocks. Twelve-month ratio intervals include zero. Retain parking as
a modest cash-management component for future research, not an established alpha
improvement or replacement for F3. Cash earns zero; distributions enter through
adjusted prices; no broker cash-yield or untouched out-of-sample claim.

Assessment and seven full reports: `research/bill-parking-2026-10-07/assessment.html`.
Frozen inputs/economics/inference: `var/research/bill-parking-20261007-v1/`.
Protocol SHA-256: `4ac477e45428bf49704b28b5fcde306b9d8003fe0a510dacc544e8ac4af0f0a8`.
Relevant regression suite: 98 passed / one optional skip. Current SOTA, monitored
membership and capital remain unchanged. Next: macro release vintages and issuer
holdings/shares/NAV recorders, then a finite country/energy/sector fundamental
pilot. ETFs remain the trading boundary; no more unregistered ranking search.

## XGBoost ranking, exposure attribution and final target caps — 2026-10-07

Completed a second finite batch after the user asked to use XGBoost predictions
for top-6/8/10 selection instead of only a weight tilt. Protocol
`fallback-ranking-construction-v1` was frozen before the new outcomes: 16 primary
portfolios, 66 cost/delay/context replays and 15 registered contrasts. The model
target remains next-month adjusted USD return relative to the universe mean;
training, features and monthly model schedule were held fixed. All ranking arms
use the F3 defensive/cash fallback, the same positive 252-session eligibility gate
and later overlays. Price/volume rankings at each N and no-XGBoost-tilt controls
separate basket size, ranking and tilt removal. Top N is a maximum, never a
forced investment in rejected assets.

Common evaluation window: January 4, 2021–October 6, 2026, starting with USD 1m,
5bp trading costs, zero cash interest/reference rate. This window was already
inspected; no untouched holdout claim is made.

| Integration | CAGR | Sharpe | Calmar | Max drawdown |
| --- | ---: | ---: | ---: | ---: |
| F3 price/volume top 6 + XGBoost tilt | 10.74% | 1.076 | 0.919 | 11.69% |
| Forecast ranking top 6, no XGBoost tilt | 9.88% | 1.014 | 0.794 | 12.43% |
| Forecast ranking top 8, no XGBoost tilt | 7.69% | 0.888 | 0.626 | 12.28% |
| Forecast ranking top 10, no XGBoost tilt | 5.96% | 0.781 | 0.484 | 12.31% |
| Price/volume top 8 + XGBoost tilt | 7.46% | 0.864 | 0.616 | 12.10% |
| Price/volume top 10 + XGBoost tilt | 6.10% | 0.798 | 0.503 | 12.12% |

Forecast top 6 increases turnover from 5.87× to 7.93× annually and remains weaker
at 10/20bp and with an extra execution-session delay. Removing the XGBoost tilt
alone gives top-6 Sharpe 1.067; prediction-driven selection itself supplies no
improvement here. Average eligible-universe rank IC is 0.110 for XGBoost versus
0.233 for price/volume over 57 complete eligible months, a descriptive diagnostic.
All 15 paired mean-return tests fail the 5% Holm-adjusted threshold across
3/6/12-month block sensitivities. The six-month Sharpe-difference interval for
forecast top 6 minus F3 is [-0.189, +0.060]. Preserve the negative result;
do not replace the monitored recipe or widen its basket on this evidence.

The exposure control calibrated on 2016–2020 freezes its scale at 0.9151117.
It does not reproduce F3 protection (Sharpe 0.861, drawdown 20.40%). Matching
F3's monthly invested budget while keeping F0 composition produces almost the
same result as F3 (Sharpe 1.077 versus 1.076). Exposure timing explains much more
than defensive selection in this window, which contains only one fallback episode.
Neither result establishes future timing skill.

A separately tested 45% final target cap sends excess weight to cash. Full
2016–October 2026 F3 Sharpe changes only from 1.058 to 1.061 and CAGR from 9.931%
to 9.949%, while maximum held weight falls from 53.65% to 46.64%. Target weights
are capped at 45%; holding drift and execution gaps remain possible. Retain as a
risk-control candidate, not a demonstrated alpha improvement or an approved
portfolio change. No cap/ranking winner combination was searched.

All 130 original monthly targets reproduced exactly; full-history F0/F3 NAV,
fills and final positions match the prior study. All 16 primary native parity
checks passed. Used 16 Python workers (18.77 seconds) and three memory-bounded
native lanes sharing 16 CPUs (127.21 seconds). 39 focused tests passed. Inputs
remain the pinned audited adjusted-price batch
`9d05d12524221f562ed949926e78ba00bf126e427ee9de704ccdb0578d79655e`, with verified
model/USD artifacts and explicit historical availability/volume/FX limitations.
No new source, recorder, monitored membership, SOTA, allocation or execution
authority change. The app's previous archive-ingestion warning has cleared.

Findings and all 16 standard reports:
[research assessment](../research/ranking-construction-2026-10-07/assessment.html).
Frozen evidence: `var/research/ranking-construction-20261007-v1/`.
Next: recorder-first Treasury-bill parking and macro/issuer/industry inputs from
the roadmap. A new momentum target or ranking-specific training objective needs
a separately frozen experiment; it was not tested here. Prospective F3 tracking
and operator promotion remain separate.

## Defensive-cash monitoring and strategy lifecycle — 2026-10-07

At the operator's request, **Qualifying defensive ETFs + cash** (`research_fallback_f3_v1`)
is now the fourth monitored strategy, with a complete application-calculated shared
report through October 6. Monitoring is separate from SOTA promotion, capital and
execution authority. Existing rolling XGBoost + activity + USD remains the SOTA
and 100% paper allocation at control revision 2; no pending change was added.

The new USD replay uses pinned published adjusted histories and verified model/USD
inputs, avoiding uncertified historical currency conversion. All 130 decisions,
2,705 daily values, 795 fills and final positions match the frozen F3 study exactly.
Four USD native runs passed execution/accounting parity. Standard report Sharpe is
1.0581, Calmar 0.6042 and maximum drawdown 16.42%; its calendar/anchor annualization
is 9.9207%, explaining the small rounding difference from the study's 9.93%.
These remain retrospective results from only three fallback episodes. Prospective
monitoring starts October 8, with no prospective observations yet. CNH portfolio
comparison uses only a separate exact-date verified FX bridge; raw USD NAV cannot
be substituted for CNH. No new data source was required.

Archive now pauses ongoing app calculations and retains the complete report.
Restore replays missed signals, scheduled trades, cash, holdings and daily NAV;
allocation remains blocked until the current membership generation is fully
published. Current SOTA, funded or pending-allocation strategies must be released
from those roles before archiving. Historical artifacts without an executable
recipe remain viewable but cannot be restored by merely relabelling them.

Publication: `19bcca6e344472ec1187f95635513e7c11de43f486636f21dc6ee937a72ef099`;
acceptance evidence: `var/research/strategy-lifecycle-20261007-*` and the publication's
`usd/study_comparison.json`. Next: operator promotion/allocation if desired, followed
by the already recorded prospective, matched-exposure and recorder-first F4 work.

## Fallback implementation and first results — 2026-10-07

Completed the authorized F0–F3 batch on the active rolling XGBoost/activity/USD
baseline, with 16-core independent calculations, 19 Python replays and four
native execution-parity checks. All 130 baseline monthly target schedules
reproduce exactly. Versioned cash/defensive fallback parameters and downstream
membership/gross-budget protection now use the shared backtest and paper target
pipeline; existing definitions retain the neutral policy.

At 5 bp costs and zero cash interest, USD Sharpe improves from 0.978 to
1.034/1.058/1.058 and Calmar from 0.443 to 0.572/0.604/0.605. Maximum drawdown
falls from 22.10% to 16.98%/16.42%/16.42%; CAGR is 9.78% versus
9.70%/9.92%/9.93%. Only three fallback episodes drive these results, with gains
concentrated in 2022–23 and missed gains in the earlier episodes. Paired return
uncertainty includes zero after multiple-comparison adjustment. Retain the
active strategy; preserve challengers for further validation, with no monitoring,
capital or execution-authority change.

Full interpretation, constraints, source hashes, costs, delayed execution,
episode attribution and next steps: [fallback results](../research/fallback-results-2026-10-07.md).
Immutable artifacts: `var/research/fallback-20261007-v1/`.

F4 remains unrun: neither BIL nor SGOV has admitted published history. The next
new-data task must implement the recorder and make its audited publication
inspectable in Market Data before features or backtests consume it. Existing
audited ETF and dollar-index sources sufficed for F0–F3. Exposure-matched controls,
final portfolio caps, cash remuneration and prospective validation remain open.

## ETF research expansion proposal — 2026-10-07

The user set an ETF-only boundary for the ongoing strategy-improvement work,
with country leading indicators, better momentum/crash handling, broader asset
exposures and sector-specific activity, growth, valuation, sentiment and
positioning information as research directions. Constituent financial statements
may inform ETF signals; single-stock trading remains outside this workstream.

The [research and data roadmap](etf-research-expansion-roadmap.md) proposes staged
universe/signal comparisons against the active October 4 rolling XGBoost +
activity + USD strategy. Priorities are a separately versioned final-weight risk
contract, dated ETF holdings/issuance, macro release vintages and macro/energy
pilots, followed by validated sector financials and selected narrow industries.
Existing SEC parsing and macro score hooks do not establish an audited sector
panel. The proposal includes recorder/source priorities, availability controls,
matched benchmarks and app-owned calculations. Experiment recipes, paid sources
and acceptance tolerances remain proposals; no experiments, recorder deployment,
new tracking, promotion or allocation changes were performed in this session.

October 7 follow-up: the user requested explicit near-total cash and alternative
fallback tests. The pool code confirms that fewer than four positive-momentum
qualifiers cause the original basket to pass through, before subsequent layers.
The roadmap now prioritizes F1 qualified base weights plus residual cash, F2
cash only, F3 qualified IEF/TLT/GLD base weights plus cash, and F4 an explicitly
specified Treasury-bill ETF parking alternative, against the unchanged F0.
Zero qualifiers may target 100% cash; no minimum investment is imposed.
Cash budgets must survive downstream overlays. Missing-data/model failures are
separate blockers, with matched cash/FX economics, re-entry and fallback-episode
attribution required. This is a research specification, not a tested improvement
or a change to the active strategy.

## Active SOTA and paper allocation — 2026-10-04

The operator approved 100% Rolling 1y XGBoost + ETF activity lag-20 + USD
(`research_rolling_xgboost_1y_lag20_v1_usd_v1`) through the strategy controls.
After evidence-preserving recovery of five completed-order conflict flags and
fresh matched IB reconciliation, the app activated that allocation and SOTA
designation at 08:56:12 +08:00 on October 4 (control revision 2). The approved
handover follows October 2 close; next execution session is October 5.
This is the existing monitored version and separate USD layer, with no model
recipe change. New routing approval remains required. Prior strategy periods,
holdings, execution history and the portfolio baseline are retained.

## USD promotion decision — 2026-10-02

The operator reviewed the momentum results and selected the tested U1 USD layer
for SOTA and both monitored portfolios. The new strategy IDs append `_usd_v1`
to the original SOTA, ETF activity lag-20 and rolling one-year XGBoost IDs.
The complete original definitions remain registered and serve as matched
benchmarks and rollback parents. This decision supersedes the earlier instruction
to retain those parents unchanged.

U1 is a separate final allocation layer: per-ETF expanding ridge with short and
older momentum, 63-return volatility, and same-vintage broad-dollar changes over
21/63 valid observations. Monthly fits require 60 completed monthly labels ending
strictly before the fit close. It preserves selected assets and gross exposure,
using the tested 12% rank tilt and 3 percentage point bounds. XGBoost keeps its
existing 26 inputs and training recipe; including USD inside the trees would
require a separately versioned, matched refit comparison. No such comparison has
been run, so the integration preserves the tested separate model.

The statistical conclusion has not changed: the USD-specific U1-minus-U0 gain is
about 14 bp/year over 30 months, with an interval including zero and Holm p=1.
U1 also contains price features; its full improvement cannot all be attributed to
USD. Prospective tracking of these selected versions begins October 2, 2026.
The inherited 45% setting remains a base allocation limit; it is not a final
holdings cap. The USD layer cannot increase an inherited overweight above 45%.
The requested addition does not alter broker risk limits or increase capital.

Market Data includes USD in Historical Daily Price for published DTWEXBGS history, index
levels, 21/63-observation changes, vintage dates, missing observations and export.
The chart uses one revised vintage; historical models use their own archived
vintages. The application acquires, audits and publishes new required snapshots,
fits models and calculates complete portfolios on refresh. Daily ALFRED archives
do not certify intraday dissemination. Revised ETF histories and legacy CNH FX
retain their existing availability limitations. USD/CNH remains unhedged.

Decision and rollback contract: `config/strategy-promotions/usd-ridge-u1-2026-10-02.json`.
The existing paper policy is bound to the previous strategy ID and therefore
disables automatic approval on restart. It must be reviewed and re-enabled for
the new version through the normal controls; live remains disabled. Paper/live
proposal calculation uses the same published USD model receipt as monitoring and
requires its ETF batch to match the audited decision inputs.

## Momentum horizon, membership and USD round — 2026-10-01

User authorized the revised research plan and all-core backtesting. Completed
102 USD replays: 24 new SOTA recipes, two parent clocks, two benchmarks, two
other-parent controls and four USD transfers, each at 5/10/20 bp per traded dollar.
All 34 base-cost portfolios plus two high-cost stress cases pass native LEAN
parity. Monthly targets reproduce all three monitored parents exactly across
129 decisions. No monitored strategy, execution policy or live setting changed.

Current monthly SOTA returns 9.17% net USD CAGR in this accounting scenario.
One/two-week momentum gives 4.17%/5.61%; the older-window blend gives 6.95%.
All four trend/skew gates trail the parent. Membership C1/C2 reduce annual cost
from 31.8 bp to 26.0/28.5 bp, but CAGR falls to 8.32%/8.41%. These are USD
adjusted-unit research results, not the existing CNH-accounting dashboard series.

Downloaded 92 ALFRED DTWEXBGS vintages and the Fed's revised daily history.
Audited same-vintage snapshots and verified analytical readback before publication
under `governance/usd-broad-index`, batch
`ddb5624ba023c71b9ca41ff0571318eb48f390ad4131ab20858d7eaafdae006b`.
The fixed 60-month ridge training requirement leaves April 2024–September 2026
for evaluation. USD adds 13.9 bp/year versus the matched price-only model;
the marginal six-month-block 95% interval is [-11.4, 33.7] bp, Holm p=1 over
the frozen 58-comparison family. Selected same-data transfers add 13.1/14.2 bp
on activity/rolling parents; these are correlated descriptive evidence.
Retain the USD hypothesis for discussion; no candidate clears promotion criteria.

Risk finding: the inherited 45% cap applies before pool reallocation; the
monthly parent reached 54.68% held weight and the weekly parent 61.52%.
A separately versioned final-weight constraint is needed before advancement.
Parent volume features remain legacy normalized proxies; audited prices are
revised vintages, and ALFRED availability is daily archive evidence with a
conservative prior-day cutoff. Legacy historical USD/CNH was excluded, so no
full historical CNH bridge is claimed. No prospective performance is claimed.

Full results: [review report](../research/momentum-results-2026-10-01.md).
Artifacts: `var/research/momentum-20261001-v1b`; earlier failed engineering
attempts and the transfer-selection correction are preserved. Tests: 48 passed,
one environment-dependent PostgreSQL integration test skipped. Source checks
and native parity retain paper-first controls.

## Rolling one-year XGBoost with lag-20 selected for app tracking — 2026-09-27

The user selected a third tracked candidate: `research_rolling_xgboost_1y_lag20_v1`.
The original rolling study had no activity overlay; the new definition adds the
unchanged lag-20 allocation overlay after XGBoost and the remaining SOTA steps.
The application owns monthly causal fitting, portfolio calculations and the full
shared report. All 129 models exactly match the study, and five native runs pass
parity. Matched activity-only and XGBoost-only controls appear in the report.

Full-history annualized return is 10.093%, Sharpe 0.9675, maximum drawdown -15.336%
through September 25, versus SOTA 9.656%, 0.9492 and -15.055%. This is historical
reconstruction selected after reviewing results; prospective tracking starts
September 28 with zero observations at publication. SOTA and existing activity
results are unchanged. No promotion, broker execution or paper-policy change.
See [strategy specification and initial acceptance](rolling-xgboost-lag20-tracking.md).

## Rolling tree, forest and XGBoost investigation — 2026-09-27

Completed all 41 native LEAN runs with unchanged parity. Monthly one-year
XGBoost/forest return 15.88%/15.75% CAGR from 2023 versus deployed frozen SOTA's
14.94%; primary six-candidate adjusted p=0.014/0.020 (63-session blocks).
However, frozen XGBoost/forest return 15.72%/15.68%, and tree-free SOTA returns
15.49%. Rolling adds only 0.159/0.063 annual percentage points versus the same
frozen model family; intervals include zero (adjusted p=0.529/0.692). Two-year
ensembles lag their frozen counterparts. Cost, delay and seed checks retain
the one-year ensemble gains versus SOTA, but gains are concentrated in 2025–26.
Long-history forest/XGBoost CAGR 9.97%/9.94% versus reconstructed SOTA 9.63%;
long adjusted p=0.068/0.108. No uniform stress-period improvement or clean
evidence for rolling refitting itself. Retain SOTA; future evidence should compare
fixed frozen and rolling ensemble recipes prospectively.

All 16 logical cores were used for independent fits; eight process workers ran
isolated two-CPU LEAN simulations. Published audited inputs, pinned FX/model
hashes, completed-label embargo and fixed portfolio rules are retained. Revised
vintages, fixed-universe selection and uncertified legacy FX remain limitations.
Archived 52,749 NAV/metric observations, six documents and 41 native receipts.
See [findings, protocol and replay](rolling-model-research-2026-09-27.md).
Calculations were a finite application job; no tracked membership, promotion,
paper policy or execution authority changed.

## App-owned tracked calculations — 2026-09-26

The application now owns the entire calculation lifecycle for monitored executable strategies. `config/strategy-monitoring.json` selects native LEAN with Python parity (default) or the application's isolated Python engine. New audited inputs/definitions trigger signal, monthly rebalance, daily NAV, held-weight and latest indicative-target calculations; unchanged revisions are reused. Complete results and their matched benchmarks publish atomically to ClickHouse. **Refresh calculations** wakes the application worker. The Codex heartbeat was deleted and its review script retired. `AGENTS.md` and the continuous research playbook explicitly prohibit agent-scheduled strategy calculation.

Both SOTA and ETF lag-20 use the same full report, including risk parity on the matched ETF universe, URTH, current SOTA, period metrics, drawdowns, holdings contributions, signal attribution, current allocation and complete decision diagrams. SOTA attribution uses risk parity; lag-20 attribution uses SOTA. History spans 2016 onward: pinned causal annual trees before 2023, then the unchanged deployed frozen model. The old 2023 card was the frozen-model companion, not a price-data boundary. The new history is a disclosed reconstruction and differs from the earlier all-years annual-refit experiment.

User decision remains **track, do not promote**. Forward observations begin 2026-09-28; historical results are not relabelled as prospective evidence. Only published audited prices are used. Legacy FX remains explicitly uncertified through September 24; validated direct IB USD/CNH close evidence supports September 25. Historical price vintages remain a limitation. Protocol and engine configuration: [app-native lag-20 tracking](etf-activity-lag20-tracking.md).

## Superseded initial ETF lag-20 observation workflow — 2026-09-26

The initial frozen card remains historical evidence in `config/etf-activity-lag20-tracking-v1.json` and ClickHouse `research-tracking/etf-activity-lag20-v1` (935 paired historical NAV points). Its daily Codex review automation has been deleted. The application calculation and common report above supersede this workflow; do not restart its agent scheduler or treat its archived card as the current strategy.

## Audited-input rerun — 2026-09-26

Retain current SOTA. The pinned audited batch has now been used for 24 native LEAN runs, all passing parity, covering 2016-01-04–2026-09-24 with causal annual fits plus actual-frozen-model companions from 2023. Baseline CAGR/Sharpe 9.84%/0.956; early signed constituent activity 9.82%/0.955, IR -0.172; constituent concentration IR -0.289. Earlier allocation/selection and joint residual trees do not establish added value. The fixed ETF lag-20 observation candidate reaches 9.99%/0.966, IR +0.285, but its 63-session family-adjusted p=0.574 and uneven period performance do not justify promotion. Candidate-specific audited cost/delay work remains before any lag-20 promotion review.

The stricter supported-raw/identity rules qualify only 32/129 monthly decisions, first 2023-08-01. Earlier months are neutral fallback, not a decade of constituent evidence. There are 551 matched scatter dates starting 2023-07-17; unsmoothed derivatives are near zero, with a modest smoothed 20-session relationship that has not improved the strategy. Do not lower coverage rules after seeing these results. Resolve historical issuer/raw-price gaps in a new audited batch before extending constituent evidence.

Future price research must read published audited continuous histories with pinned batches, verified hashes and explicit adjustment/volume bases, as required by `AGENTS.md` and the continuous research playbook. Provider archives are acquisition/audit evidence only. Auditing does not supply missing point-in-time vintages, complete delistings or certified FX. The unchanged legacy FX and assumed holdings-publication lags in this frozen rerun remain disclosed limitations.

Evidence: [audited rerun findings](audited-research-rerun-2026-09-26.md); `D:/systematic_trading_data/lean/research/audited-rerun-20260926-v1/`. ClickHouse contains 11,862 new observations and 22 documents across feature/result/review publications with exact payload readback; 24 native receipts are registered in PostgreSQL. Prior studies remain reproducible legacy evidence; the production model and monitoring-reader contracts are unchanged.

## Data-governance hold — 2026-09-26

The frozen ETF inputs used in the recent studies contain adjustment/source
boundary inconsistencies against a consistently collected new Yahoo vintage.
For HYG on 2026-05-26, the old snapshot implies -1.6528% versus +0.3379% in the
new governed series (1.9907 percentage points). That boundary coincides with
`sqlite_price_bars` changing to `platform_market_data_store`; SPY and LQD also
differ there. EWH has a separate discrepancy on 2026-04-30. Preserve prior
results as reproducible evidence of the old inputs, but rerun baseline and
candidate comparisons on pinned governed data before any promotion decision.
The identity audit also found older CSVs containing multiple economic issuers
under reused tickers (including NET/WMS/TXG). Recent price agreement does not
validate their earlier eras. Policy v2 quarantines periods before the current
provider listing boundary, or a conservative preferred-source identity floor
when that metadata is absent. Historical constituent research must map dated
issuer episodes rather than apply the current ticker's identity retrospectively.
The first governed build was quarantined before publication; its joined rows
are not accepted inputs. Original historical sources remain available for review.

No new strategy is elevated. See `docs/price-governance-2026-09-26.md`.


## Latest evidence — 2026-09-26 ten-year constituent follow-up

Retain current SOTA. The earlier January 2023 signal cutoff was a completeness
limit, not a deliberate short evaluation window. New dated IVV holdings and
archived public stock histories support 2016-01-04–2026-09-24: 122 of 129 monthly
decisions pass the unchanged primary 95%-value/70%-names rule. The 2020 and 2022
stress periods now have constituent observations. Histories remain revised,
publication lags are assumed, and IVV is a same-index proxy only for SPY.

Twenty-two long LEAN runs use annual expanding base trees to avoid future-label
leakage from the deployed pre-2023 fitted model. Baseline CAGR/Sharpe is
9.64%/0.932; early signed activity 9.68%/0.936/IR +0.158 trails the matched price
control 9.69%/0.937/+0.190. Its gain is 3.4bps CAGR, with a confidence interval
including zero and family-adjusted p=0.813. Joint residual-tree IR is +0.218
versus baseline but only +0.039 versus the price-only tree; concentration is
negative (-0.232). Selection changes three decisions and loses slightly. Early
signed activity worsens 2022. The four-run actual frozen-model companion has a
recent signed-activity IR +0.429 versus SOTA, only +0.105 versus price control,
and no statistically established gain. No promotion or trading-policy change.

The Market Data page now exposes the previously hidden ClickHouse research
archive, including stock bars, dated holdings, features and results. Added
2,298,993 current-provider stock observations, 85,050 holding rows and 7,595,897
public archived observations with exact readback. Final long-study features,
models and labels total 16,352 records; results/contrasts total 366. All 26
successful native receipts are registered. Public-source overlaps are preserved
as separate histories, not inserted into the canonical production daily bars.

Guide and replay: `docs/constituent-tenyear-research-2026-09-26.md`. Remaining
work is ETF-specific identity/publication quality and prospective validation of
fixed candidates, not further tuning on this inspected sample. Full suite 616
passed/51 optional skips; research/LEAN/browser lint, charts and browser checks
passed. Existing IB Gateway health remained unavailable during dashboard startup;
broker settings, orders and approval policy were not changed.

## Production Research Rule

Research is now part of a controlled research-to-paper-to-live pipeline. New candidates must compare against the current SOTA, use point-in-time data, record reproducible artifacts, and pass the promotion gates in `docs/industrial-platform-plan.md` before paper or live use.

## Alpha Factory Direction

The next research operating model should treat each alpha or factor as a versioned, independently observable contributor rather than only storing monolithic strategy runs. Before risk-parity-style alpha weighting is promoted, add contracts for factor identity and lineage, point-in-time signal values, theoretical factor returns, realized portfolio contribution, turnover/cost/capacity, correlation and covariance estimates, allocation weights, and retirement or rollback state.

Portfolio attribution should remain layered: strategy backtest NAV versus actual account NAV measures implementation divergence; reference-fill versus actual-fill PnL measures execution quality; factor-level theoretical and realized contribution explains which alphas earned or lost the portfolio result. Factor weights must be reproducible artifacts with concentration, correlation, liquidity, and regime-stability limits, not an unconstrained inverse-volatility calculation.

Use `.agents/skills/continuous-research-loop.md` for recurring challenger research and `.agents/skills/strategy-promotion-control.md` for promotion decisions.

## Current SOTA

September 26 earlier-integration follow-up: **retain current SOTA**. Nineteen
native LEAN runs test the selected signed-activity/breadth signals in earlier
allocation, pool selection and a shallow residual tree, with matched price-only
controls. Post-2023 earlier signed allocation is effectively identical to late
(14.77% CAGR / Sharpe 1.299 / IR +0.262); price-only early remains stronger
(14.79% / 1.301 / +0.301). Signed selection changes no weights or trades: SPY is
already held on 39/44 qualified dates and the other five have neutral/negative
signed scores. Breadth selection changes one decision and loses return.
The joint tree actually branches on stock breadth/signed activity, but 2025-onward
CAGR 18.84% / Sharpe 1.467 / IR -0.876 trails SOTA 19.03% / 1.474 and the price-only
tree 18.89% / 1.471. Twenty monthly model decisions begin February 2025; 19 change
allocations. Models have just 23/35 training months; future labels are excluded
and runtime features contain no outcome records. All samples were previously
inspected, so chronological fits are not an untouched holdout. Earlier placement
does not repair missing delistings, assumed availability or a U.S.-proxy-only
universe. Sources, four models, training labels, results and native receipts are
archived; no promotion. Next: ETF-specific constituent panels and fresh data
before a broader selection test. See
[earlier-integration evidence](constituent-integration-research-2026-09-26.md).

September 26 constituent follow-up: **retain current SOTA**. Five fixed stock
signals, their equal-weight primary composite, a price-only control and declared
robustness checks completed 15 native LEAN runs with unchanged parity. Historical
ITOT stocks guide only the SPY sleeve; they are a broad U.S. proxy, not exact SPY
or foreign-ETF membership. Full-period (2019-10-01–2026-09-24) primary CAGR
8.49% / Sharpe 0.782 / IR -0.394 versus SOTA 8.52% / 0.784. Concentration
acceleration IR -0.507. The 95%-value/70%-name complete-history rule first passes
January 2023, leaving 44 eligible monthly decisions and 33 composite target
changes. There is no constituent evidence from COVID/2022. Post-2023 primary
IR -0.540; signed activity has sample IR +0.262 but lags the price-only control
(+0.299), and its family-adjusted p=0.831 does not support inclusion. Do not
flip signs or refit weights on this reused history. Costs, delay, size and coverage
checks do not rescue the primary. All feature/results evidence is in ClickHouse
and native runs are registered; historical availability remains uncertified.
See [results and the constituent research plan](constituent-signals-research-2026-09-26.md).
Next: actual ETF-specific identities/holdings and earlier delisted histories;
then separately declared downside breadth, internal dispersion, filing-time
fundamental breadth and genuine issuance-confirmed crowding. No new recurring
job or paper/live strategy change.

September 26 flow/concentration research: **retain current SOTA**. Nineteen native
LEAN runs (17 predeclared plus two labeled post-hoc stresses) compare the current
12-ETF stack with activity-share acceleration, direction/Hurst/HHI/volume
ablations, a literal exit gate and parameter neighbors. Over 2013-04-01 to
2026-09-24, the predeclared primary returned 9.06% annually / 0.919 Sharpe versus
SOTA 9.11% / 0.924. A 20-session neighbor returned 9.28% / 0.935 and survived
matched higher-cost and delay checks, but full-period family-adjusted p=0.354
and weak neighborhood consistency do not support promotion. Retain that fixed
variant for observation; it was selected after results. The literal gate held
64.8% cash and returned 2.90%. Historical actual net flows, shares outstanding,
holdings and certified point-in-time constituent-sector membership remain absent; activity is not net inflow.
All runs passed unchanged parity and remain research-only. See the
[research report and data plan](flow-concentration-research-2026-09-26.md) and
`D:/systematic_trading_data/lean/research/flow-concentration-20260926-v3/`.
These numbers are a fresh adjusted-CNH LEAN comparison, not a recertification of
the older canonical artifact below. Next: timestamped net-issuance data and an
untouched prospective observation period, not more optimization on these dates.

Sector-HHI follow-up: daily Yahoo price/volume history for all eleven sector
SPDRs and SPY is now frozen separately under
`D:/systematic_trading_data/research/sector-hhi-20260926-v1/` (research only).
The 1,823 common signal dates, 2019-01-02–2026-04-02, show weak SPY return
correlations with share-volume HHI (+0.075/+0.115/+0.093 at 20/60/120 sessions)
and almost zero correlations with its daily first/second differences.
Smoothing does not establish an acceleration effect; period and dollar-volume
checks weaken the level relationship. These are descriptive overlapping-label
plots, not a new LEAN backtest or a promotion. ETF activity is not full-sector
turnover or investor net flows; historical adjustment vintages remain
uncertified. See [plots, methods and findings](sector-hhi-correlations-2026-09-26.md).

Underlying-stock follow-up: the public-data pilot now uses 95 historical monthly
ITOT equity snapshots, 3,267 populated stock histories and sector aggregates of
the stocks' own volumes/returns. It has dated sector cohorts, a modeled 45-day
publication lag and explicit missing/identity coverage, rather than today's
constituents applied to all past dates. However, only 139 common signal dates
(2025-09-15–2026-04-02) pass the 95%-value/70%-name coverage rules and have all
forward horizons observed. Raw first/second differences remain near zero in
that sample; its length and overlapping labels preclude a stable market-wide
conclusion. The longer observed-subset sample has material missing/delisted
history. The stock/fund histories and computed aggregates are archived under
ClickHouse `sector-research/<dataset>/` source prefixes. Keep SOTA unchanged.
See [underlying-sector evidence and storage guide](underlying-sector-hhi-2026-09-26.md).

September 26 audit: historical results below are retained as prior research
artifacts, not re-certified after the timing/data corrections. Missing source
vintages, fixed-universe survivorship and legacy FX lineage remain limitations.
The pre-2023 tree is fitted; post-2023 has been used repeatedly for strategy
selection and is not an untouched holdout. The new LEAN adjusted-CNH-unit scenario
has separate economics and artifacts; it does not overwrite these numbers or
promote a replacement. See [audit findings](platform-audit-2026-09-26.md) and
[LEAN workflow](lean-backtesting.md).

Paper operations now include separately tagged initial-allocation and 2 percentage point drift-maintenance proposals. Monthly signal calculation is preserved; intraday TWAP timing and additional turnover are not represented in the existing monthly benchmark. Keep attribution separate and validate execution/cost effects before live promotion.

### Original parent record — superseded by the October 2 USD version

- Name: SOTA: price/volume top 6 + technical tree + relative/adaptive
- Promoted on: 2026-05-26
- Registry: `systematic_trading.research.strategy_catalog.legacy_sota_definition`; `current_sota_definition` now returns the USD version described above.
- Backtest hurdle: future candidates should compare against the current USD SOTA and preserve this parent as a matched control.
- Canonical artifact folder: `var/backtests/sota_current/`
- Model HTML: `var/backtests/sota_current/sota_model.html`
- Promotion source artifact: `var/backtests/monthly_allweather_sleeve_variant_floor_search_20260525/`
- Prior SOTA artifact: `var/backtests/sota_current/history/2026-05-17_sota_dynamic_sleeve_commodity_guard_55/`

## Original Parent Model Summary

The original parent uses the expanded multi-asset ETF universe and static monthly rebalancing. The current SOTA appends the USD layer described above to this stack:

- Base: monthly multi-asset ETF universe, 63-bar inverse-volatility risk parity, 45% base weight cap before subsequent reallocation, 2% cash reserve.
- Pool filter: rank assets using 63/126/252-bar price momentum and 21/126-bar volume pressure; keep the top 6, require at least 4 selected assets, require positive 252-bar momentum, and reallocate residual weight.
- Technical tree: frozen pre-2023 regression tree, max depth 3, min leaf 25, trained on 1,572 in-sample asset-month observations with MACD, Bollinger, RSI, price trend, volume pressure, drawdown, valuation, and macro features. Tilt is 16%, with active changes capped at 6% per ETF.
- Relative momentum: 20/60-bar relative momentum overlay, 12% calm and 12% risk tilt, with active changes capped at 5% per ETF.
- Adaptive trend: 63/126/252-bar trend and volume/rebound/volatility-shock gates with weak, neutral, defensive, and rebound scaling.
- Benchmark: the canonical folder includes a benchmark-only run using the same multi-asset universe and static monthly scheduler.

Canonical results versus benchmark-only multi-asset risk parity, 2012-01-03 to 2026-04-29, split 2023-01-01:

| Window | Ann. Return | Sharpe | Calmar | Max DD | Alpha vs Benchmark | Information Ratio |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Full | 9.10% | 0.95 | 0.65 | -14.11% | 134.60% | 0.63 |
| In-sample | 6.89% | 0.77 | 0.49 | -14.11% | 54.07% | 0.49 |
| Out-of-sample | 16.92% | 1.48 | 2.00 | -8.46% | 28.57% | 1.13 |

Stability note: this candidate was promoted because it is cleaner than the high-OOS all-weather sleeve after penalizing weak in-sample evidence. The OOS/IS Sharpe ratio is still high at about 1.92, so it should be treated as the current best production candidate rather than a final answer to the stability objective.

## Workflow Rule

Use `scripts/export_sota_artifacts.py` to regenerate the canonical SOTA folder after a promotion. Use the multi-asset research scripts for new challengers; use legacy `scripts/compare_trend_signal.py` only for old single-basket diagnostics or to quantify value added versus the original beta sleeve.

The comparison artifacts include model structure diagrams for the SOTA and candidate:

- Layer diagram: data, rebalance schedule, base beta sleeve, overlays, final targets.
- Decision tree: the gating and transformation logic used by each model.
- HTML reports shade the out-of-sample region and mark the split date when a split is provided.

## Short-Horizon Relative Momentum Tests

Artifacts:

- `var/backtests/relative_momentum_20_40_signal_2012/`
- `var/backtests/relative_momentum_20_60_signal_2012/`
- `var/backtests/relative_momentum_40_60_signal_2012/`
- `var/backtests/relative_momentum_20_40_60_trend_rank_2012/`
- `var/backtests/relative_momentum_20_60_tilt_grid_2012/`
- `var/backtests/relative_momentum_20_60_tilt20_2012/`

Results versus prior 126/252d SOTA, 2012-01-03 to 2026-04-29, split 2023-01-01:

| Candidate | Full Alpha vs SOTA | In-Sample Alpha vs SOTA | OOS Alpha vs SOTA | OOS Sharpe Delta | OOS Max DD Delta |
| --- | ---: | ---: | ---: | ---: | ---: |
| Relative momentum 20/40d, 12% tilt | -2.31% | -1.39% | 0.16% | -0.00 | 0.02% |
| Relative momentum 20/60d, 12% tilt | -0.09% | -0.42% | 0.36% | 0.00 | 0.05% |
| Relative momentum 40/60d, 12% tilt | -1.29% | -0.80% | 0.24% | -0.00 | 0.06% |
| Three-horizon trend rank 20/40/60d, 12% tilt | -0.89% | -0.30% | -0.09% | -0.00 | 0.06% |
| Relative momentum 20/60d, 20% tilt | 1.09% | -1.02% | 1.47% | 0.01 | 0.03% |

The 20/60d shorter-horizon pair became a prior registered SOTA and remains part of the current promoted stack at a more restrained 12% calm / 12% risk tilt. A 25-case tilt grid ranked 20% calm / 20% risk tilt first by OOS alpha. It still trailed the MSCI World proxy by 0.87% OOS, versus the prior 126/252d SOTA trailing URTH by 2.34% OOS, so future work should continue using URTH as an external benchmark check.

## Latest Country-Factor Research

Added `CountryCompositeFactorOverlay` for country ETF allocation research. It can blend:

- Price trend: 63/126/252-bar relative trend ranks.
- Volume pressure: up-volume share and signed volume acceleration.
- Mean reversion: 21-bar reversal and 63-bar moving-average deviation.
- Optional valuation score maps where positive means cheaper or more attractive.
- Optional macro-growth score maps where positive means stronger country growth.

Artifacts:

- Diversified price-trend candidate: `var/backtests/country_factor_trend_only_2012/`
- Balanced multi-factor candidate: `var/backtests/country_factor_signal_2012/`
- Aggressive US macro-prior candidate: `var/backtests/country_factor_macro_us_2012/`

Results versus prior 126/252d SOTA, 2012-01-03 to 2026-04-29, split 2023-01-01:

| Candidate | Full Alpha vs SOTA | OOS Alpha vs SOTA | OOS Sharpe Delta | OOS Max DD Delta |
| --- | ---: | ---: | ---: | ---: |
| Country factor, 63/126/252d trend only, 20% tilt | 0.10% | 1.19% | 0.01 | 0.00% |
| Balanced trend/volume/mean-reversion default | -0.87% | -0.54% | -0.01 | 0.08% |
| Aggressive US macro prior, 100% macro weight, 100% tilt | 213.16% | 27.62% | 0.17 | -4.15% |

MSCI World proxy check using URTH in CNH:

| Candidate | Full Alpha vs URTH | OOS Alpha vs URTH |
| --- | ---: | ---: |
| Country factor, 63/126/252d trend only, 20% tilt | -163.54% | -1.16% |
| Aggressive US macro prior, 100% macro weight, 100% tilt | 49.51% | 25.28% |

Promotion note: these country-factor candidates were not promoted. The diversified trend-only country factor is a credible challenger but only modestly improves out-of-sample and is weaker in-sample. The aggressive US macro-prior candidate beats URTH, but it is mostly a persistent US overweight and uses a static score map across history. Treat it as a benchmark-aware stress case until point-in-time macro and valuation tables are added to the SQLite data contract.

## Signal Library And Decision Tree

The code-backed signal library is in `systematic_trading.signals.library`; the human-readable table is `docs/signal-library.md`. Decision-tree runs also write `signal_library.md` and `decision_tree_training.json` in their output directory.

Decision-tree candidate:

- Artifacts: `var/backtests/decision_tree_signal_tilt20_2012/`
- Training sample: 655 in-sample asset-month rows, ending before the 2023-01-01 split.
- Features: 16 signal-library features from that run, covering trend, mean reversion, volume, risk regime, valuation score, and macro-growth score. The library now also includes the promoted 20/60d momentum features for future training runs.
- Model: max-depth 3 regression tree, min leaf 25, target is next-rebalance asset return minus cross-sectional basket mean.
- Learned first split: `macro_growth_score <= 0.5`, then short momentum, extended momentum, and volatility ratio.

Results versus prior 126/252d SOTA, 2012-01-03 to 2026-04-29:

| Candidate | Full Alpha vs SOTA | OOS Alpha vs SOTA | OOS Sharpe Delta | OOS Max DD Delta |
| --- | ---: | ---: | ---: | ---: |
| Decision tree, depth 3, 20% tilt | 29.00% | 0.50% | 0.01 | 0.08% |

MSCI World proxy check using URTH in CNH:

| Candidate | Full Alpha vs URTH | OOS Alpha vs URTH |
| --- | ---: | ---: |
| Decision tree, depth 3, 20% tilt | -134.64% | -1.84% |

Promotion note: do not promote the decision tree yet. It helped versus the prior 126/252d SOTA OOS, but the OOS edge was small, the tree uses a static macro score map, and it still trails URTH. It is useful as an interpretable research candidate and a framework for point-in-time macro/valuation data once those tables exist.
