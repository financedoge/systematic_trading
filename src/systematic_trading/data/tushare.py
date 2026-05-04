from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

from systematic_trading.data.providers import DataSourceManifest, DataSourceType, MarketDataProvider, ProviderCapability
from systematic_trading.domain.market import PriceBar


DEFAULT_TUSHARE_TOKEN_PATH = Path("tushare_token.txt")


def read_tushare_token(token_path: Path = DEFAULT_TUSHARE_TOKEN_PATH) -> str | None:
    path = Path(token_path)
    if not path.exists():
        return None
    try:
        token = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return token or None


class TushareUsDailyProvider(MarketDataProvider):
    def __init__(
        self,
        *,
        token_path: Path = DEFAULT_TUSHARE_TOKEN_PATH,
        adjusted: bool = True,
    ) -> None:
        self.token_path = Path(token_path)
        self.adjusted = adjusted
        self._token = read_tushare_token(self.token_path)
        self.manifest = DataSourceManifest(
            source_id="tushare",
            name="Tushare Pro",
            source_type=DataSourceType.MARKET_DATA,
            regions=["China", "US"],
            capabilities=[ProviderCapability.DAILY_BARS, ProviderCapability.CORPORATE_ACTIONS],
            configured=self._token is not None,
            notes=(
                "Reads the token from tushare_token.txt by default. US bars use us_daily_adj when adjusted=True; "
                "install the optional tushare SDK before fetching."
            ),
        )

    def fetch_daily_bars(self, symbols: Sequence[str], start_date: date, end_date: date) -> dict[str, list[PriceBar]]:
        if self._token is None:
            raise ValueError(f"Tushare token was not found at {self.token_path}.")

        pro = self._client()
        method_name = "us_daily_adj" if self.adjusted else "us_daily"
        method = getattr(pro, method_name)
        results: dict[str, list[PriceBar]] = {}
        for symbol in symbols:
            frame = method(
                ts_code=symbol,
                start_date=_tushare_date(start_date),
                end_date=_tushare_date(end_date),
            )
            results[symbol] = _bars_from_records(_records(frame), adjusted=self.adjusted)
        return results

    def _client(self) -> Any:
        try:
            import tushare as ts
        except ImportError as exc:
            raise RuntimeError("Install the optional tushare SDK to use TushareUsDailyProvider.") from exc
        return ts.pro_api(self._token)


def _records(frame: Any) -> list[dict[str, Any]]:
    if frame is None:
        return []
    if hasattr(frame, "to_dict"):
        return list(frame.to_dict("records"))
    return list(frame)


def _bars_from_records(records: list[dict[str, Any]], *, adjusted: bool) -> list[PriceBar]:
    bars: list[PriceBar] = []
    for row in records:
        factor = _decimal(row.get("adj_factor")) if adjusted and row.get("adj_factor") is not None else Decimal("1")
        open_price = _decimal(row.get("open")) * factor
        high = _decimal(row.get("high")) * factor
        low = _decimal(row.get("low")) * factor
        close = _decimal(row.get("close")) * factor
        if min(open_price, high, low, close) <= Decimal("0"):
            continue
        bars.append(
            PriceBar(
                trade_date=datetime.strptime(str(row["trade_date"]), "%Y%m%d").date(),
                open=open_price,
                high=high,
                low=low,
                close=close,
                volume=int(_decimal(row.get("vol", 0))),
            )
        )
    return sorted(bars, key=lambda item: item.trade_date)


def _decimal(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")
    parsed = Decimal(str(value))
    return parsed if parsed.is_finite() else Decimal("0")


def _tushare_date(value: date) -> str:
    return value.strftime("%Y%m%d")
