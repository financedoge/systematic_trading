# Signal decay, alpha overlays and portfolio robustness — research plan

## Current checkpoint — November 7, 2026

WRDS holdings access and the subsequent coverage check are complete. All 29
equity-fund candidates have dated vendor mappings, with 2,012 portfolio/report
dates from December 2020–September 2026. MDY's December 2024 snapshot has 382
unique identifier matches to the retained filing, all exact on shares and value.
Eighteen foreign identifier bridges, a VNOM CUSIP mismatch, missing report dates,
portfolio completeness and receipt/dissemination/vintage timing remain open.
No current vendor date is silently converted into historical available_at.
All extracts stay local; 15 focused holdings tests pass. Continue qualification
before any constituent-alpha replay.
[Holdings report](../research/p421-wrds-holdings-coverage-20261107-v1/results.md).

The subsequent five-case reconciliation and CRSP/early-close/minute diagnostics
are complete. Three of five large discrepancies have exact Alpaca/IBKR daily
volume agreement. The two FIX gaps persist in direct minute queries; CRSP agrees
with IBKR on their daily totals. On UTHR's July 3 early-close control, Alpaca and
IBKR agree on every clock bucket and exact price/size/condition multisets, while
CRSP differs. No provider is admitted as a universal replacement.

WRDS data is retained locally: 2,783 rows, nine dated security matches covering
2,277 stock-days, 253 FLEX rows withheld for lack of a retained identifier bridge,
and 253 WSO Class B rows kept separate. The nine matched securities' closes and
24 cash-distribution events corroborate the bounded published window. Three
isolated native audit publications pass exact hash readback; all historical
available_at values remain null. 41 focused tests pass. No active-history update
or strategy replay.

P4.21 remains in data qualification. Continue identifier, historical holdings/
membership and source-definition work; unresolved historical availability and
qualified lookback coverage still block constituent-alpha research. See the
[five-case report](../research/p421-large-volume-20261107-v1/results.md) and its
linked CRSP, early-close and minute-query reports.

Preceding pilot checkpoint (its proposed five-case follow-up is now complete):

The ten-stock SIP-volume pilot is complete for February 27, 2024–February 28,
2025: 2,530 stock-days, with 2,480 newly captured daily bars and 50 prior rows
reused with original hashes/timestamps. All sessions are present; no fill or
source replacement. The native analytical store contains a separate, versioned
field-audit publication with every observation/document hash verified. It is not
admitted to the active history catalog or any strategy input.

Median absolute volume difference versus the pinned history is 0.006888%, but
five observations differ by more than 1%: RPM April 29 (+11.1644%), UTHR June 25
(+7.4032%) and June 21 (+2.8303%), FIX February 7 (−1.5548%) and February 4
(−1.0672%). Only 21 of 2,530 volumes match exactly. These are descriptive
comparisons, not acceptance tolerances; which source is correct remains open.
The wider window therefore does not inherit the five-day sample's small residuals.

All closes are within $0.005 of prior IBKR RTH bars; 2,529 are within that
diagnostic versus published raw closes. FLEX October 18 retains a
−$0.005001525878906 published residual, without widening the threshold.
All split multipliers are one; 24 retained dividend records and no split records
appear in the window. This does not independently certify action completeness.
Current broker identities match, but historical identity and availability reviews
remain open. Historical available_at stays null for all 2,530 observations.

32 focused tests, Ruff and dependency preflight pass. Two failed transport receipts
and the one successful new response remain local. Existing catalog, registered
assets, consumers and paper/live guards remain unchanged. No strategy replay.

**Stop for discussion.** Proposed next item: freeze the five largest percentage
volume discrepancies above for Alpaca trade reconstruction and independent IBKR
full-day tick controls. This is a diagnostic selection after the pilot, not random
validation or a new qualification threshold. P4.21 remains in data qualification;
its constituent-alpha backtest has not started. Historical holdings/membership,
dated identity and decision-time availability are separate remaining gates.
[Pilot report](../research/p421-sip-volume-pilot-20261107-v1/results.md).

Preceding fourteen-case checkpoint (its proposed next item is now complete):

The 14 preidentified volume-rounding exceptions are now fully compared. Across
seven stocks, 307,092 Alpaca trade/reference records reproduce all 14 archived
daily volumes and all 4,289 returned minute volumes exactly. The 1,916 absent
minutes contain 550,359 eligible shares but no price-eligible trade. Tape-specific
NYSE/Nasdaq rules and update states were declared before acquisition. No update
flags appeared; historical correction/publication timing remains uncertified.

Three preselected independent IBKR controls also agree exactly on full-day
volume and condition-size multisets: CSL February 26 (249,124 shares), FIX February
25 (889,484), and MANH February 27 (464,873). Backward boundary checks pass. These
three controls do not independently qualify the other eleven stock-days. Regular-
hours clock buckets differ by 2,538 shares for CSL and 100 for FIX across the
16:00 boundary; whole-day totals agree and source clocks remain unchanged.

