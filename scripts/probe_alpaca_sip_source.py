"""Bounded P4.21 Alpaca SIP source inspection; never publishes strategy inputs."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import getpass
import gzip
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import time
import warnings
from urllib.parse import urlencode
from zoneinfo import ZoneInfo


ROOT = Path(__file__).resolve().parents[1]
ENDPOINT = "https://data.alpaca.markets/v2/stocks/bars"
REQUEST = ROOT / "research/p421-volume-contract-20261107-v1/source-request.json"
REQUEST_HASH = "8380ef95bd63b9300a6bc0401a48bd5e5892dad0c3b20143d93809ed7f35d457"
CREDENTIALS = ROOT / "var/private/alpaca/credentials.json"
NY = ZoneInfo("America/New_York")
MAX_BYTES = 3_000_000
MAX_PAGES = 10


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def scope(stage: str) -> tuple[list[str], list[str]]:
    raw = REQUEST.read_bytes()
    if sha(raw) != REQUEST_HASH:
        raise ValueError("Frozen source request changed")
    request = json.loads(raw)
    symbols = [item["symbol"] for item in request["identities"]]
    dates = request["initial_dates"]
    return (symbols[:1], dates[:1]) if stage == "probe" else (symbols, dates)


def valid_credentials(value: dict) -> dict:
    for name in ("key_id", "secret_key"):
        field = value.get(name)
        if not isinstance(field, str) or not field or any(ord(c) < 33 or ord(c) > 126 for c in field):
            raise ValueError("API credentials must be nonempty printable values without whitespace")
    return {name: value[name] for name in ("key_id", "secret_key")}


def load_credentials(path: Path, env_file: Path) -> dict:
    """Read the existing local credential source without copying or logging keys."""
    if path.is_file():
        return valid_credentials(json.loads(path.read_text(encoding="utf-8")))
    from dotenv import dotenv_values

    values = dotenv_values(env_file, interpolate=False) if env_file.is_file() else {}
    for key_name, secret_name in (("ST_ALPACA_MARKET_API_KEY", "ST_ALPACA_MARKET_API_SECRET"),
                                   ("APCA_API_KEY_ID", "APCA_API_SECRET_KEY")):
        if key_name in values or secret_name in values:
            return valid_credentials({"key_id": values.get(key_name), "secret_key": values.get(secret_name)})
    raise FileNotFoundError("Alpaca credentials are not configured in the selected local files")


def setup_credentials(path: Path) -> None:
    if path.exists():
        raise FileExistsError("Credential file already exists; preserved")
    print("Paste your Alpaca PAPER account API key and secret below. Input is hidden.")
    with warnings.catch_warnings():
        warnings.simplefilter("error", getpass.GetPassWarning)
        credentials = valid_credentials({"key_id": getpass.getpass("API key ID: "),
                                         "secret_key": getpass.getpass("API secret: ")})
    # Reuse the established new-file ACL helper; no shared service is modified.
    spec = importlib.util.spec_from_file_location("wrds_acl", ROOT / "scripts/setup_wrds_access.py")
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        helper.protect_new_file(path)
        json.dump(credentials, handle)
        handle.write("\n")
    print("Saved locally with restricted file permissions. API access is not yet verified.")


def parameters(symbols: list[str], dates: list[str], timeframe: str) -> dict:
    if timeframe not in ("1Day", "1Min"):
        raise ValueError("Unsupported aggregation")
    return {"symbols": ",".join(symbols), "timeframe": timeframe,
            "start": dates[0] + "T00:00:00-05:00", "end": dates[-1] + "T23:59:59-05:00",
            "feed": "sip", "adjustment": "raw", "asof": "-", "currency": "USD",
            "sort": "asc", "limit": 10000}


def fetch(params: dict, credentials: dict, *, local_proxy: bool = False) -> tuple[int, bytes]:
    """Fixed-origin HTTPS GET. Credentials on stdin, never argv; no redirects."""
    credentials = valid_credentials(credentials)
    if params.get("feed") != "sip" or params.get("adjustment") != "raw":
        raise ValueError("Only raw SIP requests are allowed")
    url = ENDPOINT + "?" + urlencode(params)
    config = "\n".join([
        "url = " + json.dumps(url),
        "header = " + json.dumps("APCA-API-KEY-ID: " + credentials["key_id"]),
        "header = " + json.dumps("APCA-API-SECRET-KEY: " + credentials["secret_key"]),
    ]) + "\n"
    command = ["curl.exe", "-q", "--config", "-", "--silent", "--show-error", "--ipv4",
         "--proto", "=https", "--connect-timeout", "10", "--max-time", "25",
         "--max-filesize", str(MAX_BYTES), "--write-out", "\n%{http_code}"]
    if local_proxy:
        command.extend(["--proxy", "http://127.0.0.1:7892"])
    result = subprocess.run(
        command,
        input=config.encode("utf-8"), capture_output=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    if result.returncode:
        raise OSError(f"Verified HTTPS transport failed (curl {result.returncode})")
    body, separator, status = result.stdout.rpartition(b"\n")
    if not separator or len(body) > MAX_BYTES or not status.isdigit():
        raise ValueError("Invalid or oversized HTTP response")
    if any(secret.encode() in body for secret in credentials.values()):
        raise ValueError("Refused credential echo")
    return int(status), body


def inspect_page(payload: dict, params: dict, dates: list[str], seen: set) -> list[dict]:
    bars = payload.get("bars")
    if not isinstance(bars, dict):
        raise ValueError("Missing bars object")
    symbols = set(params["symbols"].split(","))
    if set(bars) - symbols:
        raise ValueError("Unexpected symbol")
    out = []
    page_seen = set()
    for symbol, records in bars.items():
        if records is None:
            continue
        if not isinstance(records, list):
            raise ValueError("Invalid bar list")
        for record in records:
            instant = datetime.fromisoformat(record["t"])
            if instant.tzinfo is None:
                raise ValueError("Naive source timestamp")
            local = instant.astimezone(NY)
            if local.date().isoformat() not in dates:
                raise ValueError("Unexpected date")
            if local.second or local.microsecond or (params["timeframe"] == "1Day" and (local.hour or local.minute)):
                raise ValueError("Unexpected bar boundary")
            identity = (symbol, instant)
            if identity in seen or identity in page_seen:
                raise ValueError("Duplicate bar across source pages")
            for field in ("o", "h", "l", "c", "v", "n"):
                value = record[field]
                if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                    raise ValueError("Invalid numeric bar field")
                if value < 0 or (field in ("o", "h", "l", "c") and value == 0):
                    raise ValueError("Negative activity or nonpositive price")
            if record["h"] < max(record["o"], record["c"], record["l"]) or record["l"] > min(record["o"], record["c"]):
                raise ValueError("Inconsistent OHLC")
            page_seen.add(identity)
            out.append({"symbol": symbol, **record})
    seen.update(page_seen)
    return out


def capture(stage: str, credentials: dict, archive_root: Path, *, local_proxy: bool = False,
            transport_attempts: int = 1) -> Path:
    symbols, dates = scope(stage)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    root = archive_root / (stage + "-" + stamp)
    root.mkdir(parents=True, exist_ok=False)
    runner = Path(__file__).read_bytes()
    (root / Path(__file__).name).write_bytes(runner)
    manifest = {"status": "in_progress", "stage": stage, "endpoint": ENDPOINT,
                "transport": "verified_https_ipv4_local_proxy" if local_proxy else "verified_https_ipv4",
                "max_transport_attempts_per_page": transport_attempts,
                "created_at": datetime.now(UTC).isoformat(), "symbols": symbols, "dates": dates,
                "source_request_sha256": REQUEST_HASH, "runner_sha256": sha(runner),
                "source_release": None, "historical_availability_certified": False,
                "publications": 0, "strategy_input_use": False, "requests": [], "series": {}}
    save(root / "manifest.json", manifest)
    for timeframe in ("1Day", "1Min"):
        params = parameters(symbols, dates, timeframe)
        seen, tokens, rows = set(), set(), []
        series_complete = False
        for page in range(1, MAX_PAGES + 1):
            receipt = {"parameters": dict(params), "started_at": datetime.now(UTC).isoformat(),
                       "transport_attempts": []}
            try:
                for attempt in range(transport_attempts):
                    attempt_receipt = {"started_at": datetime.now(UTC).isoformat()}
                    try:
                        status, raw = (fetch(params, credentials, local_proxy=True) if local_proxy else fetch(params, credentials))
                    except OSError as error:
                        match = re.fullmatch(r"Verified HTTPS transport failed \(curl (\d+)\)", str(error))
                        code = int(match[1]) if match else None
                        attempt_receipt.update(captured_at=datetime.now(UTC).isoformat(), curl_exit_code=code)
                        receipt["transport_attempts"].append(attempt_receipt)
                        if code not in {5, 6, 7, 18, 28, 35, 52, 55, 56} or attempt + 1 == transport_attempts:
                            raise
                        time.sleep(1)
                    else:
                        attempt_receipt.update(captured_at=datetime.now(UTC).isoformat(), http_status=status)
                        receipt["transport_attempts"].append(attempt_receipt)
                        break
                filename = f"{timeframe}-{page:02d}.json.gz"
                blob = gzip.compress(raw, mtime=0)
                (root / filename).write_bytes(blob)
                receipt.update(http_status=status, path=filename, sha256=sha(blob),
                               response_sha256=sha(raw), response_bytes=len(raw))
                if status != 200:
                    raise RuntimeError(f"HTTP {status}; capture stopped")
                payload = json.loads(raw)
                page_rows = inspect_page(payload, params, dates, seen)
                rows.extend(page_rows)
                token = payload.get("next_page_token")
                if token is not None and (not isinstance(token, str) or not token or token in tokens):
                    raise ValueError("Invalid or repeated pagination token")
                receipt.update(status="ok", row_count=len(page_rows), has_next_page=token is not None)
                series_complete = token is None
                if token is not None:
                    tokens.add(token)
                    params["page_token"] = token
            except Exception as error:
                receipt.update(status="failed", error_type=type(error).__name__)
                if type(error) is OSError:
                    # fetch creates this fixed error text from curl's numeric exit code.
                    receipt["transport_error"] = str(error)
            receipt["captured_at"] = datetime.now(UTC).isoformat()
            manifest["requests"].append(receipt)
            save(root / "manifest.json", manifest)
            print(json.dumps({"timeframe": timeframe, "page": page, "status": receipt["status"],
                              "http": receipt.get("http_status"), "rows": receipt.get("row_count")}), flush=True)
            if receipt["status"] != "ok" or series_complete:
                break
        observed = {(r["symbol"], datetime.fromisoformat(r["t"]).astimezone(NY).date().isoformat()) for r in rows}
        missing = sorted(set((s, d) for s in symbols for d in dates) - observed)
        manifest["series"][timeframe] = {"pagination_complete": series_complete, "rows": len(rows),
                                           "missing_stock_days": missing}
        if not series_complete or missing or receipt["status"] != "ok":
            manifest["status"] = "incomplete"
            break
    else:
        manifest["status"] = "captured_pending_qualification"
    save(root / "manifest.json", manifest)
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", action="store_true")
    parser.add_argument("--credentials", type=Path, default=CREDENTIALS)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--stage", choices=("probe", "sample"), default="probe")
    parser.add_argument("--local-proxy", action="store_true", help="Use the existing localhost:7892 HTTP proxy")
    parser.add_argument("--transport-attempts", type=int, choices=(1, 2, 3), default=1)
    parser.add_argument("--archive-root", type=Path,
                        default=Path("D:/systematic_trading_data/source-archives/alpaca"))
    args = parser.parse_args()
    if args.setup:
        setup_credentials(args.credentials)
        return 0
    try:
        credentials = load_credentials(args.credentials, args.env_file)
    except FileNotFoundError:
        print("Alpaca credentials are not configured. Use the local .env or --setup first.")
        return 2
    root = capture(args.stage, credentials, args.archive_root, local_proxy=args.local_proxy,
                   transport_attempts=args.transport_attempts)
    status = json.loads((root / "manifest.json").read_text())["status"]
    print(json.dumps({"archive": str(root), "status": status}))
    return 0 if status == "captured_pending_qualification" else 1


if __name__ == "__main__":
    raise SystemExit(main())
