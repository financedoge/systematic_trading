from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from qualify_ten_mdy_histories import REQUIRED_GATES, qualified, identity_matches


def test_complete_prices_and_current_identity_do_not_replace_independent_evidence():
    gates=dict.fromkeys(REQUIRED_GATES,True)
    assert qualified(gates)
    for key in REQUIRED_GATES:
        missing=dict(gates)
        del missing[key]
        assert not qualified(missing)
        assert not qualified(dict(gates, **{key:'unverified'}))
        assert not qualified(dict(gates, **{key:False}))
    assert not qualified({})


def test_historical_filing_and_current_contract_require_matching_identifiers():
    issuer=dict(cik=123,filings=[dict(fields=dict(TradingSymbol=['X'],Security12bTitle=['Common stock'],EntityCentralIndexKey=['0000123']))])
    broker=dict(status='identity_verified',lookup=dict(secIdType='ISIN',secId='US0000000001'),details=dict(contract=dict(symbol='X')))
    assert all(identity_matches('X','US0000000001',issuer,broker).values())
    assert not identity_matches('X','US0000000002',issuer,broker)['current_isin_contract']
    assert not identity_matches('X','US0000000001',dict(issuer,cik=124),broker)['historical_filing_anchors']
    assert not identity_matches('Y','US0000000001',issuer,broker)['historical_filing_anchors']