All 14 published-history residuals remain 52–184 shares, at most 0.049799%, with
no exact or nearest-100 match. Their cause remains unproven; no truncation rule,
fitted multiplier or acceptance tolerance was introduced. Existing data was not
overwritten. Ninety-two new payloads, 18 prior payloads and pinned published inputs
verify; 17 focused tests, Ruff and whitespace checks pass. Source responses and
failed-request receipts remain local. No new publication or strategy replay.

**Stop for discussion.** Recommend a versioned, audited SIP-volume pilot for the
frozen ten-stock history, preserving the old series and its residuals. Declare
full-day eligibility, corporate-action basis and decision-time availability before
admission; regular-session inputs need a separate clock contract. This is a
proposed next item, not automatic qualification or publication.
[Fourteen-case report](../research/p421-volume-exceptions-20261107-v1/results.md).

Preceding full-day CSL diagnostic follows.

The full-day CSL trade reconciliation is complete for February 24, 2025. Alpaca
eligible SIP trades and IBKR historical ticks each contain 14,669 trading records
and 413,821 shares; Alpaca's daily bar matches exactly. Published daily history is
413,800, a 21-share residual compatible with nearest-100 rounding on this day.

IBKR's 223,314-share all-hours bar total equals its ticks after excluding vendor-
flagged activity: 162,920 odd-lot shares, 6,501 average-price shares and 21,086
extended-hours prior-reference-price shares. Every one of its 931 minute bars
matches the corresponding unflagged ticks. This refines the earlier short sample:
71 flagged records are not odd lots. Alpaca's 242 returned minutes all match trade
volume; 205 omitted minutes have 36,439 shares but no price-eligible trade. Their
volume explains the entire minute-to-daily gap. Do not fill absent prices or
replace published activity with filtered IBKR bar volume.

All clock-bin volumes and condition-size multisets match across sources. Exact
second/price/size comparison retains 164 differences: exploratory diagnostics find
153 one-second shifts and 11 price differences of $0.0001. Source values remain
unchanged; these are not a new tolerance or unique trade-identity proof. No update
flags appear in Alpaca's snapshot, which does not prove historical corrections or
publication availability were absent.

Twenty-two new payloads, 18 prior payloads, runner hashes, pinned publication
inputs and an independent 1,001-tick backward boundary check verify. Twenty-three
focused tests and Ruff pass. An IBKR farm interruption resumed from verified
completed seconds; Alpaca's initial overly strict zero-size marker check was
corrected and saved responses revalidated. All failures and raw source responses
remain local. No publications, strategy replay, subscriptions or orders.

The authorized 14-case follow-up is now complete and reported above.
Field-specific admission and historical availability remain separate open gates.
[Full-day report](../research/p421-csl-trades-20261107-v1/results.md).

Preceding coverage and source-selection checkpoints follow.

P4.21's [data coverage assessment](../research/p421-coverage-20261104-v1/results.md)
and [December 2024 qualification pilot](../research/p421-quarter-20261104-v1/results.md)
are complete. Sixteen of 29 equity ETFs have public month-end holdings, first
eligible for March 3. Even MDY, with all 401 equity tickers disclosed, has
complete price windows on just 17.92% of equity value. Historical replay
remains blocked. The [five-holding MDY price audit](../research/p421-mdy-audit-20261104-v1/results.md)
is complete. All five have candidate observations, one under a later ticker.
The [remaining 329-holding inventory](../research/p421-mdy-inventory-20261105-v1/results.md)
is complete. Full windows already exist for 71.84% of MDY equity value in
that group. The remaining uncovered records account for 5.12% after candidate
identity and ticker links are separated. The subsequent
[ten-holding evidence pilot](../research/p421-ten-qualification-20261106-v1/results.md)
verified identities and internal consistency, with zero new qualifications.
The subsequent [IBKR comparison](../research/p421-ibkr-reconcile-20261106-v1/results.md)
restored access and completed all ten windows. 2,529 of 2,530 closes agree
within half a cent; one MANH close differs by one cent. Volume and opening-price
semantics remain unresolved; three all-hours controls explain part of the
volume gap. Zero new publications. Next item: settle the volume/session
contract and field-specific qualification, retaining the closing-price evidence
and earlier identity/action reviews. The November 7
[volume-definition review](../research/p421-volume-contract-20261107-v1/results.md)
is complete: split reconstruction and a constant unit conversion do not explain
the gap. A proposed full-tape volume contract preserves the preceding-close
cutoff and requires the latest actually available complete activity session;
same-day after-hours volume cannot pass that cutoff. Existing asset versions
remain pinned. Next: qualify the prepared 50-stock-day consolidated sample once
documented source access is established. Stop for discussion at this checkpoint.

WRDS follow-up: password-file setup and verified TLS/read-only reconnects are
complete. Actual CRSP annual daily-price and historical-identity reads pass.
The tested TAQ trade/master views deny access (42501); raw 2024/2025 schemas also
lack usage. Access evidence is retained locally. Stop for discussion before the
frozen 50-stock-day CRSP comparison and field-definition review. Every extract
must be retained locally with its query and provenance; audit/publication remains
mandatory before research use. TAQ session decomposition needs source access.

