# Architecture

## Dated trading allocations

The operator can designate SOTA separately from a dated paper trading allocation.
Transactional state and immutable events own approvals and handovers; the app's
management and analytics services own activation, virtual strategy accounting and
replay. Proposals bind to allocation versions and verified model/data publications.
See [Trading allocations](trading-allocations.md) for contracts and limitations.

## Shared application contracts

The [economic vintage recorder](economic-vintage-recorder.md) extends Market Data
with app-owned ALFRED acquisition and independently committed snapshots/catalogs.
Raw evidence, date-level archive availability and actual first capture are separate.
Pinned readers verify hashes, require explicit historical availability assumptions,
reject stale inputs and never substitute a later vintage. This research-only panel
does not alter active strategy inputs or execution authority.

The expanded eleven-series registry distinguishes seven leading candidates from
payroll, production and inflation context. Named predecessor hashes permit only
additive series extensions with unchanged existing definitions and schedules;
old publications remain addressable by their original catalog and snapshot hashes.
Feature groups have independent readiness, no fills and explicit daily-archive
availability. Regional forward surveys retain their own identity; national PMI
and consensus feeds are visible source gaps, not inferred data.

Intraday acquisition has a separate app-owned recovery worker with a durable
per-window ledger, raw-first writes, transactional outbox batches and bounded
IB pacing. It runs alongside streaming and resumes six-month 5-second history
after outages, including closed-market days. Recovery has no order authority;
its observations remain unapproved raw evidence. See [intraday recovery](intraday-recovery.md).

The [connection repair record](app-connection-repairs-2026-09-28.md) documents the portfolio, data and recovery boundaries. `portfolio/context.py` resolves the monitoring episode independently of accounting compaction. `portfolio/targets.py` selects approved deployed targets; `portfolio/valuation.py` applies observed mark/FX freshness; `portfolio/revision.py` invalidates derived EOD results. Paired actual/reference checkpoints and dated executions support replay without future-baseline leakage. Broker capture time cannot be reassigned to a historical session.

Production decisions and strategy tracking consume hash-pinned published governed inputs. The application-owned `research/governed_refresh.py` producer audits and verifies a complete supported ETF batch before publishing its catalog pointer. Research and operations projections run independently and expose their errors/freshness. The economic cash ledger bridges NAV to security P&L, flows, income, costs and cash FX; unresolved differences remain visible and suppress reconciled flow-adjusted returns.

The research analytics lane also owns recorder-first ETF admissions through
`recorders/research_etfs.py`, using the same verified publisher. Research-source
failures retain the last complete catalog and do not suppress independent jobs.
Verified inherited delta files and their physical publication receipts survive
subsequent active-universe refreshes without an unbounded parent chain. Market
Data exposes recorder coverage and quarantine status. See the
[bill recorder and parking contract](bill-recorder-and-parking.md).

`web/shell.py` owns the shared workspace presentation. Application health includes recurring broker probes, calculation workers and durable delivery receipts. NAS SQL snapshots carry external dependency manifests; missing analytical data/artifacts defer incoming restore before database mutation. Paper/live gates and checks preventing replacement of active local databases remain mandatory.

The governed historical-price research layer is documented in
`docs/price-governance-2026-09-26.md`. Immutable batches in
`market_data.governed_daily` and `market_data.governance_comparisons` retain
explicit adjustment bases, source lineage and overlap/gap audits. ClickHouse
analytics publications commit a catalog only after complete row/document hash
verification. The read-only Market Data governance API serves committed
workspace-scoped batches. This layer does not change the production daily-bar
reader, broker execution contracts or strategy selection.

Local two-PC operation uses [optional NAS backups](database-sync.md):
local PostgreSQL/SQLite engines, local recovery checkpoints and verified immutable
NAS snapshots. Latest observed database revisions win; unchanged copies retain
their age, publication is serialized and incoming restores require stopped services.
NAS failures defer sync without blocking startup/shutdown. Interrupted local
restores still block application access. It does not replicate ClickHouse, broker configuration or raw
market-data files, and it does not change execution approval or reconciliation gates.

