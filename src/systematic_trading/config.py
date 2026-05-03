from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

from systematic_trading.domain.enums import Currency, OrderEnvironment


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="ST_",
        extra="ignore",
    )

    app_name: str = "systematic-trading"
    base_currency: Currency = Currency.CNH
    default_environment: OrderEnvironment = OrderEnvironment.PAPER

    ib_host: str = "127.0.0.1"
    ib_paper_port: int = 7497
    ib_live_port: int = 7496
    ib_client_id: int = 101

    data_dir: Path = Path("var")
    database_path: Path = Path("var/systematic_trading.db")

    primary_eod_provider: str = "UNSET"
    primary_eod_api_key: str | None = None
    openai_api_key: str | None = None
    sec_user_agent: str = "systematic-trading/0.1"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
