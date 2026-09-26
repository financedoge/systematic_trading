from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from decimal import Decimal
from hashlib import sha256
from typing import Any, Iterable, Sequence
from urllib.error import HTTPError

from systematic_trading.domain.market import FXRate, PriceBar

DAILY_BARS_TABLE = "market_data.daily_bars"
FX_RATES_TABLE = "market_data.fx_rates"

DAILY_BARS_DDL = """
CREATE DATABASE IF NOT EXISTS market_data;

CREATE TABLE IF NOT EXISTS market_data.daily_bars
(
    symbol LowCardinality(String),
    trade_date Date,
    open Float64,
    high Float64,
    low Float64,
    close Float64,
    volume UInt64,
    source_name LowCardinality(String),
    source_priority UInt16,
    adjustment LowCardinality(String),
    available_at DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC'),
    quality_flags Array(String),
    payload_hash String
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(trade_date)
ORDER BY (symbol, trade_date);
"""

FX_RATES_DDL = """
CREATE DATABASE IF NOT EXISTS market_data;

CREATE TABLE IF NOT EXISTS market_data.fx_rates
(
    base_currency LowCardinality(String),
    quote_currency LowCardinality(String),
    rate_date Date,
    rate Float64,
    source_name LowCardinality(String),
    source_priority UInt16,
    available_at DateTime64(3, 'UTC'),
    ingested_at DateTime64(3, 'UTC'),
    quality_flags Array(String),
    payload_hash String
)
ENGINE = ReplacingMergeTree(ingested_at)
PARTITION BY toYYYYMM(rate_date)
ORDER BY (base_currency, quote_currency, rate_date);
"""


class ClickHouseMarketDataClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8123",
        *,
        database: str = "systematic_trading",
        user: str = "st_app",
        password: str = "local-dev-change-me",
        timeout_seconds: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.database = database
        self.user = user
        self.password = password
        self.timeout_seconds = timeout_seconds

    def execute(self, sql: str) -> str:
        data = sql.encode("utf-8")
        params = urllib.parse.urlencode({"database": self.database, "user": self.user, "password": self.password})
        request = urllib.request.Request(f"{self.base_url}/?{params}", data=data, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"ClickHouse HTTP {exc.code}: {detail}") from exc

    def ensure_daily_bars_table(self) -> None:
        for statement in _split_sql_statements(DAILY_BARS_DDL):
            self.execute(statement)

    def ensure_fx_rates_table(self) -> None:
        for statement in _split_sql_statements(FX_RATES_DDL):
            self.execute(statement)

    def insert_daily_bar_rows(self, rows: Iterable[dict[str, Any]]) -> int:
        materialized = list(rows)
        if not materialized:
            return 0
        payload = "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in materialized)
        self.execute(f"INSERT INTO {DAILY_BARS_TABLE} FORMAT JSONEachRow\n{payload}")
        return len(materialized)

    def insert_fx_rate_rows(self, rows: Iterable[dict[str, Any]]) -> int:
        materialized = list(rows)
        if not materialized:
            return 0
        payload = "\n".join(json.dumps(row, sort_keys=True, separators=(",", ":")) for row in materialized)
        self.execute(f"INSERT INTO {FX_RATES_TABLE} FORMAT JSONEachRow\n{payload}")
        return len(materialized)

    def query_daily_bars(
        self,
        *,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 5000,
    ) -> list[dict[str, Any]]:
        conditions = [f"symbol = {_sql_string(symbol.upper())}"]
        if start_date is not None:
            conditions.append(f"trade_date >= {_sql_string(start_date)}")
        if end_date is not None:
            conditions.append(f"trade_date <= {_sql_string(end_date)}")
        query = f"""
            SELECT
                symbol,
                trade_date,
                open,
                high,
                low,
                close,
                volume,
                source_name,
                source_priority,
                adjustment,
                available_at,
                ingested_at,
                quality_flags,
                payload_hash
            FROM {DAILY_BARS_TABLE} FINAL
            WHERE {' AND '.join(conditions)}
            ORDER BY trade_date ASC
            LIMIT {int(limit)}
            FORMAT JSONEachRow
        """
        response = self.execute(query)
        return [json.loads(line) for line in response.splitlines() if line.strip()]

    def query_daily_bar_symbols(self) -> list[dict[str, Any]]:
        query = f"""
            SELECT
                symbol,
                count() AS row_count,
                min(trade_date) AS first_trade_date,
                max(trade_date) AS last_trade_date
            FROM {DAILY_BARS_TABLE} FINAL
            GROUP BY symbol
            ORDER BY symbol ASC
            FORMAT JSONEachRow
        """
        response = self.execute(query)
        return [json.loads(line) for line in response.splitlines() if line.strip()]

    def query_daily_bar_dates(
        self,
        *,
        symbol: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[str]:
        conditions = [f"symbol = {_sql_string(symbol.upper())}"]
        if start_date is not None:
            conditions.append(f"trade_date >= {_sql_string(start_date)}")
        if end_date is not None:
            conditions.append(f"trade_date <= {_sql_string(end_date)}")
        query = f"""
            SELECT trade_date
            FROM {DAILY_BARS_TABLE} FINAL
            WHERE {' AND '.join(conditions)}
            ORDER BY trade_date ASC
            FORMAT JSONEachRow
        """
        response = self.execute(query)
        return [json.loads(line)["trade_date"] for line in response.splitlines() if line.strip()]

    def query_fx_rates(
        self,
        *,
        base_currency: str,
        quote_currency: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict[str, Any]]:
        conditions = [
            f"base_currency = {_sql_string(base_currency.upper())}",
            f"quote_currency = {_sql_string(quote_currency.upper())}",
        ]
        if start_date is not None:
            conditions.append(f"rate_date >= {_sql_string(start_date)}")
        if end_date is not None:
            conditions.append(f"rate_date <= {_sql_string(end_date)}")
        query = f"""
            SELECT
                base_currency,
                quote_currency,
                rate_date,
                rate,
                source_name,
                source_priority,
                available_at,
                ingested_at,
                quality_flags,
                payload_hash
            FROM {FX_RATES_TABLE} FINAL
            WHERE {' AND '.join(conditions)}
            ORDER BY rate_date ASC
            FORMAT JSONEachRow
        """
        response = self.execute(query)
        return [json.loads(line) for line in response.splitlines() if line.strip()]

    def delete_daily_bar_dates(self, *, symbol: str, trade_dates: Sequence[str]) -> int:
        dates = sorted({value for value in trade_dates if value})
        if not dates:
            return 0
        date_list = ", ".join(_sql_string(value) for value in dates)
        query = f"""
            ALTER TABLE {DAILY_BARS_TABLE}
            DELETE WHERE symbol = {_sql_string(symbol.upper())}
              AND trade_date IN ({date_list})
            SETTINGS mutations_sync = 1
        """
        self.execute(query)
        return len(dates)


def daily_bar_row(
    *,
    symbol: str,
    bar: PriceBar,
    source_name: str,
    source_priority: int = 100,
    adjustment: str = "provider_default",
    available_at: datetime | None = None,
    ingested_at: datetime | None = None,
    quality_flags: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "open": str(bar.open),
        "high": str(bar.high),
        "low": str(bar.low),
        "close": str(bar.close),
        "volume": int(bar.volume),
    }
    now = datetime.now(tz=UTC)
    return {
        "symbol": symbol.upper(),
        "trade_date": bar.trade_date.isoformat(),
        "open": float(Decimal(bar.open)),
        "high": float(Decimal(bar.high)),
        "low": float(Decimal(bar.low)),
        "close": float(Decimal(bar.close)),
        "volume": int(bar.volume),
        "source_name": source_name,
        "source_priority": int(source_priority),
        "adjustment": adjustment,
        "available_at": _iso_utc(available_at or ingested_at or now),
        "ingested_at": _iso_utc(ingested_at or now),
        "quality_flags": sorted(set(quality_flags or []) | ({"availability_unverified"} if available_at is None else set())),
        "payload_hash": canonical_payload_hash(payload),
    }


def fx_rate_row(
    *,
    rate: FXRate,
    source_name: str,
    source_priority: int = 100,
    available_at: datetime | None = None,
    ingested_at: datetime | None = None,
    quality_flags: list[str] | None = None,
) -> dict[str, Any]:
    payload = {
        "base_currency": rate.base_currency.value,
        "quote_currency": rate.quote_currency.value,
        "rate": str(rate.rate),
    }
    now = datetime.now(tz=UTC)
    return {
        "base_currency": rate.base_currency.value,
        "quote_currency": rate.quote_currency.value,
        "rate_date": rate.rate_date.isoformat(),
        "rate": float(Decimal(rate.rate)),
        "source_name": source_name,
        "source_priority": int(source_priority),
        "available_at": _iso_utc(available_at or ingested_at or now),
        "ingested_at": _iso_utc(ingested_at or now),
        "quality_flags": sorted(set(quality_flags or []) | ({"availability_unverified"} if available_at is None else set())),
        "payload_hash": canonical_payload_hash(payload),
    }


def _split_sql_statements(sql: str) -> list[str]:
    return [statement.strip() for statement in sql.split(";") if statement.strip()]


def _sql_string(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def canonical_payload_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=str,
    ).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"
