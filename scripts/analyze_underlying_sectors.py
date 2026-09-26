"""Aggregate dated underlying-stock cohorts and plot coverage-qualified HHI diagnostics."""
from __future__ import annotations

import argparse
import csv
from datetime import UTC, date, datetime, timedelta
from difflib import SequenceMatcher
from functools import lru_cache
import html
import json
from pathlib import Path
import re
import shutil
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.live.trading_calendar import is_us_trading_day
from systematic_trading.research.sector_hhi import correlations, correlation_block_interval
from systematic_trading.research.underlying_sectors import aggregate_cohort, horizon_returns, hhi_features, scalar_features

HORIZONS = (20, 60, 120)
FEATURES = ('HHI', 'first_derivative', 'second_derivative')
LEGAL = {'INC', 'CORP', 'CORPORATION', 'CO', 'COMPANY', 'LTD', 'PLC', 'CLASS', 'HOLDINGS', 'HOLDING', 'GROUP', 'COMMON', 'STOCK', 'COM', 'THE'}


@lru_cache(maxsize=None)
def compatible_name(historical, current, ticker):
    if ticker in ('FB', 'ANTM', 'BK', 'MMC', 'HEIA', 'SQ', 'ABC', 'BLL'):
        return True  # Verified issuer-announced renames recorded in the report.
    def clean(s):
        return ' '.join(w for w in re.findall(r'[A-Z0-9]+', (s or '').upper()) if w not in LEGAL)
    a, b = clean(historical), clean(current)
    if not a or not b:
        return False
    tokens = set(a.split()) & set(b.split())
    return bool(any(len(t) >= 3 for t in tokens)) or SequenceMatcher(None, a, b).ratio() >= .55


def load_arrays(root, snapshots, dates):
    symbols = sorted({r['yahoo'] for s in snapshots for r in s['rows']})
    lookup, day_index = {s: i for i, s in enumerate(symbols)}, {d: i for i, d in enumerate(dates)}
    shape = (len(dates), len(symbols))
    close, volume, adjusted = [np.full(shape, np.nan) for _ in range(3)]
    metadata, issues = {}, []
    for symbol in symbols:
        item = json.loads((root/'bars_metadata'/f'{symbol}.json').read_text())
        metadata[symbol] = item
        if item['status'] != 'ok':
            continue
        raw = json.loads((root/'bars_raw'/f'{symbol}.json').read_text())['chart']['result'][0]
        quotes = raw['indicators']['quote'][0]
        adj = raw['indicators'].get('adjclose', [{}])[0].get('adjclose', [])
        col = lookup[symbol]
        seen = set()
        for i, stamp in enumerate(raw.get('timestamp', [])):
            day = datetime.fromtimestamp(stamp, UTC).date().isoformat()
            if day not in day_index:
                continue
            if day in seen:
                raise ValueError('Duplicate stock/date: '+symbol+' '+day)
            seen.add(day)
            c, v, a = quotes['close'][i], quotes['volume'][i], adj[i] if i < len(adj) else None
            row = day_index[day]
            if c is not None and np.isfinite(c) and c > 0:
                close[row, col] = c
            if v is not None and np.isfinite(v) and v >= 0:
                volume[row, col] = v
            if a is not None and np.isfinite(a) and a > 0:
                adjusted[row, col] = a
            if not np.isfinite([close[row, col], volume[row, col], adjusted[row, col]]).all():
                issues.append(dict(symbol=symbol, date=day, close=c, volume=v, adjusted=a))
    write_json(root/'bar_quality_issues.json', issues)
    return lookup, metadata, close, volume, adjusted


