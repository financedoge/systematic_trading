from types import SimpleNamespace

import pytest

from systematic_trading.execution.broker import IbApiOrderClient


@pytest.mark.parametrize('acknowledgement', ['open', 'status', 'none', 'error'])
def test_algo_date_warning_requires_real_order_acknowledgement(monkeypatch, acknowledgement):
    import systematic_trading.execution.broker as broker

    client = pytest.importorskip('ibapi.client').EClient
    monkeypatch.setattr(client, 'connect', lambda app, *args: app.nextValidId(1))
    monkeypatch.setattr(client, 'run', lambda app: None)
    monkeypatch.setattr(client, 'disconnect', lambda app: None)
    monkeypatch.setattr(broker, '_to_ib_contract', lambda value: value)
    monkeypatch.setattr(broker, '_to_ib_order', lambda value: value)

    def submit(app, order_id, contract, order):
        app.error(order_id, 2111, 'Algorithm time adjusted to next trading date')
        assert not app.order_events[order_id].is_set()
        if acknowledgement == 'open':
            app.openOrder(order_id, contract, order, SimpleNamespace())
        elif acknowledgement == 'status':
            app.orderStatus(order_id, 'PreSubmitted', 0, 1, 0, 1, 0, 0, 101, '')
        elif acknowledgement == 'error':
            app.error(order_id, 201, 'Order rejected')

    monkeypatch.setattr(client, 'placeOrder', submit)
    adapter = IbApiOrderClient(order_ack_timeout_seconds=0.01)
    adapter.connect(SimpleNamespace(host='test', port=0, client_id=101))
    try:
        if acknowledgement == 'none':
            with pytest.raises(TimeoutError, match='2111'):
                adapter.place_order(1, object(), object())
        elif acknowledgement == 'error':
            with pytest.raises(RuntimeError, match='201:Order rejected'):
                adapter.place_order(1, object(), object())
        else:
            adapter.place_order(1, object(), object())
        assert adapter.warnings_for_order(1) == ['1:2111:Algorithm time adjusted to next trading date']
    finally:
        adapter.disconnect()