Tushare alternative checked November 7: `us_daily` returned five CSL stock-days,
then an explicit one-call-per-minute limit; `us_daily_adj` denied permission.
Sources and receipts are retained locally. Reviewed U.S. documentation does not
establish the consolidated trade/session contract needed to replace TAQ. Retain
as a limited daily cross-check candidate, with no publication or research replay.
The frozen CRSP sample/field-definition check remains available as a control.
The operator then requested an online alternative-source search, now
[complete](../research/p421-source-alternatives-20261107-v1/results.md). Recommend
a free historical Alpaca SIP probe using the same 50 stock-days; Massive Developer
is a paid fallback, and AlgoSeek daily session/FINRA totals are another candidate
subject to extract pricing. Access/quality were untested at that source-selection
checkpoint; the authorized sample result follows. Retain the audit/publication
and availability gates.

The authorized Alpaca/IBKR source comparison is complete. Credentials were read
from the operator's ignored `.env`; no secret values were displayed or copied.
The frozen ten-stock/five-session SIP sample returned 50 daily bars and 13,878
minute bars. All 50 closes match the pinned published histories within half a
cent; daily-volume residuals have median 0.006373% and maximum 0.049799%, with no
exact matches. Nearest-100 rounding is compatible with 36/50 only. This is source
inspection evidence, not a new volume acceptance threshold or publication.

IBKR older history also works: 1,004 CSL ticks, five regular-hours daily bars,
five all-hours daily bars and 931 minute bars returned to completion. In the
33 complete minutes of the tick sample, IBKR minute volume equals tick volume
excluding its flagged odd lots (12,918 shares versus 24,441 total). Alpaca volumes
match all 23 common minutes exactly; its ten absent minutes contain only flagged
odd-lot ticks. This supports an aggregation/eligibility explanation in this
interval, not full-day certification. Current MANH/SPY frozen quotes explicitly
require additional API permission (10089); billing packages remain uninspected.
The earlier session/IP errors did not recur; operator reports no other live
session and the reason for recovery is unknown.

All 18 payload hashes across ten attempts and pinned comparison inputs verify;
35 focused tests, Ruff and whitespace checks pass. Raw responses remain locally
archived outside Git, with replayable inspection runners. No shared provider,
strategy, order, subscription or publication changed. Volume qualification remains
open beyond the completed CSL day. The authorized full-day follow-up is now
reported above; retain the wider audit/publication and availability gates.
[Completed source comparison](../research/p421-alpaca-access-20261107-v1/results.md).

The [reconciled completion review](research-plan-review-2026-10-31.md) separates
completed experiments, withheld net replays and remaining data/platform work.
The fixed cash-relative net retest requested below is **complete**, with
126 cases, 35 focused tests and three independent native LEAN accounting checks.
Class-first/monthly was selected on 2021–2024; it improves the matching control
later but does not beat FR25's guarded risk/return comparison. Both weakest-ETF
inspections are ready. [Report](../research/cash-relative-net-20261031-v1/results.md).
The operator **retained cash-relative as research evidence** and authorized the
six cost-excluded Alpha101 signals. That separate study is now **complete**:
222 cases on52 supported histories,55 passing tests/one optional skip and three
native accounting checks. All six training-selected policies are monthly;
Alpha54/monthly leads training but establishes no robust guarded advantage across
eras. [Illustrated report](../research/alpha101-net-20261031-v1/index.html).
The operator retained Alpha54/the six-signal study as research evidence onNovember1.
P4.20 [evidence/decay governance](research-evidence-governance-v1.md) is now complete.
Operator continued November2. Expanded-pool FR25 net replay is now **complete**:
144 cases,52 supported histories,63 passing tests,nine exact monthly policy checks
and three exact native accounting checks. Monthly wins training; expanded later
return81.59% exceeds original14's54.93%, but Sharpe1.726<2.003 and
DD15.18%>8.31%. Training comparison also fails original14 guards; no net
superiority established. EWC/XLK weakest inspections and P4.20 dossier are ready.
[Illustrated report](../research/expanded-fr25-net-20261102-v1/index.html).
The operator used this discussion to request a percentage fallback and a joint
expanded-pool M,N search. That follow-up is complete. Requiring 15 of 52 with
six slots matched the original training fallback frequency but lowered IS Sharpe.
The training-only 42/33 winner returned 9.46% in the later period with Sharpe
1.271 and maximum drawdown 5.08%. [Breadth report](../research/fr25-breadth-20261103-v1/index.html).
The operator then requested a check for concentrated winners and stable
annualized returns. The [completed comparison](../research/etf-stability-20261103-v1/index.html)
selected monthly Alpha54 using training data. Its CAGR and Sharpe gaps were
smaller than both 6/4 books, with wide conditional uncertainty. The top-three
withholding experiment leaves both 6/4 books profitable in the later period.
The operator retained the [methodological guidance](research-stability-guidelines.md)
and continued. The [class/volatility net replay](../research/class-vol-net-20261103-v1/index.html)
is complete with 192 cases across the original and current pools. The selected
monthly pooled volatility-normalized book earned 2.73% later CAGR versus 3.94%
for BIL. Its return guard failed in every later friction case.
**Stop for discussion.** This completes the planned withheld net replays.
P4.21 remains blocked on historical holdings and membership evidence.
The original screens below remain historical evidence, not current cost-policy gates.

