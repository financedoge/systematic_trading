from __future__ import annotations

import argparse
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import IbApiOrderClient, InteractiveBrokersAdapter


def main() -> None:
    parser = argparse.ArgumentParser(description="Smoke-test the Interactive Brokers paper TWS API connection.")
    parser.add_argument("--timeout-seconds", type=float, default=15.0)
    args = parser.parse_args()

    settings = AppSettings()
    profile = InteractiveBrokersAdapter(settings).profile_for(OrderEnvironment.PAPER)
    client = IbApiOrderClient(connection_timeout_seconds=args.timeout_seconds)
    next_order_id = client.connect(profile)
    try:
        print(f"environment={profile.environment.value}")
        print(f"host={profile.host}")
        print(f"port={profile.port}")
        print(f"client_id={profile.client_id}")
        print(f"next_valid_order_id={next_order_id}")
        print("status=connected")
    finally:
        client.disconnect()
        print("status=disconnected")


if __name__ == "__main__":
    main()
