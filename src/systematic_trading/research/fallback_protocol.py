"""Finite fallback ablation; no registry promotion or monitored membership changes."""
from dataclasses import replace

from systematic_trading.research.strategy_catalog import registered_strategy_definition, OverlaySpec

BASELINE = 'research_rolling_xgboost_1y_lag20_v1_usd_v1'
POLICIES = dict(F0='neutral', F1='eligible_cash', F2='all_cash', F3='defensive_cash')


def definition(recipe):
    base = registered_strategy_definition(BASELINE)
    if recipe == 'F0':
        return base
    policy = POLICIES[recipe]
    pool = base.overlays[0]
    return replace(base, key='research_fallback_'+recipe.lower()+'_v1', name='Fallback '+recipe+' · '+policy,
        state='research', promoted_on=None,
        description='Active rolling XGBoost/activity/USD parent; only weak-breadth fallback changes to '+policy+'.',
        overlays=(OverlaySpec(pool.kind, dict(pool.parameters, fallbackPolicy=policy)), *base.overlays[1:]))


def protocol(end):
    return dict(version='fallback-v1', baseline=BASELINE, warmup_start='2012-01-05', start='2016-01-04', end=end,
        initial_cash_usd='1000000', recipes={k:definition(k).to_dict() for k in POLICIES},
        cost_bps=[5,10,20], delayed_sessions=1, family_size=3, bootstrap_blocks=[3,6,12],
        bootstrap_replications=20000, seed=20261007, promotion_eligible=False,
        cash_policy='Zero interest for every arm; engineering scenario, not historical broker cash returns.',
        resource_policy='Use all logical CPUs for independent jobs; native memory bounded to 4 GiB/run plus 2 GiB reserve.',
        comparisons=['F1-F0','F2-F0','F3-F0'],
        interpretation='Retrospective paired research. No untouched holdout; future paper evidence required.',
        f4_status='Deferred until a bill ETF recorder, audited publication, Market Data visibility and fixed cap are qualified.',
        limitations=[
            'USD accounting only. Uncertified historical USD/CNH is excluded; no CNH performance claim.',
            'Audited adjusted OHLC vintages are revised history, not certified historical publication vintages.',
            'Inherited split-adjusted source volume remains a price/volume proxy, not raw traded activity or fund flows.',
            'Rolling XGBoost and USD models reuse the pinned application schedules; no re-tuning or new fit.',
            'Adjusted units, whole shares, next-session open, no separate dividends, no modeled spread/market impact.',
            'Cash earns zero; Sharpe uses zero reference rate. Calmar is CAGR divided by absolute maximum drawdown.',
            'The inherited 45% cap applies before selection and overlays, not final holdings; not changed in this ablation.',
            'Native parity validates frozen-target execution/accounting; target logic is separately checked against the app baseline.',
        ])