## Cost policy and retest requested October 17, 2026

The 44 bp annual-cost ceiling is retired by operator instruction. Replay declared
candidates and controls without an absolute cost or IC-proxy veto; evaluate
incremental returns after incremental costs, net Sharpe and Calmar, return/drawdown
guards, cost/delay stress and chronological stability. Historical gate outcomes
remain reproducible but cannot exclude a new comparison.
[Audit and reopened hypotheses](research-cost-policy-review-2026-10-17.md).

Completed October 31: retest the fixed cash-relative family against matched removal-only controls,
current SOTA FR25 and monitored recipes, including monthly and the existing three
dynamic thresholds. The operator retained it as research evidence. Subsequently,
the six cost-only Alpha101 exclusions completed their separate full-supported-pool
net study. Those checkpoints were resolved; the current discussion is the completed
expanded FR25 replay above. No strategy promotion or allocation follows.

## Target-change rebalance study requested October 15, 2026

**P4.22 and P4.23 are complete.** The fixed-top-six threshold study retained
monthly in all chronological selections. The joint maximum selected count X and
target-change threshold n study also retained 6/monthly in all annual windows and
the final trailing-three-year window. Its [6-by-8 grid](../research/selection-width-timing-20261015-v1/protocol.json)
was frozen before joint results; 588 scenarios, six native checks and 98 adoption
checks passed. Wider selection lowered turnover but did not qualify under the
registered FR25 objective and guardrails. [Results](../research/selection-width-timing-20261015-v1/results.md).
Missing daily macro snapshots may use the previous
completed monthly snapshot by explicit operator instruction, with actual source
dates retained. The operator distinguishes strategy target adoption
from trading housekeeping and requested a threshold-selection backtest. Use
`sum(abs(latest theoretical target - last adopted target))`, including cash;
holdings and fills affect accounting, not this trigger. Latest adopted versus
actual held remains a Trading concern. Keep model fitting and monthly events.

The operator selected net Sharpe with return/drawdown guardrails and explicitly
chose the existing FR25 and F3 universes first, with full-pool validation later.
The [complete protocol](target-change-rebalance-plan.md) defines eight thresholds,
monthly/daily controls, causal annual selection, cost/delay stress, stability,
uncertainty and a prospective candidate freeze. Gârleanu-Pedersen (2013) is saved
with provenance in the reference library. This timing study does not change the
existing expanded-universe rejection or grant execution/promotion authority.

## Agreed priorities after the 2026-10-11 review

The [second review](strategy-review-2026-10-11.md) supersedes conflicting numerical claims in the
historical completion notes in the archive. No further budget/exit optimization should use those old results.

**Operator agreement — 2026-10-11.** The operator accepted these recommendations and explicitly
requested substantial expansion of the tradable ETF universe. Universe expansion is a major workstream,
not a two-ticker extension; the staged delivery and acceptance requirements are registered in P4.16d
below. This records the agreed direction and dependencies, not an allocation change.

1. Finish the minimum P8.1–P8.5 paper execution contract for the complete 14-ETF pool; retain all
   approval, raw-share sizing, account permission and reconciliation checks. Bind FR25 financial-model
   schedules and audited activity inputs in the paper target builder, resolve the union of component
   instruments, and verify target/order/reconciliation parity. This minimum delivery need not wait for
   the full multi-venue platform. A shared gate alone does not complete the execution contract.
2. **Completed October 12 for retrospective diagnostics:** P4.19a full-session collection and reference
   publication enabled the P4.19 matched comparison: 27 orders / seven ETFs / five sessions. Routed
   TWAP, close and VWAP reference costs are 1.185, 3.769 and 9.471 bps before fees. Retain current
   execution policy; this sample cannot establish achievable style effects. The close comparison
   changes sign under session omission. [Findings and source limitations](execution-reference-findings.md).
3. Deliver the substantial ETF-universe expansion under P4.16d: candidate inventory and registry,
   staged audited admission, comparable peer groups and scalable app calculations. Include volatility
   normalization, duplicate-exposure control, point-in-time membership and full-pool attribution.
   More tickers alone are not independent breadth.
4. Register one incremental alpha hypothesis with a declared horizon, training/validation split,
   1/5/10/21-session decay diagnostics, and net contribution versus the unchanged base. Separate
   reversal and trend families; correlated 46/49/51 passes are not independent discoveries.
5. Before another TP/SL run, specify actual fill-based alpha-sleeve PnL, exposure/risk units, time expiry,
   re-entry/cooldown and gap rules. The repaired legacy study is a prior-close contribution proxy;
   it cannot establish intraday TP/SL execution. Keep a small fixed comparison and an untouched
   prospective period instead of another inspected-sample exit grid.

