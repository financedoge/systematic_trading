"""Run reproducible native LEAN parity, repeatability and research stress cases."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.config import AppSettings
from systematic_trading.lean.bundle import export_bundle
from systematic_trading.lean.contracts import write_json
from systematic_trading.lean.fixtures import make_fixture_bundle
from systematic_trading.lean.registry import register_run
from systematic_trading.lean.runner import run_bundle
from systematic_trading.market_data.store import ClickHouseMarketDataStore
from systematic_trading.storage.postgres import PostgresStore


def metrics(rows, starting_nav):
    if not rows:
        return None
    peak = float(starting_nav)
    drawdown = 0.0
    for row in rows:
        value = float(row['nav'])
        peak = max(peak, value)
        drawdown = min(drawdown, value / peak - 1)
    return {'sessions': len(rows), 'total_return': float(rows[-1]['nav']) / float(starting_nav) - 1,
            'max_drawdown': drawdown, 'end_nav_cnh': rows[-1]['nav']}


def write_summary(root, summary):
    write_json(root / 'summary.json', summary)
    lines = ['# LEAN validation evidence', '',
             'Status: ' + ('complete; every requested case passed' if summary.get('complete') else 'partial suite; only listed cases have passed'),
             '', summary['warning'], '', '`' + summary['image'] + '`', '',
             '| Case | Sessions | End NAV (CNH) | Return | Max drawdown | Python wall (s) | LEAN wall (s) | LEAN peak RSS (MiB) |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for case, row in summary['runs'].items():
        metric, receipt = row['metrics'], row['receipt']
        lines.append(f"| {case} | {metric['sessions']} | {float(metric['end_nav_cnh']):,.2f} | "
                     f"{metric['total_return']:.2%} | {metric['max_drawdown']:.2%} | "
                     f"{receipt['reference_wall_seconds']:.2f} | {receipt['lean_wall_seconds']:.2f} | "
                     f"{row['lean_resources']['peak_rss_bytes']/1024**2:.1f} |")
        if 'repeat' in row:
            repeated = row['repeat']
            lines.append(f"| {case} repeat | {metric['sessions']} | {float(metric['end_nav_cnh']):,.2f} | "
                         f"{metric['total_return']:.2%} | {metric['max_drawdown']:.2%} | "
                         f"{repeated['reference_wall_seconds']:.2f} | {repeated['lean_wall_seconds']:.2f} | — |")
    lines += ['', 'All cases require exact decision sessions, symbol sets, integer fills and final holdings; '
              'target tolerance is 1e-8 and cash/fee/NAV tolerance is 0.01 CNH. The repeated fixture must '
              'produce the same normalized economic hash.', '',
              'Wall time includes process/container startup. Process CPU and peak RSS, engine labels, '
              'runtime versions, event counts, artifact sizes, fitted/post-2023 metrics and hashes are '
              'in summary.json. Python runs on Windows and LEAN on Linux with 2 CPUs/4 GiB limits. '
              'These timings describe this setup; image download time is excluded. No cold-cache flush '
              'is performed against the operating platform.', '',
              'The long-history case executes 2013-02-01 through 2026-04-29 with warmup from 2012-01-05. '
              'This is a separate adjusted-CNH-unit scenario, not a reproduction of the older USD-cash '
              'performance claim. Native engine results remain research-only.', '']
    (root / 'report.md').write_text('\n'.join(lines), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True, help='New immutable validation suite directory on D:')
    parser.add_argument('--image', required=True)
    parser.add_argument('--cases', nargs='+', default=['fixture-targets', 'fixture-shared', 'fixture-stress',
        'year-sota', 'year-benchmark', 'year-cost', 'year-delay', 'year-lookback42', 'year-lookback84',
        'full-sota', 'full-benchmark'])
    args = parser.parse_args()
    if args.root.exists():
        parser.error('Use a new suite directory; prior evidence is immutable')
    args.root.mkdir(parents=True)
    settings = AppSettings()
    market = ClickHouseMarketDataStore.from_settings(settings)
    registry = PostgresStore.from_settings(settings)
    summary = {'image': args.image, 'promotion_eligible': False, 'runs': {},
        'warning': 'Engineering parity only. Legacy FX, adjusted vintages and fixed universe are uncertified; '
                   'pre-2023 is fitted and post-2023 has been used in strategy selection.'}
    for case in args.cases:
        bundle, output = args.root / 'datasets' / case, args.root / 'runs' / case
        print(f'Preparing {case}', flush=True)
        if case.startswith('fixture-'):
            if case not in {'fixture-targets', 'fixture-shared', 'fixture-stress'}:
                parser.error('Unknown case: ' + case)
            stress = case.endswith('stress')
            make_fixture_bundle(bundle, mode='targets' if case.endswith('targets') else 'shared',
                                cost_bps='25' if stress else '5', slippage_bps='20' if stress else '0',
                                delay=1 if stress else 0)
        else:
            full = case.startswith('full-')
            if case not in {'year-sota', 'year-benchmark', 'year-cost', 'year-delay', 'year-lookback42',
                            'year-lookback84', 'full-sota', 'full-benchmark'}:
                parser.error('Unknown case: ' + case)
            export_bundle(store=market, root=bundle, start=date(2013, 2, 1) if full else date(2025, 1, 2),
                          end=date(2026, 4, 29) if full else date(2025, 12, 31),
                          warmup_start=date(2012, 1, 5) if full else date(2023, 10, 1),
                          strategy='benchmark' if case.endswith('benchmark') else 'sota', legacy_fx=True,
                          cost_bps='25' if case == 'year-cost' else '5',
                          slippage_bps='20' if case == 'year-cost' else '0',
                          delay=1 if case == 'year-delay' else 0,
                          lookback_bars=42 if case == 'year-lookback42' else 84 if case == 'year-lookback84' else 63)
        print(f'Running {case}', flush=True)
        receipt = run_bundle(bundle=bundle, output=output, image=args.image)
        register_run(registry, output)
        # An identical insertion must be a no-op, proving registry idempotency.
        register_run(registry, output)
        actual = json.loads((output / 'economic.json').read_text(encoding='utf-8'))
        reference = json.loads((output / 'reference.json').read_text(encoding='utf-8'))
        native_resources = json.loads((output / 'resources.json').read_text(encoding='utf-8'))
        rows = actual['nav']
        before = [r for r in rows if r['date'] < '2023-01-01']
        after = [r for r in rows if r['date'] >= '2023-01-01']
        item = {'receipt': receipt, 'metrics': metrics(rows, '1000000'),
                'fitted_pre2023': metrics(before, '1000000'),
                'selected_post2023': metrics(after, before[-1]['nav'] if before else '1000000'),
                'reference_resources': reference['resources'], 'lean_resources': native_resources,
                'artifact_bytes': sum(p.stat().st_size for p in output.rglob('*') if p.is_file())}
        summary['runs'][case] = item
        if case == 'fixture-targets':
            repeated = run_bundle(bundle=bundle, output=args.root / 'runs' / 'fixture-repeat', image=args.image)
            if repeated['economic_sha256'] != receipt['economic_sha256']:
                raise ValueError('Repeated native LEAN economic output changed')
            register_run(registry, args.root / 'runs' / 'fixture-repeat')
            item['repeat'] = repeated
        write_summary(args.root, summary)
        print(f'Passed {case}: {len(rows)} sessions', flush=True)
    write_summary(args.root, dict(summary, complete=True))


if __name__ == '__main__':
    main()
