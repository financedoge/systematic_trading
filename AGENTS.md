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
- Tracked strategies must be complete, versioned strategies calculated by the app's own strategy/analytics services: signals, scheduled rebalances, latest target and held weights, portfolio value, and benchmark reports. Do not use agents, Codex automations, reminders or manually maintained research cards to perform recurring strategy calculations. Implement missing calculation capabilities in the app. Use the shared SOTA detail/report format and include the full decision flow; keep tracking separate from promotion and execution authority.
- Use point-in-time data semantics for any historical research or promoted strategy work.
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
