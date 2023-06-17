import traceback
def router_wrapper(func):
    def wrap(*args, **kwargs):
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            return str(traceback.format_exc())

    wrap.__name__ = func.__name__
    return wrap

