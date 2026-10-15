"""Rebuild the frozen P4.16d reference inventory offline; never admit or trade.

Only reference fields are extracted from the issuer page. Performance, prices,
fund size and yields on that page are deliberately not inputs to this inventory.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime
import gzip
import hashlib
from html.parser import HTMLParser
import io
import json
from pathlib import Path
import statistics


DEFAULT_ROOT = (
    Path(__file__).resolve().parents[1] / "research/etf-universe-inventory-2026-10-13"
)
EXCHANGES = {"P": "NYSE Arca", "Q": "Nasdaq", "Z": "Cboe BZX", "N": "NYSE"}
COMMON_GAPS = [
    "dated_mandate_and_security_master_review",
    "historical_membership_and_closure_coverage",
    "causal_liquidity_and_spread_evidence",
    "dated_holdings_overlap_review",
    "fresh_broker_contract_permissions_calendar_lot_and_reconciliation",
    "expanded_app_execution_and_parity_contract",
]


class IssuerTable(HTMLParser):
    """Strict first-table extraction; ignore the later mutual-fund table."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.table = 0
        self.in_table = False
        self.cell = None
        self.row = []
        self.rows = []
        self.href = None
        self.headers = []
        self.header = False

    def handle_starttag(self, tag, attrs):
        if tag == "table":
            self.table += 1
            self.in_table = self.table == 1
        if not self.in_table:
            return
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"}:
            self.cell, self.href, self.header = [], None, tag == "th"
        elif tag == "a" and self.cell is not None:
            self.href = dict(attrs).get("href")

    def handle_data(self, data):
        if self.in_table and self.cell is not None:
            self.cell.append(data)

    def handle_endtag(self, tag):
        if not self.in_table:
            return
        if tag in {"td", "th"} and self.cell is not None:
            value = " ".join("".join(self.cell).split())
            if self.header:
                self.headers.append(value)
            else:
                self.row.append((value, self.href))
            self.cell = None
        elif tag == "tr" and self.row:
            self.rows.append(self.row)
        elif tag == "table":
            self.in_table = False


def issuer_metadata(html):
    parser = IssuerTable()
    parser.feed(html)
    if parser.headers[:2] != ["Ticker", "Name"] or parser.headers[6:7] != [
        "Incept. Date"
    ]:
        raise ValueError("Issuer metadata table schema changed")
    result = {}
    for cells in parser.rows:
        if len(cells) != len(parser.headers):
            raise ValueError("Incomplete issuer metadata row")
        symbol, name, inception = cells[0][0], cells[1][0], cells[6][0]
        url = cells[0][1]
        if not url or not url.startswith("/us/products/") or symbol in result:
            raise ValueError("Duplicate or unsupported issuer identity")
        product_id = url.split("/")[3]
        if not product_id.isdigit():
            raise ValueError("Invalid issuer product ID")
        result[symbol] = dict(
            name=name,
            inception=datetime.strptime(inception, "%b %d, %Y").date().isoformat(),
            issuer_product_id="ishares:" + product_id,
            issuer_url="https://www.ishares.com" + url,
        )
    return result


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_sources(root):
    manifest = json.loads((root / "source-manifest.json").read_text(encoding="utf8"))
    result = {}
    for name, entry in manifest["files"].items():
        source_path = root / entry["file"]
        path = source_path.resolve()
        if not path.is_relative_to(root.resolve()) or source_path.is_symlink():
            raise ValueError("Unsafe source path")
        data = path.read_bytes()
        if sha(data) != entry["stored_sha256"]:
            raise ValueError("Source hash mismatch: " + name)
        raw = gzip.decompress(data) if entry["file"].endswith(".gz") else data
        if sha(raw) != entry["content_sha256"]:
            raise ValueError("Source content mismatch: " + name)
        result[name] = raw
    return result


