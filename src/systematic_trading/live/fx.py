from datetime import date, timedelta
from pydantic import BaseModel, Field

from systematic_trading.domain.enums import Currency
from systematic_trading.domain.market import FXRate


class FXRefreshResult(BaseModel):
    rates_upserted: int = 0
    latest_dates: dict[str, date | None] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


def refresh_required_fx(*, store, target_date, currencies, provider):
    result = FXRefreshResult()
    for currency in sorted(set(currencies) - {Currency.CNH}):
        existing = store.list_fx_rates(currency, end_date=target_date)
        if not existing or existing[-1].rate_date != target_date:
            # Readiness refresh is bounded; historical gaps remain visible to data audit.
            start = max(existing[-1].rate_date + timedelta(days=1) if existing else target_date,
                target_date - timedelta(days=7))
            try:
                bars = provider.fetch_daily_bars(f"{currency.value}/CNH", start, target_date)
                observed = [bar for bar in bars if start <= bar.trade_date <= target_date]
                for bar in observed:
                    store.upsert_fx_rate(FXRate(rate_date=bar.trade_date, base_currency=currency, rate=bar.close))
                    result.rates_upserted += 1
                if not any(bar.trade_date == target_date for bar in observed):
                    result.warnings.append(f"{currency.value}/CNH: no observed FX close for {target_date}.")
            except Exception as exc:
                result.warnings.append(f"{currency.value}/CNH refresh failed: {exc}")
        rates = store.list_fx_rates(currency, end_date=target_date)
        result.latest_dates[currency.value] = rates[-1].rate_date if rates else None
    return result
