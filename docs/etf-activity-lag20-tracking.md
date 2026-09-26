# App-native tracked strategy calculations

The user chose **track ETF lag-20, do not promote**. The subsequent correction makes the application responsible for all recurring calculations. The Codex heartbeat `track-etf-lag-20-research-candidate` was deleted; the earlier research card and daily-review publisher are superseded. Their immutable historical publications remain audit evidence.

## Executable strategies and engines

`etf_activity_lag20_definition()` registers a complete versioned strategy: current SOTA's inverse-volatility allocation, top-six price/volume filter, technical regression tree, relative momentum and adaptive trend, followed by the unchanged lag-20 activity overlay. The overlay remains EMA 10, normalization 63, prior noise 126, second difference lag 20, threshold 0.5, directional confirmation, 15% relative tilt and 3 percentage point active cap. No Hurst filter, parameter retuning or new selections. `current_sota_definition()` is unchanged and remains the production SOTA.

`config/strategy-monitoring.json` declares monitored strategy IDs, audited historical boundaries, pinned model/legacy FX evidence, execution assumptions and engine. Every monitored ID must resolve to a complete executable definition; unsupported definitions fail explicitly instead of becoming static holdings marks. The reusable registered adapter currently supports monthly strategies on the multi-asset ETF universe.

- `calculation.engine: lean`: native LEAN signal/fill/NAV replay plus the existing Python oracle; all parity checks must pass. Successful receipts are also registered in PostgreSQL.
- `calculation.engine: python`: the same immutable definition, data, monthly signal schedule, next-open execution, whole-unit cash accounting and fees run through the app's Python engine in an isolated process. This mode is explicitly labelled Python; it does not claim a native LEAN validation for that run.

Both modes preserve source and input hashes and write immutable calculation directories below the app data directory's `tracked_strategies/`. The analytics worker checks input and definition revisions, calculates changed versions and publishes all monitored results atomically to ClickHouse (`tracked-strategies/calculations`). Unchanged revisions are a no-op. `POST /api/v1/strategies/refresh` and the full report's **Refresh calculations** button wake the application worker. An agent, prompt, notebook or human is not needed to keep a strategy calculated.

## History and benchmarks

The default chart covers **2016 onward** (with a December 31, 2015 initial-capital anchor), not just 2023. The prior card showed only the deployed frozen-model companion because its tree was trained before 2023. Applying that same model backwards would introduce lookahead. This report uses the previously pinned annual causal models in 2016–2022, then the deployed frozen model from 2023 onward, for both SOTA and its lag-20 enhancement. The regime change is labelled on the chart. This is a declared historical reconstruction; it is distinct from the earlier research study which refitted annually through 2026. It is not an untouched out-of-sample result.

Benchmarks share the same sessions, initial capital, audited prices, supported FX and modeled 5 bps fees:

- Monthly inverse-volatility **risk parity on the same ETF universe**, with the same cap/cash rules and no alpha overlays.
- **URTH** buy-and-hold, adjusted for distributions, with a fee on entry and whole CNH-adjusted units.
- **Current SOTA**, using the identical historical model regime and current deployed definition.

Candidate and SOTA execute through the shared full report renderer: benchmark selection, performance/Sharpe/IR/tracking error, allocation background, drawdowns, yearly/quarterly/monthly metrics, holdings/contribution and signal attribution. Attribution compares lag-20 with SOTA, and SOTA's combined allocation/alpha overlays with matched risk parity; this labelled attribution baseline is independent of the chart's benchmark selector. The full decision flow and deployed regression-tree branch thresholds/leaf forecasts are included, with zoom and pan. Causal reconstruction and deployed-model periods are labelled separately, not misnamed IS/OOS.

## Current weights and value

The app calculates daily marked portfolio value and held weights from **actual simulated fills**, not requested order quantities. The page also shows the last monthly target and indicative targets recalculated from the latest complete price history. Indicative targets do not rebalance the simulated book before the next scheduled session and do not place broker orders. Data-through, valuation date, target known-through, last/next rebalance, calculation engine and timestamp are visible. Country exposures describe the underlying ETF basket; the existing adjusted-unit simulation accounts in CNH although the ETFs quote in USD.

Forward monitoring begins September 28, 2026. Earlier observations stay historical; late reconstructions are not evidence of contemporaneous signal capture. No capital is allocated by this analytics service. Current SOTA, approval policy, broker routing and promotion controls are unchanged.

## Data gates and failure behavior

Prices and signal volumes come only from committed audited histories, pinned to the batch and verified manifest files. Raw provider downloads and canonical daily bars are not fallback research inputs. Every strategy session must match the calendar; no interpolation, dropped-session shortcut or data-dependent survivor change.

The existing legacy FX snapshot through September 24 remains explicitly uncertified historical evidence. New USD/CNH observations require stored IB MIDPOINT evidence: the normalized result must equal the raw USD/CNH leg, OHLC must be valid and capture must follow 17:00 New York close. Original files, hashes and availability timestamps are retained and the validated observations are published to ClickHouse (`governance/fx-usd-cnh`). This validation does not retroactively certify historical FX or price vintages. It does not substitute CNY or manufacture missing FX.

A missing FX session stops valuation before the gap while latest price-only targets can remain current. Missing/invalid price inputs, changed pinned artifacts or failed engine checks retain the last complete publication and expose an app error, never fallback to stale final holdings as though signals replayed. New audited revisions produce a separate reproducible calculation version; past publications remain available as evidence.

The calculation worker pins the implementation loaded at process startup. Changed calculation source requires a guarded application restart before it can publish a new revision, and the source is checked again before committing a completed run. A failed strategy calculation preserves the previous strategy/dashboard publications while unrelated account, execution and raw-data analytical imports can continue.
