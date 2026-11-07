"""Date/identifier-qualified CRSP comparison; licensed row details stay local."""
from collections import Counter
from decimal import Decimal
import gzip
import json
from pathlib import Path
import statistics

import capture_crsp_pilot as capture
import capture_large_volume_sources as large
from reconcile_large_volume_sources import baseline
from probe_alpaca_sip_source import save, sha


def retained(root, name):
    m = json.loads((root / "manifest.json").read_text())
    if m["status"] != "captured_pending_qualification" or m["protocol_sha256"] != capture.PROTOCOL_HASH:
        raise ValueError("Incomplete or wrong CRSP source")
    for f,h in m["files"].items():
        if sha((root/f).read_bytes()) != h:
            raise ValueError("Changed WRDS capture recipe")
    receipt = next(r for r in m["queries"] if r["name"] == name)
    blob = (root/receipt["path"]).read_bytes()
    raw = gzip.decompress(blob)
    if sha(blob) != receipt["sha256"] or sha(raw) != receipt["response_sha256"]:
        raise ValueError("Changed WRDS source rows")
    data = json.loads(raw)
    if len(data["rows"]) != receipt["row_count"]:
        raise ValueError("WRDS source count differs")
    return [dict(zip(data["columns"],r,strict=True)) for r in data["rows"]]


def select_identity(histories, identity, day, bridge=None):
    """Current headers and an ambiguous ticker never decide historical share class."""
    symbol, isin = identity["symbol"], identity["isin"]
    if isin.startswith("US") and len(isin) == 12:
        cusip9 = isin[2:-1]
    elif bridge and bridge.get("isin") == isin:
        cusip9 = bridge["cusip"]
    else:
        return None, "non_US_ISIN_requires_retained_CUSIP_bridge"
    candidates = [r for r in histories if r["ticker"] == symbol and r["tradingsymbol"] == symbol
                  and r["cusip9"] == cusip9 and r["secinfostartdt"] <= day <= r["secinfoenddt"]]
    if len(candidates) != 1:
        return None, "missing_or_ambiguous_dated_identity"
    return candidates[0], None


def number(value):
    if value is None:
        raise ValueError("Missing numeric source field")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite source field")
    return result


def summary(rows):
    return dict(rows=len(rows),exact_volume_vs_sip=sum(r["volume_minus_sip"] == 0 for r in rows),
        exact_volume_vs_published=sum(r["volume_minus_published"] == 0 for r in rows),
        median_abs_volume_vs_sip_percent=statistics.median(abs(r["volume_vs_sip_percent"]) for r in rows),
        max_abs_volume_vs_sip_percent=max(abs(r["volume_vs_sip_percent"]) for r in rows),
        close_vs_published_within_half_cent=sum(abs(r["close_minus_published"]) <= .005 for r in rows),
        max_abs_close_vs_published=max(abs(r["close_minus_published"]) for r in rows),
        price_flags=dict(Counter(r["price_flag"] for r in rows)),
        return_missing_flags=dict(Counter(r["return_missing_flag"] for r in rows)))


