from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.backtest.reporting import write_backtest_report


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a backtest JSON artifact as a standalone HTML report.")
    parser.add_argument("--input", default="var/backtests/first_real_backtest.json")
    parser.add_argument("--output", default=None)
    parser.add_argument("--database", default="var/systematic_trading.db")
    parser.add_argument(
        "--benchmark-symbol",
        default=None,
        help="Use one stored symbol as the benchmark. Defaults to an equal-weight universe benchmark.",
    )
    args = parser.parse_args()

    result_path = Path(args.input)
    output_path = Path(args.output) if args.output else None
    database_path = Path(args.database) if args.database else None
    report = write_backtest_report(
        result_path=result_path,
        output_path=output_path,
        database_path=database_path,
        benchmark_symbol=args.benchmark_symbol,
    )
    for warning in report.warnings:
        print(f"warning: {warning}")
    print(report.output_path)


if __name__ == "__main__":
    main()
