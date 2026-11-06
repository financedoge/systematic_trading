# Research cost policy and rejection audit — October 17, 2026

**October 31 follow-up:** the fixed cash-relative net retest is
[complete](../research/cash-relative-net-20261031-v1/results.md). The table below
preserves what was withheld originally. Class-first/monthly improves its matching
control later but fails guarded FR25 comparisons; uncertainty includes zero.
The operator retained cash-relative as research evidence. The six separate
Alpha101 hypotheses are now [complete](../research/alpha101-net-20261031-v1/results.md):
222 net cases,52 supported histories, fixed/dynamic timing and six frictions.
Alpha54/monthly ranks highest in training but no robust matched-control advantage
across eras is established. This replaces withheld replay with empirical evidence;
it does not restore the old cost veto. The operator retained Alpha54/the study on
November1. P4.20 [evidence/decay governance](research-evidence-governance-v1.md) is
now complete and preserves the prohibition on cost/IC profitability vetoes.

**November 2–3 follow-up:** expanded FR25 now has a
[completed full-supported-pool net replay](../research/expanded-fr25-net-20261102-v1/index.html):
144 cases, fixed/dynamic timing and matched controls. Monthly is training-selected;
expanded later return is higher but original14 has better Sharpe/drawdown in both
eras. No guarded superiority established. The historical withheld verdict below
is preserved. The [class/volatility net replay](../research/class-vol-net-20261103-v1/index.html)
subsequently completed all 16 formerly withheld cases at six frictions on each
of two pinned batches. Pooled risk/monthly won training but failed the matched
return guard later. These results close the last pending replay in this queue.

The operator removed the 44 bp annual-cost ceiling. Incremental return must be
judged after incremental cost against matched controls. Current diagnostics do
not use an absolute cost ceiling or an IC-margin proxy to decide portfolio
profitability. Net Sharpe, Calmar, return/drawdown guards, realistic traded costs,
execution delay and chronological stability determine the research comparison.
Promotion, allocations, broker approval and live-disabled controls are separate.

The original cutoff was incumbent turnover 8.07x times assumed cost 5 bp, rounded
from 40.4 to 40 bp and multiplied by a 10% tolerance. It was never an optimum.
The October 11 operator objection was already recorded; treating it as a binding
limit again in the October 16/17 studies was an error.

## Audit of recent decisions

The [machine-readable audit](../research/research-cost-policy-20261017-v1/audit.json)
records source hashes and every gate row. This audits historical decisions; it
does not establish that any rejected candidate is profitable.

| Study / version | Cost-only failures | Were their portfolio replays withheld? | Current interpretation |
| --- | ---: | --- | --- |
| Cash-relative momentum, Oct 17 | 1 of 16 | Yes | Class-first monthly (45.66 bp, IC margin 3.59x) needs a net replay with its controls. The other 15 also failed the old information heuristic; their net performance remains untested. |
| Corrected standalone Alpha101, v4 | 6 of 16 | Yes | Alphas 24, 26, 46, 49, 53 and 54 were rejected solely for cost despite passing the old IC margin. Reopen as research hypotheses, not established strategies. |
| Class/volatility screen, Oct 16 | 0 of 16 | All 16 withheld | 14 failed cost and information, two information alone. Weak IC is a concern, but the screen never measured net portfolio performance. |
| Expanded FR25, Oct 14 | 0 | Expanded arm withheld | Cost 67.73 bp and negative IC −0.01463; not a cost-only rejection, and no net-return verdict is established. |
| Corrected matched-payoff Alpha101 tilt, v3 | 0 of 48 | Screening study | Seven failed both diagnostics, 28 payoff alone, three insufficient; ten passed. Do not confuse the standalone six with these tilt results. |
| Sleeve construction, v2 | 2 | No: boundary exceptions replayed | POOL and SLV-COMP were replayed at 45.91/46.41 bp. Their exposure/risk findings were not caused by withholding a replay. |
| Hierarchical construction, v2 | 1 | No: boundary exception replayed | HIER-K2 was replayed at 45.47 bp. Its concentration/drawdown and uncertainty concerns remain. |
| Alpha101 larger budgets / daily events / exit rules, v2 | 10 / 17 / 10 | No: all arms replayed | Their grids are superseded by the second review for other defects. Removing the ceiling does not rehabilitate those economic conclusions. |

The six standalone Alpha101 cases were:

| Alpha | Implied annual cost at 5 bp | IC margin |
| --- | ---: | ---: |
| 24 | 51.74 bp | 5.22x |
| 26 | 71.93 bp | 4.98x |
| 46 | 63.86 bp | 5.22x |
| 49 | 70.01 bp | 4.07x |
| 53 | 74.30 bp | 5.41x |
| 54 | 69.66 bp | 4.02x |

These were historical 14-ETF tests. A new Alpha101 study must use the full
supported pool, audited raw activity where required, matched horizons and dynamic
versus fixed timing. Related 46/49 signals are not independent discoveries.

P4.22/P4.23 timing/width tests, P4.18 exposure targeting and the accepted fixed
FR25 versus 5% tilt comparison already used portfolio returns after costs. Their
reported shortcomings were not cost-ceiling exclusions. The accepted fixed tilt
comparison trails FR25 in return and Sharpe across its six scenarios. Earlier
exit/budget optima must remain superseded as the second review specifies.

## Implementation and next comparison

`turnover_gate.screen` is now `turnover-diagnostics-v2`: complete diagnostics return
`requires_replay`, missing evidence returns `insufficient`, and neither is a
strategy promotion. The old `legacy_screen` is explicitly limited to historical
reproduction; frozen studies retain their original results and hashes. The
current plan and project memory supersede old affordability instructions.

The first retest keeps all four cash-relative/removal-only constructions and
monthly/0.10/0.40/0.80 policies fixed. Replay all 16 without either proxy veto,
compare with current SOTA FR25 and the monitored recipes on common dates and
costs, and report Sharpe and Calmar before proceeding to another planned item.
The six Alpha101 hypotheses remain a separate queued follow-up, not an automatic
addition to the monitored strategies. No favorable horizon or threshold is
selected after seeing the new results.