def build(root):
    sources = read_sources(root)
    seed = json.loads(sources["candidate-seed.json"])
    taxonomy = json.loads(sources["taxonomy.json"])
    protocol = json.loads(sources["protocol.json"])
    events = json.loads(sources["identity-events.json"])
    publication = json.loads(sources["governance-publication.json"])
    manifest = json.loads(sources["governance-manifest.json"])
    if sha(sources["governance-manifest.json"]) != publication["version"]:
        raise ValueError("Governance batch identity mismatch")
    if sha(sources["governance-catalog.json"]) != manifest["catalog.json"]:
        raise ValueError("Governance catalog hash mismatch")
    catalog = {r["symbol"]: r for r in json.loads(sources["governance-catalog.json"])}
    evidence = json.loads(sources["governance-evidence.json"])
    if evidence["batch"] != publication["version"]:
        raise ValueError("Audit evidence belongs to another batch")
    holds = json.loads(sources["admission-holds.json"])
    configured = {
        r["symbol"]: r
        for r in json.loads(sources["research-etf-recorders.json"])["funds"]
    }
    issuer = issuer_metadata(sources["ishares-products.html"].decode("utf8"))
    directory = list(
        csv.DictReader(
            io.StringIO(sources["nasdaqtraded.txt"].decode("utf8")), delimiter="|"
        )
    )
    if not directory or not directory[-1]["Nasdaq Traded"].startswith(
        "File Creation Time:"
    ):
        raise ValueError("Incomplete listing directory")
    listings = {}
    for row in directory[:-1]:
        symbol = row["Symbol"]
        if symbol in listings:
            raise ValueError("Duplicate listing symbol")
        listings[symbol] = row
    groups = {g["peer_group"]: g for g in taxonomy["groups"]}
    candidates, seen, ids = [], set(), set()
    for candidate in seed["candidates"]:
        row = dict(candidate)
        symbol = row["symbol"]
        if symbol in seen or row["candidate_id"] in ids:
            raise ValueError("Duplicate candidate identity")
        seen.add(symbol)
        ids.add(row["candidate_id"])
        group = groups[row["peer_group"]]
        listing, metadata, audit = (
            listings.get(symbol),
            issuer.get(symbol, {}),
            catalog.get(symbol),
        )
        gaps = COMMON_GAPS.copy()
        row.update(
            asset_class=group["asset_class"],
            exposure_region=group["exposure_region"],
            exposure=group["exposure"],
            intended_listing_currency="USD",
            listing_currency=None,
            currency_verification="pending",
            issuer_product_id=None,
            isin=None,
            cusip=None,
            inception=None,
            listing_date=None,
            closure_date=None,
            closure_status="not_established_by_current_directory",
            mandate_history_status="unverified",
            metadata_sources=["nasdaqtraded.txt"] if listing else [],
        )
        row.update(metadata)
        if metadata:
            row["metadata_sources"].append("ishares-products.html")
        cfg = configured.get(symbol, {})
        recorder = (audit or {}).get("research_recorder", {})
        if recorder:
            row.update(
                isin=recorder["isin"],
                inception=recorder["inception"],
                listing_date=recorder.get("listing_date"),
                listing_currency=recorder["currency"],
                currency_verification="published_issuer_evidence",
            )
            row["metadata_sources"].append("governance-catalog.json/research_recorder")
        elif cfg:
            row.update(
                configured_isin_unverified_here=cfg["isin"],
                configured_inception=cfg["inception"],
            )
        if symbol == "EUHY":
            row.update(
                cusip="464286210",
                mandate_history_status="known_change_quarantined",
                lineage_event="hyxu-euhy-2025",
                metadata_sources=row["metadata_sources"]
                + ["euhy.html", "identity-events.json"],
            )
        if symbol == "HYXU":
            row.update(
                cusip="464286210",
                lineage_event="hyxu-euhy-2025",
                mandate_history_status="legacy_symbol_changed_not_fund_closed",
            )
        row["fund_entity_reference"] = (
            "cusip:" + row["cusip"]
            if row["cusip"]
            else "isin:" + row["isin"]
            if row["isin"]
            else row["issuer_product_id"] or row["candidate_id"]
        )
        row["record_kind"] = (
            "legacy_symbol_regime" if symbol == "HYXU" else "current_candidate"
        )
        row["name"] = (
            metadata.get("name")
            or (listing or {}).get("Security Name")
            or (audit or {}).get("name")
        )
        valid_listing = (
            listing and listing["ETF"] == "Y" and listing["Test Issue"] == "N"
        )
        row["listing_status"] = (
            "directory_etf_observed" if valid_listing else "missing_or_not_etf"
        )
        row["listing_exchange_code"] = (listing or {}).get("Listing Exchange")
        row["listing_venue"] = EXCHANGES.get(row["listing_exchange_code"])
        row["directory_round_lot"] = (listing or {}).get("Round Lot Size")
        row["round_lot_note"] = (
            "Directory quote round lot is not broker minimum order size"
        )
        if not valid_listing or row["listing_venue"] is None:
            gaps.append("current_listing_unresolved")
        if not row["listing_currency"]:
            gaps.append("listing_currency_confirmation")
        if not row["isin"] and not row["cusip"]:
            gaps.append("external_security_identifier")
        if not row["inception"]:
            gaps.append("issuer_inception_and_listing_boundary")
        row["governed"] = None
        if audit:
            proof = evidence["inputs"][symbol]
            for key in [
                "status",
                "first",
                "last",
                "rows",
                "raw_rows",
                "raw_volume_rows",
            ]:
                if audit.get(key) != proof["audit"].get(key):
                    raise ValueError(
                        "Catalog/audit disagreement: " + symbol + "/" + key
                    )
            row["governed"] = {
                k: audit.get(k)
                for k in [
                    "status",
                    "first",
                    "last",
                    "rows",
                    "raw_rows",
                    "raw_volume_rows",
                    "adjusted_internal_coverage_complete",
                    "raw_internal_coverage_complete",
                    "historical_available_at",
                    "identity_status",
                    "internal_gaps",
                    "conflict_dates",
                    "storage_batch",
                    "raw_tape_certified",
                    "full_listing_history_certified",
                ]
            }
            row["governed"].update(
                catalog_batch=publication["version"],
                audit_sha256=proof["audit_sha256"],
                bars_sha256=proof["bars_sha256"],
            )
            if audit["status"] != "audited_with_limitations":
                gaps.append("governance_status_" + audit["status"])
            if audit["last"] != protocol["required_completed_session"]:
                gaps.append("price_refresh_to_frozen_cutoff")
            if not audit["adjusted_internal_coverage_complete"]:
                gaps.append("adjusted_price_coverage")
            if (
                not audit["raw_internal_coverage_complete"]
                or audit["raw_volume_rows"] != audit["rows"]
            ):
                gaps.append("audited_raw_activity_coverage")
            gaps.append("historical_publication_availability_not_certified")
        else:
            gaps.append("no_series_in_pinned_publication")
        if symbol in holds:
            row["admission_hold"] = holds[symbol]
            gaps.append("existing_admission_hold")
        if symbol in {"EUHY", "HYXU"}:
            gaps.append("mandate_transition_and_alias_audit")
        row.update(
            gaps=sorted(set(gaps)),
            inventory_grants_research_admission=False,
            inventory_grants_execution_authority=False,
            secondary_tags=["industrial_demand"] if symbol in {"SLV", "SIVR"} else [],
        )
        candidates.append(row)
    stats = {
        "candidates": len(candidates),
        "proposed_peer_groups": len(groups),
        "fund_entity_references": len({r["fund_entity_reference"] for r in candidates}),
        "legacy_symbol_regimes": sum(
            r["record_kind"] == "legacy_symbol_regime" for r in candidates
        ),
        "singleton_groups": sum(
            n == 1 for n in Counter(r["peer_group"] for r in candidates).values()
        ),
        "directory_etfs_observed": sum(
            r["ETF"] == "Y" and r["Test Issue"] == "N" for r in listings.values()
        ),
        "issuer_reference_rows": len(issuer),
        "stages": dict(Counter(r["stage"] for r in candidates)),
        "asset_classes": dict(Counter(r["asset_class"] for r in candidates)),
        "governance_status": dict(
            Counter((r["governed"] or {}).get("status", "absent") for r in candidates)
        ),
        "price_current_to_cutoff": sum(
            bool(
                r["governed"]
                and r["governed"]["last"] == protocol["required_completed_session"]
            )
            for r in candidates
        ),
        "gaps": dict(Counter(g for r in candidates for g in r["gaps"])),
    }
    costs = estimate_costs(evidence["inputs"], [52, len(candidates)], protocol)
    return dict(
        version=seed["version"],
        date=seed["date"],
        publication=publication["version"],
        source_manifest_sha256=sha((root / "source-manifest.json").read_bytes()),
        protocol=protocol,
        identity_events=events,
        summary=stats,
        capacity_estimates=costs,
        candidates=sorted(candidates, key=lambda r: r["symbol"]),
    )


