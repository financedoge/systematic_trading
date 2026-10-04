from copy import deepcopy
from datetime import date
from decimal import Decimal
from types import SimpleNamespace
import json

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.domain.enums import Currency
from systematic_trading.domain.portfolio import CashBalance
from systematic_trading.domain.market import FXRate
from systematic_trading.execution.broker import InteractiveBrokersAdapter
from systematic_trading.live.sota import LiveAccountSnapshotInput, build_sota_live_rebalance_plan
from systematic_trading.live import strategy_models
from systematic_trading.lean.strategy import targets_for_day
from systematic_trading.research.strategy_catalog import rolling_xgboost_1y_definition, usd_strategy_definition
from systematic_trading.storage.sqlite import SQLiteStore
from test_rolling_tracking import model_record
from test_usd_promotion import panel


def test_rolling_usd_live_targets_exactly_match_monitored_service(tmp_path,monkeypatch):
    histories,usd=panel()
    definition=usd_strategy_definition(rolling_xgboost_1y_definition())
    schedule={'2024-10-31':model_record()}
    monkeypatch.setattr(strategy_models,'published_rolling_schedule',lambda *args:(schedule,{'receipt':'verified-test'}))
    from systematic_trading.research import usd_tracking
    monkeypatch.setattr(usd_tracking,'published_live_schedule',lambda *args:(usd,{'receipt':'verified-test'}))
    store=SQLiteStore(tmp_path/'test.db');store.initialize()
    for symbol,rows in histories.items():
        for row in rows:
            store.upsert_price_bar(symbol,row)
    store.upsert_fx_rate(FXRate(rate_date=date(2024,10,31),base_currency=Currency.USD,rate=Decimal(7)))
    settings=AppSettings(data_dir=tmp_path,database_path=store.database_path)
    snapshot=LiveAccountSnapshotInput(as_of=date(2024,10,31),cash=[CashBalance(currency=Currency.USD,amount=100000)])
    plan=build_sota_live_rebalance_plan(store=store,broker=InteractiveBrokersAdapter(settings),
        account_snapshot=snapshot,decision_date=date(2024,10,31),definition=definition)
    expected=targets_for_day({s:[r.model_dump(mode='json') for r in rows] for s,rows in histories.items()},
        date(2024,11,1),definition=definition,base_tree_models=schedule,usd_models=usd)
    assert plan.proposal.targets == expected
    assert plan.proposal.input_provenance['rolling_model']['receipt']=='verified-test'
    assert not store.list_proposals()
    schedule.clear()
    with pytest.raises(ValueError,match='Missing monthly'):
        build_sota_live_rebalance_plan(store=store,broker=InteractiveBrokersAdapter(settings),
            account_snapshot=snapshot,decision_date=date(2024,10,31),definition=definition)


def test_rolling_execution_rejects_changed_receipt_and_wrong_data_batch(tmp_path,monkeypatch):
    from systematic_trading.market_data.analytics_store import digest,encode
    definition=usd_strategy_definition(rolling_xgboost_1y_definition())
    schedule={'2024-10-31':model_record()}
    attempt=tmp_path/'tracked_models'/'revision'/'attempts'/'one'
    receipt=dict(artifact_path=str(attempt),files={'schedule.json':'verified'})
    report=dict(strategyDefinition=definition.to_dict(),modelTraining=dict(receipt=receipt,
        fitAsOf='2024-10-31',modelSha256=digest(encode(schedule['2024-10-31']['model']))))
    document=[dict(payload=json.dumps(report)),dict(version='calculation',provenance=json.dumps(dict(inputs=dict(batch='audited'))))]
    monkeypatch.setattr(strategy_models.AnalyticsStore,'from_settings',lambda _:SimpleNamespace(document=lambda *args:document))
    monkeypatch.setattr(strategy_models,'read_model_artifacts',lambda root:(schedule,receipt))
    settings=AppSettings(data_dir=tmp_path)
    assert strategy_models.published_rolling_schedule(settings,definition,'audited')[0]==schedule
    with pytest.raises(ValueError,match='differ'):
        strategy_models.published_rolling_schedule(settings,definition,'other')
    changed=deepcopy(receipt);changed['files']['schedule.json']='changed'
    monkeypatch.setattr(strategy_models,'read_model_artifacts',lambda root:(schedule,changed))
    with pytest.raises(ValueError,match='differs'):
        strategy_models.published_rolling_schedule(settings,definition,'audited')


