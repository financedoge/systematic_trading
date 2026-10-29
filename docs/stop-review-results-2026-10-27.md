# Standing stops, exit reassessment and policy learning

Operator selects entry-value **B**, the symmetric directional HMM with fixed
policy, as the research baseline. This choice is not promotion. The new study
keeps B0 exactly, adds standing OHLC protection in B1, then adds near-exit recovery
and warning-driven policy learning in B2. No portfolio or monthly overlay.
Study opened October27; final checks completed October28, Asia/Shanghai.

[Interactive report and all ETF charts](../research/stop-review-20261027-v1/index.html).
The initial view is CPER2025-03-04..09-04; IWM2024-07-01..12-01 and each era's
weakest B2 have direct controls. Candles, exact date/OHLC/fill hover, two-click
zoom, interval account returns, trade and warning tables, and mathematical
definitions are included. Static incident and weakest figures are retained.

## Findings

Primary net results:5bp per side, next-open signal orders, plus5bp modeled stop
slippage. Interval returns mark the continuously traded account; not fresh
backtests starting at the user-selected dates.

| User interval | B0 original | B1 standing stop | B2 review/learning | Conditional touch-to-close |
|---|---:|---:|---:|---:|
| CPER2025-03-04..09-04 | -15.45% | +10.00% | +11.81% | +11.76% |
| IWM2024-07-01..12-01 | -14.04% | -9.64% | -11.60% | -9.29% |

December1 was not a trading session; the IWM interval ends November29's close.
Touch-to-close is a fixed-policy execution diagnostic, not B2. Daily OHLC cannot
establish whether a trigger occurred before the relevant venue/auction cutoff.
It is **not** a validated closing-auction implementation.

CPER's March7 trade:April3 open30.50 was already below stop30.5605. Modeled
gap-aware fill30.48475 gives+3.13%, versus April4 open28.17 / -4.70% under B0.
May27 trade:July28 low33.71 touched stop33.9456; close34.79 recovered. B1 models
exit33.9287 / +12.98%, instead of July31 open27.14 / -9.62%. This improvement
comes from an earlier touch, not perfect execution during the later crash.
April21 trade is a counterexample:April30 protection loses5.59% versus1.83%
on May5 under B0. Interval result remains+8.53% with50bp extra stop slippage
and+8.45% under min(open,stop,close), both model sensitivities, not fill guarantees.

IWM's July15 trade improves from-7.96% on August5 to-3.25% on August2 under B1.
Later trend/thesis exits and late entries remain. B2 selected the wider policy
before July's trade and lost8.00% at the August5 gap, giving back B1's benefit.
The later faster-policy September trade improves to roughly breakeven but does
not offset this. Warnings and parameter changes do not establish new edge.

Neither incident interval contains a recovery-rule buy. IWM after September9:
exit203.15, upper recovery band207.41. September12 close206.53 is still nearby,
but HMM up is near zero; September17 up74.2% arrives at214.14, outside the band.
After October31, November5 close219.59 is nearby but up1.7%; November6 up98.6%
arrives after price232.31. Waiting for the same HMM to endorse reversing its exit
recreates the original delay. Complete10-session condition traces are saved in
`incident-audit.json`.

| Era | B0 median Sharpe / CAGR | B1 | B2 | B2 within preservation guards |
|---|---:|---:|---:|---:|
| 2023–2026 | .392 / 3.13% | .402 / 2.90% | .350 / 2.15% | 60.8% |
| 2020–2022 | .322 / 2.40% | .312 / 2.07% | .326 / 2.18% | 63.3% |

Both challengers fail all12 era/friction acceptance cases. B1 improves18/worsens22
later risky ETFs (11 unchanged),16/32 earlier (1 unchanged). B2 improves19/worsens32
later and25/24 earlier. Warning-reset median Sharpe is lower than continuous
learning without reset in both eras (.350 vs .383; .326 vs .366). Completed
recovery trades are sparse:fixed recovery9 later/26 earlier; B2 9/35 with4/17
winners. Largest preservation failures include EWY later+100.64%→+57.39%,
SLV later+69.82%→+28.65%. Do not select ETFs retrospectively from these outcomes.

Weakest B2 **TLT later-23.36%**:6 winners/24 trades,15 warning days,10 policy
changes. **PPLT earlier-41.52%**:7 winners/27 trades,20 protective exits,19 warnings,
13 changes; B0 was-20.06%, B1-33.63%. Both charts ready. These are repeatedly
inspected development eras, not fresh out-of-sample evidence.

