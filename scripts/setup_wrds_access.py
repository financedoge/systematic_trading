"""Set up a local WRDS password file without putting secrets in chat or logs.

Run interactively in a local terminal. --check-only never prompts or writes a
password. Uses the standard libpq passfile understood by the WRDS package too.
No market data is downloaded or published by this connection check.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import getpass
import json
import os
from pathlib import Path
import re
import select
import socket
import ssl
import subprocess
import sys
import threading
from urllib.parse import urlparse

import psycopg


WRDS_HOST = "wrds-pgdata.wharton.upenn.edu"
WRDS_PORT = 9737
WRDS_DATABASE = "wrds"


class WrdsProxyTunnel:
    """Temporary loopback relay through an existing local HTTP proxy.

    TLS remains end-to-end: libpq verifies the WRDS hostname/certificate. The
    relay cannot decrypt credentials. Fixed destination/port preserve pgpass
    matching. No global proxy or network configuration is changed.
    """

    def __init__(self, proxy: str):
        parsed = urlparse(proxy)
        if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}
                or parsed.username or parsed.password or not parsed.port):
            raise ValueError("Only an existing unauthenticated loopback HTTP proxy is supported")
        self.proxy = (parsed.hostname, parsed.port)
        self.stop = threading.Event()
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        self.listener.bind(("127.0.0.1", WRDS_PORT))
        self.listener.listen(2)
        self.listener.settimeout(0.5)
        self.worker = threading.Thread(target=self._serve, daemon=True)

    def start(self):
        self.worker.start()

    def close(self):
        self.stop.set()
        self.listener.close()
        self.worker.join(timeout=2)

    def _serve(self):
        while not self.stop.is_set():
            try:
                client, _ = self.listener.accept()
            except socket.timeout:
                continue
            except OSError:
                return
            with client:
                try:
                    with socket.create_connection(self.proxy, timeout=15) as remote:
                        remote.sendall(
                            f"CONNECT {WRDS_HOST}:{WRDS_PORT} HTTP/1.1\r\n"
                            f"Host: {WRDS_HOST}:{WRDS_PORT}\r\n\r\n".encode("ascii")
                        )
                        header = b""
                        while not header.endswith(b"\r\n\r\n"):
                            chunk = remote.recv(1)
                            if not chunk or len(header) >= 8192:
                                raise ConnectionError("Incomplete proxy response")
                            header += chunk
                        if b" 200 " not in header.split(b"\r\n", 1)[0]:
                            raise ConnectionError("Proxy refused WRDS tunnel")
                        remote.settimeout(None)
                        while not self.stop.is_set():
                            ready, _, _ = select.select([client, remote], [], [], 0.5)
                            for source in ready:
                                data = source.recv(65536)
                                if not data:
                                    break
                                (remote if source is client else client).sendall(data)
                            else:
                                continue
                            break
                except OSError:
                    # Closing the client makes libpq surface its bounded failure.
                    # Never log the opaque forwarded bytes.
                    continue


def default_passfile() -> Path:
    if os.name == "nt":
        return Path(os.environ["APPDATA"]) / "postgresql" / "pgpass.conf"
    return Path.home() / ".pgpass"


def escape_field(value: str) -> str:
    if not value or any(char in value for char in "\r\n\0"):
        raise ValueError("Empty or multiline password-file fields are unsupported")
    return value.replace("\\", "\\\\").replace(":", "\\:")


def password_record(username: str, password: str) -> str:
    return ":".join(
        escape_field(str(value))
        for value in (WRDS_HOST, WRDS_PORT, WRDS_DATABASE, username, password)
    ) + "\n"


def protect_new_file(path: Path) -> None:
    """Restrict a newly created, still empty file before writing the secret."""
    if os.name != "nt":
        path.chmod(0o600)
        return
    creationflags = subprocess.CREATE_NO_WINDOW
    result = subprocess.run(
        ["whoami", "/user", "/fo", "csv", "/nh"],
        check=True, capture_output=True, text=True, creationflags=creationflags,
    )
    match = re.search(r"S-1-5-[\d-]+", result.stdout)
    if not match:
        raise RuntimeError("Unable to determine local Windows security identifier")
    subprocess.run(
        ["icacls", str(path), "/inheritance:r", "/grant:r",
         f"*{match.group()}:(F)", "*S-1-5-18:(F)"],
        check=True, capture_output=True, text=True, creationflags=creationflags,
    )


def save_new_passfile(path: Path, username: str, password: str) -> None:
    """Never overwrite an existing password file or unrelated DB credentials."""
    record = password_record(username, password)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="\n") as handle:
        protect_new_file(path)
        handle.write(record)


def write_ca_bundle(path: Path) -> None:
    certificates = ssl.create_default_context().get_ca_certs(binary_form=True)
    if not certificates:
        raise RuntimeError("No trusted certificates available for verified TLS")
    path.write_text(
        "".join(ssl.DER_cert_to_PEM_cert(cert) for cert in certificates),
        encoding="ascii", newline="\n",
    )


def connect(username: str, passfile: Path, ca_file: Path, password: str | None = None,
            *, via_proxy: bool = False):
    kwargs = dict(
        host=WRDS_HOST, port=WRDS_PORT, dbname=WRDS_DATABASE, user=username,
        passfile=str(passfile), sslmode="verify-full", sslrootcert=str(ca_file),
        connect_timeout=120, application_name="systematic-trading-wrds-access-check",
        options=("-c default_transaction_read_only=on "
                 "-c statement_timeout=30000 -c lock_timeout=5000"),
    )
    if password is not None:
        kwargs["password"] = password
    if via_proxy:
        kwargs["hostaddr"] = "127.0.0.1"
    # An inherited PGPASSWORD would bypass the passfile test. Refuse it.
    if os.environ.get("PGPASSWORD"):
        raise RuntimeError("Unset PGPASSWORD before checking the password file")
    return psycopg.connect(**kwargs)


def inspect_access(connection) -> dict:
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('transaction_read_only')")
        read_only = cursor.fetchone()[0] == "on"
        if not read_only:
            raise RuntimeError("WRDS access probe must be read-only")
        schema_query = (
            "SELECT nspname, has_schema_privilege(oid, 'USAGE') "
            "FROM pg_namespace WHERE nspname LIKE 'crsp%' "
            "OR nspname LIKE 'taq%' ORDER BY nspname"
        )
        cursor.execute(schema_query)
        schemas = [{"schema": name, "usage": usage} for name, usage in cursor]
    return {"read_only": read_only, "schemas": schemas,
            "metadata_query": schema_query, "driver_version": psycopg.__version__,
            "table_access_verified": False, "market_data_rows_downloaded": 0}


def save_status(path: Path, **fields) -> None:
    fields["recorded_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(fields, indent=2) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", required=True)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--proxy", help="Existing loopback HTTP proxy, e.g. http://127.0.0.1:7892")
    parser.add_argument("--output", type=Path, default=Path("var/private/wrds/setup-status.json"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    passfile = default_passfile()
    ca_file = output.parent / "trusted-ca.pem"
    saved = False
    tunnel = None
    try:
        write_ca_bundle(ca_file)
        if args.proxy:
            tunnel = WrdsProxyTunnel(args.proxy)
            tunnel.start()
        if not args.check_only:
            if passfile.exists():
                raise FileExistsError("An existing password file will not be overwritten")
            if not sys.stdin.isatty():
                raise RuntimeError("Run this setup in your own interactive terminal")
            save_status(output, status="awaiting_local_password", password_saved=False)
            print("WRDS connection setup. Enter your password here, never in chat.")
            print(f"Account: {args.username}; destination: {WRDS_HOST}:{WRDS_PORT}")
            print(f"After successful login, save to: {passfile}")
            print("Approve the WRDS Duo Mobile push if one appears during connection.")
            password = getpass.getpass("WRDS password (hidden): ")
            password_record(args.username, password)  # Validate before authentication.
            save_status(output, status="authenticating", password_saved=False)
            with connect(args.username, passfile, ca_file, password,
                         via_proxy=bool(tunnel)) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    assert cursor.fetchone() == (1,)
            save_new_passfile(passfile, args.username, password)
            password = None
            saved = True
        if not passfile.is_file():
            raise FileNotFoundError("The standard password file does not exist")
        save_status(output, status="checking_saved_connection", password_saved=saved)
        with connect(args.username, passfile, ca_file, via_proxy=bool(tunnel)) as connection:
            access = inspect_access(connection)
        save_status(output, status="connected", password_saved=saved,
                    passfile_verified=True, passfile_path=str(passfile),
                    tls="verify-full", route="local_http_proxy" if tunnel else "direct", **access)
        print(f"Connected successfully using {passfile}")
        print("Read-only connection and saved password verified. No market data downloaded.")
        return 0
    except (Exception, KeyboardInterrupt) as error:
        # Connection exceptions can contain connection parameters. Keep details
        # out of logs and receipts; a SQLSTATE plus error type is enough to triage.
        save_status(output, status="failed", password_saved=saved,
                    error_type=type(error).__name__, sqlstate=getattr(error, "sqlstate", None))
        print(f"Setup did not complete ({type(error).__name__}). No password is logged.")
        return 1
    finally:
        if tunnel:
            tunnel.close()


if __name__ == "__main__":
    raise SystemExit(main())
