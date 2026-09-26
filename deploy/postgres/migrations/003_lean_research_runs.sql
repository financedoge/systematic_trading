-- Research evidence only. No relationship to executable proposals or broker orders.
CREATE TABLE ops.lean_research_runs (
    run_id text PRIMARY KEY,
    recorded_at timestamptz NOT NULL DEFAULT now(),
    manifest_sha256 text NOT NULL,
    receipt_sha256 text NOT NULL,
    artifact_path text NOT NULL,
    promotion_eligible boolean NOT NULL DEFAULT false CHECK (NOT promotion_eligible),
    payload jsonb NOT NULL
);
