# Documentation index

Read current status before historical results. The Kanban is the open-work tracker;
research state records accepted conclusions. Operational authority lives in app
state and reviewed controls, never in a prose status note.

## Start here

- [Architecture](architecture.md)
- [Industrial Platform Plan](industrial-platform-plan.md)
- [Execution Kanban](execution-kanban.md)
- [Research State](research-state.md)
- [Expanded ETF study and rejection findings](etf-expansion-findings-2026-10-14.md)
- [Full-pool class and volatility screen — 2026-10-16](class-volatility-screen-findings.md)
- [Cash-relative momentum and matched BIL-removal controls — 2026-10-17](cash-relative-momentum-findings.md)
- [Repository maintenance](repository-maintenance.md)
- [Disk cleanup and native Windows migration](storage-retention-and-windows-native-plan.md)

## Operations and recovery

- [Native Windows runtime, limits and migration evidence](native-windows-runtime.md)
- [Gateway trading operations](trading-operations.md)
- [Trading strategy roles and capital allocation](trading-allocations.md)
- [Live Rollout](live-rollout.md)
- [One IB Gateway for the local platform](ib-gateway-operation.md)
- [Optional NAS backups and PC handoff](database-sync.md)
- [Application recovery backups](full-system-backup.md)
- [Database consolidation and D: storage](database-consolidation.md)
- [Service Supervisor Plan](service-supervisor.md)
- [Dashboard performance](dashboard-performance.md)
- [Intraday outage recovery](intraday-recovery.md)
- [Application calculation resources](app-calculation-resources.md)
- [FR25 execution readiness and expanded-pool boundary](execution-readiness-2026-10-13.md)
- [Tracked-calculation performance: measurements and levers](calculation-performance.md)
- [API Workflow](api-workflow.md)

## Data and storage contracts

- [Data Contracts](data-contracts.md)
- [Market Data Recorder Contract](market-data-recorder-contract.md)
- [Market Data Recorder Source Plan](market-data-recorder-source-plan.md)
- [Market Data Golden Source](market-data-golden-source.md)
- [Columnar Store Target Design](columnar-store-target-design.md)
- [Postgres Transactional Store Design](postgres-transactional-store-design.md)
- [Analytical time-series migration](analytics-migration.md)
- [Schema Registry Convention](schema-registry-convention.md)
- [Queue Adapter Selection](queue-adapter-selection.md)
- [Governed underlying price histories — 2026-09-26](price-governance-2026-09-26.md)
- [Economic vintage recorder](economic-vintage-recorder.md)
- [EIA energy fundamentals recorder](energy-fundamentals-recorder.md)
- [Issuer ETF fundamentals pilot — 2026-10-09](issuer-etf-recorder.md)
- [Research ETF recorder and Treasury-bill parking](bill-recorder-and-parking.md)
- [Market History and chart navigation](market-history-and-chart-navigation.md)
- [CRSP cross-reference: access pending](crsp-data-access.md)

## Research and strategy contracts

- [ETF expansion inventory and first admission wave — 2026-10-13](etf-universe-inventory-2026-10-13.md)

- [Research Framework](research-framework.md)
- [Signal Library](signal-library.md)
- [Signal decay, alpha overlays and portfolio robustness — research plan](signal-decay-and-alpha-plan.md)
- [Target-change rebalance backtest plan (P4.22)](target-change-rebalance-plan.md)
- [Target-change rebalance results (P4.22)](../research/target-change-rebalance-20261015-v1/results.md)
- [Target-change rebalance acceptance receipt (P4.22)](../research/target-change-rebalance-20261015-v1/receipt.json)
- [Joint selection-width and timing protocol (P4.23)](../research/selection-width-timing-20261015-v1/protocol.json)
- [Joint selection-width and timing results (P4.23)](../research/selection-width-timing-20261015-v1/results.md)
- [Joint selection-width and timing acceptance receipt (P4.23)](../research/selection-width-timing-20261015-v1/receipt.json)
- [ETF strategy research and data expansion](etf-research-expansion-roadmap.md)
- [Execution generality — routing any admitted IB contract](execution-generality-plan.md)
- [App-owned execution benchmark collection](execution-benchmark-collection.md)
- [App-native tracked strategy calculations](etf-activity-lag20-tracking.md)
- [Rolling one-year XGBoost with ETF activity lag-20](rolling-xgboost-lag20-tracking.md)
- [FR25 tracked strategy](fr25-selection-tracking.md)
- [Local LEAN research worker](lean-backtesting.md)
- [LEAN backtest integration plan](lean-backtest-integration-plan.md)
- [Trading engine assessment: LEAN and NautilusTrader](trading-engine-assessment.md)
- [Turnover and breakeven-IC gate (P4.15)](turnover-gate.md)
- [Probability-Based Stock Valuation Implementation](stock-valuation-framework.md)

