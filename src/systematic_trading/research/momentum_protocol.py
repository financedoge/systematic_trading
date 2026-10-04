"""Finite, pre-result experiment registration for the October momentum study."""
from datetime import UTC, datetime


def protocol():
    monthly = [f"A{i}" for i in range(1, 9)] + [f"B{i}" for i in range(1, 5)] + [f"C{i}" for i in range(3)]
    weekly = ["A1", "A2", "A7", "A8", "C0", "C1", "C2"]
    recipes = [dict(id="parent-M", recipe="parent", cadence="monthly")]
    recipes += [dict(id=r+"-M", recipe=r, cadence="monthly") for r in monthly]
    recipes += [dict(id="parent-W", recipe="parent", cadence="weekly")]
    recipes += [dict(id=r+"-W", recipe=r, cadence="weekly") for r in weekly]
    recipes += [dict(id=r+"-M", recipe=r, cadence="monthly", prerequisite="published_pit_broad_usd") for r in ("U0", "U1")]
    comparisons = []
    def pair(name, terms):
        comparisons.append(dict(id=name, terms=terms))
    for r in monthly + ["U0", "U1"]:
        pair(r+"-parent-M", {r+"-M": 1, "parent-M": -1})
    for b in [f"B{i}" for i in range(1, 5)]:
        for a in ("A6", "A7", "A8"):
            pair(b+"-"+a, {b+"-M": 1, a+"-M": -1})
    for r in ("C1", "C2"):
        pair(r+"-C0-M", {r+"-M": 1, "C0-M": -1})
    pair("C1-C2-M", {"C1-M": 1, "C2-M": -1})
    pair("A6-A7-M", {"A6-M": 1, "A7-M": -1})
    pair("U1-U0-M", {"U1-M": 1, "U0-M": -1})
    pair("parent-W-M", {"parent-W": 1, "parent-M": -1})
    for r in weekly:
        pair(r+"-parent-W", {r+"-W": 1, "parent-W": -1})
        pair(r+"-clock-interaction", {r+"-W": 1, "parent-W": -1, r+"-M": -1, "parent-M": 1})
    for r in ("C1", "C2"):
        pair(r+"-C0-W", {r+"-W": 1, "C0-W": -1})
    pair("C1-C2-W", {"C1-W": 1, "C2-W": -1})
    for slot in range(1, 4):
        for parent in ("activity", "rolling"):
            pair(f"transfer-{slot}-{parent}", {f"transfer-{slot}-{parent}": 1, f"parent-{parent}": -1})
    return dict(version="momentum-20261001-v1", registered_at=datetime.now(UTC).isoformat(),
        authorization="User: Let's do that. If you can use all cores available for the backtesting.",
        start="2016-01-04", warmup_start="2012-01-05", end="2026-09-30",
        initial_cash_usd="1000000", cost_bps=[5, 10, 20], slippage_bps=0,
        accounting="USD cash and adjusted units; prior-close sizing; next-session open fills; cents; whole units; sells first; proportional affordability; no leverage; no interest",
        price_basis="Published audited dividend/split-adjusted OHLC; revised vintages, not historical publication vintages",
        inherited_volume_basis="Published audited split-adjusted source volume, retained solely to reproduce parent ratio features and frozen models. Not raw dollar turnover or net ETF flows; no new traded-activity feature is introduced.",
        recipe_definitions={
            "A1": "rank(P[t]/P[t-5]-1)", "A2": "rank(P[t]/P[t-10]-1)",
            "A3": "rank(P[t]/P[t-21]-1)", "A4": "rank(P[t-21]/P[t-42]-1)",
            "A5": "rank(P[t-21]/P[t-63]-1)", "A6": "S=(A1+A2)/2", "A7": "L=(A4+A5)/2", "A8": "(S+L)/2",
            "B1": "a=.75 up / .25 down / .5 neutral; a*S+(1-a)*L", "B2": "B1 mirrored",
            "B3": "a=.75 right / .25 left / .5 neutral; a*S+(1-a)*L", "B4": "B3 mirrored",
            "C0": "D={eligible:q>=q6-.10}; enter and exit immediately on scheduled dates",
            "C1": "enter D immediately; exit after 5 consecutive completed sessions outside D",
            "C2": "enter after 5 consecutive completed sessions in D; exit immediately",
        },
        momentum_pool="Replace only 75% trend category; retain 25% volume and positive 252-session gate. Tied ranks [-1,1].",
        regime=dict(equities=["SPY", "VGK", "EWJ", "EWH", "EWY", "MCHI"], daily_return="equal-weight mean", lookback=126,
                    trend="sign of compounded returns", skew="adjusted Fisher-Pearson; thresholds +/-0.25; zero variance neutral"),
        membership=dict(margin="0.10", confirmation_sessions=5, seed="eligible top six on first scheduled date; seed exception recorded",
                        floor="fill highest-ranked eligible to six, record delayed-entry overrides; four/five select all; below four neutral overlay and reset",
                        hard_exit="positive-252 gate failure forces exit at next scheduled rebalance; no intraperiod discretionary trades",
                        counter="daily from first decision; no trade between scheduled rebalances"),
        clock="First session of month or ISO week; prior session close; weekly model refits remain monthly; first sample session is a declared initial deployment",
        usd_model=dict(window="expanding", minimum_completed_months=60, label="next-month return minus universe mean; completed strictly before fit close",
                       features=["S", "L", "vol63"], extra_features=["USD21", "USD63"], standardization="training means/std only",
                       model="per-ETF ridge; mean squared error plus 1.0*sum(beta^2); unpenalized intercept; no tuning",
                       tilt="rank predictions, 12% proportional tilt, +/-3pp active, preserve parent gross and zero weights, 45% cap unless inherited larger",
                       unavailable="U0 and U1 both unavailable without release/vintage-audited broad USD; no proxy substitution"),
        recipes=recipes, comparisons=comparisons, family_size=len(comparisons),
        inference=dict(endpoint="12*mean(paired calendar-month net returns)", sample="all 129 complete months; 2023 split and subperiods descriptive",
                       blocks=[6, 3, 12], replications=20000, seed=20261001, method="joint circular calendar-block bootstrap; centered two-sided null; Holm over frozen full ledger",
                       unavailable_p=1, intervals="95% marginal percentile; no simultaneous interval claim"),
        transfer_selection="At most three. Require positive full-history and 2023+ paired mean at 5bp, positive full-history mean at 20bp, drawdown worsening <=2pp. Sort by full-history 5bp paired mean descending, id lexical tie-break. Transfer unchanged rules and cadence. Descriptive stress check only: same-data adaptive selection invalidates confirmatory transfer p-values; report p=1 for reserved slots and descriptive intervals only.",
        annual_cost_budget_bps=25, net_return_materiality_hurdle=None,
        stresses={"2018": ["2018-01-01", "2018-12-31"], "covid": ["2020-02-01", "2020-04-30"], "2022": ["2022-01-01", "2022-12-31"]},
        approval="Research only. No strategy promotion, monitoring registration, trading-policy change, orders or live enablement.",
        limitations=["Reused history; not untouched validation.", "Auditing prices does not certify historical publication vintages.",
                     "Earlier unrecorded research trials are outside the computable correction; selection bias remains.",
                     "Parent fitted models retain their original feature basis; activity-transfer evidence remains a legacy proxy, not audited traded dollar volume."])
