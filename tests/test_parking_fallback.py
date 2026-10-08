from decimal import Decimal as D
import pytest

from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.research.parking_fallback import park


def targets(weight):
    return [AllocationTarget(symbol="SPY", sleeve="test", target_weight=D(weight), rationale="fixture")]


@pytest.mark.parametrize("incoming,expected", [("0",".45"),(".3",".45"),(".7",".28"),(".97",".01"),(".98","0"),("1","0")])
def test_residual_cash_respects_bill_cap_and_reserve(incoming, expected):
    original = targets(incoming)
    result = park(original, fallback=True)
    assert result[:-1] == original and result[-1].target_weight == D(expected)
    assert sum(t.target_weight for t in result) <= 1


def test_normal_breadth_explicitly_exits_bill_without_changing_parent():
    original = targets(".3")
    result = park(original, fallback=False)
    assert result[:-1] == original and result[-1].target_weight == 0


def test_missing_regime_is_not_cash_permission():
    with pytest.raises(ValueError, match="decision required"):
        park(targets(".3"), fallback=None)
    with pytest.raises(ValueError, match="outside"):
        park([targets(".3")[0].model_copy(update=dict(symbol="BIL"))], fallback=True)


def test_bill_uses_existing_ib_stock_etf_contract_without_order_submission():
    from systematic_trading.config import AppSettings
    from systematic_trading.domain.enums import Currency
    from systematic_trading.execution.broker import InteractiveBrokersOrderRouter, _to_ib_contract
    from systematic_trading.research.parking_fallback import BILL
    router = InteractiveBrokersOrderRouter(AppSettings(), instruments={BILL.symbol: BILL})
    spec = router.contract_spec_for('BIL')
    assert spec.symbol == 'BIL' and spec.security_type == 'STK'
    assert spec.exchange == 'SMART' and spec.currency == Currency.USD
    contract = _to_ib_contract(spec)
    assert (contract.symbol, contract.secType, contract.exchange, contract.currency) == ('BIL','STK','SMART','USD')
    # The existing ETF mapper deliberately avoids assigning the NYSE family as
    # primary venue. IB contract qualification must establish actual ARCA identity.
    assert spec.primary_exchange is None
