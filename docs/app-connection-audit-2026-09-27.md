# Cross-application connection audit — 2026-09-27

The two reported symptoms are confirmed. The broader problem is that individual
features have their own definitions of active history, target portfolio, data
readiness and service status. They share some low-level functions, but do not
consistently share the context that determines which facts belong together.

This is an audit and proposed repair register, not an implementation or promotion
decision. No application code, portfolio baseline, approval policy, strategy
selection or broker order was changed. Existing uncommitted work was preserved.

## Evidence and scope

- Inspected Trading, Strategies and the full SOTA report, System, and Market Data
  in the running browser, plus eight local API responses.
- Traced portfolio/reset, executions, attribution, account snapshots, EOD jobs,
  target selection, governed inputs, analytics publication, health, alerts and
  database handoff through their producers and consumers.
- Captured runtime evidence at 2026-09-27 15:39 UTC. A later read of the latest
  reconciliation confirmed a matched six-position account at 15:42:28 UTC.
- Ran **109 existing tests successfully; two optional integration tests skipped**.
  Covered opening resets, accounting read reuse, account performance, execution
  histories, analytics publication, initial allocation, monthly staging and blotter
  filters. This was a focused audit suite, not the full application suite.
- Separate in-memory probes reproduced compaction/reference-P&L disagreement,
  pre-baseline historical-query leakage, missing-FX false completeness and stale-FX
  acceptance. They never connected to a broker or wrote the production ledger.

Local receipts: [runtime observations](../var/research/link-audit-runtime-20260927.json),
[offline reproductions](../var/research/link-audit-probes-20260927.json),
[existing test results](../var/research/link-audit-existing-tests.xml).
Reproduction programs are retained beside those receipts.

Evidence labels below distinguish a **runtime reproduction**, **offline
reproduction**, **code-confirmed gap**, and **known missing integration**. A
code-confirmed gap describes a reachable path; it does not assert that every
failure scenario has occurred in the current portfolio.

## Prioritized register

P1 means incorrect financial interpretation, historical contamination or an
essential operational dependency. P2 means presentation, diagnosability or a
documented completeness/portability gap. These are repair priorities, not claims
that a live order was placed incorrectly.

| ID | Priority | Connection that is missing or inconsistent | Evidence |
| --- | --- | --- | --- |
| C01 | P2 | Shared application layout does not govern all four workspaces | Browser + code |
| C02 | P1 | Portfolio inception/reset is not a shared monitoring context | Runtime + code |
| C03 | P1 | Execution attribution, slippage and missed orders use different scopes and event units | Runtime + code |
| C04 | P1 | Accounting compaction does not preserve reference-fill attribution | Offline reproduction |
| C05 | P1 | Historical P&L queries can consume a baseline from their future | Offline reproduction |
| C06 | P1 | Reset/fill revisions do not invalidate EOD completion state | Code-confirmed gap |
| C07 | P1 | EOD catch-up can label a current broker portfolio with a historical date | Code-confirmed gap |
| C08 | P1 | Holdings comparison and rebalance controller select targets differently | Code-confirmed gap |
| C09 | P1 | Audited strategy reports and trading decisions read different price histories | Code-confirmed gap |
| C10 | P1 | Recurring ingestion does not publish the new audited batches that tracking needs | Code-confirmed gap |
| C11 | P1 | Price basis/source identity is lost between storage, strategy decisions and proposals | Code-confirmed gap |
| C12 | P1 | Missing/stale valuation inputs are handled differently across P&L, NAV and readiness | Offline reproduction + code |
| C13 | P2 | Account NAV, local P&L and broker P&L have no complete economic reconciliation | Known missing integration |
| C14 | P2 | A research calculation failure can stop account-performance publication | Code-confirmed gap |
| C15 | P2 | System Gateway health is disconnected from ongoing broker observations | Runtime + code |
| C16 | P2 | Analytical freshness and alert delivery are outside consolidated health | Code-confirmed gap |
| C17 | P2 | Database handoff does not include all dependencies needed to reproduce the app | Known missing integration |

### C01 — Four pages, multiple independent visual systems

Trading injects a separate CSS/layout layer into the older operator template. It
has a dark 68-pixel header, different spacing and card styles. Strategies, System
and Market Data retain independently embedded white-header templates. Changes
to Trading therefore do not propagate to the other workspaces. Navigation links
do exist; the missing connection is common presentation ownership.

