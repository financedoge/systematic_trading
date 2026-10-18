CREATE TABLE IF NOT EXISTS native_analytics.publication_heads (
 workspace text NOT NULL, source_id text NOT NULL, version text NOT NULL,
 activated_at timestamptz NOT NULL,
 PRIMARY KEY(workspace,source_id),
 FOREIGN KEY(workspace,source_id,version) REFERENCES native_analytics.publications(workspace,source_id,version)
);
INSERT INTO native_analytics.publication_heads
SELECT DISTINCT ON(workspace,source_id) workspace,source_id,version,published_at
FROM native_analytics.publications ORDER BY workspace,source_id,published_at DESC,version DESC
ON CONFLICT DO NOTHING;
GRANT SELECT,INSERT,UPDATE ON native_analytics.publication_heads TO st_app;
