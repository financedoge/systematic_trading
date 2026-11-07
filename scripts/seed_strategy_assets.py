"""One-time initial asset catalog migration; refuses to replace an existing catalog."""
import json
from pathlib import Path

from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.research.strategy_dependencies import load_registry


def main():
    path = Path(__file__).resolve().parents[1] / 'src/systematic_trading/research/strategy_assets.json'
    if path.exists():
        raise ValueError('Initial catalog already exists. Version and migrate instead of regenerating pins.')
    assets = {}
    def add(key, name, kind, provider, inputs=(), *, basis='adjusted', cadence='daily', parameters=None,
            source=None, monitor='evidence_gap', limitations=None):
        contract = dict(kind=kind, provider=provider, inputs={k: assets[k]['sha256'] for k in inputs},
            basis=basis, cadence=cadence, parameters=parameters or {},
            availability='Completed observations only; actual capture and vintage cutoffs remain binding.',
            missing='Abstain or fail under the frozen provider contract; never fill or substitute.',
            monitor=monitor if kind == 'signal' else None)
        assets[key] = dict(name=name, contract=contract, sha256=digest(encode(contract)), source=source,
            limitations=limitations or ['Audited histories do not certify historical dissemination availability.'])
    add('prices-adjusted-v1', 'Audited adjusted price histories', 'time_series',
        'systematic_trading.research.governed_inputs:GovernedInputs', source='governance/catalog')
    add('activity-raw-v1', 'Audited raw price and volume', 'time_series',
        'systematic_trading.research.m1_monitoring:load_inputs', basis='audited raw prices and raw volume', source='governance/catalog')
    add('fx-usdcnh-v1', 'Observed USD/CNH', 'time_series',
        'systematic_trading.research.tracked_inputs:publish_observed_fx', basis='observed post-close midpoint', source='governance/fx-usd-cnh')
    add('usd-vintages-v1', 'Broad-dollar vintage histories', 'time_series',
        'systematic_trading.research.usd_data:load_usd', basis='original published vintages', source='governance/usd-broad-index')
    add('economic-context-v1', 'Original economic context vintages', 'time_series',
        'systematic_trading.research.economic_tracking:economic_inputs', basis='original eleven-series vintage subset')
    add('financial-context-v1', 'FR25 financial-condition vintages', 'time_series',
        'systematic_trading.research.fr25_tracking:economic_inputs', basis='frozen financial vintage subset')
    add('technical-features-v1', 'Price and technical features', 'signal',
        'systematic_trading.signals.library:compute_signal_features', ['prices-adjusted-v1'])
    add('risk-parity-volatility-v1', 'Risk-parity realized volatility', 'signal',
        'systematic_trading.data.analytics:realized_volatility_from_bars', ['prices-adjusted-v1'], parameters={'lookback_sessions':63})
    add('activity-lag20-v1', 'Lagged activity features', 'signal',
        'systematic_trading.research.flow_concentration:concentration_features', ['prices-adjusted-v1'], parameters={'lag':20}, basis='adjusted prices and published volume; legacy activity contract')
    add('activity-audited-lag20-v1', 'Audited raw-dollar activity · lag 20', 'signal',
        'systematic_trading.research.candidate_pool:AuditedActivity', ['prices-adjusted-v1','activity-raw-v1'], parameters={'lag':20}, basis='raw dollar activity; adjusted return direction')
    add('fixed-tree-v1', 'Frozen technical decision tree', 'signal',
        'systematic_trading.signals.decision_tree:DecisionTreeSignalOverlay', ['technical-features-v1'], cadence='frozen fit; daily inference')
    add('m1-selection-v1', 'M1 momentum and volume selection', 'signal',
        'systematic_trading.research.signal_decay_job:signal_values', ['prices-adjusted-v1','activity-raw-v1'], monitor='m1_rank_ic')
    for count in (12,14):
        add(f'rolling-xgboost-{count}-v1', f'Rolling one-year XGBoost · {count} ETFs', 'signal',
            'systematic_trading.research.rolling_tracking:prepare_model_schedule', ['technical-features-v1'],
            cadence='monthly fit; daily inference', parameters={'universe_size':count,'training_years':1,'label_embargo':'strictly before fit close'})
        add(f'usd-ridge-{count}-v1', f'USD ridge · {count} ETFs', 'signal',
            'systematic_trading.research.usd_tracking:prepare_usd_schedule', ['prices-adjusted-v1','usd-vintages-v1'],
            cadence='monthly fit; daily inference', parameters={'universe_size':count})
    add('economic-ridge-v1', 'Economic expanding ridge', 'signal',
        'systematic_trading.research.economic_tracking:economic_inputs', ['prices-adjusted-v1','economic-context-v1'], cadence='monthly fit; daily inference')
    add('fr25-selection-v1', 'FR25 financial rank forecast', 'signal',
        'systematic_trading.research.fr25_tracking:economic_inputs', ['prices-adjusted-v1','financial-context-v1'], cadence='monthly fit; daily inference')
    add('alpha101-tilt-v1', 'Alpha101 activity tilt', 'signal',
        'systematic_trading.research.alpha101_tilt_overlay:Alpha101FamilyTiltOverlay', ['prices-adjusted-v1','activity-raw-v1'])
    add('broadtrend-models-v1', 'BroadTrend frozen per-ETF models', 'model',
        'systematic_trading.research.broadtrend:model_pack', cadence='frozen; new version required to refit',
        parameters={'sha256':'40cb164b06d0052ab7f7641d6446d0ee9f93c810ae8204d05f3b6114e74a994e','training_end':'2022-12-30'})
    add('broadtrend-signals-v1', 'BroadTrend daily trend and long/cash states', 'signal',
        'systematic_trading.research.broadtrend:signal_history', ['prices-adjusted-v1','broadtrend-models-v1'],
        monitor='broadtrend_time_series', parameters={'universe_size':51,'execution':'next open','prospective_start':'2026-10-30'},
        limitations=['Frozen 2022 models; inspected historical development. Prospective monitoring starts 2026-10-30.',
            'HMM scores are not calibrated probabilities; close-tested stops execute next open.',
            'Fractional adjusted units; signals confer no broker execution authority.'])
    add('conditional-snapshot-v1', 'Conditional FR25 frozen signal snapshot', 'signal',
        'systematic_trading.research.fr25_lifecycle_conditional:verified_input_provenance', ['prices-adjusted-v1'], cadence='historical snapshot; no daily extension')
    composites = {}
    for key in load_registry()['strategies']:
        ids = ['prices-adjusted-v1']
        if key == 'broadtrend_full_pool_v1': ids += ['broadtrend-signals-v1']
        elif key == 'fr25_lifecycle_conditional_v1': ids += ['conditional-snapshot-v1']
        elif key == 'risk_parity': ids += ['risk-parity-volatility-v1']
        else:
            ids += ['fx-usdcnh-v1','technical-features-v1']
            is14 = key in {'research_m1_14_v1','research_fr25_14_v1','research_fr25_alpha_tilt_5_v1'}
            isusd = key.endswith('_usd_v1') or key in {'research_fallback_f3_v1','research_economic_context_ridge_v1'} or is14
            rolling = 'rolling_xgboost' in key or key in {'research_fallback_f3_v1','research_economic_context_ridge_v1'} or is14
            if 'activity' in key or rolling: ids += ['activity-audited-lag20-v1' if is14 else 'activity-lag20-v1'] if '1y_v1' not in key else []
            if rolling: ids += [f'rolling-xgboost-{14 if is14 else 12}-v1']
            else: ids += ['fixed-tree-v1']
            if isusd: ids += [f'usd-ridge-{14 if is14 else 12}-v1']
            if is14: ids += ['m1-selection-v1']
            if key == 'research_economic_context_ridge_v1': ids += ['economic-ridge-v1']
            if key in {'research_fr25_14_v1','research_fr25_alpha_tilt_5_v1'}: ids += ['fr25-selection-v1']
            if key == 'research_fr25_alpha_tilt_5_v1': ids += ['alpha101-tilt-v1']
        composites[key] = {k: assets[k]['sha256'] for k in ids}
    reviews = {k:dict(search_terms=['existing executable providers','time-series','rolling models'],
        inspected_assets=list(refs), decision='Initial migration: reuse the existing application providers and frozen recipes; no model refit or parameter change.') for k,refs in composites.items()}
    path.write_text(json.dumps(dict(schema_version=1, assets=assets, composites=composites,reuse_reviews=reviews),indent=2)+'\n', encoding='utf8')


if __name__ == '__main__':
    main()
