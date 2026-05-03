from decimal import Decimal

from systematic_trading.backtest.accounting import CashLedger, FxConverter
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.portfolio import CashBalance


def test_cash_ledger_can_fund_usd_purchase_from_cnh() -> None:
    converter = FxConverter({Currency.USD: Decimal("7.20")})
    ledger = CashLedger([CashBalance(currency=Currency.CNH, amount=Decimal("10000"))])

    ledger.fund_and_withdraw(Currency.USD, Decimal("100"), converter)

    assert ledger.balance(Currency.CNH) == Decimal("9280.00")
    assert ledger.balance(Currency.USD) == Decimal("0.00")
