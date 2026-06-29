from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from systematic_trading.domain.events import AnyPlatformEvent


class NatsConnection(Protocol):
    def jetstream(self) -> Any:
        ...

    async def drain(self) -> None:
        ...


NatsConnect = Callable[..., Awaitable[NatsConnection]]


@dataclass(frozen=True)
class NatsJetStreamPublisher:
    servers: Sequence[str] = ("nats://127.0.0.1:4222",)
    name: str = "systematic-trading-outbox-dispatcher"
    connect_timeout_seconds: float = 2.0
    connect: NatsConnect | None = None

    def publish(self, event: AnyPlatformEvent, *, subject: str) -> None:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.publish_async(event, subject=subject))
            return
        raise RuntimeError("NatsJetStreamPublisher.publish cannot run inside an active event loop; use publish_async instead.")

    async def publish_async(self, event: AnyPlatformEvent, *, subject: str) -> None:
        connector = self.connect or _default_connect
        connection = await connector(
            servers=list(self.servers),
            name=self.name,
            connect_timeout=self.connect_timeout_seconds,
        )
        try:
            jetstream = connection.jetstream()
            await jetstream.publish(
                subject,
                _event_payload(event),
                headers={
                    "event_id": event.event_id,
                    "event_type": event.event_type.value,
                    "schema_version": str(event.schema_version),
                },
            )
        finally:
            await connection.drain()


async def _default_connect(**kwargs: Any) -> NatsConnection:
    try:
        import nats
    except ImportError as exc:
        raise RuntimeError("NATS publishing requires the optional dependency: pip install -e .[queue]") from exc
    return await nats.connect(**kwargs)


def _event_payload(event: AnyPlatformEvent) -> bytes:
    return json.dumps(event.model_dump(mode="json"), separators=(",", ":"), sort_keys=True).encode("utf-8")
