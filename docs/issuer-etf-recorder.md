# Issuer ETF fundamentals pilot — 2026-10-09

The application now captures XLE, XOP and XLB issuer snapshots every six hours,
with independent publication per fund. Inspect them in **Market Data → ETF
Fundamentals** (`/platform/market-data-audit?view=issuer`). This is a data
qualification milestone, not a strategy admission or a performance result.
The trading boundary remains ETFs only; recording an ETF's constituent names
does not create individual-stock candidates.

## Price admission and first universe control — completed 2026-10-09

**Scope correction:** The user requested candidate-pool expansion, not compulsory
portfolio allocations. The first price-only inverse-volatility experiment below
does not answer that request. The [corrected top-six candidate-pool and momentum
study](../research/candidate-pool-momentum-2026-10-09/index.html) is complete:
XLE/XLB enter only when selected, four momentum policies have matched 12/14
controls, and no strategy has been promoted. Existing-rule expansion weakens
Sharpe; faster momentum is a research lead with unresolved statistical evidence
and a larger full-history drawdown.

XLE and XLB now each have 6,991 audited published sessions from 1998-12-22
through 2026-10-08. The common catalog pin is
`4bfdef171ba1d180f2191c589d269a9ad42e2f497b9f069b80e1e9043668f3fd`.
The research ETF recorder verifies issuer ISIN, inception and exact listing
date before publication. Historical availability and reconstructed price-basis
limitations remain; current identity checks do not establish historical availability.

XOP remains quarantined: the issuer reports listing on 2006-06-23, while the
provider's first-trade metadata and first bar are 2006-06-22. The original
capture is preserved in `var/governance/research-2026-10-08-f7edd995880b/`.
An explicit admission hold preserves that evidence and lets the other funds
refresh independently. Do not trim the first bar or reinterpret the listing
boundary without independent dated evidence.

Read-only paper IB ISIN queries verified the current BIL/XLE/XOP/XLB contract
identities (USD, STK, ARCA, SMART). Account/product permission and settlement
eligibility remain unverified. Contract discovery neither grants those permissions
nor constitutes an order preview; no order was submitted. Evidence:
`var/research/etf-admission-20261009/ib-identity.json`.

The [first frozen universe control and full strategy reports](../research/energy-materials-universe-2026-10-09/index.html)
compare the original 12 ETFs with those same ETFs plus XLE/XLB under identical
monthly inverse-63-session-volatility sizing, a 45% target cap and 2% cash floor.
This isolates the opportunity set before introducing ranking or new information.
The current app-owned F3 and URTH are separate benchmarks. Original
F3 prices, quotes, decisions, fills, NAV and final positions reproduce exactly.

| Full period, 2016-01-04–2026-10-08 | CAGR | Sharpe, zero reference | Calmar | Maximum drawdown |
| --- | ---: | ---: | ---: | ---: |
| Original 12, inverse volatility | 5.73% | 0.748 | 0.255 | -22.46% |
| Add XLE/XLB, inverse volatility | 6.16% | 0.753 | 0.311 | -19.81% |
| Current F3 | 9.85% | 1.050 | 0.600 | -16.42% |
| URTH buy and hold | 12.73% | 0.795 | 0.380 | -33.54% |

USD accounting, 5bp costs and zero-interest cash are explicit scenarios.
The predeclared 0.05 Sharpe-improvement threshold fails (+0.0056); Calmar,
return budget, drawdown and cost/delay checks pass. Paired 3/6/12-month block
intervals include zero for return, Sharpe and Calmar changes. Return p-values
range 0.224–0.265. Reject this unchanged-sizing expansion under the declared
screen; this does not reject every possible energy/materials strategy.

All 14 cost/delay replays, four full native parity checks and three 10,000-draw
uncertainty jobs completed using the 16 logical CPUs, with memory-bounded native
concurrency. The frozen protocol SHA-256 is
`0d25e4fb623a25cbe52cceb0e5ae1e3c76b5244f3c961c1a3bfc424d0335ff7a`;
inputs, source, bundles and receipts are in
`var/research/energy-materials-universe-20261009-v1/`.

