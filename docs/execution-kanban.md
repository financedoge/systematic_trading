# Execution Kanban

Current work and unresolved acceptance gates, consolidated 2026-10-12. Update at the
start and end of each implementation session. Completed rows and historical sessions
are preserved byte-for-byte in the [history archive](archive/README.md).
Use [research state](research-state.md) for accepted conclusions and the
[research plan](signal-decay-and-alpha-plan.md) for the ordered research programme.

## Outstanding rebalance recovery — 2026-10-24

**Implemented and verified offline; runtime activation pending.** October 21 has
three synthetic missed records, no automatic attempt or broker submission; its
ordinary drift proposal was excluded from renewal and used stale forward pricing.
Current alignment also lacks October 23 USD/CNH and HKD/CNH observations because
IB history requests time out. Separate durable intent state now survives expiry,
retains approved targets, rebuilds fresh residual attempts and records cancellation,
completion and supersession. Background expiry, queue progress, dated drift/blocker
visibility and account/claim guards are covered by 282 distinct focused checks
across targeted runs, including disposable native PostgreSQL and Node UI checks;
Ruff passes. Existing uncommitted work is preserved. The running app was not
restarted: that would also activate unrelated pre-existing research edits.
Next: coordinated application restart, fresh matched reconciliation and recovery
of the missing observed FX; verify the successor in the normal enabled paper
policy. No policy, allocation, approval or broker state was changed by this session.
[Incident, contract and rollout notes](rebalance-intent-recovery-2026-10-24.md).

## Allocation theoretical NAV resumed through the latest audited session — 2026-10-20

**Complete — calculation restarted and theoretical curve advanced to 2026-10-19.** The
operator reported the allocation theoretical NAV stopped at 2026-10-16 while the account
NAV continued to 2026-10-19. Cause: tracked-strategy calculation was deferred because
generated artifacts used 38.5 GiB of the 40 GiB admission limit (2 GiB new-work reserve);
the theoretical series is built from the published tracked FR25/M1 NAVs, so it could not
advance past the last published valuation. The last successful revision (2026-10-19
21:02 UTC) had also raced the 2026-10-19 USD/CNH observation captured at 21:01 UTC and
valued only through 2026-10-16. A guarded retention request queued after that publication
never ran because only dashboard-level restarts had happened.

Fix: full platform stop keeping NATS/Postgres (`stop_local_platform.ps1
-KeepInfrastructure`), app-owned guarded `maintain_research_storage.ps1` at the stopped
boundary, then `start_local_platform.ps1 -SkipNats`. Retention verified protection pins and
retired 2 superseded tracked calculation revisions plus 5 unreferenced model fits with
manifests/receipts in `var/maintenance`; unique generated footprint 38.48 → 37.40 GiB, so
admission passed. Recalculation (revision `de9c8cb1…`) completed, strategy-serving
republished (`ae428582…`) with valuation through 2026-10-19, and the dashboard-serving
publication rebuilt after one transient strategy-version race.

Verification: `/api/v1/dashboard/performance` theoretical series now ends 2026-10-19
(matching the account); the 2026-10-15 allocation period is valued through 2026-10-19
(3 observations, theoretical -0.12%, P&L -1,048.64 CNH); missing-FX warning gone; analytics
errors empty. No trading/allocation/funding/promotion/monitoring change: allocation
revision 7 unchanged, no new proposals or orders. Outstanding: pre-existing NAS
`operation.lock` local-only sync state; conditional candidate remains "Catching up" by
design (frozen panel through 2026-10-12); each new tracked revision adds ~2 GiB, so run
guarded retention at the next full stopped start and consider closed-study retirement for
more headroom.

## Performance panel N/A after a proposal expiry — 2026-10-20

**Complete — root cause fixed and deployed.** The operator reported every Performance
section value as N/A. Loading `/operator` expires due pending proposals through
`GET /api/v1/proposals`; on 2026-10-20 at 20:35:50 local `drift-97f2af32c2d7-20261019`
expired `pending` → `missed` with no fills, and `allocation_ledger_revision` counted every
missed proposal. That retired the saved dashboard performance publication, so
`/api/v1/dashboard/performance` returned 503 while the browser only retried on its
60-second cycle, leaving four `n/a` chips and an empty chart until the next publication.

Fix: missed proposals count towards `allocation_ledger_revision` only when execution
evidence (fills) exists; the performance endpoint requests an in-process rebuild and
returns `Retry-After: 2` when its publication is stale; the Performance panel shows a
visible refreshing status, retries a 503 within 1.5/3/5/8 s, and uses `refreshing…`
placeholders only before any publication has rendered.

Verification: new ledger-revision and endpoint tests plus updated operator JavaScript
checks; ruff clean; focused suites pass. Guarded dashboard restart deployed the change
(PID 50528); the live stale path requested the refresh and performance returned 200 after
warm-up; a due proposal expired during verification without invalidating the publication.
No trading, allocation, funding, promotion or monitoring state changed.

Outstanding, pre-existing: tracked-strategy calculation is deferred by the 40 GiB artifact
admission limit (~38.5 GiB used), so strategy-serving is stale ("Catching up") and the
monitored conditional candidate's report page still has a missing-current-allocation-field
rendering defect that can only be regenerated after retention/calculation resumes. The
expired `drift-97f2af32c2d7-20261020` cleanup proposal is now `missed`; no order was routed.

## Automatic renewal of missed paper rebalances — 2026-10-20

**Complete — missed handover recovered and automatic renewal deployed.** The FR25
allocation activated after the 2026-10-15 close produced a prepared
`handover-fe2d3613…` rebalance for the 2026-10-16 TWAP window. The proposal was never
approved or routed, expired as `missed` with only synthetic missed records, and the later
automatic-policy opt-in produced nothing because the controller only scans pending
proposals. Investigation also found the execution market-data refresh and drift/universe
helpers still used the 12-ETF SOTA universe instead of the active 14-ETF allocation
(XLB/XLE had no execution bars), the renewal rebuilt component models at a superseded
target date, and renewal rejected a legitimate whole-share top-up leg. Fix: an enabled
paper policy bound to the allocation renews one expired application-prepared rebalance
into the next complete TWAP window (frozen target weights and original slippage benchmark
preserved; quantities recalculated; policy revision recorded), after which the ordinary
preflight, approval and router checks apply; real/uncertain broker attempts and
session-limited catch-up authorizations are never renewed. Two follow-on defects found
while recovering a partially filled batch were fixed: allocation component targets bind
the requested monthly decision session instead of the later activation close, and a
partially filled rebalance that ends `missed` keeps its frozen targets as the adopted
target instead of falling back to the previous month-end.

Recovery (2026-10-19 UTC): renewal audit at 16:47:59, automatic approval at 16:50:24 under
policy revision 19, seven paper TWAP orders submitted at 16:50:27 (IB IDs 47–53), six legs
fully filled (DBC 185, EWH 813, EWJ 18, SPY 2, VGK 22, XLE 327), unfilled 1-share EWY
remainder cancelled by IB at the 13:20 New York window end, and a fresh matched
reconciliation with zero breaks. Automatic approval was paused at revision 20 only to
block a stale month-end-target drift proposal (rejected with no broker records) while the
adopted-target fix deployed, then restored at revision 21 with the same allocation,
account and CNH 1,000,000 cap; all holding drifts are now below 2pp (largest SPY +0.56pp).
A one-share EWY residual cleanup proposal `drift-97f2af32c2d7-20261019` (1,005.89 CNH)
remains pending operator review and is not auto-eligible. Full test suite: one run exited
zero; two other runs each had transient native-worker mutex-contention failures from the
live analytics worker, and every failed test passed on isolated rerun. Contract and
incident record:
[paper rebalance renewal](paper-rebalance-renewal-2026-10-20.md). No promotion,
monitoring membership, allocation change, funding, live authority or operator policy
cap/account changed beyond the documented temporary pause/restore.

## Cost-charged conditional FR25 overlay and monitoring candidate — 2026-10-19

**Complete — candidate kept for monitoring review only, delay weakness unresolved.** Rebuilt
the conditional 80/20 FR25 + Rule A short-only overlay as a single portfolio in the shared
application accounting engine, so every intra-FR25, intra-sleeve and inter-sleeve trade is
charged and execution delay is explicit. Fixed-monthly overlay (month-end only) is the
control; the dynamic candidate adopts at month-end anchors plus whenever the theoretical
blended target changes by at least 10% L1. Condition: sleeve enabled only in months whose
stable union-signal breadth is at or above the pre-2023 median (36/52; true in 68% of
months).

