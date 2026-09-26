"""Summarize native LEAN study outputs, temporal checks and paired uncertainty."""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from systematic_trading.lean.contracts import write_json, sha256, verify_bundle
from systematic_trading.domain.market import PriceBar
from systematic_trading.research.flow_concentration import FlowConcentrationSpec, concentration_features


WINDOWS = {
    'full': ('2013-04-01', '2026-09-24'),
    'fitted_pre2023': ('2013-04-01', '2022-12-31'),
    'reused_post2023': ('2023-01-01', '2026-09-24'),
    'post2023_to_old_end': ('2023-01-01', '2026-04-29'),
    'post_artifact_extension': ('2026-04-30', '2026-09-24'),
    'stress_2015_16': ('2015-01-01', '2016-12-31'),
    'stress_2018': ('2018-01-01', '2018-12-31'),
    'stress_2020': ('2020-01-01', '2020-12-31'),
    'stress_2022': ('2022-01-01', '2022-12-31'),
    **{str(year): (f'{year}-01-01', f'{year}-12-31') for year in range(2013, 2027)},
}


def return_vector(rows: list[dict], initial=1_000_000):
    values = np.array([float(r['nav']) for r in rows])
    return values / np.r_[initial, values[:-1]] - 1


def metrics(economic: dict, start: str, end: str, initial=1_000_000):
    rows = economic['nav']
    mask = np.array([start <= r['date'] <= end for r in rows])
    returns = return_vector(rows, initial)[mask]
    if not len(returns):
        return None
    wealth = np.cumprod(1+returns)
    peak = np.maximum.accumulate(np.r_[1.0, wealth])[1:]
    dd = float(np.min(wealth/peak-1))
    cagr = float(wealth[-1] ** (252/len(returns))-1)
    vol = float(np.std(returns, ddof=1)*math.sqrt(252))
    prior_nav = {r['date']: initial if i == 0 else float(rows[i-1]['nav']) for i, r in enumerate(rows)}
    fills = [f for f in economic.get('fills', []) if start <= f['date'] <= end]
    turnover = sum(abs(f['quantity'])*float(f['price'])/prior_nav[f['date']] for f in fills)*252/len(returns)
    selected = [r for r, keep in zip(rows, mask) if keep]
    return dict(sessions=len(returns), total_return=float(wealth[-1]-1), cagr=cagr,
                volatility=vol, sharpe=float(np.mean(returns)*252/vol) if vol else 0,
                max_drawdown=dd, calmar=cagr/abs(dd) if dd else None,
                annual_traded_notional_over_nav=turnover,
                fee_cnh=sum(float(f['fee']) for f in fills), fills=len(fills),
                average_cash=float(np.mean([float(r.get('cash', 0))/float(r['nav']) for r in selected])))


def block_audit(matrix: np.ndarray, names: list[str], replicates=2000, block=63, seed=20260926):
    """Paired circular blocks; max-t centered-null adjustment across all trials."""
    n, k = matrix.shape
    rng = np.random.default_rng(seed)
    full_blocks, remainder = divmod(n, block)
    doubled = np.vstack((matrix, matrix[:block]))
    prefix = np.vstack((np.zeros((1, k)), np.cumsum(doubled, axis=0)))
    sums = prefix[np.arange(n)+block] - prefix[np.arange(n)]
    tail = prefix[np.arange(n)+remainder] - prefix[np.arange(n)]
    starts = rng.integers(n, size=(replicates, full_blocks))
    draws = (sums[starts].sum(axis=1)+tail[rng.integers(n, size=replicates)])/n
    means = matrix.mean(axis=0)
    se = draws.std(axis=0, ddof=1)
    se = np.maximum(se, 1e-16)
    null = (draws-means)/se
    max_null = null.max(axis=1)
    result = {}
    for i, name in enumerate(names):
        statistic = means[i]/se[i]
        lo, hi = np.quantile(draws[:, i]*252, [.025, .975])
        result[name] = dict(annual_arithmetic_excess=float(means[i]*252),
            ci95=[float(lo), float(hi)],
            one_sided_p=float((1+np.sum(null[:, i] >= statistic))/(replicates+1)),
            max_t_family_adjusted_p=float((1+np.sum(max_null >= statistic))/(replicates+1)))
    return dict(block_sessions=block, replicates=replicates, seed=seed, trials=result,
                caveat='Exploratory dependent-return bootstrap; reused baseline selection and nonstationarity remain uncorrected.')


