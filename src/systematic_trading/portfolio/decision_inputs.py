"""Pinned, reusable decision input session; signal and broker units stay separate."""
import json
from datetime import date
from pathlib import Path
from math import isfinite

from systematic_trading.domain.market import PriceBar
from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.governed_inputs import GovernedInputs, etf_bar


class DecisionInputSession:
    """Pin once per proposal; cache checked rows across allocation components.

    This cache lives only for the current request. A later request resolves its
    own publication, so refreshed or revoked inputs cannot remain cached globally.
    """
    def __init__(self, settings, through, *, analytics=None):
        analytics = analytics or AnalyticsStore.from_settings(settings)
        self.publication = analytics.latest("governance/catalog")
        if not self.publication:
            raise ValueError("No published audited history for strategy decisions")
        self.reader = GovernedInputs(Path(json.loads(self.publication["provenance"])["root"]), self.publication["version"])
        config = json.loads(settings.strategy_monitoring_config_path.read_text(encoding="utf8"))
        self.start = config["calculation"]["warmup_start"]
        self.through = str(through or date.today())
        self.rows, self.audits, self.files, self.typed = {}, {}, {}, {}

    def load(self, symbols, *, raw_activity=False, marks_only=False):
        from systematic_trading.research.candidate_pool import audited_bar
        from systematic_trading.research.etf_admission import admission_hold
        signal, raw_bars, prices, used = {}, {}, {}, {}
        for symbol in symbols:
            if symbol not in self.rows:
                before = dict(self.reader.used)
                audit = self.reader.audit(symbol)
                if audit.get("status") == "unavailable" or audit.get("identity_status") == "complex_identity_requires_review":
                    raise ValueError(f"Governed identity/coverage requires review: {symbol}")
                rows = self.reader.rows(symbol, self.start, self.through)
                if not rows:
                    raise ValueError(f"Missing audited decision inputs: {symbol}")
                self.rows[symbol], self.audits[symbol] = rows, audit
                self.files[symbol] = {k:v for k,v in self.reader.used.items() if before.get(k) != v}
            rows, audit = self.rows[symbol], self.audits[symbol]
            used.update(self.files[symbol])
            if raw_activity:
                if admission_hold(symbol) or audit.get("status") != "audited_with_limitations":
                    raise ValueError(f"Audited raw activity admission requires review: {symbol}")
            if not marks_only:
                key = (symbol, raw_activity)
                if key not in self.typed:
                    adjusted = ([PriceBar.model_validate(audited_bar(r)) for r in rows] if raw_activity else
                        [PriceBar.model_validate(etf_bar(r)) for r in rows])
                    raw = [PriceBar.model_validate(audited_bar(r, raw=True)) for r in rows] if raw_activity else []
                    self.typed[key] = (adjusted, raw)
                signal[symbol], raw = self.typed[key]
                if raw_activity:
                    raw_bars[symbol] = raw
            row = rows[-1]
            raw = row.get("raw_close")
            if raw is None or not isfinite(float(raw)) or raw <= 0:
                raise ValueError(f"Unsupported audited raw execution mark: {symbol}")
            prices[symbol] = dict(trade_date=row["trade_date"], close=str(raw))
        receipt = dict(batch=self.publication["version"], files=used,
            signal_price_basis="dividend_split_adjusted",
            signal_volume_basis="audited_raw_volume" if raw_activity else "provider_reported_split_adjusted_source_volume",
            signal_volume_note="Raw close times raw volume with adjusted-price direction" if raw_activity else
                "Provider-reported volume, split-adjusted by the source; not the reconstructed raw-volume basis.",
            execution_price_basis="audited_raw", execution_marks=prices,
            historical_availability="Revised provider vintages; historical publication availability is not certified")
        if raw_activity:
            receipt["raw_activity_contract"] = "raw_dollar_adjusted_direction_v1"
        receipt["sha256"] = digest(encode(receipt))
        return signal, prices, receipt, raw_bars

    def marks(self, symbols):
        _, prices, receipt, _ = self.load(symbols, marks_only=True)
        return prices, receipt


def decision_inputs(settings, symbols, through, *, analytics=None):
    signal, prices, receipt, _ = DecisionInputSession(settings, through, analytics=analytics).load(symbols)
    return signal, prices, receipt
