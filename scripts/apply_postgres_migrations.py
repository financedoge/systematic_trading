from __future__ import annotations

import argparse
import sys
from pathlib import Path

import psycopg
from psycopg import sql
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from systematic_trading.config import AppSettings  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply versioned Postgres migrations for transactional state.")
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=ROOT / "deploy" / "postgres" / "migrations",
        help="Directory containing *.sql migration files.",
    )
    parser.add_argument(
        "--no-set-owner-role",
        action="store_true",
        help="Do not SET ROLE to ST_POSTGRES_OWNER_ROLE before applying DDL.",
    )
    args = parser.parse_args()

    settings = AppSettings()
    applied = apply_migrations(
        settings=settings,
        migrations_dir=args.migrations_dir,
        set_owner_role=not args.no_set_owner_role,
    )
    if applied:
        for migration_id in applied:
            print(f"applied={migration_id}")
    else:
        print("applied=0")
    return 0


def apply_migrations(
    *,
    settings: AppSettings,
    migrations_dir: Path,
    set_owner_role: bool = True,
) -> list[str]:
    migrations = sorted(migrations_dir.glob("*.sql"))
    if not migrations:
        raise FileNotFoundError(f"no Postgres migrations found in {migrations_dir}")

    password = settings.postgres_migrator_password or settings.migrator_postgre_db_password
    kwargs = {
        "host": settings.postgres_host,
        "port": settings.postgres_port,
        "dbname": settings.postgres_database,
        "user": settings.postgres_migrator_user,
        "sslmode": settings.postgres_sslmode,
        "application_name": f"{settings.app_name}-migrator",
        "options": "-c timezone=UTC",
        "row_factory": dict_row,
    }
    if password:
        kwargs["password"] = password

    applied: list[str] = []
    with psycopg.connect(**kwargs) as connection:
        if set_owner_role and settings.postgres_owner_role:
            connection.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(settings.postgres_owner_role)))
        _ensure_migration_table(connection)
        already_applied = _applied_migration_ids(connection)
        for migration_path in migrations:
            migration_id = migration_path.stem
            if migration_id in already_applied:
                continue
            migration_sql = migration_path.read_text(encoding="utf-8")
            with connection.transaction():
                connection.execute(migration_sql)
                connection.execute(
                    """
                    INSERT INTO ops.schema_migrations(migration_id, applied_at)
                    VALUES (%s, now())
                    ON CONFLICT(migration_id) DO NOTHING
                    """,
                    (migration_id,),
                )
            applied.append(migration_id)
    return applied


def _ensure_migration_table(connection: psycopg.Connection) -> None:
    connection.execute("CREATE SCHEMA IF NOT EXISTS ops")
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS ops.schema_migrations (
            migration_id text PRIMARY KEY,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def _applied_migration_ids(connection: psycopg.Connection) -> set[str]:
    rows = connection.execute("SELECT migration_id FROM ops.schema_migrations").fetchall()
    return {row["migration_id"] for row in rows}


if __name__ == "__main__":
    raise SystemExit(main())
