from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systematic_trading.config import AppSettings  # noqa: E402
from systematic_trading.domain.enums import OrderEnvironment  # noqa: E402
from systematic_trading.execution.ib_health import probe_ib_tws_health  # noqa: E402
from systematic_trading.services.health import write_service_state_file  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe IB TWS/Gateway API health and write a platform state file.")
    parser.add_argument("--state-path", type=Path, default=Path("var/run/ib_tws_api.state.json"))
    parser.add_argument("--timeout-seconds", type=float, default=8.0)
    parser.add_argument("--client-id", type=int, default=None)
    parser.add_argument(
        "--environment",
        choices=[OrderEnvironment.PAPER.value, OrderEnvironment.LIVE.value],
        default=OrderEnvironment.PAPER.value,
    )
    args = parser.parse_args()

    settings = AppSettings()
    result = probe_ib_tws_health(
        settings,
        environment=OrderEnvironment(args.environment),
        client_id=args.client_id,
        timeout_seconds=args.timeout_seconds,
    )
    write_service_state_file(
        args.state_path,
        service_id="ib_tws_api",
        running=result.ok,
        heartbeat_at=result.checked_at,
        last_error=None if result.ok else result.message,
        message=result.message,
        details=result.model_dump(mode="json"),
    )
    print(result.model_dump_json())
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
