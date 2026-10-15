# Execution Kanban

Current work and unresolved acceptance gates, consolidated 2026-10-12. Update at the
start and end of each implementation session. Completed rows and historical sessions
are preserved byte-for-byte in the [history archive](archive/README.md).
Use [research state](research-state.md) for accepted conclusions and the
[research plan](signal-decay-and-alpha-plan.md) for the ordered research programme.

## Repository restructuring and maintenance — 2026-10-12

**Done — source and local maintenance:** Separated presentation assets, API
contracts and pure preview construction; repaired invalid preview inputs, cap
rounding and the relocated Alpha101 reference. Static page rendering and streaming
hash verification have measured improvements. Consolidated current docs and
preserved complete originals; compressed seven verified logs from 92.8 MB to 6.3 MB.
**Validation:** 1,691 passed / 55 optional skips; Ruff, local links, whitespace,
isolated wheel rendering, frozen bundle resources and archive hashes pass.
[Scope, measurements and recovery](repository-maintenance.md); receipts in
`var/maintenance/`. Existing uncommitted execution work and all trading/data gates
are preserved. **Deployed October 13:** guarded restart, matched reconciliation,
existing paper policy restored and application catch-up verified. Historical
partially filled orders remain in the ledger. Later source changes require their
own guarded restart; the source-identity check remains enforced.

## Execution readiness and ETF expansion — 2026-10-13

**Delivered — execution and first-wave study; research rejection ready for review:** scalable paper execution
contracts and FR25 readiness (P8.1-P8.5), then the accepted P4.16d first admission
wave, then reproducible full-admitted-pool backtests. Stage 1 inventory/rules were
reviewed and the operator instructed continuation. Preserve existing allocation
approval, reconciliation and live-disabled controls. Deliver a concrete conditional
5% FR25 / 95% F3 preview after readiness; tradability itself does not fund a strategy.
Baseline blockers: unbound FR25 financial/raw-activity inputs, first-component-only
instrument resolution and no execution contract registry. Record fresh operational
and parity evidence before calling FR25 paper-ready.

Source implementation and focused parity checks now pass; the immutable 14-ETF
execution registry contains fresh issuer/IB identities and successful account-bound
paper previews. All 38 proposed additions also have verified broker identities.
Deployment, app catch-up and the conditional allocation preview passed on October
13; allocation remains F3 100%. Recorder publication now covers 39 of 41 entries.
The October 14 retrospective study pins the completed catalog, reviews all 52
candidates and supports 50 common-window histories (BWX held, CPER zero-volume limitation).
Expanded FR25 failed the registered pre-test (67.73 bp implied cost versus 44 bp; IC −0.01463), so its portfolio replay was withheld. Original-pool 5/10 bp controls and URTH passed native parity. [Full findings](etf-expansion-findings-2026-10-14.md). Final acceptance: 1,713 full-suite tests passed / 55 optional skips, five additional preview/frozen-runner checks and 14 dispatcher regression checks (one new). App catch-up and refreshed FR25 preview passed, reconciliation matched, and the same F3 policy was restored. Final platform health is OK. Funding remains F3 100%; there is no pending allocation.
See [session evidence and acceptance](execution-readiness-2026-10-13.md).

## Current priorities

**2026-10-14 research session — Review:** P4.16d stage 1 accepted: 299
symbol/regime records (298 provisional fund references), proposed taxonomy and
complete gap matrix, 38-addition first wave alongside the original 14, frozen
proposed screening rules and file-density/capacity estimates. All 16 input
snapshots and the pinned catalog hashes verify; 11 inventory tests pass.
[Inventory report](etf-universe-inventory-2026-10-13.md). Research ingestion is
enabled; the first full supported-pool comparison is running. No allocation
change. The HYXU closure claim is corrected
from primary sources; its legacy history and new EUHY regime remain quarantined.

- P4.19 retrospective execution references complete; retain current execution policy.
  [Findings](execution-reference-findings.md). Missing fills/contracts and raw-unit
  limitations remain; this does not qualify continuous intraday research inputs.
