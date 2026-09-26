"""Verified, versioned analytical projections; never an execution state store."""
from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Any

from systematic_trading.market_data.golden import ClickHouseMarketDataClient, _sql_string


DDL = """
CREATE DATABASE IF NOT EXISTS analytics;
CREATE TABLE IF NOT EXISTS analytics.observations (
 workspace String, source_id String, version String, point_key String,
 family LowCardinality(String), entity String,
 observed_at Nullable(DateTime64(6, 'UTC')),
 available_at Nullable(DateTime64(6, 'UTC')),
 ingested_at DateTime64(6, 'UTC'), payload String
) ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (workspace, source_id, version, point_key);
CREATE TABLE IF NOT EXISTS analytics.documents (
 workspace String, source_id String, version String, point_key String,
 media_type LowCardinality(String), ingested_at DateTime64(6, 'UTC'), payload String
) ENGINE = ReplacingMergeTree(ingested_at)
ORDER BY (workspace, source_id, version, point_key);
CREATE TABLE IF NOT EXISTS analytics.publications (
 workspace String, source_id String, version String,
 published_at DateTime64(6, 'UTC'), observation_count UInt64,
 document_count UInt64, provenance String
) ENGINE = ReplacingMergeTree(published_at)
ORDER BY (workspace, source_id, version);
CREATE VIEW IF NOT EXISTS analytics.current_observations AS
SELECT o.* FROM analytics.observations AS o FINAL
INNER JOIN (
 SELECT workspace, source_id, argMax(version, published_at) AS version
 FROM analytics.publications GROUP BY workspace, source_id
) AS p USING (workspace, source_id, version);
"""


def encode(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, ensure_ascii=True, allow_nan=False)


def digest(value: str | bytes) -> str:
    return sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def timestamp(value: Any) -> str | None:
    if not isinstance(value, (str, datetime)):
        return None
    try:
        dt = value if isinstance(value, datetime) else datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Date-only observations have a logical UTC midnight. Undated times
        # remain null; the full source payload preserves the original encoding.
        return dt.replace(tzinfo=UTC).isoformat() if dt.tzinfo is None else dt.astimezone(UTC).isoformat()
    except ValueError:
        return None


