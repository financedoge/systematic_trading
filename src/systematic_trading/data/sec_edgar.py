from __future__ import annotations

import json
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from systematic_trading.domain.market import FundamentalSnapshot, PriceBar


SEC_TICKERS_EXCHANGE_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SEC_COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

REVENUE_TAGS = (
    "RevenueFromContractWithCustomerExcludingAssessedTax",
    "Revenues",
    "SalesRevenueNet",
)
GROSS_PROFIT_TAGS = ("GrossProfit",)
OPERATING_INCOME_TAGS = ("OperatingIncomeLoss",)
NET_INCOME_TAGS = ("NetIncomeLoss",)
EPS_TAGS = ("EarningsPerShareDiluted", "EarningsPerShareBasic")
CFO_TAGS = ("NetCashProvidedByUsedInOperatingActivities",)
CAPEX_TAGS = ("PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets")
ASSETS_TAGS = ("Assets",)
CURRENT_ASSETS_TAGS = ("AssetsCurrent",)
CURRENT_LIABILITIES_TAGS = ("LiabilitiesCurrent",)
EQUITY_TAGS = ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest")
CASH_TAGS = ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents")
DEBT_TAGS = (
    "ShortTermBorrowings",
    "ShortTermDebt",
    "LongTermDebtCurrent",
    "LongTermDebtAndFinanceLeaseObligationsCurrent",
    "LongTermDebtNoncurrent",
    "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
)
INTEREST_TAGS = ("InterestExpenseNonOperating", "InterestExpense")
SHARES_TAGS = ("EntityCommonStockSharesOutstanding", "CommonStocksIncludingAdditionalPaidInCapital")


