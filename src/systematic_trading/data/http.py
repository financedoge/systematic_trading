"""Bounded retries for idempotent recorder reads using normal verified TLS."""
from http.client import IncompleteRead, RemoteDisconnected
import ssl
import shutil
import subprocess
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import getproxies, proxy_bypass, urlopen


def read_bytes(request, *, timeout, max_bytes, attempts=3, native_fallback=False):
    """Retry transient open/read failures; never return a partial response.

    Keep urllib's configured proxy and certificate verification. Identity and
    content audits remain the caller's responsibility after raw capture.
    """
    for attempt in range(attempts):
        try:
            with urlopen(request, timeout=timeout) as response:
                content = response.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise ValueError("Source exceeds bounded response size")
            return content
        except (OSError, IncompleteRead) as exc:
            reason = exc.reason if isinstance(exc, URLError) else exc
            transient = (
                exc.code in {408, 429, 502, 503, 504} if isinstance(exc, HTTPError)
                else isinstance(reason, (ssl.SSLEOFError, TimeoutError, ConnectionError,
                                         RemoteDisconnected, IncompleteRead))
            )
            if not transient:
                raise
            if attempt + 1 == attempts:
                if native_fallback:
                    content = _native_read_bytes(request, timeout=timeout, max_bytes=max_bytes)
                    if content is not None:
                        return content
                raise
            time.sleep(0.5 * (2 ** attempt))
    raise ValueError("HTTP attempts must be positive")


def _native_read_bytes(request, *, timeout, max_bytes):
    """One Windows curl/Schannel GET after transient urllib retry exhaustion.

    Preserve the exact URL, headers and urllib's proxy routing. Disable curlrc,
    require HTTPS (including redirects), verify certificates and reject partial
    or oversized output. No shell, source substitution or audit bypass.
    """
    executable = shutil.which('curl.exe') if sys.platform == 'win32' else None
    if not executable:
        return None
    parsed = urlsplit(request.full_url)
    if parsed.scheme != 'https' or request.get_method() != 'GET':
        raise ValueError('Native transport supports HTTPS GET only')
    bypass = proxy_bypass(parsed.hostname)
    proxy = '' if bypass else getproxies().get('https', '')
    command = [executable, '-q', '--fail', '--silent', '--show-error', '--location',
               '--max-redirs', '3', '--proto', '=https', '--proto-redir', '=https',
               '--max-time', str(timeout), '--max-filesize', str(max_bytes),
               '--proxy', proxy, '--noproxy', '*' if bypass else '', '--url', request.full_url]
    for name, value in request.header_items():
        command.extend(['--header', f'{name}: {value}'])
    try:
        result = subprocess.run(command, capture_output=True, timeout=timeout + 5,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except subprocess.TimeoutExpired as exc:
        raise OSError('Native HTTPS acquisition timed out') from exc
    if result.returncode:
        raise OSError(f'Native HTTPS acquisition failed (curl exit {result.returncode})')
    if len(result.stdout) > max_bytes:
        raise ValueError('Source exceeds bounded response size')
    return result.stdout
