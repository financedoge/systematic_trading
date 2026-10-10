# FR25 tracked strategy

The user authorized monitoring `research_fr25_14_v1` (FR25) on October 10, 2026,
after the frozen full-pool selection study. Like every tracked strategy, the
application owns the recurring calculation. No agent, notebook, reminder or
manually maintained research card produces FR25 numbers.

Monitoring is not promotion. FR25 grants no capital, approval, reconciliation or
broker authority, and it is not allocation-ready.

## Executable definition

`fr25_definition()` in `research/strategy_catalog.py` registers a complete,
versioned `multi_asset_14` strategy on the existing `static_monthly` scheduler:

- **Candidate pool**: the original 12 ETFs plus XLE and XLB. Assets compete for
  six slots; none is forced into the portfolio.
- **Selection**: 75% of the M1 score rank and 25% of the financial-ridge
  total-return forecast rank, combined as midranks across all 14 candidates
  *before* the eligibility gate. Exact ties resolve by symbol order.
- **M1 score**: 75% momentum over 21/63/126 sessions and 25% volume.
- **Eligibility**: positive 126-session momentum gate, top six with a minimum of
  four, and the existing defensive-cash fallback. With fewer than four positive
  qualifiers only qualifying IEF/TLT/GLD weights survive and the rest is cash,
  with that budget protected through later overlays.
- **Financial ridge**: five published series (T10Y3M, T10Y2Y, NFCICREDIT,
  DRTSCILM, DRTSCIS) produce eight features; per-ETF standardized expanding ridge
  with alpha 1 and at least 36 completed monthly labels.
- **Downstream layers** are unchanged from M1/14: causal monthly XGBoost sizing,
  relative and adaptive trend, audited raw dollar trading activity, and the USD
  ridge.
- **Final cap**: ETF targets are capped at 45% and the excess remains cash. Held
  weights may still drift between monthly rebalances.

XGBoost carries **zero selection weight** in FR25 and keeps only its existing
downstream sizing role. Missing or incomplete financial inputs revert the whole
selector to original M1 ranking, eligibility and fallback; the downstream sizing
and the final cap still apply. The model never fills a gap from a later vintage.

Registered parameters (`fr25_tracking.PARAMETERS`) are frozen:
version `fr25-financial-selection-v1`, group `financial`, blend `R25`, ridge
alpha `1`, minimum labels `36`, forecast `total_return`, momentum weight `0.75`,
financial weight `0.25`, XGBoost selection weight `0`, prospective start
`2026-10-10`.

## Calculation and publication

FR25 runs inside the regular analytics service. `tracked_runtime` loads its
financial inputs and replays it through the shared evaluator alongside M1/14, so
the candidate and parent strategies share one price-publication batch and one
atomic ClickHouse publication. The published calculation carries monthly
scheduled decisions, fills, daily NAV, held and target weights, the matched
risk-parity benchmark, the full decision flow and an inspectable rank table for
every decision.

The calculation revision binds code, published inputs and the monitoring
generation. A changed revision discards obsolete work and retains the last
complete publication, so an interrupted recalculation can never become current.

## Availability contract

Historical financial inputs assume ALFRED archive availability one calendar day
before the prior trading close. That is an explicit retrospective assumption,
not evidence that the application held the data. **From October 10, 2026** a
decision additionally requires actual application capture before its cutoff;
late recorder catch-up cannot backdate economic knowledge, and an unavailable
series abstains rather than being filled.

## Monitoring evidence

Registered at membership generation 4, membership revision 4. Research parity was
verified against the frozen selection-blend protocol
`5399931f5267d8beceb1ff52b15d84a81547f4f1e8a285a413bace7702769276`:

- 130 decisions, 898 fills, 2,707 daily NAV observations, 130 model fits, final
  positions matched.
- Evidence: `var/research/fr25-monitoring-20261010/`.

Parity is bound to the audited price batch it was run against. That verification
used batch `4bfdef17…`; the live runtime revision is calculated on the newer
committed batch `b02d9372…`. They are distinct evidence versions of the same
frozen recipe and their outputs are not bit-identical — the first differing NAV is
2016-02-25 (about 48 CNH) and recent rebalances differ by about one share. This is
the documented "a new audited revision produces a separate reproducible
calculation version" behaviour, not a code, definition or contract change. Any
future exact-parity claim must name its batch. `runtime-final.json` records both
batches and re-verifies 11 native parity receipts.

## Limitations

FR25 was selected from a predeclared finite menu over an already-inspected
sample. It passed practical effect-size, mean-only, cost/delay and risk-budget
screens, but **no** contrast passed 5% Holm across the 50-comparison return
family, and recent substitutions concentrate its advantage. It is a research
candidate under monitoring, not an established superior strategy.

The report states these limitations explicitly, including the retrospective
selection, the cap and drift behaviour, and the archive-availability assumption.
The research record is in `docs/research-state.md`; the complete study is
`research/selection-blend-2026-10-10/index.html`.
