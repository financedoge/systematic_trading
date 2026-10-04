"""Transactional compare-and-swap state with an immutable operator audit log."""
import json


SQLITE_CONTROL_SCHEMA = """
CREATE TABLE IF NOT EXISTS strategy_control_state (
    scope TEXT PRIMARY KEY, revision INTEGER NOT NULL, payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS strategy_control_events (
    scope TEXT NOT NULL, revision INTEGER NOT NULL, event_id TEXT NOT NULL,
    payload TEXT NOT NULL, PRIMARY KEY(scope, revision), UNIQUE(scope, event_id)
);
CREATE TRIGGER IF NOT EXISTS strategy_control_no_update BEFORE UPDATE ON strategy_control_events
BEGIN SELECT RAISE(ABORT, 'Strategy control events are immutable'); END;
CREATE TRIGGER IF NOT EXISTS strategy_control_no_delete BEFORE DELETE ON strategy_control_events
BEGIN SELECT RAISE(ABORT, 'Strategy control events are immutable'); END;
"""


class StrategyControlStore:
    """Mixed into the two transactional stores; no filesystem control state."""

    def strategy_approval_times(self):
        table = 'approval_decisions' if hasattr(self, 'database_path') else 'portfolio.approval_decisions'
        with self._connect() as connection:
            rows = connection.execute(f"SELECT proposal_id, decided_at FROM {table} WHERE status = 'approved' ORDER BY decided_at").fetchall()
        return {r['proposal_id']: r['decided_at'].isoformat() if hasattr(r['decided_at'], 'isoformat') else r['decided_at'] for r in rows}

    def _control_sql(self, sql):
        if hasattr(self, 'database_path'):
            return sql
        return sql.replace('strategy_control_', 'portfolio.strategy_control_').replace('?', '%s')

    def strategy_control_state(self, scope):
        with self._connect() as connection:
            row = connection.execute(self._control_sql(
                'SELECT payload FROM strategy_control_state WHERE scope = ?'), (scope,)).fetchone()
        return json.loads(row['payload']) if row else None

    def strategy_control_events(self, scope):
        with self._connect() as connection:
            rows = connection.execute(self._control_sql(
                'SELECT payload FROM strategy_control_events WHERE scope = ? ORDER BY revision'), (scope,)).fetchall()
        return [json.loads(row['payload']) for row in rows]

    def commit_strategy_control(self, scope, expected_revision, state, event):
        """Idempotent retry returns the original state, never silently overwrites it."""
        with self._connect() as connection:
            if hasattr(self, 'database_path'):
                connection.execute('BEGIN IMMEDIATE')
            else:
                connection.execute('SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))', (scope,))
            previous = connection.execute(self._control_sql(
                'SELECT payload FROM strategy_control_events WHERE scope = ? AND event_id = ?'),
                (scope, event['event_id'])).fetchone()
            if previous:
                recorded = json.loads(previous['payload'])
                if recorded['request_hash'] != event['request_hash']:
                    raise ValueError('Idempotency key was already used for a different change.')
                return recorded['state']
            row = connection.execute(self._control_sql(
                'SELECT revision FROM strategy_control_state WHERE scope = ?'), (scope,)).fetchone()
            revision = row['revision'] if row else 0
            if revision != expected_revision:
                raise ValueError('Strategy configuration changed. Refresh and preview again.')
            state = dict(state, revision=revision + 1)
            event = dict(event, revision=revision + 1, state=state)
            connection.execute(self._control_sql(
                'INSERT INTO strategy_control_events(scope, revision, event_id, payload) VALUES (?, ?, ?, ?)'),
                (scope, revision + 1, event['event_id'], json.dumps(event)))
            connection.execute(self._control_sql(
                'INSERT INTO strategy_control_state(scope, revision, payload) VALUES (?, ?, ?) '
                'ON CONFLICT(scope) DO UPDATE SET revision = excluded.revision, payload = excluded.payload'),
                (scope, revision + 1, json.dumps(state)))
            return state