- P4.16d: substantial ETF candidate inventory, dated taxonomy and comparable groups,
  followed by audited admission, app readiness and full-pool research.
- P6.15: measure worker memory and scheduling before expanding concurrency.
- P8.1–P8.5: minimum 14-ETF paper execution acceptance passed; broader registry
  migration and market support remain separate work.
- Last recorded paper allocation: F3 100%, revision 5, no pending change (2026-10-12
  acceptance receipt). This is historical context; consult app state before acting.

## Operating Rule

Before starting work:

1. Read `docs/industrial-platform-plan.md`, `docs/execution-kanban.md`, and `log.md`.
2. Pick the highest-priority `Pending` or `Review` item that is not blocked.
3. Move it to `In Progress`.
4. Record assumptions or blockers in the item notes.

After finishing work:

1. Move completed items to `Done` only after tests or equivalent verification pass.
2. Add evidence paths, commands, or reports.
3. Update dependent items if their status changed.
4. Add a concise entry to `log.md`.

## P0: Project Memory And Governance

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P0.7 | Pending | Decision log discipline | Every architecture or production-control decision gets a dated `log.md` entry. | Ongoing habit, not a one-time task. |

## P3: Market Data Recording And Data Quality

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P3.4a | In Progress | Pilot raw-data proving and audit loop | Record a small ETF pilot, audit raw/catalog coverage, inspect gaps/duplicates/freshness/disk use, and only then scale. | Pilot capture and historical recovery are implemented. Delayed quote samples remain inspection-only; paid real-time entitlement and admitted continuous intraday coverage remain unresolved. See [intraday recovery](intraday-recovery.md). Historical receipts remain in the archive. |
| P3.4 | In Progress | Normalized bar/quote pipeline | Convert raw records and external daily loaders into columnar golden daily/intraday tables with quality flags. | Daily serving and governed research publications exist. Remaining: normalized intraday serving, explicit source precedence/disagreement and comprehensive gap/freshness panels. Old row counts and repair receipts are historical; see [data governance](price-governance-2026-09-26.md). |
| P3.4c | In Progress | Migrate strategy, rebalance, PnL, and backtest market-data reads to ClickHouse | Signal generation, portfolio rebalance proposal generation, dashboard valuation/PnL, and stored backtests read daily bars from ClickHouse `market_data.daily_bars` instead of SQLite `price_bars`; SQLite price endpoints are either deprecated or explicitly marked legacy. | PostgreSQL/ClickHouse are the active store defaults; SQLite is explicit offline test/recovery only. App strategy decisions consume pinned governed publications. Remaining: intraday serving and full migration/soak acceptance. See [analytics migration](analytics-migration.md). |
| P3.5 | Pending | Data freshness checks | Detect stale bars, missing FX, source gaps, duplicates, and clock drift. | Alerts must be generated. |
| P3.6 | Pending | Replay a trading day | Reconstruct a paper-trading day from recorded data and compare to stored decisions. | Phase 2 exit criterion. |
| P3.7 | Blocked | Paid/primary market-data vendor | Source-of-record vendor choice and credentials are not settled. | Use IB/Yahoo/Tushare only as current interim sources. |
| P3.8 | Pending | Promote `review` series to `audited_with_limitations` | Investigate the `review` population, fix the fixable gaps, and stop conflating "fixable data gap" with "never certified". Acceptance: every reviewed series is either promoted with evidence or reclassified under an explicit permanent limitation; the decision gate in `portfolio/decision_inputs.py` then reflects a meaningful distinction. | **Deferred by the user 2026-10-10:** leave the gate as it is for now and spend effort later on promotion. Triage of batch `b02d9372…` (5,341 series; 1,056 `audited_with_limitations`, 3,482 `review`, 803 `unavailable`): all 3,482 `review` series carry the same four certification gaps (`identity_not_certified`, `raw_tape_not_certified`, `listing_boundary_not_certified`, `listing_history_not_certified`), and 3,471 also carry at least one data gap. By research role the population is `underlying-sector-hhi-20260926-v1` (3,460) and `ivv-constituents-2012-2026-v1` (680, partly overlapping), i.e. research-only constituent stocks. **Only 4 `review` series are ETFs, and none is in the trading universe: IVV (1,014 cross-source conflicts), XLF (890), XLRE (2 volume conflicts), HYXU (stale 2020 tail, 1,304 conflicts; **2026-10-13 correction:** name/symbol and mandate changed to EUHY in 2025, not a proven 2020 closure; [evidence](etf-universe-inventory-2026-10-13.md#corrected-hyxu-identity)).** Suggested tiers: (1) the four ETFs, including separately auditing HYXU/EUHY dated identity and mandate regimes; retain `review` until evidence qualifies; (2) the two data-gap classes across the constituent population — `volume_conflicts` 2,818 and `cross_source_conflicts` 2,401 — which likely share a few systemic root causes (provider volume conventions, source precedence) and so may flip in bulk from one rule fix; (3) identity and tape certification, which needs a security master and is blocked on the same access gap as P3.7/CRSP. |

## P4: Research, Backtest, And Promotion Registry

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P4.1 | Pending | Strategy spec schema | Versioned strategy spec includes universe, data, features, schedule, risk, execution, and artifacts. | Required before registry. |
| P4.2 | Pending | Strategy promotion registry | Persist state transitions from idea to retired with evidence and approval. | Should emit promotion events. |
| P4.3 | Review | LEAN integration design | Document how current strategy definitions map into LEAN or LEAN-equivalent runs. | LEAN design is implemented; reconcile the original milestone with [worker contract](lean-backtesting.md) and remaining promotion requirements. |
| P4.4 | Review | LEAN smoke backtest | One current SOTA or simplified strategy runs through LEAN path with reproducible artifacts. | Native smoke and long-history parity passed in [validation evidence](lean-validation-2026-09-26.md); do not treat historical data as certified for promotion. |
| P4.5 | Review | Backtest artifact hashes | Reports, inputs, configs, and outputs are hashed and linked to strategy versions. | Frozen bundle and output hashes plus registry exist; acceptance now concerns coverage of the broader promotion contract. |
| P4.6 | Pending | Overfit/stability gate | Promotion requires split, benchmark, turnover, fee, stress, and parameter stability checks. | Extend current SOTA workflow. |
| P4.7 | Review | LEAN runtime/dependency setup | Requires installing/configuring LEAN runtime or choosing equivalent deployment path. | Pinned local container runtime is installed and used. Prior setup blocker is superseded; P6.15 resource review remains open. |
| P4.16d | Review: first wave ingested; unchanged expanded FR25 rejected at pre-test | Substantial tradable ETF expansion, granular classes and volatility-aware ranking *(operator reaffirmed 2026-10-11)* | Versioned candidate inventory, dated taxonomy and data/contract gap matrix; staged audited admission; scalable app and paper-execution contracts; then controlled full-pool comparisons. Design capacity for hundreds of candidates, with duplicate-exposure controls and risk-normalized class ranking. | **First wave delivered 2026-10-14:** [299-record inventory](etf-universe-inventory-2026-10-13.md), 38-addition recorder wave and [50-fund current-cohort diagnostic](etf-expansion-findings-2026-10-14.md). Expanded FR25 fails the cost/IC gate; full expanded replay withheld. Class/volatility-aware design and historical membership reconstruction remain open. Research comparisons require pinned audited publication and explicit membership limitations; no provider archives or online prices as study inputs. Admission does not mandate allocation. **P4.16c remains parked behind this work.** [Plan](signal-decay-and-alpha-plan.md). |
| P4.20 | Pending | Decay-based promotion gate | Require any new signal to demonstrate a minimum estimated half-life and sub-period IC stability before it can enter a monitored recipe. | Registered October 10; depends on P4.13. Structural protection against the survivor-selection problem described in the plan's Appendix A. Governance only. |
| P4.21 | Pending | Look-through constituent alpha | Compute the structurally cross-sectional alphas on the constituent cross-section (680 IVV constituent series plus issuer holdings and sector data) and aggregate holdings-weighted to ETF scores. | Registered October 10 and deferred. The only honest route to the 76 structurally cross-sectional alphas, which need breadth that 14 ETFs cannot supply. Carries three disclosed caveats: index-membership history is a survivorship trap, issuer holdings snapshots are prospective-only from October 2026, and the constituent series are the `review`-status population from P3.8. Blocked on the constituent-coverage assessment; do not start before P4.16 answers whether the cross-sectional premise holds. |

## P5: Portfolio Blotter And Execution Controls

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P5.1 | Pending | Rebalance blotter domain model | Model current, target, proposed orders, expected cash, FX, fees, residuals, and constraints. | Stronger than current proposal preview. |
| P5.2 | Pending | Pre-trade check engine | Checks stale data, missing FX, price bands, buying power, duplicate orders, open orders, turnover, concentration, and live caps. | Must block routing. |
| P5.3 | Pending | Blotter API | Dashboard/API can show proposal, constraints, violations, and operator decision actions. | Current dashboard can be extended. |
| P5.4 | Pending | Resize/defer workflow | Operator can approve, reject, resize, defer, or cancel generated orders. | Must persist audit events. |
| P5.5 | In Progress | IB connection health gate | Confirm server time, account, managed accounts, next valid id, and profile before routing. | Read-only recurring broker health, failure backoff and reconnect wakeups exist. Preserve fresh environment/account readiness before every route; ongoing hardening and external Gateway login remain operational dependencies. |
| P5.6 | In Progress | Broker reconciliation gate | Compare IB positions, cash, open orders, fills, and commissions before routing. | Routing and EOD enforce fresh broker reconciliation; durable individual executions and reviewed recovery exist. Broader open-order/commission reconciliation acceptance remains open. See [trading operations](trading-operations.md). |
| P5.7 | Pending | Live kill switch | A hard config/runtime switch prevents live order routing immediately. | Must be tested in paper. |
| P5.8 | Pending | Live capital caps | Per-account, per-strategy, per-symbol, per-order, turnover, and drawdown caps. | Required before Phase 5. |
| P5.9 | Blocked | Live account enablement | Requires explicit human approval, credentials, account id, and proven paper evidence. | Keep live disabled. |
| P5.11 | Blocked | Intraday signal activation and stop-loss execution | Publish audited intraday bars usable for research, then add intraday routing, broker-side or monitored stops, intraday pre-trade risk checks and intraday reconciliation. Until both exist, any stop-loss research is limited to a daily-resolution approximation (a stop fills when the session low breaches it), and that approximation must be disclosed because it flatters stops in gap-down markets. | Registered 2026-10-10 from the [signal decay and alpha plan](signal-decay-and-alpha-plan.md). This is a **platform** workstream, not research: there are no intraday tables in ClickHouse, the recorder holds only raw five-second sampled quotes for five ETFs from 2026-04-04 flagged `research_approved: false`, and routing is a single monthly TWAP window. Blocked on intraday data publication plus P5.1-P5.4. |

## P6: Observability, Alerts, And Incidents

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P6.15 | Pending | Research worker deployment and resource budgets | Benchmark real host/container memory, CPU, startup/data-copy costs and whole-batch latency; compare host-native LEAN, right-sized containers and multicore scheduling. | Operator requested October 11. Fixed 4 GiB/run plus 2 GiB headroom caps LEAN at three jobs on 15.39 GiB Docker, despite 31.55 GiB host RAM. Preserve parity, resource headroom and operator/ClickHouse latency. [Plan](calculation-performance.md#p615--worker-deployment-and-resource-budget-review). |
| P6.1 | Pending | Metrics contract | Define service, data, queue, strategy, portfolio, execution, and reconciliation metrics. | Prometheus/OpenTelemetry compatible. |
| P6.2 | Pending | Local metrics endpoint | API/service exposes metrics for scraping or dashboard display. | Start with FastAPI endpoint if needed. |
| P6.3 | Pending | Grafana dashboard plan | Dashboard panels defined for data freshness, queue lag, broker state, PnL, exposure, and alerts. | Implementation depends on metrics path. |
| P6.5 | Pending | Desktop popup alert channel | Local machine popup for trading-critical warnings/errors. | Windows implementation required. |
| P6.6 | Pending | Incident registry | Alerts can open/update/resolve incidents with durable status. | Links to event ids. |
| P6.7 | Pending | Alert delivery audit | Track which channels received each alert and whether delivery failed. | Required before live. |
| P6.8 | Blocked | SMS/push provider | Requires provider choice and credentials. | Email exists; urgent channel pending. |

## P7: Daily Operating Loops

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P7.1 | Pending | Daily post-trade report | Generate PnL, attribution, slippage, fills, reconciliation, and alert summary. | Uses `.agents/skills/daily-post-trade-analysis.md`. |
| P7.2 | Pending | Continuous research report | Daily/weekly challenger report updates research state and candidate status. | Uses `.agents/skills/continuous-research-loop.md`. |
| P7.3 | Pending | Robustness review report | Weekly service/data/queue/broker/alert health review. | Uses `.agents/skills/system-robustness-review.md`. |
| P7.4 | Pending | Promotion review report | Formal approve/reject/defer/retire artifact for strategy transitions. | Uses `.agents/skills/strategy-promotion-control.md`. |
| P7.6 | Pending | Disaster recovery drill | Backup and restore check for trading-critical local state. | Required before live. |

## P8: Execution Generality

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P8.1 | Done for the reviewed US-listed USD ETF boundary | Contract identity registry | IB `reqContractDetails` captured raw, audited and published as an immutable hash-versioned registry carrying `conId`, `secType`, `localSymbol`, exchanges, currency, multiplier, `minTick` and trading class. Ambiguity fails closed. Re-derivable from retained raw evidence. | Foundation for everything else. Uses the existing raw-first, audit, publish discipline rather than a new pattern. |
| P8.2 | Done for the reviewed US-listed USD ETF boundary | Symbol to contract resolution | Resolution requires explicit disambiguation keys (ISIN, or exchange plus currency hint) and rejects ambiguity instead of guessing. Deterministic and recorded per decision. | The hard correctness problem: `BHP` is an ADR on NYSE and a listing on LSE and ASX. A ticker-only lookup is the failure being retired and must not return as the new default. |
| P8.3 | Partial: frozen membership and component unions implemented | Registry-backed universe selectors | Universes become declared selectors over the registry plus explicit membership, replacing the literal `Instrument` dicts in `research/etf_universe.py`, `all_weather_universe.py` and `stock_universe.py`. Existing universes resolve identically to today. | A new instrument then costs a registry entry, not a code edit. Research definitions keep their frozen membership. |
| P8.4 | Done for the reviewed US-listed USD ETF boundary | Instrument admission gate | A contract is tradable only when identity is verified, an audited price history exists, a CNH FX path exists, IB reports it tradable for this account, and its market rules are registered. Admission is an immutable event and every instrument can answer "why not tradable". | Admission stays narrow and reviewed; capability is what generalises. |
| P8.5 | Done for the reviewed US-listed USD ETF boundary | Capability check replacing the hard-coded allocation gate | The shared conservative execution-contract check is extended to verified instrument capabilities: a strategy is allocation-supported when every instrument in its resolved universe is admitted for execution and its execution contract is registered. FR25 and M1/14 become allocatable by admitting XLE and XLB, with no code change. | 2026-10-13: UI/backend share the registry-backed check; FR25/M1 admission and the conditional FR25 preview passed. First customer is deliberately XLE/XLB, which are US-listed USD ETFs, so P8.1-P8.5 need no FX, calendar or data widening. |
| P8.6 | Blocked | Per-currency CNH FX path | Non-USD instruments valued and reconciled in CNH with point-in-time discipline and a declared authoritative source per pair. | **Blocked on data, not engineering:** FX is a documented unresolved input class. Until it is resolved, "any IB tradable" silently means "any USD tradable". |
| P8.7 | Pending | Per-venue calendars and execution windows | Each listing venue has its own session calendar and an execution window in its own timezone, with a defined convention for asynchronous sessions and an explicit valuation date. | `exchange-calendars` is already a dependency. Today routing assumes US sessions only (`live/sota.py:113,281`). |
| P8.8 | Pending | Lot size, tick and minimum-size enforcement | HKEX board lots and TSE hundred-share lots cannot produce an invalid quantity; venue tick regimes enforced at sizing. | The US ETF registry validates whole-share support and cent ticks. Board-lot multiples, non-US tick regimes and broader multipliers remain unsupported. |
| P8.9 | Blocked | Multi-currency governed price lane | Non-USD and non-ETF series admitted through the existing audit and publication process, with per-venue sources, retention rights, basis and corporate-action coverage. | **Blocked on source and licence decisions.** `research/governed_refresh.py:144` currently requires `currency == "USD"` and `instrumentType == "ETF"`. |
| P8.10 | Pending | Generalised exposure, staleness and reporting | Country and currency aggregation, staleness checks and reports correct across venues and calendars. | Reconciliation itself matches on `order_ref` and is already symbol-agnostic, so this is mostly free. |

## Next Recommended Work Order

Revised after the 2026-10-11 second review. The research queue is now governed by the
[signal decay and alpha plan](signal-decay-and-alpha-plan.md); the items below
are the cross-cutting platform work that runs alongside it.

**Research, one item at a time with a review between items.** The second review and the
fixed P4.18 experiment and the scoped P4.19 retrospective comparison are complete. Next
review the **P4.16d first-wave rejection** ([findings](etf-expansion-findings-2026-10-14.md)), then separately register comparable-group and volatility-aware ranking before another cross-sectional
alpha study. Register horizon, peer-group, incremental payoff and actual fill-based exit
contracts before any new budget/TP/SL grid. See the current priorities at the top of the plan.

**Platform, in parallel:** the new **P8** execution-generality phase
([plan](execution-generality-plan.md)) removes the 12-ETF assumption. Its critical
path P8.1–P8.5 is deliberately narrow — XLE and XLB are US-listed USD ETFs, so
opening the 14-ETF allocation gate needs no FX, calendar or data widening — and
it replaces the hard-coded strategy gate so the next strategy needs no code edit.

Platform and data work, in parallel:

1. Qualify original-release sector and energy history — the standing prerequisite for any new feature block. Historical EIA/CFTC/issuer observations are captured prospectively and are not admissible for earlier decisions; this remains unresolved and blocks new feature blocks that depend on it.
2. Resolve the IB market-data entitlement blocker (IB 10089/420 for `reqRealTimeBars`) so live capture can move off the delayed sampled channel, which is inspection evidence and not complete interval OHLCV. This is a precondition for P5.11.
3. P3.8: promote `review` series where the gaps are fixable, starting with the four ETFs (IVV, XLF, XLRE, and resolving the HYXU/EUHY mandate transition without splicing the stale series), then the two data-gap classes that likely share systemic root causes.
4. P3.4: add ClickHouse source-observation tables, source precedence, cross-source disagreement checks and the daily gap/source-disagreement panels.
5. P4.1: define the versioned strategy spec schema, then P6.1 metrics and P5.1 the stronger rebalance blotter domain model.
6. Register the remaining governed-data cleanups as small items: the two private-name couplings between `research_etfs` and `governed_refresh`, and the absence of a published-batch list route in `web/governed_data.py`.

**Deferred / not started by this plan:** P4.21 (look-through constituent alpha)
until the next look-through research design and required published inputs are accepted; P5.11 (intraday activation and stops) until audited intraday
data is published and an intraday execution stack exists.