## Target State

The embedded trading management loop owns an optional paper automatic-approval controller. Its machine/profile/strategy-bound policy defaults off and is audited locally and in the event outbox. Eligible new strategy proposals pass fresh account, data, sizing, exposure, open-order and session checks before a compare-and-set approval and normal idempotent router handoff. A durable attempt claim precedes submission; restarts never retry uncertain attempts. SQLite and PostgreSQL approval decisions support expected-status checks. Read-only post-trade TWAP jobs use a separate IB client and retain observed bars in `var/execution_benchmarks/`.

The target architecture is an industrial 24x7 systematic trading platform: micro-services connected by a message queue, immutable market-data recording, columnar analytics storage, transactional order and approval state, LEAN-compatible backtesting, Interactive Brokers execution, strong portfolio rebalancing controls, and Grafana-class monitoring.

The full target-state system chart and execution schedule are maintained in `docs/industrial-platform-plan.md`.

## Current State

Analytical histories and prepared Strategy/account performance responses use a
verified ClickHouse projection worker. Requests read the last complete publication;
source changes refresh it in the background. PostgreSQL retains transactional
authority and original files remain replay evidence. See [analytical migration](analytics-migration.md).

Tracked rolling models use an isolated application fitting process, with parallel
monthly fits, hash-verified model caches and portable inference shared by Python
and native LEAN. The analytics worker publishes complete strategies and matched
controls together after parity checks. The report exposes training lineage and
the executable allocation trace. See [rolling XGBoost tracking](rolling-xgboost-lag20-tracking.md).

The current implementation is the v0 control plane and research harness. It is intentionally Python-first, local-first, and paper-first while the contracts, tests, and operator workflow are hardened.

The operator's live PnL is a dedicated read-only IB account/position subscription,
with an independent client ID and cached HTTP reads. Account totals retain the
broker base currency and position rows retain contract currency. Missing/stale
callbacks do not fall back to historical daily marks.
Last received values remain visible with explicit stale timestamps and connection
status after hours or during an HTTP refresh failure; missing fields remain
unavailable individually. Dashboard panels load independently. Accounting reuses
identical ledger/FX/price reads only within a calculation, never across requests.

The [LEAN worker](lean-backtesting.md) consumes hash-verified frozen D: inputs and
runs the existing strategy inside a pinned, network-isolated container. LEAN owns
simulated orders, fills, portfolio and cash; the Python engine checks declared
CNH-adjusted-unit economics. Passed artifacts enter `ops.lean_research_runs` as
research evidence only. No broker credentials, approvals or executable events
cross this boundary. Legacy history remains uncertified for promotion.

## Principles

Local recovery is a separate process owned by platform startup. It restores
missing desired services through existing guarded entry points and honors
explicit stops. Embedded trading/broker workers survive transient iteration
failures; isolated calculations use locked, immutable attempts and atomic bundle
publication. The event outbox retains bounded at-least-once delivery. See the
[robustness review](robustness-review-2026-09-30.md) for failure tests and remaining
operator dependencies. Recovery confers no trading authority.

Registered monitored strategies are application-owned analytical calculations. The analytics worker reads committed audited batches, verifies source hashes and FX evidence, freezes complete strategy definitions, and runs either the internal Python engine or isolated LEAN with Python parity. A single ClickHouse publication commits matched results, current weights and report data only after all calculations succeed; failures retain the previous complete publication with an error status. No broker credentials or order authorization enter this boundary. The shared report renderer serves both SOTA and tracked challengers. Codex/agent schedules are not calculation infrastructure.

- Optimize for low turnover, concentrated, thesis-driven portfolios.
- Keep CNH as the accounting and risk currency even when assets trade in foreign currencies.
- Separate research, backtesting, proposal generation, and broker execution concerns.
- Keep v1 human-in-the-loop. The platform proposes trades and explains them; the operator accepts or rejects them.
- Preserve point-in-time data contracts between research, backtesting, paper trading, and live trading.
- Treat every order intent, approval, broker event, fill, reconciliation result, and operator action as audit data.
- Keep paper and live behavior on the same contracts, separated by environment controls and hard limits.
- Use Go, Rust, or C++ only for service boundaries where measured Python performance or reliability is insufficient.

