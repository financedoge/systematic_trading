"""One portfolio episode and temporal scope for all monitoring consumers.

Accounting checkpoints are optimizations; they never define monitoring inception.
Legacy resets are resolved without rewriting their immutable evidence.
"""
from datetime import UTC, date, datetime, time, timedelta
from hashlib import sha256
from zoneinfo import ZoneInfo

from pydantic import BaseModel

NY = ZoneInfo("America/New_York")


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class PortfolioContext(BaseModel):
    schema_version: int = 1
    portfolio_id: str = "default-paper"
    episode_id: str = "legacy"
    environment: str = "paper"
    account_id: str | None = None
    start_date: date | None = None
    cutoff_at: datetime | None = None
    timezone: str = "America/New_York"
    reporting_currency: str = "CNH"
    opening_snapshot_path: str | None = None
    source: str = "legacy_history"

    def includes(self, timestamp: datetime, *, through: datetime | None = None) -> bool:
        value = utc(timestamp)
        return (self.cutoff_at is None or value > utc(self.cutoff_at)) and (through is None or value <= utc(through))

    def includes_session(self, session: date) -> bool:
        return self.start_date is None or session >= self.start_date


def context_from_baseline(baseline) -> PortfolioContext:
    if baseline is None:
        return PortfolioContext()
    if baseline.portfolio_context:
        return PortfolioContext.model_validate(baseline.portfolio_context)
    cutoff = baseline.account_reset_at
    if cutoff is None and baseline.source == "ib_broker_authoritative_reset":
        cutoff = baseline.cutoff_at
    if cutoff is None:
        return PortfolioContext()
    cutoff = utc(cutoff)
    return PortfolioContext(
        account_id=baseline.account_id,
        episode_id=sha256(cutoff.isoformat().encode()).hexdigest()[:20],
        cutoff_at=cutoff, start_date=(cutoff + timedelta(microseconds=1)).astimezone(NY).date(),
        opening_snapshot_path=baseline.account_snapshot_path, source=baseline.source,
    )


def portfolio_context(store) -> PortfolioContext:
    return context_from_baseline(store.latest_pnl_baseline())


def session_end(day: date) -> datetime:
    return datetime.combine(day, time.max, NY).astimezone(UTC)


def accounting_checkpoint(store, as_of: datetime, *, reference: bool = False):
    latest = store.latest_pnl_baseline()
    context = context_from_baseline(latest)
    if context.cutoff_at is not None and as_of <= utc(context.cutoff_at):
        raise ValueError("Requested date precedes this portfolio episode; select audit history instead.")
    history = store.list_pnl_baselines() if hasattr(store, "list_pnl_baselines") else ([latest] if latest else [])
    eligible = [b for b in history if utc(b.cutoff_at) <= as_of
                and (context.cutoff_at is None or utc(b.cutoff_at) >= utc(context.cutoff_at))]
    # Reference checkpoints introduced with the paired-ledger contract. Legacy
    # compactions are replayed from the original reset (or inception), never
    # relabelled actual-cost checkpoints as reference-cost checkpoints.
    if reference:
        eligible = [b for b in eligible if b.reference_open_lots is not None
                    or (b.account_reset_at is not None and utc(b.account_reset_at) == utc(b.cutoff_at))
                    or b.source in {"ib_broker_authoritative_reset", "operator_confirmed_paper_opening_reset"}]
    result = max(eligible, key=lambda b: (utc(b.cutoff_at), utc(b.created_at)), default=None)
    if context.cutoff_at is not None and result is None:
        raise ValueError("Portfolio opening checkpoint is unavailable; historical accounting cannot be reconstructed.")
    return result
