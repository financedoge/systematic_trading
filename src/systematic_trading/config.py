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
    ib_market_data_client_id: int | None = None
    ib_execution_sync_client_id: int | None = None
    ib_account_snapshot_client_id: int | None = None

    data_dir: Path = Path("var")
    database_path: Path = Path("var/systematic_trading.db")

    automation_enabled: bool = False
    automation_timezone: str = "America/New_York"
    automation_after_close_time: str = "16:20"
    automation_loop_interval_seconds: int = 15
    automation_execution_poll_seconds: int = 60
    automation_eod_retry_seconds: int = 300
    automation_queue_rebalance: bool = True
    automation_market_data_carry_forward: bool = True
    automation_market_data_carry_forward_max_calendar_days: int = 4
    execution_twap_start_time: str = "09:30"
    execution_twap_end_time: str = "10:00"
    automation_alert_dedupe_seconds: int = 3600
    automation_alert_smtp_host: str | None = None
    automation_alert_smtp_port: int = 587
    automation_alert_smtp_username: str | None = None
    automation_alert_smtp_password: str | None = None
    automation_alert_smtp_use_tls: bool = True
    automation_alert_smtp_timeout_seconds: int = 10
    automation_alert_email_from: str | None = None
    automation_alert_email_to: str | None = None

    primary_eod_provider: str = "UNSET"
    primary_eod_api_key: str | None = None
    tushare_token_path: Path = Path("tushare_token.txt")
    openai_api_key: str | None = None
    sec_user_agent: str = "systematic-trading/0.1"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