Evidence: [Trading composition](../src/systematic_trading/web/operator.py),
[Trading CSS](../src/systematic_trading/web/trading_workspace.py),
[System/Market Data templates](../src/systematic_trading/web/platform.py),
[strategy report renderer](../src/systematic_trading/backtest/reporting.py).

Proposed repair: one application shell, navigation component and design tokens,
with reusable cards, tables, date controls, freshness and empty/error states.
Keep exportable research reports supported. Acceptance: all four workspaces and
an embedded strategy report visibly share those components at desktop/mobile sizes.

### C02 — No portfolio lifecycle contract

`PnLBaseline` carries an accounting cutoff and optional account reset timestamp,
but there is no portfolio lifecycle record consumed by all monitoring services.
Account performance derives tracking start from the first snapshot with holdings;
the blotter defaults to Today; proposals are listed by status across history;
missed-order analysis reads all orders. These are separate policies, not one
portfolio start date propagated through the app.

The current baseline is `d229466e93af`, with cutoff
`2026-09-25T03:59:59.999999Z`: immediately before September 25 in New York. The
account chart deliberately retains a September 24 opening-capital anchor. That
anchor is useful and should be labelled explicitly, not counted as a trading day.
The current tracking date is September 25. Research's September 28 prospective
date has a different purpose and must remain independent.

Evidence: [baseline model](../src/systematic_trading/domain/pnl.py),
[portfolio models](../src/systematic_trading/domain/portfolio.py),
[dashboard scope selection](../src/systematic_trading/web/api.py),
[blotter date controls](../src/systematic_trading/web/trading_workspace.py),
[opening reset](../src/systematic_trading/live/pnl_reset.py).

Proposed repair: a versioned portfolio context identifying account/environment,
monitoring episode, start session and exact UTC boundary, trading timezone,
reporting currency, opening state and approved strategy deployment. Every
monitoring read resolves this once. Keep the accounting compaction cutoff separate
from inception. Acceptance: changing the selected episode changes all portfolio
metrics together; All history remains available for audit.

### C03 — Attribution mixes reset P&L with lifetime execution history

The runtime execution-quality API reports **220 missed orders**, all with missed
timestamps before the current reset, and **24 filled order rows**, of which **18
predate the reset**. Local P&L correctly uses subsequent individual executions.
The displayed execution gain is **CNH -983.04**, while its **-197.24 bps** is
computed from the lifetime slippage rows and their CNH 15,015,183.97 notional.
Restricting the existing order rows to the six current orders gives approximately
**-11.57 bps**. This calculation is diagnostic, not a replacement official metric:
execution-level FX and rounding must also be aligned.

`dashboard_execution_quality()` never applies the baseline or `as_of` to missed
records. `_execution_slippage_rows()` uses cumulative order quantity, average
price and submission/update time, whereas the P&L ledger uses each execution's
quantity, price and fill time. A TWAP crossing a boundary cannot be fixed safely
by filtering only the parent order's date. The current P&L count of 48 represents
execution slices; the attribution count of 24 represents lifetime orders.

Evidence: [execution-quality builder and slippage helpers](../src/systematic_trading/web/api.py),
[execution-level P&L ledger](../src/systematic_trading/live/pnl.py).

Proposed repair: a shared scoped execution ledger for P&L, reference P&L, notional,
bps, counts and charts. Associate misses with their intended trading session and
portfolio episode, not the time a later sweep noticed the expiry. Label order and
execution counts separately. Acceptance: summaries equal their constituent rows,
and pre-start misses appear only in audit history; spanning TWAPs are split by fill.

### C04 — Compaction erases reference execution differences

Both actual and reference P&L initialize from the same actual-cost baseline.
`build_pnl_baseline()` preserves actual lots/realized P&L but does not preserve the
reference-cost ledger. Once fills are compacted, reference P&L inherits actual
cost and their historical execution difference disappears.

Offline reproduction: buy ten shares at 101 against a 100 reference, with FX 7.
Before compaction, actual/reference P&L are 1,330/1,400 and execution difference
is -70. After compaction they are 1,330/1,330 and the difference is zero, while
the slippage rows still report -70.

