"""Compatibility at the IB SDK boundary; broker decisions remain unchanged."""
from functools import wraps
from inspect import signature


def compatible_ib_errors(callback):
    """Accept legacy errors and current errors with the added errorTime argument."""
    @wraps(callback)
    def receive(self, reqId, *args, **kwargs):
        kwargs.pop("errorTime", None)
        if len(args) >= 3 and isinstance(args[1], int):
            args = args[1:]
        return callback(self, reqId, *args, **kwargs)
    return receive


def cancel_ib_order(client, order_id):
    if "orderCancel" in signature(client.cancelOrder).parameters:
        from ibapi.order_cancel import OrderCancel
        client.cancelOrder(order_id, OrderCancel())
    else:
        client.cancelOrder(order_id)
