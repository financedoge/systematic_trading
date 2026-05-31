from datetime import date
from decimal import Decimal

from systematic_trading.data.sec_edgar import company_facts_to_snapshots
from systematic_trading.domain.market import PriceBar


def test_company_facts_to_snapshots_uses_filing_date_as_availability() -> None:
    snapshots = company_facts_to_snapshots(
        symbol="AAPL",
        company_facts=_company_facts(),
        price_bars=[
            PriceBar(
                trade_date=date(2020, 1, 31),
                open=Decimal("10"),
                high=Decimal("10"),
                low=Decimal("10"),
                close=Decimal("10"),
                volume=1_000_000,
            )
        ],
        start_available_date=date(2020, 1, 1),
        end_available_date=date(2020, 12, 31),
    )

    assert len(snapshots) == 1
    snapshot = snapshots[0]
    assert snapshot.period_end == date(2019, 12, 31)
    assert snapshot.available_date == date(2020, 1, 31)
    assert snapshot.filing_date == date(2020, 1, 31)
    assert snapshot.gross_margin == Decimal("0.4")
    assert snapshot.free_cash_flow_margin == Decimal("0.2")
    assert snapshot.earnings_yield == Decimal("0.1")
    assert snapshot.free_cash_flow_yield == Decimal("0.2")
    assert snapshot.current_ratio == Decimal("2")


def _company_facts() -> dict[str, object]:
    return {
        "facts": {
            "dei": {
                "EntityCommonStockSharesOutstanding": {
                    "units": {
                        "shares": [
                            _instant("EntityCommonStockSharesOutstanding", 100, unit="shares"),
                        ]
                    }
                }
            },
            "us-gaap": {
                "Revenues": {"units": {"USD": [_duration("Revenues", 1000)]}},
                "GrossProfit": {"units": {"USD": [_duration("GrossProfit", 400)]}},
                "OperatingIncomeLoss": {"units": {"USD": [_duration("OperatingIncomeLoss", 150)]}},
                "NetIncomeLoss": {"units": {"USD": [_duration("NetIncomeLoss", 100)]}},
                "NetCashProvidedByUsedInOperatingActivities": {"units": {"USD": [_duration("CFO", 250)]}},
                "PaymentsToAcquirePropertyPlantAndEquipment": {"units": {"USD": [_duration("Capex", 50)]}},
                "AssetsCurrent": {"units": {"USD": [_instant("AssetsCurrent", 600)]}},
                "LiabilitiesCurrent": {"units": {"USD": [_instant("LiabilitiesCurrent", 300)]}},
                "StockholdersEquity": {"units": {"USD": [_instant("StockholdersEquity", 500)]}},
                "LongTermDebtNoncurrent": {"units": {"USD": [_instant("LongTermDebtNoncurrent", 100)]}},
                "CashAndCashEquivalentsAtCarryingValue": {"units": {"USD": [_instant("Cash", 20)]}},
                "InterestExpenseNonOperating": {"units": {"USD": [_duration("InterestExpense", 10)]}},
            },
        }
    }


def _duration(tag: str, value: int) -> dict[str, object]:
    return {
        "accn": "0000000000-20-000001",
        "form": "10-K",
        "fy": 2019,
        "fp": "FY",
        "start": "2019-01-01",
        "end": "2019-12-31",
        "filed": "2020-01-31",
        "val": value,
    }


def _instant(tag: str, value: int, *, unit: str = "USD") -> dict[str, object]:
    return {
        "accn": "0000000000-20-000001",
        "form": "10-K",
        "fy": 2019,
        "fp": "FY",
        "end": "2019-12-31",
        "filed": "2020-01-31",
        "val": value,
    }
