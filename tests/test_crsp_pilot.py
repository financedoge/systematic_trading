"""Dated identifiers must resolve the exact share class before source joins."""
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0,str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("crsp_pilot_audit",SCRIPTS / "audit_crsp_pilot.py")
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
from capture_flex_identifier_bridge import extract_bridge  # noqa: E402
sys.path.pop(0)


def history(**updates):
    return dict(permno=66376,ticker="WSO",tradingsymbol="WSO",cusip9="942622200",
                secinfostartdt="2024-01-01",secinfoenddt="2025-12-31",**updates)


def test_watsco_class_b_cannot_match_class_a_despite_same_ticker():
    a=history()
    b=dict(a,permno=46068,tradingsymbol="WSOB",cusip9="942622101")
    identity=dict(symbol="WSO",isin="US9426222009")
    assert audit.select_identity([b,a],identity,"2024-06-25")[0] == a
    assert audit.select_identity([b],identity,"2024-06-25")[0] is None


def test_interval_gap_or_overlap_is_not_repaired_with_current_identity():
    identity=dict(symbol="WSO",isin="US9426222009")
    assert audit.select_identity([history()],identity,"2023-12-31")[0] is None
    assert audit.select_identity([history(),history()],identity,"2024-01-01")[0] is None


def test_non_us_isin_does_not_turn_into_a_fabricated_cusip():
    identity=dict(symbol="FLEX",isin="SG9999000020")
    h=dict(history(),permno=80329,ticker="FLEX",tradingsymbol="FLEX",cusip9="Y2573F102")
    assert audit.select_identity([h],identity,"2024-06-25")[0] is None
    assert audit.select_identity([h],identity,"2024-06-25",dict(isin=identity["isin"],cusip="Y2573F102"))[0] == h


@pytest.mark.parametrize("value",[None,"NaN","Infinity"])
def test_missing_source_values_are_not_filled(value):
    with pytest.raises(ValueError):
        audit.number(value)


def test_sec_bridge_requires_both_identifiers_in_one_holding_and_pre_window_filing():
    raw=b'<root><invstOrSec><name>Flex Ltd</name><title>Ordinary</title><cusip>Y2573F102</cusip><identifiers><isin value="SG9999000020"/></identifiers><curCd>USD</curCd></invstOrSec></root>'
    index=b'<div class="infoHead">Filing Date</div><div class="info">2023-11-29</div>'
    assert extract_bridge(raw,index)["holding"]["cusip"] == "Y2573F102"
    with pytest.raises(ValueError,match="before"):
        extract_bridge(raw,index.replace(b'2023-11-29',b'2025-01-01'))
    with pytest.raises(ValueError,match="unique"):
        extract_bridge(raw.replace(b'Y2573F102',b'000000000'),index)
