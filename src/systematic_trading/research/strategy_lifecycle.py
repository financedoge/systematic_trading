"""Durable global monitoring membership; independent of account resets and funding."""
from datetime import UTC, datetime
import json

from systematic_trading.execution.locks import ORDER_CONNECTION_LOCK
from systematic_trading.market_data.analytics_store import digest, encode
from systematic_trading.portfolio.strategy_allocation import control_state, scope_for
from systematic_trading.research.strategy_catalog import registered_strategy_definition

SCOPE = 'strategy-monitoring-v1'


def membership(settings, store):
    config = json.loads(settings.strategy_monitoring_config_path.read_text(encoding='utf8'))
    reader = getattr(store, 'strategy_control_state', None)
    saved = reader(SCOPE) if reader else None
    saved = saved or dict(revision=0, overrides={})
    keys = set(config.get('monitored_strategy_ids', []))
    for key, row in saved['overrides'].items():
        (keys.add if row['lifecycle']=='monitored' else keys.discard)(key)
    return dict(saved, monitored=sorted(keys))


def effective_config(settings, store):
    config = json.loads(settings.strategy_monitoring_config_path.read_text(encoding='utf8'))
    state = membership(settings, store)
    config.update(monitored_strategy_ids=state['monitored'], membership_revision=state['revision'],
        monitoring_generations={key:row['generation'] for key,row in state['overrides'].items()})
    return config


def required_generation(state, key):
    return state['overrides'].get(key, {}).get('generation', 0)


def replay_supported(key):
    try:
        d = registered_strategy_definition(key)
        return d.universe_key=='multi_asset' and d.scheduler=='static_monthly'
    except ValueError:
        return False


def archive_blocker(store, key):
    roles = control_state(store)
    if key == roles['sota_key']:
        return 'Choose another SOTA before archiving this strategy.'
    if any(r['strategy_key']==key for r in roles['active']['allocations']):
        return 'Remove this strategy from the active allocation before archiving it.'
    pending = (roles.get('pending') or {}).get('change', {})
    if key==pending.get('sota_key') or any(r['strategy_key']==key for r in pending.get('allocations') or []):
        return 'Cancel or complete the pending allocation change before archiving this strategy.'
    return None


def change_membership(settings, store, *, key, lifecycle, expected_revision, event_id, operator, reason):
    if lifecycle not in {'monitored','archived'} or not operator.strip() or not reason.strip():
        raise ValueError('A lifecycle, operator and reason are required.')
    if not replay_supported(key):
        raise ValueError('This historical artifact has no supported replay definition. It cannot be monitored yet.')
    request_hash = digest(encode([key,lifecycle,expected_revision,operator,reason]))
    with ORDER_CONNECTION_LOCK:
        for previous in store.strategy_control_events(SCOPE):
            if previous['event_id']==event_id:
                if previous['request_hash']!=request_hash:
                    raise ValueError('Idempotency key was used for a different change.')
                return membership(settings, store)
        state = membership(settings, store)
        if state['revision']!=expected_revision:
            raise ValueError('Strategy membership changed. Refresh and try again.')
        if (key in state['monitored'])==(lifecycle=='monitored'):
            return state
        roles=control_state(store)
        if lifecycle=='archived' and (issue:=archive_blocker(store,key)):
            raise ValueError(issue)
        now=datetime.now(UTC).isoformat()
        overrides=dict(state['overrides'], **{key:dict(lifecycle=lifecycle,generation=state['revision']+1,changed_at=now)})
        store.commit_strategy_control(SCOPE,expected_revision,dict(overrides=overrides),
            dict(event_id=event_id,request_hash=request_hash,kind='monitoring_'+lifecycle,at=now,
                 strategy_key=key,operator=operator,reason=reason),
            guard_revisions={scope_for(store):roles['revision']})
        return membership(settings,store)


def require_monitored(settings, store, keys):
    state=membership(settings,store)
    missing=sorted(set(keys)-set(state['monitored']))
    if missing:
        raise ValueError('Allocation is restricted to monitored strategies: '+', '.join(missing))
    return state


def calculation_ready(detail, state, through=None):
    key=detail['strategy_id']
    return (key in state['monitored'] and detail.get('lifecycle')=='monitored'
        and detail.get('monitoring_generation',0)==required_generation(state,key)
        and detail.get('app_tracking',False) and (through is None or detail.get('end_date','')>=through))


def decorate_catalog(payload, settings, store):
    state=membership(settings,store)
    through=payload.get('expected_through')
    present={r['strategy_id'] for r in payload['strategies']}
    for key in set(state['monitored'])-present:
        definition=registered_strategy_definition(key)
        payload['strategies'].append(dict(strategy_id=key,name=definition.name,lifecycle='monitored',
            app_tracking=False,report_available=False,report_url=None,allocation=[],
            accounting_currency='USD' if key in {'research_fallback_f3_v1','research_economic_context_ridge_v1'} else 'CNH'))
    for row in payload['strategies']:
        key=row['strategy_id'];ready=calculation_ready(row,state,through)
        row.update(lifecycle='monitored' if key in state['monitored'] else 'archived',
            calculation_status='Current' if ready else 'Catching up' if key in state['monitored'] else 'Paused',
            allocation_ready=ready,can_restore=replay_supported(key),archive_blocker=archive_blocker(store,key))
    payload['membership_revision']=state['revision']
    return payload
