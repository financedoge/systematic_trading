"""Capture the frozen P4.21 five-session U.S. daily sample for source inspection.

Uses the existing token reader and verified HTTPS transport. Never feeds provider
responses directly to strategy research or updates an audited publication.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.request import Request

from systematic_trading.config import AppSettings
from systematic_trading.data.http import read_bytes
from systematic_trading.data.tushare import read_tushare_token


ENDPOINT = "https://api.tushare.pro"
DATES = {"20250224", "20250225", "20250226", "20250227", "20250228"}
SYMBOLS = ["CSL", "WSO", "MANH", "RPM", "UTHR", "XPO", "FIX", "FLEX", "CASY", "RS"]
FIELDS = "ts_code,trade_date,open,high,low,close,vol,amount,vwap"


def native_post(payload: bytes) -> bytes:
    """One fixed-origin verified HTTPS POST; credential body travels only on stdin."""
    result = subprocess.run(
        ["curl.exe", "-q", "--silent", "--show-error", "--fail", "--max-time", "20",
         "--max-filesize", "1000000", "--proto", "=https", "--proxy", "",
         "--request", "POST", "--header", "Content-Type: application/json",
         "--data-binary", "@-", "--url", ENDPOINT],
        input=payload, capture_output=True, timeout=25,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode or len(result.stdout) > 1_000_000:
        raise OSError("Native HTTPS POST failed or exceeded response bound")
    return result.stdout


def inspect_response(response: dict, symbol: str) -> dict:
    if response.get("code") != 0:
        return {"status": "api_error", "api_code": response.get("code"),
                "message": response.get("msg"), "row_count": 0}
    data = response.get("data") or {}
    fields, items = data.get("fields") or [], data.get("items") or []
    if len(set(fields)) != len(fields) or not {"ts_code", "trade_date", "close", "vol"}.issubset(fields):
        raise ValueError("Missing or duplicate source fields")
    observed = set()
    for item in items:
        if len(item) != len(fields):
            raise ValueError("Source fields/items length mismatch")
        row = dict(zip(fields, item, strict=True))
        if row["ts_code"] != symbol or row["trade_date"] not in DATES:
            raise ValueError("Response outside the frozen request")
        if row["trade_date"] in observed:
            raise ValueError("Duplicate source stock-day")
        observed.add(row["trade_date"])
    return {"status": "ok", "api_code": 0, "row_count": len(items),
            "fields": fields, "complete_five_sessions": observed == DATES,
            "missing_dates": sorted(DATES - observed)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive-root", type=Path, required=True)
    parser.add_argument("--api", action="append", choices=["us_daily", "us_daily_adj"])
    parser.add_argument("--native-post", action="store_true", help="Bounded direct Windows HTTPS POST")
    args = parser.parse_args()
    token = read_tushare_token(AppSettings().tushare_token_path)
    if not token:
        raise SystemExit("Configured Tushare token is unavailable")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = args.archive_root.resolve() / f"us-daily-{stamp}"
    root.mkdir(parents=True, exist_ok=False)
    (root / Path(__file__).name).write_bytes(Path(__file__).read_bytes())
    manifest = {
        "kind": "Tushare U.S. source inspection", "endpoint": ENDPOINT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "source_release": None, "source_release_note": "No release/vintage supplied by endpoint",
        "transport": "native_verified_https_direct" if args.native_post else "shared_verified_https_reader",
        "requests": [], "catalog_publications": 0, "strategy_input_use": False,
    }

    def save():
        (root / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8", newline="\n")

    save()
    for api_name in args.api or ["us_daily", "us_daily_adj"]:
        for symbol in SYMBOLS:
            params = {"ts_code": symbol, "start_date": "20250224", "end_date": "20250228"}
            fields = FIELDS + (",adj_factor,exchange" if api_name == "us_daily_adj" else "")
            public_request = {"api_name": api_name, "params": params, "fields": fields}
            request = Request(ENDPOINT, data=json.dumps({**public_request, "token": token}).encode("utf-8"),
                              headers={"Content-Type": "application/json"}, method="POST")
            receipt = {"request": public_request, "started_at": datetime.now(timezone.utc).isoformat()}
            try:
                raw = (native_post(request.data) if args.native_post else
                       read_bytes(request, timeout=20, max_bytes=1_000_000, attempts=2, native_fallback=False))
                # Refuse to archive any unexpected credential echo from the server.
                if token.encode("utf-8") in raw:
                    raise ValueError("Credential echo refused")
                filename = f"{api_name}-{symbol}.json.gz"
                compressed = gzip.compress(raw, mtime=0)
                (root / filename).write_bytes(compressed)
                receipt.update({"path": filename, "sha256": hashlib.sha256(compressed).hexdigest(),
                                "response_sha256": hashlib.sha256(raw).hexdigest(), "response_bytes": len(raw)})
                response = json.loads(raw)
                receipt.update(inspect_response(response, symbol))
            except Exception as error:
                receipt.update({"status": "failed", "error_type": type(error).__name__})
            receipt["captured_at"] = datetime.now(timezone.utc).isoformat()
            manifest["requests"].append(receipt)
            save()
            print(json.dumps({"api": api_name, "symbol": symbol, "status": receipt["status"],
                              "rows": receipt.get("row_count"), "code": receipt.get("api_code")}), flush=True)
            if receipt["status"] != "ok":
                break
    manifest["status"] = "complete"
    manifest["market_observation_rows"] = sum(r.get("row_count", 0) for r in manifest["requests"])
    save()
    print(json.dumps({"archive": str(root), "rows": manifest["market_observation_rows"]}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
