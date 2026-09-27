# Application connection repairs — 2026-09-28

Implementation of the seventeen findings in [the connection audit](app-connection-audit-2026-09-27.md), authorized by the user. The central change is a shared portfolio episode: the existing reset defines monitoring inception, while later accounting checkpoints only accelerate replay. The current portfolio starts **September 25, 2026 in New York**, with an exact boundary of `2026-09-25T03:59:59.999999Z`. No additional portfolio reset was performed.

## Delivered changes

| Finding | Implemented connection | Verification / boundary |
| --- | --- | --- |
| C01 Presentation | Trading, Strategies, System, Market Data and strategy detail reports use `web/shell.py` for navigation, typography, colors, panels, focus and compact headers. | Shared-shell regression and browser inspection. |
| C02 Portfolio inception | Versioned `PortfolioContext` carries episode, start session, exact cutoff, environment, reporting currency, account when known, and opening evidence. Performance, holdings, execution quality, proposals, blotter, P&L and EOD resolve it. | Existing reset migrates by derivation, without rewriting evidence. Compaction retains the episode. Portfolio period is the blotter default; historical records remain accessible. |
| C03 Attribution scope | Misses use intended trading sessions; individual execution slices use their actual New York dates and dated FX. Order counts are separate from execution counts. Basis points use the same P&L difference as the headline. | Active period has 6 filled orders, 48 slices and 0 missed orders. Rounded row totals and the reconciliation difference are explicit API fields. |
| C04 Reference accounting | Checkpoints save both actual and reference lots/realized balances. Legacy actual-only compactions replay reference accounting from the reset. | Paired-ledger compaction regression preserves both totals and their difference. |
| C05 Historical accounting | Reads select an eligible checkpoint at or before the requested time, within the current episode. | Earlier dates cannot inherit future holdings. Unsupported previous-episode requests return a conflict instead of a valuation. |
| C06 EOD invalidation | Completion is keyed to episode/baseline, executions, marks and dated FX revisions. Current-period dates are requeued when financial inputs change. | Financial revision tests distinguish changed fills/marks from ordinary broker polling. Old backlog dates are excluded. |
| C07 Observation dates | Live broker snapshots retain their actual capture date. Historical catch-up requires an actual same-day observation. Charts reject backdated captures and preserve the exact opening anchor. | Historical snapshot and opening-anchor regressions. Missing historical evidence remains unavailable. |
| C08 Active targets | Holdings and allocation control share the approved current-strategy, current-window, current-episode selector. Scheduled reconstruction is the explicit fallback. | Pending/rejected proposals and file modification times cannot select the active target. Completed orders no longer appear as outstanding trade instructions. |
| C09 Governed decisions | Production decisions consume the same published audited histories as tracking. Signals use adjusted prices; execution references use audited raw prices. | Governed-input reader and producer/consumer integration tests. Missing or unsupported inputs stop calculation. |
| C10 Publication producer | The application acquires provider evidence, audits coverage/identity/actions/revisions, verifies ClickHouse writes and commits a new catalog only after the complete ETF batch succeeds. | Mocked end-to-end success/failure tests. Failure retains the previous publication and quarantines evidence. Retries are bounded. |
| C11 Replay provenance | New decision receipts include the full strategy definition, portfolio context, input batch/file hashes, price bases, raw marks, FX values and target lineage. | Immutable input/hash checks, including composed-catalog parent hashes. |
| C12 Incomplete valuation | One session-aware mark/FX policy rejects missing and stale observations. No average-cost or future-FX substitution creates a complete value. | Missing fill FX, stale marks and dashboard missing-price tests. Incomplete P&L is withheld in the UI and from successful EOD persistence. |
| C13 Economic reconciliation | Signed, evidence-referenced cash events support deposits/withdrawals, dividends, interest, fees, tax and adjustments. The NAV bridge includes security P&L and cash FX; Modified Dietz return is available only after reconciliation. | Idempotent event identity, account/episode/environment checks and deposit/return tests. **CNH -92.98 remains explicitly unresolved** in the current account; broker statement evidence is still needed. |
| C14 Worker independence | Research and account/execution projections run in independent application workers. A tracked-strategy failure does not stop account publication. | Projection failure regression. Per-lane jobs, completion times and errors are visible. |
| C15 Broker health | A recurring read-only application probe refreshes the IB health state. | Fresh broker handshake observed after restart; stale state is distinguishable from a failed probe. |
| C16 Calculation and delivery health | System health includes analytics and alert delivery. Old operations completions become degraded; configured delivery failures persist in a receipt log. | Stale-completion regression and health tests. Current email delivery is explicitly disabled because SMTP host/recipient are unconfigured. |
| C17 Restore prerequisites | SQL snapshots include a versioned dependency receipt for immutable inputs/models, governed manifests and analytical publications. Restore checks these before changing databases or ownership. | NAS round-trip tests and missing-dependency rejection. ClickHouse/artifacts remain separate migration prerequisites; a SQL-only restore cannot claim a complete application handoff. |

