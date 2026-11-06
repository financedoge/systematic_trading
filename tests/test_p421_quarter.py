from collections import defaultdict
from datetime import date
from pathlib import Path
import io
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from acquire_p421_quarter import TABLES, members
from qualify_p421_quarter import FIELDS, complete_window, eligible, observe, security_keys, unique_symbol, window_days


def test_revision_waits_for_evidence_and_period_must_match():
    first = dict(symbol='X', as_of='2024-12-31', filed='2025-02-24', accepted_new_york='2025-02-24 11:12:00', filing='NPORT-P')
    change = dict(first, filed='2025-03-03', accepted_new_york='2025-03-03 11:00:00', filing='NPORT-P/A')
    rows = [change, first, dict(first, symbol='Y', as_of='2025-01-31')]
    assert eligible(rows, date(2025,2,24)) == {}
    assert eligible(rows, date(2025,3,3)) == {'X':first}
    assert eligible(rows, date(2025,3,4)) == {'X':change}


def test_identifier_conflicts_and_missing_ids_stay_unmatched():
    links = defaultdict(lambda: defaultdict(set))
    reverse = defaultdict(set)
    keys = security_keys(dict(cusip='000000000', identifiers=[{'type':'isin','value':'SG9999000020'}]))
    assert keys == [('isin','SG9999000020')]
    observe(links, reverse, keys[0], 'FLEX', 'MDY')
    assert unique_symbol(keys, links, reverse) == ('FLEX', ['MDY'])
    observe(links, reverse, ('isin','XX0000000000'), 'FLEX', 'another line')
    assert unique_symbol(keys, links, reverse) is None
    observe(links, reverse, ('cusip','123456789'), 'A', 'a')
    observe(links, reverse, ('cusip','123456789'), 'B', 'b')
    assert unique_symbol([('cusip','123456789')],links,reverse) is None
    assert unique_symbol([],links,reverse) is None


def test_two_different_identifier_types_must_agree():
    links = defaultdict(lambda: defaultdict(set))
    rev = defaultdict(set)
    ids = [('cusip','123456789'),('isin','XX0000000000')]
    observe(links,rev,ids[0],'A','source 1')
    observe(links,rev,ids[1],'B','source 2')
    assert unique_symbol(ids,links,rev) is None


def test_complete_window_requires_every_session_price_basis_and_raw_volume():
    days = window_days(date(2025,2,28))
    assert len(days) == 253 and days[0] == '2024-02-27' and '2025-01-09' not in days
    rows = [dict.fromkeys(FIELDS,1.) | dict(trade_date=d) for d in days]
    assert complete_window(rows,days)
    assert not complete_window(rows[:-1],days)
    for k in ['adjusted_high','raw_close','raw_volume']:
        assert not complete_window([dict(rows[0], **{k:None})] + rows[1:],days)


def test_sec_zip_members_require_integrity():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for table in TABLES:
            z.writestr(table,b'field\nvalue\n')
    data = bytearray(buf.getvalue())
    assert set(members(data)) == set(TABLES)
    assert members(data[:15]) == {}
    data[14] ^= 1
    with pytest.raises(ValueError,match='Damaged member'):
        members(data)
