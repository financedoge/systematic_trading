# Strategy dependencies and change control

Reusable time-series, signals and model inputs now have a separate governed asset
catalog, demand-driven monitoring and retirement controls. See
[strategy assets](strategy-assets.md). Every archive records service-side impact
and rechecks the asset-lifecycle revision; the dialog reviews continuing inputs.

The application must track dependencies separately from monitoring membership.
Archiving a report is not permission to delete its executable recipe, stop a
shared data publisher, or remove a benchmark needed by another strategy.

## Contract

Implemented by `research/strategy_dependencies.py` and the checked-in
`research/strategy_dependencies.json` registry. The initial registry covers all
15 registered executable contracts. The Strategies page includes a read-only
**Dependencies and change impact** panel. Its API is
`GET /api/v1/strategies/dependencies?key=<strategy-key>&action=archive|modify|retire`.
There is no recipe deletion or automatic pin-update endpoint.

Maintain a versioned registry of executable strategy contracts and their direct
recipe, calculation, report and shared-data dependencies. Resolve transitive
dependencies and reject missing references and cycles. Keep recipe inheritance
separate from report benchmarks: a candidate may use a parent's recipe while
the parent's report compares with the candidate, without creating a calculation
cycle.

Pin executable definition fingerprints. Changing an existing version's universe,
scheduler or overlays must fail preflight for its protected dependents. Introduce
a new strategy version and explicitly migrate the affected dependency instead of
silently refreshing the expected fingerprint. Display names and prose are not
execution contracts. Existing code/input hashes and native validation remain
required; a dependency graph does not prove that arbitrary implementation changes
are correct.

Protected roots include monitored strategies, SOTA, active allocations and pending
allocation changes. The application exposes direct requirements, transitive users,
contract status and the impact of archive, modification or recipe retirement.
The impact also includes retained archived consumers so a future restore is not
silently broken by removing an unmonitored ancestor. These recipe references do
not preserve disposable generated outputs.
Lifecycle writes must recheck the current dependency state under the existing
membership/allocation concurrency guards. A missing or changed required contract
must prevent new calculation publication and allocation readiness while retaining
the previous complete report.

## Runtime ownership

Shared acquisition and audited publications belong to application services. They
must not be side effects of monitoring an unrelated strategy. In particular,
observed USD/CNH publication must keep updating for USD allocation comparisons
after the older CNH strategy is archived.

Required benchmark work must be explicit in the calculation plan. If an archived
recipe supplies an internally replayed benchmark, calculate the dependency without
restoring its monitoring or funding status. Where a dependency requires a continuing
published strategy result, prevent its removal until its consumers are migrated.
Optional comparisons must be labelled as optional and report their absence.

Store a compact dependency receipt with each atomic calculation publication.
Check its identity again before publishing. Dependency metadata grants no approval,
promotion or execution authority.

## Retention

Retain required recipes, contracts, pinned active inputs and their existing audit
evidence. Do not protect every historical experiment or generated output merely
because a strategy shares its ancestry. Completed disposable research remains
subject to the operator's selective retention policy. Removing an executable
recipe is a distinct operation from archiving its recurring report.

## Developer preflight and migration

Run `.venv/Scripts/python.exe scripts/check_strategy_dependencies.py --contracts-only`
to validate the complete registry without a database. Run the same script with
`--key <strategy-key> --action archive`, `modify` or `retire` for a read-only
preview against current monitored, funded, SOTA and pending roles. A blocked
preview exits nonzero. It never changes membership, definitions or fingerprints.

For a behavior change, retain the old executable version, introduce the new
version, declare and pin its dependencies, test its consumers and migrate those
consumers explicitly. Do not regenerate old fingerprints as a repair. Existing
promotion, allocation and execution approval requirements still apply. For a
shared implementation change that preserves the declared executable contract,
inspect all affected services/consumers, run the relevant regression/native
checks, and publish a new calculation revision under the existing code hashes.

Recipe inheritance is an acyclic graph. Report benchmark edges are kept separate:
two independent calculations can compare each other's results without forming a
recipe cycle. `requires_monitoring` is reserved for an actual continuing-result
contract; current internally replayed benchmarks do not need to masquerade as
monitored or funded strategies. Optional comparisons are distinct from required
benchmarks and must disclose missing coverage.

The registry snapshot and resolved plan are retained in the tracked calculation's
`dependencies` document; its provenance also contains the dependency receipt.
This records the contract used by that publication even after a later migration.

## Incident motivating the change

On November 7, 2026 the allocation comparison stopped at October 30 even though
USD strategy results and observed FX captures reached November 6. FX publication
was coupled to a legacy CNH loader and stopped after that strategy was archived.
The independent FX publication repair and dependency guards address separate
parts of the failure: restoring the current chart and preventing hidden lifecycle
coupling from recurring.
