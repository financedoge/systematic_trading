"""Published strategy inputs and replay receipts shared by paper/live decisions."""
import json
from datetime import date
from pathlib import Path

from systematic_trading.domain.market import PriceBar
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar


def decision_inputs(settings, symbols, through, *, analytics=None):
    analytics = analytics or AnalyticsStore.from_settings(settings)
    publication = analytics.latest("governance/catalog")
    if not publication:
        raise ValueError("No published audited history for strategy decisions")
    reader = GovernedInputs(Path(json.loads(publication["provenance"])["root"]), publication["version"])
    config = json.loads(settings.strategy_monitoring_config_path.read_text(encoding="utf8"))
    start = config["calculation"]["warmup_start"]
    signal, prices = {}, {}
    for symbol in symbols:
        audit = reader.audit(symbol)
        if audit.get("status") == "unavailable" or audit.get("identity_status") == "complex_identity_requires_review":
            raise ValueError(f"Governed identity/coverage requires review: {symbol}")
        rows = reader.rows(symbol, start, str(through or date.today()))
        signal[symbol] = [PriceBar.model_validate(dict(symbol=symbol, **etf_bar(row))) for row in rows]
        if not rows:
            raise ValueError(f"Missing audited decision inputs: {symbol}")
        row = rows[-1]
        # Quantities and broker references require traded-price units, whereas
        # return signals use dividend/split-adjusted prices.
        raw = row.get("raw_close")
        if raw is None or raw <= 0:
            raise ValueError(f"Unsupported audited raw execution mark: {symbol}")
        prices[symbol] = dict(trade_date=row["trade_date"], close=str(raw))
    receipt = dict(batch=publication["version"], files=reader.used,
        signal_price_basis="dividend_split_adjusted",
        signal_volume_basis="provider_reported_split_adjusted_source_volume",
        signal_volume_note="Provider-reported volume, split-adjusted by the source. "
            "This is not the reconstructed raw-volume basis (raw_volume); a signal that "
            "needs traded activity must declare which basis it consumed.",
        execution_price_basis="audited_raw", execution_marks=prices,
        historical_availability="Revised provider vintages; historical publication availability is not certified")
    receipt["sha256"] = digest(encode(receipt))
    return signal, prices, receipt
