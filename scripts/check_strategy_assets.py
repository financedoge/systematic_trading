"""Find reusable governed assets or inspect retirement; this command never mutates."""
import argparse
import json

from systematic_trading.research import strategy_assets as assets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--search', default='')
    parser.add_argument('--composite')
    parser.add_argument('--retire', help='Read-only retirement impact for an asset version')
    parser.add_argument('--contracts-only', action='store_true')
    args = parser.parse_args()
    registry = assets.load_registry()
    if args.retire:
        from systematic_trading.config import AppSettings
        from systematic_trading.storage import create_trading_store
        settings = AppSettings()
        result = assets.retirement_impact(settings, create_trading_store(settings), args.retire)
        print(json.dumps(result, indent=2))
        return 0 if result['allowed'] else 1
    if args.contracts_only:
        result = assets.resolve({k:v['sha256'] for k,v in registry['assets'].items()},registry)
        assets.composite_assets(registry['composites'],registry)
    elif args.composite:
        result = assets.demand([args.composite],registry)
    else:
        result = {k:v for k,v in registry['assets'].items() if args.search.casefold() in json.dumps([k,v]).casefold()}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
