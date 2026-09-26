"""Export a frozen bundle and run the offline LEAN research worker."""
import argparse
from datetime import date
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))

from systematic_trading.config import AppSettings
from systematic_trading.lean.bundle import export_bundle
from systematic_trading.lean.runner import run_bundle
from systematic_trading.market_data.store import ClickHouseMarketDataStore


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--image', help='Pinned quantconnect/lean@sha256:...')
    parser.add_argument('--export', action='store_true')
    parser.add_argument('--register', action='store_true', help='Append passed research evidence to PostgreSQL')
    parser.add_argument('--start', default='2025-01-02')
    parser.add_argument('--end', default='2025-12-31')
    parser.add_argument('--warmup-start', default='2023-10-01')
    parser.add_argument('--strategy', choices=['sota', 'benchmark'], default='sota')
    parser.add_argument('--mode', choices=['targets', 'shared'], default='shared')
    parser.add_argument('--allow-legacy-fx', action='store_true', help='Uncertified engineering parity only: retain original FX dates, maximum 7-day carry')
    parser.add_argument('--cost-bps', default='5')
    parser.add_argument('--slippage-bps', default='0')
    parser.add_argument('--delay-sessions', type=int, default=0)
    parser.add_argument('--lookback-bars', type=int, default=63)
    args = parser.parse_args()
    if args.export:
        export_bundle(store=ClickHouseMarketDataStore.from_settings(AppSettings()), root=args.bundle,
                      start=date.fromisoformat(args.start), end=date.fromisoformat(args.end),
                      warmup_start=date.fromisoformat(args.warmup_start), strategy=args.strategy, mode=args.mode,
                      cost_bps=args.cost_bps, slippage_bps=args.slippage_bps, delay=args.delay_sessions,
                      legacy_fx=args.allow_legacy_fx, lookback_bars=args.lookback_bars)
        print(f'Frozen bundle: {args.bundle}')
    if args.output:
        if not args.image:
            parser.error('--output requires --image with a digest')
        print(run_bundle(bundle=args.bundle, output=args.output, image=args.image))
        if args.register:
            from systematic_trading.lean.registry import register_run
            from systematic_trading.storage.postgres import PostgresStore
            print("Registered:", register_run(PostgresStore.from_settings(AppSettings()), args.output))


if __name__ == '__main__':
    main()
