CREATE TABLE portfolio.strategy_control_state (
    scope TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE portfolio.strategy_control_events (
    scope TEXT NOT NULL, revision INTEGER NOT NULL, event_id TEXT NOT NULL,
    payload TEXT NOT NULL, PRIMARY KEY(scope, revision), UNIQUE(scope, event_id)
);
CREATE TRIGGER strategy_control_events_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE ON portfolio.strategy_control_events
FOR EACH STATEMENT EXECUTE FUNCTION ops.reject_lean_evidence_mutation();
