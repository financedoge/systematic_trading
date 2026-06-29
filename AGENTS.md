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
- Use point-in-time data semantics for any historical research or promoted strategy work.
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
