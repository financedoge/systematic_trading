"""Early-close clock bins and isolated evidence-publication safeguards."""
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0,str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location("p421_evidence_publisher",SCRIPTS / "publish_p421_data_checks.py")
publisher = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(publisher)
from reconcile_early_close_sources import clock_bucket  # noqa: E402
sys.path.pop(0)


def test_early_close_uses_the_session_close_instead_of_sixteen_hundred():
    opened,closed = 100,300
    assert clock_bucket(99,opened,closed) == "before_open"
    assert clock_bucket(100,opened,closed) == "regular_before_close"
    assert clock_bucket(299,opened,closed) == "regular_before_close"
    assert clock_bucket(300,opened,closed) == "closing_minute"
    assert clock_bucket(359,opened,closed) == "closing_minute"
    assert clock_bucket(360,opened,closed) == "after_closing_minute"


def test_available_at_is_unknown_even_when_observed_date_is_old():
    row=dict(symbol="RPM",date="2024-04-29",historical_published_at=None)
    result=publisher.observations([row],"test")
    assert result[0]["available_at"] is None
    assert result[0]["point_key"] == "RPM/2024-04-29"
    with pytest.raises(ValueError,match="Duplicate"):
        publisher.observations([row,row],"test")


def test_source_audit_cannot_claim_historical_availability_or_write_active_catalog():
    with pytest.raises(ValueError,match="does not certify"):
        publisher.observations([dict(symbol="RPM",date="2024-04-29",historical_published_at="2024-04-30")],"test")
    assert all(source.startswith("governance/pilots/") for _,source in publisher.SCOPES.values())
    with pytest.raises(KeyError):
        publisher.publish("governance/catalog")
