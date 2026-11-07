from http.client import IncompleteRead
import ssl
from urllib.error import HTTPError, URLError

import pytest

from systematic_trading.data import yahoo


@pytest.mark.parametrize('failure,retryable', [
    (URLError(ssl.SSLEOFError('EOF')), True),
    (TimeoutError('timed out'), True),
    (IncompleteRead(b'partial'), True),
    (HTTPError('https://example.invalid', 429, 'rate limit', {}, None), True),
    (HTTPError('https://example.invalid', 404, 'missing', {}, None), False),
    (URLError(ssl.SSLCertVerificationError('bad certificate')), False),
])
def test_acquisition_preserves_retry_classification(monkeypatch, failure, retryable):
    calls = []

    def fail(request, timeout):
        calls.append(request.full_url)
        raise failure

    monkeypatch.setattr(yahoo, 'urlopen', fail)
    with pytest.raises(yahoo.ChartAcquisitionError) as result:
        yahoo.fetch_chart_bytes('SPY', 'interval=1d')
    assert result.value.retryable is retryable
    assert len(calls) == 2
    assert 'query1:' in str(result.value) and 'query2:' in str(result.value)


def test_mixed_transport_and_permanent_failure_is_not_fast_retried(monkeypatch):
    failures = iter([TimeoutError(), HTTPError('https://example.invalid', 404, 'missing', {}, None)])

    def fail(*args, **kwargs):
        raise next(failures)

    monkeypatch.setattr(yahoo, 'urlopen', fail)
    with pytest.raises(yahoo.ChartAcquisitionError) as result:
        yahoo.fetch_chart_bytes('SPY', 'interval=1d')
    assert not result.value.retryable
