"""Bind trading inference to the same verified publication used by monitoring."""
import json
from pathlib import Path

from systematic_trading.market_data.analytics_store import AnalyticsStore, digest, encode
from systematic_trading.research.rolling_tracking import read_model_artifacts, select_rolling_model


def published_rolling_schedule(settings, definition, price_batch):
    if not price_batch:
        raise ValueError('Rolling strategy requires published audited decision inputs.')
    document = AnalyticsStore.from_settings(settings).document('tracked-strategies/calculations', 'report/'+definition.key)
    if not document:
        raise ValueError('Rolling strategy calculation has not been published.')
    report, provenance = json.loads(document[0]['payload']), json.loads(document[1]['provenance'])
    if provenance['inputs']['batch'] != price_batch or report['strategyDefinition'] != definition.to_dict():
        raise ValueError('Rolling model and audited decision inputs differ; await application refresh.')
    training = report['modelTraining']
    receipt = training['receipt']
    attempt = Path(receipt['artifact_path']).resolve()
    root = attempt.parent.parent
    if not root.is_relative_to((settings.data_dir/'tracked_models').resolve()):
        raise ValueError('Rolling model is outside the managed model directory.')
    schedule, verified = read_model_artifacts(root)
    if verified != receipt:
        raise ValueError('Published rolling receipt differs from the verified training artifact.')
    if digest(encode(schedule[training['fitAsOf']]['model'])) != training['modelSha256']:
        raise ValueError('Published rolling model hash mismatch.')
    return schedule, dict(receipt=receipt, calculation_revision=document[1]['version'],
        batch=price_batch, model_sha256=training['modelSha256'])


def bind_rolling_model(settings, definition, price_batch, overlays, histories, day):
    schedule, receipt = published_rolling_schedule(settings, definition, price_batch)
    model = select_rolling_model(schedule, histories, day)
    for overlay, spec in zip(overlays, definition.overlays, strict=True):
        if spec.kind == 'rolling_model':
            overlay.model = model
    return receipt