**Conditional paper pilot.** Once the minimum execution contract passes, prepare a concrete allocation
preview for **5% FR25 / 95% F3 paper capital**, with combined risk limits and the existing approval flow.
This capital share is distinct from a 5% Alpha101 tilt. Keep the alpha variant at zero allocation while
incremental evidence is absent. Retain app-owned targets, raw-share orders, fills, cash and reconciliation;
review the first 30 sessions for operational behavior, without treating that short sample as proof of
alpha. A contract or reconciliation failure stops new pilot orders and invokes the reviewed rollback
plan toward F3, subject to reconciliation and the existing controls. XLE/XLB permission was manually
confirmed by the operator and gateway/reconciliation passed during the review; these are not presumed
denied, and operational checks must be fresh at execution. Planning agreement does not submit orders.

P4.18's registered fixed rule is now complete and rejected: 18 replays, all risk/return criteria failed,
including against the exposure-matched diagnostic; native parity passed. See the protocol below and
`var/research/volatility-target-20261011-v1/`. This closes that fixed rule without target/window tuning.
P4.20 must distinguish base momentum coverage from the Alpha101 tilt's incremental diagnostic gap.

**Platform dependency — P6.15, requested 2026-10-11.** Review research-worker deployment and resource
scheduling before scaling the ETF universe: measure actual per-engine memory and CPU use, compare
host-native and containerized LEAN, remove avoidable duplication and serial work, and replace fixed
resource assumptions with a tested budget. The objective is useful multicore throughput with responsive
database/operations services. Do not assume that enlarging Docker's memory cap is the solution or that
ClickHouse supplies shared working memory to research processes. Preserve reproducible outputs and
independent engine parity. See [resource review](calculation-performance.md#p615--worker-deployment-and-resource-budget-review).


Registered 2026-10-10. This is the plan for the next research phase, agreed with
the user after a review of the existing research record and a first-hand reading
of Kakushadze's *101 Formulaic Alphas*. It authorises no promotion, funding or
execution change. Each item is registered in
[`docs/execution-kanban.md`](execution-kanban.md) as `P4.13`–`P4.21`.

## Working cadence

The operator updated the cadence on November 7: continue data acquisition,
reconciliation, verification and database preparation autonomously. Close each
bounded check with a retained report and update `log.md`, `docs/research-state.md`
and the Kanban. Ask for required access or missing decisions only when existing
authorization and evidence cannot resolve them. Stop and discuss investment
decisions or new strategy discoveries before proceeding. Earlier item-by-item
discussion instructions remain historical records, superseded for pipework.

## Completed programme and historical protocols

P4.13-P4.19 are historical experiments or completed diagnostics. Current corrected
conclusions are in [research state](research-state.md) and the
[second review](strategy-review-2026-10-11.md). Earlier completion narratives and
all original registered protocols, formula premises and outcomes remain in the
[research-plan archive](archive/README.md). They do not authorize new tuning or orders.

- [Signal decay](signal-decay-findings.md) and [turnover admission](turnover-gate.md).
- [FR25 robustness](fr25-robustness-findings.md) and [placebo/retention](fr25-placebo-findings.md).
- [Sleeve](sleeve-construction-findings.md) and [hierarchical construction](hierarchical-construction-findings.md).
- [Corrected Alpha101 screen](alpha101-screen-findings.md), [tilt](alpha101-tilt-findings.md),
  [replay](alpha101-tilt-replay-findings.md), [daily](alpha101-tilt-daily-findings.md)
  and [exit-rule limits](alpha101-tilt-exit-findings.md).
- P4.18 fixed 10%/63-session volatility-target rule: rejected; frozen evidence
  `var/research/volatility-target-20261011-v1/`, no parameter search authorized.
- [P4.19 original coverage audit](execution-timing-findings.md) and
  [completed retrospective references](execution-reference-findings.md).


### P4.16d — Granular asset classes, a wider ETF pool and volatility-aware class ranking

**Operator's comments, recorded 2026-10-11.** Four asset classes are probably not enough to
differentiate performance between asset classes at all. The operator suggests a more granular
taxonomy:

- **equity** split by region — US equity, EU equity, Asian-ex-China equity, China equity;
- **fixed income** differentiated regionally, not treated as one block;
- **commodities** split by complex — base metals, energy, precious metals, agriculture,
  chemicals/industrial — with semiconductors listed alongside them;
- **boundary cases are real and must be decided, not ignored**: silver is both a precious and an
  industrial metal, and a fund's mandate can straddle categories or change (index switch,
  share-class change, roll methodology). Any taxonomy therefore needs dated, documented assignment
  rules, an explicit treatment of multi-category funds, and a rule for mandate changes rather than a
  static label;
- **volatility control is part of the question, not an afterthought.** In the operator's words,
  selecting the top-performing asset *without* volatility control is not a good idea, because the
  top performer is often simply the most volatile one. A class ranking must therefore be
  risk-adjusted, or class selection must carry an explicit volatility ceiling or size adjustment,
  and that rule must be frozen before outcomes;
