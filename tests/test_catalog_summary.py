import json
from datetime import date
from pathlib import Path

from systematic_trading.recorders import MarketDataRecorder, RawDataCatalog, RawMarketDataWriter, query_raw_catalog
from systematic_trading.recorders.catalog_summary import manifest_summary
from test_market_data_recorder import _bar


def test_summary_reuses_unchanged_manifest_and_invalidates_append(tmp_path, monkeypatch):
    recorder = MarketDataRecorder(writer=RawMarketDataWriter(tmp_path, fsync=False),
        catalog=RawDataCatalog(tmp_path, fsync=False), event_store=None)
    recorder.record_bar(_bar())
    manifest = next((tmp_path/'raw/_manifest').glob('*.jsonl'))
    first = manifest_summary(manifest)
    original = Path.open
    def guarded(path, *args, **kwargs):
        assert path != manifest, 'unchanged manifest must not be rescanned'
        return original(path, *args, **kwargs)
    with monkeypatch.context() as patch:
        patch.setattr(Path, 'open', guarded)
        assert manifest_summary(manifest) == first
    recorder.record_bar(_bar().model_copy(update={'symbol':'QQQ'}))
    result = query_raw_catalog(tmp_path, summarize=True)
    assert {r.symbol for r in result.entries} == {'SPY','QQQ'}
    assert result.matched_entries == 2
    assert query_raw_catalog(tmp_path, summarize=True, symbol='QQQ').matched_entries == 1
    assert query_raw_catalog(tmp_path, summarize=True, start_date=date(2099,1,1)).entries == []


def test_corrupt_summary_rebuilds_and_preserves_manifest_errors(tmp_path):
    recorder = MarketDataRecorder(writer=RawMarketDataWriter(tmp_path, fsync=False),
        catalog=RawDataCatalog(tmp_path, fsync=False), event_store=None)
    recorder.record_bar(_bar())
    manifest = next((tmp_path/'raw/_manifest').glob('*.jsonl'))
    with manifest.open('a', encoding='utf8') as stream:
        stream.write('invalid json\n')
    first = manifest_summary(manifest)
    cache = manifest.parent/'_summaries'/(manifest.name+'.json')
    saved = json.loads(cache.read_text(encoding='utf8'))
    saved['payload']['entries'] = []
    cache.write_text(json.dumps(saved), encoding='utf8')
    assert manifest_summary(manifest) == first
    assert first['records_invalid'] == 1 and first['errors']


def test_manifest_rewrite_truncation_and_incomplete_append_are_not_cached_as_complete(tmp_path):
    recorder = MarketDataRecorder(writer=RawMarketDataWriter(tmp_path, fsync=False),
        catalog=RawDataCatalog(tmp_path, fsync=False), event_store=None)
    recorder.record_bar(_bar())
    manifest = next((tmp_path/'raw/_manifest').glob('*.jsonl'))
    original = manifest.read_bytes()
    assert manifest_summary(manifest)['records_read'] == 1
    manifest.write_bytes(original.replace(b'SPY', b'QQQ'))
    assert manifest_summary(manifest)['entries'][0]['symbol'] == 'QQQ'
    manifest.write_bytes(original + original[:-1])
    assert manifest_summary(manifest)['records_read'] == 1
    with manifest.open('ab') as stream:
        stream.write(b'\n')
    assert manifest_summary(manifest)['records_read'] == 2
    manifest.write_bytes(original)
    assert manifest_summary(manifest)['records_read'] == 1
