from copy import deepcopy
from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
import json
import sqlite3

import pytest

from systematic_trading.domain.execution import BrokerExecutionFill, TradeProposal, ProposalReasoning
from systematic_trading.domain.portfolio import AllocationTarget
from systematic_trading.portfolio.strategy_allocation import (
    AllocationChange, allocation_binding_issues, combine_targets, control_state, scope_for,
)
from systematic_trading.portfolio.strategy_book import (
    D, RESERVE, apply_fill, apply_internal, book_value, initial_book, rebalance_intent,
)
from systematic_trading.storage.sqlite import SQLiteStore


@pytest.fixture
def store(tmp_path):
    value = SQLiteStore(tmp_path/'control.db')
    value.initialize()
    return value


def commit(store, revision, key, weight='1'):
    state = control_state(store)
    active = dict(state['active'], version=f'{key}-{revision}', key=key,
        allocations=[dict(strategy_key=key,weight=weight)])
    return store.commit_strategy_control(scope_for(store), revision, dict(state,active=active),
        dict(event_id=f'event-{revision}',request_hash=f'hash-{revision}',kind='allocation_activated'))


def test_state_survives_restart_and_a_b_a_never_rewrites_history(store):
    original = control_state(store)['active']
    assert original['version'] == 'legacy' and original['allocations'][0]['weight'] == '1'
    commit(store,0,'A');commit(store,1,'B');commit(store,2,'A')
    recovered = SQLiteStore(store.database_path)
    assert control_state(recovered)['revision'] == 3
    events = recovered.strategy_control_events(scope_for(store))
    assert [e['state']['active']['key'] for e in events] == ['A','B','A']
    with store._connect() as connection, pytest.raises(sqlite3.IntegrityError,match='immutable'):
        connection.execute('DELETE FROM strategy_control_events')


def test_cas_and_idempotent_retry_do_not_overwrite_newer_state(store):
    first = commit(store,0,'A')
    commit(store,1,'B')
    assert commit(store,0,'A') == first
    assert control_state(store)['active']['key'] == 'B'
    with pytest.raises(ValueError,match='changed'):
        store.commit_strategy_control(scope_for(store),0,{},dict(event_id='other-event',request_hash='x'))
    with pytest.raises(ValueError,match='different change'):
        store.commit_strategy_control(scope_for(store),2,{},dict(event_id='event-0',request_hash='different'))


@pytest.mark.parametrize('weights', [['.6','.5'],['-.2'],['NaN'],['1','0']])
def test_invalid_capital_weights_fail_before_any_change(weights):
    with pytest.raises(ValueError):
        AllocationChange(expected_revision=0,event_id='new-event',operator='Operator',reason='Review',
            allocations=[dict(strategy_key=str(i),weight=w) for i,w in enumerate(weights)],effective_close='2026-10-02')


def test_combined_weights_keep_internal_and_external_cash():
    targets = {k:[AllocationTarget(symbol='SPY',target_weight=D(w),sleeve=k,rationale='test')]
        for k,w in [('A','.3'),('B','.2')]}
    result = combine_targets({'A':D('.6'),'B':D('.4')},targets,sleeve='combined')
    assert result[0].target_weight == D('.26')
    result = combine_targets({'A':D('.5'),'B':D('.3')},targets,sleeve='combined')
    assert result[0].target_weight == D('.21')


def test_old_proposals_blocked_after_new_allocation_even_after_rollback(store):
    proposal = TradeProposal(as_of=date(2026,10,2),sleeve='old',summary='old',reasoning=ProposalReasoning(summary='old'))
    assert allocation_binding_issues(store,proposal) == []
    commit(store,0,'A');commit(store,1,'B');commit(store,2,'A')
    assert allocation_binding_issues(store,proposal)


def test_overlap_internal_cross_and_partial_fills_conserve_positions_and_cash():
    snapshot = dict(positions=[dict(symbol='SPY',quantity='10')],cash=[dict(currency='USD',amount='1000')])
    book = initial_book(snapshot,[dict(strategy_key='A',weight='.6'),dict(strategy_key='B',weight='.4')])
    prices,fx = {'SPY':D(100)},{'USD':D(1)}
    total = sum(book_value(b,prices,fx) for b in book.values())
    intent = rebalance_intent(book,{'A':{'SPY':D('.1')},'B':{'SPY':D('1')}},
        {'A':D('.6'),'B':D('.4'),RESERVE:D(0)},prices,fx)
    assert sum(D(c['quantity']) for c in intent['crosses']) == 4
    assert intent['demands']['SPY'] == {'A':'-0.80'}
    apply_internal(book,intent)
    assert sum(book_value(b,prices,fx) for b in book.values()) == total
    # A different order has two buyers. Partial real fills are allocated pro rata.
    buy = dict(demands={'SPY':{'A':'6','B':'4'}})
    fill = BrokerExecutionFill(symbol='SPY',side='buy',quantity=3,average_price=D(101),currency='USD')
    old = deepcopy(book)
    apply_fill(book,buy,fill)
    assert D(book['A']['positions']['SPY'])-D(old['A']['positions']['SPY']) == D('1.8')
    assert D(book['B']['positions']['SPY'])-D(old['B']['positions']['SPY']) == D('1.2')
    assert sum(D(b['positions']['SPY']) for b in book.values()) == 13
    assert sum(D(b['cash']['USD']) for b in book.values()) == 697