## Findings, audits and historical implementation evidence

These preserve dated results and limitations. A completed experiment does not
grant promotion or execution authority; newer reviews may supersede conclusions.

- [Peer review of the Alpha101 work: five findings, all confirmed, and what changed](alpha101-peer-review-corrections.md)
- [> **Corrected 2026-10-11 after peer review.** The rank IC ranked tied values in ticker order instead](alpha101-screen-findings.md)
- [> **Corrected 2026-10-11 after peer review.** The band arms and the control originally re-submitted](alpha101-tilt-daily-findings.md)
- [> **Corrected 2026-10-11 after peer review.** This study had four implementation defects: the arms](alpha101-tilt-exit-findings.md)
- [> **Corrected 2026-10-11 after peer review.** This measurement used the defective alpha 43 and the](alpha101-tilt-findings.md)
- [> **Corrected 2026-10-11 after peer review.** Re-run as `var/research/alpha101-tilt-replay-20261011-v2`](alpha101-tilt-replay-findings.md)
- [> **Corrected 2026-10-11 after peer review.** Re-run as `var/research/alpha101-tilt-surface-20261011-v2`](alpha101-tilt-surface-findings.md)
- [Cross-application connection audit — 2026-09-27](app-connection-audit-2026-09-27.md)
- [Application connection repairs — 2026-09-28](app-connection-repairs-2026-09-28.md)
- [Audited-history strategy and concentration rerun](audited-research-rerun-2026-09-26.md)
- [Earlier constituent information in the ETF strategy](constituent-integration-research-2026-09-26.md)
- [Constituent information for ETF allocation](constituent-signals-research-2026-09-26.md)
- [Longer constituent evidence and the Market Data archive](constituent-tenyear-research-2026-09-26.md)
- [Leading economic ETF response experiment](economic-response-research.md)
- [P4.19 — Matched execution references, October 12, 2026](execution-reference-findings.md)
- [P4.19 — Execution timing: retained-evidence audit](execution-timing-findings.md)
- [Flow and concentration acceleration research — September 26, 2026](flow-concentration-research-2026-09-26.md)
- [P4.14 Part B — FR25 placebo rank, data-through-2022 refit and sensitivity](fr25-placebo-findings.md)
- [P4.14 Part A — FR25 robustness attribution](fr25-robustness-findings.md)
- [P4.16b — Hierarchical construction: qualify the class, then pick inside it](hierarchical-construction-findings.md)
- [LEAN validation evidence](lean-validation-2026-09-26.md)
- [Trading and backtesting audit — 2026-09-26](platform-audit-2026-09-26.md)
- [Platform recovery review — 2026-09-30](robustness-review-2026-09-30.md)
- [Rolling model research — September 27, 2026](rolling-model-research-2026-09-27.md)
- [Sector-volume HHI and subsequent returns — 2026-09-26](sector-hhi-correlations-2026-09-26.md)
- [P4.13 — Signal decay, IC instrumentation and the decay warning](signal-decay-findings.md)
- [P4.16 — Sleeve-aware construction](sleeve-construction-findings.md)
- [Strategy review and repair — 2026-10-11](strategy-review-2026-10-11.md)
- [Underlying-stock sector concentration research](underlying-sector-hhi-2026-09-26.md)

## Historical memory and reference attachments

- [Compressed project history and research protocols](archive/README.md).
- [Historical heading and milestone index](archive/history-index.md).
- [Stock valuation reference PDF](<Probability Based Stock Valuation Framework V1.pdf>).
- [Recent project log](../log.md).

Some rendered research reports are local artifacts excluded from Git. Missing
rendered targets retain their original paths with explicit availability notes.
Evidence was not reconstructed or substituted.
