"""Versioned leading/context feature groups from exact published daily vintages.

No latest-vintage replacement, consensus surprise, allocation, fitting or tuning.
The diffusion indexes are regional forward expectations, not national PMI.
"""
from datetime import date, datetime
from decimal import Decimal as D

from systematic_trading.recorders.economics import NY

VERSION = "us-leading-context-features-v1"
LEADING = ["ICSA", "PERMIT", "AWHMAN", "TEMPHELPS", "NEWORDER",
           "NOFDFSA066MSFRBPHI", "NEFDFSA066MSFRBPHI"]
CONTEXT = ["PAYEMS", "IPMAN", "CPIAUCSL", "CPILFESL"]
COUNTS = {s: (13 if s in {"ICSA", "CPIAUCSL", "CPILFESL"} else
              4 if s == "PAYEMS" else 3 if "FRBPHI" in s else 6)
          for s in LEADING + CONTEXT}
SPEC = dict(version=VERSION, leading=LEADING, context=CONTEXT,
    objective="Predict each ETF separately; economic conditions may help some assets and hurt others.",
    comparison="Leading-only tree versus same-input linear model and unchanged parent; add context as a separate ablation, never silently mix it into leading indicators.",
    transformations="Claims 4w/13w mean - 1; permits/temp help/core capital orders/output latest 3m/previous 3m sum - 1; manufacturing hours change in 3m mean; regional expectations 3m mean / 100; payroll average monthly 3m change (thousands); CPI/core CPI 3m annualized and 12m changes.",
    stale="Separate readiness per group; all observations required within a group. Unavailable is not zero. Integrity errors abort.",
    availability="Explicit archive_daily assumption; prior calendar-day archive before prior trading close. Observation month is not release time.",
    fitting="Expanding chronological training, original historical-vintage features, training-only preprocessing, labels must finish before the decision cutoff.",
    exclusions="GDP excluded. No national PMI or consensus-surprise feature until permitted dated source is recorded and published.",
    interpretation="Leading economic indicators need not lead asset prices; these are testable predictors, not known causal sensitivities.")


def measurements(snapshot):
    s = snapshot["series"]["id"]
    if s not in COUNTS:
        raise ValueError("Unregistered economic feature")
    count = COUNTS[s]
    rows = snapshot["observations"][-count:]
    if len(rows) != count or any(r["value"] is None for r in rows):
        raise ValueError("Incomplete economic feature window")
    values = [D(r["value"]) for r in rows]
    survey = "FRBPHI" in s
    if any(not v.is_finite() or (not survey and v <= 0)
           or (survey and not -100 <= v <= 100) for v in values):
        raise ValueError("Invalid economic feature level")
    if s == "ICSA":
        features = {s: (sum(values[-4:])/4)/(sum(values)/13)-1}
    elif survey:
        features = {s: sum(values)/3/100}
    elif s == "AWHMAN":
        features = {s: (sum(values[-3:])-sum(values[:3]))/3}
    elif s == "PAYEMS":
        features = {s: (values[-1]-values[-4])/3}
    elif s in {"CPIAUCSL", "CPILFESL"}:
        features = {s+"_3m_annualized": (values[-1]/values[-4])**4-1,
                    s+"_12m": values[-1]/values[0]-1}
    else:
        features = {s: sum(values[-3:])/sum(values[:3])-1}
    return dict(version=VERSION, series=s, vintage=snapshot["vintage"],
                features={k:str(v) for k,v in features.items()},
                required_window_start=rows[0]["date"], endpoint=rows[-1]["date"],
                required_observations=count)


def panel(reader, vintage, known_at):
    """Verify each source even if another optional feature is unavailable."""
    if known_at.tzinfo is None:
        raise ValueError("Economic decision must include timezone")
    result = dict(version=VERSION, vintage=vintage, known_at=known_at.isoformat(),
                  availability="archive_daily", features={}, sources={}, unavailable=[])
    for s in LEADING + CONTEXT:
        snap = reader.snapshot(s, vintage)
        if known_at <= datetime.fromisoformat(snap["archive_available_at"]):
            raise ValueError("Economic vintage unavailable at decision time")
        age = (known_at.astimezone(NY).date()-date.fromisoformat(snap["last"])).days
        rows = snap["observations"][-COUNTS[s]:]
        if not snap["usable"] or age > snap["series"]["max_age_days"]:
            reason = "stale_or_missing_endpoint"
        elif len(rows) != COUNTS[s] or any(r["value"] is None for r in rows):
            reason = "incomplete_window"
        else:
            item = measurements(snap)
            result["sources"][s] = item
            result["features"].update(item["features"])
            continue
        result["unavailable"].append(dict(series=s, reason=reason, endpoint=snap["last"],
            age_days=age, max_age_days=snap["series"]["max_age_days"]))
    result["leading_ready"] = all(s in result["sources"] for s in LEADING)
    result["context_ready"] = all(s in result["sources"] for s in CONTEXT)
    return result
