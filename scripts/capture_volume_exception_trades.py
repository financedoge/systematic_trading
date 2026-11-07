"""Bounded multi-case source inspection, preserving the preceding CSL recipe."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from decimal import Decimal
import gzip
import json
from pathlib import Path
import subprocess
import time
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from capture_csl_trade_sources import timestamp_ns, retain, TRANSIENT
from probe_alpaca_sip_source import CREDENTIALS, ROOT, load_credentials, save, sha, valid_credentials


STUDY = ROOT / "research/p421-volume-exceptions-20261107-v1"
NY = ZoneInfo("America/New_York")


def protocol() -> dict:
    return json.loads((STUDY / "protocol.json").read_text())


def key(case: dict) -> str:
    return case["symbol"] + "-" + case["date"]


def window(case: dict) -> tuple[int, int]:
    start = datetime.fromisoformat(case["date"]).replace(tzinfo=NY)
    return int(start.timestamp()), int((start + timedelta(days=1)).timestamp())


def parameters(case: dict) -> dict:
    start, end = window(case)
    return {"start": datetime.fromtimestamp(start, UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end": datetime.fromtimestamp(end - 1, UTC).strftime("%Y-%m-%dT%H:%M:%S.999999999Z"),
            "feed": "sip", "asof": "-", "currency": "USD", "sort": "asc", "limit": 10000}


def validate_page(payload: dict, case: dict, seen: set, last: int) -> tuple[list, int]:
    start, end = window(case)
    known_conditions = set(protocol()["rules"][case["tape"] + "_known"])
    if payload.get("symbol") != case["symbol"] or not isinstance(payload.get("trades"), list):
        raise ValueError("Unexpected source identity/shape")
    staged = set()
    for row in payload["trades"]:
        if set(row) - {"c", "i", "p", "s", "t", "u", "x", "z"}:
            raise ValueError("Unreviewed trade fields")
        stamp = timestamp_ns(row["t"])
        if not start * 10**9 <= stamp < end * 10**9 or stamp < last:
            raise ValueError("Out-of-window or unordered trade")
        if row.get("u") not in (None, "canceled", "incorrect", "corrected"):
            raise ValueError("Unknown trade update state")
        if row.get("z") != case["tape"] or not isinstance(row.get("x"), str) or not row["x"]:
            raise ValueError("Unexpected listing tape or exchange")
        if not isinstance(row.get("c"), list) or any(not isinstance(c, str) for c in row["c"]):
            raise ValueError("Invalid trade conditions")
        if set(row["c"]) - known_conditions:
            raise ValueError("Unreviewed trade conditions")
        for field in ("i", "s"):
            if isinstance(row.get(field), bool) or not isinstance(row.get(field), int) or row[field] < 0:
                raise ValueError("Invalid trade identifier or size")
        if row["s"] == 0 and not {"M", "Q", "9"}.intersection(row["c"]):
            raise ValueError("Unrecognized zero-size price marker")
        price = Decimal(str(row["p"]))
        if not price.is_finite() or price <= 0:
            raise ValueError("Invalid trade price")
        identity = json.dumps(row, sort_keys=True, separators=(",", ":"))
        if identity in seen or identity in staged:
            raise ValueError("Exact repeated trade record")
        staged.add(identity)
        last = stamp
    seen.update(staged)
    return payload["trades"], last


def fetch(case: dict, params: dict, credentials: dict) -> tuple[int, bytes]:
    """Reuse the fixed-origin stdin-auth transport contract for frozen symbols."""
    if case not in protocol()["cases"] or any(params.get(k) != v for k, v in parameters(case).items()):
        raise ValueError("Outside frozen request scope")
    credentials = valid_credentials(credentials)
    url = "https://data.alpaca.markets/v2/stocks/" + case["symbol"] + "/trades?" + urlencode(params)
    config = "\n".join(["url = " + json.dumps(url),
        "header = " + json.dumps("APCA-API-KEY-ID: " + credentials["key_id"]),
        "header = " + json.dumps("APCA-API-SECRET-KEY: " + credentials["secret_key"])]) + "\n"
    response = subprocess.run(["curl.exe", "-q", "--config", "-", "--silent", "--show-error", "--ipv4",
        "--proto", "=https", "--connect-timeout", "10", "--max-time", "25", "--max-filesize", "3000000",
        "--proxy", "http://127.0.0.1:7892", "--write-out", "\n%{http_code}"],
        input=config.encode(), capture_output=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if response.returncode:
        raise OSError(response.returncode, "Verified HTTPS transport failed")
    raw, separator, code = response.stdout.rpartition(b"\n")
    if not separator or not code.isdigit() or len(raw) > 3_000_000:
        raise ValueError("Malformed or oversized source response")
    if any(secret.encode() in raw for secret in credentials.values()):
        raise ValueError("Refused credential echo")
    return int(code), raw


def archive(provider: str, resume: Path | None, runner: Path) -> tuple[Path, dict]:
    if resume is not None:
        result = json.loads((resume / "manifest.json").read_text())
        if result["provider"] != provider or result["protocol_sha256"] != sha((STUDY / "protocol.json").read_bytes()):
            raise ValueError("Wrong resume source/protocol")
        if sha(runner.read_bytes()) != result["runner_sha256"]:
            raise ValueError("Changed runner requires a separately recorded validation amendment")
        return resume, result
    root = Path("D:/systematic_trading_data/source-archives") / provider / (
        "volume-exceptions-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
    root.mkdir(parents=True, exist_ok=False)
    files = [runner, ROOT / "scripts/capture_csl_trade_sources.py", ROOT / "scripts/probe_alpaca_sip_source.py",
             ROOT / "scripts/probe_ibkr_source_access.py", ROOT / "scripts/acquire_mdy_ibkr_history.py",
             Path(__file__), STUDY / "protocol.json"]
    hashes = {}
    for source in files:
        raw = source.read_bytes()
        (root / source.name).write_bytes(raw)
        hashes[source.name] = sha(raw)
    result = {"provider": provider, "status": "in_progress", "started_at": datetime.now(UTC).isoformat(),
              "protocol_sha256": hashes["protocol.json"], "runner": runner.name, "runner_sha256": sha(runner.read_bytes()),
              "files_sha256": hashes, "requests": [], "cases": {}, "publications": 0, "order_calls": 0,
              "historical_availability_certified": False}
    save(root / "manifest.json", result)
    return root, result


def verified_payload(root: Path, receipt: dict) -> dict:
    if Path(receipt["path"]).name != receipt["path"]:
        raise ValueError("Invalid source path")
    blob = (root / receipt["path"]).read_bytes()
    raw = gzip.decompress(blob)
    if sha(blob) != receipt["sha256"] or sha(raw) != receipt["response_sha256"]:
        raise ValueError("Changed source payload")
    return json.loads(raw)


def retained_state(root: Path, manifest: dict, case: dict) -> tuple[set, int, str | None, int, bool]:
    seen, last, token, pages, complete = set(), window(case)[0] * 10**9, None, 0, False
    tokens = set()
    for receipt in manifest["requests"]:
        if receipt["case"] != key(case) or receipt.get("http_status") != 200:
            continue
        if complete or receipt["parameters"].get("page_token") != token:
            raise ValueError("Broken saved page chain")
        payload = verified_payload(root, receipt)
        _, last = validate_page(payload, case, seen, last)
        if "next_page_token" not in payload:
            raise ValueError("Missing completion token")
        token = payload["next_page_token"]
        if token is not None and (not isinstance(token, str) or not token or token in tokens):
            raise ValueError("Invalid or cyclic page token")
        tokens.add(token)
        pages += 1
        complete = token is None
    return seen, last, token, pages, complete


def capture(resume: Path | None = None) -> Path:
    credentials = load_credentials(CREDENTIALS, ROOT / ".env")
    root, manifest = archive("alpaca", resume, Path(__file__))
    try:
        for case in protocol()["cases"]:
            seen, last, token, pages, complete = retained_state(root, manifest, case)
            tokens = {r["parameters"].get("page_token") for r in manifest["requests"] if r["case"] == key(case)}
            tokens.add(token)
            while not complete and pages < 30:
                params = parameters(case)
                if token is not None:
                    params["page_token"] = token
                receipt = {"case": key(case), "parameters": params, "started_at": datetime.now(UTC).isoformat(), "attempts": []}
                try:
                    for attempt in range(3):
                        started = datetime.now(UTC).isoformat()
                        try:
                            code, raw = fetch(case, params, credentials)
                        except OSError as error:
                            receipt["attempts"].append({"started_at": started, "curl_code": error.errno})
                            if error.errno not in TRANSIENT or attempt == 2:
                                raise
                            time.sleep(1)
                        else:
                            receipt["attempts"].append({"started_at": started, "http_status": code})
                            break
                    receipt.update(http_status=code, **retain(root, f"{key(case)}-{len(manifest['requests']) + 1:04d}", raw))
                    if code != 200:
                        raise ValueError("HTTP denial or error")
                    payload = json.loads(raw)
                    rows, last = validate_page(payload, case, seen, last)
                    if "next_page_token" not in payload:
                        raise ValueError("Missing completion token")
                    next_token = payload["next_page_token"]
                    if next_token is not None and (not isinstance(next_token, str) or not next_token or next_token in tokens):
                        raise ValueError("Invalid pagination token")
                    token, complete = next_token, next_token is None
                    tokens.add(token)
                    receipt.update(status="ok", rows=len(rows), next_page=not complete)
                except Exception as error:
                    receipt.update(status="failed", error_type=type(error).__name__)
                receipt["captured_at"] = datetime.now(UTC).isoformat()
                manifest["requests"].append(receipt)
                save(root / "manifest.json", manifest)
                print(json.dumps({"case": key(case), "page": pages + 1, "status": receipt["status"],
                                  "rows": receipt.get("rows"), "http": receipt.get("http_status")}), flush=True)
                if receipt["status"] != "ok":
                    raise ValueError("Case acquisition stopped")
                pages += 1
                time.sleep(.35)
            if not complete or not seen:
                raise ValueError("Incomplete or empty case")
            manifest["cases"][key(case)] = {"rows": len(seen), "pages": pages, "complete": True}
            save(root / "manifest.json", manifest)
        manifest["status"] = "captured_pending_qualification"
    except Exception as error:
        manifest.update(status="incomplete", error_type=type(error).__name__)
    manifest["completed_at"] = datetime.now(UTC).isoformat()
    save(root / "manifest.json", manifest)
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume", type=Path)
    args = parser.parse_args()
    root = capture(args.resume)
    status = json.loads((root / "manifest.json").read_text())["status"]
    print(json.dumps({"archive": str(root), "status": status}), flush=True)
    return 0 if status == "captured_pending_qualification" else 1


if __name__ == "__main__":
    raise SystemExit(main())