def build(root, protocol, snapshots):
    first, last = date(2018, 10, 1), date.fromisoformat(protocol['end'])
    dates = np.array([(first+timedelta(days=i)).isoformat() for i in range((last-first).days+1) if is_us_trading_day(first+timedelta(days=i))])
    sectors = protocol['sectors']
    lookup, metadata, close, volume, adjusted = load_arrays(root, snapshots, dates)
    n, m = len(dates), len(sectors)
    out = {k: np.full((n, m), np.nan) for k in ('shares', 'dollars', 'within_hhi', 'value_coverage', 'name_coverage',
        'return_value_coverage', 'return_name_coverage', 'weighted_return', 'equal_return')}
    feat = {f'{measure}_{mode}': np.full((n, 3), np.nan) for measure in ('dollars', 'shares') for mode in ('raw', 'smoothed')}
    within = {s: np.full((n, 3), np.nan) for s in sectors}
    counts = np.zeros((n, m), int)
    snapshot_ids = np.full(n, '', dtype='<U10')
    market = np.full(n, np.nan)
    equal_market = np.full(n, np.nan)
    market_coverage = np.full(n, np.nan)
    feature_gate = np.full((n, 3), False)
    exclusions = []
    activations = [s['assumed_available'] for s in snapshots]
    for i, snapshot in enumerate(snapshots):
        active = (dates >= activations[i]) & (dates < (activations[i+1] if i+1 < len(snapshots) else '9999-12-31'))
        if not active.any():
            continue
        merged = {}
        for row_index, row in enumerate(snapshot['rows']):
            identity = (row['yahoo'], row['sector']) if row['yahoo'] != '-' else f'unknown-identity-{row_index}'
            if identity in merged:
                old = merged[identity]
                old['market_value'] += row['market_value']
                old['weight_pct'] += row['weight_pct']
            else:
                merged[identity] = row.copy()
        rows = list(merged.values())
        ids = [lookup[r['yahoo']] for r in rows]
        sec = np.array([sectors.index(r['sector']) for r in rows])
        weights = np.array([r['market_value'] for r in rows])
        c, v, a = close[:, ids].copy(), volume[:, ids].copy(), adjusted[:, ids].copy()
        # A symbol alone is not a security identifier. Exclude obvious mismatched names.
        accepted = {}
        for j, row in enumerate(rows):
            meta = metadata[row['yahoo']]
            if meta['status'] == 'ok' and not compatible_name(row['name'], meta.get('name'), row['ticker']):
                c[:, j], v[:, j], a[:, j] = np.nan, np.nan, np.nan
                exclusions.append(dict(snapshot=snapshot['as_of'], **row, vendor_name=meta.get('name'), reason='incompatible_name'))
            elif meta['status'] == 'ok':
                accepted.setdefault(row['yahoo'], []).append(j)
        for symbol, columns in accepted.items():
            if len(columns) > 1:
                c[:, columns], v[:, columns], a[:, columns] = np.nan, np.nan, np.nan
                for j in columns:
                    exclusions.append(dict(snapshot=snapshot['as_of'], **rows[j], vendor_name=metadata[symbol].get('name'), reason='ambiguous_multiple_sectors'))
        agg = aggregate_cohort(c, v, a, sec, weights)
        cohort_gate = ((agg['value_coverage'] >= .95) & (agg['name_coverage'] >= .70)).all(axis=1)
        for gate_index, lookback in enumerate((0, 2, 70)):
            pass_window = np.zeros(n, bool)
            failed = np.r_[0, np.cumsum(~cohort_gate)]
            pass_window[lookback:] = (failed[lookback+1:]-failed[:n-lookback]) == 0
            feature_gate[active, gate_index] = pass_window[active]
        for k in out:
            out[k][active] = agg[k][active]
        for s in range(m):
            counts[active, s] = (sec == s).sum()
        snapshot_ids[active] = snapshot['as_of']
        for measure in ('dollars', 'shares'):
            for mode in ('raw', 'smoothed'):
                # Recompute prior feature values using today's dated cohort before differencing.
                feat[f'{measure}_{mode}'][active] = hhi_features(agg[measure], smoothing=mode)[active]
        for j, s in enumerate(sectors):
            within[s][active] = scalar_features(agg['within_hhi'][:, j], smoothing='smoothed')[active]
        broad = aggregate_cohort(c, v, a, np.zeros(len(rows), int), weights, sector_count=1)
        market[active] = broad['weighted_return'][active, 0]
        equal_market[active] = broad['equal_return'][active, 0]
        market_coverage[active] = broad['return_value_coverage'][active, 0]
    write_json(root/'identity_exclusions.json', exclusions)
    # Coverage is separate from the observed sums; never replace missing stock data by invented bars.
    gate = (out['value_coverage'] >= .95) & (out['name_coverage'] >= .70)
    ret_gate = (out['return_value_coverage'] >= .95) & (out['return_name_coverage'] >= .70)
    returns = {s: out['weighted_return'][:, j] for j, s in enumerate(sectors)}
    returns['Underlying_market'] = market
    returns['Equal_weight_stocks'] = equal_market
    gates = {s: ret_gate[:, j] for j, s in enumerate(sectors)}
    gates['Underlying_market'] = (market_coverage >= .95) & ret_gate.all(axis=1)
    gates['Equal_weight_stocks'] = gates['Underlying_market']
    labels, qualified = {}, {}
    for target, daily in returns.items():
        labels[target] = np.column_stack([horizon_returns(daily, h) for h in HORIZONS])
        qualified[target] = np.column_stack([horizon_returns(np.where(gates[target], daily, np.nan), h) for h in HORIZONS])
    return dates, sectors, out, feat, within, labels, qualified, gate, feature_gate, counts, snapshot_ids, market_coverage


