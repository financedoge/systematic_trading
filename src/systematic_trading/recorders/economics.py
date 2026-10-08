"""Raw-first ALFRED acquisition and verified publication, independent of trading.

Daily archives are date-level evidence, not a certified intraday release feed.
Source availability and the application's first capture are deliberately separate.
"""
import csv
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
import io
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4
from zoneinfo import ZoneInfo

from systematic_trading.lean.contracts import sha256
from systematic_trading.live.trading_calendar import next_us_trading_day, previous_us_trading_day
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.runtime_io import atomic_json, exclusive_lock

NY = ZoneInfo("America/New_York")
PREFIX = "governance/economic-vintage/"
CATALOG = "governance/economic-catalog"
POLICY = "alfred-activity-v1"
LIMITATIONS = [
    "ALFRED daily vintages use source, provider or first-FRED dates; intraday dissemination is not certified.",
    "Archive availability assumes the end of the vintage day in New York. Actual first capture is recorded separately.",
    "Historical snapshots were retrieved later; they are not evidence that this app observed them historically.",
    "Monthly decision snapshots are not a complete release calendar. No consensus surprises or country-wide signal is supplied.",
    "Missing values remain missing. Compare growth within one vintage; index bases may change between vintages.",
]


def configuration(settings):
    path = settings.economic_recorder_config_path
    config = json.loads(path.read_text(encoding="utf8"))
    ids = [s["id"] for s in config["series"]]
    if len(ids) != len(set(ids)) or any(not re.fullmatch("[A-Z0-9]{1,20}", s) for s in ids):
        raise ValueError("Invalid economic series registry")
    if not 1 <= config["max_captures_per_cycle"] <= 12:
        raise ValueError("Economic capture budget must be bounded")
    if any(not re.fullmatch("[a-f0-9]{64}", h) for h in config.get("compatible_config_sha256", [])):
        raise ValueError("Invalid economic migration hash")
    for s in config["series"]:
        if s["frequency"] not in {"monthly", "weekly_saturday", "weekly_friday", "daily_weekday", "quarterly"} or s["min"] >= s["max"]:
            raise ValueError("Unsupported economic schema")
    return config


def validate_registry_extension(config, previous):
    """Add identities without reinterpreting any retained published contract."""
    current = {s["id"]: s for s in config["series"]}
    old = {s["id"]: s for s in previous["series"]}
    if (config["version"] == previous["version"] or not old.keys() < current.keys()
            or any(current.get(s) != contract for s, contract in old.items())
            or any(config[k] != previous[k] for k in
                   ["observation_start", "decision_start", "prospective_start"])):
        raise ValueError("Economic registry changed; versioned migration required (not additive)")


def verify_registry_entries(config, config_hash, entries):
    """Explicitly named old registries may survive only as verified extensions.

    Original captures and hashes remain unchanged. Verify each distinct old
    registry from its manifest-bound bytes, then verify each entry's identity.
    """
    checked = {}
    for entry in entries.values():
        previous_hash = entry["config_sha256"]
        if entry["policy"] != POLICY:
            raise ValueError("Economic registry changed; versioned migration required")
        if previous_hash == config_hash:
            continue
        if previous_hash not in config.get("compatible_config_sha256", []):
            raise ValueError("Economic registry changed; versioned migration required")
        if previous_hash not in checked:
            previous = checked_document(entry["root"], entry["batch"], "config.json")
            # config.json is a canonical serialization, not the original file's
            # whitespace. The original byte hash is bound by the same manifest.
            receipt = checked_document(entry["root"], entry["batch"], "receipt.json")
            if receipt["config_sha256"] != previous_hash:
                raise ValueError("Economic registry provenance hash mismatch")
            validate_registry_extension(config, previous)
            checked[previous_hash] = {s["id"] for s in previous["series"]}
        if entry["series"] not in checked[previous_hash]:
            raise ValueError("Economic series absent from its original registry")


def next_month(d):
    return date(d.year + (d.month == 12), d.month % 12 + 1, 1)


def next_observation(d, frequency):
    if frequency == 'monthly':
        return next_month(d)
    if frequency == 'quarterly':
        return next_month(next_month(next_month(d)))
    if frequency in {'weekly_saturday','weekly_friday'}:
        return d + timedelta(days=7)
    if frequency == 'daily_weekday':
        d += timedelta(days=1)
        while d.weekday() >= 5:
            d += timedelta(days=1)
        return d
    raise ValueError('Unsupported economic frequency')


