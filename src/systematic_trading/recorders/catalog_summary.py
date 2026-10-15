"""Disposable symbol/date summaries of immutable raw manifest snapshots.

This is a lookup cache, never a replacement for raw-envelope hash validation.
Changed or corrupt cache entries are rebuilt from the original manifest.
"""
import json
from hashlib import sha256
from pathlib import Path
from threading import Lock

from systematic_trading.runtime_io import atomic_json

_lock = Lock()


def _anchors(stream, size):
    stream.seek(0)
    head = sha256(stream.read(min(size, 4096))).hexdigest()
    stream.seek(max(0, size-4096))
    tail = sha256(stream.read(min(size, 4096))).hexdigest()
    return [head, tail]


def manifest_summary(path):
    from systematic_trading.recorders.market_data import RawCatalogEntry

    path = Path(path)
    cache = path.parent / '_summaries' / (path.name + '.json')
    with _lock:
        stat = path.stat()
        identity = [str(path.resolve()), stat.st_ino, stat.st_size, stat.st_mtime_ns]
        previous = None
        try:
            saved = json.loads(cache.read_text(encoding='utf8'))
            payload = saved['payload']
            encoded = json.dumps(payload, sort_keys=True).encode()
            if saved['sha256'] == sha256(encoded).hexdigest() and saved['version'] == 2:
                if saved['identity'] == identity:
                    return payload
                old = saved['identity']
                # Manifests are append-only. Check both ends of the old snapshot
                # before consuming its suffix; rewrites/truncations rebuild.
                if old[:2] == identity[:2] and old[2] < stat.st_size and saved['offset'] == old[2]:
                    with path.open('rb') as stream:
                        if _anchors(stream, old[2]) == saved['anchors']:
                            previous = saved
        except (OSError, ValueError, KeyError, TypeError):
            pass
        representatives, counts, errors = {}, {}, []
        records_read = invalid = 0
        offset = 0
        if previous:
            payload = previous['payload']
            counts, errors = payload['counts'], payload['errors']
            records_read, invalid = payload['records_read'], payload['records_invalid']
            for row in payload['entries']:
                key = json.dumps([row['recorder_date'], row['source_name'], row['environment'],
                                  row['data_kind'], row['symbol'], row['raw_schema_version']])
                representatives[key] = row
            offset = previous['offset']
        with path.open('rb') as stream:
            stream.seek(offset)
            # Only complete lines in this bounded snapshot; a concurrent append
            # is picked up on the next call, never certified by a newer stat.
            while stream.tell() < stat.st_size:
                line = stream.readline()
                if not line.endswith(b'\n') or stream.tell() > stat.st_size:
                    break
                offset = stream.tell()
                if not line.strip():
                    continue
                records_read += 1
                try:
                    entry = RawCatalogEntry.model_validate_json(line)
                except ValueError as exc:
                    invalid += 1
                    if len(errors) < 50:
                        errors.append(f'{path}#{records_read}: {exc}')
                    continue
                key = json.dumps([str(entry.recorder_date), entry.source_name, entry.environment,
                                  entry.data_kind, entry.symbol, entry.raw_schema_version])
                representatives[key] = entry.model_dump(mode='json')
                counts[key] = counts.get(key, 0) + 1
            anchors = _anchors(stream, stat.st_size)
        payload = dict(entries=list(representatives.values()), counts=counts,
                       records_read=records_read, records_invalid=invalid, errors=errors)
        try:
            atomic_json(cache, dict(version=2, identity=identity, offset=offset, anchors=anchors, payload=payload,
                sha256=sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()))
        except OSError:
            pass  # Read-only archives still work without a cache.
        return payload
