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
    if report['strategyDefinition'] != definition.to_dict():
        raise ValueError(f'Strategy recipe mismatch for {definition.name}; published model cannot be used. '
                         'Refresh calculations for the registered recipe before activation.')
    if provenance['inputs']['batch'] != price_batch:
        detail = ''
        path = settings.data_dir/'run/strategy-compute.json'
        if path.exists():
            try:
                compute = json.loads(path.read_text(encoding='utf8'))
                if compute.get('phase') == 'failed':
                    detail = f' Calculation failed: {compute.get("error", "See calculation logs")}'
            except (OSError, ValueError):
                detail = ' Calculation status is unreadable; inspect the application logs.'
        raise ValueError(f'Rolling model and audited decision inputs differ for {definition.name}: '
            f'model prices through {provenance["inputs"].get("price_through", "unknown")}, '
            f'model batch {provenance["inputs"]["batch"][:12]}, required batch {price_batch[:12]}. '
            'Allocation and order preparation are blocked until a matching verified calculation is published.'+detail)
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
