import importlib.util
import json
from pathlib import Path
import pytest


spec = importlib.util.spec_from_file_location('sector_import', Path(__file__).resolve().parents[1]/'scripts/import_sector_research_clickhouse.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_raw_prices_missing_volume_and_unknown_availability_are_preserved():
    raw = dict(chart=dict(result=[dict(meta=dict(instrumentType='EQUITY', currency='USD'),
        timestamp=[1672756200], indicators=dict(quote=[dict(open=[10], high=[11], low=[9], close=[10], volume=[None])],
                                              adjclose=[dict(adjclose=[8])]))]))
    row = module.yahoo_rows(json.dumps(raw), 'ABC', 'raw-hash')[0]
    payload = json.loads(row['payload'])
    assert payload['close'] == 10 and payload['adjusted_close'] == 8
    assert payload['volume'] is None
    assert 'missing_or_invalid_volume' in payload['quality_flags']
    assert row['available_at'] is None
    assert payload['source_raw_sha256'] == 'raw-hash'


def test_holdings_publication_assumption_is_not_fabricated_known_availability():
    rows = module.holding_rows(dict(as_of='2018-12-31', assumed_available='2019-02-14',
        retrieved_at='2026-09-26T00:00:00+00:00', raw_sha256='h',
        rows=[dict(ticker='FB', yahoo='META', market_value=100, sector='Communication')]))
    assert rows[0]['available_at'] is None
    payload = json.loads(rows[0]['payload'])
    assert payload['assumed_available'] == '2019-02-14'
    assert payload['ticker'] == 'FB' and rows[0]['entity'] == 'META'


def test_verified_alias_keeps_original_holding_identity():
    rows = module.holding_rows(dict(as_of='2022-12-30', assumed_available='2023-02-13',
        retrieved_at='2026-09-26T00:00:00+00:00', raw_sha256='h',
        rows=[dict(ticker='BK', yahoo='BK', market_value=100, sector='Financials')]), {'BK': 'BNY'})
    payload = json.loads(rows[0]['payload'])
    assert rows[0]['entity'] == 'BNY'
    assert payload['ticker'] == payload['yahoo'] == 'BK'
    assert payload['resolved_yahoo'] == 'BNY'


def test_bulk_import_does_not_publish_when_readback_is_wrong():
    class Client:
        def __init__(self):
            self.calls = []

        def execute(self, sql):
            self.calls.append(sql)
            return ''

    client = Client()
    store = module.ResearchBatchAnalytics(client, 'test')
    row = module.observation('key', 'research', 'ABC', {'value': 1})
    with pytest.raises(ValueError, match='readback mismatch'):
        store.publish_batch([('source', 'version', [row], {})])
    assert not any(c.startswith('INSERT INTO analytics.publications') for c in client.calls)