def test_capital_drifts_until_explicit_monthly_reset():
    book = {'A':dict(positions={'SPY':'10'},cash={'USD':'0'}),
        'B':dict(positions={},cash={'USD':'1000'}),RESERVE:dict(positions={},cash={'USD':'0'})}
    args = (book,{'A':{'SPY':D(1)},'B':{}},{'A':D('.5'),'B':D('.5'),RESERVE:D(0)}, {'SPY':D(120)},{'USD':D(1)})
    drifting = rebalance_intent(*args)
    assert drifting['capital_nav_cnh']['A']=='1200' and not drifting['cash_transfers']
    reset = rebalance_intent(*args,reset_capital=True)
    assert D(reset['capital_nav_cnh']['A']) == 1100
    assert D(reset['cash_transfers']['A']) == -100
    assert sum(D(v) for v in reset['cash_transfers'].values()) == 0


def test_marked_handover_attributes_inherited_asset_gain_to_correct_period(monkeypatch):
    from systematic_trading.portfolio import allocation_analytics as module
    from systematic_trading.research.strategy_catalog import current_sota_definition
    key=current_sota_definition().key
    events=[]
    for day,mark,version in [('2026-10-01','100','A'),('2026-10-02','110','B')]:
        snapshot=dict(positions=[dict(symbol='SPY',quantity='1')],cash=[dict(currency='USD',amount='0')])
        active=dict(version=version,allocations=[dict(strategy_key=key,weight='1')],approved_at=day+'T19:00:00+00:00',
            opening=dict(at=day+'T21:00:00+00:00',snapshot=snapshot,book=initial_book(snapshot,[dict(strategy_key=key,weight='1')]),
                prices={'SPY':mark},fx={'USD':'1'},targets=[]))
        events.append(dict(kind='allocation_activated',active=active,effective_close=day,at=day+'T21:00:00+00:00',operator='Test',reason='Switch'))
    rows=[dict(trade_date=d,raw_close=v,adjusted_close=v) for d,v in [('2026-10-01',100),('2026-10-02',110),('2026-10-05',115)]]
    monkeypatch.setattr(module,'control_events',lambda store:events)
    monkeypatch.setattr(module,'allocation_revision',lambda store:'fixture')
    monkeypatch.setattr(module,'allocation_ledger_revision',lambda store:'fixture')
    monkeypatch.setattr(module,'GovernedInputs',lambda *args:SimpleNamespace(rows=lambda *a:rows,used={}))
    fake=SimpleNamespace(list_proposals=lambda:[],strategy_approval_times=lambda:{},list_broker_order_records=lambda:[],
        list_fx_rates=lambda currency,**kw:[SimpleNamespace(rate_date=kw['start_date'],rate=D(1))])
    analytics=SimpleNamespace(latest=lambda key:dict(version='audited-fixture',provenance=json.dumps(dict(root='.'))))
    result=module.build_allocation_analytics(None,fake,analytics)
    assert [p['sleeves'][0]['pnl_cnh'] for p in result['periods']]==['10','5']
    assert all(p['complete'] for p in result['periods'])
    assert module.period_for(result['timeline'],'2026-10-02')['version']=='A'
    assert module.period_for(result['timeline'],'2026-10-05')['version']=='B'
    # An approval after the last marked session must not alter its PnL.
    future=TradeProposal(proposal_id='future',as_of=date(2026,10,5),sleeve=key,summary='Test',status='approved',
        reasoning=ProposalReasoning(summary='Test'),input_provenance=dict(allocation=dict(version='B',
            intent=dict(cash_transfers={key:'10'},fx={'USD':'1'},crosses=[]))))
    fake.list_proposals=lambda:[future]
    fake.strategy_approval_times=lambda:{'future':'2026-10-06T13:00:00+00:00'}
    result=module.build_allocation_analytics(None,fake,analytics)
    assert result['periods'][-1]['sleeves'][0]['pnl_cnh']=='5'


