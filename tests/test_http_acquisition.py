from http.client import IncompleteRead, RemoteDisconnected
import io
import ssl
import subprocess
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest

from systematic_trading.data import http
from systematic_trading.recorders import economics, energy, research_etfs


@pytest.mark.parametrize("fetch", [economics.fetch_csv, energy.fetch_bytes, research_etfs.fetch_issuer])
def test_recorder_recovers_tls_eof_without_changing_request_or_tls(monkeypatch, fetch):
    calls, delays = [], []
    def open_request(request, **kwargs):
        calls.append((request, kwargs))
        if len(calls) < 3:
            raise URLError(ssl.SSLEOFError(8, "unexpected EOF"))
        return io.BytesIO(b"complete source")
    monkeypatch.setattr(http, "urlopen", open_request)
    monkeypatch.setattr(http.time, "sleep", delays.append)
    assert fetch("https://source.example/data") == b"complete source"
    assert delays == [0.5, 1.0]
    assert all(c[0] is calls[0][0] for c in calls)
    assert all(set(c[1]) == {"timeout"} for c in calls)  # no unverified context


@pytest.mark.parametrize("error,retries", [
    (URLError(ssl.SSLEOFError(8, "EOF")), 3),
    (TimeoutError("timeout"), 3),
    (RemoteDisconnected("closed without response"), 3),
    (URLError(ssl.SSLCertVerificationError(1, "bad certificate")), 1),
    (HTTPError("https://example", 403, "Forbidden", {}, None), 1),
    (HTTPError("https://example", 503, "Unavailable", {}, None), 3),
])
def test_retry_exhaustion_and_nontransient_failures(monkeypatch, error, retries):
    calls = []
    def fail(*args, **kwargs):
        calls.append(1)
        raise error
    monkeypatch.setattr(http, "urlopen", fail)
    monkeypatch.setattr(http.time, "sleep", lambda _: None)
    with pytest.raises(type(error)):
        http.read_bytes(Request("https://example"), timeout=1, max_bytes=20)
    assert len(calls) == retries


def test_partial_body_is_discarded_and_response_closed(monkeypatch):
    class Interrupted(io.BytesIO):
        def read(self, size):
            raise IncompleteRead(b"partial")
    first = Interrupted()
    responses = iter([first, io.BytesIO(b"whole")])
    monkeypatch.setattr(http, "urlopen", lambda *a, **k: next(responses))
    monkeypatch.setattr(http.time, "sleep", lambda _: None)
    assert http.read_bytes(Request("https://example"), timeout=1, max_bytes=20) == b"whole"
    assert first.closed


def test_oversized_body_is_rejected_without_retry(monkeypatch):
    response = io.BytesIO(b"too large")
    monkeypatch.setattr(http, "urlopen", lambda *a, **k: response)
    monkeypatch.setattr(http.time, "sleep", lambda _: pytest.fail("Unexpected retry"))
    with pytest.raises(ValueError, match="bounded response size"):
        http.read_bytes(Request("https://example"), timeout=1, max_bytes=3)
    assert response.closed


@pytest.mark.parametrize('bypass', [False, True])
def test_native_fallback_preserves_request_proxy_and_verified_tls(monkeypatch, bypass):
    monkeypatch.setattr(http.sys, 'platform', 'win32')
    monkeypatch.setattr(http.shutil, 'which', lambda _: 'C:/Windows/System32/curl.exe')
    monkeypatch.setattr(http, 'getproxies', lambda: {'https':'http://127.0.0.1:7892'})
    monkeypatch.setattr(http, 'proxy_bypass', lambda _: bypass)
    calls = []
    def run(command, **kwargs):
        calls.append(command)
        assert kwargs['timeout'] == 15 and kwargs['capture_output']
        assert 'shell' not in kwargs
        return SimpleNamespace(returncode=0, stdout=b'complete')
    monkeypatch.setattr(http.subprocess, 'run', run)
    request = Request('https://example/data?exact=vintage', headers={'User-Agent':'audit'})
    assert http._native_read_bytes(request, timeout=10, max_bytes=100) == b'complete'
    command = calls[0]
    assert command[1] == '-q'
    for flag, value in {'--proto':'=https', '--proto-redir':'=https', '--max-time':'10',
                        '--max-filesize':'100', '--url':request.full_url,
                        '--proxy':'' if bypass else 'http://127.0.0.1:7892',
                        '--noproxy':'*' if bypass else ''}.items():
        assert command[command.index(flag)+1] == value
    assert 'User-agent: audit' in command
    assert not {'--insecure', '-k', '--proxy-insecure', '--ssl-no-revoke'} & set(command)