def test_new_drift_proposal_does_not_repeat_previous_capital_transfer(tmp_path,monkeypatch):
    from systematic_trading.live import allocated_plan, sota
    from systematic_trading.portfolio import decision_inputs
    from systematic_trading.domain.execution import TradeProposal,ProposalReasoning
    from systematic_trading.domain.portfolio import AllocationTarget
    from systematic_trading.research.strategy_catalog import current_sota_definition,etf_activity_lag20_definition
    from systematic_trading.research import instruments_for_definition
    from systematic_trading.portfolio.strategy_book import initial_book
    from systematic_trading.portfolio.strategy_allocation import control_state,scope_for
    store=SQLiteStore(tmp_path/'new-intent.db');store.initialize()
    keys=[current_sota_definition().key,usd_strategy_definition(etf_activity_lag20_definition()).key]
    rows=[dict(strategy_key=keys[0],weight='.6'),dict(strategy_key=keys[1],weight='.4')]
    snapshot=LiveAccountSnapshotInput(as_of=date(2026,10,2),positions=[dict(symbol='SPY',quantity=10)],
        cash=[dict(currency='USD',amount=1000)])
    book=initial_book(snapshot.model_dump(mode='json'),rows)
    active=dict(version='v1',key='allocation-v1',allocations=rows,effective_close='2026-09-30',opening={'book':book})
    store.commit_strategy_control(scope_for(store),0,dict(control_state(store),active=active),dict(event_id='fixture',request_hash='fixture'))
    targets={keys[0]:[AllocationTarget(symbol='SPY',target_weight=Decimal('.3'),sleeve=keys[0],rationale='monthly')],
        keys[1]:[AllocationTarget(symbol='SPY',target_weight=Decimal('.2'),sleeve=keys[1],rationale='monthly')]}
    prior=TradeProposal(as_of=date(2026,9,30),target_as_of=date(2026,9,30),sleeve='allocation-v1',summary='prior',
        reasoning=ProposalReasoning(summary='prior'),status='approved',input_provenance=dict(allocation=dict(version='v1',
            components={k:dict(targets=[t.model_dump(mode='json') for t in v]) for k,v in targets.items()},
            intent={'cash_transfers':{keys[0]:'100',keys[1]:'-100'}})))
    store.save_proposal(prior)
    monkeypatch.setattr(allocated_plan,'replay_book',lambda *args,**kwargs:(book,[]))
    symbols=instruments_for_definition(current_sota_definition())
    monkeypatch.setattr(decision_inputs,'decision_inputs',lambda *args:({},
        {s:dict(close='100',trade_date='2026-10-02') for s in symbols},{}))
    monkeypatch.setattr(sota,'_latest_fx_to_cnh',lambda **kwargs:{Currency.USD:Decimal(1),Currency.CNH:Decimal(1)})
    def build(**kwargs):
        if kwargs.get('explicit_targets') is not None:
            proposal=prior.model_copy(update=dict(status='pending',targets=kwargs['explicit_targets'],
                input_provenance=dict(allocation=kwargs['allocation_receipt'])))
        else:
            proposal=prior.model_copy(update=dict(targets=targets[kwargs['definition'].key],input_provenance={'batch':'verified'}))
        return SimpleNamespace(proposal=proposal,validation_issues=[])
    monkeypatch.setattr(sota,'build_sota_live_rebalance_plan',build)
    plan=allocated_plan.build_allocated_plan(store=store,broker=SimpleNamespace(settings=AppSettings()),
        account_snapshot=snapshot,decision_date=date(2026,10,2),intended_trade_date=date(2026,10,5),
        environment='paper',order_type='twap',target_decision_date=date(2026,9,30),target_proposal=prior)
    assert not plan.proposal.input_provenance['allocation']['intent']['capital_reset']
    assert plan.proposal.input_provenance['allocation']['intent']['cash_transfers']=={}
    assert plan.proposal.targets[0].target_weight==Decimal('.26')
