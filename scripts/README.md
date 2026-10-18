# Script entry points

Run scripts from the repository root with `.venv/Scripts/python.exe` or PowerShell.
Keep existing filenames stable: service launchers, receipts and frozen studies
reference them. Reusable logic belongs in `src/systematic_trading/`; scripts
should compose that logic and record explicit inputs/outputs.

| Task | Entry point / guidance |
| --- | --- |
| Start, inspect, stop local services | `start_local_platform.ps1`, `watch_local_platform.ps1`, `stop_local_platform.ps1` |
| Guarded operator start | `start_operator_dashboard.ps1` |
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
| Finite expanded ETF comparison | `run_etf_expansion.py prepare`, then `models`, then `replay`; pinned audited inputs, candidate-specific pre-test gate, app-owned models and native parity. Existing completed bundles are immutable; resumes execute the hash-verified frozen runner and package. |
| Retrospective execution evidence | `analyze_execution_timing.py`, `analyze_execution_references.py`; see [findings](../docs/execution-reference-findings.md) |
| Explicit log compression | `archive_logs.py`; [maintenance and recovery](../docs/repository-maintenance.md) |
| Documentation links and archive hashes | `check_docs.py` |

Historical `run_*research.py`, `optimize_*` and `analyze_*` scripts are retained for
evidence replay, not a blanket recommendation for new experiments. Follow
[research state](../docs/research-state.md): new work requires published audited
histories, pinned batches/hashes, explicit price/volume basis, point-in-time
limitations and full supported-pool evaluation. Legacy provider-archive scripts
are not templates for future research.

No maintenance command changes funding, approvals, broker account configuration
or live enablement. Read each operational command's explicit confirmation contract.
