# Independent decision review and predictive model weighting

Completed research on the full supported52/50 ETF pool; no overlay, promotion,
broker or live changes. Report: [interactive charts](../research/decision-review-20261028-v1/index.html).

The authorized three-arm experiment compares A, the previous standing-protection
B1; B, independent price/volume entry/exit review; and C, review with established
and recent model weighting. The prior entry-value B remains the broader research
reference. A was not promoted as its universal replacement.

## Frozen design

Protocol `2fdb1cc9e3f982591d4fef9e8452d54ae55eacdb028ca32d7036028dc6feaade`.
Pinned audited published batch
`5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd`;
adjusted OHLC and audited raw volume, verified parent/input hashes. No provider
archives or online prices. Historical publication-vintage limitations remain.

Six joint features describe one/three-session returns, close location, signed
volume, relative volume and low-price change. Per-ETF shared-covariance Gaussian
class models predict positive five-session open returns and conditional expected
return. Each fit uses at most756 matured training origins; the final origin is
six sessions before cutoff. All new decision thresholds are fixed engineering
choices frozen before evaluation, not fitted to operator-nominated incidents.

C keeps the established model fixed and initializes a recent model at effective
sample size40. Stored forecasts are scored only after their labels mature.
Tempered predictive weights update continuously, including in cash. Large losses,
third/fourth consecutive losses and reversed decisions temper weights toward equal
and accelerate forgetting for21 sessions. These are working statistical scores,
not calibrated financial probabilities or a BOCPD implementation. HMM parameters
and protection distances remain unchanged. All stop levels only ratchet upward.

CUSUM-style review adds an exit when evidence contradicts the upward thesis and
allows recovery without the old HMM gate. Recovery still requires nearby price,
expected return above costs and candle/volume confirmation. A next-open price guard
cancels stale or chased recovery orders. The report provides full formulas.

## Results and decision

| Era | A Sharpe / CAGR | B Sharpe / CAGR | C Sharpe / CAGR |
|---|---:|---:|---:|
|2023–2026|0.402 /2.90%|0.402 /2.53%|0.402 /2.90%|
|2020–2022|0.312 /2.07%|0.312 /2.07%|0.268 /1.75%|

Neither challenger passes any of12 era/friction acceptance cases. Preservation
within1pp CAGR/2pp drawdown is96.08%/92.16% for B/C later and97.96%/87.76%
earlier. All results are after fees/slippage. Medians describe separate ETF
strategies, not a portfolio. Both eras are repeatedly inspected development data.

CPER2025-03-04..09-04 is+10.00% under all three; IWM2024-07-01..12-01 is−9.64%
under all three. No new recovery executes in either interval. IWM September12
fixed/adaptive forecasts52.8%/52.9% up but expected gains only0.087%/0.018%, below
0.15% modeled friction; cumulative recovery evidence is zero. November5 expected
returns are negative. The independent model does not identify these rebounds.

Recovery gate audit exactly matches recorded signals. Later C:16,445 flat watch
days;482 evidence crossings;282 also pass probability/value;22 pass nearby price;
1 passes all filters and is cancelled at next open. Later B has no signals.
Earlier B completes1 recovery (loser); C3 (all winners), with4 other orders
cancelled. This is insufficient to establish useful recovery behavior. Features
and hard confirmation gates duplicate some information and jointly overrestrict.

Forecast IC medians B .014/.004 and C−.040/−.004 later/earlier. Median Brier gains
relative to fixed training up-rate are negative for both; C−.0053/−.0043.
No predictive benefit demonstrated. Removing warning acceleration restores C's
earlier median Sharpe to .312. Fifty-bp stop-slippage stresses worsen outcomes;
extra-delay/cost/annual outcomes are all retained in the report.

## Failures ready for visual inspection

- Weakest C later: TLT−24.49%, versus A−21.44%, B−16.65%. B improves two profit
  exits; C misses them and cuts August2–7,2024 for−1.18% versus A's eventual+1.53%.
- Weakest C earlier: IWM−32.05%, versus A/B−32.35%. Initial risk7.28%; the
  May12–13,2020 trade loses7.42%. Learning after loss cannot protect the original
  trade; an independent pre-entry loss budget needs separate research.
- Largest fixed-review deterioration: PPLT later+21.60%→−4.08%. April21,2025
  trade exitsMay28 for+12.09% instead ofJuly30 for+35.48%; later July18 ordinary
  entry loses11.44%. Exits alter the future entry path as well as one trade.
- IAT earlier adaptive−2.65%→−18.03%; October6,2020 winner cut at+15.16% instead
  of+34.12%. Faster adaptation can mistake an ordinary pullback for invalidation.
- GLD unchanged: later+52.22%, earlier−0.10% for all standing-stop arms. WEAT C
  later−19.00% versus A−15.98%; earlier+21.01% versus+18.17%.

## Next direction

Retain the existing research baseline; reject this reviewer as a replacement.
Define setup-conditioned path outcomes: post-exit reclaim versus further adverse
excursion; post-entry thesis failure versus acceptable loss budget. Compare simple
price-only and price/volume forecasts using chronological calibration and a single
net-benefit decision, rather than many overlapping hard filters. Require adaptive
shadow forecasts to beat frozen and constant-prior controls before letting model
weights alter actual trades. Do not loosen thresholds against inspected examples.
Any follow-up is a newly frozen study, with the same full-pool preservation checks.

## Verification and recipe

1,836 main cases;612 primary component/slippage diagnostics.612 exact parent
controls and612 exact disabled-review paths. Independent ordered-fill ledger
max error5.55e-15.41 focused Python tests. Interactive controls cover306 chart
combinations, exact dates, two-click zoom, interval NAV and weakest-era shortcuts.
Native Windows LEAN fixtures validate ordered accounting on a synthetic event
clock; they do not validate intraday stop executability or model inference.
Browser layout is not certified; scientific figures are inspected separately.

Recipe: `scripts/research_decision_review.py` prepare/fit/evaluate;
`scripts/analyze_decision_review.py`; `scripts/inspect_decision_review.py`;
`scripts/build_decision_review_report.py`; `scripts/validate_decision_review.py`;
`scripts/seal_decision_review.py`. Active inputs and frozen fits retained. Artifact
manifest and QA receipt record final checks. No frozen parent source changed.