Evidence: [baseline creation and P&L initialization](../src/systematic_trading/live/pnl.py),
[reproduction receipt](../var/research/link-audit-probes-20260927.json).

Proposed repair: preserve both accounting bases or preserve a complete execution
attribution accumulator. Acceptance: compaction leaves every economic metric and
historical comparison unchanged; a deliberate new portfolio episode remains a
different operation.

### C05 — Historical reads use the latest baseline regardless of date

`_build_pnl_snapshot(as_of=...)` always loads `latest_pnl_baseline()`. There is no
guard against a baseline after the requested date. `_pnl_comparison_history()`
also recomputes historical reference values using that latest baseline.

Offline reproduction: a baseline through August 4 caused an August 3 query to
return ten shares bought on August 4, marked `valuation_complete=true`.

Evidence: [P&L builder](../src/systematic_trading/live/pnl.py),
[history recomputation](../src/systematic_trading/web/api.py),
[reproduction receipt](../var/research/link-audit-probes-20260927.json).

Proposed repair: select a valid historical checkpoint and replay only eligible
events, or explicitly reject unsupported historical reads. Store paired
actual/reference observations with their episode and input revision. Acceptance:
no future holding/baseline enters an earlier date; results remain stable after
compaction.

### C06 — EOD completion is not keyed to the portfolio or ledger revision

The management loop treats `last_eod_pnl_date == service_date` as completion.
Reset handlers save a baseline without invalidating that marker. Backlog selection
uses `last_eod_date` and pending dates without a portfolio inception boundary.
A reset, recovered execution, or corrected input can therefore leave a previously
completed date unchanged; downtime can also preserve obsolete pre-start jobs.

Evidence: [EOD readiness/backlog](../src/systematic_trading/live/management_service.py),
[reset write](../src/systematic_trading/execution/reconciliation.py),
[opening reset](../src/systematic_trading/live/pnl_reset.py).

Proposed repair: completion keys include episode, ledger revision and valuation
input revision. Reset/recovery events invalidate affected derived results and
wake the relevant app worker. Acceptance: same-day reset/recovery is reflected
without hand-editing state files; pre-inception monitoring jobs are excluded while
real unresolved order obligations remain visible and continue to block routing.

### C07 — Catch-up dates can be attached to today's broker holdings

During an EOD backlog, `_run_eod()` calls
`fetch_and_write_account_snapshot(as_of=service_date)`. That function requests
current account summary/positions from IB and assigns the supplied date. Account
performance later groups and values snapshots using that `as_of`. `captured_at`
is retained, but does not prevent this current observation from being used as a
historical portfolio. This is a reachable catch-up path, not a claim that the
current four displayed account points have been corrupted.

Evidence: [EOD snapshot call](../src/systematic_trading/live/management_service.py),
[snapshot capture](../src/systematic_trading/live/account_snapshot.py),
[account NAV history](../src/systematic_trading/web/api.py).

Proposed repair: distinguish observation time, valuation session and reconstructed
historical state. Backfill historical holdings from eligible ledger evidence or
leave the day unavailable. Acceptance: simulating two missed sessions cannot
backdate the current broker portfolio into either historical session.

### C08 — The holdings screen and controller have different target selectors

The holdings endpoint takes the newest live-plan file by modification time;
otherwise it takes the first stored proposal. It does not require an approved,
current-strategy, post-reset target. The drift controller instead selects an
approved current-sleeve target in the monthly window, after reset, or reconstructs
the scheduled target. A newer rejected/pending plan or copied historical file can
therefore alter the screen without altering the controller's active target.

At inspection both paths happened to use the September 24 initial-allocation
target. The SOTA report correctly had separate scheduled held/target weights and
September 25 indicative targets. Those legitimately differ; the app should
explain and link their roles rather than force numerical equality.

Evidence: [holdings target selector](../src/systematic_trading/web/api.py),
[controller target selection](../src/systematic_trading/live/initial_allocation.py),
[tracked state](../src/systematic_trading/research/tracked_runtime.py).

Proposed repair: shared target-resolution service with explicit approved active,
last scheduled and indicative roles, decision dates and source IDs. Acceptance:
pending/rejected/unrelated/newly copied files cannot silently become the active
holdings-comparison target.

