-- PostgreSQL commits immutable Parquet manifests; bulk rows remain on disk.
CREATE SCHEMA IF NOT EXISTS native_analytics;
CREATE TABLE native_analytics.datasets (
    workspace TEXT NOT NULL,
    dataset_key TEXT NOT NULL,
    revision TEXT NOT NULL,
    manifest_sha256 TEXT NOT NULL,
    manifest JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace, dataset_key, revision)
);
CREATE TABLE native_analytics.heads (
    workspace TEXT NOT NULL,
    dataset_key TEXT NOT NULL,
    revision TEXT NOT NULL,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (workspace, dataset_key),
    FOREIGN KEY (workspace, dataset_key, revision)
        REFERENCES native_analytics.datasets(workspace, dataset_key, revision)
);
CREATE TABLE native_analytics.publications (
    workspace TEXT NOT NULL,
    source_id TEXT NOT NULL,
    version TEXT NOT NULL,
    published_at TIMESTAMPTZ NOT NULL,
    observation_count BIGINT NOT NULL,
    document_count BIGINT NOT NULL,
    provenance TEXT NOT NULL,
    datasets JSONB NOT NULL,
    storage_format TEXT NOT NULL DEFAULT 'parquet-v1',
    PRIMARY KEY (workspace, source_id, version)
);
CREATE TABLE native_analytics.retirements (
    receipt_id TEXT PRIMARY KEY,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    payload JSONB NOT NULL
);
CREATE TRIGGER native_datasets_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON native_analytics.datasets
FOR EACH STATEMENT EXECUTE FUNCTION ops.reject_lean_evidence_mutation();
CREATE TRIGGER native_publications_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON native_analytics.publications
FOR EACH STATEMENT EXECUTE FUNCTION ops.reject_lean_evidence_mutation();
CREATE TRIGGER native_retirements_immutable BEFORE UPDATE OR DELETE OR TRUNCATE ON native_analytics.retirements
FOR EACH STATEMENT EXECUTE FUNCTION ops.reject_lean_evidence_mutation();
GRANT USAGE ON SCHEMA native_analytics TO st_app;
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA native_analytics TO st_app;
GRANT UPDATE ON native_analytics.heads TO st_app;
