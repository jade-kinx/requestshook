import configparser
import uuid
import functools
from requestshook.utils import (
    CONF_FILE_PATH,
    write_syslog,
    get_current_service,
    add_request_id,
    add_request_from,
)

# get Requests.PreparedRequest from args, kwargs if exists
def get_prepared_request(*args, **kwargs):
    # is_prepared_request = lambda p : 'PreparedRequest' in str(type(p))
    from requests.models import PreparedRequest
    is_prepared_request = lambda p : isinstance(p, PreparedRequest)

    for arg in args:
        if is_prepared_request(arg): return arg

    for k, v in kwargs.items():
        if is_prepared_request(v): return v

    return None

# hook on requests.adapters.HttpAdapter.send() : adding request-id, request-from to header
def requestshook(f):
    @functools.wraps(f)
    def inner(*args, **kwargs):

        # requestshook enabled?
        cfg = configparser.ConfigParser()
        cfg.read(CONF_FILE_PATH)
        enabled = cfg.getboolean('DEFAULT', 'enabled', fallback=False)
        if enabled:
            # add request-id, request-from to header
            try:
                req = get_prepared_request(*args, **kwargs)
                if req and hasattr(req, 'headers'):
                    add_request_id(req.headers, uuid.uuid4().hex)
                    add_request_from(req.headers, get_current_service() or 'unknown')
            except Exception as e:
                write_syslog(e)

        # call requests.adapters.HttpAdapter.send()
        return f(*args, **kwargs)
    return inner

