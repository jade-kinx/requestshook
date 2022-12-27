import uuid
import functools
from requestshook._utils import (
    write_error,
    get_current_service,
    get_service_from_url
)

# get Requests.PreparedRequest from args, kwargs if exists
def get_prepared_request(*args, **kwargs):
    is_prepared_request = lambda p : 'PreparedRequest' in str(type(p))

    for arg in args:
        if is_prepared_request(arg): return arg

    for k, v in kwargs.items():
        if is_prepared_request(v): return v

    return None


def inject_service_name(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        try:
            req = get_prepared_request(*args, **kwargs)
            if req and hasattr(req, 'headers'):
                req.headers['x-requestshook-request-id'] = uuid.uuid4().hex
                req.headers['x-requestshook-request-from'] = get_current_service()
                req.headers['x-requestshook-request-to'] = get_service_from_url(req.url)
        except Exception as e:
            write_error(__name__, e)

        # call requests.HttpAdapter.send()
        return f(*args, **kwargs)
    return inner

