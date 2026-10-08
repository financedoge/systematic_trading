"""Fixed F4 ablation: F1 positions plus capped Treasury-bill parking."""
from decimal import Decimal as D

from systematic_trading.domain.enums import AssetClass, Currency, Exchange
from systematic_trading.domain.market import Instrument
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research.construction_controls import gross

BILL = Instrument(symbol="BIL", name="State Street SPDR Bloomberg 1-3 Month T-Bill ETF",
                  asset_class=AssetClass.ETF, exchange=Exchange.NYSE, quote_currency=Currency.USD,
                  country="US", sector="Treasury bills")
SPEC = dict(version="f4-bil-v1", parent="F1", symbol="BIL", final_target_cap="0.45", cash_reserve="0.02",
            trigger="Fewer than four of the original twelve ETFs have positive 252-session momentum",
            placement="After all F1 overlays; original ETF weights unchanged; exit BIL on first normal monthly decision",
            distributions="Included in audited adjusted prices; no additional dividend cash credit",
            cash_interest="Zero; BIL fund returns are not broker cash interest")


def park(targets, *, fallback):
    if type(fallback) is not bool:
        raise ValueError("Valid weak-breadth decision required")
    if any(t.symbol == BILL.symbol for t in targets):
        raise ValueError("Parking asset must be outside the original selection universe")
    invested = gross(targets)
    residual = max(D(0), D(1)-invested-D(SPEC["cash_reserve"]))
    weight = min(D(SPEC["final_target_cap"]), residual) if fallback else D(0)
    return [*targets, AllocationTarget(symbol=BILL.symbol, sleeve="f4-bill-parking", target_weight=weight,
              rationale="Fixed residual-cash parking during valid weak breadth" if fallback else "Exit parking on normal breadth")]
