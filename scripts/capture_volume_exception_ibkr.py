"""Three predeclared paper-only IBKR Time & Sales controls for volume exceptions."""
from __future__ import annotations

import argparse
from datetime import UTC, datetime
import json
from pathlib import Path
from threading import Event, Thread
import time

from acquire_mdy_ibkr_history import verified_prior
from capture_csl_trade_sources import next_ib_second, retain
from capture_volume_exception_trades import archive, key, protocol, verified_payload, window
from probe_alpaca_sip_source import save
from probe_ibkr_source_access import inspect_history
from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.execution.ib_compat import compatible_ib_errors


def saved_progress(root: Path, manifest: dict, case: dict) -> tuple[int, int, bool, bool]:
    start, end = window(case)
    cursor, pages, boundary, tail = start, 0, False, False
    for receipt in manifest["requests"]:
        if receipt["case"] != key(case):
            continue
        payload = verified_payload(root, receipt)
        if not receipt["complete_callback"] or receipt["error_codes"]:
            continue
        rows = payload["rows"]
        if len(rows) != receipt["row_count"]:
            raise ValueError("Changed IB control row count")
        if receipt["direction"] == "tail":
            if not boundary:
                raise ValueError("Tail precedes forward completion")
            tail = True
            continue
        if boundary:
            raise ValueError("Forward pages continue beyond completion")
        expected = datetime.fromtimestamp(cursor, UTC).strftime("%Y%m%d %H:%M:%S UTC")
        if receipt["parameters"]["startDateTime"] != expected:
            raise ValueError("Gap in saved IB control")
        cursor = next_ib_second(rows, cursor)
        pages += 1
        boundary = not rows or cursor >= end
    return cursor, pages, boundary, tail


def capture(resume: Path | None = None) -> Path:
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    root, manifest = archive("ibkr", resume, Path(__file__))
    contracts = verified_prior("ib-contracts.json")["funds"]
    profile = InteractiveBrokersAdapter(AppSettings()).profile_for(OrderEnvironment.PAPER)
    manifest.update(environment="paper", client_id=29410)

    class App(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.ready, self.accounts_seen = Event(), Event()
            self.accounts, self.messages, self.rows, self.events, self.ends = [], [], {}, {}, set()

        def nextValidId(self, orderId):  # noqa: N802
            self.ready.set()

        def managedAccounts(self, accountsList):  # noqa: N802
            self.accounts = [v.strip() for v in accountsList.split(",") if v.strip()]
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
            raise RuntimeError("Read-only source inspection cannot place orders")

    app, worker, last_request = None, None, 0.0

    def disconnect():
        if app is not None:
            app.disconnect()
            manifest.setdefault("connection_messages", []).append(app.messages)
        if worker is not None:
            worker.join(timeout=2)

    def connect():
        nonlocal app, worker
        app = App()
        app.connect(profile.host, profile.port, manifest["client_id"])
        worker = Thread(target=app.run, daemon=True)
        worker.start()
        if not app.ready.wait(10):
            raise TimeoutError("Gateway handshake timed out")
        app.reqManagedAccts()
        if not app.accounts_seen.wait(10) or not app.accounts or any(not a.startswith("DU") for a in app.accounts):
            raise ValueError("Paper account check failed")
        manifest.update(paper_accounts_verified=True, server_version=app.serverVersion())

    def request(case: dict, cursor: int, direction: str) -> list:
        nonlocal last_request
        contract = Contract()
        fields = contracts[case["symbol"]]["details"]["contract"]
        for name in ("conId", "symbol", "secType", "currency", "exchange", "primaryExchange"):
            if name in fields:
                setattr(contract, name, fields[name])
        clock = datetime.fromtimestamp(cursor, UTC).strftime("%Y%m%d %H:%M:%S UTC")
        params = {"startDateTime": clock if direction == "forward" else "",
                  "endDateTime": clock if direction == "tail" else "", "numberOfTicks": 1000,
                  "whatToShow": "TRADES", "useRth": False, "ignoreSize": False}
        while True:
            time.sleep(max(0, 11 - (time.monotonic() - last_request)))
            req = 110000 + len(manifest["requests"])
            app.rows[req], app.events[req] = [], Event()
            started = datetime.now(UTC).isoformat()
            last_request = time.monotonic()
            app.reqHistoricalTicks(req, contract, **params, miscOptions=[])
            app.events[req].wait(40)
            rows = list(app.rows[req])
            messages = [m for m in app.messages if m["request"] == req]
            checked = inspect_history(req in app.ends, rows, messages)
            payload = {"symbol": case["symbol"], "date": case["date"], "contract": fields,
                       "request": params, "rows": rows, "messages": messages,
                       "started_at": started, "captured_at": datetime.now(UTC).isoformat(),
                       "complete_callback": checked["complete_callback"]}
            receipt = {"case": key(case), "direction": direction, "parameters": params, **checked,
                       **retain(root, f"{key(case)}-{len(manifest['requests']) + 1:04d}", json.dumps(payload, sort_keys=True).encode())}
            manifest["requests"].append(receipt)
            save(root / "manifest.json", manifest)
            print(json.dumps({"case": key(case), "direction": direction, "request": len(manifest["requests"]),
                              "rows": len(rows), "complete": checked["complete_callback"], "errors": checked["error_codes"]}), flush=True)
            if checked["complete_callback"] and not checked["error_codes"]:
                return rows
            if checked["error_codes"] or manifest.get("reconnections", 0) >= 2:
                raise ValueError("IB control request failed")
            disconnect()
            manifest["reconnections"] = manifest.get("reconnections", 0) + 1
            time.sleep(1)
            connect()

    try:
        connect()
        for control in protocol()["ibkr_tick_controls"]:
            case = next(c for c in protocol()["cases"] if key(c) == key(control))
            cursor, pages, boundary, tail = saved_progress(root, manifest, case)
            start, end = window(case)
            while not boundary and pages < 100:
                rows = request(case, cursor, "forward")
                cursor = next_ib_second(rows, cursor)
                pages += 1
                boundary = not rows or cursor >= end
            if not boundary:
                raise ValueError("IB page bound reached")
            if not tail:
                rows = request(case, end, "tail")
                next_ib_second(rows, start)
            manifest["cases"][key(case)] = {"forward_pages": pages, "complete": True, "backward_check_captured": True}
            save(root / "manifest.json", manifest)
        manifest["status"] = "captured_pending_qualification"
    except Exception as error:
        manifest.update(status="incomplete", error_type=type(error).__name__)
    finally:
        disconnect()
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