def estimate_costs(inputs, counts, protocol):
    compressed = [
        r["compressed_bytes"] / r["audit"]["rows"]
        for r in inputs.values()
        if r["audit"]["rows"]
    ]
    raw = [
        r["uncompressed_bytes"] / r["audit"]["rows"]
        for r in inputs.values()
        if "uncompressed_bytes" in r
    ]
    per_row, raw_row = statistics.median(compressed), statistics.median(raw)
    # Transparent planning scenarios, not observed wall time or database size.
    years, sessions, fields = 15, 252, 10
    return dict(
        compressed_bytes_per_row_median=per_row,
        uncompressed_bytes_per_row_median=raw_row,
        measured_files=len(compressed),
        measured_uncompressed_files=len(raw),
        caveat="File-density measurements only; HTTP/audit/ClickHouse/LEAN timings and peak RSS are not measured here. No concurrency change.",
        scenarios=[
            dict(
                candidates=n,
                years=years,
                sessions_per_year=sessions,
                rows=n * years * sessions,
                gzip_MiB=n * years * sessions * per_row / 2**20,
                json_MiB=n * years * sessions * raw_row / 2**20,
                dense_ten_field_float64_MiB=n * years * sessions * fields * 8 / 2**20,
                full_reacquisition_requests=n,
                incremental_rows_per_session=n,
                serial_acquisition_minutes_at_2s=n * 2 / 60,
                serial_acquisition_minutes_at_10s=n * 10 / 60,
                extra_replica_and_snapshot_multiplier=protocol[
                    "capacity_storage_multiplier"
                ],
            )
            for n in counts
        ],
    )