def first_observation(start, frequency):
    if frequency in {'weekly_saturday','weekly_friday'}:
        return start+timedelta(days=((5 if frequency=='weekly_saturday' else 4)-start.weekday())%7)
    if frequency=='daily_weekday':
        while start.weekday() >= 5:
            start += timedelta(days=1)
    return start


def planned_vintages(config, now):
    """Previous-day archive before each first-session decision's prior close.

    Daily captures after recorder launch catch up calendar gaps after outages.
    Acquisition prioritizes the latest completed NY archive, then oldest backlog.
    """
    today = now.astimezone(NY).date()
    cutoff = today - timedelta(days=1)
    dates = {cutoff}
    if config.get('capture_latest_signal_vintage'):
        # The next-session indicative signal uses one extra day of vintage lag
        # before the latest completed trading close, including launch catch-up.
        dates.add(previous_us_trading_day(today)-timedelta(days=1))
    cursor = date.fromisoformat(config["decision_start"]).replace(day=1)
    while cursor <= today:
        decision = next_us_trading_day(cursor - timedelta(days=1))
        vintage = previous_us_trading_day(decision) - timedelta(days=1)
        if vintage <= cutoff:
            dates.add(vintage)
        cursor = next_month(cursor)
    cursor = date.fromisoformat(config["prospective_start"])
    while cursor <= cutoff:
        dates.add(cursor)
        cursor += timedelta(days=1)
    return [str(cutoff)] + sorted(str(d) for d in dates if d != cutoff)


def fetch_csv(url):
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 economic research recorder"}), timeout=25) as response:
        result = response.read(4_000_001)
    if len(result) > 4_000_000:
        raise ValueError("Economic source exceeds bounded response size")
    return result


def audit_csv(content, series, vintage, start):
    reader = csv.DictReader(io.StringIO(content.decode("utf-8-sig")))
    column = series["id"] + "_" + vintage.replace("-", "")
    if reader.fieldnames != ["observation_date", column]:
        raise ValueError("Economic identity/vintage header mismatch")
    rows, prior = [], None
    for raw in reader:
        if set(raw) != {"observation_date", column} or raw[column] is None:
            raise ValueError("Malformed economic observation")
        d = date.fromisoformat(raw["observation_date"])
        if not start <= str(d) <= vintage or (prior and d <= prior):
            raise ValueError("Economic dates are duplicate, unordered or outside the requested vintage")
        frequency = series['frequency']
        valid = (d.day == 1 if frequency=='monthly' else
                 d.day == 1 and d.month in {1,4,7,10} if frequency=='quarterly' else
                 d.weekday() == 5 if frequency=='weekly_saturday' else
                 d.weekday() == 4 if frequency=='weekly_friday' else
                 d.weekday() < 5 if frequency=='daily_weekday' else False)
        if not valid:
            raise ValueError("Economic frequency mismatch")
        if prior and d != next_observation(prior,frequency):
            raise ValueError("Economic calendar gap; no implicit fill permitted")
        value = None if raw[column] in {"", ".", "ND"} else Decimal(raw[column])
        if value is not None and (not value.is_finite() or not series["min"] <= value <= series["max"]):
            raise ValueError("Economic level outside declared domain")
        rows.append(dict(date=str(d), value=None if value is None else str(value)))
        prior = d
    if len(rows) < series["minimum_rows"]:
        raise ValueError("Economic history is too short")
    first = first_observation(date.fromisoformat(start),series['frequency'])
    unsupported_prefix = []
    if series['frequency']=='daily_weekday':
        from systematic_trading.live.trading_calendar import is_us_trading_day
        # ALFRED omits the initial closed holiday before its first numeric value
        # (Jan 2, 2006), but retains null holidays inside the returned history.
        # Admit only closed initial weekdays and disclose them; never manufacture
        # rows or excuse a missing open session such as Jan 3.
        while str(first)<rows[0]['date'] and not is_us_trading_day(first):
            unsupported_prefix.append(str(first))
            first=next_observation(first,'daily_weekday')
    if rows[0]["date"] != str(first):
        raise ValueError("Economic history starts late")
    # An old endpoint may be published for inspection, but cannot enter a signal.
    age = (date.fromisoformat(vintage) - prior).days
    usable = rows[-1]["value"] is not None and age <= series["max_age_days"]
    return dict(observations=rows, first=rows[0]["date"], last=rows[-1]["date"], rows=len(rows),
                missing=sum(r["value"] is None for r in rows), age_days=age, usable=usable,
                status="audited_with_limitations" if usable else "stale_or_missing_endpoint",
                policy=POLICY, limitations=LIMITATIONS, unsupported_prefix_dates=unsupported_prefix)