@pytest.mark.parametrize('failure', ['partial', 'certificate', 'oversized', 'timeout'])
def test_native_failure_cannot_return_bytes(monkeypatch, failure):
    monkeypatch.setattr(http.sys, 'platform', 'win32')
    monkeypatch.setattr(http.shutil, 'which', lambda _: 'curl.exe')
    monkeypatch.setattr(http, 'proxy_bypass', lambda _: True)
    def run(command, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(command, 1)
        return SimpleNamespace(returncode={'partial':18,'certificate':60}.get(failure, 0), stdout=b'partial')
    monkeypatch.setattr(http.subprocess, 'run', run)
    with pytest.raises((OSError, ValueError)):
        http._native_read_bytes(Request('https://example'), timeout=1, max_bytes=3)


@pytest.mark.parametrize('error', [URLError(ssl.SSLCertVerificationError(1, 'certificate')),
                                 HTTPError('https://example',403,'Forbidden',{},None)])
def test_nontransient_failure_never_uses_native_fallback(monkeypatch, error):
    monkeypatch.setattr(http, 'urlopen', lambda *a, **k: (_ for _ in ()).throw(error))
    monkeypatch.setattr(http, '_native_read_bytes', lambda *a, **k: pytest.fail('Must fail closed'))
    with pytest.raises(type(error)):
        http.read_bytes(Request('https://example'), timeout=1, max_bytes=3, native_fallback=True)


@pytest.mark.parametrize('fetch,timeout,limit', [
    (economics.fetch_csv, 25, 4_000_000), (energy.fetch_bytes, 30, 10_000_000),
])
@pytest.mark.parametrize('error', [RemoteDisconnected('closed'), TimeoutError('timeout')])
def test_recorders_use_bounded_native_fallback_after_transient_exhaustion(monkeypatch, fetch, timeout, limit, error):
    requests = []
    def fail(request, **kwargs):
        assert kwargs == {'timeout': timeout}
        requests.append(request)
        raise error
    def native(request, **kwargs):
        assert len(requests) == 3 and all(r is request for r in requests)
        assert request.full_url == 'https://source.example/exact?vintage=2026-11-06'
        assert kwargs == {'timeout': timeout, 'max_bytes': limit}
        return b'complete audited-source candidate'
    monkeypatch.setattr(http, 'urlopen', fail)
    monkeypatch.setattr(http.time, 'sleep', lambda _: None)
    monkeypatch.setattr(http, '_native_read_bytes', native)
    assert fetch('https://source.example/exact?vintage=2026-11-06') == b'complete audited-source candidate'


@pytest.mark.parametrize('fetch', [economics.fetch_csv, energy.fetch_bytes])
@pytest.mark.parametrize('error', [URLError(ssl.SSLCertVerificationError(1, 'certificate')),
                                 HTTPError('https://example', 403, 'Forbidden', {}, None)])
def test_recorder_permanent_failure_never_uses_native_fallback(monkeypatch, fetch, error):
    monkeypatch.setattr(http, 'urlopen', lambda *a, **k: (_ for _ in ()).throw(error))
    monkeypatch.setattr(http, '_native_read_bytes', lambda *a, **k: pytest.fail('Must fail closed'))
    with pytest.raises(type(error)):
        fetch('https://example')


@pytest.mark.parametrize('fallback', [False, True])
def test_energy_empty_response_rejected_from_both_transports(monkeypatch, fallback):
    def open_request(*args, **kwargs):
        if fallback:
            raise RemoteDisconnected('closed')
        return io.BytesIO(b'')
    monkeypatch.setattr(http, 'urlopen', open_request)
    monkeypatch.setattr(http.time, 'sleep', lambda _: None)
    monkeypatch.setattr(http, '_native_read_bytes', lambda *a, **k: b'')
    with pytest.raises(ValueError, match='Unexpected EIA response size'):
        energy.fetch_bytes('https://example')
