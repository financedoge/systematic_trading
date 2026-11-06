# Script entry points

Run scripts from the repository root with `.venv/Scripts/python.exe` or PowerShell.
Keep existing filenames stable: service launchers, receipts and frozen studies
reference them. Reusable logic belongs in `src/systematic_trading/`; scripts
should compose that logic and record explicit inputs/outputs.

| Task | Entry point / guidance |
| --- | --- |
| FR25 proportional fallback and M,N search | Run `research_fr25_breadth.py` stages `prepare`, `bank`, `search`, `selected_runs` in order. Generate the report with `report_fr25_breadth.py`, validate with `validate_fr25_breadth.py`, then run `report_fr25_breadth.py close`. The training selection is sealed before the later replay. |
| Start, inspect, stop local services | `start_local_platform.ps1`, `watch_local_platform.ps1`, `stop_local_platform.ps1`; startup starts a stopped PostgreSQL Windows service and asks for administrator permission (UAC) when needed |
| PostgreSQL Windows service control | `postgres_service.ps1 -Action Ensure\|Start\|Restart\|Status`; direct, elevated-child and declined-prompt handling, no database file changes. [Runtime guide](../docs/native-windows-runtime.md) |
| Service PID identity | `service_process.ps1` `Get-ServiceProcessState`; recycled Windows PIDs never authorize stopping or skipping a service |
| Guarded operator start | `start_operator_dashboard.ps1` |
| Read-only PostgreSQL startup check | `probe_postgres_readiness.py`; configured app credentials, catalog and bounded relation reads |
| Native NATS lifecycle and verification | `native_nats.ps1`, `install_native_nats.py`, `verify_native_nats.py` |
| Daily serving-history acquisition | `backfill_daily_bars.py`; honors the configured backend; the old ClickHouse filename remains a compatible entry point |
| Native analytical migration and verification | `migrate_native_analytics.py`, `verify_native_analytics.py`; staged stopped-writer operation |
| Isolated native recovery drill | `verify_native_restore.py`; requires verified migration evidence and a new destination |
| Guarded research retirement | `retire_research_artifacts.py plan`, `apply_research_retention.ps1`; startup maintenance uses `maintain_research_storage.ps1` |
| One-time legacy Docker retirement | `retire_legacy_docker.ps1 -PlanOnly`, then the same script without that switch; exact project resources and completed native acceptance required |
| Retired Docker disk compaction | `compact_retired_docker_disk.ps1` from Administrator PowerShell after verified retirement and Docker shutdown; saves measured before/after sizes |
| IB SDK installation | `install_ib_api.py` |
| Broker diagnosis | `probe_ib_tws_health.py`, `test_ib_paper_connection.py` |
| Reconciliation and reviewed execution recovery | `reconcile_ib_paper_account.py`, `recover_ib_paper_executions.py`; follow [rollout controls](../docs/live-rollout.md) |
| Native frozen backtest | `run_lean_backtest.py`; follow [LEAN contract](../docs/lean-backtesting.md) |
| Read-only calculation scheduling benchmark | `benchmark_calculation_parallelism.py`; verified retained USD/M1 input, identical serial/parallel targets, no publication or broker changes |
| Expanded FR25 net replay | `research_expanded_fr25_net.py prepare/models/signals/evaluate`; full supported pool, original14 and matched M1, fixed/dynamic timing, no cost/IC veto. `report_expanded_fr25_net.py`, `validate_expanded_fr25_net.py`, `close_expanded_fr25_net.py` prepare charts, native checks and evidence review. Finite research, no operational authority. |
| Historical expanded ETF screen | `run_etf_expansion.py prepare/models/replay`; frozen old proxy-gated experiment only. New research uses the net replay above. Existing completed bundles are immutable; resumes execute the hash-verified frozen runner and package. |
| Retrospective execution evidence | `analyze_execution_timing.py`, `analyze_execution_references.py`; see [findings](../docs/execution-reference-findings.md) |
| Fixed cash-relative net retest | `research_cash_relative_retest.py prepare`, then `evaluate`, `validate_cash_relative_retest.py`, `report_cash_relative_retest.py`, then `research_cash_relative_retest.py verify`; immutable October 31 protocol and existing audited inputs, no app/broker mutation. [Review](../docs/research-plan-review-2026-10-31.md). |
| Six standalone Alpha101 net retests | `research_alpha101_net.py prepare`, then `signals`, then `evaluate`; `validate_alpha101_net.py` for native parity and `report_alpha101_net.py` for review. Completed frozen stages must not be overwritten. Full published pool, six formulas, monthly/dynamic timing, six frictions; no app/broker writes. [Results](../research/alpha101-net-20261031-v1/results.md). |
| Explicit log compression | `archive_logs.py`; [maintenance and recovery](../docs/repository-maintenance.md) |
| Documentation links and archive hashes | `check_docs.py` |
| Versioned research evidence review | `review_research_evidence.py DOSSIER --output REVIEW`; verifies exact policy/artifact hashes and sample-use declarations, records missing evidence, grants no authority. [P4.20 policy](../docs/research-evidence-governance-v1.md). |

Historical `run_*research.py`, `optimize_*` and `analyze_*` scripts are retained for
evidence replay, not a blanket recommendation for new experiments. Follow
[research state](../docs/research-state.md): new work requires published audited
histories, pinned batches/hashes, explicit price/volume basis, point-in-time
limitations and full supported-pool evaluation. Legacy provider-archive scripts
are not templates for future research.

No maintenance command changes funding, approvals, broker account configuration
or live enablement. Read each operational command's explicit confirmation contract.
