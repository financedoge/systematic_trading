from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Iterable, Mapping

from systematic_trading.domain.enums import Currency
from systematic_trading.domain.portfolio import CashBalance, PortfolioPosition, PortfolioSnapshot

MONEY_STEP = Decimal("0.01")
RATE_STEP = Decimal("0.0000001")


def quantize_money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY_STEP, rounding=ROUND_HALF_UP)


class FxConverter:
    def __init__(self, rates_to_cnh: Mapping[Currency | str, Decimal | str]) -> None:
        self._rates: dict[Currency, Decimal] = {Currency.CNH: Decimal("1")}
        for currency, rate in rates_to_cnh.items():
            code = currency if isinstance(currency, Currency) else Currency(currency)
            self._rates[code] = Decimal(rate)

    def rate(self, base: Currency | str, quote: Currency | str = Currency.CNH) -> Decimal:
        base_code = base if isinstance(base, Currency) else Currency(base)
        quote_code = quote if isinstance(quote, Currency) else Currency(quote)

        if base_code == quote_code:
            return Decimal("1")

        try:
            base_to_cnh = self._rates[base_code]
            quote_to_cnh = self._rates[quote_code]
        except KeyError as exc:
            raise KeyError(f"Missing FX rate for {exc.args[0]}") from exc

        return (base_to_cnh / quote_to_cnh).quantize(RATE_STEP, rounding=ROUND_HALF_UP)

    def convert(
        self,
        amount: Decimal | str,
        base: Currency | str,
        quote: Currency | str = Currency.CNH,
    ) -> Decimal:
        return quantize_money(Decimal(amount) * self.rate(base, quote))


class InsufficientCashError(ValueError):
    """Raised when the cash ledger cannot fund a requested trade."""


class CashLedger:
    def __init__(self, balances: Iterable[CashBalance] | None = None) -> None:
        self._balances: dict[Currency, Decimal] = defaultdict(lambda: Decimal("0.00"))
        for balance in balances or []:
            self.deposit(balance.currency, balance.amount)

    def balance(self, currency: Currency | str) -> Decimal:
        code = currency if isinstance(currency, Currency) else Currency(currency)
        return quantize_money(self._balances[code])

    def deposit(self, currency: Currency | str, amount: Decimal | str) -> None:
        code = currency if isinstance(currency, Currency) else Currency(currency)
        self._balances[code] += quantize_money(Decimal(amount))

    def withdraw(self, currency: Currency | str, amount: Decimal | str) -> None:
        code = currency if isinstance(currency, Currency) else Currency(currency)
        cash_amount = quantize_money(Decimal(amount))
        if self.balance(code) < cash_amount:
            raise InsufficientCashError(f"Insufficient cash in {code}")
        self._balances[code] = quantize_money(self._balances[code] - cash_amount)

    def fund_and_withdraw(
        self,
        target_currency: Currency | str,
        amount: Decimal | str,
        converter: FxConverter,
        preferred_source: Currency = Currency.CNH,
    ) -> None:
        target_code = target_currency if isinstance(target_currency, Currency) else Currency(target_currency)
        target_amount = quantize_money(Decimal(amount))
        shortfall = quantize_money(target_amount - self.balance(target_code))
        if shortfall > 0:
            source_required = converter.convert(shortfall, target_code, preferred_source)
            self.withdraw(preferred_source, source_required)
            self.deposit(target_code, shortfall)
        self.withdraw(target_code, target_amount)

    def snapshot(self) -> list[CashBalance]:
        balances = []
        for currency in sorted(self._balances, key=lambda item: item.value):
            balance = self.balance(currency)
            if balance != Decimal("0.00"):
                balances.append(CashBalance(currency=currency, amount=balance))
        return balances

    def total_in_cnh(self, converter: FxConverter) -> Decimal:
        total = Decimal("0.00")
        for balance in self.snapshot():
            total += converter.convert(balance.amount, balance.currency, Currency.CNH)
        return quantize_money(total)


class PortfolioValuationService:
    @staticmethod
    def build_snapshot(
        *,
        as_of: date,
        positions: Iterable[PortfolioPosition],
        cash: Iterable[CashBalance],
        converter: FxConverter,
        base_currency: Currency = Currency.CNH,
    ) -> PortfolioSnapshot:
        gross_exposure_cnh = Decimal("0.00")
        nav_cnh = Decimal("0.00")
        country_exposure: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        currency_exposure: dict[Currency, Decimal] = defaultdict(lambda: Decimal("0.00"))

        normalized_positions = list(positions)
        normalized_cash = list(cash)

        for position in normalized_positions:
            position_value_local = Decimal(position.quantity) * position.market_price
            position_value_cnh = converter.convert(position_value_local, position.currency, Currency.CNH)
            gross_exposure_cnh += position_value_cnh
            nav_cnh += position_value_cnh
            country_exposure[position.country] += position_value_cnh
            currency_exposure[position.currency] += position_value_cnh

        for balance in normalized_cash:
            balance_cnh = converter.convert(balance.amount, balance.currency, Currency.CNH)
            nav_cnh += balance_cnh
            currency_exposure[balance.currency] += balance_cnh

        return PortfolioSnapshot(
            as_of=as_of,
            base_currency=base_currency,
            cash=normalized_cash,
            positions=normalized_positions,
            nav_cnh=quantize_money(nav_cnh),
            gross_exposure_cnh=quantize_money(gross_exposure_cnh),
            country_exposure_cnh={
                country: quantize_money(amount) for country, amount in sorted(country_exposure.items())
            },
            currency_exposure_cnh={
                currency: quantize_money(amount) for currency, amount in sorted(currency_exposure.items(), key=lambda item: item[0].value)
            },
        )