def checked_document(root, batch, name):
    root = Path(root).resolve()
    if sha256(root / "manifest.json") != batch:
        raise ValueError("Economic publication manifest changed")
    files = json.loads((root / "manifest.json").read_text(encoding="utf8"))
    if name not in files:
        raise ValueError("Economic document is not in the manifest")
    for relative, expected in files.items():
        path = (root / relative).resolve()
        if not path.is_relative_to(root) or sha256(path) != expected:
            raise ValueError("Economic publication input changed: " + relative)
    return json.loads((root / name).read_text(encoding="utf8"))


def publish_files(analytics, source, root, documents, *, provenance, observations=()):
    files = {p.name: sha256(p) for p in root.iterdir() if p.is_file() and p.name != "manifest.json"}
    atomic_json(root / "manifest.json", files)
    batch = sha256(root / "manifest.json")
    analytics.publish(source, batch, observations,
        [dict(point_key=k, media_type="application/json", payload=encode(v)) for k, v in documents.items()],
        provenance=dict(provenance, root=str(root.resolve()), batch=batch))
    return batch


def capture(settings, analytics, config, series, vintage, now, fetch):
    params = dict(id=series["id"], cosd=config["observation_start"], coed=vintage, vintage_date=vintage)
    url = "https://alfred.stlouisfed.org/graph/alfredgraph.csv?" + urlencode(params)
    root = settings.data_dir / "governance/economic-captures" / series["id"] / vintage / uuid4().hex
    root.mkdir(parents=True)
    receipt = dict(series=series["id"], vintage=vintage, url=url, attempted_at=now.isoformat(),
                   config_sha256=sha256(settings.economic_recorder_config_path), code_sha256=sha256(Path(__file__)))
    atomic_json(root / "receipt.json", receipt)
    try:
        content = fetch(url)
        # Retrieval time must follow the response, not be inherited from a run's start.
        first_seen = max(now, datetime.now(UTC))
        (root / "source.csv").write_bytes(content)
        receipt.update(first_seen_at=first_seen.isoformat(), source_sha256=sha256(root / "source.csv"))
        atomic_json(root / "receipt.json", receipt)
        audit = audit_csv(content, series, vintage, config["observation_start"])
        available = datetime.combine(date.fromisoformat(vintage), time.max, NY).astimezone(UTC)
        snapshot = dict(series=series, vintage=vintage, archive_available_at=available.isoformat(),
                        first_seen_at=first_seen.isoformat(), receipt=receipt, **audit)
        atomic_json(root / "snapshot.json", snapshot)
        atomic_json(root / "config.json", config)
        rows = [dict(point_key=series["id"] + "/" + vintage, family="economic_vintage", entity=series["id"],
                     observed_at=audit["last"], available_at=first_seen.isoformat(), payload=encode(snapshot))]
        provenance = dict(series=series["id"], vintage=vintage, first=audit["first"], last=audit["last"],
                          rows=audit["rows"], missing=audit["missing"], usable=audit["usable"],
                          first_seen_at=first_seen.isoformat(), archive_available_at=available.isoformat(),
                          config_sha256=receipt["config_sha256"], policy=POLICY)
        batch = publish_files(analytics, PREFIX + series["id"] + "/" + vintage, root,
                              dict(snapshot=snapshot), provenance=provenance, observations=rows)
        checked_document(root, batch, "snapshot.json")
        return dict(provenance, root=str(root.resolve()), batch=batch)
    except Exception as exc:
        atomic_json(root / "failure.json", dict(message=str(exc), attempted_at=now.isoformat()))
        raise


def load_catalog(analytics):
    p = analytics.latest(CATALOG)
    if not p:
        raise ValueError("Economic history has not completed a verified publication")
    root = json.loads(p["provenance"])["root"]
    return checked_document(root, p["version"], "catalog.json"), dict(root=root, batch=p["version"])


