"""Compare native constituent-overlay LEAN runs with SOTA and archive the evidence."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime
import json
from pathlib import Path
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, verify_bundle, write_json
from systematic_trading.lean.registry import register_run
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.analytics_projection import observation
from systematic_trading.research.constituent_signals import SIGNALS, ConstituentOverlaySpec, selected_score
from systematic_trading.research.sector_hhi import correlations
from systematic_trading.storage.postgres import PostgresStore
from analyze_flow_concentration_research import metrics, return_vector, block_audit, price_benchmark


def information_ratio(active):
    volatility = float(np.std(active, ddof=1)*np.sqrt(252))
    annual = float(np.mean(active)*252)
    return dict(annual_arithmetic_active_return=annual, tracking_error=volatility,
                information_ratio=annual/volatility if volatility > 1e-12 else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    protocol = json.loads((root/'protocol.json').read_text())
    progress = json.loads((root/'progress.json').read_text())
    if not progress['complete']:
        raise ValueError('Complete every declared trial before analysis')
    for name, expected in json.loads((root/'input_manifest.json').read_text()).items():
        if sha256(root/name) != expected:
            raise ValueError('Frozen input changed: '+name)
    economies = {}
    for name in progress['passed']:
        verify_bundle(root/'datasets'/name)
        receipt = json.loads((root/'runs'/name/'run.json').read_text())
        if receipt['status'] != 'succeeded' or receipt['economic_sha256'] != progress['passed'][name]:
            raise ValueError('Invalid receipt')
        if sha256(root/'runs'/name/'economic.json') != receipt['artifacts']['economic.json']:
            raise ValueError('Changed LEAN output')
        economies[name] = json.loads((root/'runs'/name/'economic.json').read_text())
    days = np.array([r['date'] for r in economies['sota']['nav']])
    vectors = {n: return_vector(e['nav']) for n, e in economies.items()}
    for e in economies.values():
        if [r['date'] for r in e['nav']] != list(days):
            raise ValueError('Mismatched comparison sessions')
    windows = dict(full=(protocol['start'], protocol['end']), pre2023=(protocol['start'], '2022-12-31'),
                   reused_post2023=('2023-01-01', protocol['end']), recent2025=('2025-01-01', protocol['end']),
                   **{str(y): (f'{y}-01-01', f'{y}-12-31') for y in range(2019, 2027)})
    summary = {}
    for name, e in economies.items():
        base = 'sota'+('__'+name.split('__')[1] if '__' in name else '')
        summary[name] = {}
        for label, (start, end) in windows.items():
            mask = (days >= start) & (days <= end)
            m = metrics(e, start, end)
            b = metrics(economies[base], start, end)
            summary[name][label] = dict(**m, **information_ratio((vectors[name]-vectors[base])[mask]),
                cagr_delta=m['cagr']-b['cagr'], sharpe_delta=m['sharpe']-b['sharpe'], comparator=base)
    candidates = [n for n, cfg in protocol['trials'].items() if cfg is not None]
    matrix = np.column_stack([vectors[n]-vectors['sota'] for n in candidates])
    uncertainty = {str(block): block_audit(matrix, candidates, block=block) for block in (63, 126)}
    uncertainty['reused_post2023'] = {str(block): block_audit(matrix[days >= '2023-01-01'], candidates, block=block)
                                    for block in (63, 126)}
    uncertainty['primary_vs_price_control'] = information_ratio(vectors['composite']-vectors['price_control'])
    features = json.loads((root/'features.json').read_text())
    decisions = economies['sota']['decisions']
    activity = {}
    for name, cfg in protocol['trials'].items():
        if cfg is None:
            continue
        spec = ConstituentOverlaySpec(**cfg)
        available = selected = nonzero = changed = 0
        entries = []
        for execution, row in decisions.items():
            feature_row = features.get(str(spec.holdings_lag_days), {}).get(row['known_through'])
            qualifies = (feature_row is not None and feature_row['scores'] is not None
                and feature_row['value_coverage'] >= spec.min_value_coverage and feature_row['name_coverage'] >= spec.min_name_coverage)
            score = selected_score(features, datetime.fromisoformat(row['signal_session']).date(), row['known_through'], spec)
            before = {t['symbol']: float(t['target_weight']) for t in row['targets']}
            after = {t['symbol']: float(t['target_weight']) for t in economies[name]['decisions'][execution]['targets']}
            available += int(qualifies)
            selected += int(qualifies and before.get('SPY', 0) > 0)
            nonzero += int(score != 0)
            changed += int(any(abs(after[s]-w) > 1e-12 for s, w in before.items()))
            entries.append(dict(date=execution, known_through=row['known_through'], available=qualifies,
                signal=score, spy_before=before.get('SPY', 0), spy_after=after.get('SPY', 0)))
        activity[name] = dict(decisions=len(decisions), available=available, available_and_spy_selected=selected,
                              nonzero_signal=nonzero, changed_targets=changed, records=entries)
    # Descriptive ICs use qualified feature dates and future observed SPY adjusted returns.
    stock_bars = json.loads((Path(protocol['etf_snapshot'])/'bars.json').read_text())['SPY']
    px = np.array([float(r['close']) for r in stock_bars])
    index = {r['trade_date']: i for i, r in enumerate(stock_bars)}
    ic = {}
    raw_keys = dict(concentration='concentration_z', breadth='breadth', breadth_change='breadth_change',
                    participation='participation', signed_activity='signed_activity')
    for signal in (*SIGNALS, 'composite', 'price_control'):
        ic[signal] = {}
        for h in (20, 60, 120):
            x, y = [], []
            for day, row in features['45'].items():
                j = index.get(day)
                if j is None or j+h >= len(px) or day < protocol['start'] or row['scores'] is None:
                    continue
                if row['value_coverage'] < .95 or row['name_coverage'] < .70:
                    continue
                x.append(row['values'][raw_keys[signal]] if signal in raw_keys else row['scores'][signal])
                y.append(px[j+h]/px[j]-1)
            ic[signal][str(h)] = correlations(np.array(x), np.array(y))
    fx = json.loads((Path(protocol['etf_snapshot'])/'fx.json').read_text())
    spy_hold = price_benchmark(stock_bars, fx, list(days))
    context = metrics(spy_hold, protocol['start'], protocol['end'])
    write_json(root/'summary.json', summary)
    write_json(root/'uncertainty.json', uncertainty)
    write_json(root/'signal_activity.json', activity)
    write_json(root/'information_coefficients.json', ic)
    write_json(root/'spy_buy_hold_context.json', context)
    with (root/'daily_returns.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['date', *vectors])
        writer.writerows([d, *[v[i] for v in vectors.values()]] for i, d in enumerate(days))
    sys.path.insert(0, 'D:/systematic_trading_data/lean/research/plot_dependencies')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'axes.spines.top': False, 'axes.spines.right': False})
    stamps = [datetime.fromisoformat(d) for d in days]
    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    for name, color in [('sota', '#334155'), ('composite', '#0891b2'), ('concentration', '#d97706')]:
        axes[0, 0].plot(stamps, np.cumprod(1+vectors[name]), label=name, color=color, lw=1.4)
    axes[0, 0].set_title('Net wealth in CNH (initial = 1)')
    axes[0, 0].legend(frameon=False)
    axes[0, 0].axvspan(stamps[0], datetime(2023, 1, 17), color='#e2e8f0', alpha=.35, zorder=-1)
    for name in ('composite', 'concentration', 'breadth', 'breadth_change', 'participation', 'signed_activity', 'price_control'):
        relative = np.cumprod(1+vectors[name])/np.cumprod(1+vectors['sota'])-1
        axes[0, 1].plot(stamps, relative, label=name, lw=1.1)
    axes[0, 1].axhline(0, color='#94a3b8', lw=.7)
    axes[0, 1].set_title('Relative wealth versus unchanged SOTA')
    axes[0, 1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0, 1].legend(fontsize=8, ncol=2, frameon=False)
    axes[0, 1].axvspan(stamps[0], datetime(2023, 1, 17), color='#e2e8f0', alpha=.35, zorder=-1)
    vals = [summary[n]['full']['information_ratio'] or 0 for n in candidates]
    axes[1, 0].barh(candidates, vals, color=['#0891b2' if v > 0 else '#b45309' for v in vals])
    axes[1, 0].axvline(0, color='#64748b', lw=.7)
    axes[1, 0].set_title('Information ratio of daily active returns')
    cov = features['45']
    cd = [datetime.fromisoformat(d) for d in cov]
    axes[1, 1].plot(cd, [r['value_coverage'] for r in cov.values()], label='Holding value covered')
    axes[1, 1].plot(cd, [r['name_coverage'] for r in cov.values()], label='Names covered')
    axes[1, 1].axhline(.95, ls='--', color='#64748b', lw=.8)
    axes[1, 1].axhline(.70, ls=':', color='#64748b', lw=.8)
    axes[1, 1].set_title('Complete 211-session stock-history coverage')
    axes[1, 1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1, 1].legend(frameon=False)
    fig.suptitle('Do U.S. constituent signals improve the current ETF strategy?', x=.04, ha='left', fontsize=20, weight='bold')
    fig.text(.04, .935, '2019-10-01 to 2026-09-24 | 95%/70% coverage first passes Jan 2023 | Native LEAN, 5bp fees | Uncertified public-data proxy', fontsize=10, color='#475569')
    fig.tight_layout(rect=(.02, .02, 1, .915), w_pad=4, h_pad=3)
    fig.savefig(root/'results.png', dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 7))
    matrix_ic = np.array([[ic[s][str(h)]['spearman'] if ic[s][str(h)]['spearman'] is not None else np.nan for h in (20, 60, 120)] for s in ic])
    im = ax.imshow(matrix_ic, cmap='RdBu', vmin=-.55, vmax=.55)
    ax.set_xticks(range(3), ['20', '60', '120'])
    ax.set_xlabel('Forward return horizon (trading sessions)', labelpad=10)
    ax.set_yticks(range(len(ic)), list(ic))
    for i, signal in enumerate(ic):
        for j, h in enumerate((20, 60, 120)):
            ax.text(j, i, f'{matrix_ic[i,j]:+.3f}\nn={ic[signal][str(h)]["n"]}', ha='center', va='center', fontsize=11)
    ax.set_title('Qualified stock signals vs future SPY return\nDescriptive Spearman IC; overlapping labels', pad=18)
    fig.colorbar(im, ax=ax, shrink=.7)
    fig.tight_layout()
    fig.savefig(root/'ic.png', dpi=160)
    plt.close(fig)
    lines = ['# Constituent signals in the current SOTA ETF strategy', '',
        'Research-only public-data pilot. Dated ITOT equity cohorts are a US equity proxy for SPY, not exact SPY holdings. Historical prices, identities and availability are uncertified. No paper/live promotion.', '',
        f"Native LEAN, {protocol['start']}–{protocol['end']}; CNH accounting, zero-hurdle Sharpe, 5bp fees. IR is annualized mean daily return difference from matched SOTA divided by its tracking error. All runs pass original parity tolerances.", '',
        '| Trial | CAGR | Sharpe | IR vs SOTA | Δ CAGR (pp) | Max drawdown | Changed monthly targets |',
        '| --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for n in protocol['trials']:
        m = summary[n]['full']
        ir = f"{m['information_ratio']:.3f}" if m['information_ratio'] is not None else '—'
        lines.append(f"| {n} | {m['cagr']:.2%} | {m['sharpe']:.3f} | {ir} | {m['cagr_delta']*100:+.3f} | {m['max_drawdown']:.2%} | {activity[n]['changed_targets'] if n in activity else '—'} |")
    lines += ['', 'The fixed composite is the primary. Individual winners are exploratory. The base coverage rule first passes on January 17, 2023: pre-2023 overlays are neutral, so this does not test constituent signals in COVID or the 2022 selloff. Reused post-2023 data is not an untouched holdout. Coverage-neutral periods remain in full-period metrics; see signal_activity.json for available decisions and actual changes. Bootstrap resamples paired daily active returns in contiguous 63/126-session circular blocks across all ten challengers, for the full period and separately post-2023.', '',
        '## Primary and robustness', '', '| Window / scenario | SOTA CAGR / Sharpe | Composite CAGR / Sharpe | Composite IR |', '| --- | --- | --- | ---: |']
    for window in ('full', 'pre2023', 'reused_post2023', 'recent2025'):
        b, m = summary['sota'][window], summary['composite'][window]
        lines.append(f"| {window} | {b['cagr']:.2%} / {b['sharpe']:.3f} | {m['cagr']:.2%} / {m['sharpe']:.3f} | {m['information_ratio'] if m['information_ratio'] is None else round(m['information_ratio'], 3)} |")
    for stress in protocol['stresses']:
        b, m = summary['sota__'+stress]['full'], summary['composite__'+stress]['full']
        lines.append(f"| {stress} | {b['cagr']:.2%} / {b['sharpe']:.3f} | {m['cagr']:.2%} / {m['sharpe']:.3f} | {m['information_ratio']:.3f} |")
    lines += ['', '## Inference', '', '```json', json.dumps({k: uncertainty[k]['trials']['composite'] for k in ('63', '126')}, indent=2), '```', '',
        'Volume measures trading activity, not net capital inflow; HHI acceleration is not a Hurst exponent. Missing snapshot value does not bound missing turnover. Complete-case selection reduces cohort changes inside the feature window but cannot recover delisted securities. The 90%-value trial is a declared coverage sensitivity, not certified evidence. Changing cohorts can still change successive decision scores; each individual derivative uses a fixed cohort.', '',
        'Files: protocol.json (formulas and limits), input_manifest.json (frozen features/code), clickhouse_receipt.json (archive verification), summary.json (period metrics/costs/turnover), uncertainty.json, signal_activity.json, information_coefficients.json, daily_returns.csv and all datasets/runs. SPY buy-and-hold context is a separate friction-matched calculation, not a native strategy run.', '']
    (root/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    shutil.copyfile(__file__, root/'analysis_source.py')
    files = ['summary.json', 'uncertainty.json', 'signal_activity.json', 'information_coefficients.json',
             'spy_buy_hold_context.json', 'daily_returns.csv', 'results.png', 'ic.png', 'report.md', 'analysis_source.py']
    write_json(root/'analysis_manifest.json', {n: sha256(root/n) for n in files})
    store = AnalyticsStore.from_settings(AppSettings())
    observations = [observation(n+'/'+w, 'research_constituent_backtest', n, row) for n, windows_out in summary.items() for w, row in windows_out.items()]
    docs = [dict(point_key=n, media_type='text/markdown' if n.endswith('.md') else 'application/json', payload=(root/n).read_text(encoding='utf-8'))
            for n in ('report.md', 'summary.json', 'uncertainty.json', 'signal_activity.json', 'information_coefficients.json', 'analysis_manifest.json')]
    version = digest(encode(json.loads((root/'analysis_manifest.json').read_text())))
    changed = store.publish('constituent-research/'+root.name+'/results', version, observations, docs,
                            provenance=dict(research_only=True, historical_certification=False, all_lean_parity_passed=True))
    write_json(root/'results_clickhouse_receipt.json', dict(version=version, changed=changed, rows=len(observations), documents=len(docs)))
    registry = PostgresStore.from_settings(AppSettings())
    write_json(root/'registry_receipt.json', {n: register_run(registry, root/'runs'/n) for n in economies})
    print((root/'report.md').read_text(encoding='utf-8'), flush=True)


if __name__ == '__main__':
    main()