### C09 — Strategy reports and trading decisions have separate price authority

Tracked SOTA/challengers read the committed governance batch and verify pinned
files. `build_sota_live_rebalance_plan()` reads `store.list_price_bars()` from the
legacy daily-bar serving table. The live refresh path writes Yahoo adjusted bars
with IB fallback. Sharing strategy overlays does not make these different input
histories equivalent, and a newly audited correction does not update the trading
reader automatically. Earlier documentation explicitly retained this separation;
it is still an unresolved connection, not a newly discovered migration.

Evidence: [tracked input contract](../src/systematic_trading/research/tracked_inputs.py),
[trading signal inputs](../src/systematic_trading/live/sota.py),
[operational refresh](../src/systematic_trading/live/market_data.py),
[existing governance limitation](price-governance-2026-09-26.md).

Proposed repair: declare and pin input policy per deployed strategy, verify
same-date signal/target parity, and migrate the reader through a governed
deployment. Acceptance: every difference between displayed research targets and
deployed targets is explained by strategy version, decision date, policy or input
revision. Do not silently switch execution to a new research dataset.

### C10 — Tracking has a consumer but no recurring audited-price publisher

The analytics worker notices new `governance/catalog` publications. Routine market
refresh/backfill updates the daily-bar table, not that catalog. The governance
builder/publisher are separate scripts; the current builder has a fixed
`CUTOFF='2026-09-25'`. No recurring producer connecting acquisition, audit and
committed governed publication was found in the app/service startup path.

Thus tracked calculations can remain at September 25 even while ordinary market
bars advance. This is not yet a missed trading session at the Sunday inspection;
it is a gap before the declared September 28 prospective start. The Refresh
calculations button cannot obtain a newer audited batch by itself.

Evidence: [tracked inputs](../src/systematic_trading/research/tracked_inputs.py),
[analytics jobs](../src/systematic_trading/research/analytics_service.py),
[fixed-date builder](../scripts/build_governed_prices.py),
[publisher](../scripts/publish_governed_prices.py),
[service manifest](../config/service-manifest.json).

Proposed repair: application-owned acquisition → audit/quarantine → verified
publication → strategy refresh, with per-symbol/session coverage and failure
status. Acceptance: a new observed session produces a new committed batch and
tracked output without an agent or manual research job; a failed audit retains
the previous batch and visibly reports the coverage delay.

### C11 — Data lineage is discarded before it reaches a proposal

ClickHouse rows can retain source, adjustment, availability and quality flags,
but `list_price_bars()` reduces them to `PriceBar` OHLCV/date. `PriceBar` and
`FXRate` have no basis, vintage or publication reference. Generic platform writes
use `platform_market_data_store` and default adjustment metadata, losing the
original provider selected by the live refresh. `TradeProposal` does not bind
the consumed data hashes or complete executable strategy version.

This prevents a direct proposal → exact signal → audited input → displayed market
series audit trail. Adjusted return research and actual-share valuation also need
different, explicitly supported basis contracts, especially around corporate
actions. This inspection establishes missing enforcement, not a measured current
split-related accounting error.

Evidence: [market models](../src/systematic_trading/domain/market.py),
[storage adapter](../src/systematic_trading/market_data/store.py),
[source row contract](../src/systematic_trading/market_data/golden.py),
[proposal model](../src/systematic_trading/domain/execution.py).

Proposed repair: typed, versioned market observations plus a decision receipt
carrying strategy/input hashes, basis, availability, coverage and target identity.
Acceptance: a proposal can reproduce its original inputs after a new data vintage
is published; unsupported basis or availability cannot pass as an audited input.

### C12 — Valuation completeness does not follow input completeness

P&L can skip a fill for missing FX and still return `valuation_complete=true`,
zero position and zero P&L. An offline probe reproduced this with one filled order.
Another probe accepted January FX for an August valuation without a stale warning.
P&L also permits later valuation-date FX when fill-date FX is absent.

The account NAV path has a different policy: it can substitute average cost when
market price is missing, and only warns after four calendar days for FX. Order
readiness has stricter same-session checks. `_run_eod()` marks a saved snapshot
ready without explicitly checking `valuation_complete`.

