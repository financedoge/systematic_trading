from copy import deepcopy

import pytest

from systematic_trading.research.ib_admission import validate_contract


FUND = dict(symbol="XOP", currency="USD", isin="US78468R5569")
DETAIL = dict(contract=dict(symbol="XOP", secType="STK", currency="USD", primaryExchange="ARCA", conId=42),
              validExchanges="SMART,ARCA", secIdList=[dict(tag="ISIN", value=FUND["isin"])])


def test_resolved_identity_never_grants_account_or_settlement_permission():
    result = validate_contract(FUND, [DETAIL])
    assert result["status"] == "identity_verified"
    assert result["account_permission"] == result["settlement_eligibility"] == "unverified"


@pytest.mark.parametrize("key,value", [("symbol", "OTHER"), ("secType", "OPT"), ("currency", "EUR"),
                                      ("primaryExchange", "ISLAND"), ("conId", 0)])
def test_contract_identity_mismatch_is_rejected(key, value):
    row = deepcopy(DETAIL)
    row["contract"][key] = value
    with pytest.raises(ValueError, match="identity disagreement"):
        validate_contract(FUND, [row])


@pytest.mark.parametrize("rows", [[], [DETAIL, DETAIL]])
def test_missing_or_ambiguous_resolution_is_rejected(rows):
    with pytest.raises(ValueError, match="Missing or ambiguous"):
        validate_contract(FUND, rows)


def test_contradictory_security_id_is_rejected():
    row = deepcopy(DETAIL)
    row["secIdList"][0]["value"] = "OTHER"
    with pytest.raises(ValueError, match="ISIN disagreement"):
        validate_contract(FUND, [row])
