import uuid
import functools
from requestshook.utils import (
    write_syslog,
    get_current_service,
    get_service_from_url,
    add_request_id,
    add_request_from,
)

# get Requests.PreparedRequest from args, kwargs if exists
def get_prepared_request(*args, **kwargs):
    is_prepared_request = lambda p : 'PreparedRequest' in str(type(p))

    for arg in args:
        if is_prepared_request(arg): return arg

    for k, v in kwargs.items():
        if is_prepared_request(v): return v

    return None

# register hook
def register_hook(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):
        try:
            req = get_prepared_request(*args, **kwargs)
            if req and hasattr(req, 'headers'):
                add_request_id(req.headers, uuid.uuid4().hex)
                add_request_from(req.headers, get_current_service() or 'unknown')
        except Exception as e:
            write_syslog(e)

        # call requests.HttpAdapter.send()
        return f(*args, **kwargs)
    return inner