## Layers

1. Domain layer: instruments, theses, proposals, orders, positions, fills, and portfolio snapshots.
2. Data layer: market data adapters, FX series, filings, corporate actions, and quality checks.
3. Research layer: watchlists, memo drafting, valuation context, catalysts, and invalidation rules.
4. Strategy layer: beta and alpha sleeves that emit target weights and human-readable rationale.
5. Backtest layer: deterministic in-repo engine for unit-scale checks; LEAN-compatible production backtests for promotion.
6. Portfolio layer: rebalance blotter, constraints, pre-trade checks, sizing, and approval workflow.
7. Execution layer: Interactive Brokers paper-first routing, validation, reconciliation, idempotent order submission, and audit.
8. Web layer: operator interface for monitoring, approvals, paper trading, and later controlled live trading.
9. Storage layer: PostgreSQL for operational state and immutable legacy SQLite evidence; explicit SQLite only for offline tests/recovery; ClickHouse for columnar query serving; Parquet for immutable market-data archive and DuckDB-readable research snapshots.
10. Observability layer: metrics, logs, traces, dashboards, alerts, incidents, and daily operating reports.

## Initial module boundaries

- `domain/`: schema and business language.
- `backtest/`: FX conversion, cash ledger, valuation, risk helpers, and daily engine.
- `storage/`: local persistence and schema management.
- `portfolio/`: sleeve logic and proposal builders.
- `data/`: source manifests and future provider adapters.
- `execution/`: broker environment manifests and future routing adapters.
- `web/`: API endpoints and request contracts.

## Target Service Boundaries

- Market data recorder: capture raw live data before downstream processing and publish normalized events.
- Data quality service: validate freshness, gaps, duplicates, corporate actions, FX, and source precedence.
- Feature service: compute versioned point-in-time features shared by research, backtests, paper, and live.
- Strategy service: load approved strategy versions and emit target portfolios.
- Portfolio service: convert targets into rebalance proposals with risk and cash constraints.
- Order management service: persist order intents, enforce idempotency, submit to IB, and track lifecycle.
- Reconciliation service: compare local state to broker orders, fills, positions, cash, and commissions.
- Alert service: route warnings to email, SMS or push, desktop popup, dashboards, and incident logs.
- Reporting service: generate post-trade, PnL, slippage, exposure, and robustness reports.

## Near-Term Roadmap

- Add persistent storage for raw data, normalized bars, FX, and research artifacts.
- Add filings and macro adapters.
- Add paper broker state mirroring and approval queue persistence.
- Add a thin web UI on top of the current API.
- Introduce event schemas, Postgres transactional state, and the ClickHouse plus Parquet columnar market-data path.
- Maintain event and data schemas through the code-based registry in `systematic_trading.schemas` until a separate schema registry service is justified.
- Build an always-on market-data recorder and replay path.
- Promote ClickHouse `market_data.daily_bars` and later intraday tables as the golden market-data source for UI, research, backtests, feature jobs, and validation.
- Integrate LEAN into the promotion path for production candidates.
- Build the strong rebalance blotter before any live trading.
- Add Grafana-class dashboards and multi-channel alerts.

The [database consolidation record](database-consolidation.md) documents the server-store defaults and physical storage relocation. The [LEAN integration plan](lean-backtest-integration-plan.md) defines an isolated backtest worker with frozen input bundles and no brokerage access.


## Strategy monitoring lifecycle

Monitoring membership is application state in the transactional strategy-control tables, under the global `strategy-monitoring-v1` scope. The versioned config seeds membership; immutable operator events override it across account resets. Each archive/restore increments a generation and uses compare-and-swap, with guarded allocation revisions. PostgreSQL serializes lifecycle and allocation commits with a shared advisory lock; SQLite tests use an immediate transaction.

