"""Strict parsers for official EIA report snapshots, never inferred vintages."""
from __future__ import annotations

import csv
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from html import unescape
import json
import re
from zoneinfo import ZoneInfo

NY = ZoneInfo("America/New_York")


def number(value):
    if value is None or str(value).strip() in {"", "-", "--", "NA", "N/A", "–", "– –"}:
        return None
    try:
        result = Decimal(str(value).replace(",", "").strip())
    except InvalidOperation as exc:
        raise ValueError("Unexpected EIA numeric field") from exc
    if not result.is_finite():
        raise ValueError("Non-finite EIA value")
    return str(result)


def difference(current, previous):
    return None if current is None or previous is None else str(Decimal(current) - Decimal(previous))


def release_time(day, clock):
    clock = clock.lower().replace(".", "").strip()
    return datetime.strptime(day + " " + clock, "%Y-%m-%d %I:%M %p").replace(tzinfo=NY).astimezone(UTC)


def _dates(current, previous, released):
    current, previous = date.fromisoformat(current), date.fromisoformat(previous)
    if current.weekday() != 4 or (current - previous).days != 7 or current >= released.astimezone(NY).date():
        raise ValueError("EIA report period / release dates are inconsistent")


def _csv(raw):
    # EIA legacy table CSVs use Windows-1252 and may end with DOS EOF.
    return [[v.strip() for v in row] for row in csv.reader(raw.decode("cp1252").replace("\x1a", "").splitlines()) if row]


def _iso(value):
    return datetime.strptime(value, "%m/%d/%y").date().isoformat()


def _one(rows, predicate):
    found = [row for row in rows if predicate(row)]
    if len(found) != 1:
        raise ValueError("Missing or duplicate EIA table identity")
    return found[0]


def petroleum(files):
    stocks = json.loads(files["stocks.json"].decode("utf-8-sig"))
    metadata, us = stocks["metadata"], stocks["data"]["U.S."]
    if (metadata["source"] != "U.S. Energy Information Administration" or
            metadata["release_name"] != "Weekly Petroleum Status Report" or
            metadata["periodicity"] != "Weekly" or us["sourcekey"] != "WCESTUS1" or
            us["units"] != "thousand barrels"):
        raise ValueError("EIA crude stock source identity or units changed")
    released = release_time(metadata["release_date"], metadata["release_time"])
    current = metadata["time_period"]["end_date"]
    balance, estimates = _csv(files["balance.csv"]), _csv(files["estimates.csv"])
    stock_header = _one(balance, lambda r: r[0] == "STUB_1" and r[1] != "STUB_2")
    flow_header = _one(balance, lambda r: r[:2] == ["STUB_1", "STUB_2"])
    estimate_header = _one(estimates, lambda r: r[:2] == ["STUB_1", "STUB_2"])
    if len(stock_header) != 8 or len(flow_header) != 13 or len(estimate_header) != 8:
        raise ValueError("EIA column layout changed")
    previous = _iso(stock_header[2])
    if any(_iso(h[i]) != current or _iso(h[i+1]) != previous
           for h, i in [(stock_header, 1), (flow_header, 2), (estimate_header, 2)]):
        raise ValueError("Mixed EIA petroleum release files")
    if stock_header[3:5] != ["Difference", "Percent Change"] or flow_header[4] != "Difference":
        raise ValueError("EIA column identity changed")
    if (any(_iso(flow_header[i]) != current for i in [7, 10]) or
            any(_iso(flow_header[i]) != _iso(flow_header[5]) for i in [8, 11]) or
            _iso(estimate_header[6]) != current or _iso(estimate_header[7]) != _iso(estimate_header[4])):
        raise ValueError("EIA averaging-window dates changed")
    _dates(current, previous, released)
    metrics = []
    for key, label in [("crude-ex-spr", "Commercial (Excluding SPR)"), ("spr", "Strategic Petroleum Reserve (SPR)"),
                       ("gasoline", "Total Motor Gasoline"), ("distillate", "Distillate Fuel Oil")]:
        row = _one(balance, lambda r: r[0] == label)
        if len(row) != 8:
            raise ValueError("EIA stock row layout changed")
        value, prior = number(row[1]), number(row[2])
        metrics.append(dict(id=key, name=label + " stocks", units="million barrels", value=value,
                            previous_value=prior, previous_date=previous, change=difference(value, prior),
                            year_ago_value=number(row[5]), year_ago_date=_iso(stock_header[5]), source_row=row))
    flows = [("production", "Crude Oil Supply", "Domestic Production"),
             ("imports", "Crude Oil Supply", "Imports"), ("exports", "Crude Oil Supply", "Exports"),
             ("refinery-inputs", "Crude Oil Supply", "Crude Oil Input to Refineries"),
             ("products-supplied", "Products Supplied", "Total"),
             ("gasoline-supplied", "Products Supplied", "Finished Motor Gasoline"),
             ("distillate-supplied", "Products Supplied", "Distillate Fuel Oil")]
    for key, section, label in flows:
        row = _one(balance, lambda r: len(r) == 13 and r[0] == section and
                   re.sub(r"^\(\d+\)\s*", "", r[1]) == label)
        value, prior = number(row[2]), number(row[3])
        metrics.append(dict(id=key, name=section + ": " + label, units="thousand barrels/day", value=value,
                            previous_value=prior, previous_date=previous, change=difference(value, prior),
                            four_week_average=number(row[7]), year_ago_four_week_average=number(row[8]),
                            year_ago_value=number(row[5]), year_ago_date=_iso(flow_header[5]), source_row=row))
    row = _one(estimates, lambda r: r[:2] == ["Refiner Inputs and Utilization", "Percent Utilization"])
    if len(row) != 8:
        raise ValueError("EIA utilization layout changed")
    value, prior = number(row[2]), number(row[3])
    if value is not None and not 0 <= Decimal(value) <= 100:
        raise ValueError("EIA utilization out of range")
    metrics.append(dict(id="utilization", name="Refinery utilization", units="percent", value=value,
                        previous_value=prior, previous_date=previous, change=difference(value, prior),
                        year_ago_value=number(row[4]), year_ago_date=_iso(estimate_header[4]),
                        four_week_average=number(row[6]), source_row=row))
    history = []
    for point in us["time_series"]:
        day = date.fromisoformat(point["date"])
        if day.weekday() != 4 or str(day) > current:
            raise ValueError("EIA rolling history date is invalid")
        flag = point["suppression_flag"]
        if flag not in {None, "-", "--"}:
            raise ValueError("Unknown EIA suppression flag")
        val = number(point["value"])
        if flag is not None and val is not None:
            raise ValueError("Conflicting EIA suppression flag and value")
        history.append(dict(date=str(day), value=None if val is None else str(Decimal(val)/1000), suppression_flag=flag))
    history.sort(key=lambda r: r["date"])
    if not history or history[-1]["date"] != current or any(
            (date.fromisoformat(b["date"]) - date.fromisoformat(a["date"])).days != 7
            for a, b in zip(history, history[1:])):
        raise ValueError("EIA rolling history has gaps, duplicates or wrong endpoint")
    if number(history[-1]["value"]) != number(metrics[0]["value"]):
        if history[-1]["value"] is None or metrics[0]["value"] is None or Decimal(history[-1]["value"]) != Decimal(metrics[0]["value"]):
            raise ValueError("EIA crude stock JSON / balance table mismatch")
    return dict(report_date=current, source_release_at=released.isoformat(), metrics=metrics,
                reference_history=dict(series="crude-ex-spr", units="million barrels", rows=history,
                                       availability="All rows belong to this captured release, not their observation dates."))


