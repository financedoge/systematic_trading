from datetime import date
from decimal import Decimal

from scripts.fetch_ib_paper_account_snapshot import AccountSummaryRow, IbPositionRow, build_live_snapshot
from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import Currency
from systematic_trading.live.account_snapshot import fetch_and_write_account_snapshot


def test_build_live_snapshot_prefers_total_cash_and_keeps_sota_positions() -> None:
    result = build_live_snapshot(
        summary_rows=[
            AccountSummaryRow(account="DU1", tag="CashBalance", value="900", currency="USD"),
            AccountSummaryRow(account="DU1", tag="TotalCashValue", value="1000", currency="USD"),
            AccountSummaryRow(account="DU1", tag="TotalCashValue", value="0", currency="BASE"),
        ],
        position_rows=[
            IbPositionRow(
                account="DU1",
                symbol="SPY",
                security_type="STK",
                currency="USD",
                quantity=Decimal("3"),
                average_cost=Decimal("500.25"),
            )
        ],
        as_of=date(2026, 4, 29),
        sota_universe_only=True,
    )

    assert result.snapshot.as_of == date(2026, 4, 29)
    assert result.snapshot.cash[0].currency == Currency.USD
    assert result.snapshot.cash[0].amount == Decimal("1000")
    assert result.snapshot.positions[0].symbol == "SPY"
    assert result.snapshot.positions[0].quantity == 3
    assert result.warnings == []


def test_build_live_snapshot_warns_for_unsupported_positions() -> None:
    result = build_live_snapshot(
        summary_rows=[AccountSummaryRow(account="DU1", tag="TotalCashValue", value="1000", currency="USD")],
        position_rows=[
            IbPositionRow(
                account="DU1",
                symbol="AAPL",
                security_type="STK",
                currency="USD",
                quantity=Decimal("1"),
                average_cost=Decimal("100"),
            ),
            IbPositionRow(
                account="DU1",
                symbol="SPY",
                security_type="STK",
                currency="USD",
                quantity=Decimal("1.5"),
                average_cost=Decimal("500"),
            ),
            IbPositionRow(
                account="DU1",
                symbol="TLT",
                security_type="STK",
                currency="USD",
                quantity=Decimal("-2"),
                average_cost=Decimal("90"),
            ),
        ],
        as_of=None,
        sota_universe_only=True,
    )

    assert result.snapshot.positions == []
    assert "ignored non-SOTA position AAPL quantity=1" in result.warnings
    assert "ignored fractional position SPY quantity=1.5; current SOTA live model uses whole shares" in result.warnings
    assert "ignored short position TLT quantity=-2; current SOTA live model is long-only" in result.warnings


def test_fetch_and_write_account_snapshot_uses_dedicated_client_id(tmp_path) -> None:
    client = _FakeAccountSnapshotClient()

    result = fetch_and_write_account_snapshot(
        settings=AppSettings(
            data_dir=tmp_path,
            database_path=tmp_path / "snapshot.db",
            ib_client_id=101,
            ib_account_snapshot_client_id=444,
        ),
        client=client,
        as_of=date(2026, 5, 20),
    )

    assert result.output_path.exists()
    assert result.snapshot.as_of == date(2026, 5, 20)
    assert client.profile.client_id == 444


class _FakeAccountSnapshotClient:
    def __init__(self) -> None:
        self.profile = None

    def fetch(self, profile):
        self.profile = profile
        return (
            [AccountSummaryRow(account="DU1", tag="TotalCashValue", value="1000", currency="USD")],
            [],
            ["DU1"],
        )
