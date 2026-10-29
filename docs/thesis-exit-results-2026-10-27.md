# Thesis invalidation and shallow-decline exits — 27 October 2026

[Full report, formulas and all ETF charts](../research/thesis-exit-20261027-v1/index.html).

The operator approved the INDA incident's next step: test abandoning a failed
upward thesis and address shallow declines classified as neutral. Completed a
separate frozen study across all 52 supported ETFs, two chronological eras and
six cost/delay cases (1,836 asset/arm/friction cases). No portfolio or overlay.

## Definition and selection

Three algorithms only:

- A: exact preceding hard-reset C strategy.
- B: A plus persistent low up-state probability and a nonpositive fast slope.
  Per ETF, select floor 0.1/0.2/0.3 and persistence 2/3 closes. During slow-up
  probability >=0.7, halve the floor and add two confirming closes.
- C: B plus effective down = HMM down + HMM neutral × Gaussian probability that
  the fast slope is below minus 0.02 training daily volatility. Compare with the
  current policy's original down-exit threshold. Gaussian-slope families already
  have directional probabilities and are not corrected twice.

C is a heuristic exit-level combination, not a new HMM posterior or a refitted
market model. B and C independently select from the same six tuples; their
comparison includes selected settings and changed learning trajectories.

Selection uses the fixed base policy over the final 756 training return sessions,
with a flat funded start one close earlier. Models use all pre-evaluation training
history; this is in-sample fitting, not nested validation. Require at least three
closed trades, improved net Sharpe, CAGR within 1 percentage point and maximum
drawdown within 2 points of the training control. Choose highest Sharpe, then
CAGR, smaller floor and longer persistence. If none qualify, disable the entire
addition. No evaluation-driven overrides. B/C enabled on 27/28 of 51 later risky
ETFs and 10/14 of 49 earlier risky ETFs. BIL remains a separate visible reference.

Reinitialize the nine policy payoff seeds from training shadow trades using the
chosen exit. Actual and evaluation shadow trades share that exit. Keep the parent
four-effective-trade cap, discounting, hard resets, freshness/cooldowns and policy
adoption. Original winner-sigma calibration, market fits and stop widths remain.
Pending orders bind; stops do not loosen; close decisions execute next open plus
0/1 extra session. Fees 5/10/20 bp per side, zero-interest cash, adjusted fractional
units. Existing rearming/re-entry retained. No new support stop or hard risk cap.

## Primary results

Net cumulative returns, 5 bp each side, next-open execution:

| ETF / era | A current | B thesis exit | C plus shallow declines |
|---|---:|---:|---:|
| INDA 2023–2026 | -18.99% | -0.57% | -7.82% |
| GLD 2023–2026 | +90.66% | +85.87% | +85.87% |
| WEAT 2023–2026 | -13.88% | -13.88% | -11.98% |
| TLT 2023–2026 | -17.66% | -17.66% | -17.66% |
| GLD 2020–2022 | +14.70% | -12.74% | -0.38% |
| MCHI 2020–2022 | -38.69% | -41.37% | -41.37% |
| USO 2023–2026 | +4.64% | -17.63% | -17.63% |

The INDA December 3 entry now exits December 19 at -1.12% in both additions,
versus February 27 at -10.82%. B uses a 0.30 floor/three closes, C a 0.10 floor/
three closes but its shallow-decline signal acts first. This differs from the
previous illustrative 20%/two-close rule. Both new trades enter on the same date;
B's policy has changed to 0, C retains policy 5. These are complete adaptive paths,
not only substituting an exit on an otherwise fixed ledger.

INDA B reduces max drawdown from 35.25% to 15.44% and raises Sharpe from -0.430
to +0.027. Its full-period return remains slightly negative. C loses more than B
despite fixing the same incident.

Later pool median Sharpe A/B/C: 0.370/0.415/0.403; median CAGR 2.76%/3.74%/3.61%.
Preservation fractions B/C are 86.3%/84.3%, below the 90% criterion. B improves
16 ETFs and worsens 11; C improves 18 and worsens 10; remaining rows tie. Earlier
median Sharpe is 0.217 for all three; B worsens lower-quartile CAGR by 0.65 points.
B passes only one of twelve era/friction cases (earlier, 5 bp, delay 1); C passes
none. Neither is a robust general replacement. Median annual costs later rise
from 38.4 to 47.7 bp; earlier 43.4 to 46.8/46.9 bp. No absolute cost ceiling.
Later median ETF returns improve in 2023 but deteriorate in 2025 and 2026.

