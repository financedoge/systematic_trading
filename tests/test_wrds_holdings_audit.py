"""Holdings inspection preserves date, share-class and foreign-identifier gaps."""
import importlib.util
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
SPEC=importlib.util.spec_from_file_location('holdings_audit',SCRIPTS/'audit_wrds_holdings_coverage.py')
audit=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
sys.path.pop(0)


def test_unknown_dates_cannot_behave_as_open_ended_intervals():
    assert audit.within('2024-01-01','2024-12-31','2024-12-31')
    assert not audit.within('2024-01-01',None,'2024-12-31')
    assert not audit.within(None,'2024-12-31','2024-12-31')
    assert not audit.within('2025-01-01','2025-12-31','2024-12-31')


def test_name_and_map_must_agree_uniquely_at_report_date():
    names=[dict(ticker='MDY',et_flag='F',crsp_fundno=1,crsp_portno=2,
                chgdt='2024-01-01',chgenddt='2024-12-31')]
    maps=[dict(crsp_fundno=1,crsp_portno=2,begdt='2024-01-01',enddt='2024-12-31')]
    assert audit.candidates(names,maps,'MDY','2024-12-31') == [2]
    assert audit.candidates(names*2,maps,'MDY','2024-12-31') == []
    assert audit.candidates(names,[dict(maps[0],crsp_portno=3)],'MDY','2024-12-31') == []
    assert audit.candidates(names,[dict(maps[0],begdt='2025-01-01')],'MDY','2024-12-31') == []


def node(cusip,isin):
    return ET.fromstring(f'<invstOrSec><cusip>{cusip}</cusip><identifiers><isin value="{isin}"/></identifiers></invstOrSec>')


def test_foreign_isin_is_not_a_silent_cusip_bridge():
    assert audit.sec_identifier(node('000000000','SG9999000020')) is None
    assert audit.sec_identifier(node('000000000','US9426222009')) == '94262220'


def test_conflicting_filed_identifiers_stop_join():
    with pytest.raises(ValueError,match='Conflicting'):
        audit.sec_identifier(node('942622101','US9426222009'))
