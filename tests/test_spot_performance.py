from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal as D

import pytest

from systematic_trading.live.broker_pnl import BrokerPnlSnapshot, PositionPnl
from systematic_trading.research.spot_performance import mark_spot_performance


NOW = datetime(2026, 10, 5, 14, 0, tzinfo=UTC)


def inputs():
    broker = BrokerPnlSnapshot(account='DU1', currency='HKD', status='live', connected=True, received_at=NOW,
        positions=[PositionPnl(contract_id=1, security_type='STK', symbol='SPY', currency='USD', quantity=10,
            market_value=1100, daily_pnl=999, received_at=NOW, stale=False)])
    payload = dict(spot_basis=dict(id='pinned', close_date='2026-10-02', session='2026-10-05',
        closes={'SPY':'100'}, fx={'USD':'7','CNH':'1'}, base_nav_cnh='10000', account_base_nav_cnh='10000',
        epoch=dict(version='new',label='New'), last_strategy=dict(nav_cnh='9000'),
        period=dict(start='2026-10-02', theoretical_return='0',actual_start_nav_cnh='9500'),
        components=[dict(weight='0.8',holdings={'SPY':'0.75','Cash':'0.25'},next_rebalance='2026-11-02')],
        account=dict(account_id='DU1',captured_at=NOW.isoformat(),cash=[dict(currency='CNH',amount='3000')],
                     positions=[dict(symbol='SPY',quantity=10,currency='USD')]), warnings=[]))
    return broker, payload


def test_spot_uses_held_weights_and_price_return_not_pnl_over_value():
    broker, payload = inputs()
    original = deepcopy(payload)
    result = mark_spot_performance(broker, payload, now=NOW)
    assert result.positions[0].daily_return == D('.1')
    assert result.positions[0].market_price == 110
    spot = result.performance
    assert D(spot['strategy']['nav_cnh']) == 9540  # 9000 * (1 + .8*.75*.1)
    assert D(spot['strategy']['index']) == D('95.4')  # retain prior strategy's loss
    assert D(spot['actual_rebased']['nav_cnh']) == 10070
    assert D(spot['actual_rebased']['index']) == D('95.4')
    assert D(spot['account']['nav_cnh']) == 10700
    assert payload == original


@pytest.mark.parametrize('change', ['stale','disconnected','missing','currency','security','duplicate','rebalance','old_close','closed'])
def test_unverified_or_outdated_marks_never_extend_theory(change):
    broker, payload = inputs()
    now = NOW
    if change == 'stale': broker.positions[0].stale = True
    if change == 'disconnected': broker.connected = False
    if change == 'missing': broker.positions[0].market_value = None
    if change == 'currency': broker.positions[0].currency = 'HKD'
    if change == 'security': broker.positions[0].security_type = 'OPT'
    if change == 'duplicate': broker.positions.append(broker.positions[0].model_copy())
    if change == 'rebalance': payload['spot_basis']['components'][0]['next_rebalance'] = '2026-10-05'
    if change == 'old_close': payload['spot_basis']['session'] = '2026-10-02'
    if change == 'closed': now = NOW.replace(hour=21)
    result = mark_spot_performance(broker, payload, now=now)
    assert result.performance['strategy'] is None
    assert result.performance['warnings']


@pytest.mark.parametrize('change', ['quantity','cash_age','identity','extra_holding'])
def test_account_requires_same_holdings_recent_cash_and_account(change):
    broker, payload = inputs()
    if change == 'quantity': payload['spot_basis']['account']['positions'][0]['quantity'] = 9
    if change == 'cash_age': payload['spot_basis']['account']['captured_at'] = '2026-10-05T13:00:00Z'
    if change == 'identity': broker.account = 'DU2'
    if change == 'extra_holding': broker.positions.append(PositionPnl(contract_id=2,symbol='ABC',currency='USD',quantity=1))
    result = mark_spot_performance(broker, payload, now=NOW)
    assert result.performance['account'] is None
    assert result.performance['strategy'] is not None


def test_missing_cached_publication_leaves_broker_pnl_available():
    broker, _ = inputs()
    result = mark_spot_performance(broker, None, now=NOW)
    assert result.status == 'live' and result.positions[0].daily_pnl == 999
    assert result.performance['strategy'] is None


@pytest.mark.parametrize('kind,minute,currency,accepted', [
    ('broker_live',1,'CNH',True), ('legacy',1,'CNH',False),
    ('broker_live',-20,'CNH',False), ('broker_live',10,'CNH',False),
    ('broker_live',1,'EUR',False)])
def test_current_cash_refresh_is_independent_of_history_and_rejects_invalid_captures(tmp_path,kind,minute,currency,accepted):
    import json
    from datetime import timedelta
    from systematic_trading.config import AppSettings
    from systematic_trading.research.spot_performance import refresh_spot_cash
    _, payload = inputs()
    original = deepcopy(payload)
    root = tmp_path/'live/account_snapshots'
    root.mkdir(parents=True)
    snapshot = dict(observation_kind=kind, as_of='2026-10-05',captured_at=(NOW+timedelta(minutes=minute)).isoformat(),
        cash=[dict(currency=currency,amount='3500')],positions=[dict(symbol='SPY',quantity=10,currency='USD')])
    (root/'ib_paper_account_snapshot_20261005_220100.json').write_text(json.dumps(snapshot))
    updated = refresh_spot_cash(AppSettings(data_dir=tmp_path),payload,now=NOW+timedelta(minutes=2))
    assert payload == original
    assert updated['spot_basis']['id'] == 'pinned'
    assert (updated['spot_basis']['account']['cash'][0]['amount'] == '3500') == accepted
    if accepted:
        assert len(updated['spot_basis']['account']['document_sha256']) == 64
        assert updated['spot_basis']['account']['account_id'] == 'DU1'
