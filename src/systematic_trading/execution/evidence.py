"""Immutable, deduplicated broker execution responses for replay and diagnosis."""
import hashlib
import json
import os
from pathlib import Path
from uuid import uuid4


def _write(path: Path, payload: str) -> None:
    temporary = path.with_name(path.name + '.' + uuid4().hex + '.tmp')
    try:
        temporary.write_text(payload, encoding='utf-8')
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def retain_execution_response(directory: Path, response: dict, *, client_id: int, captured_at: str) -> str:
    """Failure to retain evidence fails the read; it must never produce success."""
    payload = json.dumps(response, sort_keys=True, ensure_ascii=False, separators=(',', ':'))
    digest = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (digest + '.json')
    if path.exists():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError('Retained broker execution evidence has a hash mismatch.')
    else:
        _write(path, payload)
    _write(directory / f'latest-{client_id}.json', json.dumps(dict(
        captured_at=captured_at, sha256=digest, evidence_ref=str(path),
        completed=response['completed'], request_error=response.get('request_error'))))
    return str(path)
