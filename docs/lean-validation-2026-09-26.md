# LEAN validation evidence

Status: complete; every requested case passed

Engineering parity only. Legacy FX, adjusted vintages and fixed universe are uncertified; pre-2023 is fitted and post-2023 has been used in strategy selection.

`quantconnect/lean@sha256:27f27a17149211a6a523430c537663bc12ee8fc5c504e54fc34a76c880e1bc59`

| Case | Sessions | End NAV (CNH) | Return | Max drawdown | Python wall (s) | LEAN wall (s) | LEAN peak RSS (MiB) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| fixture-targets | 51 | 1,028,817.41 | 2.88% | -3.30% | 0.69 | 11.90 | 560.2 |
| fixture-targets repeat | 51 | 1,028,817.41 | 2.88% | -3.30% | 0.56 | 11.83 | — |
| fixture-shared | 51 | 1,028,817.41 | 2.88% | -3.30% | 0.72 | 12.35 | 587.1 |
| fixture-stress | 51 | 1,029,302.65 | 2.93% | -3.30% | 0.78 | 12.07 | 570.7 |
| year-sota | 250 | 1,191,346.45 | 19.13% | -7.30% | 1.17 | 14.26 | 613.2 |
| year-benchmark | 250 | 1,126,887.51 | 12.69% | -5.30% | 0.79 | 13.30 | 597.1 |
| year-cost | 250 | 1,164,630.79 | 16.46% | -7.75% | 1.05 | 14.44 | 593.2 |
| year-delay | 250 | 1,191,812.88 | 19.18% | -7.58% | 1.20 | 14.82 | 618.0 |
| year-lookback42 | 250 | 1,187,948.16 | 18.79% | -7.25% | 1.21 | 13.42 | 596.9 |
| year-lookback84 | 250 | 1,188,801.66 | 18.88% | -7.23% | 1.09 | 14.16 | 617.7 |
| full-sota | 3330 | 3,204,641.45 | 220.46% | -14.17% | 30.33 | 46.14 | 868.0 |
| full-benchmark | 3330 | 2,023,244.37 | 102.32% | -16.79% | 17.84 | 39.50 | 872.5 |

All cases require exact decision sessions, symbol sets, integer fills and final holdings; target tolerance is 1e-8 and cash/fee/NAV tolerance is 0.01 CNH. The repeated fixture must produce the same normalized economic hash.

Wall time includes process/container startup. Process CPU and peak RSS, engine labels, runtime versions, event counts, artifact sizes, fitted/post-2023 metrics and hashes are in summary.json. Python runs on Windows and LEAN on Linux with 2 CPUs/4 GiB limits. These timings describe this setup; image download time is excluded. No cold-cache flush is performed against the operating platform.

The long-history case executes 2013-02-01 through 2026-04-29 with warmup from 2012-01-05. This is a separate adjusted-CNH-unit scenario, not a reproduction of the older USD-cash performance claim. Native engine results remain research-only.

## Retained artifacts and integration

Suite root: `D:/systematic_trading_data/lean/validation/20260926-v1/`. Each case has a frozen input/source manifest and separate immutable output directory. Twelve completed runs (eleven cases plus identical replay) were inserted into `ops.lean_research_runs`; repeat insertion was verified idempotent.

Pinned official image release label: `18130`, .NET 10; observed embedded Python 3.11.14. The container runs without network, broker credentials or project environment files. Filesystem/input are read-only; output is isolated; limits are 2 CPUs, 4 GiB memory, 512 PIDs and 900 seconds per engine.

The fast Python engine remains useful for short research cycles. LEAN provides independent event-driven execution/accounting validation. This benchmark does not support replacing Python on speed grounds. Missing historical vintage/universe/FX evidence and unsupported raw corporate-action/TWAP scenarios still block promotion.

See [worker usage](lean-backtesting.md) and [platform audit](platform-audit-2026-09-26.md).