def matrix(result):
    gap_codes = {
        gap: f"G{index:02d}"
        for index, gap in enumerate(sorted(result["summary"]["gaps"]), 1)
    }
    lines = [
        "# P4.16d candidate gap matrix",
        "",
        "Generated offline; proposed classifications confer no research or trading authority.",
        "",
        "Full identifiers, field provenance and gaps: [inventory.json](inventory.json).",
        "",
        "Gap codes below apply to every marked row; none represents a passed gate.",
        "",
        "| Code | Outstanding evidence |",
        "| --- | --- |",
        *[f"| {code} | {gap.replace('_', ' ')} |" for gap, code in gap_codes.items()],
        "",
        "| Candidate | Stage | Proposed peer / overlap bucket | Listing venue | Inception | Pinned data status / end | Outstanding gaps |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in result["candidates"]:
        g = row["governed"]
        state = (g["status"] + " / " + g["last"]) if g else "not published"
        lines.append(
            f"| {row['symbol']} | {row['stage']} | {row['peer_group']} | {row['listing_venue'] or 'unresolved'} | {row['inception'] or 'unverified'} | {state} | {' '.join(gap_codes[g] for g in row['gaps'])} |"
        )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify hashes and exact deterministic outputs without writing",
    )
    args = parser.parse_args()
    result = build(args.root)
    outputs = {
        "inventory.json": json.dumps(
            result, indent=2, ensure_ascii=False, allow_nan=False
        )
        + "\n",
        "gap-matrix.md": matrix(result),
    }
    for name, content in outputs.items():
        path = args.root / name
        if args.check:
            if not path.exists() or path.read_text(encoding="utf8") != content:
                raise ValueError("Generated output changed: " + name)
        else:
            path.write_text(content, encoding="utf8", newline="\n")
    print(json.dumps(result["summary"], indent=2))


if __name__ == "__main__":
    main()
