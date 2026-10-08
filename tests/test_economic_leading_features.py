from datetime import datetime, UTC
from decimal import Decimal as D
import copy
import pytest

from systematic_trading.research.economic_leading_features import (
    LEADING, CONTEXT, COUNTS, measurements, panel,
)


def snap(series, values=None):
    values = values or [100]*COUNTS[series]
    return dict(series=dict(id=series, max_age_days=100), vintage="2026-09-29",
        archive_available_at="2026-09-30T03:59:59.999999+00:00", usable=True,
        last="2026-09-01", observations=[dict(date=f"row-{i}", value=str(v) if v is not None else None)
                                       for i,v in enumerate(values)])


def test_transformations_keep_direction_and_units():
    assert D(measurements(snap("ICSA", [100]*9+[200]*4))["features"]["ICSA"]) > 0
    assert D(measurements(snap("PERMIT", [100]*3+[110]*3))["features"]["PERMIT"]) == D(".1")
    assert D(measurements(snap("AWHMAN", [40]*3+[39]*3))["features"]["AWHMAN"]) == -1
    assert D(measurements(snap("PAYEMS", [1000, 1100, 1200, 1300]))["features"]["PAYEMS"]) == 100


def test_inflation_horizons_use_same_vintage_and_correct_lags():
    values = [100]*9+[110, 113, 117, 121]
    x = measurements(snap("CPIAUCSL", values))["features"]
    assert D(x["CPIAUCSL_3m_annualized"]) == D("1.1")**4-1
    assert D(x["CPIAUCSL_12m"]) == D(".21")


def test_signed_survey_uses_level_not_percentage_growth_across_zero():
    s = "NOFDFSA066MSFRBPHI"
    assert D(measurements(snap(s, [-30, 0, 30]))["features"][s]) == 0
    assert D(measurements(snap(s, [-30, -15, 0]))["features"][s]) == D("-.15")


@pytest.mark.parametrize("values", [[100], [None]*6, ["NaN"]*6, [0]*6])
def test_unavailable_or_invalid_windows_are_never_zero_filled(values):
    with pytest.raises(ValueError):
        measurements(snap("TEMPHELPS", values))


class Reader:
    def __init__(self):
        self.calls = []
        self.data = {s:snap(s) for s in LEADING+CONTEXT}

    def snapshot(self, series, vintage):
        assert vintage == "2026-09-29"  # no latest-vintage fallback permitted
        self.calls.append((series, vintage))
        return copy.deepcopy(self.data[series])


def test_ex_ante_panel_uses_only_exact_published_vintage():
    reader = Reader()
    result = panel(reader, "2026-09-29", datetime(2026, 9, 30, 20, tzinfo=UTC))
    assert result["leading_ready"] and result["context_ready"]
    assert len(result["features"]) == 13 and len(reader.calls) == 11
    # Changes to a separate later publication cannot affect the requested one.
    reader.data["unrequested_latest"] = snap("PAYEMS", [999999]*4)
    assert panel(reader, "2026-09-29", datetime(2026, 9, 30, 20, tzinfo=UTC)) == result


def test_same_day_archive_and_naive_decision_are_rejected():
    reader = Reader()
    with pytest.raises(ValueError, match="unavailable"):
        panel(reader, "2026-09-29", datetime(2026, 9, 29, 20, tzinfo=UTC))
    with pytest.raises(ValueError, match="timezone"):
        panel(reader, "2026-09-29", datetime(2026, 9, 30, 20))


def test_readiness_is_group_specific_and_all_integrity_checks_still_run():
    reader = Reader()
    reader.data["PAYEMS"]["last"] = "2025-01-01"
    result = panel(reader, "2026-09-29", datetime(2026, 9, 30, 20, tzinfo=UTC))
    assert result["leading_ready"] and not result["context_ready"]
    assert "PAYEMS" not in result["features"]
    assert len(reader.calls) == 11
    reader.data["CPILFESL"]["observations"][-1]["value"] = "NaN"
    with pytest.raises(ValueError, match="Invalid"):
        panel(reader, "2026-09-29", datetime(2026, 9, 30, 20, tzinfo=UTC))


def test_missing_leading_series_is_not_replaced_by_context():
    reader = Reader()
    reader.data["NEWORDER"]["observations"][-2]["value"] = None
    result = panel(reader, "2026-09-29", datetime(2026, 9, 30, 20, tzinfo=UTC))
    assert not result["leading_ready"] and result["context_ready"]
    assert "NEWORDER" not in result["features"]