def test_missed_activation_never_backdates_or_changes_account(store,monkeypatch):
    from systematic_trading.live import strategy_control as module
    from systematic_trading.config import AppSettings
    state=control_state(store)
    change=AllocationChange(expected_revision=0,event_id='pending-event',operator='Me',reason='Test',
        allocations=[dict(strategy_key=state['sota_key'],weight='1')],effective_close='2026-10-02')
    store.commit_strategy_control(scope_for(store),0,dict(state,pending=dict(change=change.model_dump(mode='json'))),
        dict(event_id='pending-event',request_hash='pending'))
    before=control_state(store)
    result=module.activate_pending(AppSettings(),store,now=datetime(2026,10,5,15,tzinfo=UTC))
    assert 'missed' in result and control_state(store)==before


def test_schedule_requires_concrete_preview_token_and_does_not_activate(store,monkeypatch):
    from systematic_trading.live import strategy_control as module
    from systematic_trading.config import AppSettings
    state=control_state(store)
    change=AllocationChange(expected_revision=0,event_id='pending-event',operator='Me',reason='Reviewed evidence',
        allocations=[dict(strategy_key=state['sota_key'],weight='1')],effective_close='2026-10-02')
    preview=dict(membership_revision=0,review_token='reviewed',active=dict(version='new'),evidence={},rollback=state['active']['allocations'])
    monkeypatch.setattr(module,'preview_change',lambda *a,**k:preview)
    with pytest.raises(ValueError,match='Preview again'):
        module.schedule_change(AppSettings(),store,change,'stale',evidence_reviewed=True)
    assert control_state(store)['revision']==0
    saved=module.schedule_change(AppSettings(),store,change,'reviewed',evidence_reviewed=True)
    assert saved['active']==state['active'] and saved['pending']
    assert not store.list_proposals() and not store.list_broker_order_records()
    assert module.schedule_change(AppSettings(),store,change,'reviewed',evidence_reviewed=True)==saved


def test_reference_carries_positions_across_switch_instead_of_splicing_nav():
    from systematic_trading.portfolio.allocation_analytics import replay_reference
    opening=dict(snapshot=dict(positions=[dict(symbol='SPY',quantity=1)],cash=[dict(currency='USD',amount=100)]),targets=[])
    events=[dict(at='2026-10-01T21:00:00+00:00',effective_close='2026-10-01',active=dict(version='A',opening=opening)),
        dict(at='2026-10-02T21:00:00+00:00',effective_close='2026-10-02',active=dict(version='B',opening=dict(targets=[])))]
    rows={'SPY':{'2026-10-01':dict(raw_close=100,adjusted_close=100),'2026-10-02':dict(raw_close=110,adjusted_close=110),'2026-10-05':dict(raw_close=115,adjusted_close=115)}}
    fake=SimpleNamespace(list_fx_rates=lambda currency,**kwargs:[SimpleNamespace(rate_date=kwargs['start_date'],rate=D(1))])
    points=replay_reference(events,[],{},list(rows['SPY']),rows,fake)
    assert D(points[0]['nav_cnh'])==200
    assert D(points[1]['nav_cnh'])>209
    assert D(points[2]['nav_cnh'])<210  # Already liquidated under A; no fictional second asset gain.
    assert points[-1]['version']=='B'


def test_control_ui_has_review_gate_and_asset_names():
    from systematic_trading.web.strategy_control_ui import with_strategy_controls
    from systematic_trading.web.operator import strategy_portal
    html=strategy_portal().body.decode()
    assert 'Promote / allocate' in html and 'sc-reviewed' in html
    assert 'AssetNames.name' in html and 'review_token' in html
    assert "call('/schedule'" in html


def test_editing_configuration_requires_a_fresh_preview_even_after_rechecking_approval():
    import subprocess
    import shutil
    from pathlib import Path
    from systematic_trading.web.strategy_control_ui import JS
    node=shutil.which('node')
    if not node:
        pytest.skip('Node is required for approval-form behavior checks.')
    subprocess.run([node,str(Path(__file__).with_name('strategy_control_ui_checks.cjs'))],
        input=JS,text=True,encoding='utf8',capture_output=True,check=True,timeout=20)


