import traceback
from functools import wraps


def router_wrapper(func):
    # @wraps keeps func.__name__, which Flask uses as the endpoint name
    @wraps(func)
    def wrap(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception:
            # non-200 so the frontend's error branch actually fires
            return {"result": False, "message": traceback.format_exc()}, 500
    return wrap