Strategies shows Archive beneath each monitored name and Restore to monitored for supported archived definitions. Archiving removes a recipe from ongoing calculation jobs and keeps its last complete report. It is blocked for the designated SOTA, an actively funded strategy, or a pending allocation reference. Historical artifacts without a registered monthly multi-asset execution recipe cannot be restored until that recipe exists.

Restoring requests an application refresh. It replays every supported session from the pinned initial state, including all scheduled signals, fills, fees, cash, quantities, daily NAV, benchmark reports and current targets. This deliberately uses full replay rather than an unverified incremental checkpoint. The prior report stays readable with Catching up status. Only a complete publication bearing the required generation unlocks allocation. Failed jobs retain the previous complete evidence; membership and data changes during a batch prevent publication. This is simulated history and never places catch-up orders in a broker account.

`research_fallback_f3_v1` (Qualifying defensive ETFs + cash) is an executable registered strategy, calculated by `research/usd_monitored.py` inside the regular analytics service and published in the common tracked-strategy/report sources. Its USD replay uses audited adjusted ETF prices, pinned inputs and source hashes, causal rolling model schedules and published USD vintages. Its standard report explicitly labels USD; matched benchmarks also use USD. The report adapter retains existing internal money-field names, but CNH allocation comparisons consume only its separate `cnh_nav_series`, using exact dates from the published verified observed FX series. Missing FX is never filled. If this strategy becomes SOTA, CNH reports disclose the unavailable matched comparison instead of substituting another SOTA or mixing currency returns.

Membership is independent of funding, promotion and execution authority. Portfolio preview, scheduling, activation and proposal assembly enforce monitored membership; a restored strategy must finish its generation before allocation evidence is accepted. Existing paper-only approval, account, reconciliation and routing checks still apply.

### Monitored economic context ridge

`research_economic_context_ridge_v1` is the frozen CR recipe from economic-response v2: the unchanged F3 pipeline, a final 45% target cap with excess left in cash, then standardized per-ETF ridge (alpha 1) using the original seven leading and six context features. It uses at least 36 completed monthly return labels, expands chronologically, and preserves parent gross, cash and positive membership. Missing features or insufficient training abstain to capped F3. Settings are fixed until the requested ETF-universe revisit.

The analytics service owns the exact economic input subset, model schedule, monthly signals, replay, native parity, full benchmark report and indicative next-session targets. Publication binds the strategy definition, source hashes, price batch and the original eleven-series economic subset. Unrelated financial recorder extensions do not invalidate this recipe. A changed used vintage or calculation generation does. Model receipts are verified again when a later operator-approved allocation prepares targets; monitoring itself grants no execution authority.

Historical evaluation explicitly assumes daily ALFRED archive availability one calendar day before the prior trading close. Decisions from October 8, 2026 additionally require actual app first capture before that cutoff. Restoring an archived strategy replays missed calculations using those capture times; late recorder catch-up cannot backdate economic knowledge. The shared report shows available model predictions, coefficients, feature lineage, readiness and the full decision flow. Unavailable economic signals have a yellow abstention notice.

### Financial-condition recorder extension

The economic recorder supports weekday daily Treasury slopes (T10Y3M/T10Y2Y), Friday weekly Chicago Fed credit conditions (NFCICREDIT), and quarterly SLOOS lending standards (DRTSCILM/DRTSCIS). These extend the original eleven definitions through an audited additive registry migration. Original bytes, publication-vintage boundaries, actual capture timestamps, missing values and source attribution remain separate. The recorder also captures the vintage required by the latest indicative decision. Only omitted initial closed-market weekdays may be disclosed as unsupported prefix dates; no observations are inserted. Internal calendar gaps and missing initial open dates fail audit. Missing endpoint/window values remain unusable for research.

NFCICREDIT is a revised standardized composite, not a corporate bond spread. Corporate-spread storage rights, national PMI and pre-release consensus remain source gaps. New financial inputs are visible under Market Data → Economic Data but never silently enter the monitored CR feature set. Separate finite challenger studies use published snapshots and frozen manifests, with original-context sample/availability controls.