def test_delayed_partial_fill_replay_uses_execution_time_and_deduplicates():
    from systematic_trading.portfolio.strategy_book import replay_book
    opening=dict(at='2026-10-01T21:00:00+00:00',book=initial_book(
        dict(positions=[],cash=[dict(currency='USD',amount=1000)]),
        [dict(strategy_key='A',weight='.6'),dict(strategy_key='B',weight='.4')]))
    intent=dict(cash_transfers={},crosses=[],demands={'SPY':{'A':'6','B':'4'}})
    proposal=TradeProposal(proposal_id='rebalance',as_of=date(2026,10,1),sleeve='combined',summary='Test',
        status='approved',reasoning=ProposalReasoning(summary='Test'),
        input_provenance=dict(allocation=dict(version='v1',intent=intent)))
    early=BrokerExecutionFill(execution_id='one',symbol='SPY',side='buy',quantity=3,
        average_price=D(10),currency='USD',filled_at=datetime(2026,10,2,14,tzinfo=UTC))
    late=early.model_copy(update=dict(execution_id='two',quantity=7,average_price=D(11),filled_at=datetime(2026,10,5,14,tzinfo=UTC)))
    record=SimpleNamespace(proposal_id='rebalance',local_order_id='order',filled_quantity=10,
        execution_fills=[late,early,early],order=SimpleNamespace(reference_price=D(10)))
    fake=SimpleNamespace(list_proposals=lambda:[proposal],strategy_approval_times=lambda:{'rebalance':'2026-10-02T13:30:00+00:00'},
        list_broker_order_records=lambda:[record])
    active=dict(version='v1',opening=opening)
    partial,warnings=replay_book(fake,active,through=datetime(2026,10,2,22,tzinfo=UTC))
    assert not warnings and D(partial['A']['positions']['SPY'])==D('1.8')
    final,warnings=replay_book(fake,active)
    assert D(final['A']['positions']['SPY'])==6 and D(final['B']['positions']['SPY'])==4
    assert sum(D(v['cash']['USD']) for v in final.values())==893
    reference,_=replay_book(fake,active,reference=True)
    assert sum(D(v['cash']['USD']) for v in reference.values())==900


@pytest.mark.parametrize('activation_day', [2, 5])
def test_activation_is_atomic_blocks_uncertainty_and_invalidates_old_policy(store,tmp_path,monkeypatch,activation_day):
    from systematic_trading.live import strategy_control as module
    from systematic_trading.live import allocated_plan
    from systematic_trading.live.auto_approval import PaperAutoApproval
    from systematic_trading.live.sota import LiveAccountSnapshotInput
    from systematic_trading.config import AppSettings
    from systematic_trading.execution import management
    settings=AppSettings(data_dir=tmp_path,database_path=store.database_path)
    state=control_state(store)
    change=AllocationChange(expected_revision=0,event_id='pending-event',operator='Me',reason='Test',
        allocations=[dict(strategy_key=state['sota_key'],weight='1')],effective_close='2026-10-02')
    active=dict(version=change.event_id,key='allocation-'+change.event_id,
        allocations=[r.model_dump(mode='json') for r in change.allocations],effective_close='2026-10-02')
    pending=dict(change=change.model_dump(mode='json'),approved_at='2026-10-02T19:00:00+00:00',
        preview=dict(active=active,evidence={}))
    store.commit_strategy_control(scope_for(store),0,dict(state,pending=pending),dict(event_id='pending-event',request_hash='pending'))
    policy=PaperAutoApproval(settings,store)
    policy.policy=policy.policy.model_copy(update=dict(enabled=True,strategy_key=state['active']['key'],binding=policy._binding()))
    now=datetime(2026,10,activation_day,21,tzinfo=UTC)
    monkeypatch.setattr(module,'activation_issues',lambda *args:['Open order'])
    assert module.activate_pending(settings,store,now=now)=='Open order'
    assert control_state(store)['active']==state['active']
    monkeypatch.setattr(module,'activation_issues',lambda *args:[])
    monkeypatch.setattr(management,'sync_orders',lambda *args,**kwargs:pytest.fail('Allocation preparation must not contact IB'))
    snapshot=LiveAccountSnapshotInput(as_of=now.date(),captured_at=now,cash=[dict(currency='USD',amount=1000)])
    monkeypatch.setattr(module,'snapshot_for',lambda *args:snapshot)
    monkeypatch.setattr(module,'load_latest_ib_reconciliation',lambda *args:SimpleNamespace(
        managed_accounts=['DU123'],checked_at=now,broker_positions=[],broker_cash=[dict(currency='USD',amount='1000')]))
    proposal=TradeProposal(as_of=now.date(),sleeve=active['key'],summary='Test',reasoning=ProposalReasoning(summary='Test'),
        input_provenance=dict(allocation=dict(intent=dict(prices={'SPY':'100'},fx={'USD':'1'}))))
    monkeypatch.setattr(allocated_plan,'build_allocated_plan',lambda **kwargs:SimpleNamespace(proposal=proposal,validation_issues=[]))
    assert 'activated' in module.activate_pending(settings,store,now=now)
    changed=control_state(store)
    assert changed['revision']==2 and changed['pending'] is None
    assert changed['active']['version']==change.event_id
    assert changed['active']['effective_close'] == str(now.date())
    assert changed['active']['requested_effective_close'] == '2026-10-02'
    assert len(store.list_proposals()) == 1 and not store.list_broker_order_records()
    assert store.list_proposals()[0].status.value == 'pending'
    policy.tick(now=now)
    assert policy.policy.enabled is False
    assert module.activate_pending(settings,store,now=now) is None
    # Simulate a queue-write interruption after the atomic configuration commit.
    # The persisted outbox copy restores exactly one pending proposal.
    with store._connect() as connection:
        connection.execute('DELETE FROM proposals')
    assert 'restored' in module.activate_pending(settings,store,now=now)
    assert len(store.list_proposals()) == 1
    assert module.activate_pending(settings,store,now=now) is None