2023-2026, 5bp, next-open fills: frozen FR25 16.75% CAGR / 1.469 Sharpe / 2.063 Sortino /
−8.65% DD / 1.935 Calmar. Dynamic conditional candidate 16.08% / 1.479 / 2.10 / −7.64% /
2.10 (8.8× turnover, ~44bp cost). It beats FR25 on all four risk-adjusted measures at 5bp,
10bp and 20bp but gives up 0.66pp CAGR at 5bp. It beats the unconditional sleeve control
(15.71%/1.461) and all three random-condition controls on the risk measures, and beats the
fixed-monthly conditional control (16.19%/1.481/−8.39%/1.93) on DD and Calmar. **It fails the
+1-session delay test** (Sharpe 1.39 vs matched FR25 1.41; only DD still better), which is the
main open weakness.

Status: research candidate for monitoring review (`candidate.json`). The dynamic candidate is now
frozen as versioned package `fr25-lifecycle-conditional-v1` v1.0.0 with a full project-standard
strategy page (spec, decision flow, cost/delay stress, latest target 2026-09-30 marked to
2026-10-12, rebalance ledger, sleeve parameter table, risk limits and promotion checklist):
[research/fr25-lifecycle-conditional-v1/index.html](../research/fr25-lifecycle-conditional-v1/index.html).
No monitored strategy, allocation, funding, promotion, broker or live setting changed. Adding to
monitoring requires an app-tracked versioned strategy and calculation pipeline, paper-trading
evidence, resolution of the delay weakness, risk limits, operator approval and a rollback plan.
**Monitored update (2026-10-19):** candidate added to monitored membership and app tracked publication (detail/report HTTP 200), 947 observations through 2026-10-12, CAGR 16.09%, Sharpe 1.479, max DD -7.64%. Status Catching up because 23/52 pool ETFs lack audited app bars for 2026-10-13..16; allocation unavailable (dynamic clock vs monthly multi-asset allocation contract); monitoring only, no execution authority.

**App-tracked implementation update:** registered definition `fr25_lifecycle_conditional_v1`
in the strategy catalog; app-owned module `research/fr25_lifecycle_conditional.py` plus frozen
parameter JSON; application-side calculation through the shared `DailyBacktestEngine` (947
sessions, 55 rebalances, CAGR 16.09% versus 16.08% on the research page); tracked artifact
`var/research/fr25-lifecycle-conditional-v1/tracked/artifact.json` (SHA-256 `58557e78…`) and
promotion record `config/strategy-promotions/fr25-lifecycle-conditional-2026-10-19.json`.
Monitoring membership still NOT changed. Artifact-level validation now passes
(`tracked/validation.json`); runtime publication wiring is blocked because only PostgreSQL is
running (app/analytics/LEAN services off) and the candidate needs a dedicated tracked-runtime
family branch plus a verified refresh before the operator-approved
`config/strategy-monitoring.json` entry. No blind config or core-runtime edit was made.
[Candidate dossier](conditional-fr25-lifecycle-overlay-candidate-2026-10-19.md),
[candidate strategy page](../research/fr25-lifecycle-conditional-v1/index.html),
[cost/delay report](../research/gld-lifecycle-overlay-robustness-20261019-v1/index.html).

## Two-era stable life-cycle signals as an FR25/M1 eligibility filter — 2026-10-19

**Complete — deeper fits work, eligibility filter fails its matched control, conditional
overlay is the only survivor.** Per-ETF refit on pre-2023 only (300 random bounded vectors +
GLD vector + 60 anchor mutations per domain; screened by the worse of 2005-2015 and
2016-2022; top 20 replayed across 5/10/20bp and +1 delay; stability requires positive fitness
and ≥2 trades in both eras, ≥8 total and ≥10% exposure): **25/52 short-range and 9/52
long-range sleeves pass** (2 fallbacks each; long-range is the hard case). The stable
active/inactive state was then used only as a monthly eligibility filter on frozen FR25/M1,
with matched random filters removing the same number of names per rebalance.

FR25 2023-2026 at 5bp: frozen 16.75% CAGR / 1.469 Sharpe / −8.65% DD. Union-filtered
(renormalised) 15.79% / 1.302 / −8.82%, turnover 9.9x, 49bp cost; cash variant 12.94% /
1.275 / −7.78%. Matched random filters span 15.00–18.60% CAGR and 1.31–1.44 Sharpe, so the
life-cycle filter has **no demonstrated edge** over random removal and is worse than frozen
FR25; at 20bp it drops to 14.15%/1.179 and with +1 delay to 14.26%/1.192 (not delay-robust).
M1 conditioning is immaterial (2.67% vs 2.91% frozen). The eligibility-filter route is
retired.

The one survivor is the **pre-2023-calibrated conditional 20% Rule A short-only overlay**:
sleeve on only in months whose stable union-signal breadth (36/52, pre-2023 median) is at
or above threshold (true in 69% of months). Conditional overlay 16.01% CAGR / 1.478 Sharpe /
−7.67% DD / Calmar 2.09 versus frozen FR25 16.75% / 1.469 / −8.65% and the unconditional
overlay 15.54% / 1.454 / −7.67%. It improves Sharpe slightly and drawdown by ~1pp while
giving up 0.74pp CAGR: a marginal risk-shaping sleeve, not a SOTA replacement. An
FR25-breadth-weak version could not be calibrated (only one pre-2023 FR25 rebalance).

Next: charge explicit inter-sleeve rebalancing cost and +1 delay to the conditional overlay
and require multi-measure risk-adjusted improvement; do not pursue the eligibility filter
further. No promotion, monitoring, allocation, funding or broker action changed.
[Findings](gld-lifecycle-conditioning-findings-2026-10-19.md),
[report](../research/gld-lifecycle-conditioning-20261019-v1/index.html).

## Daily life-cycle opportunity scanner / CTA portfolios — 2026-10-19

**Complete — the rules work, but the opportunity stream is not selective enough:** the
operator asked for two daily, event-driven constructions built from the sealed two-horizon
signals. Rule A keeps holdings until their signal exits and re-splits the book equally
whenever a new entry fires (cap 6); Rule B gives each accepted entry one 1/6 slot and leaves
unused slots in a government/cash proxy (BIL base, SHY/IEF sensitivity). Both start flat at
2023-01-03, fill on daily 0→1 signal transitions and exit on 1→0 transitions, next-open
fills, 5/10/20bp and +1 delay stressed.

2023-01-03 to 2026-10-12: Rule A union 8.51% CAGR / 0.94 Sharpe / -11.04% DD; Rule B 7.20%
/ 0.85 / -10.09%; best variant (short-only equal-split) 10.57% / 1.04 / -10.27%; 8-slot
variation 9.06% / 0.89. References: FR25 SOTA 16.75% / 1.47 / -8.65%, equal-weight 14.74% /
1.38, URTH 20.45% / 1.40, BIL 4.46%. Correlations 0.73 with FR25 and 0.66 with URTH. The
daily books are positive and cost-robust but do not beat the benchmarks.

**Binding finding:** the cash/government leg is effectively unused. The fitted per-ETF
signals are active ~73% of OOS asset-days, so the 52-ETF universe almost always offers six
simultaneous signals: 0.0% of sessions had zero holdings, 83% had the full six, average
holdings 5.7 (29 accepted entries / 23 exits). The rules are concentrated rotating six-name
portfolios, and BIL/SHY/IEF cash proxies give identical results. This is a signal-selectivity
problem, not a portfolio-rule problem; the permissive per-ETF fits were selected for breadth
in the pool study (median short sleeve long 59% of IS sessions).

No OOS tuning; no promotion, monitoring, allocation, funding or broker action. Next
experiments in order: pre-2023-calibrated entry-strength threshold to create real cash
periods; replace-when-full ranking; stricter event-style per-ETF fits (5-50% exposure,
two-era stability); a smaller sector/asset-class universe. 17 focused tests still pass and
Ruff is clean.
[Findings](gld-lifecycle-daily-scanner-findings-2026-10-19.md),
[report](../research/gld-lifecycle-daily-scanner-20261019-v1/index.html).

## Two-horizon lifecycle on the 52-ETF pool and versus FR25 — 2026-10-19

**Complete — signals generalise, selection rule does not beat SOTA:** the sealed short-range
and long-range lifecycle algorithms were fitted independently per ETF on the pinned 52-asset
audited pool, pre-2023 only (200 random bounded vectors + the sealed GLD vector + 40 anchor
mutations screened at 5bp; top 15 per domain replayed at 5/10/20bp and +1 session delay;
evidence requires ≥5 closed IS episodes and ≥5% exposure; one vector sealed per ETF/domain;
no transfer fallbacks needed). Short-range evidence passed for 52/52 ETFs, long-range for
47/52. Signals and extension scores were mapped onto the portfolio panel, and predeclared
selection rules were replayed on 2023-01-03 to 2026-10-12 through the same shared accounting
engine that reproduces the frozen FR25 SOTA path (max relative NAV deviation 0.03%).

