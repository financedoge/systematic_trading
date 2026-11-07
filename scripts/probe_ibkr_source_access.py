"""Read-only P4.21 access recheck; no paid snapshots, orders or publications."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Thread
import time

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.execution.ib_compat import compatible_ib_errors


ROOT = Path(__file__).resolve().parents[1]


def inspect_history(ended, rows, messages):
    advisory = {2104, 2106, 2107, 2108, 2158, 2174, 2176, 2188}
    errors = [m["code"] for m in messages if m["code"] not in advisory]
    return {"complete_callback": ended, "row_count": len(rows), "error_codes": errors,
            "history_returned": bool(ended and rows and not errors),
            "recent_api_subscription_warning": any(m["code"] == 2188 for m in messages)}


def main():
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--historical-ticks-only", action="store_true")
    args = parser.parse_args()

    spec = importlib.util.spec_from_file_location("mdy_ibkr", ROOT / "scripts/acquire_mdy_ibkr_history.py")
    prior = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(prior)
    contracts = prior.verified_prior("ib-contracts.json")["funds"]
    profile = InteractiveBrokersAdapter(AppSettings()).profile_for(OrderEnvironment.PAPER)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
    root = Path("D:/systematic_trading_data/source-archives/ibkr") / ("access-" + stamp)
    root.mkdir(parents=True, exist_ok=False)
    runner = Path(__file__).read_bytes()
    (root / Path(__file__).name).write_bytes(runner)
    result = {"started_at": datetime.now(UTC).isoformat(), "environment": "paper",
              "client_id": 29408, "runner_sha256": hashlib.sha256(runner).hexdigest(),
              "order_calls": 0, "regulatory_snapshots": False, "snapshots": [], "histories": [],
              "historical_tick_probe": args.historical_ticks_only}

    class App(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.ready, self.accounts_seen = Event(), Event()
            self.accounts, self.messages, self.ticks, self.rows, self.ends, self.events = [], [], {}, {}, {}, {}
            self.types = {}

        def nextValidId(self, orderId):  # noqa: N802
            self.ready.set()

        def managedAccounts(self, accountsList):  # noqa: N802
            self.accounts = [s for s in accountsList.split(",") if s]
            self.accounts_seen.set()

        def marketDataType(self, reqId, marketDataType):  # noqa: N802
            self.types[reqId] = marketDataType

        def tickPrice(self, reqId, tickType, price, attrib):  # noqa: N802
            self.ticks[reqId].append({"kind": "price", "tick_type": tickType, "value": str(price)})

        def tickSize(self, reqId, tickType, size):  # noqa: N802
            self.ticks[reqId].append({"kind": "size", "tick_type": tickType, "value": str(size)})

        def tickString(self, reqId, tickType, value):  # noqa: N802
            self.ticks[reqId].append({"kind": "string", "tick_type": tickType, "value": value})

        def tickSnapshotEnd(self, reqId):  # noqa: N802
            self.ends[reqId] = {"snapshot_end": True}
            self.events[reqId].set()

        def historicalData(self, reqId, bar):  # noqa: N802
            self.rows[reqId].append({k: str(getattr(bar, k)) for k in
                                    ("date", "open", "high", "low", "close", "volume", "wap", "barCount")})

        def historicalDataEnd(self, reqId, start, end):  # noqa: N802
            self.ends[reqId] = {"start": start, "end": end}
            self.events[reqId].set()

        def historicalTicksLast(self, reqId, ticks, done):  # noqa: N802
            self.rows[reqId].extend({"time": t.time, "price": str(t.price), "size": str(t.size),
                                     "exchange": t.exchange, "special_conditions": t.specialConditions,
                                     "past_limit": t.tickAttribLast.pastLimit,
                                     "unreported": t.tickAttribLast.unreported} for t in ticks)
            if done:
                self.ends[reqId] = {"historical_ticks_done": True}
                self.events[reqId].set()

        @compatible_ib_errors
        def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):  # noqa: N802
            self.messages.append({"request": reqId, "code": errorCode, "message": errorString})

        def placeOrder(self, *args, **kwargs):  # noqa: N802
            raise RuntimeError("Read-only client cannot place orders")

    def contract(symbol):
        c = Contract()
        fields = (contracts[symbol]["details"]["contract"] if symbol in contracts else
                  {"symbol": "SPY", "secType": "STK", "currency": "USD", "exchange": "SMART", "primaryExchange": "ARCA"})
        for key in ("conId", "symbol", "secType", "currency", "exchange", "primaryExchange"):
            if key in fields:
                setattr(c, key, fields[key])
        return c

    def retain(label, payload):
        blob = gzip.compress(json.dumps(payload, sort_keys=True).encode(), mtime=0)
        path = root / (label + ".json.gz")
        path.write_bytes(blob)
        return {"path": path.name, "sha256": hashlib.sha256(blob).hexdigest()}

    app, thread = App(), None
    try:
        app.connect(profile.host, profile.port, result["client_id"])
        thread = Thread(target=app.run, daemon=True)
        thread.start()
        if not app.ready.wait(10):
            raise TimeoutError("Gateway handshake timed out")
        app.reqManagedAccts()
        if not app.accounts_seen.wait(10) or not app.accounts or any(not a.startswith("DU") for a in app.accounts):
            raise RuntimeError("Paper account verification failed")
        result.update(paper_accounts_verified=True, server_version=app.serverVersion())
        # Saturday: frozen real-time quotes (type 2), no delayed fallback requested.
        app.reqMarketDataType(2)
        for req, symbol in enumerate(() if args.historical_ticks_only else ("CSL", "MANH", "SPY"), 96001):
            app.ticks[req], app.events[req] = [], Event()
            c = contract(symbol)
            started = datetime.now(UTC).isoformat()
            app.reqMktData(req, c, "", True, False, [])
            app.events[req].wait(13)
            if req not in app.ends:
                app.cancelMktData(req)
            messages = [m for m in app.messages if m["request"] == req]
            payload = {"symbol": symbol, "request": {"market_data_type": 2, "snapshot": True,
                       "regulatory_snapshot": False, "exchange": c.exchange},
                       "started_at": started, "captured_at": datetime.now(UTC).isoformat(),
                       "returned_market_data_type": app.types.get(req), "ticks": app.ticks[req],
                       "end": app.ends.get(req), "messages": messages}
            receipt = {"symbol": symbol, "returned_market_data_type": app.types.get(req),
                       "tick_count": len(app.ticks[req]), "message_codes": [m["code"] for m in messages],
                       **retain(symbol + "-frozen-snapshot", payload)}
            result["snapshots"].append(receipt)
            print(json.dumps(receipt), flush=True)
        for req, (bar_size, duration, end, rth) in enumerate([] if args.historical_ticks_only else [
            ("1 day", "1 W", "20250301 05:00:00 UTC", 1),
            ("1 day", "1 W", "20250301 05:00:00 UTC", 0),
            ("1 min", "1 D", "20250225 05:00:00 UTC", 0),
        ], 97001):
            app.rows[req], app.events[req] = [], Event()
            params = {"endDateTime": end, "durationStr": duration, "barSizeSetting": bar_size,
                      "whatToShow": "TRADES", "useRTH": rth, "formatDate": 2, "keepUpToDate": False}
            started = datetime.now(UTC).isoformat()
            app.reqHistoricalData(req, contract("CSL"), **params, chartOptions=[])
            done = app.events[req].wait(40)
            if not done:
                app.cancelHistoricalData(req)
            messages = [m for m in app.messages if m["request"] == req]
            payload = {"symbol": "CSL", "conId": contract("CSL").conId, "request": params,
                       "started_at": started, "captured_at": datetime.now(UTC).isoformat(),
                       "rows": app.rows[req], "end": app.ends.get(req), "messages": messages}
            receipt = {"symbol": "CSL", "request": params, **inspect_history(req in app.ends, app.rows[req], messages),
                       **retain(f"CSL-history-{req}", payload)}
            result["histories"].append(receipt)
            print(json.dumps(receipt), flush=True)
            if not receipt["history_returned"]:
                break
            time.sleep(2)
        if args.historical_ticks_only:
            req = 98001
            app.rows[req], app.events[req] = [], Event()
            params = {"startDateTime": "20250224 14:30:00 UTC", "endDateTime": "",
                      "numberOfTicks": 1000, "whatToShow": "TRADES", "useRth": False,
                      "ignoreSize": False}
            started = datetime.now(UTC).isoformat()
            app.reqHistoricalTicks(req, contract("CSL"), **params, miscOptions=[])
            app.events[req].wait(40)
            messages = [m for m in app.messages if m["request"] == req]
            payload = {"symbol": "CSL", "request": params, "started_at": started,
                       "captured_at": datetime.now(UTC).isoformat(), "rows": app.rows[req],
                       "end": app.ends.get(req), "messages": messages}
            receipt = {"symbol": "CSL", "request": params,
                       **inspect_history(req in app.ends, app.rows[req], messages),
                       **retain("CSL-historical-ticks", payload)}
            result["histories"].append(receipt)
            print(json.dumps(receipt), flush=True)
        result["status"] = "inspection_complete"
    except Exception as error:
        result.update(status="incomplete", error_type=type(error).__name__)
    finally:
        app.disconnect()
        if thread is not None:
            thread.join(timeout=2)
        result.update(completed_at=datetime.now(UTC).isoformat(), messages=app.messages)
        (root / "manifest.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"archive": str(root), "status": result["status"]}), flush=True)


if __name__ == "__main__":
    main()
