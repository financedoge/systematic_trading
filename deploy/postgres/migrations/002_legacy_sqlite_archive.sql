-- Immutable source evidence, never replayed into the active approval/order tables.
CREATE SCHEMA IF NOT EXISTS legacy;
CREATE TABLE legacy.sqlite_snapshots (
    snapshot_id text PRIMARY KEY,
    source_name text NOT NULL,
    manifest jsonb NOT NULL,
    archived_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE legacy.sqlite_rows (
    snapshot_id text NOT NULL REFERENCES legacy.sqlite_snapshots(snapshot_id),
    table_name text NOT NULL,
    ordinal bigint NOT NULL,
    row_json text NOT NULL,
    PRIMARY KEY (snapshot_id, table_name, ordinal)
);
