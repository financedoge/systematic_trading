# Schema Registry Convention

## Status

The project starts with a code-based schema registry in `systematic_trading.schemas`.

This is enough for the current single-repo phase: producers, consumers, tests, replay tools, and future migrations can all import the same registry. An external registry can be added later only after there are multiple independently deployed producers and consumers that need runtime negotiation.

## Registry Scope

The registry covers:

- Platform events published to NATS, JSONL, or the transactional outbox.
- Core data records that feed storage, replay, research, and backtesting.
- Future config schemas that affect service behavior or promotion gates.

Current code entry point:

```python
from systematic_trading.schemas import build_default_schema_registry

registry = build_default_schema_registry()
```

Each registered schema has:

- `schema_id`: stable logical id, such as `event.market_data.recorded` or `data.price_bar`.
- `kind`: `event`, `data`, or `config`.
- `version`: positive integer version.
- `model`: Pydantic model that owns validation and JSON Schema export.
- `owner`: service or domain team responsible for changes.
- `compatibility`: compatibility policy for future versions.
- `status`: `active`, `deprecated`, or `retired`.
- Optional `subject`: message subject for event schemas.

## Naming Rules

Event schemas use:

```text
event.<event_type>
```

Examples:

- `event.market_data.recorded`
- `event.order.status_changed`
- `event.alert.raised`

Queue subjects remain:

```text
systematic_trading.events.v{schema_version}.{event_type}
```

Data schemas use:

```text
data.<record_name>
```

Examples:

- `data.instrument`
- `data.price_bar`
- `data.fx_rate`
- `data.fundamental_snapshot`

Future config schemas should use:

```text
config.<service_or_domain>.<purpose>
```

## Version Rules

The current event envelope uses integer `schema_version`. For event subjects, this integer is the major wire version. A breaking event change must publish on a new subject version.

Allowed without a new major version:

- Clarifying documentation.
- Adding an optional field when the registered compatibility mode permits it.
- Adding a new event type with a new `schema_id`.
- Adding a new data schema with a new `schema_id`.

Requires a new version:

- Adding a required field.
- Removing a field.
- Renaming a field.
- Changing a field type, enum meaning, timestamp semantics, unit, currency convention, or point-in-time semantics.
- Reinterpreting an existing field.
- Changing validation in a way that rejects records that were valid under the previous active version.

Requires deprecation before removal:

- Retiring a schema id.
- Retiring a queue subject.
- Retiring a data table/export contract that is referenced by replay, research, promotion artifacts, or reports.

## Compatibility Modes

`strict`

The candidate schema must preserve field names, required fields, and field shapes. This is the default for event schemas because current event models forbid extra fields.

`backward`

New consumers can read old records. Optional additions are allowed, but required additions, removals, and type changes are not.

`forward`

Old consumers can read new records. This is restrictive when models reject extra fields.

`full`

Backward and forward compatibility both hold. Optional additions are treated as incompatible because older strict consumers may reject them.

`none`

No compatibility promise. Use only for private experimental schemas that are not published, stored, or used in promotion evidence.

## Change Process

1. Add or update the Pydantic model.
2. Register the schema in `systematic_trading.schemas.registry`.
3. Add a test that proves the schema is registered and can export JSON Schema.
4. Run compatibility checks against the previous active model when changing an existing schema.
5. Update this document or the data-contract docs if semantics change.
6. Update `docs/execution-kanban.md` and `log.md` for architecture-relevant schema changes.

Event producers must not publish unregistered event types or unregistered schema versions. Consumers should reject unknown event schema versions unless a documented compatibility bridge exists.

## Current Registered Families

Event schemas:

- `event.market_data.recorded`
- `event.feature.computed`
- `event.proposal.created`
- `event.proposal.decision_recorded`
- `event.order.intent_created`
- `event.order.status_changed`
- `event.fill.recorded`
- `event.reconciliation.completed`
- `event.alert.raised`
- `event.incident.recorded`

Data schemas:

- `data.instrument`
- `data.price_bar`
- `data.fx_rate`
- `data.fundamental_snapshot`
- `data.broker_order_record`

## Future External Registry Trigger

Keep the code registry until one of these becomes true:

- Producers and consumers are deployed from separate repositories.
- Services need runtime schema negotiation.
- Multiple schema versions must be served simultaneously for an extended period.
- Non-Python services need generated schemas as build artifacts.
- A queue/database migration requires centrally stored schema fingerprints.

When that happens, use the code registry as the source for exported JSON Schema artifacts and fingerprints instead of manually maintaining a parallel registry.
