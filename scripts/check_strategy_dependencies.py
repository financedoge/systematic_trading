"""Read-only dependency validation/impact preview; never updates contract pins."""
import argparse
import json

from systematic_trading.config import AppSettings
from systematic_trading.research.strategy_dependencies import inspection, validate_required, load_registry
from systematic_trading.storage import create_trading_store


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--key', help='Strategy version to inspect')
    parser.add_argument('--action', choices=['archive', 'modify', 'retire'], default='modify')
    parser.add_argument('--contracts-only', action='store_true', help='Validate all registered pins without a database')
    args = parser.parse_args()
    if args.contracts_only:
        print(json.dumps(validate_required(load_registry()['strategies']), indent=2))
        return 0
    settings = AppSettings()
    result = inspection(settings, create_trading_store(settings), key=args.key, action=args.action)
    print(json.dumps(result, indent=2))
    return 1 if result['issues'] or result.get('impact', {}).get('blockers') else 0


if __name__ == '__main__':
    raise SystemExit(main())