class EconomicInputs:
    """Pinned published snapshots only; consumers must name availability policy."""
    def __init__(self, root, batch):
        self.catalog = checked_document(root, batch, "catalog.json")
        self.batch = batch

    def snapshot(self, series, vintage, *, decision_at=None, availability="first_seen"):
        if availability not in {"first_seen", "archive_daily"}:
            raise ValueError("Unknown economic availability policy")
        entry = next((r for r in self.catalog["snapshots"] if r["series"] == series and r["vintage"] == vintage), None)
        if entry is None:
            raise ValueError("Required economic vintage is unpublished; no substitution")
        data = checked_document(entry["root"], entry["batch"], "snapshot.json")
        if data["series"]["id"] != series or data["vintage"] != vintage or data["policy"] != POLICY:
            raise ValueError("Economic publication identity mismatch")
        if decision_at is not None:
            if decision_at.tzinfo is None:
                raise ValueError("Decision timestamp must include timezone")
            boundary = datetime.fromisoformat(data["first_seen_at"] if availability == "first_seen" else data["archive_available_at"])
            if decision_at <= boundary:
                raise ValueError("Economic vintage unavailable at decision time")
            age = (decision_at.astimezone(NY).date() - date.fromisoformat(data["last"])).days
            if not data["usable"] or age > data["series"]["max_age_days"]:
                raise ValueError("Economic input is stale or missing")
        return data


def refresh_economics(settings, analytics, *, now=None, fetch=fetch_csv):
    config = configuration(settings)
    if not settings.governed_refresh_enabled or not config["enabled"]:
        return False
    now = now or datetime.now(UTC)
    with exclusive_lock(settings.data_dir / "run/economic-recorder.lock"):
        path = settings.data_dir / "governance/economic-recorder-state.json"
        state = json.loads(path.read_text(encoding="utf8")) if path.exists() else {}
        # Recover committed captures after a crash before catalog publication.
        committed = analytics.publication_index(PREFIX)
        config_hash = sha256(settings.economic_recorder_config_path)
        entries = {source.removeprefix(PREFIX): dict(json.loads(p["provenance"]), batch=p["version"])
                   for source, p in committed.items()}
        verify_registry_entries(config, config_hash, entries)
        for key, entry in entries.items():
            state[key] = dict(status="published", batch=entry["batch"],
                              attempted_at=state.get(key, {}).get("attempted_at", entry["first_seen_at"]))
        planned = [(s, v) for v in planned_vintages(config, now) for s in config["series"]]
        pending, errors, changed = [], [], False
        for series, vintage in planned:
            key = series["id"] + "/" + vintage
            if key in entries:
                continue
            old = state.get(key, {})
            if old and (now - datetime.fromisoformat(old["attempted_at"])).total_seconds() < 300:
                continue
            if len(pending) >= config["max_captures_per_cycle"]:
                break
            pending.append((key, series, vintage))
            state[key] = dict(status="acquiring", attempted_at=now.isoformat())
        atomic_json(path, state)
        # Independent source identities; the catalog commits only after their
        # individual exact-readback publications. Bound external I/O to three.
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = {pool.submit(capture, settings, analytics, config, series, vintage, now, fetch):key
                       for key, series, vintage in pending}
            for future in as_completed(futures):
                key = futures[future]
                try:
                    entries[key] = future.result()
                    state[key].update(status="published", batch=entries[key]["batch"])
                    changed = True
                except Exception as exc:
                    state[key].update(status="quarantined", message=str(exc))
                    errors.append(key + ": " + str(exc))
                atomic_json(path, state)
        catalog = dict(policy=POLICY, config=config, snapshots=sorted(entries.values(), key=lambda e:(e["series"], e["vintage"])),
                       expected=len(planned), completed=sum(s["id"] + "/" + v in entries for s, v in planned),
                       through=planned[0][1], limitations=LIMITATIONS)
        latest = analytics.latest(CATALOG)
        if not latest or load_catalog(analytics)[0] != catalog:
            root = settings.data_dir / "governance/economic-catalogs" / digest(encode(catalog))
            root.mkdir(parents=True, exist_ok=True)
            atomic_json(root / "catalog.json", catalog)
            publish_files(analytics, CATALOG, root, dict(catalog=catalog), provenance=dict(policy=POLICY))
            changed = True
        if errors:
            raise ValueError("Economic recorder: " + "; ".join(errors))
        return changed


def recorder_status(settings):
    path = settings.data_dir / "governance/economic-recorder-state.json"
    state = json.loads(path.read_text(encoding="utf8")) if path.exists() else {}
    return dict(enabled=configuration(settings)["enabled"] and settings.governed_refresh_enabled,
                owner="application", failures=[dict(key=k, **v) for k, v in state.items() if v["status"] != "published"])
