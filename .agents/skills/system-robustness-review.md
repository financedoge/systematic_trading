# System Robustness Review

## Trigger

Run weekly, after incidents, before promotion to live, and after any material infrastructure change.

## Inputs

- Service health metrics.
- Queue lag and dead-letter records.
- Database ingest, query, storage, and backup status.
- Market-data gap reports.
- Broker connectivity and reconciliation reports.
- Alert delivery records.
- Incident log and prior follow-ups.

## Workflow

1. Review service restarts, crashes, slowdowns, and resource pressure.
2. Review market-data gaps, stale feeds, duplicate events, and clock drift.
3. Review queue lag, failed messages, replay behavior, and schema violations.
4. Review database health, backups, restore readiness, and disk capacity.
5. Review broker disconnects, rejects, retry behavior, and reconciliation breaks.
6. Confirm alerts reached the intended channels and were recorded in the incident log.
7. Test or verify kill switch and rollback paths where relevant.
8. Update `log.md` with unresolved risks and owners.

## Outputs

- Robustness review summary.
- Incident trend summary.
- Risk register updates.
- Concrete follow-up tasks.

## Stop Conditions

- No verified backup or restore path for trading-critical state.
- Alerts cannot reach the operator.
- Broker reconciliation is unreliable.
- Market data cannot be replayed for a trading day under review.
