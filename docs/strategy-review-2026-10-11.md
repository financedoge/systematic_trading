# Strategy review and repair — 2026-10-11

This review follows the supplied `Strategy_research_review_2026-10-11.docx` and the
other agent's subsequent repairs. The document is evidence, not an instruction
source. The operator clarified that allocation means **paper capital first**.
Existing uncommitted contributions and historical evidence roots were preserved.

The main conclusion is unchanged by the repaired accounting: **FR25 + 5% Alpha101
does not establish an improvement over FR25.** Several previous claims were too
strong, and the earlier repair was incomplete. The code fixes below are implemented;
the canonical new measurements are identified separately from archived grids.

## Corrected FR25 comparison

Fixed recipe, 70 monthly decisions, 2021-01-04–2026-10-08, USD adjusted units,
$1m initial funding, 5 bp per traded notional, no extra execution delay, zero cash
interest. All 14 supported candidates remain eligible; the tilt ranks held names.

| Strategy | CAGR | Sharpe, zero cash rate | Maximum drawdown | Annual cost |
| --- | ---: | ---: | ---: | ---: |
| FR25 | 13.091% | 1.193 | −8.656% | 40.352 bp |
| FR25 + 5% monthly family tilt | 12.988% | 1.182 | −8.253% | 40.365 bp |

The tilt sacrifices 0.103 percentage points of CAGR and improves maximum drawdown
by 0.402 points. It also trails in return and Sharpe in **all six** cost/delay
scenarios (5/10/20 bp; zero/one session delay). With a one-session delay its
drawdown becomes worse than FR25's. The primary six-month-block paired bootstrap
estimates annualized arithmetic excess of −0.0855 points, with a 95% interval
[−0.3773, +0.2281] points and p=0.580. This is inconclusive, not equivalence and not
proof of positive alpha. The window and recipe were already inspected.

Evidence: `var/research/strategy-review-20261011-v3/`, protocol SHA-256
`d0a56ce47f6f78bd672aa37230ad854e8f98206207759aacf6ffdf1794bed2c8`.
Twelve matched replays completed. The app worker reproduces every frozen FR25
control target; independently constructed research HOLD targets match all 70 app
decisions. Replays agree exactly in fills, final quantities, NAV, cash and fees.
Both headline arms pass independent native LEAN parity. This verifies the
calculation contract, not broker execution or historical data availability.

Review attempt v1 also labelled a 2016 start “full”; FR25 decisions only begin in
2021, so it padded the prehistory with cash. That comparison is withdrawn. v2
removed it; v3 additionally includes the missing-window ADV correction. Use v3.

## Repairs and limits of the evidence

| Finding | Final treatment |
| --- | --- |
| Daily repetition silently rebalanced monthly HOLD | Monthly rows occur on every scheduled date, including unchanged weights; shares are held between events. Fixed-pair app/research accounting parity now verifies this, beyond engine-only parity. |
| Same-session close used by an open-time exit; wrong entry anchor | Exits only read prior closes, and missing closes are not carried forward. The historical exit study explicitly uses a **prior-close contribution proxy**. It is not fill-based trade PnL or an executable intraday TP/SL model. |
| Re-entry unreachable | Re-entry is evaluated after exit while the tilt is empty; regression tests exercise exit and re-entry. |
| Alpha 43 used current ADV throughout history | Each ratio uses its own rolling raw-dollar ADV; 39 observations are required. Missing observations invalidate affected windows without poisoning later complete windows. |
| Ordinal ranks biased IC ties | Spearman diagnostics use average tied ranks; symbol relabelling tests protect this. |
| First return/fees/drawdown omitted | Funding precedes the first NAV; first-session loss and costs enter every metric and monthly return. |
| Singleton DBC/GLD bypassed positive momentum | The positive 126-session gate applies independently of sleeve size. Existing corrected construction evidence and synthetic counterexamples are retained. |
| Small tilt credited with whole-book information; nonpositive cost auto-pass | The tilt's own forward payoff must be positive and cover positive incremental cost at least 3×. Missing active legs invalidate payoff; no-op dates count as zero. Full-pool IC is diagnostic only. Zero-cost generic mappings still require positive information. |
| Adjusted close × raw volume treated as dollars | Date-aligned audited raw close **and raw volume** now reach screen, studies, app overlay and historical app worker. Adjusted OHLC remains the return basis. Missing raw data stays missing. |
| Calibration compared different calendars | CP/M1 now use the same 70 evaluation decisions as measured NAV, rather than 130 full-history decisions. Replay receipts and calendars are checked. Their measured/implied ratios are about 0.9852, previously 0.9673/0.9653. |
| Hierarchical score used different members from holdings | The other agent's repair is retained and tested. It changes scored membership on 35/130 decisions but not selected classes in the inspected sample. |
| LEAN children orphaned after spawn/inspection failures | Existing cleanup repair is retained and covered by concurrency failure tests. |
| 63 prices used for 63 returns; alpha 53 over-rejected windows | Sizing uses 64 prices; alpha 53 needs valid endpoint denominators only. |
| Daily event metadata inherited an old monthly cutoff | Every event now records its own strictly prior cutoff; templates use the latest actual decision, never a later decision in the same month. |
| Verification could rewrite evidence | Screen/tilt verification recomputes in temporary directories. Completed results reject overwrites; new studies verify pinned parent hashes and retain source snapshots. |
| Dashboard offered strategies the backend rejected | Catalog, allocation candidate list and backend share the same execution-contract check and a specific reason. Alpha monitoring now also discloses its missing incremental decay diagnostic. |