Evidence: [P&L fill/valuation handling](../src/systematic_trading/live/pnl.py),
[account NAV valuation](../src/systematic_trading/web/api.py),
[readiness](../src/systematic_trading/live/initial_allocation.py),
[EOD persistence](../src/systematic_trading/live/management_service.py),
[probe results](../var/research/link-audit-probes-20260927.json).

Proposed repair: shared session-aware valuation policy returning values,
observation dates, quality and explicit missing components. Missing accounting
inputs must remain incomplete; average cost must not become performance NAV.
Acceptance: missing/stale prices or FX cannot create a zero/complete result or a
successful EOD publication, and later FX cannot silently value an earlier trade.

### C13 — There is no complete NAV-to-P&L economic bridge

The account series measures NAV change including external cash flows. Local P&L
is a securities fill/mark ledger and explicitly excludes commissions/fees; it has
no complete cash-flow, dividend, interest, corporate-action or cash-FX attribution
ledger. Live IB P&L uses broker periods and currencies. The current screen correctly
discloses these distinctions, but there is no reconciliation explaining the gap.

Runtime example: the opening-to-latest account NAV change was CNH 1,500.84,
whereas local security P&L was CNH 977.08. The CNH 523.76 difference is not labelled
as a particular fee, cash flow or FX contribution by this audit; its causes need
the missing evidence. Broker totals were displayed in HKD and positions in USD.

Evidence: [account series and return](../src/systematic_trading/web/api.py),
[P&L ledger](../src/systematic_trading/live/pnl.py),
[broker P&L service](../src/systematic_trading/live/broker_pnl.py),
[execution fill model](../src/systematic_trading/domain/execution.py).

Proposed repair: a reconciled economic ledger and a bridge from opening NAV,
external flows, market/FX P&L, income and costs to closing NAV, plus an explained
broker/local difference. Preserve the broker-native feed. Acceptance: portfolio
returns are flow-adjusted and every residual is either attributed from evidence
or explicitly unresolved. A start-date setting alone cannot supply missing data.

### C14 — Research refresh can block operational performance freshness

`AnalyticsService.refresh()` runs tracked research before account jobs. A tracked
calculation error explicitly skips both strategy-serving and dashboard-serving.
Long native runs also delay subsequent jobs in the same worker. Account imports
may eventually succeed, but the published account-performance chart is held back
because it is bundled with the strategy comparison. That endpoint checks baseline
identity but does not attach the analytics worker's error status as the strategy
endpoint does.

Evidence: [job ordering/failure branch](../src/systematic_trading/research/analytics_service.py),
[combined performance publication](../src/systematic_trading/research/analytics_projection.py),
[dashboard read](../src/systematic_trading/web/api.py).

Proposed repair: independently publish account state and strategy state, each with
its own revision/freshness, then align them for comparison. Acceptance: a failed
or slow challenger calculation leaves account updates available and identifies
the stale strategy side without computing legacy substitute results.

### C15 — Gateway health is an old probe, not an ongoing observation

At capture, System reported a Gateway error because its probe was **37,931 seconds
old**. Subsequent reconciliation was matched at 15:42:28 UTC with six positions.
The manifest marks the standalone state file stale after 180 seconds; startup and
the separately invoked watchdog refresh it. The main health endpoint does not
update that evidence from ongoing broker services. The automation status response
also retained an older reconciliation timestamp than the latest reconciliation
file. These are different status sources presented without a unified account view.

Evidence: [Gateway manifest](../config/service-manifest.json),
[health aggregation](../src/systematic_trading/app.py),
[startup probe](../scripts/start_local_platform.ps1),
[watchdog probe](../scripts/watch_local_platform.ps1),
[management status](../src/systematic_trading/live/management_service.py).

Proposed repair: scheduled probe ownership and a shared observation model showing
transport, account subscription, orders, market data and reconciliation separately.
Acceptance: a stale diagnostic reads "probe stale/unknown" rather than asserting
broker failure, while real connection/reconciliation failures still block the
appropriate operations. A successful account call does not prove feed entitlement.

### C16 — Analytics and alert-delivery failures are outside System health

