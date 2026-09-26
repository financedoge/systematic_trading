from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import date, datetime, timedelta, UTC
from decimal import Decimal
from pathlib import Path

from systematic_trading.backtest.accounting import quantize_money
from systematic_trading.daily_quality import captured_before_close, completed_session, valid_ohlc
from systematic_trading.domain.market import PriceBar
from systematic_trading.lean.contracts import BacktestRunSpec, sha256, write_json, verify_bundle
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.live.trading_calendar import us_equity_market_close, is_us_trading_day
from systematic_trading.research import current_sota_definition, instruments_for_definition
from systematic_trading.research.flow_concentration import FlowConcentrationSpec
from systematic_trading.research.constituent_signals import ConstituentOverlaySpec


def export_bundle(*, store, root: Path, start: date, end: date, warmup_start: date,
                  strategy='sota', mode='shared', cost_bps='5', slippage_bps='0', delay=0, legacy_fx=False, lookback_bars=63) -> Path:
    """Freeze current ClickHouse values as explicitly uncertified research evidence."""
    if root.exists():
        raise FileExistsError(f'Immutable bundle already exists: {root}')
    if not warmup_start < start <= end or not completed_session(end):
        raise ValueError('Require warmup < start <= completed end session')
    definition = current_sota_definition()
    instruments = instruments_for_definition(definition)
    data, provenance = {}, {}
    for symbol in instruments:
        raw = store.client.query_daily_bars(symbol=symbol, start_date=warmup_start.isoformat(), end_date=end.isoformat(), limit=50000)
        if not raw:
            raise ValueError(f'Missing {symbol} data')
        bars = []
        for row in raw:
            item = PriceBar.model_validate(row)
            if not completed_session(item.trade_date) or captured_before_close(row):
                raise ValueError(f'{symbol}: unfinished daily source observation on {item.trade_date}')
            if not valid_ohlc(item) or item.volume <= 0:
                raise ValueError(f'{symbol}: invalid OHLC/volume on {item.trade_date}')
            bars.append(item.model_dump(mode='json'))
        data[symbol] = bars
        provenance[symbol] = raw
    days = [row['trade_date'] for row in next(iter(data.values()))]
    for symbol, rows in data.items():
        if [row['trade_date'] for row in rows] != days:
            raise ValueError(f'{symbol}: missing/duplicate/different sessions; no forward-fill permitted')
    fx_rows = store.client.query_fx_rates(base_currency='USD', quote_currency='CNH', start_date=warmup_start.isoformat(), end_date=end.isoformat())
    fx = {row['rate_date']: row for row in fx_rows}
    fx_used, fx_lineage = {}, {}
    for day in days:
        candidates = [d for d in fx if d <= day]
        chosen = max(candidates) if candidates else None
        if not chosen or (chosen != day and not legacy_fx) or (date.fromisoformat(day) - date.fromisoformat(chosen)).days > 7:
            raise ValueError(f'Missing/stale USD/CNH observation for {day}; legacy carry requires explicit opt-in')
        if Decimal(str(fx[chosen]['rate'])) <= 0:
            raise ValueError(f'Invalid FX for {day}')
        fx_used[day] = str(fx[chosen]['rate'])
        fx_lineage[day] = {'observation_date': chosen, 'source': fx[chosen]['source_name'], 'carried': chosen != day}
    spec_values = dict(strategy=strategy, mode=mode, start_date=start.isoformat(), end_date=end.isoformat(),
                       warmup_start=warmup_start.isoformat(), transaction_cost_bps=cost_bps, slippage_bps=slippage_bps,
                       execution_delay_sessions=delay, lookback_bars=lookback_bars,
                       fx_policy="legacy_carry_max7" if legacy_fx else "exact_observation")
    return freeze_bundle(root=root, bars=data, fx=fx_used,
                         provenance={'bars': provenance, 'fx': fx_rows, 'fx_lineage': fx_lineage, 'fx_warning': 'Legacy rates may include onshore CNY proxies; uncertified CNH engineering comparison only', 'license': 'Local provider data; no redistribution rights inferred'},
                         spec_values=spec_values)


