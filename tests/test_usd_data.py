from http.client import IncompleteRead
import io
import json
import ssl
from types import SimpleNamespace
from urllib.error import URLError

import pytest

from systematic_trading.data import http
from systematic_trading.lean.contracts import sha256, write_json
from systematic_trading.research import usd_data
from systematic_trading.research.usd_index_governance import audit_snapshot
from test_analytics_projection import MemoryAnalytics
from test_usd_index_research import snapshot


@pytest.fixture
def setup(tmp_path, monkeypatch):
    content, metadata = snapshot()
    prior = audit_snapshot(content.replace('20200429', '20200428'),
                          dict(metadata, vintage_date='2020-04-28', known_through='2020-04-29'))
    root = tmp_path/'prior'
    root.mkdir()
    write_json(root/'snapshots.json', [prior])
    write_json(root/'manifest.json', {'snapshots.json': sha256(root/'snapshots.json')})
    analytics = MemoryAnalytics()
    analytics.publish(usd_data.SOURCE, sha256(root/'manifest.json'), [], provenance={'root':str(root)})
    monkeypatch.setattr(http.time, 'sleep', lambda _: None)
    monkeypatch.setattr(http, '_native_read_bytes', lambda *a, **k: None)
    return SimpleNamespace(data_dir=tmp_path), analytics, content.encode()


def test_timeout_then_partial_response_retries_before_audited_publication(setup, monkeypatch):
    settings, analytics, content = setup
    calls = []
    class Partial(io.BytesIO):
        def read(self, size):
            raise IncompleteRead(b'partial')
    partial = Partial()
    def open_request(request, **kwargs):
        calls.append(request)
        assert kwargs == {'timeout':35}
        if len(calls) == 1:
            raise TimeoutError('The read operation timed out')
        return partial if len(calls) == 2 else io.BytesIO(content)
    monkeypatch.setattr(http, 'urlopen', open_request)
    assert usd_data.refresh_usd(settings, analytics, '2020-04-30')
    assert len(calls) == 3 and all(r is calls[0] for r in calls)
    assert 'vintage_date=2020-04-29' in calls[0].full_url
    assert partial.closed
    raw = settings.data_dir/'market_data/usd_archives/2020-04-29/DTWEXBGS.csv'
    assert raw.read_bytes() == content
    metadata = json.loads(raw.with_name('receipt.json').read_text())
    rows, pin = usd_data.load_usd(analytics)
    assert rows[-1]['known_through'] == '2020-04-30'
    assert rows[-1]['source_sha256'] == metadata['sha256'] == sha256(raw)
    assert rows[-1]['retrieved_at'] == metadata['retrieved_at']
    assert pin['batch'] == analytics.latest(usd_data.SOURCE)['version']
    monkeypatch.setattr(http, 'urlopen', lambda *a, **k: pytest.fail('Published vintage must be idempotent'))
    assert not usd_data.refresh_usd(settings, analytics, '2020-04-30')


@pytest.mark.parametrize('error,attempts', [
    (TimeoutError('The read operation timed out'), 3),
    (URLError(ssl.SSLEOFError(8, 'unexpected EOF')), 3),
    (URLError(ssl.SSLCertVerificationError(1, 'bad certificate')), 1),
])
def test_failed_acquisition_preserves_publication_and_has_dated_error(setup, monkeypatch, error, attempts):
    settings, analytics, _ = setup
    before = analytics.latest(usd_data.SOURCE)
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise error
    monkeypatch.setattr(http, 'urlopen', fail)
    with pytest.raises(ValueError, match='DTWEXBGS/2020-04-29 for signal close 2020-04-30') as caught:
        usd_data.refresh_usd(settings, analytics, '2020-04-30')
    assert caught.value.__cause__ is error
    assert len(calls) == attempts
    assert analytics.latest(usd_data.SOURCE) == before
    assert not list((settings.data_dir/'market_data/usd_archives').rglob('*.csv'))
    assert not list((settings.data_dir/'market_data/usd_archives').rglob('receipt.json'))


def test_oversized_response_never_becomes_truncated_archive(setup, monkeypatch):
    settings, analytics, _ = setup
    before = analytics.latest(usd_data.SOURCE)
    monkeypatch.setattr(http, 'urlopen', lambda *a, **k: io.BytesIO(b'x' * 4_000_001))
    with pytest.raises(ValueError, match='bounded response size'):
        usd_data.refresh_usd(settings, analytics, '2020-04-30')
    assert analytics.latest(usd_data.SOURCE) == before
    assert not list((settings.data_dir/'market_data/usd_archives').rglob('*.csv'))


def test_wrong_vintage_is_retained_as_raw_evidence_but_not_published(setup, monkeypatch):
    settings, analytics, content = setup
    before = analytics.latest(usd_data.SOURCE)
    wrong = content.replace(b'20200429', b'20200428')
    monkeypatch.setattr(http, 'urlopen', lambda *a, **k: io.BytesIO(wrong))
    with pytest.raises(ValueError, match='Wrong USD identity/vintage'):
        usd_data.refresh_usd(settings, analytics, '2020-04-30')
    assert analytics.latest(usd_data.SOURCE) == before
    raw = settings.data_dir/'market_data/usd_archives/2020-04-29/DTWEXBGS.csv'
    assert raw.read_bytes() == wrong
    raw.write_bytes(content)
    monkeypatch.setattr(http, 'urlopen', lambda *a, **k: pytest.fail('Changed evidence must fail closed'))
    with pytest.raises(ValueError, match='Changed USD provider archive'):
        usd_data.refresh_usd(settings, analytics, '2020-04-30')


def test_native_response_still_passes_the_same_raw_capture_and_audit(setup, monkeypatch):
    settings, analytics, content = setup
    monkeypatch.setattr(http, 'urlopen', lambda *a, **k: (_ for _ in ()).throw(TimeoutError('timeout')))
    calls = []
    def native(request, **kwargs):
        calls.append(request.full_url)
        assert kwargs == {'timeout':35, 'max_bytes':4_000_000}
        return content
    monkeypatch.setattr(http, '_native_read_bytes', native)
    assert usd_data.refresh_usd(settings, analytics, '2020-04-30')
    assert len(calls) == 1 and 'vintage_date=2020-04-29' in calls[0]
    assert usd_data.load_usd(analytics)[0][-1]['known_through'] == '2020-04-30'