def statistics(x, y, dates):
    result = {}
    for i, name in enumerate(FEATURES):
        result[name] = {}
        for j, h in enumerate(HORIZONS):
            row = {'full': correlations(x[:, i], y[:, j])}
            for key, mask in [('pre2023', dates < '2023-01-01'), ('post2023', dates >= '2023-01-01')]:
                row[key] = correlations(x[:, i][mask], y[:, j][mask])
            row['block_ci95'] = correlation_block_interval(x[:, i], y[:, j])
            result[name][str(h)] = row
    return result


def scatter(plt, root, dates, x, y, title, subtitle, path, stats):
    fig, axes = plt.subplots(3, 3, figsize=(15, 11.5), sharey='col')
    labels = ['HHI level', 'First derivative (HHI × 10³ / session)', 'Second derivative (HHI × 10³ / session²)']
    post = dates >= '2023-01-01'
    for i, factor in enumerate((1, 1000, 1000)):
        for j, h in enumerate(HORIZONS):
            ax = axes[i, j]
            a, b = x[:, i]*factor, y[:, j]*100
            ax.scatter(a[~post], b[~post], c='#64748b', s=9, alpha=.3, edgecolors='none')
            ax.scatter(a[post], b[post], c='#0891b2', s=9, alpha=.3, edgecolors='none')
            if len(a) >= 20 and np.std(a) > 0:
                xx = np.linspace(min(a), max(a), 100)
                ax.plot(xx, np.polyval(np.polyfit(a, b, 1), xx), c='#1e293b', lw=1.3)
                bins = np.array_split(np.argsort(a), 5)
                ax.plot([np.mean(a[k]) for k in bins], [np.mean(b[k]) for k in bins], c='#d97706', marker='o', ms=4)
            s = stats[FEATURES[i]][str(h)]['full']
            caption = f"r = {s['pearson']:+.3f}   ρ = {s['spearman']:+.3f}\nn = {s['n']:,}" if s['pearson'] is not None else 'Insufficient data'
            ax.text(.03, .97, caption, transform=ax.transAxes, va='top', fontsize=10, bbox=dict(facecolor='white', edgecolor='none', alpha=.9))
            ax.axhline(0, c='#94a3b8', lw=.7)
            if i:
                ax.axvline(0, c='#cbd5e1', lw=.7)
            if i == 0:
                ax.set_title(f'Next {h} trading sessions', fontsize=12)
            if j == 0:
                ax.set_ylabel('Constituent-aggregate return (%)')
            ax.set_xlabel(labels[i], fontsize=9)
            ax.grid(alpha=.15)
    fig.suptitle(title, x=.07, y=.975, ha='left', fontsize=18, fontweight='bold')
    fig.text(.07, .938, subtitle, fontsize=11, color='#475569')
    period = f'{dates[0]}–{dates[-1]}' if len(dates) else 'No eligible dates'
    fig.text(.07, .909, f'{period} · 45-day-lagged monthly holdings · Same dates across panels · Observed-stock subset', fontsize=10, color='#475569')
    fig.text(.07, .037, 'Gray: before 2023 · Teal: 2023 onward · Black: linear fit · Orange: five equal-count mean returns', fontsize=10, color='#475569')
    fig.text(.07, .016, 'Public-data pilot: missing/delisted histories and unverified vintages. Overlapping outcomes; no whole-market or trading-edge conclusion.', fontsize=9, color='#64748b')
    fig.subplots_adjust(left=.07, right=.975, top=.86, bottom=.10, hspace=.32, wspace=.18)
    fig.savefig(root/'plots'/path, dpi=145)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--plot-deps', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    for name, digest in json.loads((root/'data_manifest.json').read_text()).items():
        if sha256(root/name) != digest:
            raise ValueError('Frozen source changed: '+name)
    protocol = json.loads((root/'protocol.json').read_text())
    snapshots = [json.loads(p.read_text()) for p in sorted((root/'holdings').glob('*.json'))]
    alias_path = root/'symbol_aliases.json'
    aliases = json.loads(alias_path.read_text())['aliases'] if alias_path.exists() else {}
    for snapshot in snapshots:
        for row in snapshot['rows']:
            if row['ticker'] in aliases:
                row['original_yahoo'] = row['yahoo']
                row['yahoo'] = aliases[row['ticker']]
    dates, sectors, data, feat, within, labels, qualified, gate, feature_gate, counts, snapshot_ids, market_coverage = build(root, protocol, snapshots)
    sys.path.insert(0, str(args.plot_deps))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.ticker import PercentFormatter
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.spines.top': False,
        'axes.spines.right': False, 'axes.facecolor': '#f8fafc', 'figure.facecolor': '#f8fafc', 'text.color': '#0f172a'})
    (root/'plots').mkdir(exist_ok=True)
    show = dates >= protocol['signal_start']
    result, gallery = {}, []
    for measure in ('dollars', 'shares'):
        for mode in ('raw', 'smoothed'):
            x = feat[f'{measure}_{mode}']
            for quality in ('observed_subset', 'coverage_qualified'):
                # Primary market/basket plots plus underlying sector return grids for dollar activity.
                targets = list(labels) if measure == 'dollars' and mode == 'smoothed' else ['Underlying_market']
                for target in targets:
                    y = labels[target] if quality == 'observed_subset' else qualified[target]
                    mask = show & np.isfinite(x).all(axis=1) & np.isfinite(y).all(axis=1)
                    if quality == 'coverage_qualified':
                        mask &= feature_gate[:, 1 if mode == 'raw' else 2]
                    key = '__'.join((target.replace(' ', '_'), measure, mode, quality))
                    stats = statistics(x[mask], y[mask], dates[mask])
                    result[key] = dict(n=int(mask.sum()), start=str(dates[mask][0]) if mask.any() else None,
                                       end=str(dates[mask][-1]) if mask.any() else None, correlations=stats)
                    if measure == 'dollars' or (target == 'Underlying_market' and quality == 'coverage_qualified'):
                        subtitle = f'{measure.title()}-volume HHI across 11 sectors · '+('Daily differences' if mode == 'raw' else 'EMA(10), lag-10 differences')+' · '+quality.replace('_', ' ')
                        path = key+'.png'
                        scatter(plt, root, dates[mask], x[mask], y[mask], 'Underlying stock concentration → '+target.replace('_', ' '), subtitle, path, stats)
                        gallery.append(dict(label=key.replace('__', ' | ').replace('_', ' '), path='plots/'+path))
    # Within-sector stock concentration answers a distinct, sector-specific question.
    for j, target in enumerate(sectors):
        x, y = within[target], labels[target]
        mask = show & np.isfinite(x).all(axis=1) & np.isfinite(y).all(axis=1)
        key = target.replace(' ', '_')+'__within_sector'
        stats = statistics(x[mask], y[mask], dates[mask])
        result[key] = dict(n=int(mask.sum()), correlations=stats)
        scatter(plt, root, dates[mask], x[mask], y[mask], 'Within-sector stock concentration → '+target,
                'Stock dollar-volume HHI within this sector · EMA(10), lag-10 differences · Observed subset; coverage not certified', key+'.png', stats)
        gallery.append(dict(label=target+' | within-sector concentration | observed subset', path='plots/'+key+'.png'))
    # Coverage and aggregate volume/returns are saved at each date, including failed gates.
    with (root/'sector_observations.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.writer(stream)
        writer.writerow(['date', 'snapshot', 'sector', 'expected_names', *data.keys(), 'coverage_pass', *[f'forward_{h}' for h in HORIZONS]])
        for t in np.flatnonzero(show):
            for j, sector in enumerate(sectors):
                row = [dates[t], snapshot_ids[t], sector, counts[t, j], *[a[t, j] for a in data.values()], bool(gate[t, j]), *labels[sector][t]]
                writer.writerow(['' if isinstance(v, (float, np.floating)) and not np.isfinite(v) else v for v in row])
    np.savez_compressed(root/'calculated_arrays.npz', dates=dates, sectors=np.array(sectors), **{f'feature_{k}': v for k, v in feat.items()}, **{f'returns_{k}': v for k, v in labels.items()}, gate=gate, feature_gate=feature_gate)
    coverage = dict(sessions=int(show.sum()), all_sector_volume_pass=int((gate.all(axis=1)&show).sum()),
        sector_summary={s: dict(expected_names_min=int(counts[show, j].min()), expected_names_max=int(counts[show, j].max()),
            median_value_coverage=float(np.nanmedian(data['value_coverage'][show, j])), min_value_coverage=float(np.nanmin(data['value_coverage'][show, j])),
            median_name_coverage=float(np.nanmedian(data['name_coverage'][show, j])), pass_days=int((gate[:, j]&show).sum())) for j, s in enumerate(sectors)})
    write_json(root/'coverage.json', coverage)
    write_json(root/'correlations.json', result)
    stamps = [datetime.fromisoformat(d) for d in dates[show]]
    fig, axes = plt.subplots(3, 1, figsize=(15, 11), sharex=True)
    for j, s in enumerate(sectors):
        axes[0].plot(stamps, data['value_coverage'][show, j], label=s, lw=1)
    axes[0].axhline(.95, ls='--', c='#d97706', label='95% value threshold')
    axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].set_ylabel('Snapshot value covered')
    axes[0].legend(ncol=4, fontsize=8, loc='lower right')
    for j, s in enumerate(sectors):
        axes[1].plot(stamps, data['name_coverage'][show, j], lw=1)
    axes[1].axhline(.70, ls='--', c='#d97706')
    axes[1].yaxis.set_major_formatter(PercentFormatter(1))
    axes[1].set_ylabel('Constituent names covered')
    axes[2].plot(stamps, feat['dollars_raw'][show, 0], c='#94a3b8', lw=.7, label='Dollar-volume HHI')
    axes[2].plot(stamps, feat['dollars_smoothed'][show, 0], c='#0891b2', lw=1.4, label='EMA(10)')
    axes[2].set_ylabel('Observed-subset HHI')
    axes[2].legend(frameon=False)
    fig.suptitle('Underlying-stock coverage and sector trading concentration', x=.08, ha='left', fontsize=20, fontweight='bold')
    fig.text(.08, .933, 'Historical monthly ITOT cohorts; 45-day availability assumption. Missing histories remain in coverage denominators.', fontsize=10, color='#475569')
    fig.subplots_adjust(left=.08, right=.97, top=.90, bottom=.08, hspace=.22)
    fig.savefig(root/'plots'/'coverage_timeline.png', dpi=145)
    plt.close(fig)
    # Sector-volume shares and constituent-aggregate forward returns.
    fig, axes = plt.subplots(4, 1, figsize=(15, 12), sharex=True)
    shares = data['dollars']/data['dollars'].sum(axis=1, keepdims=True)
    axes[0].stackplot(stamps, shares[show].T, labels=sectors, alpha=.9)
    axes[0].set_ylabel('Dollar-volume share')
    axes[0].yaxis.set_major_formatter(PercentFormatter(1))
    axes[0].legend(ncol=4, fontsize=8, loc='upper left')
    for j, h in enumerate(HORIZONS):
        axes[j+1].plot(stamps, labels['Underlying_market'][show, j], c='#0891b2', lw=1)
        axes[j+1].axhline(0, c='#94a3b8', lw=.7)
        axes[j+1].yaxis.set_major_formatter(PercentFormatter(1))
        axes[j+1].set_ylabel(f'Next {h} sessions\naggregate return')
    fig.suptitle('Sector turnover shares and underlying-stock forward returns', x=.08, ha='left', fontsize=20, fontweight='bold')
    fig.text(.08, .935, 'All observed constituents; lower-coverage dates included here. Lagged holding-value weights; USD adjusted-close returns.', fontsize=10, color='#475569')
    fig.subplots_adjust(left=.08, right=.97, top=.90, bottom=.07, hspace=.22)
    fig.savefig(root/'plots'/'sector_timeline.png', dpi=145)
    plt.close(fig)
    options = ''.join(f'<option value="{html.escape(g["path"])}">{html.escape(g["label"])}</option>' for g in gallery)
    default = 'plots/Underlying_market__dollars__raw__coverage_qualified.png'
    page = f'''<!doctype html><html><head><meta charset="utf-8"><title>Underlying-stock sector HHI</title><style>body{{font:16px system-ui;max-width:1500px;margin:30px auto;padding:0 24px;background:#f8fafc;color:#0f172a}}img{{width:100%}}p{{line-height:1.6;color:#475569}}select{{max-width:100%;padding:12px;font:inherit}}a{{color:#0369a1}}</style></head><body><h1>Underlying-stock sector concentration</h1><p>95 historical monthly ITOT equity snapshots; 45-day availability assumption; stock volumes and stock returns aggregated by dated sectors. This is a public-data pilot with incomplete delisted-stock coverage and unverified publication vintages, not a certified whole-market history.</p><p>Coverage-qualified requires each sector to cover ≥95% of lagged holding value and ≥70% of names, including future return paths. Observed-subset plots retain lower-coverage dates and cannot establish a market-wide effect.</p><select id="choice">{options}</select><img id="chart" src="{default}"><p><a href="report.md">Report</a> · <a href="sector_observations.csv">Sector observations CSV</a> · <a href="correlations.json">All correlations</a> · <a href="coverage.json">Coverage audit</a></p><img src="plots/coverage_timeline.png"><img src="plots/sector_timeline.png"><script>const c=document.querySelector('#choice');c.value='{default}';c.addEventListener('change',()=>document.querySelector('#chart').src=c.value);</script></body></html>'''
    (root/'index.html').write_text(page, encoding='utf-8')
    lines = ['# Underlying-stock sector HHI pilot', '', 'See coverage.json, correlations.json and sector_observations.csv for full results.', '',
        'Historical ITOT equity holdings provide a broad US equity sample and dated sector classifications. Monthly snapshots activate 45 calendar days later; actual first-publication/revision times remain unverified. Yahoo supplies constituent daily close, adjusted close and volume. Obvious name mismatches are excluded, not silently joined by ticker. Missing/delisted stocks remain in coverage denominators. This is not a certified whole-market history.', '',
        'Sector dollar turnover = sum(provider close × volume) over observed stocks. Share-volume sums are a sensitivity. Returns are weighted means of observed constituent daily adjusted-close returns, with weights from the lagged holdings market values. They are conditional observed-subset returns, not a replication of ITOT or a market-cap index; no fund return is used. Sector weights update only with lagged snapshots. The equal-weight sensitivity is the daily mean return of all observed constituent stocks.', '',
        'First/second derivatives use the same dated cohort for every point in their backward stencil, excluding mechanical changes in constituent membership. Raw differences use lag 1; smoothing is causal EMA(10), lag 10, 50-session initialization. Coverage-qualified features require all sectors above 95% holding-value and 70% name coverage over the backward window. Qualified returns require coverage on every forward day. Missing prices/returns are not filled; aggregate sums and means describe only observed names.', '',
        'Daily outcomes overlap. Black lines are descriptive OLS, orange lines are equal-count quintile means. Pearson and rank correlations, pre/post-2023 diagnostics and circular block intervals over 240 adjacent retained observations (1,000 replicates, seed 20260926) are provided where at least 480 observations remain. Gaps between retained dates weaken calendar-time interpretation. No multiplicity correction or untouched holdout is claimed.', '',
        '## Market correlations', '', '| Definition | n | HHI 20/60/120 | First derivative 20/60/120 | Second derivative 20/60/120 |', '| --- | ---: | --- | --- | --- |']
    for key, item in result.items():
        if not key.startswith('Underlying_market'):
            continue
        values = []
        for name in FEATURES:
            values.append(' / '.join('n/a' if item['correlations'][name][str(h)]['full']['pearson'] is None else f"{item['correlations'][name][str(h)]['full']['pearson']:+.3f}" for h in HORIZONS))
        lines.append(f'| {key} | {item["n"]} | '+ ' | '.join(values)+' |')
    lines += ['', '## Sources and limitations', '',
        '- Holdings: https://www.blackrock.com/ae/intermediaries/products/239724/ishares-core-sp-total-us-stock-market-etf ; exact dated download URLs and hashes are retained.',
        '- Yahoo chart API: raw responses, source URLs, retrieval timestamps, corporate actions and errors are retained for every requested ticker. Provider split/volume conventions and historical revisions are uncertified.',
        '- Verified ticker aliases: FB→META (https://investor.atmeta.com/investor-news/press-release-details/2022/Meta-Platforms-Inc.-to-Change-Ticker-Symbol-to-META-on-June-9/default.aspx), ANTM→ELV (https://www.elevancehealth.com/newsroom/anthem-inc-shareholders-approve-corporate-rebranding-new-name). Class-share punctuation is normalized; name matching only detects obvious identity mismatches, not all ticker reuse.',
        '- Additional issuer-verified symbol renames and class-share mappings, with sources, are frozen in symbol_aliases.json. Original symbols/download failures remain unchanged. These data repairs preceded correlation results.',
        '- The missing fraction of holding value does not bound the missing fraction of trading volume. No return/HHI conclusion can be generalized to the full market from this pilot.',
        '- Volume does not identify capital inflow. This study adds no LEAN backtest and changes no strategy or trading policy. Certified security IDs, delisting returns, daily universe history and timestamped sector classifications remain prerequisites for strategy evidence.', '']
    (root/'report.md').write_text('\n'.join(lines), encoding='utf-8')
    shutil.copyfile(__file__, root/'analysis_script.py')
    shutil.copyfile(Path(__file__).resolve().parents[1]/'src/systematic_trading/research/underlying_sectors.py', root/'aggregation_source.py')
    write_json(root/'analysis_manifest.json', {p.relative_to(root).as_posix(): sha256(p) for p in root.rglob('*') if p.is_file() and p.name != 'analysis_manifest.json'})
    print(json.dumps(dict(coverage=coverage, market_results={k: v for k, v in result.items() if k.startswith('Underlying_market')}), indent=2))


if __name__ == '__main__':
    main()
