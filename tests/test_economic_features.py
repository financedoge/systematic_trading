from decimal import Decimal
import pytest
from systematic_trading.research.economic_features import activity_feature


def snapshot(series, values):
    return dict(series=dict(id=series), vintage="2026-10-06", observations=[
        dict(date=str(i), value=None if v is None else str(v)) for i,v in enumerate(values)])


def test_claims_higher_recent_average_means_weakening():
    feature = activity_feature(snapshot("ICSA", [100]*9 + [200]*4))
    assert Decimal(feature["value"]) == Decimal(200)/(Decimal(1700)/13)-1
    assert feature["weakening"]
    assert not activity_feature(snapshot("ICSA", [100]*13))["weakening"]


@pytest.mark.parametrize("series", ["PERMIT", "IPMAN"])
def test_monthly_growth_matches_calendar_lag_and_is_scale_invariant(series):
    values = [100]*3 + [300]*9 + [90]*3
    feature = activity_feature(snapshot(series, values))
    assert Decimal(feature["value"]) == Decimal("-0.1") and feature["weakening"]
    assert activity_feature(snapshot(series, [v*7 for v in values]))["value"] == feature["value"]


@pytest.mark.parametrize("values", [[100]*12, [100]*12+[None], [100]*12+[0], [100]*12+["NaN"]])
def test_missing_or_invalid_claims_window_is_rejected(values):
    with pytest.raises(ValueError):
        activity_feature(snapshot("ICSA", values))
