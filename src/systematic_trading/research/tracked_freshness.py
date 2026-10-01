"""Daily strategy freshness and independent, evidence-first FX catch-up."""
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
import json

from systematic_trading.live.trading_calendar import latest_completed_us_session, us_trading_dates_after, previous_us_trading_day
from systematic_trading.portfolio.context import NY
from systematic_trading.research.tracked_inputs import validated_fx_observations


def refresh_tracked_fx(settings, store, *, now=None, provider=None):
    """Fill missing research FX evidence independently of account/EOD readiness."""
    path = settings.strategy_monitoring_config_path
    config = json.loads(path.read_text(encoding="utf8")) if path.exists() else {}
    if config.get("schema_version") != 2:
        return False
    now = now or datetime.now(UTC)
    end = latest_completed_us_session(now)
    if now.astimezone(NY) < datetime.combine(end, time(17), NY):
        end = previous_us_trading_day(end)
    observed, _ = validated_fx_observations((settings.data_dir / "market_data/fx_observations").glob("USD_CNH_*.json"))
    start = date.fromisoformat(config["calculation"]["legacy_fx_through"])
    missing = [d for d in us_trading_dates_after(start, end) if str(d) not in observed]
    # Bound each fetch, but always start at the earliest missing session so a
    # laptop offline for weeks cannot leave an unrecoverable historical hole.
    refreshed, remaining = observed, []
    if missing:
        through = min(end, missing[0] + timedelta(days=30))
        if provider is None:
            from systematic_trading.data.ib_fx import IbFxDailyBarProvider
            provider = IbFxDailyBarProvider(settings)
        provider.fetch_daily_bars("USD/CNH", missing[0], through)
        refreshed, _ = validated_fx_observations((settings.data_dir / "market_data/fx_observations").glob("USD_CNH_*.json"))
        remaining = [d for d in missing if d <= through and str(d) not in refreshed]
    from systematic_trading.domain.enums import Currency
    from systematic_trading.domain.market import FXRate
    # Evidence may have been saved just before a database outage. Reconcile the
    # normalized store even when acquisition has no gaps; avoid refetching or
    # treating a source file as proof that every downstream write committed.
    existing = {str(r.rate_date): r.rate for r in store.list_fx_rates(Currency.USD, start_date=start+timedelta(days=1), end_date=end)}
    changed = False
    for day, observation in refreshed.items():
        if str(start) < day <= str(end) and existing.get(day) != Decimal(str(observation["rate"])):
            store.upsert_fx_rate(FXRate(rate_date=day, base_currency=Currency.USD, rate=observation["rate"]))
            changed = True
    if remaining:
        raise ValueError(f"Strategy USD/CNH evidence unavailable from {remaining[0]}; NAV remains dated to the last supported session")
    return bool(missing) or changed


def freshness(inputs, now=None):
    expected = str(latest_completed_us_session(now))
    price, valuation = inputs.get("price_through"), inputs.get("valuation_through")
    stale = not price or not valuation or min(price, valuation) < expected
    return dict(strategy_expected_through=expected, strategy_price_through=price,
                strategy_valuation_through=valuation, strategy_stale=stale,
                strategy_freshness_message=(f"Daily strategy update pending: expected {expected}; prices {price or 'unavailable'}, "
                    f"NAV/held weights {valuation or 'unavailable'}." if stale else f"Daily strategies current through {expected}."))
