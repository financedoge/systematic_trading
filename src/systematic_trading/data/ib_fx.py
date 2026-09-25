"""Observed IB midpoint FX closes, including auditable same-date cross rates."""
from datetime import UTC, date, datetime, time
from threading import RLock
import json
from zoneinfo import ZoneInfo

from systematic_trading.data.ib import IbApiHistoricalDataClient
from systematic_trading.domain.enums import OrderEnvironment
from systematic_trading.domain.market import PriceBar
from systematic_trading.execution.broker import InteractiveBrokersAdapter

FX_CONNECTION_LOCK = RLock()


class IbFxDailyBarProvider:
    def __init__(self, settings, *, client=None):
        self.settings = settings
        self.client = client or IbApiHistoricalDataClient(historical_timeout_seconds=15)

    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        base, quote = symbol.split("/")
        if quote != "CNH" or base not in {"USD", "HKD", "EUR", "JPY"}:
            raise ValueError(f"No verified IB FX mapping for {symbol}.")
        if datetime.now(UTC) < datetime.combine(end_date, time(17), ZoneInfo("America/New_York")):
            raise ValueError("The requested FX daily close is not complete until 17:00 New York time.")
        profile = InteractiveBrokersAdapter(self.settings).profile_for(OrderEnvironment.PAPER).model_copy(
            update={"client_id": self.settings.ib_fx_client_id or self.settings.ib_client_id + 80})
        legs = {}
        def fetch(left, right):
            bars = self.client.fetch_daily_bars(profile, left, start_date, end_date, forex_currency=right)
            bars = [bar for bar in bars if start_date <= bar.trade_date <= end_date]
            legs[f"{left}/{right}"] = [bar.model_dump(mode="json") for bar in bars]
            return {bar.trade_date: bar for bar in bars}
        with FX_CONNECTION_LOCK:
            cnh = fetch("USD", "CNH")
            if base == "USD":
                result = list(cnh.values())
                formula = "USD/CNH observed midpoint close"
            else:
                other = fetch("EUR", "USD") if base == "EUR" else fetch("USD", base)
                result = []
                for day in sorted(cnh.keys() & other.keys()):
                    left, right = cnh[day], other[day]
                    if base == "EUR":
                        prices = dict(open=left.open*right.open, high=left.high*right.high,
                            low=left.low*right.low, close=left.close*right.close)
                    else:
                        prices = dict(open=left.open/right.open, high=left.high/right.low,
                            low=left.low/right.high, close=left.close/right.close)
                    result.append(PriceBar(trade_date=day, volume=0, **prices))
                formula = "USD/CNH * EUR/USD" if base == "EUR" else f"USD/CNH / USD/{base}"
        # Preserve evidence before any caller persists normalized rates.
        directory = self.settings.data_dir / "market_data" / "fx_observations"
        directory.mkdir(parents=True, exist_ok=True)
        observed_at = datetime.now(UTC)
        payload = dict(source="interactive-brokers", data_type="MIDPOINT", pair=symbol, formula=formula,
            observed_at=observed_at.isoformat(), start_date=str(start_date), end_date=str(end_date),
            legs=legs, rates=[bar.model_dump(mode="json") for bar in result])
        (directory / f"{base}_CNH_{end_date}_{observed_at:%Y%m%dT%H%M%S%fZ}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return sorted(result, key=lambda bar: bar.trade_date)