def natural_gas(files):
    data = json.loads(files["storage.json"].decode("utf-8-sig"))
    text = " ".join(unescape(re.sub(r"<[^>]+>", " ", files["release.html"].decode("utf-8-sig"))).split())
    match = re.search(r"Released:\s*([A-Za-z]+ \d{1,2}, \d{4}) at (\d{1,2}:\d{2}\s*[ap]\.m\.)", text)
    period = re.search(r"for week ending ([A-Za-z]+ \d{1,2}, \d{4})", text)
    if not match or not period or data["release_name"] != "Weekly Natural Gas Storage Report":
        raise ValueError("EIA gas release timestamp is missing")
    release_day = datetime.strptime(match[1], "%B %d, %Y").date().isoformat()
    if (datetime.strptime(data["release_date"], "%Y-%b-%d %H:%M:%S").date().isoformat() != release_day or
            datetime.strptime(period[1], "%B %d, %Y").date().isoformat() != data["current_week"]):
        raise ValueError("Mixed EIA gas release files")
    released = release_time(release_day, match[2])
    _dates(data["current_week"], data["week_ago"], released)
    total = _one(data["series"], lambda r: r["series_id"] == "png.nw2_epg0_swo_r48_bcf.w")
    if total["units"] != "billion cubic feet" or total["name"] != "total lower 48 states":
        raise ValueError("EIA gas series identity / units changed")
    if [r[0] for r in total["data"]] != [data["current_week"], data["week_ago"], data["year_ago"]]:
        raise ValueError("EIA gas comparison dates changed")
    for flag_name in ["revision_flag", "reclassification_flag"]:
        if len(total[flag_name]) != 3 or any(v not in {"true", "false"} for v in total[flag_name]):
            raise ValueError("EIA gas revision flags invalid")
    value, prior, year_ago = [number(row[1]) for row in total["data"]]
    metrics = [dict(id="working-gas", name="Lower 48 working gas", units="billion cubic feet", value=value,
                    previous_value=prior, previous_date=data["week_ago"], change=difference(value, prior),
                    year_ago_value=year_ago, year_ago_date=data["year_ago"], source_row=total)]
    for key, name, field, units in [("gas-net-change", "Storage net change", "net_change", "billion cubic feet"),
                                   ("gas-implied-flow", "Storage implied flow", "implied_flow", "billion cubic feet"),
                                   ("gas-five-year-average", "Storage five-year average", "5yr-avg", "billion cubic feet"),
                                   ("gas-vs-five-year", "Storage vs five-year average", "pct-chg_5yr-avg", "percent")]:
        calculated = total["calculated"]
        flags = {f: calculated[f + "_" + field] for f in ["revision_flag", "reclassification_flag"]}
        if any(v not in {"true", "false"} for v in flags.values()):
            raise ValueError("EIA gas calculated revision flags invalid")
        metrics.append(dict(id=key, name=name, units=units, value=number(calculated[field]),
                            comparison_window=data["5yr_avg"], **flags))
    return dict(report_date=data["current_week"], source_release_at=released.isoformat(), metrics=metrics,
                reference_history=None)
