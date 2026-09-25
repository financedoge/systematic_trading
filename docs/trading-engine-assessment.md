# Trading engine assessment: LEAN and NautilusTrader

Assessment date: 2026-09-25. Documentation review and project fit assessment; neither engine was installed, benchmarked or connected to the account.

## Recommendation

Keep the current operator, approval, audit and storage services. Evaluate **LEAN first as an independent backtest and strategy-validation engine** for the existing monthly ETF strategy. Do not replace the live order manager as part of that experiment. Evaluate **NautilusTrader as a separate candidate for intraday event processing and execution** if intraday strategies become a funded priority or measurements show the present implementation cannot meet its reliability or throughput requirements.

This follows the existing `industrial-platform-plan.md`, which already selects LEAN or a LEAN-equivalent validation stage. Collecting five-second bars by itself is not a reason to replace the whole trading platform. Our observed outages involved Docker sockets, machine-local paths, an old IB client warning and broker sessions; switching engines does not inherently fix those causes.

## Comparison for this repository

| Decision | LEAN | NautilusTrader |
| --- | --- | --- |
| Current monthly, long-only stock/ETF allocation | Preferred first evaluation: portfolio simulation and equity lifecycle modeling align with the present strategy. | Feasible, but validate equity lifecycle and reporting requirements in the pinned release before porting. |
| Intraday/tick-driven strategies | Supports event-driven algorithms; measure behavior with our feed and execution requirements. | Strong candidate for an event-driven runtime with Rust core and Python strategy interfaces. Performance still needs a local benchmark. |
| Broker integration | IB integration, including an external Gateway connection. | IB adapter for market data, historical requests and execution through TWS/Gateway. |
| What we must retain | Human approvals, risk/reconciliation gates, evidence registry, CNH accounting checks and audit continuity. | The same controls; the engine's reconciliation is not automatically equivalent to ours. |
| Data migration | Export normalized data plus the required equity metadata; do not double-count dividends in already-adjusted prices. | Map instruments, timestamps, bars and event identities into the pinned version's data/catalog contracts. |
| Deployment implications | C# engine with Python/C# algorithms; CLI/container integration is separate from our native Python service. | Rust/Python package; stable v1 and v2 documentation/package APIs must not be mixed. |
| Practical next step | Frozen-input SOTA replay with a parity report, without brokerage access. | Offline tick/bar replay and restart/reconciliation experiment before any routing experiment. |

The preferences in this table are engineering judgments for this repository, not measured rankings of engine speed or strategy returns.

## Evidence and constraints

LEAN exposes configurable fill, slippage, fee, buying-power and settlement models. Defaults assume liquid instruments and are not automatically a faithful model of our next-open TWAP. Its equity handling includes dividend and symbol-change events. This is useful for improving the daily simulation, provided the underlying data and normalization are correct. Our CNH ledger, global exchange coverage and fractional/whole-share policy need explicit acceptance tests. [Reality modeling](https://www.quantconnect.com/docs/v2/writing-algorithms/reality-modeling/key-concepts), [equity corporate actions](https://www.quantconnect.com/docs/v2/writing-algorithms/securities/asset-classes/us-equity/corporate-actions).

LEAN's source is Apache-2.0 licensed. The supported QuantConnect LEAN CLI workflow currently requires membership in a paid-tier organization; data and cloud services are separate decisions. Running the open-source engine directly involves a different build/operations burden. An external Gateway is supported, but then login and Gateway maintenance remain ours. Its managed IB deployment also requires weekly authentication. Do not launch a second engine-managed Gateway with the same username alongside the active platform. [LEAN source](https://github.com/QuantConnect/Lean), [IB deployment and external Gateway](https://www.quantconnect.com/docs/v2/lean-cli/live-trading/brokerages/interactive-brokers).

NautilusTrader combines deterministic event-driven simulation and live execution, with a Rust core and Python interfaces. Its repository currently distinguishes stable v1 installs from the v2 prerelease documentation; pin a release and its matching docs before evaluating it. The source is LGPL-3.0 licensed. These are version and integration considerations, not a conclusion that Windows or this PC's Python is unsupported. [NautilusTrader source and installation notes](https://github.com/nautechsystems/nautilus_trader), [installation guide](https://nautilustrader.io/docs/latest/getting_started/installation/).

The current development IB adapter documents market-data, historical and execution clients using one external Gateway and distinct client IDs per process. IB still controls pacing, entitlements and historical availability. Its engine reconciliation handles bounded history and missing reports, but cannot manufacture old executions the broker no longer returns. We must preserve our durable fills and baseline/recovery evidence and test adapter-specific restart behavior. These development-branch capabilities must be confirmed against the release selected for a pilot. [IB adapter guide](https://github.com/nautechsystems/nautilus_trader/blob/develop/docs/integrations/interactive_brokers.md), [reconciliation](https://nautilustrader.io/docs/latest/concepts/execution/reconciliation/).

Neither engine removes IBKR's weekly authentication requirement or converts our delayed feed into entitled realtime data. [IBKR restart policy](https://ibkrguides.com/traderworkstation/auto-restart-considerations.htm).

## Proposed evaluation and migration boundary

1. Freeze one strategy specification, data snapshot, calendar, FX inputs and software versions. Audit point-in-time availability first; the restored legacy dataset is not automatically certified research input. Include splits/dividends, a month-end, an early close and missing data.
2. Implement the monthly SOTA strategy in a separate LEAN experiment. Export a chronological decision/target/order/fill/cash/NAV report. Compare targets within a declared numeric tolerance, require exact agreement on intended session and integer quantities where the policies match, and explain every cash/NAV difference by fees, FX, corporate actions or execution assumptions. Identical headline Sharpe is not an acceptance test.
3. Benchmark identical workloads on this PC: elapsed backtest time, peak memory, event loss/duplication, restart recovery, and the effort needed to reproduce artifacts. No performance benefit has been measured yet. Add a Nautilus replay using the same recorded intraday input only if the intraday roadmap justifies it.
4. Keep the chosen engine in shadow mode: it emits versioned targets/proposals to our existing approval service and has no order-submission access. Preserve Postgres as the authoritative audit store and ClickHouse/raw files as replayable inputs. There must be exactly one broker order writer.
5. Consider replacing the order manager only after explicit order/execution identity mapping, full/partial-fill recovery, cancellation, reconnect, cash reconciliation, missing-history behavior and delayed-data exclusions pass fault tests and a supervised paper soak. Include a monthly rebalance or equivalent deterministic replay; do not claim readiness from a few successful connections.
6. Rollback means stopping the candidate writer before re-enabling the original, then reconciling broker state. Retain both engines' immutable evidence and do not merge divergent order histories automatically.

Proceed with the Gateway operational consolidation now. A bounded LEAN validation pilot is worth doing next; a wholesale migration to either engine is not justified by the current evidence.
