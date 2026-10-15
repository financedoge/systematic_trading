"""The planning inventory must fail closed and cannot manufacture admission."""

import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_etf_inventory.py"
SPEC = importlib.util.spec_from_file_location("etf_inventory", SCRIPT)
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


@pytest.fixture(scope="module")
def result():
    return inventory.build(inventory.DEFAULT_ROOT)


def test_inventory_separates_listing_data_and_authority(result):
    rows = result["candidates"]
    assert len(rows) == 299
    assert len({r["candidate_id"] for r in rows}) == len(rows)
    assert all(not r["inventory_grants_research_admission"] for r in rows)
    assert all(not r["inventory_grants_execution_authority"] for r in rows)
    assert sum(r["stage"] == "wave_1_proposed" for r in rows) == 38
    assert sum(r["stage"] == "baseline" for r in rows) == 14
    assert sum(r["governed"] is None for r in rows) == 247


def test_regime_change_does_not_join_prices_or_claim_closure(result):
    rows = {r["symbol"]: r for r in result["candidates"]}
    old, new = rows["HYXU"], rows["EUHY"]
    assert old["fund_entity_reference"] == new["fund_entity_reference"]
    assert old["peer_group"] != new["peer_group"]
    assert old["governed"]["last"] == "2020-04-01"
    assert new["governed"] is None
    assert old["closure_date"] is None
    assert old["stage"] == new["stage"] == "hold"
    assert old["record_kind"] == "legacy_symbol_regime"


def test_missing_metadata_and_existing_hold_remain_explicit(result):
    rows = {r["symbol"]: r for r in result["candidates"]}
    assert rows["XOP"]["stage"] == "hold"
    assert "existing_admission_hold" in rows["XOP"]["gaps"]
    assert "listing-boundary" in rows["XOP"]["admission_hold"]["conflict"]
    assert rows["SPY"]["listing_currency"] is None
    assert "listing_currency_confirmation" in rows["SPY"]["gaps"]
    assert rows["XLE"]["listing_currency"] == "USD"
    assert rows["XLE"]["currency_verification"] == "published_issuer_evidence"


def test_boundary_taxonomy_does_not_count_equities_as_commodities(result):
    rows = {r["symbol"]: r for r in result["candidates"]}
    assert rows["SOXX"]["asset_class"] == rows["PICK"]["asset_class"] == "equity"
    assert rows["SLV"]["asset_class"] == "commodity"
    assert rows["SLV"]["secondary_tags"] == ["industrial_demand"]
    assert (
        rows["SLV"]["duplicate_review_group"] == rows["SIVR"]["duplicate_review_group"]
    )


def test_tampered_source_is_rejected(tmp_path):
    (tmp_path / "source.txt").write_text("tampered", encoding="utf8")
    (tmp_path / "source-manifest.json").write_text(
        json.dumps(
            {
                "files": {
                    "test": {
                        "file": "source.txt",
                        "stored_sha256": "0" * 64,
                        "content_sha256": "0" * 64,
                    }
                }
            }
        ),
        encoding="utf8",
    )
    with pytest.raises(ValueError, match="Source hash mismatch"):
        inventory.read_sources(tmp_path)


def test_manifest_cannot_read_outside_inventory(tmp_path):
    (tmp_path / "source-manifest.json").write_text(
        json.dumps({"files": {"test": {"file": "../outside.txt"}}}), encoding="utf8"
    )
    with pytest.raises(ValueError, match="Unsafe source path"):
        inventory.read_sources(tmp_path)


def issuer_table(return_value="999"):
    headers = [
        "Ticker",
        "Name",
        "12m Trailing Yield (%)",
        "As of",
        "YTD Return (%)",
        "As of",
        "Incept. Date",
    ]
    cells = [
        '<a href="/us/products/123/example">ABC</a>',
        "Example ETF",
        "7",
        "today",
        return_value,
        "today",
        "Jan 01, 2020",
    ]
    return (
        "<table><tr>"
        + "".join(f"<th>{x}</th>" for x in headers)
        + "</tr><tr>"
        + "".join(f"<td>{x}</td>" for x in cells)
        + "</tr></table>"
    )


def test_issuer_performance_is_not_an_inventory_input():
    assert inventory.issuer_metadata(issuer_table("999")) == inventory.issuer_metadata(
        issuer_table("-999")
    )
    assert inventory.issuer_metadata(issuer_table())["ABC"] == {
        "name": "Example ETF",
        "inception": "2020-01-01",
        "issuer_product_id": "ishares:123",
        "issuer_url": "https://www.ishares.com/us/products/123/example",
    }


def test_schema_drift_rejected_instead_of_misreading_inception():
    with pytest.raises(ValueError, match="schema changed"):
        inventory.issuer_metadata(issuer_table().replace("Incept. Date", "Price"))


def test_mutual_fund_table_is_ignored():
    assert len(inventory.issuer_metadata(issuer_table() + issuer_table())) == 1


def test_catalog_batch_tamper_rejected(monkeypatch):
    sources = inventory.read_sources(inventory.DEFAULT_ROOT)
    sources["governance-manifest.json"] += b" "
    monkeypatch.setattr(inventory, "read_sources", lambda root: sources)
    with pytest.raises(ValueError, match="Governance batch identity mismatch"):
        inventory.build(inventory.DEFAULT_ROOT)


def test_missing_series_is_not_promoted_from_issuer_metadata(result):
    row = next(r for r in result["candidates"] if r["symbol"] == "SOXX")
    assert row["issuer_product_id"]
    assert row["governed"] is None
    assert "no_series_in_pinned_publication" in row["gaps"]
