"""Versioned research price histories with a single, verified batch commit."""
from __future__ import annotations

from systematic_trading.market_data.analytics_store import AnalyticsStore, encode, digest
from systematic_trading.market_data.golden import _sql_string


DDL = """
CREATE DATABASE IF NOT EXISTS market_data;
CREATE TABLE IF NOT EXISTS market_data.governed_daily (
 workspace String, batch String, symbol LowCardinality(String), trade_date Date32,
 payload String, payload_hash String
) ENGINE = ReplacingMergeTree ORDER BY (workspace,batch,symbol,trade_date);
CREATE TABLE IF NOT EXISTS market_data.governance_comparisons (
 workspace String, batch String, symbol LowCardinality(String), source_id LowCardinality(String), trade_date Date32,
 payload String, payload_hash String
) ENGINE = ReplacingMergeTree ORDER BY (workspace,batch,symbol,source_id,trade_date);
"""


class GovernanceStore:
    def __init__(self,analytics: AnalyticsStore):
        self.analytics=analytics

    def initialize(self):
        self.analytics.initialize()
        for sql in DDL.split(';'):
            if sql.strip():
                self.analytics.client.execute(sql)

    def insert_verified(self,table,batch,symbol,records):
        if table not in ('governed_daily','governance_comparisons'):
            raise ValueError('Unknown governed table')
        comparison=table=='governance_comparisons'
        rows=[]
        expected={}
        for r in records:
            payload=encode(r)
            identity=(r['source_id'],r['trade_date']) if comparison else r['trade_date']
            if identity in expected:
                raise ValueError('Duplicate governed row identity')
            expected[identity]=digest(payload)
            rows.append(dict(workspace=self.analytics.workspace,batch=batch,symbol=symbol,trade_date=r['trade_date'],
                payload=payload,payload_hash=expected[identity],**(dict(source_id=r['source_id']) if comparison else {})))
        for i in range(0,len(rows),10000):
            self.analytics.client.execute(f'INSERT INTO market_data.{table} FORMAT JSONEachRow\n'+'\n'.join(encode(r) for r in rows[i:i+10000]))
        fields='source_id,' if comparison else ''
        result=self.analytics.query(f'SELECT {fields}trade_date,lower(hex(SHA256(payload))) AS hash FROM market_data.{table} FINAL WHERE '
            +'workspace='+_sql_string(self.analytics.workspace)+' AND batch='+_sql_string(batch)+' AND symbol='+_sql_string(symbol))
        actual={(r['source_id'],r['trade_date']) if comparison else r['trade_date']:r['hash'] for r in result}
        if actual!=expected:
            raise ValueError('Governed readback mismatch: '+table+'/'+symbol)
        return len(rows)


def latest_batch(analytics):
    p=analytics.latest('governance/catalog')
    return p['version'] if p else None