## Frozen methods and limitations

Use published audited adjusted OHLC and audited raw volume, pinned batch
5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd, through
2026-10-16. Every ETF's OHLC geometry and finite positive coverage checked.
Historical publication vintage remains unproven. No online/provider-archive prices.

Standing stop:low<=pre-existing level;fill=min(open,level)*(1-slip). Entry-day
brackets allowed. Current high never moves a stop tested against current low.
Completed-close trailing levels only; no loosening. Scheduled opening exits
precede intraday tests; protective exits cancel pending orders. Intraday
discontinuities, spread and liquidity are unknown:OHLC does not guarantee fills.

Review:1..10 sessions after exit, close within fee-adjusted exit and one frozen
ATR above it; up>=.55,down<=.35,positive/improving fast slope,bullish bar/location
>=.6 and three-session signed volume pressure>=0. Next-open execution, no same-day
rebuy. Open can gap past the band. Applied to all exit reasons, not just stops.

Three policies anchored to each ETF's B:original; thresholds-.05, stop distances
*.75, thesis count-1; thresholds+.05, distances*1.25,count+1. Explicit bounds and
all equations in report. Held policy remains fixed. HMM/Kalman parameters are
not refitted here. Fully observed net daily shadow-account returns update a
discounted Gaussian working mean with precision4 prior and63-session half-life.
Equal evidence counts mean the shared uncertainty penalty cancels in selection.
No calibrated independence/confidence claim. Warnings replace learned evidence
with last21 completed evaluation returns; no forced switch or permanent pause.
Training756-session replay uses full-training fits, caps initial weight20 and
calibrates large loss by positive-trade dispersion (fallback sigma*sqrt21).
This calibration is in-sample; no threshold selection on the incident windows.

52 later/50 earlier ETFs including BIL;3 main arms×6 cost/delay combinations:
1,836 main cases, plus1,632 attribution/execution diagnostics. Fees5/10/20bp,
signal delay0/1; already-standing stops are not delayed. Acceptance excludes BIL:
higher median Sharpe/lower-quartile CAGR and>=90% within1pp CAGR/2pp maxDD of B0.
No annual-cost ceiling. Retain all annual, dependence, IC, turnover and cost data.

## Validation and correction

All612 original B controls match saved outcomes exactly; the new event engine
with old close protection also matches all612 NAV paths exactly. Independent
multi-fill cash/share reconstruction maximum error6.44e-15. The first control
run exposed30 extra-delay cases in which an opening exit erased rearming learned
while waiting. Corrected before accepting evaluation; training fits unchanged
in all102 cases. Original protocol/source/checks and correctness amendment retained.
Final protocol8c639aee04780ed2651372910d57c131c1a780e2b89b6a1534e897a1ed8c86f9.

Native Windows LEAN independently checks frozen event accounting, using an
explicit synthetic event clock for each modeled fill and real closing mark.
Those fixtures validate ordering, whole-unit sizing, costs and NAV; they do not
independently establish OHLC fill executability or fit the HMM. Production
contracts, approval checks and native runtime acceptance remain unchanged.
Offline chart controls and static scientific figures are checked; browser
layout is not certified.
Focused suite48 passed; all306 main chart combinations and incident/date controls
passed offline. Native CPER/IWM/TLT/PPLT accounting discrepancies are$0.00 against
the independent application oracle. Whole-share/cent-price fixtures differ from
fractional research NAV, as explicitly reported in their receipts.

## Decision and next research

Keep operator-selected B0 as the research baseline. Neither B1 nor B2 is a
universal replacement. Retain standing protection as a promising component
and the precise incident evidence; reject this combined policy as implemented.

Next predeclare separate components:an independent disaster-loss budget that
recent-reward learning cannot widen; exit invalidation from price reclaim,
failure to make fresh lows and supportive volume without waiting for the same
HMM up threshold; a small recovery position/no-chasing rule; and an evidence
comparison between old/recent parameters with tempered forgetting versus hard
reset. HMM refitting should be a separate test. Require full-pool matched
outcomes and preservation of good cases. A closing-auction implementation
requires audited intraday timestamps and venue/order-cutoff modeling first.

No monitoring, paper allocation, broker, live, portfolio or promotion change.
