import json
from datetime import UTC, datetime
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import pytest

from systematic_trading.config import AppSettings
from systematic_trading.execution.registry import ExecutionRegistry, publish_registry
from systematic_trading.research import instruments_for_definition, union_instruments
from systematic_trading.research.strategy_catalog import fr25_definition, current_sota_definition


def entries_for(instruments):
    entries = {}
    for n, (symbol, instrument) in enumerate(instruments.items(), 1):
        fund = dict(symbol=symbol, isin='US0000000001', currency='USD', primary_exchange='ARCA')
        details = dict(contract=dict(symbol=symbol, conId=n, secType='STK', currency='USD',
            primaryExchange='ARCA', localSymbol=symbol, tradingClass=symbol),
            minSize='1', sizeIncrement='1', minTick='0.01', orderTypes='MKT,LMT', validExchanges='SMART,ARCA',
            timeZoneId='US/Eastern',stockType='ETF')
        entries[symbol] = dict(state='admitted', fund=fund, instrument=instrument.model_dump(mode='json'),
            identity=dict(status='identity_verified', lookup=dict(secIdType='ISIN', secId=fund['isin']), details=details),
            calendar='XNYS', lot_size=1, price_inputs=dict(batch='checked', files={'audit':'hash'}),
            permission=dict(kind='ib_paper_what_if',what_if=True, account='DU123',con_id=n,errors=[],
                captured_at=datetime.now(UTC).isoformat(),
                state=dict(status='PreSubmitted',initMarginAfter='100',maintMarginAfter='100',warningText='')))
    return entries


def test_registry_union_is_complete_and_capability_is_separate_from_allocation(tmp_path):
    from systematic_trading.portfolio.strategy_allocation import allocation_contract_issue
    definitions = [current_sota_definition(), fr25_definition()]
    instruments = union_instruments(definitions)
    assert len(instruments) == 14
    settings = AppSettings(data_dir=tmp_path)
    assert allocation_contract_issue(definitions[1],settings)
    version = publish_registry(settings,entries_for(instruments),account='DU123',reason='Test proof')
    registry = ExecutionRegistry(settings)
    assert registry.receipt(instruments)['version'] == version
    assert allocation_contract_issue(definitions[1],settings) is None
    with pytest.raises(ValueError,match='different account'):
        registry.resolve(instruments,account='DU456')
    changed = dict(instruments)
    changed['XLE'] = changed['XLE'].model_copy(update={'country':'different'})
    with pytest.raises(ValueError,match='disagreement'):
        registry.resolve(changed)
    frozen = replace(definitions[0], universe_key='frozen-test',
        universe_members=tuple(i.model_dump(mode='json') for i in instruments.values()))
    assert instruments_for_definition(frozen) == instruments
    unsupported = replace(frozen, universe_members=())
    with pytest.raises(ValueError,match='Unregistered'):
        instruments_for_definition(unsupported)


def test_registry_rejects_changed_evidence_and_unsupported_market_rules(tmp_path):
    settings = AppSettings(data_dir=tmp_path)
    instruments = instruments_for_definition(fr25_definition())
    entries = entries_for(instruments)
    for path, value in [(('permission','what_if'),False), (('permission','con_id'),999),
                        (('identity','details','sizeIncrement'),'100')]:
        invalid = deepcopy(entries)
        current = invalid['XLB']
        for part in path[:-1]:current = current[part]
        current[path[-1]] = value
        with pytest.raises(ValueError):publish_registry(settings,invalid,account='DU123',reason='Test')
    version = publish_registry(settings,entries,account='DU123',reason='Test')
    path = tmp_path/'execution_registry'/(version+'.json')
    path.write_text('{}')
    with pytest.raises(ValueError,match='hash mismatch'):ExecutionRegistry(settings)


def test_router_resolves_active_allocation_and_pins_contract_ids(tmp_path,monkeypatch):
    from systematic_trading.execution import broker, reconciliation
    from systematic_trading.portfolio import strategy_allocation
    instruments = instruments_for_definition(fr25_definition())
    settings = AppSettings(data_dir=tmp_path)
    publish_registry(settings,entries_for(instruments),account='DU123',reason='Test')
    monkeypatch.setattr(strategy_allocation,'trading_definition',lambda _:fr25_definition())
    monkeypatch.setattr(reconciliation,'load_latest_ib_reconciliation',lambda _:SimpleNamespace(managed_accounts=['DU123']))
    router = broker.InteractiveBrokersOrderRouter(settings)
    receipt = ExecutionRegistry(settings).receipt(instruments)
    proposal = SimpleNamespace(input_provenance=dict(execution_registry=receipt))
    contracts = router._proposal_contracts(None,proposal)
    assert set(contracts) == set(instruments)
    assert broker._to_ib_contract(contracts['XLE']).conId == receipt['contracts']['XLE']
    assert router.contract_spec_for('XLE').con_id == receipt['contracts']['XLE']
    proposal.input_provenance = {}
    with pytest.raises(ValueError,match='lacks execution registry'):router._proposal_contracts(None,proposal)
    proposal.input_provenance = dict(execution_registry=dict(receipt,version='stale'))
    with pytest.raises(ValueError,match='admission changed'):router._proposal_contracts(None,proposal)
    pointer = tmp_path/'execution_registry/current.json'
    pointer.write_text(json.dumps(dict(version='../escape')))
    with pytest.raises(ValueError,match='Invalid execution'):ExecutionRegistry(settings)


def test_deleted_registry_never_downgrades_an_already_bound_legacy_proposal(tmp_path,monkeypatch):
    from systematic_trading.execution.broker import InteractiveBrokersOrderRouter
    from systematic_trading.portfolio import strategy_allocation
    monkeypatch.setattr(strategy_allocation,'trading_definition',lambda _:current_sota_definition())
    proposal = SimpleNamespace(input_provenance=dict(execution_registry=dict(version='old')))
    with pytest.raises(ValueError,match='registry is missing'):
        InteractiveBrokersOrderRouter(AppSettings(data_dir=tmp_path))._proposal_contracts(None,proposal)
