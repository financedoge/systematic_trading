"""Fixed same-vintage activity measurements; no allocation or fitted model."""
from decimal import Decimal

VERSION = "us-activity-features-v1"


def activity_feature(snapshot):
    series = snapshot["series"]["id"]
    count = 13 if series == "ICSA" else 15
    rows = snapshot["observations"][-count:]
    if series not in {"ICSA", "PERMIT", "IPMAN"} or len(rows) != count or any(r["value"] is None for r in rows):
        raise ValueError("Incomplete economic feature window")
    values = [Decimal(r["value"]) for r in rows]
    if any(not v.is_finite() or v <= 0 for v in values):
        raise ValueError("Invalid economic feature level")
    if series == "ICSA":
        value = (sum(values[-4:]) / 4) / (sum(values) / 13) - 1
        formula = "Four-week mean / thirteen-week mean - 1"
        weakening = value > 0
    else:
        value = sum(values[-3:]) / sum(values[:3]) - 1
        formula = "Latest three-month sum / same three months one year earlier - 1"
        weakening = value < 0
    return dict(version=VERSION, series=series, vintage=snapshot["vintage"], endpoint=rows[-1]["date"],
                value=str(value), weakening=weakening, formula=formula,
                required_window_start=rows[0]["date"], required_window_end=rows[-1]["date"],
                required_observations=count)