Analytics has its own `/analytics/status`, but the consolidated service graph and
health response do not include its worker or data coverage. Missing SMTP
configuration or failed email delivery is written to local error logs rather than
surfaced as delivery health with a receipt. Portfolio-alignment warnings are
recorded with `notify=False`. Therefore a service being "running" or an alert
being recorded does not establish that calculations are current or an operator
was notified. No notification was sent during this audit.

Evidence: [application health](../src/systematic_trading/app.py),
[analytics status](../src/systematic_trading/research/analytics_service.py),
[alert delivery](../src/systematic_trading/live/alerts.py),
[alignment event](../src/systematic_trading/live/management_service.py).

Proposed repair: add dataset/worker readiness and alert delivery results to the
same health model, with explicit channel configuration, delivery/failure state,
deduplication and resolution. Define which persistent alignment blocks deserve
notification. Acceptance: a failed calculation or configured delivery failure is
visible on System and the affected page; transient states do not create alert spam.

### C17 — A successful database handoff is not a complete application handoff

NAS synchronization snapshots PostgreSQL and the configured SQLite recovery file.
It does not migrate ClickHouse, raw/governed evidence or the model/FX files needed
by tracking. The tracking configuration contains absolute D: file paths and
governance provenance also points to local immutable files. This exclusion is
documented, but increasingly conflicts with the app's dependence on those files
and analytical publications after switching PCs or restoring state.

Evidence: [handoff configuration](../config/database-sync.json),
[snapshot implementation](../src/systematic_trading/storage/nas_sync.py),
[tracking dependencies](../config/strategy-monitoring.json),
[existing documented boundary](database-sync.md).

Proposed repair: a versioned application dependency/restore manifest covering
transactional and analytical data plus immutable model/input artifacts, with
portable resolution and preflight verification. Acceptance: a clean second-machine
restore can serve the same portfolio/report revisions and replay them, or explicitly
blocks with the precise missing dependency. Retain single-writer ownership checks.

## Proposed shared contracts and repair sequence

The user's portfolio start date should become part of a **portfolio context**, not
separate filters added to each widget. Its initial migration can derive September
25, New York, from the existing verified opening reset; that is a proposed mapping,
not a change made by this audit. Preserve the opening-capital anchor separately.

1. **Portfolio/accounting foundation — C02–C07 and C12.** Establish episode and
   temporal contracts; shared execution queries; paired actual/reference accounting;
   revision-aware EOD; strict valuation quality. Migrate existing baselines without
   rewriting original fills, approvals or snapshots. Replay and compare before
   serving the new results.
2. **Strategy/data connection — C08–C11.** Establish target roles and decision
   receipts, build the app-owned audited-publication lifecycle, then verify any
   deployed-reader migration. Tracking continues to confer no execution authority.
3. **Common presentation and observability — C01 and C14–C16.** Use one shell and
   freshness model; decouple account refresh from research; make health and alert
   delivery reflect their actual observed states. The visual shell can be worked
   on independently once implementation is selected.
4. **Complete economics and portability — C13 and C17.** Ingest missing economic
   events and verify a complete restore/replay path. These are broader additions
   requiring real source evidence, not just UI cleanup.

Every portfolio monitoring response should identify its episode, effective window,
valuation session, source revision, completeness and calculation time. The UI may
share a selected window within portfolio monitoring, while research keeps its own
historical/prospective windows. Chart zoom is a view choice, not an accounting reset.

Working orders, uncertain submissions and unresolved reconciliation issues remain
safety obligations even if they originated before monitoring inception. A date
filter must never hide them from routing checks. Keep explicit audit-history access,
paper-first defaults, live-disabled controls and existing approvals throughout.

## Connections already present that should be preserved

- Actual local P&L already respects the opening reset and individual execution times.
- Account performance rejects a saved publication from a different baseline.
- Individual execution identities, transactional reconciliation and idempotent order
  controls are covered by the passing focused tests; do not replace them with a UI filter.
- Trading and research share strategy components, and monitored candidates remain
  separate from deployed SOTA and order authority.
- Tracked calculations are app-owned and verify their governed batch/model inputs;
  shared chart navigation is already used across several reports.
- Live broker P&L correctly retains native currencies and explicit stale timestamps.

The audit does not claim a live-readiness certification, a complete cash/commission
reconciliation, a restore drill, or that each code-path risk has occurred in production.
The register is the reviewable scope for deciding which repairs to implement.