Results at 5bp, next-open fills, 45% cap, 98% budget: FR25 SOTA CAGR 16.75%, Sharpe 1.47,
DD -8.65%, Calmar 1.93; equal weight 14.74%/1.38; URTH 20.45%/1.40. Primary lifecycle rule
R1 (active sleeves with positive 126-session momentum, extension-ranked top six) monthly
7.35%/1.00/-8.62%, event 4.46%/0.63 (the 10% L1 event threshold over-trades: 299 rebalances,
29x turnover). R3 lifecycle allocation monthly 8.05%/1.20/-6.66%. Best lifecycle-only rule
R4 (active sleeves ranked by 126-session momentum) 14.53%/1.00/-11.62% event and
14.09%/0.93/-13.50% monthly. **No standalone lifecycle selection rule beats FR25 on both
net CAGR and Sharpe.** The predeclared 80/20 FR25+R1 monthly tilt is 14.86% CAGR,
Sharpe 1.475, DD -7.53% versus FR25 16.75%/1.47/-8.65% — a risk-shaping (lower drawdown)
control that gives up return, not a return improvement. Daily R1/FR25 return correlation 0.60.

Diagnostics: the shallow per-ETF fit finds signals but not necessarily each asset's best
rule; extension-score ranking selected defensive names (SHY 34/47 monthly slots, XLV, IBB,
XLP, EWU) and no commodities, so the sleeve missed the 2023-2026 gold/commodity trends that
the GLD deep dive captured; the lifecycle is more useful as a filter than as a ranker.

17 focused lifecycle/pool tests pass; Ruff clean. No promotion, monitoring, allocation,
funding or broker action. Next: use the lifecycle as a conditioning filter on FR25/M1 with a
deeper per-ETF fit and an explicit pre-2023 cross-period stability requirement, then retest
net Sharpe/return/drawdown, turnover and delay sensitivity against matched controls.
[Findings](gld-lifecycle-pool-findings-2026-10-19.md),
[report](../research/gld-lifecycle-pool-20261019-v1/index.html).

## GLD long-range lifecycle and short/long combination — 2026-10-19

**Complete — the two-horizon pair diversifies by time-in-market, not by asset:** the
operator asked for a second version of the GLD lifecycle that looks for longer range
periods and correspondingly longer rallies, with much larger stops. The shared checked
state machine was extended with a predeclared long-range structural domain (lookbacks
126/189/252/378/504/756 sessions; ATR 20/40/60/120; initial stops 4-20 ATR; failed-range
floors -1 to 8 ATR; trailing 3-20 ATR or 8-50%; time limits 0/126/252/504; cooldown
0-126) and fitted with the same differential-evolution objective, friction set,
evidence/guard rules, neighbourhood stability and sealing protocol as the short-range
study. Search: 326,160 pre-2023 evaluations at 5bp; 400 finalists across 5/10/20bp and
+1 session delay; sealed before any 2023+ read. The short domain is preserved exactly
(sealed IS metrics reproduce to 0.0).

The long-range rule trades 126-756-session range breaks with about 11 ATR initial risk
and a 3.8 ATR trail armed after a ~10 ATR advance. IS 2005-2022: CAGR 8.02%, Sharpe
1.05, DD -12.52%, 21.2% exposure. 2023-2026 development retest: CAGR 11.65%, Sharpe
1.29, DD -11.35%, 40.1% exposure, versus short-range 7.87%/0.86/-12.20% and buy-hold
23.75%/1.16/-26.40%. It entered the 2023-03-30 756-session range break and held 251
sessions into 2024-04-10 for +15.63%, then took +14.55% and +14.69% in the 2024 and
2025 legs. The 2005-2015 refit procedure validation again failed on 2016-2022
(0.69%/0.12/-22.30%), so the long domain is evidence-thin like the short one.

**Correlation and combination.** Daily-return correlation between the two sleeves is
0.338 out-of-sample (0.368 IS, 0.361 full); when both are long it is 0.998 because both
trade GLD. The low unconditional correlation comes from complementary time in market
(overlap OOS: 17.1% short-only / 23.3% long-only / 16.8% both / 42.9% neither). A
predeclared 50/50 independent half-account combination gives OOS CAGR 9.62%, Sharpe
1.28, max DD -6.64% versus parents 7.87%/0.86/-12.20% and 11.65%/1.29/-11.35%;
daily- and monthly-rebalanced controls are similar (OOS Sharpe 1.31/1.30). The result
is robust at 20bp per side (OOS Sharpe 1.23) and one extra session (1.23), and the
interior 25/75 and 75/25 capital splits also improve; 50/50 was predeclared, not chosen
from the OOS grid. It buys a roughly halved drawdown for some long-range CAGR; a
persistent single gold trend would reduce the time-in-market benefit.

11 focused lifecycle tests pass (shared causality, short-domain preservation and the
two structural domains). No promotion, monitoring, allocation, funding or broker
action. Next: apply both horizons to the supported ETF pool with cross-period stability
guards and shared fallbacks, then test the pair as an asset-selection rule and as a
trading/tilting sleeve against matched controls.
[Findings](gld-longrange-combination-findings-2026-10-19.md),
[report](../research/gld-lifecycle-combination-20261019-v1/index.html).

## GLD fitted lifecycle rework — 2026-10-19

**Complete — GLD mechanics fixed; pool extension is the next step:** the operator
rejected the prior GLD daily diagnostic on two fitted mechanics (8-close confirmation
and a 5-session progress exit) and on un-fitted thresholds (the arbitrary `log(1.25)`
range limit, tight `E-2ATR`/`0.5ATR` stops). This session replaced the lifecycle with
a 24-parameter state machine whose width cap, tail, lookback, drift cap, volatility
ratio, ATR period, breakout buffer, confirmation count, volume shortcut, initial stop,
failed-breakout floor, trailing basis/distance/activation, overheat thresholds, time
stop and cooldown are all fitted. Search: differential evolution, 213,120 pre-2023
evaluations, 400 finalists replayed across 5/10/20bp and one-session delay, sealed
before any 2023+ read.

The 2023 test is fixed: crossing 2023-03-13, confirmation same close, entry
2023-03-14 at $177.35, dynamic take-profit exit 2023-04-14 at $185.89 (+4.82% gross
over 23 sessions), versus the prior entry at $181.15 and five-session loss. The rule
then re-arms and holds the October 2023 breakout into March 2024 (+9.08%). IS
2005-2022: CAGR 9.21%, Sharpe 1.06, DD -13.28%, 29.8% exposure, versus buy-hold
7.60%/0.49/-45.56%. 2023-2026 development retest: CAGR 7.87%, Sharpe 0.86, DD
-12.20%, versus buy-hold 23.75%/1.16/-26.40%; the rule is stable across both
pre-2023 eras but its fast take-profit trails the exceptional persistent 2024-2026
bull leg. A fitted 2005-2015 refit failed 2016-2022 pseudo-OOS (1.00% CAGR, 0.16
Sharpe, -23.02% DD), so the procedure is data-hungry: per-ETF pool fitting must add
explicit cross-period stability and a shared-parameter fallback. Continuation
re-entry and wide trend trails were tested and rejected on pre-2023 evidence; they
are reported as ablations/sensitivity, not used for selection. The fitted range
detector is also short-horizon: 30 of 35 breakouts use a 21-63 session lookback and
no entry uses 252/504 sessions, because the fitted drift cap rejects longer windows.
That weakens the "stable for a while" premise and is the first candidate for the next
refinement, alongside the pool extension.

8 focused lifecycle tests (causality, prefix stability, stop/fill ordering,
determinism, accounting identities) pass. Report includes the full daily ledger with
range bands, triggers, effective stops, trailing levels, peak/drawdown, volume ratio,
entry/exit markers and the 2023/2024/2025 drill-downs. No promotion, monitoring,
allocation, funding or broker action. Next: apply the same algorithm to the supported
ETF pool with per-asset fits (or a shared fallback) and test it as an asset-selection
rule and as a trading/tilting sleeve against matched controls.
[Findings](gld-range-lifecycle-findings-2026-10-19.md),
[report](../research/gld-lifecycle-20261019-v1/index.html).

## Tracked-calculation/backup lock collision — 2026-10-18

**Complete — false "Strategy calculation error" removed and artifact locks
decoupled:** the hourly recovery backup shared
`var/run/research-retention.lock` with every tracked-strategy refresh, so while
a backup uploaded/verified, the calculation's non-blocking Windows lock acquire
failed and surfaced as a bare `[Errno 13] Permission denied`; a wedged NAS
upload kept that state for the whole long command timeout. The backup now holds
only `var/system-backup/capture.lock` (already probed by research-retention
maintenance), while calculations keep the artifact lock, and overlapping
contention is reported as a transient waiting warning with an explicit heading
instead of an error/alert. Restic commands now fail after
`stall_timeout_seconds` (900 s) without output, `unlock` is bounded to 120 s,
and System → Backups flags a transfer stage with no progress for 30 minutes.
224 focused tests (one optional skip) and Ruff pass; live restart/publication
and backup behavior are recorded in `log.md`. No allocation, order, approval,
funding or broker change.

## GLD daily behavior drill-down — 2026-10-18

