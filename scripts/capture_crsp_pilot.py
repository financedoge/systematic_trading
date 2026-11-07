"""Retain a bounded, read-only WRDS identity/daily extract locally, never in Git."""
from datetime import UTC, datetime
import gzip
import hashlib
import json
from pathlib import Path

from setup_wrds_access import WrdsProxyTunnel, connect, default_passfile, write_ca_bundle


ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "research/p421-crsp-qualification-20261107-v1"
PROTOCOL_HASH = "9b3a51653ef6e2099116d07ce473871dfef3b26bf90f38c1ba0e798caec01544"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    raw = (STUDY / "protocol.json").read_bytes()
    if sha(raw) != PROTOCOL_HASH:
        raise ValueError("Changed bounded CRSP scope")
    p = json.loads(raw)
    helper = Path(__file__).with_name("setup_wrds_access.py")
    if sha(helper.read_bytes()) != p["connection_helper_sha256"]:
        raise ValueError("Changed TLS/passfile helper")
    root = Path("D:/systematic_trading_data/source-archives/wrds") / (
        "pilot-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ"))
    root.mkdir(parents=True, exist_ok=False)
    files = [Path(__file__), helper, STUDY / "protocol.json"]
    for f in files:
        (root / f.name).write_bytes(f.read_bytes())
    ca = root / "trusted-ca.pem"
    write_ca_bundle(ca)
    manifest = dict(status="in_progress", protocol_sha256=PROTOCOL_HASH, source_release=None,
        started_at=datetime.now(UTC).isoformat(), historical_availability_certified=False,
        files={f.name:sha(f.read_bytes()) for f in files}, queries=[], strategy_input_use=False,
        tls="verify-full", route="existing_loopback_http_proxy", database="WRDS crsp_a_stock")

    def save():
        (root / "manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf8")

    def extract(connection, name, query, params, limit):
        receipt = dict(name=name, query=query, parameters=params, started_at=datetime.now(UTC).isoformat())
        manifest["queries"].append(receipt)
        save()
        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)
                columns = [c.name for c in cursor.description]
                types = [c.type_code for c in cursor.description]
                rows = cursor.fetchall()
            payload = json.dumps(dict(columns=columns,postgres_type_oids=types,rows=rows),
                                 default=str,ensure_ascii=False,allow_nan=False).encode("utf8")
            blob = gzip.compress(payload,mtime=0)
            path = root / (name + ".json.gz")
            path.write_bytes(blob)
            receipt.update(path=path.name,sha256=sha(blob),response_sha256=sha(payload),row_count=len(rows),
                           captured_at=datetime.now(UTC).isoformat(),status="captured")
            save()
            if len(rows) > limit:
                raise ValueError("Bounded query returned more candidates than declared")
            print(json.dumps(dict(query=name,rows=len(rows),status="retained_locally")),flush=True)
            return [dict(zip(columns,r,strict=True)) for r in rows]
        except Exception as error:
            receipt.update(status="failed",error_type=type(error).__name__,sqlstate=getattr(error,"sqlstate",None))
            save()
            raise

    tunnel = None
    save()
    print(json.dumps(dict(archive=str(root),status="connecting_read_only")),flush=True)
    try:
        tunnel = WrdsProxyTunnel("http://127.0.0.1:7892")
        tunnel.start()
        with connect("wudf26",default_passfile(),ca,via_proxy=True) as connection:
            state = extract(connection,"connection","SELECT current_setting('transaction_read_only') AS read_only",None,1)
            if state != [dict(read_only="on")]:
                raise ValueError("Read-only connection required")
            start,end = p["window"]
            discoveries = extract(connection,"identity-discovery",
                "SELECT * FROM crsp_a_stock.stksecurityinfohist WHERE ticker = ANY(%s) "
                "AND secinfostartdt <= %s AND secinfoenddt >= %s ORDER BY permno,secinfostartdt LIMIT 201",
                [p["symbols"],end,start],200)
            permnos = sorted({r["permno"] for r in discoveries})
            if not permnos or len(permnos) > p["limits"]["max_candidate_permnos"]:
                raise ValueError("Missing or excessive permanent-identity candidates")
            extract(connection,"security-history",
                "SELECT * FROM crsp_a_stock.stksecurityinfohist WHERE permno = ANY(%s) "
                "AND secinfostartdt <= %s AND secinfoenddt >= %s ORDER BY permno,secinfostartdt LIMIT 201",
                [permnos,end,start],200)
            extract(connection,"legacy-name-history",
                "SELECT * FROM crsp_a_stock.dsenames WHERE permno = ANY(%s) "
                "AND namedt <= %s AND nameendt >= %s ORDER BY permno,namedt LIMIT 201",
                [permnos,end,start],200)
            extract(connection,"daily",
                "SELECT * FROM crsp_a_stock.dsf_v2 WHERE permno = ANY(%s) AND dlycaldt BETWEEN %s AND %s "
                "ORDER BY permno,dlycaldt LIMIT 5101",[permnos,start,end],5100)
        manifest.update(status="captured_pending_qualification",completed_at=datetime.now(UTC).isoformat())
        save()
        print(json.dumps(dict(archive=str(root),status=manifest["status"])),flush=True)
        return 0
    except Exception as error:
        manifest.update(status="incomplete",error_type=type(error).__name__,sqlstate=getattr(error,"sqlstate",None),
                        completed_at=datetime.now(UTC).isoformat())
        save()
        print(json.dumps(dict(archive=str(root),status="incomplete",error_type=type(error).__name__)),flush=True)
        return 1
    finally:
        if tunnel:
            tunnel.close()


if __name__ == "__main__":
    raise SystemExit(main())
