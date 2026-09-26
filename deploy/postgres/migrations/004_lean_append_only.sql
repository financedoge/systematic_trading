-- Evidence can be appended or restored from backup, never rewritten in place.
CREATE FUNCTION ops.reject_lean_evidence_mutation() RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'LEAN research evidence is append-only';
END;
$$;

CREATE TRIGGER lean_research_runs_immutable
BEFORE UPDATE OR DELETE OR TRUNCATE ON ops.lean_research_runs
FOR EACH STATEMENT EXECUTE FUNCTION ops.reject_lean_evidence_mutation();