def price_benchmark(rows, fx, days):
    """Separate friction-matched buy/hold context, not a native LEAN strategy run."""
    by_date = {r['trade_date']: r for r in rows}
    if any(d not in by_date for d in days):
        return None
    first = days[0]
    prior = max(d for d in fx if d < first)
    opening = round(float(by_date[first]['open'])*float(fx[prior]), 2)
    quantity = math.floor(1_000_000/(opening*1.0005))
    fee = round(quantity*opening*.0005, 2)
    cash = 1_000_000-quantity*opening-fee
    return dict(nav=[dict(date=d, nav=str(cash+quantity*round(float(by_date[d]['close'])*float(fx[d]), 2)),
                          cash=str(cash)) for d in days],
                fills=[dict(date=first, quantity=quantity, price=str(opening), fee=str(fee))])


def signal_diagnostics(root, bars, economies):
    spec = FlowConcentrationSpec()
    decisions = economies['confirmed_acceleration']['decisions']
    rows = []
    for execution, decision in sorted(decisions.items()):
        cutoff = date.fromisoformat(decision['signal_session'])
        histories = {s: [PriceBar.model_validate(r) for r in v if date.fromisoformat(r['trade_date']) < cutoff]
                     for s, v in bars.items()}
        features = concentration_features(histories, spec)
        for symbol, values in features.items():
            rows.append(dict(execution_session=execution, symbol=symbol, **values))
    write_json(root/'signal_diagnostics.json', rows)
    z, mom, volume = [np.array([r[k] for r in rows]) for k in ('z', 'momentum_20', 'signed_volume_20')]
    return dict(asset_months=len(rows), buy_fraction=sum(r['signal'] == 1 for r in rows)/len(rows),
                sell_fraction=sum(r['signal'] == -1 for r in rows)/len(rows),
                correlation_z_momentum20=float(np.corrcoef(z, mom)[0, 1]),
                correlation_z_signedvolume20=float(np.corrcoef(z, volume)[0, 1]))


