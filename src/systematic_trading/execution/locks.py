from functools import wraps
from inspect import signature
from threading import RLock

ORDER_CONNECTION_LOCK = RLock()

def serialized_orders(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with ORDER_CONNECTION_LOCK:
            return function(*args, **kwargs)
    wrapped.__signature__ = signature(function, eval_str=True)
    return wrapped