class SecEdgarClient:
    def __init__(self, *, user_agent: str, timeout_seconds: int = 60) -> None:
        self.user_agent = user_agent
        self.timeout_seconds = timeout_seconds

    def fetch_ticker_cik_map(self) -> dict[str, int]:
        payload = self._get_json(SEC_TICKERS_EXCHANGE_URL)
        fields = payload.get("fields", [])
        data = payload.get("data", [])
        try:
            ticker_index = fields.index("ticker")
            cik_index = fields.index("cik")
        except ValueError as exc:
            raise ValueError("Unexpected SEC ticker mapping format.") from exc
        return {
            str(row[ticker_index]).upper(): int(row[cik_index])
            for row in data
            if row and row[ticker_index] and row[cik_index]
        }

    def fetch_company_facts(self, cik: int) -> dict[str, Any]:
        return self._get_json(SEC_COMPANY_FACTS_URL.format(cik=cik))

    def _get_json(self, url: str) -> dict[str, Any]:
        request = Request(
            url,
            headers={
                "User-Agent": self.user_agent,
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            if exc.code == 403:
                raise RuntimeError(
                    "SEC EDGAR returned HTTP 403. Set ST_SEC_USER_AGENT or pass --user-agent "
                    "with a declared name and contact email, per SEC fair-access guidance."
                ) from exc
            raise
        except URLError as exc:
            raise RuntimeError(f"SEC EDGAR request failed: {exc}") from exc


def company_facts_to_snapshots(
    *,
    symbol: str,
    company_facts: Mapping[str, Any],
    price_bars: Sequence[PriceBar] = (),
    start_available_date: date | None = None,
    end_available_date: date | None = None,
) -> list[FundamentalSnapshot]:
    concepts = company_facts.get("facts", {}).get("us-gaap", {})
    dei_concepts = company_facts.get("facts", {}).get("dei", {})
    report_keys = _report_keys(concepts)
    snapshots: list[FundamentalSnapshot] = []
    previous_by_fp: dict[tuple[str, str], dict[str, Decimal | None]] = {}
    prices_by_date = {bar.trade_date: bar.close for bar in price_bars}

    for key in sorted(report_keys, key=lambda item: (item["filed"], item["end"], item["accession"])):
        available_date = key["filed"]
        if start_available_date is not None and available_date < start_available_date:
            continue
        if end_available_date is not None and available_date > end_available_date:
            continue

        revenue = _duration_value(concepts, REVENUE_TAGS, key)
        gross_profit = _duration_value(concepts, GROSS_PROFIT_TAGS, key)
        operating_income = _duration_value(concepts, OPERATING_INCOME_TAGS, key)
        net_income = _duration_value(concepts, NET_INCOME_TAGS, key)
        eps = _duration_value(concepts, EPS_TAGS, key, unit_preference=("USD/shares", "USD-per-shares"))
        cfo = _duration_value(concepts, CFO_TAGS, key)
        capex = _duration_value(concepts, CAPEX_TAGS, key)
        fcf = None if cfo is None else cfo - abs(capex or Decimal("0"))
        assets = _instant_value(concepts, ASSETS_TAGS, key)
        current_assets = _instant_value(concepts, CURRENT_ASSETS_TAGS, key)
        current_liabilities = _instant_value(concepts, CURRENT_LIABILITIES_TAGS, key)
        equity = _instant_value(concepts, EQUITY_TAGS, key)
        cash = _instant_value(concepts, CASH_TAGS, key)
        debt = _debt_value(concepts, key)
        interest = _duration_value(concepts, INTEREST_TAGS, key)
        shares = _instant_value(dei_concepts, SHARES_TAGS, key, unit_preference=("shares",))
        market_cap = _market_cap(shares, prices_by_date, available_date)

        fp_key = (key["form"], key["fp"])
        previous = previous_by_fp.get(fp_key, {})
        previous_by_fp[fp_key] = {"revenue": revenue, "eps": eps}

        revenue_growth = _growth(revenue, previous.get("revenue"))
        eps_growth = _growth(eps, previous.get("eps"))
        annualization = Decimal("4") if key["form"] == "10-Q" else Decimal("1")
        annualized_net_income = net_income * annualization if net_income is not None else None
        annualized_fcf = fcf * annualization if fcf is not None else None

        snapshots.append(
            FundamentalSnapshot(
                symbol=symbol.upper(),
                period_end=key["end"],
                filing_date=available_date,
                available_date=available_date,
                source=f"sec-companyfacts:{key['accession']}",
                revenue_growth_yoy=revenue_growth,
                eps_growth_yoy=eps_growth,
                gross_margin=_safe_ratio(gross_profit, revenue),
                operating_margin=_safe_ratio(operating_income, revenue),
                net_margin=_safe_ratio(net_income, revenue),
                return_on_equity=_safe_ratio(annualized_net_income, equity),
                free_cash_flow_margin=_safe_ratio(fcf, revenue),
                pe_ratio=_safe_ratio(market_cap, annualized_net_income),
                pb_ratio=_safe_ratio(market_cap, equity),
                earnings_yield=_safe_ratio(annualized_net_income, market_cap),
                free_cash_flow_yield=_safe_ratio(annualized_fcf, market_cap),
                debt_to_equity=_safe_ratio(debt, equity),
                net_debt_to_ebitda=_safe_ratio(None if debt is None else debt - (cash or Decimal("0")), operating_income),
                interest_coverage=_safe_ratio(operating_income, interest),
                current_ratio=_safe_ratio(current_assets, current_liabilities),
                notes=(
                    "Derived from SEC Company Facts XBRL. Quarterly valuation yields are annualized; "
                    "line-item taxonomy mapping is approximate."
                ),
            )
        )

    return snapshots


def _report_keys(concepts: Mapping[str, Any]) -> list[dict[str, Any]]:
    keys: dict[tuple[str, str, str], dict[str, Any]] = {}
    for tag in (*REVENUE_TAGS, *NET_INCOME_TAGS, *ASSETS_TAGS):
        for record in _records(concepts, tag):
            if record.get("form") not in {"10-K", "10-Q"}:
                continue
            if not record.get("filed") or not record.get("end") or not record.get("accn"):
                continue
            key = (str(record["accn"]), str(record["end"]), str(record["filed"]))
            keys[key] = {
                "accession": str(record["accn"]),
                "end": _parse_date(record["end"]),
                "filed": _parse_date(record["filed"]),
                "form": str(record.get("form")),
                "fy": str(record.get("fy") or ""),
                "fp": str(record.get("fp") or ""),
            }
    return list(keys.values())


def _records(concepts: Mapping[str, Any], tag: str, unit_preference: Sequence[str] = ("USD",)) -> list[Mapping[str, Any]]:
    concept = concepts.get(tag)
    if not concept:
        return []
    units = concept.get("units", {})
    for unit in unit_preference:
        if unit in units:
            return list(units[unit])
    for records in units.values():
        return list(records)
    return []


def _duration_value(
    concepts: Mapping[str, Any],
    tags: Sequence[str],
    key: Mapping[str, Any],
    unit_preference: Sequence[str] = ("USD",),
) -> Decimal | None:
    candidates: list[Mapping[str, Any]] = []
    for tag in tags:
        candidates.extend(_matching_records(concepts, tag, key, unit_preference=unit_preference, require_start=True))
    if not candidates:
        return None
    if key["form"] == "10-K":
        selected = max(candidates, key=_duration_days)
    else:
        selected = min(candidates, key=_duration_days)
    return _decimal(selected.get("val"))


def _instant_value(
    concepts: Mapping[str, Any],
    tags: Sequence[str],
    key: Mapping[str, Any],
    unit_preference: Sequence[str] = ("USD",),
) -> Decimal | None:
    candidates: list[Mapping[str, Any]] = []
    for tag in tags:
        candidates.extend(_matching_records(concepts, tag, key, unit_preference=unit_preference, require_start=False))
    if not candidates:
        return None
    selected = max(candidates, key=lambda item: (str(item.get("filed", "")), str(item.get("end", ""))))
    return _decimal(selected.get("val"))


def _debt_value(concepts: Mapping[str, Any], key: Mapping[str, Any]) -> Decimal | None:
    values = [_instant_value(concepts, (tag,), key) for tag in DEBT_TAGS]
    present = [value for value in values if value is not None]
    if not present:
        return None
    return sum(present, Decimal("0"))


def _matching_records(
    concepts: Mapping[str, Any],
    tag: str,
    key: Mapping[str, Any],
    *,
    unit_preference: Sequence[str],
    require_start: bool,
) -> list[Mapping[str, Any]]:
    matches = []
    for record in _records(concepts, tag, unit_preference=unit_preference):
        if str(record.get("accn")) != key["accession"]:
            continue
        if str(record.get("end")) != key["end"].isoformat():
            continue
        if require_start and not record.get("start"):
            continue
        matches.append(record)
    return matches


def _duration_days(record: Mapping[str, Any]) -> int:
    start = record.get("start")
    end = record.get("end")
    if not start or not end:
        return 0
    return (_parse_date(end) - _parse_date(start)).days


def _market_cap(shares: Decimal | None, prices_by_date: Mapping[date, Decimal], available_date: date) -> Decimal | None:
    if shares is None or not prices_by_date:
        return None
    available_prices = [price_date for price_date in prices_by_date if price_date <= available_date]
    if not available_prices:
        return None
    return shares * prices_by_date[max(available_prices)]


def _growth(current: Decimal | None, previous: Decimal | None) -> Decimal | None:
    if current is None or previous is None or previous == Decimal("0"):
        return None
    return (current / previous) - Decimal("1")


def _safe_ratio(numerator: Decimal | None, denominator: Decimal | None) -> Decimal | None:
    if numerator is None or denominator is None or denominator == Decimal("0"):
        return None
    return numerator / denominator


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    parsed = Decimal(str(value))
    return parsed if parsed.is_finite() else None


def _parse_date(value: object) -> date:
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()
