# Agent Operating Rules

These rules are project memory for human and AI agents working in this repository.

## Required Reading

Before major architecture, trading, data, execution, or research changes, read:

- `README.md`
- `docs/industrial-platform-plan.md`
- `docs/execution-kanban.md`
- `docs/architecture.md`
- `docs/live-rollout.md`
- `docs/research-state.md`
- `log.md`

## Working Rules

- Preserve the current paper-first and live-disabled-by-default posture.
- Update `docs/execution-kanban.md` at the start and end of every implementation session.
- Do not weaken approval, reconciliation, or broker-environment checks.
- Keep research, backtesting, paper, and live contracts aligned.
- Prioritize memory and storage over recomputation time. The operator's 2026-10-17 retention decision permits deleting bulky outputs, duplicated inputs/source bundles and model fits for archived or completed exploratory research after retaining compact findings, the strategy/runner recipe and an artifact-retirement record. Exact reproduction of retired research is not required; a later rerun on a new audited batch is new evidence. Do not require full backups of intentionally disposable outputs. Protect monitored/funded/pending strategies, active research and promotion inputs, canonical audited histories, and broker/approval/reconciliation evidence. A historical research-registry reference alone does not pin every bulky artifact forever. See `docs/storage-retention-and-windows-native-plan.md`.
- The deployed runtime is native Windows PostgreSQL for operational state/publication metadata, compressed Parquet queried by native DuckDB for analytics, native NATS and independently validated native LEAN. The October 18 cutover passed data, engine, backup, restore and served-report verification; project ClickHouse/NATS Docker volumes and legacy images were retired. Do not add Docker/WSL runtime dependencies. Preserve independent engine validation, publication hashes and broker guards; legacy Docker scripts are only for explicitly selected historical recovery.
- Tracked strategies must be complete, versioned strategies calculated by the app's own strategy/analytics services: signals, scheduled rebalances, latest target and held weights, portfolio value, and benchmark reports. Do not use agents, Codex automations, reminders or manually maintained research cards to perform recurring strategy calculations. Implement missing calculation capabilities in the app. Use the shared SOTA detail/report format and include the full decision flow; keep tracking separate from promotion and execution authority.
- Use point-in-time data semantics for any historical research or promoted strategy work.
- Do not impose an absolute annual trading-cost ceiling on research. The operator retired the 44 bp rule on 2026-10-17: additional costs are acceptable when additional returns justify them after costs. Compare matched net portfolio outcomes, net Sharpe with return/drawdown guardrails, actual turnover/costs, cost and execution-delay sensitivity, and chronological robustness. Turnover and IC/breakeven diagnostics inform the study; they are not substitutes for realized net performance. Frozen legacy gates may only reproduce historical experiments and must not exclude new candidates or their controls.
- Always evaluate dynamic rebalancing as an explicit option in future strategy, ETF, feature and portfolio-construction research; include a fixed-interval control rather than assuming calendar-only rebalancing. Predeclare the trigger/threshold candidates and compare net Sharpe with return/drawdown guardrails, actual turnover/costs, execution-delay sensitivity and chronological out-of-sample stability. For target-change triggers, compare the latest theoretical target with the last adopted target, including cash; latest adopted target versus actual held weights remains Trading housekeeping. The current top-six/monthly result is specific to its tested universe and recipe, not a blanket rejection of dynamic rebalancing.
- Evaluate future ETF, feature and momentum research on the full supported candidate pool. Do not repeat standalone XLE/XLB-only tests unless the user explicitly requests them. Candidate admission never mandates portfolio allocation; constituent attribution should explain the full portfolio.
- Every research round must identify the weakest risky ETF under its training-selected policy and prepare its inspection chart before handoff. Default to lowest net cumulative return in the declared primary evaluation/cost/delay case, exclude cash references, state that criterion, and show the weakest case in each chronological evaluation. Include exact dates, price/volume context, states, fills, protection and trade outcomes; keep only two or three main model choices. Record the operator's visual observations as hypotheses for the next declared test, never as silent retrospective tuning.
- Treat FR25 as an empirical incumbent benchmark, not a universal gold standard or evidence of structural truth. Future studies must also compare cash, asset buy-and-hold, simple matched strategy controls and regime/chronological robustness. Assess whether FR25 itself benefits from particular assets/periods. Preserve frozen historical verdicts and promotion controls; separate useful diagnostic evidence from claims of portfolio superiority.
- Future research, strategy backtests, features, labels and comparison charts must use the published, audited continuous histories, with a pinned batch and verified input hashes. Do not read downloaded provider archives or fetch online prices directly as research inputs. Ingest new observations through the audit and publication process first.
- Select the supported price and volume basis explicitly: dividend/split-adjusted prices for return research; audited raw prices and raw volume where the signal requires traded activity. An audited raw-price version is distinct from an unaudited provider archive. Preserve unsupported observations as missing, enforce coverage and identity checks, and never silently splice, fill or substitute sources. Auditing does not establish historical publication availability; retain point-in-time limitations.
- Keep provider archives available only for source inspection, reconciliation and governance. Historical studies using those archives are legacy evidence, not templates for new research. Any unresolved input class (including FX or holdings availability) must be disclosed and must not be described as fully audited.
- Record durable decisions, incidents, and next actions in `log.md`.
- Add or update tests when behavior changes.
- Avoid large rewrites unless the service boundary, benchmark, and migration path are explicit.
- Introduce Go, Rust, or C++ only when a measured bottleneck or reliability requirement justifies it.
- Prefer clear contracts and replayable artifacts over implicit notebook or script state.

## Promotion Discipline

Strategy promotion requires evidence, not intuition:

- Versioned strategy specification.
- Versioned data and feature inputs.
- Reproducible backtest and benchmark report.
- Out-of-sample and robustness checks.
- Paper-trading evidence.
- Risk limits and capital caps.
- Operator approval and rollback plan.

## Recurring Project Skills

Project playbooks live under `.agents/skills/`:

- `daily-post-trade-analysis.md`
- `continuous-research-loop.md`
- `system-robustness-review.md`
- `strategy-promotion-control.md`