def audit(root):
    raw = (capture.STUDY / "protocol.json").read_bytes()
    if sha(raw) != capture.PROTOCOL_HASH:
        raise ValueError("Changed CRSP inspection scope")
    p = json.loads(raw)
    history = retained(root,"security-history")
    daily = retained(root,"daily")
    retained(root,"legacy-name-history")
    frozen = baseline(large.protocol())
    daily_index = {}
    for row in daily:
        key = row["permno"],row["dlycaldt"]
        if key in daily_index:
            raise ValueError("Duplicate CRSP daily row")
        daily_index[key] = row
    rows, exclusions, selected, events = [], [], set(), []
    days = sorted({r["activity_date"] for r in frozen.values()})
    for identity in p["identities"]:
        symbol = identity["symbol"]
        for day in days:
            match,error = select_identity(history,identity,day)
            if error:
                exclusions.append(dict(symbol=symbol,date=day,reason=error))
                continue
            d = daily_index.get((match["permno"],day))
            if d is None or d["ticker"] != symbol or d["cusip"] != match["cusip9"][:8]:
                raise ValueError("Daily row is missing or differs from dated identity")
            v,c = number(d["dlyvol"]),number(d["dlyclose"])
            if v < 0 or v != v.to_integral_value() or c <= 0:
                raise ValueError("Unsupported CRSP price/volume")
            old = frozen[symbol + "/" + day]
            sip,previous = number(old["sip_raw_volume"]),number(old["published_raw_volume"])
            rows.append(dict(symbol=symbol,date=day,permno=match["permno"],cusip9=match["cusip9"],
                crsp_volume=int(v),sip_volume=int(sip),published_volume=float(previous),crsp_close=float(c),
                volume_minus_sip=float(v-sip),volume_minus_published=float(v-previous),
                volume_vs_sip_percent=float(100*(v-sip)/sip),
                close_minus_published=float(c-number(old["paired_published_raw_close"])),
                price_flag=d["dlyprcflg"],return_missing_flag=d["dlyretmissflg"],
                historical_published_at=None,source_identity_start=match["secinfostartdt"],
                source_identity_end=match["secinfoenddt"]))
            selected.add(match["permno"])
            if number(d["dlyorddivamt"]) or number(d["dlynonorddivamt"]) or number(d["dlyfacprc"]) != 1:
                events.append({k:d[k] for k in ("permno","ticker","dlycaldt","dlyorddivamt","dlynonorddivamt","dlyfacprc")})
    if not rows:
        raise ValueError("No identifier-qualified comparison rows")
    detail = dict(rows=rows,excluded=exclusions,action_fields=events)
    detail_path = root / "dated-identity-comparison.json"
    save(detail_path,detail)
    action_path = Path(p["baseline_publication"]["root"]) / "actions.json"
    published_actions = json.loads(action_path.read_text())
    actual_dividends = {(r["ticker"],r["dlycaldt"],number(r["dlyorddivamt"])+number(r["dlynonorddivamt"]))
                        for r in events if number(r["dlyorddivamt"])+number(r["dlynonorddivamt"])}
    expected_dividends = {(s,r["date"],number(r["amount"])) for s in {r["symbol"] for r in rows}
                          for r in published_actions[s] if r["kind"] == "dividends"}
    result = dict(status="source_comparison_complete_with_identity_exclusion",protocol_sha256=capture.PROTOCOL_HASH,
        source_archive=str(root),source_manifest_sha256=sha((root/"manifest.json").read_bytes()),
        raw_daily_rows=len(daily),candidate_permnos=len({r["permno"] for r in daily}),
        matched_symbols=sorted({r["symbol"] for r in rows}),matched_sessions=len(rows),
        exclusions=[dict(symbol=s,rows=sum(r["symbol"]==s for r in exclusions),
                         reasons=sorted({r["reason"] for r in exclusions if r["symbol"]==s}))
                    for s in sorted({r["symbol"] for r in exclusions})],
        unused_candidate_permnos=sorted({r["permno"] for r in daily}-selected),
        summary=summary(rows),by_symbol={s:summary([r for r in rows if r["symbol"]==s]) for s in sorted({r["symbol"] for r in rows})},
        nonzero_distribution_or_price_factor_rows=len(events),
        cash_distribution_comparison=dict(crsp_events=len(actual_dividends),published_events=len(expected_dividends),
            exact_date_amount_set_match=actual_dividends==expected_dividends,
            crsp_only=len(actual_dividends-expected_dividends),published_only=len(expected_dividends-actual_dividends)),
        details=dict(path=str(detail_path),sha256=sha(detail_path.read_bytes())),
        findings=["WSO Class A selected by dated CUSIP9 and trading symbol; WSO/WSOB Class B retained separately, never substituted.",
                  "Foreign FLEX ISIN has no retained same-record CUSIP bridge; its 253 rows remain unjoined.",
                  "Legacy name history stops at 2024-12-31; CIZ dated intervals cover the requested 2025 dates.",
                  "CRSP daily volume is independent evidence, not a trade-condition reconstruction.",
                  "Current extract and effective identity dates do not certify historical availability of this vendor vintage."],
        catalog_publications=0,strategy_replays=0,runner_sha256=sha(Path(__file__).read_bytes()))
    save(capture.STUDY / "assessment.json",result)
    print(json.dumps({k:result[k] for k in ("status","raw_daily_rows","candidate_permnos","matched_sessions","exclusions","summary")}),flush=True)
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive",type=Path)
    audit(parser.parse_args().archive)
