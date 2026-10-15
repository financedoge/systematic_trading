# FR25 execution and ETF expansion — October 13, 2026

Implementation session in progress. The user authorized execution generality and
FR25 readiness, then the reviewed ETF admission wave and larger-pool backtests.
The existing F3 capital assignment remains in force. Paper capability does not
approve an allocation, a proposal, or live routing.

## Execution contract

- A request pins one audited catalog. Allocation components reuse verified rows,
  typed bars and raw valuation marks. The signal volume basis remains explicit:
  legacy F3 keeps its existing source-volume convention; FR25 uses audited raw
  volume and raw dollar activity with adjusted-price direction.
- FR25 binds the published financial, rolling-tree and USD model schedules. Model
  receipts must agree on the committed calculation revision and the price batch.
  Exact decision cutoffs and legitimate whole-selector abstention remain intact.
- Mixed allocations use the union of frozen component instruments. Conflicting
  identities fail. The broker resolves the active allocation for each proposal,
  rather than retaining the original universe from process startup.
- An immutable execution registry retains contract details, issuer evidence
  references, audited price receipts and account-specific paper preview results.
  Routing uses conId plus listing/currency fields. A changed registry invalidates
  a bound proposal. Missing admissions, account mismatches, unsupported rules and
  expired evidence fail closed. Legacy 12-ETF migration remains compatible until
  a registry is installed; expanded universes never receive a ticker fallback.
- Initial capability is US-listed USD ETFs, the US equity calendar, whole shares
  and cent-compatible prices at or above one dollar. Fractional broker increments
  can support whole shares, but board lots, other venues/currencies and sub-dollar
  tick rules remain unsupported. The broker response's quote round lot is not
  mistaken for the minimum permissible order size.
- Broker preview evidence expires after 30 days from its capture. Republishing
  old evidence does not reset that period. A fresh controlled broker preview is
  required to renew admission; no agent reminder runs this calculation.

IB documents that [what-if requests](https://interactivebrokers.github.io/tws-api/margin.html)
calculate credit/margin effects without routing to an execution venue. The
preview service hard-codes that flag and binds a single verified paper account.
It cannot create an executable order. Preview success is evidence of present
broker acceptance, not a guarantee of future permission, liquidity or fills.

## Evidence so far

Retained session bundle: `var/research/execution-expansion-20261013-v1/`.
All 14 FR25 issuer/ISIN identities matched fresh IB contract discovery, including
XLE conId 4215217 and XLB conId 4215200. All 14 paper what-if previews returned
PreSubmitted with no warning or error. No executable order was submitted.
All 38 first-wave additions also matched fresh ISIN/currency/listing lookups;
this does not admit them for execution.

The FR25 execution/research parity tests cover both financial forecasts and
financial abstention, downstream overlays, the final 45% cap, raw-price sizing,
and mismatched calculation revisions. The cache measurement on 51,982 audited
bars across 14 funds was 1.58 seconds for initial loading and 0.00015 seconds for
reuse plus marks on this machine. This is request reuse, not an end-to-end trading
speed claim. New requests verify a fresh publication.

Before deployment, paper reconciliation was matched and warning-free at
15:31 UTC; the gateway order sync at 15:35 UTC returned no open orders. The local
ledger retains historical partial fills; absence from the gateway is not treated
as cancellation. A trading-database checkpoint was confirmed on NAS at 15:29 UTC.
Full-system backup has an older verified manifest and an active pending upload;
that is not a claim of a recent complete restore test.

## Deployment and allocation review

Deployed October 13 at about 15:45 UTC, after pausing the existing paper policy.
Post-restart reconciliation matched without warnings, and the same F3 policy,
allocation and CNH 1,000,000 cap were restored (policy revision 6). App calculations
published through October 12 under revision
`fa51c967bdb870e3a91f8a3ac78bdfe4ac7199d2df154f69701eeb6607c02b8c`.

The saved conditional 5% FR25 / 95% F3 preview has no blockers or routing warnings.
It uses October 12 valuation data and an October 14 trade date: sell DBC 89,
EWH 60 and EWJ 25; buy EWY 5, SPY 4, VGK 5 and XLE 21. This is a review artifact,
not an active allocation or scheduled order. Its token must be refreshed against
current calculations before any later operator approval.

## Expansion acceptance

The reviewed recorder configuration is enabled. It published 39 of 41 entries;
BWX has an unresolved October 2 versus October 11, 2007 listing-boundary conflict,
and XOP retains its earlier hold. All 38 additions have verified current broker
identities, but none receives execution authority from research ingestion.

The first finite comparison pins catalog
`0c3238db078c5d28201f8d8ba57e5687a793d80c3b04817d2c2d61c5f1f1b14d`.
Its 52-candidate review yields 50 supported common-window histories; BWX is held
and CPER has zero raw volume on August 23, 2018, unsupported by the current positive-volume activity contract. No missing unit
is filled. The common window begins June 19, 2018; simulated trading begins
January 4, 2021. Protocol and receipts live in
`var/research/etf-expansion-20261014-v1/`.

This is a retrospective current-cohort diagnostic. Causal features and pinned
audited prices do not establish historical universe membership or mandate
availability. Historical membership reconstruction, spread evidence and later
promotion gates remain separate requirements.

## Final acceptance — October 14 local time

The final guarded deployment completed at 16:23 UTC on October 13. Fresh paper
reconciliation matched with no warnings; the existing F3 policy was restored at
revision 8 with the same allocation and CNH cap. App calculations and reports
caught up under revision
`28d939b195f7a91c47ac1812c9a60ed27f54cacb60b9a28b916fc94c12e36b76`,
using the expanded committed catalog above through October 12.

The refreshed 5% FR25 / 95% F3 preview at 16:34 UTC has no blockers or routing
warnings. Its target weights match the earlier preview exactly. Updated account
valuation produces these seven net orders for October 14: sell DBC 89, EWH 60
and EWJ 25; buy EWY 5, SPY 4, VGK 6 and XLE 21. The final artifact is
`var/research/execution-expansion-20261013-v1/fr25-5pct-preview-final.json`.
No allocation is pending; F3 remains 100% and the order ledger still contains
270 records. This review did not submit orders or enable live trading.

Validation: full suite 1,713 passed / 55 optional skips; five additional broker
preview/frozen-runner checks passed; the dispatcher regression suite passed 14
tests, including one new progress test (1,719 distinct passed tests overall).
Ruff, whitespace, documentation links and retained archive hashes pass. Synthetic
52-asset native parity and three real control/benchmark native runs passed.
The final [expanded study](etf-expansion-findings-2026-10-14.md) rejects unchanged
expanded FR25 at its cost/IC gate; it has no expanded portfolio-return claim.

A final health check exposed transient stale-dispatcher alerts while successful
large batches were still publishing. The dispatcher now emits throttled
heartbeats after persisted publish attempts, preserving actual failure status
and the 30-second stale threshold. It does not use a background heartbeat that
could hide stuck I/O. Only the dispatcher was restarted for this fix; the
calculation process and trading controls stayed in place. Evidence and source
backups are retained in the session bundle. Existing email alert configuration,
intraday recorder/entitlement and execution-benchmark qualification gaps remain
separate operating limitations.

Final runtime sampling observed 12 dispatcher heartbeats over 48 seconds, with
maximum age 4.76 seconds and active in-batch progress. Final platform health is
`ok`, analytics reports no errors, and strategy data is current through October
12. Optional disabled/degraded services above are still disclosed.
