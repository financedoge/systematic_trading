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
- Before modifying or retiring a registered strategy or shared calculation/data service, inspect its direct and transitive dependencies with `scripts/check_strategy_dependencies.py` and follow `docs/strategy-dependencies.md`. Preserve pinned executable versions; introduce a new version and explicitly migrate consumers instead of regenerating dependency fingerprints to silence a mismatch. Archiving monitoring does not authorize deleting a required recipe or stopping a shared publisher. Keep dependency declarations, runtime planning, lifecycle guards and regression tests aligned.
- Build strategies as composites of separately governed time-series, signal and model assets. Before implementing any new input, search the asset pool (`scripts/check_strategy_assets.py --search <term>` or `/strategy-assets`), record inspected versions and the reuse/new-version decision in the composite's `reuse_reviews`, and reuse compatible existing providers. A new composite must declare pinned asset inputs; a new signal must declare its monitoring contract and appear automatically whenever a tracked composite needs it. Define rolling/walk-forward fit windows, label embargoes, availability, cadence, missing-data policy and frozen model lineage separately from portfolio construction. Follow `docs/strategy-assets.md`; do not create a duplicate pipeline or infer health from a current portfolio NAV. Every archive/retirement must run and record dependency impact; shared asset demand follows remaining tracked/protected consumers. Retiring assets preserves their definitions and historical evidence, and requires migrating all retained consumers first.
- Prioritize memory and storage over recomputation time. The operator's 2026-10-17 retention decision permits deleting bulky outputs, duplicated inputs/source bundles and model fits for archived or completed exploratory research after retaining compact findings, the strategy/runner recipe and an artifact-retirement record. Exact reproduction of retired research is not required; a later rerun on a new audited batch is new evidence. Do not require full backups of intentionally disposable outputs. Protect monitored/funded/pending strategies, active research and promotion inputs, canonical audited histories, and broker/approval/reconciliation evidence. A historical research-registry reference alone does not pin every bulky artifact forever. See `docs/storage-retention-and-windows-native-plan.md`.
- NAS is for catastrophic-laptop recovery, not replaying the entire research history (operator decision 2026-11-08). Recover code and compact research recipes/findings from Git; keep a bounded verified recovery set of durable application data and its required external dependencies. Do not accumulate unlimited SQL generations, copied source/runtime trees or disposable research outputs. PostgreSQL alone is not the whole database: the deployed app also depends on external Parquet, canonical histories and protected model/evidence files. Verify a replacement recovery set before retiring the existing complete backup. The recovery-only transition passed an isolated restore and completed NAS pruning on 2026-11-09. Retention also clears recognized retired backup files from this project's NAS recycle subtree after checking the live repository. See `docs/storage-audit-2026-11-08.md` and `docs/full-system-backup.md`.
- The operator retired the fixed 40 GiB generated-artifact admission ceiling on 2026-10-31. Retained research size alone must not block strategy calculations; check actual free disk headroom and queue guarded housekeeping. When closing disposable exploratory research, retain compact findings and the runner/protocol, and classify its generated output folders for routine retirement. Do not leave every completed experiment permanently protected merely because its artifacts can be reproduced.
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
- Retain every WRDS extract locally as a reusable source archive (operator decision 2026-11-07), including its exact query/parameters, capture time, dataset/table version, identifiers, row counts and checksums. Deduplicate identical captures without losing provenance; do not classify the sole retained WRDS source copy as disposable study output. Keep licensed rows and credentials out of Git. Archive retention does not bypass audit/publication or establish historical point-in-time availability.
- Record durable decisions, incidents, and next actions in `log.md`.
- Add or update tests when behavior changes.
- Avoid large rewrites unless the service boundary, benchmark, and migration path are explicit.
- Introduce Go, Rust, or C++ only when a measured bottleneck or reliability requirement justifies it.
- Prefer clear contracts and replayable artifacts over implicit notebook or script state.

For portfolio research, follow the [stability and winner-dependence guidance](docs/research-stability-guidelines.md). Freeze selection on training data, compare net annualized outcomes and exposures across eras, and test dependence on individual winners. Declare any return floor per study. Record sample reuse and distinguish ETF attribution from a causal claim about a market theme.

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
