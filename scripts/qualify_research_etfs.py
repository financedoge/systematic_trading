"""Persist fresh read-only IB identity evidence without submitting any orders."""
import argparse
import json
from pathlib import Path

from systematic_trading.config import AppSettings
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research.ib_admission import qualify_funds


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--client-id", type=int, default=281)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Qualification evidence already exists")
    settings = AppSettings()
    config = settings.research_etf_recorder_config_path
    funds = json.loads(config.read_text(encoding="utf8"))["funds"]
    result = qualify_funds(settings, funds, client_id=args.client_id)
    result["config_sha256"] = sha256(config)
    write_json(args.output, result)
    print(json.dumps(dict(status=result["status"], funds={s:r["status"] for s,r in result["funds"].items()},
                         account_permission=result["account_permission"], evidence=str(args.output))))
    raise SystemExit(0 if result["status"] == "identity_verified" else 1)