def test_unknown_legacy_account_is_pinned_without_reset_and_cannot_change(store, monkeypatch):
    from systematic_trading.live.strategy_control import account_binding_issues
    from systematic_trading.portfolio.context import PortfolioContext
    import systematic_trading.portfolio.strategy_allocation as module
    context=PortfolioContext(episode_id='opening-episode')
    monkeypatch.setattr(module,'portfolio_context',lambda store:context)
    scope=scope_for(store)
    assert account_binding_issues(store,'DU123')==[]
    state=control_state(store)
    store.commit_strategy_control(scope,0,dict(state,pending=dict(account_id='DU123')),
        dict(event_id='account-bind',request_hash='account-bind'))
    assert account_binding_issues(store,'DU123')==[]
    assert account_binding_issues(store,'DU999')
    context.account_id='DU123'
    assert scope_for(store)==scope and control_state(store)['revision']==1
    assert store.latest_pnl_baseline() is None


def test_historical_execution_account_mismatch_blocks_even_unassigned_context(store, monkeypatch):
    from systematic_trading.live.strategy_control import account_binding_issues
    from systematic_trading.domain.enums import OrderEnvironment
    fill=BrokerExecutionFill(account='DU123',symbol='SPY',side='buy',quantity=1,average_price=D(100))
    monkeypatch.setattr(store,'list_broker_order_records',lambda:[SimpleNamespace(environment=OrderEnvironment.PAPER,execution_fills=[fill])])
    assert account_binding_issues(store,'DU123')==[]
    assert account_binding_issues(store,'DU999')


def test_late_fill_and_approval_invalidate_attribution_without_new_account_snapshot(store,monkeypatch):
    from systematic_trading.portfolio.allocation_analytics import allocation_ledger_revision
    commit(store,0,'A')
    proposal=TradeProposal(proposal_id='approved',as_of=date(2026,10,2),sleeve='A',summary='Test',
        status='approved',reasoning=ProposalReasoning(summary='Test'),input_provenance=dict(allocation=dict(version='A-0')))
    proposals=[]
    records=[]
    monkeypatch.setattr(store,'list_proposals',lambda:proposals)
    monkeypatch.setattr(store,'list_broker_order_records',lambda:records)
    before=allocation_ledger_revision(store)
    proposals.append(proposal)
    approved=allocation_ledger_revision(store)
    assert before!=approved
    records.append(SimpleNamespace(local_order_id='fill-order',proposal_id='approved',filled_quantity=1,
        average_fill_price=D(100),execution_sync_issue=None,order=SimpleNamespace(reference_price=D(99)),
        execution_fills=[BrokerExecutionFill(symbol='SPY',side='buy',quantity=1,average_price=D(100))]))
    assert allocation_ledger_revision(store)!=approved


def test_unclassified_withdrawal_funds_zero_reserve_without_resetting_strategy_weights():
    book={'A':dict(positions={},cash={'USD':'600'}),'B':dict(positions={},cash={'USD':'400'}),
        RESERVE:dict(positions={},cash={'USD':'-10'})}
    intent=rebalance_intent(book,{'A':{},'B':{}},{'A':D('.5'),'B':D('.5'),RESERVE:D(0)}, {},{'USD':D(1)})
    assert intent['capital_reset'] is False
    assert intent['cash_transfers']=={RESERVE:'10','A':'-6','B':'-4'}
    apply_internal(book,intent)
    assert book_value(book['A'],{}, {'USD':D(1)})==594
    assert book_value(book['B'],{}, {'USD':D(1)})==396
    assert sum(book_value(b,{}, {'USD':D(1)}) for b in book.values())==990