- **the data prerequisite is binding.** A granular class selection cannot be built on the current
  14-ETF pool. It needs a **much larger audited ETF pool first**, admitted through the existing
  qualification, audit and publication process — pinned batch, verified input hashes, coverage and
  identity checks — never by reading provider archives or online prices directly into research.

**Taxonomy note.** Semiconductors are an equity industry rather than a commodity complex; they are
already registered as a narrow-industry pilot in the
[ETF expansion roadmap](etf-research-expansion-roadmap.md#portfolio-design-and-universe-expansion),
together with energy. The operator's list is recorded verbatim above while noting this, so the
eventual taxonomy is built from dated classifications rather than from the list's ordering.

**Scope strengthened by the operator — 2026-10-11.** Substantially expand the **tradable** ETF universe,
not merely the research watchlist. Design capacity for hundreds of candidate ETFs rather than a small
extension of the current fourteen; the admitted count is determined by evidence, not a ticker quota.
Cover economically distinct regional, country, sector/industry, duration, credit and commodity exposures.
Candidate admission permits selection; it never mandates a holding or an allocation.

**Staged delivery.** Preserve the one-item-at-a-time review cadence and publish an outcome for each stage:

1. **Inventory and taxonomy.** Produce a versioned candidate inventory with stable identities, listing
   venue/currency, dated peer groups, inception/closure and mandate changes, duplicate-exposure groups,
   and per-instrument data/execution gaps. Prioritize supported USD-listed venues for the first wave;
   additional venues/currencies depend on the corresponding P8 calendar, lot, FX and routing contracts.
   Freeze admission, liquidity and duplicate-handling rules before comparing strategy outcomes.
2. **Audited publication in waves.** Ingest through the existing audit/publication process; publish
   coverage and admission/rejection reasons with pinned batches and verified hashes. Use adjusted
   prices for returns and audited raw prices/volume for activity. Preserve missing history, point-in-time
   eligibility and closed funds where available; disclose survivorship and historical-availability gaps.
   Do not backfill today's surviving universe into periods before its members were eligible.
3. **App and paper execution readiness.** Use the shared registry for calculations, reports and execution
   without adding a hard-coded branch for every ETF. Benchmark refresh, feature, replay and report costs
   at the expanded scale. Verify raw sizing, account permissions, mixed-universe orders, cash and
   reconciliation for each supported contract class; show research-ready and paper-tradable states
   separately. The existing 14-ETF pilot need not wait for completion of the entire expansion.
4. **Controlled research on the expanded pool.** Freeze a new protocol and compare the existing strategy
   on its original pool with the same recipe on the full newly supported pool before adding alpha changes.
   Attribute results by constituent and peer group, control duplicate exposures, then test risk-normalized
   ranking and one declared alpha family at matched horizons/costs. Use time/group holdouts and prospective
   observations; report effective breadth and concentration as well as ticker count.

**First executable deliverable.** A candidate inventory, taxonomy, data/contract gap matrix and proposed
first admission wave with estimated storage/refresh costs. Review it before ingestion; the research
comparison waits for publication, but inventory/admission planning does not require an already expanded
pool. Actual instrument admission and strategy capital remain separate decisions.

**Stage 1 delivered and subsequently accepted — 2026-10-13:** [inventory and admission plan](etf-universe-inventory-2026-10-13.md),
299 symbol/regime records with explicit metadata gaps and 181 proposed peer buckets.
The first wave is 38 additions plus the original 14. It is now ingested, with
holds retained. The report corrects HYXU's false closure label using issuer/SEC/OCC
evidence, preserving separate HYXU/EUHY regimes and the existing price quarantine.

**First comparison — 2026-10-14:** [50-fund current-cohort diagnostic](etf-expansion-findings-2026-10-14.md).
All 52 candidates were reviewed; BWX is held and CPER has a zero-volume input
unsupported by the current activity contract. Expanded FR25 fails the frozen
pre-test (67.73 bp implied annual cost versus 44 bp, IC −0.01463), so its full
portfolio replay is withheld. Original control and benchmark native replays
pass. Historical membership reconstruction and a separately registered
class/volatility-aware design remain open; no post-result parameter tuning.

**Separate construction screen — 2026-10-16:**
[Class/volatility findings](class-volatility-screen-findings.md). Frozen before
outcomes: pooled versus top-three-class/top-two-member selection, raw 126-session
momentum versus momentum/63-session volatility, and monthly plus 0.10/0.40/0.80
target-change adoption. All 52 candidates reviewed; the same 50 published histories
used, with 24 primary classes, explicit parent/child overlap exclusions and cash
for unfilled slots. This price-only factorial design omits FR25 overlays and is a
separate construction hypothesis, not a matched FR25 improvement claim.
All 16 mappings fail the unchanged cost/IC gate; no portfolio replay follows.
Normalized monthly costs pass but information margins fail; later pooled
normalized targets average 45% BIL plus 41.64% cash. 57 tests and independent
target/adoption/IC/turnover checks pass. Stop for review. A cash-relative,
peer-comparable signal would require a separately declared hypothesis, horizon
and prospective period; it is not authorized as an automatic parameter rescue.
Historical membership/mandate and historical classification validity remain open.

**Cash-relative follow-up — 2026-10-17:** user requested continuation after the
construction-screen report. [Registered study and findings](cash-relative-momentum-findings.md)
compare excess-over-BIL momentum divided by the same volatility with a matched
control that only removes BIL. Raw positive momentum, sizing, classes/overlap,
126/63-session windows and the cost/IC gates are unchanged. All 50 published
histories remain inputs; BIL is a reference, not a holding. Pooled/class-first
construction and monthly/0.10/0.40/0.80 policies give 16 mappings, all rejected.
Class-first cash-relative monthly clears the heuristic IC margin at 3.59x but
costs 45.66 bp against 44 bp. Fixed 1/5/10/21-session diagnostics, paired static
payoffs and sparse within-class coverage do not override the gate. No replay.
The predeclared October 19, 2026-April 20, 2027 prospective decision window (labels
through May 19) stays inactive; it creates no monitoring or agent calculation job.
Historical next action (superseded by the October 17 policy above): review the cost constraint before separately declaring a turnover mechanism with
the signal fixed. No lower ceiling, horizon selection or rescue tuning is implied.

**Acceptance when it is run.** The taxonomy, its boundary rules and the risk-adjustment rule
frozen in advance; a pinned audited publication batch with verified input hashes; turnover and IC diagnostics reported for every candidate mapping without an absolute-cost veto; controls that stop
near-duplicate funds from multiplying a class's selection probability (the roadmap's existing
rule); family-adjusted tests; and judgement on drawdown across episodes, consistent with P4.16's
finding that exposure rules matter more than the partition.