The corrected standalone screen is **0 pass, 15 reject, 1 insufficient**. The
corrected matched-payoff tilt screen is **4/16 passes at 5%, 3/16 at 10%, 3/16 at
20%**, rather than the old 12/12/5 story. The 5% passes are 43/46/49/51; the last
three are closely related rules, not three independent discoveries. These are
in-sample screening results, not a recommendation to replace the family with
the winners. See [screen](../research/alpha101-screen-review-2026-10-11/index.html)
and [tilt](../research/alpha101-tilt-review-2026-10-11/index.html).

Canonical roots: `alpha101-screen-20261011-v4`, `alpha101-tilt-20261011-v3`, and
`turnover-gate-20261011-v2`, under `var/research/`. The earlier P4.17c–f grid
conclusions about optimal budgets, exits and high frequency are **superseded**;
this review did not rerun their entire combinatorial grid. Corrected source is
available, but only the new fixed-pair evidence above is accepted here. Daily
alpha events still rebalance the whole book, so their costs include resetting
base-weight drift; they do not isolate an independently held alpha sleeve.

Two interpretation corrections also matter. “1,269 to 64 re-tilts a year” was a
count over roughly 5.74 years: approximately 221 to 11 per year. And 1.212 versus
1.214 Sharpe is −0.002, not +0.02. FR25's frozen-through-2022 comparison measures
**continued causal retraining versus a frozen model**, not full-sample hindsight.
Audited revised prices still do not certify historical publication availability.

## Paper allocation decision

Control revision 5 currently assigns 100% of strategy paper capital to F3. There
is no pending allocation. The operator subsequently checked XLE/XLB manually
and reported trading permission; this is retained as operator evidence, and
permission is **not presumed denied**. After the operator logged into Gateway,
the 13:12 UTC probe verified the expected paper account and fresh reconciliation
matched all six positions, with zero unmatched orders or fills. A separate read-only
ISIN lookup verified XLE `conId=4215217` and XLB `conId=4215200`. Contract discovery
is not itself an account-permission test; the operator confirmation is separate evidence. M1/14, FR25 and the alpha variant are already monitored
by the app; calculation status and capital authority are separate.

| Gate | Assessment and action |
| --- | --- |
| 14-ETF execution contract | Genuine implementation blocker, independent of the operator-confirmed XLE/XLB permission. The paper target builder does not bind `financial_rank_selection` schedules or audited activity inputs, although the monitored worker does. The allocator derives instruments from one component, so another component's instruments can be omitted. Complete the minimum model/input binding, raw-share sizing, instrument resolution and mixed-universe reconciliation contract before funding; the full multi-venue P8 vision is not a prerequisite for two US ETFs. |
| IB paper connection and reconciliation | **Resolved during review** after the operator logged in. The expected paper account responds on port 4002 and fresh reconciliation has no breaks. These checks must remain fresh at actual allocation/order time. |
| FR25 statistical uncertainty | A reason to limit experimentation, not by itself a reason to prohibit paper observation. Conditional on the execution contract, a small, separately attributed FR25 paper sleeve is reasonable. |
| Alpha incremental evidence | No positive incremental edge established. Keep zero allocated capital while monitoring; adding a small tilt is not justified by affordability alone. |
| Hierarchical/sleeve study results | Research artifacts are not complete monitored/executable strategies. Concentration and drawdown remain material, and inspected-sample maxima do not justify skipping registration or paper evidence. |
| 44 bp turnover screen | A declared research affordability policy, not a universal law of profitable trading. A different mandate can prospectively register another budget with independent payoff evidence; it should not change this study's hurdle after observing failures. |

**No new allocation or broker order was submitted.** After contract and broker
checks pass, the proposed first experiment is a 5% **paper-capital** sleeve in
FR25, retaining 95% F3, subject to a concrete reviewed preview and combined risk
limits. This 5% capital share is different from a 5% Alpha101 tilt budget. Record
every target, raw-unit order, fill, cash movement and reconciliation; 30 sessions
can establish operational behavior but cannot establish alpha. Roll back to the
existing F3 allocation on a contract/reconciliation failure. No live activation.

## Where to look for better ETF alpha

