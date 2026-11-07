"""Publish isolated source-audit evidence with unknown historical availability."""
import argparse
from datetime import UTC, datetime
import json
from pathlib import Path

from systematic_trading.config import AppSettings
from systematic_trading.market_data.analytics_store import AnalyticsStore, encode, digest
from probe_alpaca_sip_source import ROOT, save, sha


SCOPES = {
    "crsp": ("p421-crsp-qualification-20261107-v1", "governance/pilots/p421-crsp-daily-v1"),
    "large": ("p421-large-volume-20261107-v1", "governance/pilots/p421-large-volume-v1"),
    "early-close": ("p421-crsp-early-close-20261107-v1", "governance/pilots/p421-early-close-v1"),
}


def observations(rows, family):
    seen, result = set(), []
    for r in rows:
        key = r["symbol"] + "/" + r["date"]
        if key in seen:
            raise ValueError("Duplicate source-audit identity")
        if r.get("historical_published_at") is not None:
            raise ValueError("This audit does not certify historical availability")
        seen.add(key)
        result.append(dict(point_key=key,family=family,entity=r["symbol"],
                           observed_at=r["date"]+"T00:00:00+00:00",available_at=None,payload=encode(r)))
    return result


def publish(scope):
    folder,source = SCOPES[scope]
    study = ROOT / "research" / folder
    assessment = json.loads((study / "assessment.json").read_text())
    refs = {}
    if scope == "crsp":
        detail = Path(assessment["details"]["path"])
        if sha(detail.read_bytes()) != assessment["details"]["sha256"]:
            raise ValueError("Changed licensed comparison detail")
        rows = json.loads(detail.read_text())["rows"]
        archive = Path(assessment["source_archive"])
        m = json.loads((archive/"manifest.json").read_text())
        if sha((archive/"manifest.json").read_bytes()) != assessment["source_manifest_sha256"]:
            raise ValueError("Changed WRDS source manifest")
        for q in m["queries"]:
            if q.get("path") and sha((archive/q["path"]).read_bytes()) != q["sha256"]:
                raise ValueError("Changed WRDS source response")
        refs[str(detail)] = sha(detail.read_bytes())
    else:
        if assessment["status"] != "comparison_complete":
            raise ValueError("Independent comparison is incomplete")
        rows = assessment["cases"]
        for r in assessment["sources"]:
            root = Path(r["archive"])
            if sha((root/"manifest.json").read_bytes()) != r["manifest_sha256"]:
                raise ValueError("Changed source manifest")
            m = json.loads((root/"manifest.json").read_text())
            for q in m["requests"]:
                if q.get("path") and sha((root/q["path"]).read_bytes()) != q["sha256"]:
                    raise ValueError("Changed raw response")
            refs[str(root/"manifest.json")] = r["manifest_sha256"]
    for name in ("protocol.json","assessment.json"):
        refs[str(study/name)] = sha((study/name).read_bytes())
    refs[str(Path(__file__))] = sha(Path(__file__).read_bytes())
    version = digest(encode(refs))
    obs = observations(rows,"p421_source_audit_" + scope.replace("-","_"))
    docs = [dict(point_key=name,media_type="application/json",payload=(study/name).read_text(encoding="utf8"))
            for name in ("protocol.json","assessment.json")]
    settings = AppSettings()
    if settings.market_data_store_backend != "parquet":
        raise ValueError("Native analytical runtime required")
    store = AnalyticsStore.from_settings(settings)
    before = store.latest("governance/catalog")["version"]
    store.publish(source,version,obs,docs,provenance=dict(source_files=refs,research_only=True,
        field_audit_only=True,strategy_input_use=False,historical_available_at=None,
        retention="Active qualification evidence; licensed source rows remain local."))
    back = store.pinned_rows("observations",source,version)
    documents = store.pinned_rows("documents",source,version)
    if {r["point_key"]:digest(r["payload"]) for r in back} != {r["point_key"]:digest(r["payload"]) for r in obs}:
        raise ValueError("Source-audit observation readback failed")
    if any(r["available_at"] is not None for r in back):
        raise ValueError("Invented historical availability")
    if {r["point_key"]:digest(r["payload"]) for r in documents} != {r["point_key"]:digest(r["payload"]) for r in docs}:
        raise ValueError("Source-audit document readback failed")
    receipt = dict(source_id=source,version=version,observations=len(back),documents=len(documents),
        verified_at=datetime.now(UTC).isoformat(),source_files=refs,
        native_storage=store.storage_name,exact_payload_readback=True,all_historical_available_at_null=True,
        main_catalog_before=before,main_catalog_after=store.latest("governance/catalog")["version"],
        active_catalog_written=False,registered_asset_migrations=0)
    save(study / "publication.json",receipt)
    print(json.dumps({k:receipt[k] for k in ("source_id","version","observations","documents","exact_payload_readback")}),flush=True)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("scope",choices=tuple(SCOPES))
    publish(p.parse_args().scope)
