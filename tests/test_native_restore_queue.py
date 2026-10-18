import asyncio
import json
from pathlib import Path
import runpy
from types import SimpleNamespace

import pytest


@pytest.mark.parametrize('actual_subjects', [7, 0])
def test_restore_compares_raw_server_subject_count(tmp_path, monkeypatch, actual_subjects):
    module = runpy.run_path(str(Path('scripts/verify_native_restore.py')))
    expected = dict(messages=1, bytes=10, first_seq=1, last_seq=1, consumer_count=0, num_subjects=7)
    (tmp_path/'streams.json').write_text(json.dumps({'ST_EVENTS':dict(config={},state=expected)}))
    (tmp_path/'ST_EVENTS.snapshot').write_bytes(b'queue-snapshot')
    class Connection:
        async def request(self, subject, data, **kwargs):
            if subject.startswith('$JS.API.STREAM.RESTORE.'):
                payload = {'deliver_subject':'restore.chunks'}
            elif subject.startswith('$JS.API.STREAM.INFO.'):
                payload = {'state':dict(expected,num_subjects=actual_subjects)}
            elif data:
                return SimpleNamespace(data=b'')
            else:
                payload = {}
            return SimpleNamespace(data=json.dumps(payload).encode())
        async def close(self):
            pass
    async def connect(*args, **kwargs):
        return Connection()
    monkeypatch.setattr(module['nats'], 'connect', connect)
    if actual_subjects != 7:
        with pytest.raises(ValueError,match='num_subjects'):
            asyncio.run(module['restore_queue']('nats://test',tmp_path))
    else:
        assert asyncio.run(module['restore_queue']('nats://test',tmp_path))['ST_EVENTS']==expected