**Research comparison blocked on** universe admission. The inventory and admission stages above
are the prerequisites to execute first; do not run the expanded-pool comparison before its inputs are
published. This registration does not itself admit instruments, authorize direct provider downloads
as research inputs, or change monitoring, allocation or the 45% cap.

### P4.20 — Evidence and decay review *(governance; complete November 1)*

The original proposal was a minimum half-life/sub-period IC gate. The operator's
later cost-policy and net-performance decisions supersede that universal proxy.
[Version1](research-evidence-governance-v1.md) requires a hash-bound, versioned
evidence dossier: actual period reuse, training selection, decay/stability and
uncertainty or explicit unidentifiable/insufficient status, matched net outcomes,
fixed/dynamic timing, cost/delay and chronological checks. No universal lifetime,
positive IC or annual-cost floor/ceiling substitutes for net evidence. Unsupported
untouched/prospective claims fail the review; choosing by a later period makes it
development data for that choice. File completeness is not scientific certification.

Executable read-only review and regression tests pass. Worked Alpha54 assessment
retains research evidence while exposing the decay-uncertainty gap before any
new monitored recipe. App calculation, promotion and broker authority remain
separate. No existing strategy is automatically removed or promoted. The P4.13
diagnostics and their explicit forecast/overlay coverage gaps remain historical
evidence, not a complete certificate for all monitored signals. Stop for discussion.

### P4.21 — Look-through constituent alpha *(coverage assessed, replay data-blocked)*

**Question.** Can the structurally cross-sectional alphas be used honestly by
computing them on the constituent cross-section and aggregating holdings-weighted
to ETF scores?

**Why.** The 76 structurally cross-sectional alphas need breadth; the application
already holds 680 IVV constituent series plus issuer holdings and sector data.
This is the only route to using them without pretending 14 ETFs are a
cross-section.

**Caveats to carry.** Index-membership history is a survivorship trap already
flagged in the roadmap; issuer holdings snapshots are prospective-only from
October 2026; and the constituent series are the `review`-status population from
`P3.8`, so this work carries that disclosure.

**November 4 checkpoint.** The [constituent coverage assessment](../research/p421-coverage-20261104-v1/results.md)
is complete. The 680 figure is the review-status subset of 884 IVV-tagged
symbols. Direct point-in-time issuer holdings cover 0/2,030 equity fund-months
in the declared historical comparison. Legacy IVV/ITOT availability is unknown
and admissible price-status coverage is insufficient. Earlier P4.16 ETF-level
results supply context but do not establish a constituent-level edge. The
replay remains blocked on qualified holdings, dated identity/membership and
adequate price/lookback coverage. The subsequent December filing and identity
pilot found zero certified matches across the full price window. Stop for
discussion at the [pilot report](../research/p421-quarter-20261104-v1/results.md).

### Platform item — intraday activation and stops *(not research)*

The user's "activate on an intraday alpha signal, exit on signal flip or a
predefined stop" design is registered as a **platform workstream**, not a research
item, because it needs two things that do not exist: published audited intraday
data, and an intraday execution stack (broker-side or monitored stops, intraday
risk checks, intraday reconciliation). It is tracked in the Kanban's P5 table.

Until both exist, any stop-loss research can only be approximated at daily
resolution (assume the stop fills when the session low breaches it), and that
approximation must be disclosed because it flatters stops in gap-down markets.

## Explicit non-goals

