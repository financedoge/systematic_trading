"""Identifier bridges require supported numbering rules, checksums and dated uniqueness."""
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS=Path(__file__).resolve().parents[1]/'scripts'
sys.path.insert(0,str(SCRIPTS))
SPEC=importlib.util.spec_from_file_location('holdings_identity_audit',SCRIPTS/'audit_holdings_identity.py')
audit=importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)
sys.path.pop(0)


@pytest.mark.parametrize('isin,cusip',[
    ('US9279591062','927959106'),('BMG7496G1033','G7496G103'),
    ('KYG3323L1005','G3323L100'),('VGG1890L1076','G1890L107')])
def test_documented_country_embedding_checks_both_identifiers(isin,cusip):
    assert audit.valid_isin(isin)
    assert audit.valid_cusip(cusip)
    assert audit.embedded_cusip(isin)==cusip
    broken=isin[:-1]+str((int(isin[-1])+1)%10)
    with pytest.raises(ValueError,match='ISIN'):
        audit.embedded_cusip(broken)


@pytest.mark.parametrize('isin',['SG9999000020','GB00BFMBMT84','IE00B4Q5ZN47'])
def test_valid_foreign_isin_does_not_imply_cusip_structure(isin):
    assert audit.valid_isin(isin)
    assert audit.embedded_cusip(isin) is None


def test_shape_and_check_digit_guards():
    for value in [None,'', '92795910', '927959107', 'g7496g103', '１２３４５６７８９']:
        assert not audit.valid_cusip(value)
    for value in [None,'','US927959106','us9279591062','１２９２７９５９１０６２']:
        assert not audit.valid_isin(value)


def test_conversion_boundary_and_duplicate_effective_states():
    old=dict(permno=15139,ticker='VNOM',tradingsymbol='VNOM',cusip9='92763M105',
        secinfostartdt='2023-10-01',secinfoenddt='2023-11-12')
    new=dict(old,cusip9='927959106',secinfostartdt='2023-11-13',secinfoenddt='2025-08-18')
    assert audit.dated_record([old,new],15139,'VNOM','927959106','2024-12-31')==new
    assert audit.dated_record([old,new],15139,'VNOM','92763M105','2024-12-31') is None
    assert audit.dated_record([new,new],15139,'VNOM','927959106','2024-12-31') is None
    assert audit.dated_record([dict(new,tradingsymbol='OTHER')],15139,'VNOM','927959106','2024-12-31') is None


def test_rank_ties_are_not_removed_and_late_receipts_stay_separate():
    one=dict(report_dt='2022-01-31',eff_dt='2022-02-21',security_rank=1,cusip='ABC')
    two=dict(one,cusip='DEF')
    late=dict(one,eff_dt='2022-04-07',cusip='GHI')
    groups=audit.receipt_groups([one,two,late])
    assert [len(groups[d]) for d in sorted(groups)]==[2,1]
    with pytest.raises(ValueError,match='repeated'):
        audit.receipt_groups([one,one])


@pytest.mark.parametrize('receipt',[None,'2022-01-30','not-a-date'])
def test_unknown_or_invalid_receipt_dates_fail(receipt):
    with pytest.raises(ValueError):
        audit.receipt_groups([dict(report_dt='2022-01-31',eff_dt=receipt)])
