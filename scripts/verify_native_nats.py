"""Exercise deduplication, lost-ack replay and restart using an isolated test stream."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import nats
from nats.js.api import ConsumerConfig, AckPolicy, StreamConfig

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from systematic_trading.runtime_io import atomic_json


async def main():
    connection = await nats.connect('nats://127.0.0.1:4222', name='native-migration-verification', allow_reconnect=False, max_reconnect_attempts=1)
    js = connection.jetstream()
    before = await js.stream_info('ST_EVENTS')
    stream = 'ST_NATIVE_CHECK_' + uuid4().hex[:8]
    subject = 'native_migration.' + stream
    await js.add_stream(config=StreamConfig(name=stream, subjects=[subject], storage='file', max_bytes=1024**2))
    try:
        first = await js.publish(subject, b'restart-check', headers={'Nats-Msg-Id': 'same-event'})
        duplicate = await js.publish(subject, b'restart-check', headers={'Nats-Msg-Id': 'same-event'})
        assert first.seq == duplicate.seq and duplicate.duplicate
        sub = await js.pull_subscribe(subject, durable='verification', stream=stream,
            config=ConsumerConfig(ack_policy=AckPolicy.EXPLICIT, ack_wait=1))
        original = (await sub.fetch(1, timeout=5))[0]
        assert original.data == b'restart-check'
        await connection.close()  # Deliberately lose the acknowledgment.
        for action in ('stop', 'start'):
            result = await asyncio.to_thread(subprocess.run, ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                str(ROOT / 'scripts/native_nats.ps1'), '-Action', action], timeout=45,
                capture_output=True, text=True, creationflags=subprocess.CREATE_NO_WINDOW)
            if result.returncode:
                raise RuntimeError('Native NATS ' + action + ' failed: ' + result.stderr + result.stdout)
        connection = await nats.connect('nats://127.0.0.1:4222', name='native-migration-verification', max_reconnect_attempts=1)
        js = connection.jetstream()
        sub = await js.pull_subscribe(subject, durable='verification', stream=stream)
        delivered = (await sub.fetch(1, timeout=5))[0]
        assert delivered.data == original.data and delivered.metadata.num_delivered >= 2
        await delivered.ack_sync()
        consumer = await js.consumer_info(stream, 'verification')
        assert consumer.num_ack_pending == 0
        after = await js.stream_info('ST_EVENTS')
        assert after.state.messages == before.state.messages
        assert after.state.first_seq == before.state.first_seq
        assert after.state.last_seq == before.state.last_seq
        atomic_json(ROOT / 'var/maintenance/windows-cutover/nats-restart-verification.json',
                    dict(passed=True, deduplication=True, lost_ack_redelivery=True, acknowledged=True,
                         production_state_unchanged=True, state=after.state.as_dict()))
        print(json.dumps(dict(passed=True, production_messages=after.state.messages)))
    finally:
        if connection.is_closed:
            connection = await nats.connect('nats://127.0.0.1:4222', max_reconnect_attempts=1)
            js = connection.jetstream()
        await js.delete_stream(stream)
        await connection.close()


if __name__ == '__main__':
    asyncio.run(main())