## Failure analysis and prepared charts

**GLD earlier:** A's January–March 2020 trade earns 3.76%. B exits February 5 for
1.65%, then adds trades losing 5.46% (February 24–March 2) and 12.01% (March 10–16).
A's March 27–August 12 trade earns 19.23%; B's changed policy exits April 1 at
-3.23%, re-entering June 26 for a later 10.65% winner. Exit, re-entry and Bayesian
policy feedback jointly cause the damage. C mitigates some losses but forfeits
most of the original earlier GLD gain. Dedicated GLD 2020 chart button included.

**USO later:** B reduces the February 2023 trade's loss from 11.76% to 4.00%,
then re-enters March 6 and loses 13.12%. It adds a May entry losing 8.13%.
Preventing one long hold does not prevent repeated bad entries.

**Weakest later C: TLT -17.66%, Sharpe -0.576, DD 21.59%.** Twenty closed trades,
seven wins. Every new exit tuple failed training selection: control training
Sharpe 0.428 versus best new tuple below 0.280. TLT is unchanged, not a failed
evaluation of an enabled new exit. Its late-2023 rebound remains captured. Old
training conditions can reject a change useful in a new regime; no hindsight
override made.

**Weakest earlier C: MCHI -41.37%, Sharpe -0.840, DD 59.14%.** Twenty-nine closed
trades, seven wins. Baseline already loses 38.69%; the Gaussian-slope family makes
B=C. Only one actual exit is labelled thesis failure, yet shadow learning changes
later policies. The January 12, 2022 entry loses 6.71% versus A's 2.65%; November
2022 rebound earns 3.64% versus 8.96%. Failed rebound entries and risk-policy
adaptation remain central, not just missing HMM down-state detection.

Default report opens weakest later TLT; changing era and clicking the weakest
button opens MCHI. Every ETF has dated price/volume, fast states, slow states,
effective exit evidence, fills/stops and three NAV paths. INDA incident and GLD
2020 buttons provide exact-date zooms; exported figures include USO as well.

## Decision and next hypothesis

Retain simple thesis invalidation as a promising component, not a universal rule.
Do not adopt either full package. Next isolate exit improvements from online
learning feedback and test renewed evidence for re-entry after a failed setup,
without permanently excluding continuing trends. Daily conditional predictive
evidence, independent risk boundaries and full market-model refitting remain
separate planned components. Do not retune the completed protocol on these losses.

## Verification and provenance

Protocol c472d56e579a4981db65d727d80170bc4680a693966ab9792a991cad3951a30d.
Chart hash fc733270b2d8af3cf3676e51b16b6c8d7eb111c253fb8641d35ca36680ccebdd.
Parent protocol 0b2857f166d62a570bbc4e38a34501df903e10e07a940d8006b357e8b093241d.
Published input batch 5688bb093a7481231f05b8ba4d84e3e26e016231ffeb42576b4e7aca12cf99bd.
Hashes verified through the parent chain. Raw volume is descriptive only; adjusted
prices are used for returns. Historical publication-vintage limitations remain.
Both eras were already inspected and constitute development evidence.

13 new tests and 31 parent tests pass. 612 exact controls have zero NAV discrepancy;
independent cash/share ledger error <=5.8e-15. 306 offline chart combinations plus
date hover/range and incident shortcuts checked. Native Windows single-ETF checks
INDA delay0, GLD delay1 and TLT delay0 match the application whole-unit reference
exactly. Native validates accounting of frozen signals, not independent learning.
Fractional/native returns: INDA -7.82%/-7.84%, GLD delay1 +96.49%/+95.66%, TLT
-17.66%/-17.62%; maximum normalized path difference 1.03 percentage points for GLD.
Static figures and mathematical displays reviewed; no browser-layout certification.
No broker, live, promotion, monitoring or runtime changes.
