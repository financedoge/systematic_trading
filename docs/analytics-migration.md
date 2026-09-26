# Analytical time-series migration

Scope: strategy and benchmark NAV, monitored marks, chart/attribution/period
series, research diagnostics, account and P&L observations, execution histories
and benchmarks, fundamentals, and recorded intraday market observations.
Daily bars and FX already use ClickHouse and retain their existing contracts.
Orders, approvals, reconciliation, P&L reset baselines, and the event outbox
remain authoritative in PostgreSQL. Original research and raw recorder files
remain replay evidence; this migration does not delete them or promote research.

The analytical boundary is a versioned projection in the `analytics` database.
Each source has immutable content versions, typed observation time/family/entity,
and the complete original row payload. A version is visible only after all rows
and serving documents have been read back and verified. Failed/interrupted
imports cannot replace the previous committed version. Ingestion time is separate
from observation time; unknown original availability remains unknown.

Strategy catalog, detail and report responses are prepared by a read-only worker
and stored in ClickHouse. HTTP reads use the last complete publication and expose
its generation time; they never trigger research or broker operations. Source
file changes and database market-data corrections invalidate publications. An
unavailable initial publication returns an explicit retryable response. A failed
refresh retains the previous publication with freshness metadata and worker error.

Migration keeps the previous file/PostgreSQL sources as rollback evidence. Verify
row identities, exact payload hashes, repeat-import idempotency, deleted/revised
source behavior, failed publication isolation, and before/after report equality.
Measure both cold and warm catalog/report latency; the measured baseline is
11.6 seconds for the catalog and 36.3 seconds for the current strategy report.
Explicit SQLite offline tests retain the original calculation path.

## Storage and readers

| History | ClickHouse serving source | Original evidence retained |
| --- | --- | --- |
| Daily prices and FX | `market_data.daily_bars`, `market_data.fx_rates` | Provider lineage/raw captures |
| Strategy NAV, benchmarks, monitoring extensions, chart/period/attribution series | `analytics.current_observations`, source `strategy-serving` | Versioned backtest JSON/HTML |
| Research diagnostics and nested dated candidate results | source `research-history` | All backtest JSON artifacts |
| Registered LEAN NAV, decisions and fills | source `lean-history` | Hash-verified registered output files |
| Account snapshots | sources `account-history/<capture>` | Original timestamped capture files |
| Account/strategy comparison | source `dashboard-serving` | Baselines and original observations |
| Daily accounting P&L, execution records/fills, fundamentals | source `transactional-history` | Authoritative PostgreSQL rows |
| Execution benchmark minute bars | source `execution-benchmarks` | Validated raw benchmark files |
| FX provider legs | source `fx-observations` | Original provider response files |
| Raw bar/trade/quote/FX captures | sources `market-chunk/<relative path>` | Raw-first hot/archive files |
| Sector research: stock/ETF bars, dated constituents, unavailable downloads | sources `sector-research/<dataset>/...` | Frozen raw Yahoo/issuer files and hashes; see [sector research archive](underlying-sector-hhi-2026-09-26.md) |
| Constituent features and LEAN comparison results | sources `constituent-research/<study>/features` and `/results` | Verified feature payloads, null historical availability, frozen protocol and metrics; see [constituent study](constituent-signals-research-2026-09-26.md) |

`analytics.observations` retains typed family/entity, observation timestamp,
nullable original availability, ingestion timestamp, stable row identity and exact
JSON payload. Monetary precision remains in the original string payload. Query
`analytics.current_observations` for committed latest source versions; querying
the underlying table intentionally includes superseded and uncommitted evidence.
`analytics.documents` contains prepared catalog/detail/report payloads, keyed to
the same verified publication. `analytics.publications` records row counts,
source fingerprints, provenance and commit timestamps. Use workspace filters;
different resolved data directories have isolated workspace identities.

The Strategy API, account performance chart and analytical account/P&L history
read ClickHouse. Execution benchmark lookup prefers its published observation,
with validated original-file recovery. Operational orders/fills, reconciliation,
fundamental point-in-time input reads, and P&L baselines retain their PostgreSQL
contracts; their analytical copies are separate. Live broker P&L remains the
live callback view, not a fabricated historical snapshot. This migration cannot
recover unrecorded callbacks or create missing provider observations.

Account captures and raw chunks publish independently and are batched for import;
unchanged files are not rewritten. Removed account source files get an empty
current version, while prior evidence remains. Raw files can leave the hot spool
after archival, so previously imported immutable raw chunks are retained.
Repeated captures of the same raw source event retain different receipt metadata;
identical hot/archive copies dedupe. No delayed observations become live data.

## Operation and rollback

Run `.venv/Scripts/python.exe scripts/migrate_analytical_timeseries.py` before
cutover. Exit code 2 means a source failed and the JSON output names it. Each
successful source remains committed; rerunning resumes without rewriting it.
The embedded worker polls every `ST_ANALYTICS_REFRESH_SECONDS` (default 60) after
each completed pass, including weekends and after hours. It detects historical
market corrections using row counts, ingestion revisions and payload fingerprints,
not just the latest trade date. New research/capture files are imported each pass.

`GET /api/v1/analytics/status` exposes worker errors and last completed pass.
`GET /api/v1/analytics/observations?source=strategy-serving&family=strategy_nav`
reads saved rows. JSON Strategy responses include publication/refresh metadata;
reports show generation time and refresh errors. After an account reset, the
performance endpoint refuses a publication for the previous baseline until a new
one is ready. The worker never submits orders or connects to a broker.

Set `ST_ANALYTICS_ENABLED=false` and restart only the dashboard to roll back
serving to retained file/PostgreSQL calculations. No reverse data migration or
deletion is needed. ClickHouse data uses the existing D: Docker volume. The NAS
handoff still does not transport ClickHouse: copy its volume separately or rebuild
these projections from retained source files and PostgreSQL after handoff. Do not
delete source evidence. Monitor disk growth; retained superseded report versions
currently have no automatic deletion policy.
