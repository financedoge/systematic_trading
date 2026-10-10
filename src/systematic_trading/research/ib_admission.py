"""Read-only, paper-environment ETF identity evidence; never order permission."""
from datetime import UTC, datetime
from threading import Event, Thread

from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.execution.ib_compat import compatible_ib_errors
from systematic_trading.execution.ib_health import gateway_connection_issue


def validate_contract(fund, details):
    """Require one ISIN lookup result matching the issuer's tradable identity."""
    if len(details) != 1:
        raise ValueError("Missing or ambiguous IB contract: " + fund["symbol"])
    row = details[0]
    contract = row["contract"]
    if (contract.get("symbol") != fund["symbol"] or contract.get("secType") != "STK"
            or contract.get("currency") != fund["currency"]
            or contract.get("primaryExchange") != "ARCA"
            or not isinstance(contract.get("conId"), int) or contract["conId"] <= 0
            or "SMART" not in row.get("validExchanges", "").split(",")):
        raise ValueError("IB/issuer contract identity disagreement: " + fund["symbol"])
    isins = [r["value"] for r in row.get("secIdList", []) if r["tag"].upper() == "ISIN"]
    if isins and set(isins) != {fund["isin"]}:
        raise ValueError("IB/issuer ISIN disagreement: " + fund["symbol"])
    return dict(status="identity_verified", lookup=dict(secIdType="ISIN", secId=fund["isin"]),
                details=row, account_permission="unverified", settlement_eligibility="unverified",
                limitation="Contract discovery is not product permission, an order preview or an execution test.")


def qualify_funds(settings, funds, *, client_id=281, timeout=12):
    from ibapi.client import EClient
    from ibapi.contract import Contract
    from ibapi.wrapper import EWrapper

    profile = InteractiveBrokersAdapter(settings).profile_for(OrderEnvironment.PAPER)

    class App(EWrapper, EClient):
        def __init__(self):
            EClient.__init__(self, self)
            self.ready, self.accounts_seen = Event(), Event()
            self.accounts, self.errors, self.rows, self.finished = [], [], {}, {}

        def nextValidId(self, orderId):  # noqa: N802
            self.ready.set()

        def managedAccounts(self, accountsList):  # noqa: N802
            self.accounts = [s.strip() for s in accountsList.split(",") if s.strip()]
            self.accounts_seen.set()

        def contractDetails(self, reqId, details):  # noqa: N802
            names = ("longName", "marketName", "minTick", "validExchanges", "orderTypes",
                     "timeZoneId", "tradingHours", "liquidHours", "marketRuleIds",
                     "minSize", "sizeIncrement", "suggestedSizeIncrement", "stockType")
            row = {n: str(getattr(details, n, "")) for n in names}
            row["contract"] = {n: getattr(details.contract, n, None) for n in
                               ("conId", "symbol", "secType", "currency", "exchange",
                                "primaryExchange", "localSymbol", "tradingClass")}
            row["secIdList"] = [dict(tag=p.tag, value=p.value) for p in (details.secIdList or [])]
            self.rows[reqId].append(row)

        def contractDetailsEnd(self, reqId):  # noqa: N802
            self.finished[reqId].set()

        @compatible_ib_errors
        def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):  # noqa: N802
            self.errors.append(dict(request=reqId, code=errorCode, message=errorString))
            if reqId in self.finished:
                self.finished[reqId].set()

    result = dict(started_at=datetime.now(UTC).isoformat(), environment="paper", client_id=client_id,
                  host=profile.host, port=profile.port, owner="read_only_research", funds={},
                  order_calls=0, account_permission="unverified", status="failed")
    app, thread = App(), None
    try:
        app.connect(profile.host, profile.port, client_id)
        thread = Thread(target=app.run, daemon=True)
        thread.start()
        if not app.ready.wait(timeout):
            raise TimeoutError("IB paper handshake timed out")
        app.reqManagedAccts()
        if not app.accounts_seen.wait(timeout) or not app.accounts or any(not a.startswith("DU") for a in app.accounts):
            raise ValueError("Expected verified paper managed accounts")
        for request, fund in enumerate(funds, start=1):
            app.rows[request], app.finished[request] = [], Event()
            contract = Contract()
            contract.secType, contract.exchange, contract.currency = "STK", "SMART", fund["currency"]
            contract.secIdType, contract.secId = "ISIN", fund["isin"]
            app.reqContractDetails(request, contract)
            try:
                if not app.finished[request].wait(timeout):
                    raise TimeoutError("IB contract lookup timed out")
                if any(e["request"] == request for e in app.errors):
                    raise ValueError("IB contract lookup returned an error")
                result["funds"][fund["symbol"]] = validate_contract(fund, app.rows[request])
            except (ValueError, TimeoutError) as exc:
                result["funds"][fund["symbol"]] = dict(status="unverified", reason=str(exc), details=app.rows[request])
        issue = gateway_connection_issue([f'{e["request"]}:{e["code"]}:{e["message"]}' for e in app.errors])
        if issue:
            raise ValueError("IB server connection unavailable: " + issue)
        result["status"] = "identity_verified" if all(r["status"] == "identity_verified" for r in result["funds"].values()) else "incomplete"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        app.disconnect()
        if thread is not None:
            thread.join(timeout=2)
        result.update(completed_at=datetime.now(UTC).isoformat(), managed_accounts=app.accounts, messages=app.errors)
    return result