- No further threshold or parameter search on the already-inspected sample.
- No automatic combination of previously failed recipes; the roadmap already
  forbids this.
- No implementation of the 22 Tier-D cross-sectional alphas on 14 ETFs, and no
  substitute for `indneutralize`.
- No unconditional daily Alpha101 overlay of the whole book (see Appendix A for
  the arithmetic).
- No promotion, funding, allocation or execution-authority change is implied by
  any item here. Existing approval, reconciliation, broker-environment and
  live-disabled gates remain in force.

## Appendix A — Alpha101 frozen premises

Established 2026-10-10 by extracting the paper's Appendix A verbatim and
classifying all 101 formulas; counts independently corroborated against
DolphinDB's separately written `wq101alpha` implementation, which agrees exactly
on the 19 alphas requiring an "info" table and the 43-alpha `vwap` set.

| Property | Count |
| --- | ---: |
| Requires `vwap` (not held) | 43 |
| Requires `IndClass.sector/.industry` (not held) | 18 |
| Requires `cap` (not held) | 1 |
| **Blocked by unavailable data (union)** | **49** |
| **Implementable with OHLCV + derived `adv`** | **52** |
| **Contain at least one cross-sectional operator** | **83** |
| Tier A — no cross-sectional operator (pure time series) | 18 |
| **Tier A and implementable** | **16** |

The 16 usable pure time-series alphas: **6, 7, 9, 12, 21, 23, 24, 26, 35, 43, 46,
49, 51, 53, 54, 101.** Six further Tier-B alphas (`1, 8, 10, 18, 28, 33`) become
usable if the outer `rank`/`scale` is replaced by a z-score.

`adv{d}` is not a blocker — it is `mean(close × volume, d)` and the application
publishes audited raw close and raw volume.

Holding period and cost, from the paper's own Table 1 (4 Jan 2010 – 31 Dec 2013,
1,006 observations, proprietary data):

| | Paper's figure | Implied annual one-way turnover | Cost at the frozen 5bp |
| --- | --- | ---: | ---: |
| Fastest alpha | τ=1.604, holding 0.62 sessions | ~404× | ~20.2% |
| **Median alpha** | **τ=0.475, holding 2.10 sessions** | **~120×** | **~6.0%** |
| Slowest alpha | τ=0.157, holding 6.37 sessions | ~40× | ~2.0% |
| Current strategy | — | ~8× | ~0.4% |

Other frozen premises, all from the paper or its immediate lineage:

- The paper's Table 1 caption states the performance figures are *"exclusive of any
  trading or transaction costs, price impact, etc."* The published Sharpe
  figures are therefore gross, at ~48–55% daily turnover.
- The alphas were validated on a cross-section of the top ~2,500 most liquid US
  stocks. A 14-instrument universe is roughly 0.6% of that breadth.
- The 101 are survivor-selected: the paper states 80 were in production when
  written, and reports one sample window with no out-of-sample split.
- Four alphas are "delay-0" (`42, 48, 53, 54`) and must trade at or near the same
  session's close; only `53` and `54` survive the data constraints, and both are
  high-urgency.
- The paper publishes only the *distribution* of turnover, never per-alpha
  turnover. Any per-alpha turnover used in P4.17 must be measured, not assumed.

**Reference.** Kakushadze, Z. (2016), *101 Formulaic Alphas*,
[arXiv:1601.00991](https://arxiv.org/abs/1601.00991). Full text is PDF-only —
`arxiv.org/html/1601.00991` returns 404 and ar5iv refuses the cross-origin
redirect — so re-derivation requires PDF text extraction. Retrieved copy:
sha256 `1f9c21afe32dcb3ee77b31548acdaea00451fbfa1c0ee10c907867bcc736fce9`,
244,416 bytes, 22 pages, arXiv v3. The pinned copy is now retained at
`research/references/alpha101/101_formulaic_alphas.pdf`; verification and formula
extraction enforce the same SHA-256 after its move from scratch storage.

## Appendix B — data prerequisites and blockers

| Need | Status | Blocks |
| --- | --- | --- |
| Published audited daily OHLCV + volume | Available | — |
| Continuous research-approved VWAP history | Unavailable; P4.19 has scoped retrospective session references only | VWAP-dependent alphas and general intraday research |
| Market capitalisation, industry classification | Not held | 19 alphas; `indneutralize` |
| Published audited intraday bars | Not held; raw sampled quotes are `research_approved: false` | Intraday activation and stops |
| Intraday execution stack | Does not exist (`P5.1`–`P5.4` Pending) | Intraday activation and stops |
| Constituent coverage assessment | Complete Nov 4; insufficient historical holdings, identity and price coverage | P4.21 replay blocked |
| Security master for identity certification | Blocked (same access gap as `P3.7`/CRSP) | `P3.8`; long-window alphas needing certified identity |
| Qualified USD/CNH history and FX inputs | Unresolved input class | Any CNH-denominated claim beyond the current disclosures |

No paid subscription is assumed by this plan. Source acquisition, retention and
derived-data rights must be confirmed before any paid feed is selected.
