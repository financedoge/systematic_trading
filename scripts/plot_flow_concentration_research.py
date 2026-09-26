"""Export publication-style static figures for the completed concentration study.

Optional matplotlib dependency; analysis and the trading platform do not need it.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter
import numpy as np


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root
    report = json.loads((root/'analysis.json').read_text())
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10,
                         'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titleweight': 'bold', 'axes.titlesize': 12,
                         'figure.facecolor': '#f8fafc', 'axes.facecolor': '#f8fafc',
                         'axes.edgecolor': '#cbd5e1', 'text.color': '#0f172a',
                         'xtick.color': '#475569', 'ytick.color': '#475569'})
    curves = {}
    for name in ('sota', 'confirmed_acceleration', 'lag_20', 'literal_exit_gate', 'risk_parity'):
        rows = json.loads((root/'runs'/name/'economic.json').read_text())['nav']
        curves[name] = np.array([float(r['nav'])/1_000_000 for r in rows])
    dates = [datetime.fromisoformat(r['date']) for r in rows]
    fig, axes = plt.subplots(3, 1, figsize=(12, 10), gridspec_kw={'height_ratios': [2.1, 1, 1.2]}, sharex=True)
    colors = {'sota': '#334155', 'confirmed_acceleration': '#0284c7', 'lag_20': '#15803d', 'literal_exit_gate': '#d97706', 'risk_parity': '#94a3b8'}
    labels = {'sota': 'Current SOTA', 'confirmed_acceleration': 'SOTA + concentration acceleration',
              'lag_20': '20-session neighbor (selected afterward)',
              'literal_exit_gate': 'Literal buy / sell gate', 'risk_parity': 'Risk parity'}
    for name, nav in curves.items():
        axes[0].plot(dates, nav, label=labels[name], color=colors[name], linewidth=1.5,
                     alpha=.8 if name == 'risk_parity' else 1)
    axes[0].set_ylabel('Growth of 1 CNH')
    axes[0].legend(loc='upper left', frameon=False, ncol=2, fontsize=9)
    for name, label in [('confirmed_acceleration', 'Predeclared primary'), ('lag_20', '20-session neighbor')]:
        relative = curves[name]/curves['sota']-1
        axes[1].plot(dates, relative, color=colors[name], linewidth=1.4, label=label)
    axes[1].legend(frameon=False, fontsize=8, loc='upper left')
    axes[1].axhline(0, color='#64748b', linewidth=.7)
    axes[1].set_ylabel('Variant / SOTA − 1')
    axes[1].yaxis.set_major_formatter(PercentFormatter(1, decimals=1))
    for name in ('sota', 'confirmed_acceleration', 'lag_20', 'literal_exit_gate'):
        nav = curves[name]
        peak = np.maximum.accumulate(np.r_[1, nav])[1:]
        axes[2].plot(dates, nav/peak-1, color=colors[name], linewidth=1)
    axes[2].set_ylabel('Drawdown')
    axes[2].yaxis.set_major_formatter(PercentFormatter(1))
    for ax in axes:
        ax.grid(axis='y', color='#e2e8f0', linewidth=.6)
        ax.axvline(datetime(2023, 1, 1), color='#64748b', linestyle='--', linewidth=.8)
        ax.axvspan(datetime(2026, 4, 30), dates[-1], color='#38bdf8', alpha=.08)
    axes[2].xaxis.set_major_locator(mdates.YearLocator(2))
    axes[2].xaxis.set_major_formatter(mdates.DateFormatter('%Y'))
    fig.suptitle('Does concentration acceleration improve the current SOTA?', x=.08, ha='left', fontsize=19, fontweight='bold')
    fig.text(.08, .938, 'Native LEAN · Apr 2013–Sep 2026 · Identical data and costs · Research only', fontsize=11, color='#475569')
    fig.text(.08, .025, 'Dashed line: reused post-2023 selection period. Shaded: post-artifact extension.\n'
             'Legacy adjusted data / FX / fixed universe are uncertified; monthly open fills do not model broker TWAP.', fontsize=9, color='#475569')
    fig.subplots_adjust(left=.09, right=.97, top=.9, bottom=.10, hspace=.13)
    for suffix in ('png', 'svg'):
        fig.savefig(root/f'comparison.{suffix}', dpi=160)
    plt.close(fig)

    names = [n for n, cfg in report['protocol']['trials'].items() if cfg is not None]
    names.reverse()
    fig, ax = plt.subplots(figsize=(12, 6.5))
    y = np.arange(len(names))
    full = np.array([report['runs'][n]['vs_sota']['full']['cagr_delta'] for n in names])*100
    post = np.array([report['runs'][n]['vs_sota']['reused_post2023']['cagr_delta'] for n in names])*100
    full_bars = ax.barh(y+.18, full, height=.32, color='#0284c7', label='Full period')
    post_bars = ax.barh(y-.18, post, height=.32, color='#64748b', label='Reused post-2023 period')
    ax.bar_label(full_bars, fmt='%+.2f', padding=3, fontsize=8, color='#0284c7')
    ax.bar_label(post_bars, fmt='%+.2f', padding=3, fontsize=8, color='#475569')
    ax.margins(x=.18)
    ax.set_yticks(y, labels=[n.replace('_', ' ') for n in names])
    ax.axvline(0, color='#0f172a', linewidth=.9)
    ax.grid(axis='x', color='#e2e8f0', linewidth=.6)
    ax.set_axisbelow(True)
    ax.set_xlabel('Annualized return difference vs SOTA (percentage points)')
    ax.legend(frameon=False, loc='upper left')
    fig.suptitle('All 11 predeclared challengers', x=.29, ha='left', fontsize=18, fontweight='bold')
    fig.text(.29, .916, 'No post-result parameter search; the primary was selected before backtests.', fontsize=10, color='#475569')
    fig.subplots_adjust(left=.29, right=.97, top=.85, bottom=.12)
    for suffix in ('png', 'svg'):
        fig.savefig(root/f'ablations.{suffix}', dpi=160)
    plt.close(fig)
    print(root/'comparison.png')


if __name__ == '__main__':
    main()