def exposure_stats(economic, quotes):
    holdings = {}
    fills = {}
    for fill in economic['fills']:
        fills.setdefault(fill['date'], []).append(fill)
    hh, maxw, gross = [], [], []
    for row in economic['nav']:
        day = row['date']
        for fill in fills.get(day, []):
            symbol = fill['symbol']
            holdings[symbol] = holdings.get(symbol, 0)+fill['quantity']
        weights = [quantity*float(quotes[s][day]['close'])/float(row['nav']) for s, quantity in holdings.items() if quantity]
        hh.append(sum(w*w for w in weights))
        maxw.append(max(weights, default=0))
        gross.append(sum(weights))
    return dict(average_hhi=float(np.mean(hh)), average_max_weight=float(np.mean(maxw)),
                maximum_drifted_weight=max(maxw), average_gross=float(np.mean(gross)))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    progress = json.loads((root/'progress.json').read_text())
    if not progress['complete']:
        raise ValueError('All preregistered trials must finish before analysis')
    protocol = json.loads((root/'protocol.json').read_text())
    for name, digest in json.loads((root/'snapshot'/'manifest.json').read_text()).items():
        if sha256(root/'snapshot'/name) != digest:
            raise ValueError('Frozen research snapshot changed: '+name)
    economies, summary = {}, {}
    quotes = json.loads((root/'datasets'/'sota'/'quotes.json').read_text())
    for name in progress['passed']:
        output = root/'runs'/name
        receipt = json.loads((output/'run.json').read_text())
        verify_bundle(root/'datasets'/name)
        for relative, digest in receipt['artifacts'].items():
            if sha256(output/relative) != digest:
                raise ValueError(f'Run artifact changed: {name}/{relative}')
        parity = json.loads((output/'parity.json').read_text())
        if receipt['status'] != 'succeeded' or not parity['passed']:
            raise ValueError('Native run did not pass: '+name)
        economic = json.loads((output/'economic.json').read_text())
        economies[name] = economic
        summary[name] = dict(windows={key: metrics(economic, *bounds) for key, bounds in WINDOWS.items()},
            exposure=exposure_stats(economic, quotes), parity=parity,
            engine_seconds=receipt['lean_wall_seconds'])
    baseline = economies['sota']
    dates = [r['date'] for r in baseline['nav']]
    if any([r['date'] for r in e['nav']] != dates for e in economies.values()):
        raise ValueError('Native trial sessions differ; paired comparisons require identical dates')
    names = [name for name, cfg in protocol['trials'].items() if cfg is not None]
    difference = np.column_stack([return_vector(economies[n]['nav'])-return_vector(baseline['nav']) for n in names])
    bootstrap = {}
    for window in ('full', 'reused_post2023'):
        a, b = WINDOWS[window]
        mask = np.array([a <= d <= b for d in dates])
        bootstrap[window] = block_audit(difference[mask], names)
    for name, result in summary.items():
        base = summary['sota__'+name.split('__')[1]] if '__' in name else summary['sota']
        result['vs_sota'] = {w: dict(cagr_delta=m['cagr']-base['windows'][w]['cagr'],
            sharpe_delta=m['sharpe']-base['windows'][w]['sharpe'],
            relative_wealth=(1+m['total_return'])/(1+base['windows'][w]['total_return'])-1,
            drawdown_delta=m['max_drawdown']-base['windows'][w]['max_drawdown'])
            for w, m in result['windows'].items() if m is not None}
    bars = json.loads((root/'snapshot'/'bars.json').read_text())
    fx = json.loads((root/'snapshot'/'fx.json').read_text())
    external = json.loads((root/'snapshot'/'external.json').read_text())
    benchmarks = {}
    for symbol, rows in {'SPY': bars['SPY'], **external}.items():
        benchmarks[symbol] = {}
        for window, bounds in WINDOWS.items():
            selected = [d for d in dates if bounds[0] <= d <= bounds[1]]
            run = price_benchmark(rows, fx, selected)
            benchmarks[symbol][window] = metrics(run, *bounds) if run is not None else None
    diagnostics = signal_diagnostics(root, bars, economies)
    primary = summary[protocol['primary']]
    rules = {
        'positive_full_and_post2023_sharpe': all(primary['vs_sota'][w]['sharpe_delta'] > 0 for w in ('full', 'reused_post2023')),
        'positive_full_and_post2023_relative_wealth': all(primary['vs_sota'][w]['relative_wealth'] > 0 for w in ('full', 'reused_post2023')),
        'positive_post2023_before_extension': primary['vs_sota']['post2023_to_old_end']['relative_wealth'] > 0,
        'positive_matched_cost_and_delay_full_relative_wealth': all(summary[protocol['primary']+'__'+s]['vs_sota']['full']['relative_wealth'] > 0 for s in protocol['stresses']),
        'majority_of_neighbors_positive_full_and_post2023': sum(all(summary[n]['vs_sota'][w]['relative_wealth'] > 0 for w in ('full', 'reused_post2023')) for n in ('threshold_025', 'threshold_100', 'lag_5', 'lag_20')) >= 3,
    }
    result = dict(protocol=protocol, data_audit=json.loads((root/'data_audit.json').read_text()), runs=summary,
                  bootstrap=bootstrap, external_benchmarks=benchmarks, signal_diagnostics=diagnostics,
                  retention_checks=rules, decision='observe' if all(rules.values()) else 'reject_current_proxy_overlay',
                  promotion_eligible=False)
    write_json(root/'analysis.json', result)
    lines = ['# Flow/concentration acceleration — native LEAN research', '',
             f'Period: {dates[0]} to {dates[-1]} ({len(dates):,} sessions). Decision: **{result["decision"]}**.', '',
             'Every reported strategy run used native LEAN fills and passed the unchanged Python parity tolerances. '
             'Data is uncertified legacy adjusted history; fitted/reused intervals are not untouched out-of-sample tests. '
             'Prices times volume are activity proxies, not observed net inflows.', '',
             '## All predeclared trials', '',
             '| Trial | CAGR | Sharpe (Rf=0) | Max DD | Δ CAGR vs SOTA | Post-2023 Δ CAGR | Post-2023 Δ Sharpe | Annual traded NAV | Mean cash |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for name in protocol['trials']:
        r = summary[name]
        m, delta, post = r['windows']['full'], r['vs_sota']['full'], r['vs_sota']['reused_post2023']
        lines.append(f'| {name} | {m["cagr"]:.2%} | {m["sharpe"]:.3f} | {m["max_drawdown"]:.2%} | '
                     f'{delta["cagr_delta"]:+.2%} | {post["cagr_delta"]:+.2%} | {post["sharpe_delta"]:+.3f} | '
                     f'{m["annual_traded_notional_over_nav"]:.2f}x | {m["average_cash"]:.1%} |')
    lines += ['', '## Primary versus SOTA by period', '',
              '| Window | SOTA CAGR | Primary CAGR | SOTA Sharpe | Primary Sharpe | SOTA max DD | Primary max DD | Relative terminal wealth |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for window in WINDOWS:
        a, b = summary['sota']['windows'][window], primary['windows'][window]
        lines.append(f'| {window} | {a["cagr"]:.2%} | {b["cagr"]:.2%} | {a["sharpe"]:.3f} | {b["sharpe"]:.3f} | '
                     f'{a["max_drawdown"]:.2%} | {b["max_drawdown"]:.2%} | {primary["vs_sota"][window]["relative_wealth"]:+.2%} |')
    lines += ['', 'Partial-year annualization is descriptive only; see total returns/session counts in analysis.json.', '',
              '## Matched implementation stresses', '',
              '| Stress | SOTA CAGR | Primary CAGR | SOTA Sharpe | Primary Sharpe | Relative terminal wealth |',
              '| --- | ---: | ---: | ---: | ---: | ---: |']
    for stress in protocol['stresses']:
        a, b = summary['sota__'+stress]['windows']['full'], summary[protocol['primary']+'__'+stress]['windows']['full']
        delta = summary[protocol['primary']+'__'+stress]['vs_sota']['full']['relative_wealth']
        lines.append(f'| {stress} | {a["cagr"]:.2%} | {b["cagr"]:.2%} | {a["sharpe"]:.3f} | {b["sharpe"]:.3f} | {delta:+.2%} |')
    lines += ['', '## Uncertainty and multiple testing', '',
              'Paired 63-session circular blocks, 2,000 replicates, seed 20260926. '
              'Intervals describe annualized arithmetic daily excess return, not CAGR. '
              'One-sided max-t family adjustment includes every one of the 11 challenger trials. '
              'It cannot undo prior SOTA selection or nonstationarity.', '',
              '| Window | Trial | Annual arithmetic excess | 95% interval | Family-adjusted p |',
              '| --- | --- | ---: | ---: | ---: |']
    for window, audit in bootstrap.items():
        for name, row in audit['trials'].items():
            lines.append(f'| {window} | {name} | {row["annual_arithmetic_excess"]:+.2%} | '
                         f'[{row["ci95"][0]:+.2%}, {row["ci95"][1]:+.2%}] | {row["max_t_family_adjusted_p"]:.3f} |')
    lines += ['', '## External buy-and-hold context', '',
              'These are separate Python buy-and-hold calculations using the same opening/closing CNH marks, '
              'whole units and 5bps entry cost; not additional LEAN runs. No missing-price fill is allowed. '
              'URTH has invalid early observations and is unavailable for affected windows.', '',
              '| Benchmark/window | CAGR | Sharpe | Max DD |', '| --- | ---: | ---: | ---: |']
    for symbol, windows in benchmarks.items():
        for window in ('full', 'reused_post2023', 'post_artifact_extension'):
            m = windows[window]
            lines.append(f'| {symbol}/{window} | '+(f'{m["cagr"]:.2%} | {m["sharpe"]:.3f} | {m["max_drawdown"]:.2%} |' if m else 'Unavailable | Unavailable | Unavailable |'))
    lines += ['', '## Predeclared retention checks', '', *[f'- {name}: {passed}' for name, passed in rules.items()], '',
              'No strategy was promoted and no paper/live trading configuration was changed.', '',
              'Replay: frozen protocol.json, snapshot/manifest.json, datasets/*/manifest.json, '
              'runs/*/{economic,parity,run}.json. Full metrics/exposures in analysis.json; asset-month features in signal_diagnostics.json.', '']
    (root/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    print(json.dumps(dict(decision=result['decision'], checks=rules, primary=primary['vs_sota'],
                          primary_bootstrap=bootstrap['full']['trials'][protocol['primary']]), indent=2))


if __name__ == '__main__':
    main()
