from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local trading operator dashboard.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--pid-path", default="var/run/operator_dashboard.pid")
    parser.add_argument("--disable-automation", action="store_true")
    args = parser.parse_args()

    os.environ.setdefault("ST_AUTOMATION_ENABLED", "true")
    if args.disable_automation:
        os.environ["ST_AUTOMATION_ENABLED"] = "false"

    pid_path = Path(args.pid_path)
    if not pid_path.is_absolute():
        pid_path = REPO_ROOT / pid_path
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="ascii")
    try:
        uvicorn.run(
            "systematic_trading.app:app",
            host=args.host,
            port=args.port,
            log_level="info",
        )
    finally:
        try:
            if pid_path.read_text(encoding="ascii").strip() == str(os.getpid()):
                pid_path.unlink()
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
