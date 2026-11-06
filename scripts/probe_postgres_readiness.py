"""Check configured PostgreSQL reads before startup backup or retention."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from systematic_trading.config import AppSettings  # noqa: E402
from systematic_trading.storage.postgres_readiness import probe_postgres_readiness  # noqa: E402


def main() -> int:
    settings = AppSettings()
    try:
        result = probe_postgres_readiness(settings)
    except Exception as error:
        detail = str(error)
        for secret in (settings.postgres_app_password, settings.app_postgre_db_password):
            if secret:
                detail = detail.replace(secret, "[redacted]")
        print(f"PostgreSQL read readiness FAILED ({type(error).__name__}): {detail}", file=sys.stderr)
        print(
            "Startup stopped before database preparation and retention. "
            "See docs/native-windows-runtime.md (PostgreSQL read failures). "
            "Do not bypass retention protections or delete database files.",
            file=sys.stderr,
        )
        return 1
    print("PostgreSQL read readiness OK: " + json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
