"""The holdings access probe cannot read rows or address other schemas."""
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('wrds_holdings_probe', SCRIPTS/'probe_wrds_holdings.py')
probe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(probe)
sys.path.pop(0)


def test_read_probe_is_constant_bounded_and_quoted():
    query = probe.read_query('crsp_q_mutualfunds','holdings').as_string()
    assert query == 'SELECT 1 AS row_present FROM "crsp_q_mutualfunds"."holdings" LIMIT 1'


@pytest.mark.parametrize('schema,table', [('crsp_q_mutualfunds_old','holdings'),
    ('crsp_q_mutualfunds','unplanned'),('crsp_q_mutualfunds','holdings; DROP TABLE funds')])
def test_other_scope_cannot_be_queried(schema,table):
    with pytest.raises(ValueError,match='scope'):
        probe.read_query(schema,table)
