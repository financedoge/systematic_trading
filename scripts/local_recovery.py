"""Lifecycle control for the platform-owned recovery worker."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trading.services.recovery import LocalRecovery, control


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["start", "stop", "pause", "resume", "run"])
    parser.add_argument("service", nargs="?")
    args = parser.parse_args()
    if args.action == "run":
        LocalRecovery(ROOT).run_forever()
    else:
        control(ROOT, args.action, args.service)


if __name__ == "__main__":
    main()
