# Calculation invalidation review — November 7, 2026

The operator questioned whether every source/history change should cause a full
strategy recalculation. The review confirms that invalidation is broader than
the numerical dependencies. Source provenance, calculation identity, model fit
identity and execution readiness currently use different levels of granularity.

## Measured incident

Compared calculation `8906b90b7f623337943e3ed0b23fe23a7bdb681d356c3a1619c453d21688d68b`
against the committed audited catalog
`2ecce5e8bca07c28c3f918d7ce20d36b8d54b9377c12ce6a35d80df66f118628`.
Both the old calculation and the strategy histories reach November 6.

- 441 catalog entries changed since the calculation's old price batch
  `873b2aa57c91f336f6398b2c0bfb7f60e20cf852f273f311b532362560ab8cd5`.
- All 13 recorded base price files, all 17 M1/14 price/admission files and all
  102 BroadTrend price/audit files are byte-identical. Counts overlap across
  consumers. Both publication manifests and every compared file were verified.
- Consequently this catalog change introduced **no change at all in those
  recorded strategy price/admission inputs**, not merely a small price change.
  This check does not assert that independent FX, economic or USD vintages are
  unchanged.
- The FR25 published model request's code manifest differs from current code in
  just `research/sip_volume_pilot.py`, an independent source-comparison study.
  Its addition triggers the broad calculation-source restart guard.
- The previous FR25 training receipt reports 131 monthly fits, all 131 reused,
  zero new fits. A full calculation refresh is therefore not necessarily a full
  statistical refit. It still repeats feature/schedule preparation, replay,
  independent validation and reporting work.

Read-only comparison evidence: `var/maintenance/health-20261107/invalidation-audit.json`.
The review fetched no new market data and changed no publication or execution gate.
The reproducible diagnostic is `scripts/audit_calculation_invalidation.py`;
`--calculation`, `--catalog` and `--output` pin its inputs and save a new receipt.
It reports independently pinned scopes (including the conditional strategy's
frozen catalog) separately rather than treating them as consumers of the current
global catalog. Missing or changed original evidence fails the diagnostic.

## Current coupling

`tracked_runtime.calculation_revision` hashes the entire input provenance,
including global catalog version, plus every Python source under research,
LEAN, signals, portfolio and backtest. An unrelated catalog change or research
module therefore changes the calculation identity. The batch is also in the
rolling schedule request, despite individual fits already being cached by their
actual training rows, recipe, implementation and library versions.

Trading model binding and allocation readiness require the calculation's price
batch to equal the current audited catalog. The recorder-before-calculation
ordering avoids immediately publishing a stale calculation, but also makes
unrelated broad-history acquisition delay the strategy lane. The health repair's
bounded acquisition pass limits this delay; it does not fix invalidation scope.

The existing strict checks remain in place. Simply removing the batch check,
ignoring hashes, or raising a numerical tolerance would lose the evidence that
the report and decision actually use compatible inputs.

## Required invalidation policy

| Change | Required work |
| --- | --- |
| Unused symbols, fields or dates; packaging only | Verify compatibility and record the new source lineage; reuse calculations. |
| New dates after a verified unchanged consumed prefix | Advance relevant signals, holdings, NAV and benchmarks from a verified checkpoint; fit only when the declared cadence and completed labels require it. |
| Revised observations used by a feature or model | Invalidate affected dependent assets and replay from the earliest affected state, including warmup and label dependencies. |
| Revision outside a particular fit's training/feature/label windows | Keep that fit if its complete numerical and availability inputs are identical. Other consumers can still be affected. |
| Identity, basis, availability, calendar, missing-data or corporate-action contract changes | Require governance review and invalidate affected consumers; numerical equality alone is insufficient. |
| Relevant implementation, model recipe or library change | Produce a new implementation/calculation revision and perform the required parity checks. |
| Unknown dependency impact | Fail closed and perform the conservative calculation. |

Do not use an arbitrary "small price change" cutoff. Tiny changes can cross
ranking, eligibility, sizing or stop boundaries. Even uniform dividend rebasing
can preserve a return feature while changing unit quantities or accounting.
Equivalence must be scoped to the declared consumer, basis, dates, availability
and numerical representation. Actual held weights and adopted targets remain
distinct from a newly computed theoretical target.

## Staged implementation and acceptance

1. **Verified unchanged-input reuse.** Separate immutable source/capture lineage
   from per-asset computational content. Start conservatively with exact
   equality of every declared consumed artifact and governance contract. Emit
   a compatibility receipt connecting the new committed catalog to the original
   calculation; preserve original evidence rather than rewriting old receipts.
   Atomic publication, model binding, allocation readiness and report serving
   must consume this same proof. Missing, changed or unverified inputs reject
   reuse. Narrow calculation code manifests through explicit dependency closure;
   unclassified code changes remain conservative.
2. **Append-only continuation.** Verify the entire prior consumed prefix and
   checkpoint lineage, then extend deterministic strategy state. Checkpoints
   must include cash, positions, units, adopted targets, pending decisions,
   signal/protection state and model lineage. Monthly models remain frozen until
   their declared refit date; new labels must satisfy embargo/availability.
3. **Revision-directed replay.** Record changed symbols, fields, dates and their
   dependent assets. Bound rolling fits by their actual feature/label windows;
   recursive filters and portfolio paths propagate forward until independently
   verified convergence, or through the remaining history when needed.

Acceptance must compare reused/incremental results against the current full
replay on identical pinned inputs, including targets, held units, NAV, fills,
costs, benchmark reports and independent native parity. Include unrelated
catalog updates, appends before/after fit boundaries, revised used/unused fields,
availability/identity changes, source tampering, missing evidence, concurrent
publication/lifecycle changes and restart recovery. Measure total wall time,
peak memory, disk writes and newly fitted model count, not just model fit speed.

First deploy compatibility decisions in shadow mode beside the existing full
calculation, then enable exact unchanged-input reuse. Keep full replay as the
fallback and rollback path. Append/revision continuation is a subsequent service
change, not part of the incident's transport and health-message fixes.