**In progress — confirmation / patience experiment:** Operator requests repair
of the February–March 2024 late entry and early time exit. GLD daily only;
jointly enumerate confirmation count and progress deadline, keep range/ATR/
price stops/required progress/all other parameters fixed. Numeric fitting
pre2023, 2023 regularization/model selection, then a sealed 2024+ development
retest with entry-only and holding-only ablations. Preserve the v1 diagnostic
and provide the same daily range/entry/exit calculation detail for the revision.

**Diagnostic complete; numerical repairs remain open:** Operator restricts work
to GLD first and explicitly replaces calendar execution with daily trading for
this study. Future fitting and 2023 variant selection must compare daily rules
only. Daily completed-close decisions execute at the next session open; no
calendar rebalancing. Keep inherited v3 numerical parameters fixed for this
first diagnostic, without claiming they are a newly selected daily optimum.

Interactive dated ranges, rejected window criteria, crossings/confirmations,
actual fills, daily initial/range/trailing/time levels and retained fitting
records now cover 5,512 sessions. Seven 2024+ entries, six time-rule exits;
latest trailing activation $431.98 was never reached (peak $428.07), effective
stop $357.45. Daily baseline CAGR −1.84%, Sharpe −0.229, DD −11.99%.
23 focused tests and report source/control checks pass. Independent native
daily replay matches all 13 fills and 701 NAV observations with zero error.
Browser policy blocked local-file visual QA; no browser-rendering pass claimed.
No new fit, other-ETF study, promotion, monitoring or broker action.
Next: inspect the five-session progress test and change one GLD rule at a time.
[Daily drill-down](../research/gld-breakout-drilldown-20261018-v1/index.html).

## Joint lifecycle optimization v3 — 2026-10-18

**Complete — joint search does not validate a general breakout strategy:**
33 mixed parameters, 1,100,502 unique pre-2023 evaluations across 50 qualified
ETFs; two short histories use shared parameters. Scaled net-return/Sharpe/Calmar
45/40/15 objective, soft near-buy-hold and wide-stop penalties, two seeds,
chronological/local stability, shared/shrunk variants. Calendar 2023 selects
frozen variants/clocks; all 52 choices sealed before 2024+ replay.

