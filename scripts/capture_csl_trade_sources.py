"""Frozen one-day CSL source capture; no publications or trading operations."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
from decimal import Decimal
import gzip
import json
from pathlib import Path
import re
import subprocess
from threading import Event, Thread
import time
from urllib.parse import urlencode

from acquire_mdy_ibkr_history import verified_prior
from probe_alpaca_sip_source import CREDENTIALS, load_credentials, save, sha, valid_credentials
from probe_ibkr_source_access import inspect_history
from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.execution.ib_compat import compatible_ib_errors


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research/p421-csl-trades-20261107-v1"
START = int(datetime(2025, 2, 24, 5, tzinfo=UTC).timestamp())
END = START + 86400
ALLOWED_PATHS = {"/v2/stocks/CSL/trades", "/v2/stocks/meta/exchanges", "/v2/stocks/meta/conditions/trade"}
TRANSIENT = {5, 6, 7, 18, 28, 35, 52, 55, 56}


def timestamp_ns(value: str) -> int:
    match = re.fullmatch(r"(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)(?:\.(\d{1,9}))?Z", value)
    if not match:
        raise ValueError("Expected UTC timestamp with up to nanosecond precision")
    seconds = int(datetime.fromisoformat(match[1]).replace(tzinfo=UTC).timestamp())
    return seconds * 10**9 + int((match[2] or "").ljust(9, "0"))


def validate_alpaca(payload: dict, seen: set, last_ns: int) -> tuple[list, int]:
    if payload.get("symbol") != "CSL" or not isinstance(payload.get("trades"), list):
        raise ValueError("Unexpected trade response identity or shape")
    staged = set()
    for row in payload["trades"]:
        stamp = timestamp_ns(row["t"])
        if not START * 10**9 <= stamp < END * 10**9 or stamp < last_ns:
            raise ValueError("Out-of-window or unordered trade")
        if row.get("u") not in (None, "canceled", "incorrect", "corrected"):
            raise ValueError("Unknown trade update state")
        if (not isinstance(row.get("c"), list) or any(not isinstance(c, str) for c in row["c"])
                or not isinstance(row.get("x"), str) or not row["x"] or row.get("z") != "A"):
            raise ValueError("Invalid condition/exchange or unexpected listing tape")
        if isinstance(row.get("i"), bool) or not isinstance(row.get("i"), int) or row["i"] < 0:
            raise ValueError("Invalid trade identifier")
        if isinstance(row.get("s"), bool) or not isinstance(row.get("s"), int) or row["s"] < 0:
            raise ValueError("Invalid trade size")
        if row["s"] == 0 and not {"M", "Q", "9"}.intersection(row["c"]):
            raise ValueError("Unrecognized zero-size price marker")
        price = Decimal(str(row["p"]))
        if not price.is_finite() or price <= 0:
            raise ValueError("Invalid trade price")
        # Different IDs/update states remain distinct even for otherwise identical trades.
        identity = json.dumps(row, sort_keys=True, separators=(",", ":"))
        if identity in seen or identity in staged:
            raise ValueError("Exact duplicate trade record across source pages")
        staged.add(identity)
        last_ns = stamp
    seen.update(staged)
    return payload["trades"], last_ns


def next_ib_second(rows: list[dict], cursor: int) -> int:
    if not rows:
        return cursor
    previous = cursor
    for row in rows:
        stamp = row["time"]
        if not isinstance(stamp, int) or stamp < previous:
            raise ValueError("IB timestamps regress across page boundary")
        price, size = Decimal(row["price"]), Decimal(row["size"])
        if not price.is_finite() or not size.is_finite() or price < 0 or size < 0:
            raise ValueError("Invalid IB numeric field")
        if size != size.to_integral_value() or (price == 0 and size != 0):
            raise ValueError("Unsupported IB size or halt marker")
        previous = stamp
    return previous + 1  # IB completes the final whole second, including excess rows.


def new_archive(provider: str) -> tuple[Path, dict]:
    path = Path("D:/systematic_trading_data/source-archives") / provider / (
        "csl-trades-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
    path.mkdir(parents=True, exist_ok=False)
    runner = Path(__file__).read_bytes()
    (path / Path(__file__).name).write_bytes(runner)
    (path / "protocol.json").write_bytes((STUDY / "protocol.json").read_bytes())
    helpers = {}
    for name in ("probe_alpaca_sip_source.py", "probe_ibkr_source_access.py", "acquire_mdy_ibkr_history.py"):
        raw = (ROOT / "scripts" / name).read_bytes()
        (path / name).write_bytes(raw)
        helpers[name] = sha(raw)
    manifest = {"status": "in_progress", "provider": provider, "symbol": "CSL", "date": "2025-02-24",
                "started_at": datetime.now(UTC).isoformat(), "runner_sha256": sha(runner),
                "helper_sha256": helpers, "protocol_sha256": sha((STUDY / "protocol.json").read_bytes()),
                "requests": [], "publications": 0, "order_calls": 0,
                "historical_availability_certified": False}
    save(path / "manifest.json", manifest)
    return path, manifest


def retain(root: Path, label: str, raw: bytes) -> dict:
    blob = gzip.compress(raw, mtime=0)
    path = root / (label + ".json.gz")
    path.write_bytes(blob)
    return {"path": path.name, "sha256": sha(blob), "response_sha256": sha(raw)}


def fetch(path: str, params: dict, credentials: dict) -> tuple[int, bytes]:
    if path not in ALLOWED_PATHS:
        raise ValueError("Undeclared Alpaca resource")
    if path.endswith("/CSL/trades") and (params.get("feed"), params.get("asof")) != ("sip", "-"):
        raise ValueError("Only literal CSL SIP trades permitted")
    credentials = valid_credentials(credentials)
    url = "https://data.alpaca.markets" + path + ("?" + urlencode(params) if params else "")
    config = "\n".join(["url = " + json.dumps(url),
        "header = " + json.dumps("APCA-API-KEY-ID: " + credentials["key_id"]),
        "header = " + json.dumps("APCA-API-SECRET-KEY: " + credentials["secret_key"])]) + "\n"
    result = subprocess.run(["curl.exe", "-q", "--config", "-", "--silent", "--show-error", "--ipv4",
        "--proto", "=https", "--connect-timeout", "10", "--max-time", "25", "--max-filesize", "3000000",
        "--proxy", "http://127.0.0.1:7892", "--write-out", "\n%{http_code}"],
        input=config.encode(), capture_output=True, timeout=30,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if result.returncode:
        raise OSError(result.returncode, "Verified HTTPS transport failed")
    body, separator, code = result.stdout.rpartition(b"\n")
    if not separator or not code.isdigit() or len(body) > 3_000_000:
        raise ValueError("Malformed or oversized response")
    if any(value.encode() in body for value in credentials.values()):
        raise ValueError("Refused credential echo")
    return int(code), body


def capture_alpaca() -> Path:
    credentials = load_credentials(CREDENTIALS, ROOT / ".env")
    root, manifest = new_archive("alpaca")
    seen, tokens, last_ns = set(), set(), START * 10**9
    params = {"start": "2025-02-24T05:00:00Z", "end": "2025-02-25T04:59:59.999999999Z",
              "feed": "sip", "asof": "-", "currency": "USD", "sort": "asc", "limit": 10000}
    resources = [("exchanges", "/v2/stocks/meta/exchanges", {}),
                 ("conditions", "/v2/stocks/meta/conditions/trade", {"tape": "A"})]
    for page in range(12):  # Two metadata requests, at most ten trade pages.
        if page < 2:
            label, endpoint, query = resources[page]
        else:
            label, endpoint, query = f"trades-{page - 1:02d}", "/v2/stocks/CSL/trades", dict(params)
        receipt = {"resource": endpoint, "parameters": query, "started_at": datetime.now(UTC).isoformat(),
                   "attempts": []}
        try:
            for attempt in range(3):
                started = datetime.now(UTC).isoformat()
                try:
                    code, raw = fetch(endpoint, query, credentials)
                except OSError as error:
                    receipt["attempts"].append({"started_at": started, "curl_code": error.errno})
                    if error.errno not in TRANSIENT or attempt == 2:
                        raise
                    time.sleep(1)
                else:
                    receipt["attempts"].append({"started_at": started, "http_status": code})
                    break
            receipt.update(http_status=code, **retain(root, label, raw))
            if code != 200:
                raise ValueError("Non-success HTTP response")
            payload = json.loads(raw)
            if page >= 2:
                rows, last_ns = validate_alpaca(payload, seen, last_ns)
                if "next_page_token" not in payload:
                    raise ValueError("Missing pagination completion field")
                token = payload["next_page_token"]
                if token is not None and (not isinstance(token, str) or not token or token in tokens):
                    raise ValueError("Invalid or repeated pagination token")
                receipt.update(rows=len(rows), next_page=token is not None)
                if token is None:
                    manifest["status"] = "captured_pending_qualification"
                else:
                    tokens.add(token)
                    params["page_token"] = token
            elif not isinstance(payload, dict):
                raise ValueError("Invalid source metadata")
            receipt["status"] = "ok"
        except Exception as error:
            receipt.update(status="failed", error_type=type(error).__name__)
            manifest["status"] = "incomplete"
        receipt["captured_at"] = datetime.now(UTC).isoformat()
        manifest["requests"].append(receipt)
        save(root / "manifest.json", manifest)
        print(json.dumps({"provider": "alpaca", "page": page, "status": receipt["status"],
                          "rows": receipt.get("rows"), "http": receipt.get("http_status")}), flush=True)
        if manifest["status"] != "in_progress":
            break
    if manifest["status"] == "in_progress":
        manifest["status"] = "page_bound_incomplete"
    manifest.update(rows=len(seen), completed_at=datetime.now(UTC).isoformat())
    save(root / "manifest.json", manifest)
    return root


def resume_ib(root: Path) -> tuple[int, int, dict]:
    """Resume only verified complete forward pages; failed pages are not consumed."""
    raw = (root / "manifest.json").read_bytes()
    manifest = json.loads(raw)
    if manifest["provider"] != "ibkr" or manifest["symbol"] != "CSL" or manifest["date"] != "2025-02-24":
        raise ValueError("Wrong resume source")
    if manifest["protocol_sha256"] != sha((STUDY / "protocol.json").read_bytes()):
        raise ValueError("Changed resume protocol")
    if sha((root / "capture_csl_trade_sources.py").read_bytes()) != manifest["runner_sha256"]:
        raise ValueError("Changed resume runner")
    cursor, consumed = START, 0
    if manifest.get("resume_parent"):
        parent = manifest["resume_parent"]
        if sha((Path(parent["archive"]) / "manifest.json").read_bytes()) != parent["manifest_sha256"]:
            raise ValueError("Changed parent resume manifest")
        cursor, consumed, _ = resume_ib(Path(parent["archive"]))
    for receipt in manifest["requests"]:
        blob = (root / receipt["path"]).read_bytes()
        if sha(blob) != receipt["sha256"] or sha(gzip.decompress(blob)) != receipt["response_sha256"]:
            raise ValueError("Changed resume payload")
        if receipt["parameters"]["endDateTime"]:
            continue
        if not receipt["complete_callback"] or receipt["error_codes"]:
            break
        expected = datetime.fromtimestamp(cursor, UTC).strftime("%Y%m%d %H:%M:%S UTC")
        if receipt["parameters"]["startDateTime"] != expected:
            raise ValueError("Gap in resume pages")
        rows = json.loads(gzip.decompress(blob))["rows"]
        if len(rows) != receipt["row_count"]:
            raise ValueError("Changed resume row count")
        cursor = next_ib_second(rows, cursor)
        consumed += 1
        if not rows or cursor >= END:
            raise ValueError("Forward pagination already complete; use its existing capture")
    return cursor, consumed, {"archive": str(root), "manifest_sha256": sha(raw),
                              "completed_forward_pages": consumed, "next_cursor": cursor}


def capture_ibkr(resume: Path | None = None) -> Path:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    contract = Contract()
    fields = verified_prior("ib-contracts.json")["funds"]["CSL"]["details"]["contract"]
    for key in ("conId", "symbol", "secType", "currency", "exchange", "primaryExchange"):
        if key in fields:
            setattr(contract, key, fields[key])
    profile = InteractiveBrokersAdapter(AppSettings()).profile_for(OrderEnvironment.PAPER)
    root, manifest = new_archive("ibkr")
    manifest.update(environment="paper", client_id=29409, contract=fields)
    cursor, consumed = START, 0
    if resume is not None:
        cursor, consumed, parent = resume_ib(resume)
        manifest["resume_parent"] = parent

    class App(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.ready, self.accounts_seen = Event(), Event()
            self.accounts, self.messages, self.rows, self.events, self.ends = [], [], {}, {}, set()

        def nextValidId(self, orderId):  # noqa: N802
            self.ready.set()

        def managedAccounts(self, accountsList):  # noqa: N802
            self.accounts = [s.strip() for s in accountsList.split(",") if s.strip()]
            self.accounts_seen.set()

        def historicalTicksLast(self, reqId, ticks, done):  # noqa: N802
            self.rows[reqId].extend({"time": t.time, "price": str(t.price), "size": str(t.size),
                "exchange": t.exchange, "special_conditions": t.specialConditions,
                "past_limit": t.tickAttribLast.pastLimit, "unreported": t.tickAttribLast.unreported} for t in ticks)
            if done:
                self.ends.add(reqId)
                self.events[reqId].set()

        @compatible_ib_errors
        def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):  # noqa: N802
            self.messages.append({"request": reqId, "code": errorCode, "message": errorString})
            if reqId in self.events and errorCode not in {2188, 2174, 2176}:
                self.events[reqId].set()

        def placeOrder(self, *args, **kwargs):  # noqa: N802
            raise RuntimeError("Read-only source capture cannot place orders")

    app, worker, last_request = App(), None, 0.0

    def request(page: int, cursor: int, backward: bool = False) -> tuple[list, dict]:
        nonlocal last_request
        time.sleep(max(0, 11 - (time.monotonic() - last_request)))
        request_id = 99000 + page
        app.rows[request_id], app.events[request_id] = [], Event()
        clock = datetime.fromtimestamp(cursor, UTC).strftime("%Y%m%d %H:%M:%S UTC")
        params = {"startDateTime": "" if backward else clock,
                  "endDateTime": clock if backward else "", "numberOfTicks": 1000,
                  "whatToShow": "TRADES", "useRth": False, "ignoreSize": False}
        started = datetime.now(UTC).isoformat()
        last_request = time.monotonic()
        app.reqHistoricalTicks(request_id, contract, **params, miscOptions=[])
        app.events[request_id].wait(40)
        rows = list(app.rows[request_id])
        messages = [m for m in app.messages if m["request"] == request_id]
        checked = inspect_history(request_id in app.ends, rows, messages)
        raw = json.dumps({"symbol": "CSL", "request": params, "rows": rows, "messages": messages,
                          "started_at": started, "captured_at": datetime.now(UTC).isoformat(),
                          "complete_callback": request_id in app.ends}, sort_keys=True).encode()
        receipt = {"parameters": params, **checked, **retain(root, f"{'tail' if backward else 'trades'}-{page:02d}", raw)}
        manifest["requests"].append(receipt)
        save(root / "manifest.json", manifest)
        print(json.dumps({"provider": "ibkr", "page": page, "rows": len(rows),
                          "complete": checked["complete_callback"], "errors": checked["error_codes"]}), flush=True)
        if not checked["complete_callback"] or checked["error_codes"]:
            raise ValueError("IB history failed or incomplete")
        return rows, receipt

    try:
        app.connect(profile.host, profile.port, manifest["client_id"])
        worker = Thread(target=app.run, daemon=True)
        worker.start()
        if not app.ready.wait(10):
            raise TimeoutError("Gateway handshake timed out")
        app.reqManagedAccts()
        if not app.accounts_seen.wait(10) or not app.accounts or any(not a.startswith("DU") for a in app.accounts):
            raise ValueError("Paper account verification failed")
        manifest.update(paper_accounts_verified=True, server_version=app.serverVersion())
        for page in range(consumed + 1, 51):
            rows, receipt = request(page, cursor)
            next_cursor = next_ib_second(rows, cursor)
            receipt.update(in_day_rows=sum(START <= r["time"] < END for r in rows),
                           next_cursor=next_cursor, last_second=rows[-1]["time"] if rows else None)
            if not rows or next_cursor >= END:
                manifest.update(forward_boundary="empty_completed_response" if not rows else "next_session_observed",
                                forward_complete=True)
                break
            cursor = next_cursor
        else:
            raise ValueError("IB page bound reached")
        tail, _ = request(51, END, backward=True)
        next_ib_second(tail, START)
        manifest["status"] = "captured_pending_qualification"
    except Exception as error:
        manifest.update(status="incomplete", error_type=type(error).__name__)
    finally:
        app.disconnect()
        if worker is not None:
            worker.join(timeout=2)
        manifest.update(completed_at=datetime.now(UTC).isoformat(), messages=app.messages)
        save(root / "manifest.json", manifest)
    return root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("provider", choices=("alpaca", "ibkr"))
    parser.add_argument("--resume", type=Path, help="Verified incomplete IBKR archive; keep completed pages")
    args = parser.parse_args()
    if args.resume is not None and args.provider != "ibkr":
        parser.error("Resume applies only to IBKR")
    path = capture_alpaca() if args.provider == "alpaca" else capture_ibkr(args.resume)
    status = json.loads((path / "manifest.json").read_text())["status"]
    print(json.dumps({"archive": str(path), "status": status}), flush=True)
    return 0 if status == "captured_pending_qualification" else 1


if __name__ == "__main__":
    raise SystemExit(main())
