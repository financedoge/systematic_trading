"""Explicit, verified compression of closed logs; see docs/repository-maintenance.md."""
import argparse
import json
from pathlib import Path

from systematic_trading.maintenance.log_archive import archive_log


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="+", help="Explicit basenames inside var/log")
    parser.add_argument("--log-dir", type=Path, default=Path("var/log"))
    parser.add_argument("--rotate", action="store_true", help="Detach a supported Windows append log first")
    parser.add_argument("--apply", action="store_true", help="Archive and remove verified originals")
    args = parser.parse_args()
    if not args.apply:
        print(json.dumps(dict(log_dir=str(args.log_dir.resolve()), names=args.names,
                              rotate=args.rotate, applied=False), indent=2))
        return
    for name in args.names:
        print(json.dumps(archive_log(args.log_dir, name, rotate=args.rotate), indent=2))


if __name__ == "__main__":
    main()