def freeze_bundle(*, root: Path, bars: dict, fx: dict, provenance: dict, spec_values: dict,
                  constituent_features: dict | None = None, base_tree_models: dict | None = None) -> Path:
    if root.exists():
        raise FileExistsError(root)
    days = [row['trade_date'] for row in next(iter(bars.values()))]
    first, last = date.fromisoformat(spec_values['warmup_start']), date.fromisoformat(spec_values['end_date'])
    expected = [str(first + timedelta(days=i)) for i in range((last - first).days + 1)
                if is_us_trading_day(first + timedelta(days=i))]
    for symbol, rows in bars.items():
        if [row['trade_date'] for row in rows] != expected:
            raise ValueError(f'{symbol}: missing/duplicate/out-of-order calendar sessions')
        for row in rows:
            if not valid_ohlc(PriceBar.model_validate(row)) or row['volume'] <= 0:
                raise ValueError(f'{symbol}: invalid OHLC/volume')
    if set(bars) != set(instruments_for_definition(current_sota_definition())):
        raise ValueError('Bundle universe differs from the strategy universe')
    if any(day not in fx or not Decimal(fx[day]).is_finite() or Decimal(fx[day]) <= 0 for day in days):
        raise ValueError('Missing or invalid FX observation')
    run_days = [day for day in days if spec_values['start_date'] <= day <= spec_values['end_date']]
    if not run_days:
        raise ValueError('Empty run window')
    decisions = {}
    flow_config = spec_values.get('flow_overlay')
    flow_config = FlowConcentrationSpec.model_validate(flow_config) if flow_config is not None else None
    constituent_config = spec_values.get('constituent_overlay')
    constituent_config = ConstituentOverlaySpec.model_validate(constituent_config) if constituent_config is not None else None
    if (constituent_config is not None) != (constituent_features is not None):
        raise ValueError('Constituent configuration and frozen features must be supplied together')
    if bool(spec_values.get('base_tree_model_schedule')) != (base_tree_models is not None):
        raise ValueError('Dated base-tree configuration and models must be supplied together')
    flow_state = {}
    registered = None
    if spec_values.get('strategy_definition'):
        from systematic_trading.research.strategy_catalog import StrategyDefinition
        registered = StrategyDefinition.from_dict(spec_values['strategy_definition'])
        if registered.universe_key != 'multi_asset' or registered.scheduler != 'static_monthly':
            raise ValueError('LEAN registered adapter supports the monthly multi-asset contract')
    previous_month = None
    for day in run_days:
        if day[:7] != previous_month:
            index = days.index(day)
            if index == 0:
                raise ValueError('Missing prior session')
            targets = targets_for_day(bars, date.fromisoformat(day), benchmark=spec_values.get('strategy') == 'benchmark',
                                      lookback_bars=spec_values.get('lookback_bars', 63),
                                      flow_overlay=flow_config, flow_state=flow_state,
                                      constituent_overlay=constituent_config, constituent_features=constituent_features,
                                      base_tree_models=base_tree_models, fixed_model_from=spec_values.get('fixed_model_from'),
                                      definition=registered)
            execution_index = run_days.index(day) + spec_values.get('execution_delay_sessions', 0)
            if execution_index >= len(run_days):
                continue
            decisions[run_days[execution_index]] = {
                'signal_session': day, 'known_through': days[index - 1],
                'targets': [item.model_dump(mode='json') for item in targets],
            }
            previous_month = day[:7]
    root.mkdir(parents=True)
    source_root = Path(__file__).resolve().parents[1]
    source_files = sorted(source_root.rglob('*.py'))
    source_hash = hashlib.sha256()
    for path in source_files:
        relative = Path('source/systematic_trading') / path.relative_to(source_root)
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
        source_hash.update(relative.as_posix().encode() + path.read_bytes())
    definition = current_sota_definition().to_dict()
    if registered:
        definition = registered.to_dict()
    if spec_values.get('strategy') == 'benchmark':
        from systematic_trading.research.strategy_catalog import risk_parity_definition
        definition = risk_parity_definition().to_dict()
    if spec_values.get('fixed_model_from'):
        definition = dict(definition=definition, fixed_model_from=spec_values['fixed_model_from'])
    if base_tree_models is not None:
        write_json(root / 'base_tree_models.json', base_tree_models)
        definition = dict(recipe=definition, research_base_models_sha256=sha256(root / 'base_tree_models.json'), promotion_eligible=False)
    if flow_config is not None:
        definition = dict(base=definition, research_overlay=flow_config.model_dump(), promotion_eligible=False)
    if constituent_config is not None:
        definition = dict(base=definition, research_overlay=constituent_config.model_dump(), promotion_eligible=False)
        write_json(root / 'constituent_features.json', constituent_features)
    strategy_hash = hashlib.sha256(json.dumps(definition, sort_keys=True).encode()).hexdigest()
    commit = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True, check=True).stdout.strip()
    spec = BacktestRunSpec(**spec_values, strategy_hash=strategy_hash, source_hash=source_hash.hexdigest(), repository_commit=commit)
    for filename, payload in [('spec.json', spec.model_dump()), ('bars.json', bars), ('fx.json', fx),
                              ('provenance.json', provenance), ('decisions.json', decisions),
                              ('strategy.json', definition), ('sessions.json', run_days)]:
        write_json(root / filename, payload)
    # Two observations per session; the opening FX is the prior completed session.
    quotes = {}
    for symbol, rows in bars.items():
        by_day = {row['trade_date']: row for row in rows}
        records = []
        quotes[symbol] = {}
        for day in run_days:
            prior = days[days.index(day) - 1]
            row = by_day[day]
            opening = quantize_money(Decimal(row['open']) * Decimal(fx[prior]))
            closing = quantize_money(Decimal(row['close']) * Decimal(fx[day]))
            reference = quantize_money(Decimal(by_day[prior]['close']) * Decimal(fx[prior]))
            closing_time = us_equity_market_close(date.fromisoformat(day))
            if closing_time is None:
                raise ValueError(f'Non-session input: {day}')
            records += [f'{day}T09:30:00,{opening},open', f'{day}T{closing_time.isoformat()},{closing},close']
            quotes[symbol][day] = {'open': str(opening), 'close': str(closing), 'reference': str(reference)}
        (root / 'quotes').mkdir(exist_ok=True)
        (root / 'quotes' / f'{symbol}.csv').write_text('\n'.join(records) + '\n', encoding='utf-8')
    write_json(root / 'quotes.json', quotes)
    manifest = {'schema_version': 1, 'created_at': datetime.now(UTC).isoformat(),
                'data_rows': sum(len(v) for v in bars.values()), 'decision_count': len(decisions),
                'files': {p.relative_to(root).as_posix(): sha256(p) for p in sorted(root.rglob('*')) if p.is_file()}}
    write_json(root / 'manifest.json', manifest)
    verify_bundle(root)
    return root
