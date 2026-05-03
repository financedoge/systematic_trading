# Live Rollout

## Paper-first stages

1. Proposal preview only: no orders leave the system.
2. Paper routing: manually approved paper orders are sent to IB paper.
3. Shadow live review: proposals are compared against paper fills and manual expectations.
4. Live enablement: capital caps, stronger validations, and rollback procedures are in place.

## Safeguards

- Separate paper and live environments.
- Explicit approval before order submission.
- Buying-power, duplicate-order, and stale-price checks.
- Local reconciliation of positions, orders, and cash balances against broker state.
- Durable local storage for proposal and approval history before any broker routing is enabled.
- Live remains disabled until paper trading is stable for an extended period.

## v1 order assumptions

- Stocks and ETFs only.
- Long-only.
- Daily monitoring.
- Limit, market, and open-oriented workflows only.