Selected OOS CAGR GLD −0.19%, USO −4.11%, SOXX 42.72%, versus buy-hold
27.75%/36.67%/40.83%. Gold's fitted five-session time exit misses the rally;
all three cases failed 2023 return/drawdown guards. Only 5/52 beat buy-hold
CAGR; no positive family-adjusted bound versus buy-hold. Equal-budget sleeves
7.24% event /8.39% monthly trail matched momentum 10.11%/11.94%.
7,320 individual OOS scenarios, 204 pool scenarios, 63 focused tests and five
exact Windows-native checks pass. Report includes all variants, parameters,
seed/local diagnostics, costs/delays, attribution and failed selections.
No strategy promotion, tracking, funding or execution change.
[Report](../research/range-breakout-20261018-v3/index.html),
[recipe and interpretation](range-breakout-calibration-v2.md#joint-lifecycle-v3-follow-up).

## Range-breakout individual-asset calibration v2 — 2026-10-18

**Complete — no general validation or promotion:** 52 supported /54 reviewed ETFs,
full individual histories, 1,080 range/exit/volume choices per ETF fitted strictly
before 2023. 47 individual fits,46 passing IS guards; five shared-rule fallbacks.
2023–October16 OOS CAGR: GLD20.10%,USO−3.21%,SOXX32.11%, versus v1
3.27%/3.38%/−0.46% and buy-hold23.48%/24.71%/46.95%. Wider holding captures
gold/semiconductor rallies but raises drawdowns; oil fails OOS. Only2/52 beat
buy-hold CAGR and15/52 beat the shared rule. One positive family bound is BIL,
not a risky breakout. BIL/cash dominates standalone portfolio construction.
56,160 fractional screens,1,536 exact IS replays,1,872 individual OOS and156 pool
replays;47 tests, scoped lint and five exact native LEAN checks pass. Compact
study footprint94.65MiB. [Definition/results](range-breakout-calibration-v2.md),
[report](../research/range-breakout-20261018-v2/index.html).

## Range-breakout lifecycle factor research — 2026-10-18

**Complete — research prototype, no promotion:** Implemented adaptive 42–756-session
compression, frozen-range three-close confirmation, optional raw-volume support,
holding, heat-sensitive trailing exits, false-break stops and reset states.
Fixed 252/504-session controls remain. Reviewed 53 existing-pool candidates and
tested 50; after explicit operator steering, added a separately pinned audited USO
history for 51 supported / 54 reviewed without changing the original 50 inputs or
FR25 control. Tested selection, standalone trading and a 20% FR25 sleeve under
monthly/event timing and six cost/delay cases: 972 fixed and 36 continuous
walk-forward replays across the two pools. Four native LEAN checks match exactly;
37 focused tests and scoped lint pass. About 164 MiB of artifacts, with one source
snapshot per pool and compact scenario paths.

Primary extended-pool trading: 2024+ CAGR 9.23%, Sharpe 1.413, drawdown −4.63%,
46.45% exposure; full-period CAGR 4.76%, Sharpe 0.764. The 20% tilt earns 17.00%
versus matched FR25's 19.37%; its construction-matched blend earns 15.99% with
higher Sharpe. Zero family-adjusted positive contrasts; one-session delay and
20 bp costs materially erode trading performance. Includes GLD/USO/SOXX/XLE case
charts and losers/missed trends. No monitoring/allocation/broker policy changed.
[Definition, findings and next work](range-breakout-factor.md);
[full report](../research/range-breakout-20261018-v1/index.html).

## Disk retention and Windows native migration implementation — 2026-10-18

**Complete — native cutover, research retirement, host compaction and broker follow-up.**
Final follow-up acceptance passed at 16:40 local time on October 18. Administrator
compaction reclaimed 246.15 GiB in its measured receipt; the Docker VHDX is now
2.72 GiB. Gateway is healthy and fresh reconciliation matched all six positions,
with no warnings or unmatched orders/fills. The operator already enabled paper
policy revision 19; its prior account, binding, strategy and 1,000,000 CNH cap are
unchanged. No additional policy revision was written. Live routing stays disabled.
Retired 815 selected roots: 95 superseded calculations, 128 completed-study leaves,
264 unreferenced model revisions and 328 governance projections. Verified exclusive
file contents removed total 97.73 GiB. Findings, recipes and retirement receipts
remain; protected active studies, canonical audited histories and broker evidence
passed checks. The final inventory measured about 133 GiB logical contents in `var/`,
down from 477.32 GiB; hard links make this distinct from physical reclaimed space.

Native PostgreSQL/Parquet migration verified 50,206 publications, 10,065 governed
pairs and 34,772 unique fragment hashes. Native NATS restore/reliability checks,
independent native LEAN parity, restricted-worker tests, isolated database/queue
restore and Docker-free cold startup passed. The final app revision is
`b528d1061f7757f1bcc434529662beb20251fcd69748878e7870d91b43eeddc4`:
12 native runs and artifact hashes passed; all seven monitored strategy reports
are served through October 16. Allocation control is unchanged. Worker runs are
serialized, limited to two CPUs and 4 GiB, with no network capability.

The exact first native NAS snapshot is
`8e0658e40f3d0b0451ee9770eb8d4d8c9364c26bfbb3ce43048f1277c10e0de5`.
A fresh post-calculation incremental backup completed and passed exact identity,
manifest and dependency readback, including the newly published calculation:
`2d08c381db7938ac4c0c7a1dc2efdd34e67428239a832f8f11507ef96aebc289`.
It reused 1,287,668 files and added 124,934,927 packed bytes; normal hourly supervision
has resumed. Snapshot selection now
resolves the tagged original candidate and explicitly selects its incremental parent.
The final 1,903-case broad run had one Docker-dependent test fixture failure; its
repair and backup regressions pass (21 cases). Four real isolation tests, 17 final
report/resource tests and 15 final backup tests pass; documentation links and lint
pass. Earlier retired-replay skips and repaired failures are recorded in the log.

Removed the exact project ClickHouse container, both legacy Docker data volumes
and all three images, with ownership checks and a retirement receipt. Docker and
its only WSL distribution are stopped, Docker auto-start is absent and the VHDX
is detached. Operator-run compaction and a subsequent exclusive-access check passed;
the receipt records 267,222,253,568 bytes before and 2,918,187,008 after. D: had
790.33 GiB free at the final host check. Automatic approval review blocked
removal of both disposable restore-test roots; they remain with compact evidence:
`var/system-backup/postgres-restore-drill/data` and
`D:/systematic_trading_data/native-restore-drill-20261018`.
`operator-followup-acceptance.json` verifies unchanged allocation control, paper
policy, reconciliation, seven served reports and healthy core native services.
The first resumed hourly backup also completed (snapshot
`40cbff997b972b940ec7b3f8dd440ca379cca2e06c14ca27621c6fcfd730d656`).
Existing daily coverage/acquisition and execution-benchmark gaps remain visible;
neither migration nor reconciliation waives their data-quality checks.

## Disk retention and Windows native migration plan — 2026-10-17

**Done — plan and durable policy; implementation queued:** The operator prioritizes
memory/storage over recomputation and explicitly permits retiring bulky archived
research artifacts without exact replay copies. Selected replacement: native Windows
PostgreSQL metadata/operations, compressed Parquet/native DuckDB, native NATS and a
Docker-free calculation/independent-validation path. The live catalog has 22 archived
entries (21 IDs) and seven monitored strategies; FR25 is SOTA and 100% paper allocation
at control revision 7. Latest two complete calculation directories total about
0.89 GiB versus 58.20 GiB for 239 revisions. Savings remain subject to active and
paper-evidence pins and hard-link accounting. Compact summaries and retirement
records replace an unconditional keep-every-experiment rule; no full backup of
deliberately disposable output is required. [Implementation plan](storage-retention-and-windows-native-plan.md)
covers seven ordered stages, exact code boundaries, native engine isolation/parity,
atomic publication, cutover/delta rollback, backup/restore and cleanup acceptance.
Next: stage 1 retention records/summary serving and guarded deletion manifest, then
diagnostic cleanup. No data deletion, service migration or runtime change in this
planning session; the earlier automatic-review deletion rejection remains recorded.

## Storage and service resource review — 2026-10-17

**Done — assessment; cleanup/resource policy remains follow-up:** `var/` contains
4.83M files / 477.32 GiB logical lengths. The apparent 353.17 GiB governance tree
has only 18.43 GiB of unique file contents because of existing hard links; blanket
deletion would overstate savings and break pinned research evidence. Current study
batch hashes/publications verified. Tracked bundles (58.20 GiB), study artifacts
(53.53 GiB) and models (6.77 GiB) require dependency-aware retention/deduplication.
Outside `var/`, ClickHouse holds 82.53 GiB of diagnostic logs. NATS process memory
is about 43 MiB despite a much larger Docker-accounted figure; ClickHouse's cgroup
is dominated by file cache. Neither service has a container cap; the scheduler
allows three 4 GiB LEAN workers with only 2 GiB reserved for services. Native NATS
is possible, while ClickHouse still needs WSL on Windows and LEAN still uses Docker.
Removal of a verified stopped 3.586 GiB restore-test cluster was rejected by
automatic approval review (“blocked by policy”). **No files were deleted and no
runtime settings changed.** Next: diagnostic retention, measured service/worker
budgets (P6.15), verified backup completion and dependency-aware artifact retention.
See [the storage review](repository-maintenance.md#storage-and-memory-review--october-17-2026).

## Codex desktop crash investigation and workspace-view fix — 2026-10-17

**Done — containment applied; app-side crash handed to OpenAI:** Operator reported
repeated ChatGPT/Codex desktop crashes while working in this repository. Ten Crashpad
reports are retained (nine on 2026-10-17), with the latest Electron main-process crash an
access violation `0xC0000005` in `chrome.dll`, `ERR_WORKER_OUT_OF_MEMORY` worker events,
and 4.8M-file/476 GB `var/` data trees feeding the app's file search and turn-diff
snapshots. `.gitignore` now excludes the four bulk local data trees (`var/governance/`,
`var/research/`, `var/tracked_strategies/`, `var/tracked_models/`): the repository view
fell from 4,610,923 to 2,808 files for file search and from 4,610,057 to 1,948 untracked
files for git snapshots, with enumeration from 4.0 s/19.0 s to 0.1 s. Tracked `var/`
evidence is unchanged (160 files). The crash itself is in the OpenAI client (dumps were
uploaded via Crashpad); environment follow-ups (memory/pagefile headroom, sandbox reset,
network reconnects, app version) are recorded in [log.md](../log.md). No app calculation
source, monitoring, capital, broker or live setting changed.

## Remove the annual research cost ceiling — 2026-10-17

**Done — policy and audit; retest In Progress:** The operator removed the 44 bp annual-cost rejection rule.
Evaluate incremental returns after incremental trading costs, with net Sharpe,
return/drawdown guards, cost/delay sensitivity and chronological validation.
The executable diagnostic and historical-reproduction entry points are separated;
162 focused tests and Ruff pass. Seven cost-only withheld cases are identified
([audit](research-cost-policy-review-2026-10-17.md)). Guarded restart and fresh matched
reconciliation passed; the prior paper policy/cap was restored. Existing raw-input
coverage issues remain independent of this change. Next: replay the fixed 16-arm
cash-relative family against SOTA and monitored strategies and report Sharpe/Calmar
before another item. Frozen evidence and promotion controls remain separate.

## Historical cash-relative screen — superseded interpretation, 2026-10-17

**Done — 16/16 rejected; class-first candidate misses the cost ceiling:** the
registered cash-relative score is compared with merely removing BIL, under pooled
and class-first construction and monthly/0.10/0.40/0.80 adoption. Class-first monthly
clears the heuristic information margin (3.59x versus 3x), but costs 45.66 bp
against the unchanged 44 bp ceiling. All dynamic mappings cost at least 108.46 bp.
Later static payoff improvements are before costs, exposure-sensitive and already
inspected; no replay admission or promotion follows. Comparable-class evidence is
sparse. [Full findings](cash-relative-momentum-findings.md).
All 52 candidates/50 published histories are accounted for; BIL is a measured
reference with zero target. 72 tests, Ruff and independent checks of 5,800 targets,
16 policies, 5,698 adoptions and 554 paired payoffs pass; 2,900 parent targets
reproduce exactly. Inputs, code and results are hash-verified. The reserved
October 19-April 20 prospective design remains inactive after rejection.
Next: review the cost constraint and whether a separately frozen turnover mechanism
is justified with the signal fixed; no threshold/holding-period tuning or ceiling
relaxation. No app source, monitoring, capital, broker or live setting changed.

## Historical class and volatility screen — 2026-10-16

**Done — 16/16 mappings rejected; ready for review:** the frozen 50-fund
construction screen compares pooled/class-first selection, raw/volatility-normalized
126-session momentum and monthly/0.10/0.40/0.80 target adoption. Fourteen mappings
exceed the 44 bp cost ceiling. The two normalized monthly mappings cost 24.84/38.15
bp but have information margins of only 1.91x/0.55x versus the required 3x.
Their later-period mapping ICs turn negative; the pooled version averages 45% BIL
plus 41.64% cash. No mapping qualifies for portfolio replay.
[Findings, chart and full attribution](class-volatility-screen-findings.md).
57 focused tests and Ruff pass; independent checks reproduce 5,800 daily targets,
16 policies, 4,485 adoptions, 128 turnover windows and 2,144 IC observations.
The protocol, published inputs and source/result hashes are frozen. Stop this
item for review before another hypothesis; no retuning or FR25 rescue. Historical
membership/mandate limitations and P6.15 remain open. App calculation source,
monitoring, allocation and trading settings were not changed.

## Market-data freshness incident — 2026-10-15

**Repair deployed; broad catch-up running:** AAPL is audited/published through
October 14. The intraday selector now returns its five recorded symbols in 0.11s
(previously a 4.07 GB manifest scan exceeded a 45s timeout), and charts load.
The application owns automatic daily refresh for supported current-listing
candidates, with per-symbol quarantine/retry and retained historical conflicts.
Independent freshness checks now make missing/stale daily data and intraday gaps
degrade System health and create durable alerts, including when child processes
exit successfully with warnings. Market Data displays these warnings directly.
132 regression tests, Ruff and live API/browser checks passed. The original paper
approval policy/cap was restored after matched reconciliation; live remains disabled.
**Open:** catch up the broad daily backlog, investigate quarantines and unsupported
identities, and configure an external alert channel if required (SMTP is currently
unconfigured). Do not call broad coverage recovered until actual endpoints pass.
[Incident and recovery details](market-data-freshness-2026-10-15.md).

## Rebalance mechanism review — 2026-10-15

**Standing rule and publication checks complete:** Future research must evaluate
dynamic rebalancing alongside fixed-interval controls; this is recorded in
`AGENTS.md`, the continuous-research playbook and research-state rules. The operator
authorized commit/push of P4.22/P4.23 source, tests, findings and compact acceptance
receipts. Research source matches the accepted frozen versions; Ruff, document
links and receipt hashes pass. Concurrent market-data work is a separate change.

**P4.22 and P4.23 completed; top-six monthly retained:** The 132-scenario
fixed-top-six study retained monthly in all three annual selection windows and
the final trailing-three-year window. Both parents reproduce 70 monthly decisions;
six native LEAN/Python checks pass, including the 0.10 intramonth policies.
[Results](../research/target-change-rebalance-20261015-v1/results.md).
The joint (X, n) study completed 588 full-size scenarios: X is maximum selected
ETF count and n is the target-change threshold. All three annual selections and
the final trailing-three-year selection retain 6/monthly. Wider selection lowers
traded notional but reduces net return and Sharpe in this current FR25 pool.
Top four/monthly passes performance guards in two early windows, but fails the
registered neighbor-stability requirement; no pair passes in the later windows.
The 6-by-8 grid, Sharpe/return/drawdown guards and cost/delay scenarios were frozen
before joint results. [Joint findings](../research/selection-width-timing-20261015-v1/results.md). Trading settings
and live-disabled posture stay unchanged. The operator distinguishes strategy
change (`latest theoretical - last adopted target`) from trading alignment
(`latest adopted target - actual held`). Only strategy change is optimized;
housekeeping remains in Trading. This supersedes the initial review's proposal
to use held weights in the strategy trigger and include paper drift in the grid.

[Registered protocol](target-change-rebalance-plan.md): current FR25/14 primary,
F3/12 transfer check, full-pool validation later by explicit operator choice.
Monthly plus eight target-distance thresholds competes with monthly and daily
controls. Net Sharpe selection has fixed return/drawdown guardrails, chronological
three-year selection windows, neighbor stability, six cost/delay scenarios and
an explicit monthly fallback. Pin published inputs and verify all used hashes
before running; retain existing model cadence and full account-level accounting.
Existing historical periods are inspected evidence, not untouched holdouts.
The operator explicitly authorized last-monthly macro fallback when an exact
daily snapshot is absent; retain source timestamps and carry-age diagnostics.
F3 preserves its current legacy adjusted-price/source-volume activity proxy and
is a sensitivity comparison, not raw-activity transfer confirmation.
The [joint X/n protocol](../research/selection-width-timing-20261015-v1/protocol.json)
now has membership-turnover attribution, independent checks of 98 adoption
policies and six native LEAN/Python parity checks. All 1,453 top-six daily targets
per parent and 60 common parent economic replays match exactly. Expanded-pool
validation remains later, conditional on a separately qualified parent.
The downloaded Gârleanu-Pedersen journal paper
has verified identity, 32 pages and a provenance/hash record in references.

The initial review verified daily indicative targets, monthly backtests and the
existing paper individual-ETF 0.02 alignment policy. Its 109 passed / one skipped
focused checks remain dated review evidence. P4.22 implementation checks passed
114 tests with one optional skip before the joint-study extension. The joint
extension passed 119 tests with one optional skip; Ruff, report rendering and
artifact/input hashes pass.
[Snapshot](../var/reviews/rebalance-20261015.json) and [log](../log.md).
No strategy, funding, threshold or routing setting changed.

## Repository restructuring and maintenance — 2026-10-12

**Done — source and local maintenance:** Separated presentation assets, API
contracts and pure preview construction; repaired invalid preview inputs, cap
rounding and the relocated Alpha101 reference. Static page rendering and streaming
hash verification have measured improvements. Consolidated current docs and
preserved complete originals; compressed seven verified logs from 92.8 MB to 6.3 MB.
**Validation:** 1,691 passed / 55 optional skips; Ruff, local links, whitespace,
isolated wheel rendering, frozen bundle resources and archive hashes pass.
[Scope, measurements and recovery](repository-maintenance.md); receipts in
`var/maintenance/`. Existing uncommitted execution work and all trading/data gates
are preserved. **Deployed October 13:** guarded restart, matched reconciliation,
existing paper policy restored and application catch-up verified. Historical
partially filled orders remain in the ledger. Later source changes require their
own guarded restart; the source-identity check remains enforced.

## Execution readiness and ETF expansion — 2026-10-13

**Delivered — execution and first-wave study; research rejection ready for review:** scalable paper execution
contracts and FR25 readiness (P8.1-P8.5), then the accepted P4.16d first admission
wave, then reproducible full-admitted-pool backtests. Stage 1 inventory/rules were
reviewed and the operator instructed continuation. Preserve existing allocation
approval, reconciliation and live-disabled controls. Deliver a concrete conditional
5% FR25 / 95% F3 preview after readiness; tradability itself does not fund a strategy.
Baseline blockers: unbound FR25 financial/raw-activity inputs, first-component-only
instrument resolution and no execution contract registry. Record fresh operational
and parity evidence before calling FR25 paper-ready.

Source implementation and focused parity checks now pass; the immutable 14-ETF
execution registry contains fresh issuer/IB identities and successful account-bound
paper previews. All 38 proposed additions also have verified broker identities.
Deployment, app catch-up and the conditional allocation preview passed on October
13; allocation remains F3 100%. Recorder publication now covers 39 of 41 entries.
The October 14 retrospective study pins the completed catalog, reviews all 52
candidates and supports 50 common-window histories (BWX held, CPER zero-volume limitation).
Expanded FR25 failed the registered pre-test (67.73 bp implied cost versus 44 bp; IC −0.01463), so its portfolio replay was withheld. Original-pool 5/10 bp controls and URTH passed native parity. [Full findings](etf-expansion-findings-2026-10-14.md). Final acceptance: 1,713 full-suite tests passed / 55 optional skips, five additional preview/frozen-runner checks and 14 dispatcher regression checks (one new). App catch-up and refreshed FR25 preview passed, reconciliation matched, and the same F3 policy was restored. Final platform health is OK. Funding remains F3 100%; there is no pending allocation.
See [session evidence and acceptance](execution-readiness-2026-10-13.md).

## Current priorities

**2026-10-17 research session — Review:** P4.16d stage 1 accepted: 299
symbol/regime records (298 provisional fund references), proposed taxonomy and
complete gap matrix, 38-addition first wave alongside the original 14, frozen
proposed screening rules and file-density/capacity estimates. All 16 input
snapshots and the pinned catalog hashes verify; 11 inventory tests pass.
[Inventory report](etf-universe-inventory-2026-10-13.md). Research ingestion is
enabled; expanded FR25, class/volatility and the cash-relative follow-up all failed
their pre-tests. The cash-relative class-first rule clears the heuristic IC margin
but misses cost admission. [Latest findings](cash-relative-momentum-findings.md).
No allocation change. The HYXU closure claim is corrected
from primary sources; its legacy history and new EUHY regime remain quarantined.

- P4.19 retrospective execution references complete; retain current execution policy.
  [Findings](execution-reference-findings.md). Missing fills/contracts and raw-unit
  limitations remain; this does not qualify continuous intraday research inputs.
- P4.16d: substantial ETF candidate inventory, dated taxonomy and comparable groups,
  followed by audited admission, app readiness and full-pool research.
- P6.15: measure worker memory and scheduling before expanding concurrency.
- P8.1–P8.5: minimum 14-ETF paper execution acceptance passed; broader registry
  migration and market support remain separate work.
- Last recorded paper allocation: F3 100%, revision 5, no pending change (2026-10-12
  acceptance receipt). This is historical context; consult app state before acting.

## Operating Rule

Before starting work:

1. Read `docs/industrial-platform-plan.md`, `docs/execution-kanban.md`, and `log.md`.
2. Pick the highest-priority `Pending` or `Review` item that is not blocked.
3. Move it to `In Progress`.
4. Record assumptions or blockers in the item notes.

After finishing work:

1. Move completed items to `Done` only after tests or equivalent verification pass.
2. Add evidence paths, commands, or reports.
3. Update dependent items if their status changed.
4. Add a concise entry to `log.md`.

## P0: Project Memory And Governance

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P0.7 | Pending | Decision log discipline | Every architecture or production-control decision gets a dated `log.md` entry. | Ongoing habit, not a one-time task. |

## P3: Market Data Recording And Data Quality

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P3.4a | In Progress | Pilot raw-data proving and audit loop | Record a small ETF pilot, audit raw/catalog coverage, inspect gaps/duplicates/freshness/disk use, and only then scale. | Pilot capture and historical recovery are implemented. Delayed quote samples remain inspection-only; paid real-time entitlement and admitted continuous intraday coverage remain unresolved. See [intraday recovery](intraday-recovery.md). Historical receipts remain in the archive. |
| P3.4 | In Progress | Normalized bar/quote pipeline | Convert raw records and external daily loaders into columnar golden daily/intraday tables with quality flags. | Daily serving and governed research publications exist. Remaining: normalized intraday serving, explicit source precedence/disagreement and comprehensive gap/freshness panels. Old row counts and repair receipts are historical; see [data governance](price-governance-2026-09-26.md). |
| P3.4c | In Progress | Migrate strategy, rebalance, PnL, and backtest market-data reads to ClickHouse | Signal generation, portfolio rebalance proposal generation, dashboard valuation/PnL, and stored backtests read daily bars from ClickHouse `market_data.daily_bars` instead of SQLite `price_bars`; SQLite price endpoints are either deprecated or explicitly marked legacy. | PostgreSQL/ClickHouse are the active store defaults; SQLite is explicit offline test/recovery only. App strategy decisions consume pinned governed publications. Remaining: intraday serving and full migration/soak acceptance. See [analytics migration](analytics-migration.md). |
| P3.5 | Pending | Data freshness checks | Detect stale bars, missing FX, source gaps, duplicates, and clock drift. | Alerts must be generated. |
| P3.6 | Pending | Replay a trading day | Reconstruct a paper-trading day from recorded data and compare to stored decisions. | Phase 2 exit criterion. |
| P3.7 | Blocked | Paid/primary market-data vendor | Source-of-record vendor choice and credentials are not settled. | Use IB/Yahoo/Tushare only as current interim sources. |
| P3.8 | Pending | Promote `review` series to `audited_with_limitations` | Investigate the `review` population, fix the fixable gaps, and stop conflating "fixable data gap" with "never certified". Acceptance: every reviewed series is either promoted with evidence or reclassified under an explicit permanent limitation; the decision gate in `portfolio/decision_inputs.py` then reflects a meaningful distinction. | **Deferred by the user 2026-10-10:** leave the gate as it is for now and spend effort later on promotion. Triage of batch `b02d9372…` (5,341 series; 1,056 `audited_with_limitations`, 3,482 `review`, 803 `unavailable`): all 3,482 `review` series carry the same four certification gaps (`identity_not_certified`, `raw_tape_not_certified`, `listing_boundary_not_certified`, `listing_history_not_certified`), and 3,471 also carry at least one data gap. By research role the population is `underlying-sector-hhi-20260926-v1` (3,460) and `ivv-constituents-2012-2026-v1` (680, partly overlapping), i.e. research-only constituent stocks. **Only 4 `review` series are ETFs, and none is in the trading universe: IVV (1,014 cross-source conflicts), XLF (890), XLRE (2 volume conflicts), HYXU (stale 2020 tail, 1,304 conflicts; **2026-10-13 correction:** name/symbol and mandate changed to EUHY in 2025, not a proven 2020 closure; [evidence](etf-universe-inventory-2026-10-13.md#corrected-hyxu-identity)).** Suggested tiers: (1) the four ETFs, including separately auditing HYXU/EUHY dated identity and mandate regimes; retain `review` until evidence qualifies; (2) the two data-gap classes across the constituent population — `volume_conflicts` 2,818 and `cross_source_conflicts` 2,401 — which likely share a few systemic root causes (provider volume conventions, source precedence) and so may flip in bulk from one rule fix; (3) identity and tape certification, which needs a security master and is blocked on the same access gap as P3.7/CRSP. |

## P4: Research, Backtest, And Promotion Registry

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P4.1 | Pending | Strategy spec schema | Versioned strategy spec includes universe, data, features, schedule, risk, execution, and artifacts. | Required before registry. |
| P4.2 | Pending | Strategy promotion registry | Persist state transitions from idea to retired with evidence and approval. | Should emit promotion events. |
| P4.3 | Review | LEAN integration design | Document how current strategy definitions map into LEAN or LEAN-equivalent runs. | LEAN design is implemented; reconcile the original milestone with [worker contract](lean-backtesting.md) and remaining promotion requirements. |
| P4.4 | Review | LEAN smoke backtest | One current SOTA or simplified strategy runs through LEAN path with reproducible artifacts. | Native smoke and long-history parity passed in [validation evidence](lean-validation-2026-09-26.md); do not treat historical data as certified for promotion. |
| P4.5 | Review | Backtest artifact hashes | Reports, inputs, configs, and outputs are hashed and linked to strategy versions. | Frozen bundle and output hashes plus registry exist; acceptance now concerns coverage of the broader promotion contract. |
| P4.6 | Pending | Overfit/stability gate | Promotion requires split, benchmark, turnover, fee, stress, and parameter stability checks. | Extend current SOTA workflow. |
| P4.7 | Review | LEAN runtime/dependency setup | Requires installing/configuring LEAN runtime or choosing equivalent deployment path. | Pinned local container runtime is installed and used. Prior setup blocker is superseded; P6.15 resource review remains open. |
| P4.22 | Done; monthly retained | Target-change threshold rebalance study | Latest theoretical versus last adopted target; independent of account holdings; causal selection, guards, cost/delay stress and native parity. | [Results](../research/target-change-rebalance-20261015-v1/results.md). 132 scenarios, six native checks. Explicit monthly macro fallback; F3 legacy-basis sensitivity. |
| P4.23 | Done; 6/monthly retained | Joint selection-width X and target-change threshold n | Frozen 6-by-8 grid; 588 full-size scenarios, six native checks and 98 independent adoption checks. Wider selections reduce turnover but do not qualify under FR25 selection guards/stability. | [Results](../research/selection-width-timing-20261015-v1/results.md). F3 is legacy-basis sensitivity; expanded-pool validation later. No monitoring or trading changes. |
| P4.16d | Review: expanded FR25 and subsequent class/volatility screen rejected | Substantial tradable ETF expansion, granular classes and volatility-aware ranking *(operator reaffirmed 2026-10-11)* | Versioned candidate inventory, dated taxonomy and data/contract gap matrix; staged audited admission; scalable app and paper-execution contracts; then controlled full-pool comparisons. Design capacity for hundreds of candidates, with duplicate-exposure controls and risk-normalized class ranking. | [299-record inventory](etf-universe-inventory-2026-10-13.md), 38-addition recorder wave and [50-fund FR25 diagnostic](etf-expansion-findings-2026-10-14.md) completed. The separate [October 16 construction screen](class-volatility-screen-findings.md) rejects all 16 raw/risk-normalized, pooled/class and monthly/dynamic mappings. No expanded candidate qualifies for replay. Review the cash/bill concentration and incomparable-payoff issue before a new hypothesis; historical membership reconstruction remains open. Published pinned inputs only; admission never mandates allocation. **P4.16c remains parked.** [Plan](signal-decay-and-alpha-plan.md). |
| P4.20 | Pending | Decay-based promotion gate | Require any new signal to demonstrate a minimum estimated half-life and sub-period IC stability before it can enter a monitored recipe. | Registered October 10; depends on P4.13. Structural protection against the survivor-selection problem described in the plan's Appendix A. Governance only. |
| P4.21 | Pending | Look-through constituent alpha | Compute the structurally cross-sectional alphas on the constituent cross-section (680 IVV constituent series plus issuer holdings and sector data) and aggregate holdings-weighted to ETF scores. | Registered October 10 and deferred. The only honest route to the 76 structurally cross-sectional alphas, which need breadth that 14 ETFs cannot supply. Carries three disclosed caveats: index-membership history is a survivorship trap, issuer holdings snapshots are prospective-only from October 2026, and the constituent series are the `review`-status population from P3.8. Blocked on the constituent-coverage assessment; do not start before P4.16 answers whether the cross-sectional premise holds. |

## P5: Portfolio Blotter And Execution Controls

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P5.1 | Pending | Rebalance blotter domain model | Model current, target, proposed orders, expected cash, FX, fees, residuals, and constraints. | Stronger than current proposal preview. |
| P5.2 | Pending | Pre-trade check engine | Checks stale data, missing FX, price bands, buying power, duplicate orders, open orders, turnover, concentration, and live caps. | Must block routing. |
| P5.3 | Pending | Blotter API | Dashboard/API can show proposal, constraints, violations, and operator decision actions. | Current dashboard can be extended. |
| P5.4 | Pending | Resize/defer workflow | Operator can approve, reject, resize, defer, or cancel generated orders. | Must persist audit events. |
| P5.5 | In Progress | IB connection health gate | Confirm server time, account, managed accounts, next valid id, and profile before routing. | Read-only recurring broker health, failure backoff and reconnect wakeups exist. Preserve fresh environment/account readiness before every route; ongoing hardening and external Gateway login remain operational dependencies. |
| P5.6 | In Progress | Broker reconciliation gate | Compare IB positions, cash, open orders, fills, and commissions before routing. | Routing and EOD enforce fresh broker reconciliation; durable individual executions and reviewed recovery exist. Broader open-order/commission reconciliation acceptance remains open. See [trading operations](trading-operations.md). |
| P5.7 | Pending | Live kill switch | A hard config/runtime switch prevents live order routing immediately. | Must be tested in paper. |
| P5.8 | Pending | Live capital caps | Per-account, per-strategy, per-symbol, per-order, turnover, and drawdown caps. | Required before Phase 5. |
| P5.9 | Blocked | Live account enablement | Requires explicit human approval, credentials, account id, and proven paper evidence. | Keep live disabled. |
| P5.11 | Blocked | Intraday signal activation and stop-loss execution | Publish audited intraday bars usable for research, then add intraday routing, broker-side or monitored stops, intraday pre-trade risk checks and intraday reconciliation. Until both exist, any stop-loss research is limited to a daily-resolution approximation (a stop fills when the session low breaches it), and that approximation must be disclosed because it flatters stops in gap-down markets. | Registered 2026-10-10 from the [signal decay and alpha plan](signal-decay-and-alpha-plan.md). This is a **platform** workstream, not research: there are no intraday tables in ClickHouse, the recorder holds only raw five-second sampled quotes for five ETFs from 2026-04-04 flagged `research_approved: false`, and routing is a single monthly TWAP window. Blocked on intraday data publication plus P5.1-P5.4. |

## P6: Observability, Alerts, And Incidents

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P6.15 | Pending | Research worker deployment and resource budgets | Benchmark real host/container memory, CPU, startup/data-copy costs and whole-batch latency; compare host-native LEAN, right-sized containers and multicore scheduling. | Operator requested October 11. Fixed 4 GiB/run plus 2 GiB headroom caps LEAN at three jobs on 15.39 GiB Docker, despite 31.55 GiB host RAM. Preserve parity, resource headroom and operator/ClickHouse latency. [Plan](calculation-performance.md#p615--worker-deployment-and-resource-budget-review). |
| P6.1 | Pending | Metrics contract | Define service, data, queue, strategy, portfolio, execution, and reconciliation metrics. | Prometheus/OpenTelemetry compatible. |
| P6.2 | Pending | Local metrics endpoint | API/service exposes metrics for scraping or dashboard display. | Start with FastAPI endpoint if needed. |
| P6.3 | Pending | Grafana dashboard plan | Dashboard panels defined for data freshness, queue lag, broker state, PnL, exposure, and alerts. | Implementation depends on metrics path. |
| P6.5 | Pending | Desktop popup alert channel | Local machine popup for trading-critical warnings/errors. | Windows implementation required. |
| P6.6 | Pending | Incident registry | Alerts can open/update/resolve incidents with durable status. | Links to event ids. |
| P6.7 | Pending | Alert delivery audit | Track which channels received each alert and whether delivery failed. | Required before live. |
| P6.8 | Blocked | SMS/push provider | Requires provider choice and credentials. | Email exists; urgent channel pending. |

## P7: Daily Operating Loops

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P7.1 | Pending | Daily post-trade report | Generate PnL, attribution, slippage, fills, reconciliation, and alert summary. | Uses `.agents/skills/daily-post-trade-analysis.md`. |
| P7.2 | Pending | Continuous research report | Daily/weekly challenger report updates research state and candidate status. | Uses `.agents/skills/continuous-research-loop.md`. |
| P7.3 | Pending | Robustness review report | Weekly service/data/queue/broker/alert health review. | Uses `.agents/skills/system-robustness-review.md`. |
| P7.4 | Pending | Promotion review report | Formal approve/reject/defer/retire artifact for strategy transitions. | Uses `.agents/skills/strategy-promotion-control.md`. |
| P7.6 | Pending | Disaster recovery drill | Backup and restore check for trading-critical local state. | Required before live. |

## P8: Execution Generality

| ID | Status | Work item | Acceptance criteria | Notes / dependencies |
| --- | --- | --- | --- | --- |
| P8.1 | Done for the reviewed US-listed USD ETF boundary | Contract identity registry | IB `reqContractDetails` captured raw, audited and published as an immutable hash-versioned registry carrying `conId`, `secType`, `localSymbol`, exchanges, currency, multiplier, `minTick` and trading class. Ambiguity fails closed. Re-derivable from retained raw evidence. | Foundation for everything else. Uses the existing raw-first, audit, publish discipline rather than a new pattern. |
| P8.2 | Done for the reviewed US-listed USD ETF boundary | Symbol to contract resolution | Resolution requires explicit disambiguation keys (ISIN, or exchange plus currency hint) and rejects ambiguity instead of guessing. Deterministic and recorded per decision. | The hard correctness problem: `BHP` is an ADR on NYSE and a listing on LSE and ASX. A ticker-only lookup is the failure being retired and must not return as the new default. |
| P8.3 | Partial: frozen membership and component unions implemented | Registry-backed universe selectors | Universes become declared selectors over the registry plus explicit membership, replacing the literal `Instrument` dicts in `research/etf_universe.py`, `all_weather_universe.py` and `stock_universe.py`. Existing universes resolve identically to today. | A new instrument then costs a registry entry, not a code edit. Research definitions keep their frozen membership. |
| P8.4 | Done for the reviewed US-listed USD ETF boundary | Instrument admission gate | A contract is tradable only when identity is verified, an audited price history exists, a CNH FX path exists, IB reports it tradable for this account, and its market rules are registered. Admission is an immutable event and every instrument can answer "why not tradable". | Admission stays narrow and reviewed; capability is what generalises. |
| P8.5 | Done for the reviewed US-listed USD ETF boundary | Capability check replacing the hard-coded allocation gate | The shared conservative execution-contract check is extended to verified instrument capabilities: a strategy is allocation-supported when every instrument in its resolved universe is admitted for execution and its execution contract is registered. FR25 and M1/14 become allocatable by admitting XLE and XLB, with no code change. | 2026-10-13: UI/backend share the registry-backed check; FR25/M1 admission and the conditional FR25 preview passed. First customer is deliberately XLE/XLB, which are US-listed USD ETFs, so P8.1-P8.5 need no FX, calendar or data widening. |
| P8.6 | Blocked | Per-currency CNH FX path | Non-USD instruments valued and reconciled in CNH with point-in-time discipline and a declared authoritative source per pair. | **Blocked on data, not engineering:** FX is a documented unresolved input class. Until it is resolved, "any IB tradable" silently means "any USD tradable". |
| P8.7 | Pending | Per-venue calendars and execution windows | Each listing venue has its own session calendar and an execution window in its own timezone, with a defined convention for asynchronous sessions and an explicit valuation date. | `exchange-calendars` is already a dependency. Today routing assumes US sessions only (`live/sota.py:113,281`). |
| P8.8 | Pending | Lot size, tick and minimum-size enforcement | HKEX board lots and TSE hundred-share lots cannot produce an invalid quantity; venue tick regimes enforced at sizing. | The US ETF registry validates whole-share support and cent ticks. Board-lot multiples, non-US tick regimes and broader multipliers remain unsupported. |
| P8.9 | Blocked | Multi-currency governed price lane | Non-USD and non-ETF series admitted through the existing audit and publication process, with per-venue sources, retention rights, basis and corporate-action coverage. | **Blocked on source and licence decisions.** `research/governed_refresh.py:144` currently requires `currency == "USD"` and `instrumentType == "ETF"`. |
| P8.10 | Pending | Generalised exposure, staleness and reporting | Country and currency aggregation, staleness checks and reports correct across venues and calendars. | Reconciliation itself matches on `order_ref` and is already symbol-agnostic, so this is mostly free. |

## Next Recommended Work Order

Revised after the 2026-10-11 second review. The research queue is now governed by the
[signal decay and alpha plan](signal-decay-and-alpha-plan.md); the items below
are the cross-cutting platform work that runs alongside it.

**Research, one item at a time with a review between items.** The second review and the
fixed P4.18 experiment and the scoped P4.19 retrospective comparison are complete. Next
complete the **P4.16d cash-relative net retest** with the signal fixed
([scope and audit](research-cost-policy-review-2026-10-17.md)); compare Sharpe and
Calmar against SOTA and monitored strategies, then stop for the operator report.
Register horizon, peer-group, incremental payoff and actual fill-based exit
contracts before any new budget/TP/SL grid. See the current priorities at the top of the plan.

**Platform, in parallel:** the new **P8** execution-generality phase
([plan](execution-generality-plan.md)) removes the 12-ETF assumption. Its critical
path P8.1–P8.5 is deliberately narrow — XLE and XLB are US-listed USD ETFs, so
opening the 14-ETF allocation gate needs no FX, calendar or data widening — and
it replaces the hard-coded strategy gate so the next strategy needs no code edit.

Platform and data work, in parallel:

1. Qualify original-release sector and energy history — the standing prerequisite for any new feature block. Historical EIA/CFTC/issuer observations are captured prospectively and are not admissible for earlier decisions; this remains unresolved and blocks new feature blocks that depend on it.
2. Resolve the IB market-data entitlement blocker (IB 10089/420 for `reqRealTimeBars`) so live capture can move off the delayed sampled channel, which is inspection evidence and not complete interval OHLCV. This is a precondition for P5.11.
3. P3.8: promote `review` series where the gaps are fixable, starting with the four ETFs (IVV, XLF, XLRE, and resolving the HYXU/EUHY mandate transition without splicing the stale series), then the two data-gap classes that likely share systemic root causes.
4. P3.4: add ClickHouse source-observation tables, source precedence, cross-source disagreement checks and the daily gap/source-disagreement panels.
5. P4.1: define the versioned strategy spec schema, then P6.1 metrics and P5.1 the stronger rebalance blotter domain model.
6. Register the remaining governed-data cleanups as small items: the two private-name couplings between `research_etfs` and `governed_refresh`, and the absence of a published-batch list route in `web/governed_data.py`.

**Deferred / not started by this plan:** P4.21 (look-through constituent alpha)
until the next look-through research design and required published inputs are accepted; P5.11 (intraday activation and stops) until audited intraday
data is published and an intraday execution stack exists.