This is retrospective selection research, not an untouched holdout or a claim
about expanded F3/XGBoost. New arms use adjusted prices only; the frozen F3
benchmark retains its disclosed legacy volume-proxy limitations. No uncertified
FX or prospective issuer/EIA/CFTC observations enter the new historical arms.
Holdings residuals and split-aware issuance remain unresolved. Current monitored
definitions and execution authority are unchanged. Next is P4.11 cash-reserve
and stress-deployment research on the retained parent/universe; expanded ranking
and new feature models remain separately specified future experiments.

## Sources and interpretation

| Pilot | Official source | Exposure distinction |
| --- | --- | --- |
| XLE | [State Street fund page](https://www.ssga.com/us/en/individual/etfs/state-street-energy-select-sector-spdr-etf-xle) | Broad energy equities, including producers, integrated firms, refiners and services. |
| XOP | [State Street fund page](https://www.ssga.com/us/en/individual/etfs/state-street-spdr-sp-oil-gas-exploration-production-etf-xop) | Exploration/production plus refining/marketing and integrated firms; not a pure upstream or physical-oil exposure. |
| XLB | [State Street fund page](https://www.ssga.com/us/en/individual/etfs/state-street-materials-select-sector-spdr-etf-xlb) | Materials, including chemicals, metals/mining, packaging and construction materials; not a pure chemicals exposure. |

Each page links its daily holdings workbook, captured with the page. Eight
statistics cover NAV, shares outstanding, AUM, estimated 3–5 year EPS growth,
holding count, price/book, forward FY1 P/E and weighted average market cap.
Industry/sub-industry allocation is a separate dated table. Issuer definitions
describe price/book and forward P/E as harmonic aggregates; the EPS estimates
come from the issuer's FactSet-based aggregate. These are published estimates,
not our own reconstruction of company statements or original analyst vintages.
Preserve this distinction when specifying features and interpreting cyclicals.

Source files are public retrievals retained locally for internal inspection.
This does not establish redistribution rights or entitlement to a historical
holdings/estimates feed. Tests use synthetic source shapes, not redistributed
issuer pages or workbooks. No subscription was needed for these snapshots.

## First captured observations

NAV, characteristics, holdings and allocation have issuer as-of date October 7;
listing metadata is dated October 8. Actual first captures occurred October 8
UTC (October 9 in the operator's Asia/Shanghai timezone):

| Fund | First capture (UTC) | Holdings rows | Reported weight sum (%) | Residual to 100 (percentage points) |
| --- | --- | ---: | ---: | ---: |
| XLE | 16:21:59.873391 | 24 | 100.000861 | -0.000861 |
| XOP | 16:22:03.036322 | 54 | 99.977651 | 0.022349 |
| XLB | 16:22:06.157480 | 27 | 99.915674 | 0.084326 |

NAV × shares reconciles to AUM within the displayed precision for all three.
Holdings include cash, a government money-market position and small futures
valuation weights. The issuer's security counts are 21, 51 and 24 respectively;
they are distinct from total workbook rows. Constituent sector cells are blank
markers and remain missing; they are not populated from today's classifications.
Futures valuation weights are not derivative notionals.

All three weight residuals exceed the rounding allowance justified by the six
displayed decimals. Their cause is unresolved. The snapshots publish for
inspection with a yellow warning, but the research reader rejects the holdings
feature group. No renormalization, invented balancing cash or relaxed threshold
is used. NAV, characteristics and industry allocation have separate admission
checks and can be read prospectively without granting holdings feature access.

Publication pins:

- XLE: `e8161f64469b7b16a817e9a0a08018fd5b4e47ef8ec29cfe098049e5b8cedc89`
- XOP: `537222b207e9c7ea67b4f72d4a4da3123429b74902bb391f5d1a2066205ae2b2`
- XLB: `d00d70f01950dc7120ae2c939ccba9a659fb1356a0e627e92a647229df5a7ab9`

## Recorder and reader contract

`config/issuer-etf-recorders.json` defines the source and identity registry.
The analytics research lane calls `refresh_issuer_etfs`; the operational CLI
`scripts/run_issuer_etf_recorder.py` invokes the same service. Immutable evidence
lives under `var/governance/issuer-etfs/<symbol>/`. Raw responses and completion
timestamps precede parsing. A manifest covers the original page/workbook,
receipt, normalized snapshot, configuration and copies of parser/recorder code.
Failed attempts remain evidence; they cannot replace a committed publication.
One fund failing does not stop the other funds from updating.

Snapshots preserve each section's as-of date. Changed values at unchanged dates
create a new revision with a later capture time. Unchanged observations keep
their original capture time. Source date regressions, future dates, identity
mismatches, unsupported units, malformed tables/formulas, duplicate holdings,
missing holdings weights and unreconciled NAV arithmetic fail validation.
Missing valuation metrics are preserved as missing and block that feature group.

`IssuerInputs(root, batch).snapshot(decision_at=..., groups=[...])` requires an
explicit published pin, verifies all selected evidence hashes, admits captures
strictly before the decision, enforces seven-day freshness for each requested
section and returns only those validated sections. It never substitutes an older
complete snapshot for a newer incomplete one. `capture(batch)` is an inspection
API, not a feature-admission shortcut. Displayed issuer dates do not establish
historical publication availability; no snapshot may be used in earlier training
rows or decisions. Historical source archives remain inspection-only.

The read-only catalog/history API checks publication and capture pins; a changed
catalog returns a refresh conflict. The UI distinguishes yellow missing-data or
coverage warnings from red verification/system faults. Snapshot selection, dated
statistics, industry weights and full holdings are available outside Debug mode;
manifest details are under Debug.

## Next admission and research work

The observed governed price catalog is
`0349c76d21cd8952d4a54eebed392e58d0e826bb61888e0e96e9c4a93c47d101`.
XLE and XLB have 6,982 published adjusted/raw/raw-volume observations from
1998-12-22 through 2026-09-25, with no internal gaps at that cutoff. Their
catalog still reports provisional provider identity, uncertified historical
availability and reconstructed rather than tape-certified raw prices. XOP has
no entry. This recorder does not overwrite those qualifications.

1. Qualify price histories for the pilot through a common current cutoff. Route
   XOP through the existing ETF acquisition/audit/publication service, reconcile
   issuer listing identity, and verify the necessary adjusted-return and raw
   traded-activity bases separately. Pin new publications before research reads.
2. Resolve each IB contract by issuer identity/currency/exchange and record its
   conId, trading/settlement details and account eligibility. An issuer listing
   alone is not broker/account permission. Do not submit orders for qualification.
3. Investigate holdings residuals using issuer accounting/valuation evidence.
   Build split/distribution-aware share history before net-issuance estimates.
   Rounded shares × NAV changes are not an independently measured capital flow.
4. Freeze an expanded-universe price-only control before adding information.
   Retest top-6/8/10 ranking and the existing cash/qualifying-defensive fallback
   only as a declared finite family. Keep current monitored strategies frozen.
5. Add qualified economic/sector feature blocks with matched controls and
   per-ETF regularized linear/depth-limited tree models. Test signed responses:
   demand growth, supply shocks and feedstock costs can affect producers,
   refiners and chemical producers differently. Industry composition matters;
   XOP and XLB must not be treated as pure industry baskets. Do not label EIA
   changes or valuation levels as consensus surprises.

Historical issuer holdings, share/corporate-action history, estimates revisions,
sector financial statements, chemicals activity and refinery-margin/curve data
remain source/coverage work. Existing public EIA/CFTC captures also cannot be
backdated. Until eligible overlapping history exists, combined tests using these
new snapshots are prospective shadow research. No Sharpe/Calmar improvement is
claimed from a single captured vintage. Use all 16 logical CPUs for eligible
backtests, subject to the existing memory budget.

Source samples, exact first-publication receipts, cutoff/hash verification,
price admission inspection and runtime checks are retained locally in
`var/research/issuer-source-qualification-20261009/`.
