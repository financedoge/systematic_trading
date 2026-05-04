from __future__ import annotations

import json
import time as time_module
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from systematic_trading.domain.market import PriceBar


class YahooChartProvider:
    base_url = "https://query1.finance.yahoo.com/v8/finance/chart"
    user_agent = "Mozilla/5.0 systematic-trading/0.1"

    def __init__(self, *, adjust_prices: bool = False) -> None:
        self.adjust_prices = adjust_prices

    def fetch_daily_bars(self, symbol: str, start_date: date, end_date: date) -> list[PriceBar]:
        query = urlencode(
            {
                "period1": self._to_unix(start_date),
                "period2": self._to_unix(end_date + timedelta(days=1)),
                "interval": "1d",
                "events": "history",
            }
        )
        url = f"{self.base_url}/{symbol}?{query}"
        request = Request(url, headers={"User-Agent": self.user_agent})
        try:
            response = urlopen(request, timeout=30)
        except Exception:
            time_module.sleep(2)
            response = urlopen(request, timeout=30)

        with response:
            payload = json.loads(response.read().decode("utf-8"))

        result = payload.get("chart", {}).get("result")
        if not result:
            error = payload.get("chart", {}).get("error")
            raise ValueError(f"Yahoo chart returned no data for {symbol}: {error}")

        timestamps = result[0].get("timestamp") or []
        indicators = result[0].get("indicators", {})
        quotes = (indicators.get("quote") or [{}])[0]
        adjusted_closes = (indicators.get("adjclose") or [{}])[0].get("adjclose", [])
        bars: list[PriceBar] = []
        for index, timestamp in enumerate(timestamps):
            open_price = self._decimal_at(quotes, "open", index)
            high = self._decimal_at(quotes, "high", index)
            low = self._decimal_at(quotes, "low", index)
            close = self._decimal_at(quotes, "close", index)
            volume = quotes.get("volume", [None] * len(timestamps))[index]
            if None in {open_price, high, low, close}:
                continue
            if self.adjust_prices:
                adjusted_close = self._decimal_from_list(adjusted_closes, index)
                if adjusted_close is None or close == Decimal("0"):
                    continue
                factor = adjusted_close / close
                open_price *= factor
                high *= factor
                low *= factor
                close = adjusted_close

            bars.append(
                PriceBar(
                    trade_date=datetime.fromtimestamp(timestamp, tz=UTC).date(),
                    open=open_price,
                    high=high,
                    low=low,
                    close=close,
                    volume=int(volume or 0),
                )
            )
        return bars

    @staticmethod
    def _to_unix(value: date) -> int:
        return int(datetime.combine(value, time.min, tzinfo=UTC).timestamp())

    @staticmethod
    def _decimal_at(quotes: dict[str, list[float | None]], field: str, index: int) -> Decimal | None:
        value = quotes.get(field, [None])[index]
        if value is None:
            return None
        return Decimal(str(value))

    @staticmethod
    def _decimal_from_list(values: list[float | None], index: int) -> Decimal | None:
        if index >= len(values):
            return None
        value = values[index]
        if value is None:
            return None
        return Decimal(str(value))
