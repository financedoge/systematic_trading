# Governed strategy assets

The operator's November 7 decision separates reusable inputs from portfolio
construction. The asset pool is at `/strategy-assets`; the Strategies page starts
with **Tracked signal assets**. Time-series, signal and model versions have their
own contracts, input DAG, provider, price/activity basis, availability, cadence,
missing-data rules, monitoring contract and pinned fingerprint. Composite recipes
declare exact asset versions. Recipe ancestry remains a separate dependency graph.

## Demand and registration

`research/strategy_assets.json` is the checked-in catalog. Its initial migration
maps all 15 registered composites to existing app providers without retuning or
changing portfolio rules. Normal calculation replay may rebuild verified rolling
caches under new implementation hashes; the frozen fitting policy is unchanged.
`strategy_assets.py` resolves and deduplicates demand
from monitored strategies, SOTA, active/pending roles and required benchmarks.
Shared asset definitions survive archival. An unused derived asset becomes idle;
raw-data capture retains its separate audit/recorder ownership. Tracking an asset
does not create a funded strategy or grant execution authority.

Each signal has a monitoring contract. The signal panel is derived from the
resolved DAG, including indirect dependencies, rather than a manually maintained
strategy-name map. Missing diagnostics appear as **insufficient evidence**; a
current portfolio result is not proof of signal effectiveness. The older
cross-sectional rank-IC panel is explicitly labelled Rank-signal decay.

Registration requires a recorded asset-pool search and reuse decision in
`reuse_reviews`, covering the chosen direct inputs. Search by name, methodology,
provider, basis and universe. Matching names do not imply compatible semantics.
Existing twelve- and fourteen-ETF rolling/USD models remain different assets.
Legacy adjusted activity and audited raw-dollar activity also remain separate.

```powershell
.venv/Scripts/python.exe scripts/check_strategy_assets.py --search rolling
.venv/Scripts/python.exe scripts/check_strategy_assets.py --composite research_fr25_14_v1
.venv/Scripts/python.exe scripts/check_strategy_assets.py --contracts-only
.venv/Scripts/python.exe scripts/check_strategy_dependencies.py --key research_fallback_f3_v1 --action archive
.venv/Scripts/python.exe scripts/check_strategy_assets.py --retire broadtrend-signals-v1
```

The search and preflight commands are read-only. `seed_strategy_assets.py` is the
initial migration only and refuses to overwrite a catalog. Never regenerate pins
to bypass a contract mismatch. Introduce a new version and migrate consumers.

## Calculation and evidence

The application includes the registry and resolved asset plan in calculation
identity and atomic publication, and rechecks demand/lifecycle before commit.
Existing model/data adapters continue to implement their audited recipes. Model
fits retain their verified caches and receipts. This migration does not claim
that every legacy forecast is already an independently materialized time-series:
the catalog distinguishes source publications, calculation lineage and actual
published per-decision observations. Unsupported diagnostics remain visible.

BroadTrend is decomposed into `signal_history` (per-ETF causal filter, HMM,
long/cash, stop and virtual sleeve series) and the composite capital/allocation
replay. The composite consumes that same prepared signal history once. The
application publishes the history independently of the portfolio anchor, plus
current states, actual publication times and pinned input lineage. It can maintain
the signal for another declared consumer after the BroadTrend portfolio report is
archived. Idle history is preserved by reference to its original publication,
without copying the observation rows or advancing the archived report.

BroadTrend inspection includes adjusted prices, scores and long/cash intent for
each ETF. Prospective diagnostics start October 30, 2026. A completed daily label
uses decision close t, open t+1 and open t+2, and compares the long/cash direction
with that forward return. Pending outcomes stay unavailable. Counts use trading
dates, not 51 supposedly independent ETF observations. This is a gross descriptive
association, not portfolio alpha, a calibrated probability or a cost-adjusted
edge. The net portfolio report remains the source for actual simulated costs and
returns. No effectiveness/decay threshold is approved for these independently
timed policies, so the panel exposes evidence and an insufficient verdict rather
than substituting the rank-IC test or labelling recent data healthy.

## Retirement and concurrency

Every strategy archive checks and records dependency impact on the server,
including non-UI callers. The dialog previews continuing and newly idle assets;
its review hash is revalidated on save. Existing membership revision and
allocation-role guards remain, with the asset-lifecycle revision added.
Physical executable removal remains a separate blocked preflight when retained
consumers exist; archiving never grants removal authority.

Asset retirement has a separate transactional scope (`strategy-assets-v1`).
`GET /api/v1/strategy-assets/{id}/retirement` supplies a review hash. The guarded
POST requires that hash, revision, idempotency key, operator and reason, rechecks
dependencies, and records immutable evidence. It rejects retained composite and
asset consumers, including archived composites that must remain restorable.
The transition preserves definitions and publications; it deletes no files.
New demand cannot use a retired version. Asset retirement and strategy membership
share the existing transactional revision guards.

Disposable historical research outputs still follow selective retention. A recipe
or asset reference does not protect every exploratory file forever. Protect
current materializations, pinned active inputs and operational evidence under
the existing storage policy.

## Future composite development

1. Record the asset-pool search, versions inspected and reuse decision first.
2. Define each missing series/signal separately, including units, universe,
   basis, calendar, availability/capture boundaries and missing-data behavior.
3. For rolling models, freeze training windows, label completion/embargo,
   refit/inference cadence, artifact hashes and chronological validation.
4. Register its version, upstream pins and monitor. Publish actual observations
   and an appropriate health diagnostic; disclose any unimplemented diagnostic.
5. Compose portfolio selection, sizing, timing and execution contracts from those
   assets. Preserve dynamic-rebalancing controls and promotion discipline.
6. Test reuse, automatic monitoring, archive demand and retirement impact, plus
   strategy/native parity. Tracking must not require editing a separate UI list.