1. **Match the signal to its horizon and measure incremental contribution.**
   Alpha101 describes average holding periods around 0.6–6.4 days, whereas the
   monitored candidate changes monthly. That mismatch is a research hypothesis,
   not proof that daily rebalancing will work. Measure residual returns versus
   FR25 and each ETF's risk group at 1/5/10/21 sessions; use rolling training and
   purged forward labels, symbol/regime holdouts, and untouched prospective
   observations. Separate reversal from trend families rather than averaging
   all sixteen signs. [Original paper](https://arxiv.org/abs/1601.00991).
2. **Broaden comparable groups, not just the ticker count.** The current fourteen
   combine equities, rates, credit, gold and commodity futures; many signals are
   then ranked on only the handful held. Price-level deltas, share-volume versus
   dollar-ADV comparisons and cross-asset volatility can dominate the ranking.
   More near-duplicate ETFs add little independent breadth. Admit liquid regional
   equity, duration/credit and commodity groups through identity, coverage and
   audited publication checks; normalize price changes and risk within declared
   peer groups. Retain point-in-time membership and economic exposure attribution.
   Evaluate the entire supported pool, never an XLE/XLB-only shortcut. A stock
   cross-section is not homogeneous either; look-through constituent signals need
   historical holdings and publication timestamps before honest ETF aggregation.
3. **Use exits as tested risk rules, not an assumed source of alpha.** Specify
   signal invalidation, time expiry, TP/SL units, re-entry/cooldown, and session
   handling before a run. A −2% whole-portfolio contribution stop on a small tilt
   can be so wide it rarely fires. Prefer a declared volatility/ATR-normalized
   exposure rule and actual fill-anchored attribution for the alpha sleeve. Daily
   OHLC cannot establish which of TP and SL hit first intraday or guarantee a stop
   fill through a gap. Research shows stop-loss value depends on the return
   process; it is not a universal expected-return improvement.
   [Kaminski and Lo](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=968338).
4. **Test ETF mechanisms and realistic execution.** Candidates include risk-adjusted
   short reversal conditional on liquidity/volatility, asynchronous-market
   lead/lag, and recorded issuance/NAV/premium data with actual release timestamps.
   These are hypotheses, not established ETF edges. Evidence from equities that
   liquidity changes reversal speed motivates horizon-specific tests, not direct
   transplantation. Before faster trading, measure spread, opening execution and
   delayed fills per ETF, then trade only when estimated benefit exceeds cost plus
   uncertainty. [Liquidity and reversal research](https://www.nber.org/system/files/working_papers/w30917/w30917.pdf).

## Next plan item completed: P4.18

Before outcomes, the plan registered one 10% annual-volatility target with a
63-session lookback, no leverage, monthly decisions and a maximum 1-point CAGR
sacrifice. It required at least 2 points of drawdown improvement, no lower Sharpe,
and better drawdown/Sharpe than a matched-exposure control. Shared app signal code
owns the calculation; no new strategy is registered or allocated.

| Arm, 5 bp / no delay | CAGR | Sharpe | Max drawdown | Annual cost |
| --- | ---: | ---: | ---: | ---: |
| FR25 | 13.091% | 1.193 | −8.656% | 40.352 bp |
| Fixed 10% volatility target | 10.170% | 1.113 | −8.719% | 35.111 bp |
| Matched constant scale, 87.404% of FR25 | 11.413% | 1.191 | −7.572% | 35.300 bp |

The rule reduces exposure on 33 of 70 decisions. It fails every risk/return
hurdle in all six cost/delay scenarios; affordability alone passes. The constant
scale uses full-window average target exposure and is an **ex-post diagnostic**,
not a deployable fitted parameter. Close this fixed rule without searching for a
better target/window. This does not reject every possible volatility model.

Evidence: `var/research/volatility-target-20261011-v1/`, protocol SHA-256
`d0af7deebd7ea2bba3f62fb598977c52e0a3e17f08afc906d1be802e88977175`.
All 18 replays completed; the headline dynamic arm passed native LEAN parity.

The next priorities are the minimum paper execution contract (including FR25 financial-model and audited raw-activity binding), P4.19 using retained
execution evidence, and audited comparable ETF breadth under P4.16d. A fresh
alpha-family protocol should precede further exit/budget grids. P4.20 should
require incremental signal diagnostics rather than treating base momentum coverage
as coverage of the alpha tilt.

## Validation and deployment

309 focused tests passed, including the two full frozen-screen reproduction tests;
Ruff passed on changed Python files and new modules. This is targeted validation,
not a claim that every repository test was run. The independent replay acceptance
files above are the economic checks. The dashboard was restarted through the
repository's guarded scripts; app-owned recalculation was triggered automatically.
The specific 14-ETF reasons are visible in the API and unsupported strategies no
longer appear in its allocation candidate list. F3 allocation revision 5 is preserved.
IB paper connectivity and reconciliation were subsequently restored and verified after the operator logged in. App refresh completion is recorded in the
session closeout in `log.md`: all seven strategies are current through 2026-10-09, serving publication
`79570b688658...`, with no analytics errors or routing warnings. A transient ClickHouse timeout
recovered on the next app cycle while retaining the last complete publication.
