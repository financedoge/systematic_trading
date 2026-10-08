"""One fixed US-equity economic risk overlay; no registration or order authority."""
from datetime import date, datetime
from decimal import Decimal as D

from systematic_trading.recorders.economics import NY
from systematic_trading.research.construction_controls import gross
from systematic_trading.research.economic_features import activity_feature

SPEC = dict(version="us-activity-spy-v1", series=["ICSA", "PERMIT", "IPMAN"], symbol="SPY",
    trigger="At least two weakening flags, only when all three measurements are usable",
    stressed_scale="0.75", normal_scale="1", removed_budget="zero-interest USD cash; no redistribution",
    stale="An optional macro overlay abstains for the whole decision; preserve parent targets unchanged",
    integrity="Missing publication, changed hash, invalid schema, future availability or invalid numeric data abort the run",
    features="us-activity-features-v1; claims four/thirteen-week ratio; permits/manufacturing three-month year-on-year ratios",
    thresholds="Claims >0, permits <0, manufacturing <0; zero is not weakening",
    scope="SPY only, after all parent overlays; no country extrapolation, leverage or new ETF")


def signal(reader, *, vintage, known_at):
    if known_at.tzinfo is None:
        raise ValueError("Economic decision needs a timezone")
    features, unavailable = {}, {}
    for series in SPEC["series"]:
        # Verify the exact publication independently of expected data gaps.
        s = reader.snapshot(series, vintage)
        if known_at <= datetime.fromisoformat(s["archive_available_at"]):
            raise ValueError("Economic archive not available at the decision cutoff")
        age = (known_at.astimezone(NY).date() - date.fromisoformat(s["last"])).days
        count = 13 if series == "ICSA" else 15
        window = s["observations"][-count:]
        if not s["usable"] or age > s["series"]["max_age_days"]:
            unavailable[series] = dict(reason="stale or missing endpoint", endpoint=s["last"], age_days=age)
        elif len(window) < count or any(r["value"] is None for r in window):
            unavailable[series] = dict(reason="incomplete required feature window", endpoint=s["last"], age_days=age)
        else:
            features[series] = activity_feature(s)
    ready = not unavailable
    weakening = sum(r["weakening"] for r in features.values()) if ready else None
    active = ready and weakening >= 2
    return dict(vintage=vintage, known_at=known_at.isoformat(), ready=ready, weakening=weakening,
                active=active, scale=SPEC["stressed_scale"] if active else "1", features=features,
                unavailable=unavailable, availability="archive_daily", specification=SPEC["version"])


def scale_spy(targets, scale):
    gross(targets)
    if not scale.is_finite() or not D(0) <= scale <= 1:
        raise ValueError("SPY reduction must be finite and within [0, 1]")
    if scale == 1:
        return list(targets)
    return [t.model_copy(update=dict(target_weight=t.target_weight*scale,
        rationale=t.rationale + " US economic research scale " + str(scale) + "; removed SPY budget stays cash."))
        if t.symbol == "SPY" else t for t in targets]


def apply_signal(targets, state):
    if state.get("specification") != SPEC["version"] or type(state.get("ready")) is not bool:
        raise ValueError("Unverified economic signal state")
    expected = SPEC["stressed_scale"] if state["ready"] and state["weakening"] >= 2 else "1"
    if state["scale"] != expected or state["active"] != (expected != "1"):
        raise ValueError("Inconsistent economic signal")
    return scale_spy(targets, D(expected))


def calibrate_spy(parent, candidate, *, evaluation_start="2021-01-04"):
    """Match average monthly SPY target using calibration-period targets only."""
    days = sorted(d for d in parent if "2016-01-04" <= d < evaluation_start)
    if len(days) != 60 or days != sorted(d for d in candidate if "2016-01-04" <= d < evaluation_start):
        raise ValueError("Expected sixty aligned calibration decisions")
    totals = []
    for source in [parent, candidate]:
        total = D(0)
        for day in days:
            row = source[day]
            if row["known_through"] >= day:
                raise ValueError("Unavailable calibration target")
            total += sum(D(t["target_weight"]) for t in row["targets"] if t["symbol"] == "SPY")
        totals.append(total)
    if totals[0] <= 0 or not 0 <= totals[1] <= totals[0]:
        raise ValueError("Invalid SPY exposure calibration")
    return dict(scale=str(totals[1]/totals[0]),decisions=len(days),start=days[0],end=days[-1],
                parent_mean_spy=str(totals[0]/len(days)),candidate_mean_spy=str(totals[1]/len(days)),
                inputs="Monthly targets only; no evaluation exposure, realized volatility or return fitting")
