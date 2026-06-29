from datetime import UTC, datetime
from decimal import Decimal

from systematic_trading.domain.enums import Currency, OrderEnvironment
from systematic_trading.domain.events import EventSource, MarketDataKind, MarketDataRecordedEvent, MarketDataRecordedPayload
from systematic_trading.messaging import NatsJetStreamPublisher


def test_nats_jetstream_publisher_publishes_event_payload_and_headers() -> None:
    fake_connection = _FakeNatsConnection()

    async def connect(**kwargs):
        fake_connection.connect_kwargs = kwargs
        return fake_connection

    event = MarketDataRecordedEvent(
        event_id="evt-nats-1",
        occurred_at=datetime(2026, 6, 27, 1, 30, tzinfo=UTC),
        source=EventSource(service="market-data-recorder", environment=OrderEnvironment.PAPER),
        payload=MarketDataRecordedPayload(
            source_name="ib-paper",
            data_kind=MarketDataKind.BAR,
            symbol="SPY",
            currency=Currency.USD,
            trade_date="2026-06-26",
            price=Decimal("512.34"),
            raw_ref="raw/ib/2026-06-26/SPY.jsonl#line=1",
        ),
    )
    publisher = NatsJetStreamPublisher(servers=["nats://127.0.0.1:4222"], connect=connect)

    publisher.publish(event, subject=event.subject)

    assert fake_connection.connect_kwargs["servers"] == ["nats://127.0.0.1:4222"]
    assert fake_connection.drained is True
    published = fake_connection.jetstream_client.published[0]
    assert published["subject"] == "systematic_trading.events.v1.market_data.recorded"
    assert b'"event_id":"evt-nats-1"' in published["payload"]
    assert published["headers"]["event_id"] == "evt-nats-1"
    assert published["headers"]["event_type"] == "market_data.recorded"


class _FakeNatsConnection:
    def __init__(self) -> None:
        self.jetstream_client = _FakeJetStream()
        self.connect_kwargs = {}
        self.drained = False

    def jetstream(self):
        return self.jetstream_client

    async def drain(self) -> None:
        self.drained = True


class _FakeJetStream:
    def __init__(self) -> None:
        self.published = []

    async def publish(self, subject, payload, headers=None):
        self.published.append({"subject": subject, "payload": payload, "headers": headers or {}})
