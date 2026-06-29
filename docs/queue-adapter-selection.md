# Queue Adapter Selection

Status: selected

Decision date: 2026-06-27

## Decision

Use NATS JetStream as the initial queue adapter target.

Keep the platform queue abstraction behind `PlatformEventPublisher` so Redpanda or Kafka can replace or complement NATS later without changing event producers.

## Why NATS JetStream First

The current platform stage needs:

- A simple local/server deployment path.
- Durable event storage and replay.
- At-least-once delivery with explicit acknowledgements.
- Low operational load on one machine.
- Clean mapping from current event subjects to queue subjects.
- A path to fan out events to alerts, metrics, audit, market-data processing, and future services.

NATS JetStream fits this stage best. Official NATS documentation states that JetStream is built into `nats-server`, stores messages for later replay, supports replication, and was designed to be easy to configure and operate. JetStream consumers also provide at-least-once delivery and track acknowledgements.

## Comparison

| Option | Fit Now | Strengths | Tradeoffs | Decision |
| --- | --- | --- | --- | --- |
| NATS JetStream | High | Built into NATS server, durable streams, replay, at-least-once consumers, simple local operations, subject-based routing. | Smaller ecosystem than Kafka; partitioning and large analytical stream ecosystem are not Kafka-level. | Select for initial adapter. |
| Redpanda | Medium later | Kafka API compatibility, replayable topics, high-throughput design, single binary, simpler than Kafka operationally. | More platform weight than needed now; licensing/product posture should be reviewed before committing. | Revisit for high-throughput market-data streaming or Kafka API needs. |
| Apache Kafka | Low now, high later | Battle-tested event-streaming platform, durable topics, partitions, replication, broad ecosystem and clients. | Highest operational complexity for current single-machine stage. | Defer until scale/ecosystem requirements justify it. |

## Initial NATS Design

Stream:

- Name: `ST_EVENTS`
- Subjects: `systematic_trading.events.v1.>`
- Storage: file-backed JetStream storage
- Retention: limits-based for operational events; raw market-data retention should be handled separately by the recorder/lake design

Message payload:

- JSON from `PlatformEvent.model_dump(mode="json")`
- Message key/header: `event_id`
- Subject: `event.subject`, for example `systematic_trading.events.v1.order.status_changed`

Delivery contract:

- At-least-once.
- Consumers must be idempotent by `event_id`.
- Producer path remains outbox-first: write local state and outbox event in SQLite/Postgres, then dispatch to JetStream.
- If queue publish fails, the outbox keeps the event pending for retry.

Initial durable consumers:

- `audit_replay`: reads all platform events for diagnostics.
- `alerts`: reads `alert.raised` and `incident.recorded`.
- `metrics`: reads service, data, order, and reconciliation events once those producers exist.
- `market_data_postprocess`: future consumer for normalized market-data workflows.

## P1.8 Unblock Criteria

P1.8 can start when:

1. A local NATS server runtime is available through an explicit install or Docker/system service path.
2. The Python NATS client dependency is added as an optional dependency.
3. The adapter can be tested without requiring live trading connectivity.
4. The service manifest is updated with a planned or active `nats_jetstream` service.

The selected runtime path is Docker Compose under `deploy/nats/`. The current machine still needs Docker installed before live NATS smoke tests can run.

## Re-Evaluation Triggers

Revisit Redpanda or Kafka if any of these become true:

- Live market-data recording exceeds what a simple NATS deployment can comfortably handle.
- We need Kafka-compatible connectors or external ecosystem integrations.
- We require partition-heavy analytical streams across multiple machines.
- The platform moves from local/server deployment to a multi-node cluster with independent data engineering consumers.

## Sources

- NATS JetStream docs: https://docs.nats.io/nats-concepts/jetstream
- NATS JetStream consumers: https://docs.nats.io/nats-concepts/jetstream/consumers
- Redpanda event streaming docs: https://docs.redpanda.com/streaming/current/get-started/intro-to-events/
- Apache Kafka introduction: https://kafka.apache.org/43/getting-started/introduction/