## Portfolio and accounting contract

`GET /api/v1/portfolio/context` is the monitoring scope. A reset creates a new episode through the existing verified opening/reset workflow; changing an arbitrary date without an opening state would make the accounting inconsistent. There is intentionally no independent date constant in each dashboard. Research prospective-tracking dates retain their separate meaning.

The September 24 opening-capital anchor is retained and is not a monitored trading session. The exact opening NAV is CNH 871,873.70. The confirmed baseline remains `d229466e93af`; the derived episode is `bc80316a7c2d24ed0b36`.

Current account reconciliation against closing NAV CNH 873,375.41:

| Component | CNH |
| --- | ---: |
| NAV change | 1,501.71 |
| Security P&L | 977.08 |
| Cash FX movement | 617.61 |
| Recorded external flows / income / fees / adjustments | 0.00 |
| Unexplained residual | -92.98 |

Zero recorded cash events does not establish that no fees or income occurred. No residual has been relabelled as a commission without source evidence. The application exposes `POST /api/v1/portfolio/cash-events` for source-referenced ledger ingestion and `GET /api/v1/dashboard/economic-reconciliation` for the bridge. Corrections require explicit reversing events; conflicting reuse of an external event identifier is rejected. Raw account NAV change remains clearly labelled as including cash flows. The reconciled, flow-adjusted return is a separate field and is unavailable while the residual remains unresolved.

Execution reference P&L is CNH 1,960.12; actual minus reference is CNH -983.04, or -11.57 bps on current-period reference notional. Reference-fill attribution remains distinct from strategy backtest returns and broker-native P&L.

## Data publication and recovery boundaries

The recurring governed producer covers the current strategy ETF universe plus URTH. Other catalog histories remain pinned to their existing batches; this is not a whole-universe source refresh. Revised historical return paths, truncated coverage, changed identities or unsupported observations block publication. Uniform dividend rebasing may pass the existing audit policy. Source auditing does not establish historical publication availability; receipts retain this limitation. Existing legacy FX evidence is disclosed and is not upgraded to fully audited by this change.

New NAS manifests inventory external dependencies and verify their availability before an incoming restore. They do not copy the entire ClickHouse database or immutable artifact tree into the SQL backup. A second machine needs those prerequisites at the recorded paths/namespace and versions, or startup blocks with the missing dependency. Older SQL-only backups cannot establish analytical recoverability. No forced takeover or ownership bypass was added.

## Validation and operation

- The final full suite passed **702 tests with 51 optional integrations skipped**, including opening-anchor and stale-calculation regressions: `var/research/app-connections-tests-complete.xml` and matching log. Whole-project Ruff checks passed.
- Focused post-implementation checks passed 84 tests / 3 skips, followed by 45 tests / 1 skip for accounting, publication and snapshot edge cases.
- Shared workspace headers, strategy reports, portfolio scope, attribution and reconciliation were inspected in the local browser. Desktop and compact Trading checks had no console errors or horizontal overflow. System shows eight required services healthy; service nodes remain legible with the added calculation/delivery nodes. Runtime values are captured in `var/research/app-connections-runtime-final.json`.
- The restarted backup worker produced generation `2b0c1b76a1f84600a36e7b023591ca6a` with 4,667 artifact files, one governed root and 19,946 analytical publication versions. Receipt: `var/research/app-connections-backup-receipt.json`.
- Dashboard, dispatcher and backup worker were restarted through guarded local operations. Paper execution policy, reconciliation checks, broker environment restrictions and live-disabled defaults remain intact. No new order or cash event was submitted for verification.

Follow-up evidence requirements: import and reconcile broker statement cash events; configure a delivery channel if email alerts are desired; exercise a complete second-machine recovery with the inventoried external dependencies before claiming disaster-recovery readiness. These are visible operational/data requirements, not hidden successful states.

The user's follow-up request to use available CPU cores adds [resource-aware parallel calculations](app-calculation-resources.md): independent preparation processes and native backtest workers, while retaining the independent operations lane and atomic strategy publication.

Final combined acceptance: 708 tests passed / 51 optional skips, all five native runs passed with unchanged economics, and eight required services healthy. An interrupted pre-parallel risk-parity run was preserved after confirming no associated process/container remained, then retried against the identical bundle and passed parity; evidence is in `var/research/app-connections-recovery-receipt.json`. Subsequent parallel publication completed successfully. No failed or incomplete run was promoted into a report.