class AnalyticsStore:
    def __init__(self, client: ClickHouseMarketDataClient, workspace: str):
        self.client, self.workspace = client, workspace

    @classmethod
    def from_settings(cls, settings):
        return cls(ClickHouseMarketDataClient(settings.clickhouse_http_url,
                   database=settings.clickhouse_database, user=settings.clickhouse_user,
                   password=settings.clickhouse_password),
                   digest(str(settings.data_dir.resolve()).lower()))

    def initialize(self):
        for statement in DDL.split(";"):
            if statement.strip():
                self.client.execute(statement)

    def query(self, sql):
        return [json.loads(line) for line in self.client.execute(sql + " FORMAT JSONEachRow").splitlines() if line]

    def latest(self, source_id):
        rows = self.query("SELECT * FROM analytics.publications WHERE workspace=" + _sql_string(self.workspace)
                          + " AND source_id=" + _sql_string(source_id) + " ORDER BY published_at DESC LIMIT 1")
        return rows[0] if rows else None

    def publication_index(self, prefix):
        rows = self.query("SELECT source_id, argMax(version, published_at) AS version, "
                          "argMax(provenance, published_at) AS provenance FROM analytics.publications WHERE workspace="
                          + _sql_string(self.workspace) + " AND startsWith(source_id," + _sql_string(prefix)
                          + ") GROUP BY source_id")
        return {row["source_id"]: row for row in rows}

    def current_observations(self, prefix, *, family=None, limit=1000000):
        sql = "SELECT * FROM analytics.current_observations WHERE workspace=" + _sql_string(self.workspace)
        sql += " AND startsWith(source_id," + _sql_string(prefix) + ")"
        if family:
            sql += " AND family=" + _sql_string(family)
        tie_break = ("parseDateTime64BestEffortOrNull(JSONExtractString(payload, 'created_at'), 6, 'UTC') DESC, "
                     if family == "pnl_snapshot" else "")
        return self.query(sql + f" ORDER BY observed_at DESC, {tie_break}point_key LIMIT {int(limit)}")

    def _where(self, source_id, version):
        return ("workspace=" + _sql_string(self.workspace) + " AND source_id=" + _sql_string(source_id)
                + " AND version=" + _sql_string(version))

    def publish(self, source_id, version, observations, documents=(), *, provenance=None):
        current = self.latest(source_id)
        if current and current["version"] == version:
            return False
        now = datetime.now(UTC).isoformat()
        common = dict(workspace=self.workspace, source_id=source_id, version=version, ingested_at=now)
        rows = [{**common, **row} for row in observations]
        docs = [{**common, **row} for row in documents]
        for table, records in (("observations", rows), ("documents", docs)):
            if len({row["point_key"] for row in records}) != len(records):
                raise ValueError(f"Duplicate analytical point identity in {source_id}/{table}")
            for offset in range(0, len(records), 1000):
                self.client.execute(f"INSERT INTO analytics.{table} FORMAT JSONEachRow\n"
                                    + "\n".join(encode(row) for row in records[offset:offset + 1000]))
            actual = self.query(f"SELECT point_key, lower(hex(SHA256(payload))) AS hash FROM analytics.{table} FINAL WHERE "
                                + self._where(source_id, version))
            expected = {row["point_key"]: digest(row["payload"]) for row in records}
            if {row["point_key"]: row["hash"] for row in actual} != expected:
                raise ValueError(f"Analytical readback mismatch: {source_id}/{table}")
        publication = dict(workspace=self.workspace, source_id=source_id, version=version,
                           published_at=now, observation_count=len(rows), document_count=len(docs),
                           provenance=encode(provenance or {}))
        self.client.execute("INSERT INTO analytics.publications FORMAT JSONEachRow\n" + encode(publication))
        return True

    def publish_batch(self, sources):
        """Verify independent small captures together, then commit their manifests.

        Used for append-only capture files to avoid thousands of tiny INSERTs.
        Callers select changed versions using publication_index first.
        """
        for offset in range(0, len(sources), 100):
            batch = sources[offset:offset + 100]
            now = datetime.now(UTC).isoformat()
            rows, publications, expected = [], [], {}
            for source_id, version, observations, provenance in batch:
                for row in observations:
                    identity = (source_id, version, row["point_key"])
                    if identity in expected:
                        raise ValueError("Duplicate analytical batch identity")
                    expected[identity] = digest(row["payload"])
                    rows.append(dict(workspace=self.workspace, source_id=source_id, version=version,
                                     ingested_at=now, **row))
                publications.append(dict(workspace=self.workspace, source_id=source_id, version=version,
                    published_at=now, observation_count=len(observations), document_count=0, provenance=encode(provenance)))
            for row_offset in range(0, len(rows), 1000):
                self.client.execute("INSERT INTO analytics.observations FORMAT JSONEachRow\n"
                                    + "\n".join(encode(row) for row in rows[row_offset:row_offset + 1000]))
            identities = ",".join("(" + _sql_string(source) + "," + _sql_string(version) + ")"
                                  for source, version, _, _ in batch)
            actual = self.query("SELECT source_id, version, point_key, lower(hex(SHA256(payload))) AS hash "
                "FROM analytics.observations FINAL WHERE workspace=" + _sql_string(self.workspace)
                + " AND (source_id,version) IN (" + identities + ")")
            if {(r["source_id"], r["version"], r["point_key"]): r["hash"] for r in actual} != expected:
                raise ValueError("Analytical batch readback mismatch")
            self.client.execute("INSERT INTO analytics.publications FORMAT JSONEachRow\n"
                                + "\n".join(encode(row) for row in publications))
        return bool(sources)

    def document(self, source_id, key):
        publication = self.latest(source_id)
        if publication is None:
            return None
        rows = self.query("SELECT payload, media_type FROM analytics.documents FINAL WHERE "
                          + self._where(source_id, publication["version"]) + " AND point_key=" + _sql_string(key))
        return (rows[0], publication) if rows else None

    def observations(self, source_id, *, family=None, limit=1000):
        publication = self.latest(source_id)
        if publication is None:
            return []
        sql = "SELECT * FROM analytics.observations FINAL WHERE " + self._where(source_id, publication["version"])
        if family is not None:
            sql += " AND family=" + _sql_string(family)
        tie_break = ("parseDateTime64BestEffortOrNull(JSONExtractString(payload, 'created_at'), 6, 'UTC') DESC, "
                     if family == "pnl_snapshot" else "")
        return self.query(sql + f" ORDER BY observed_at DESC, {tie_break}point_key LIMIT {int(limit)}")

    def market_revision(self):
        parts = []
        for table in ("market_data.daily_bars", "market_data.fx_rates"):
            parts.append(self.query(f"SELECT count() AS n, toString(max(ingested_at)) AS changed, "
                                    f"sum(cityHash64(payload_hash)) AS hash FROM {table} FINAL"))
        return digest(encode(parts))
