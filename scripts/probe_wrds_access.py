"""Archive bounded WRDS permission/schema probes; never publish research inputs."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path

from psycopg import sql

from setup_wrds_access import WrdsProxyTunnel, connect, default_passfile, write_ca_bundle


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--proxy")
    parser.add_argument("--archive-root", type=Path, required=True)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    root = args.archive_root.resolve() / f"access-{stamp}"
    root.mkdir(parents=True, exist_ok=False)
    for script in [Path(__file__), Path(__file__).with_name("setup_wrds_access.py")]:
        (root / script.name).write_bytes(script.read_bytes())
    ca_file = root / "trusted-ca.pem"
    write_ca_bundle(ca_file)
    manifest = {
        "kind": "WRDS connection, entitlement and schema inspection",
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "source_database": "WRDS PostgreSQL", "source_release": None,
        "source_release_note": "Database access does not certify a vendor release or vintage",
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "queries": [], "market_observation_rows_downloaded": 0,
        "input_publication": False,
    }

    def save():
        (root / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    def extract(connection, name, query, parameters=None):
        rendered = query.as_string(connection) if isinstance(query, sql.Composable) else query
        with connection.cursor() as cursor:
            cursor.execute(query, parameters)
            columns = [column.name for column in cursor.description]
            types = [column.type_code for column in cursor.description]
            rows = cursor.fetchall()
        captured = datetime.now(timezone.utc).isoformat()
        payload = json.dumps({"columns": columns, "postgres_type_oids": types, "rows": rows},
                             default=str, ensure_ascii=False).encode("utf-8")
        compressed = gzip.compress(payload, mtime=0)
        path = root / f"{name}.json.gz"
        path.write_bytes(compressed)
        manifest["queries"].append({
            "name": name, "query": rendered, "parameters": parameters,
            "captured_at": captured, "row_count": len(rows),
            "path": path.name, "sha256": hashlib.sha256(compressed).hexdigest(),
        })
        save()
        return [dict(zip(columns, row, strict=True)) for row in rows]

    tunnel = None
    save()
    try:
        if args.proxy:
            tunnel = WrdsProxyTunnel(args.proxy)
            tunnel.start()
        with connect(args.username, default_passfile(), ca_file, via_proxy=bool(tunnel)) as connection:
            state = extract(connection, "connection", "SELECT current_setting('transaction_read_only') AS read_only")
            if state != [{"read_only": "on"}]:
                raise RuntimeError("Read-only connection required")
            schemas = extract(connection, "schemas",
                "SELECT nspname AS schema, has_schema_privilege(oid, 'USAGE') AS usage "
                "FROM pg_namespace WHERE nspname LIKE 'crsp%' OR nspname LIKE 'taq%' ORDER BY nspname")
            tables = extract(connection, "tables",
                "SELECT n.nspname AS schema, c.relname AS relation, c.relkind AS kind, "
                "has_schema_privilege(n.oid, 'USAGE') AS schema_usage, "
                "has_table_privilege(c.oid, 'SELECT') AS table_select "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname = ANY(%s) AND c.relkind IN ('r','v','m','p','f') "
                "AND (n.nspname LIKE 'crsp%%' OR c.relname LIKE '%%20250224%%') "
                "ORDER BY n.nspname,c.relname",
                [["crsp_a_stock", "crsp_a_stock_new", "taqm_2024", "taqm_2025", "taqmsec", "taq"]])
            usable = [row for row in tables if row["schema_usage"] and row["table_select"]]
            daily = [row for row in usable if row["relation"] in {"dsf_v2", "dsf"}]
            daily.sort(key=lambda row: (row["relation"] != "dsf_v2", row["schema"] != "crsp_a_stock"))
            selected = daily[:1]
            identity = [row for row in usable if row["relation"] in {"stksecurityinfohist", "stocknames", "dsenames"}]
            if selected:
                identity = [row for row in identity if row["schema"] == selected[0]["schema"]]
            selected += identity[:2]
            selected += [row for row in usable if row["schema"] == "taqmsec"
                         and row["relation"] in {"ctm_20250224", "mastm_20250224"}]
            verified = []
            for number, row in enumerate(selected):
                table = sql.Identifier(row["schema"], row["relation"])
                query = sql.SQL("SELECT 1 AS row_present FROM {} LIMIT 1").format(table)
                try:
                    with connection.transaction():
                        check = extract(connection, f"read-check-{number}", query)
                except Exception as error:
                    # A visible view can still refuse access to its backing data.
                    # Preserve that verdict; never try to bypass it.
                    verified.append({"schema": row["schema"], "relation": row["relation"],
                                     "read_succeeded": False, "error_type": type(error).__name__,
                                     "sqlstate": getattr(error, "sqlstate", None)})
                    manifest["queries"].append({
                        "name": f"read-check-{number}", "query": query.as_string(connection),
                        "parameters": None, "captured_at": datetime.now(timezone.utc).isoformat(),
                        "status": "failed", "error_type": type(error).__name__,
                        "sqlstate": getattr(error, "sqlstate", None),
                    })
                    save()
                    continue
                columns = extract(connection, f"columns-{number}",
                    "SELECT a.attname AS name, format_type(a.atttypid,a.atttypmod) AS type, "
                    "col_description(c.oid,a.attnum) AS description "
                    "FROM pg_attribute a JOIN pg_class c ON c.oid=a.attrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname=%s AND c.relname=%s AND a.attnum>0 AND NOT a.attisdropped "
                    "ORDER BY a.attnum", [row["schema"], row["relation"]])
                verified.append({"schema": row["schema"], "relation": row["relation"],
                                 "read_succeeded": bool(check), "column_count": len(columns)})
            manifest["status"] = "complete"
            manifest["passfile_reconnect_verified"] = True
            manifest["tls"] = "verify-full"
            manifest["route"] = "local_http_proxy" if tunnel else "direct"
            manifest["verified_tables"] = verified
            manifest["taq_2024_2025_schema_usage"] = [
                row for row in schemas if row["schema"] in {"taqm_2024", "taqm_2025"}
            ]
            save()
            print(json.dumps({"archive": str(root), "verified_tables": verified,
                              "taq_2024_2025_schema_usage": manifest["taq_2024_2025_schema_usage"]}, indent=2))
    except Exception as error:
        manifest["status"] = "failed"
        manifest["error_type"] = type(error).__name__
        manifest["sqlstate"] = getattr(error, "sqlstate", None)
        save()
        print(json.dumps({"archive": str(root), "status": "failed", "error_type": type(error).__name__}))
        return 1
    finally:
        if tunnel:
            tunnel.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
