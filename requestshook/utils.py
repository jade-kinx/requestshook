import json
import os
import psutil

from pathlib import Path
from urllib3.util import parse_url

try:
    import syslog
except:
    syslog = None

# requestshook header parameters
X_REQUESTSHOOK_REQUEST_ID = 'X-Requestshook-Request-Id'
X_REQUESTSHOOK_REQUEST_FROM = 'X-Requestshook-Request-From'

PACKAGE_NAME = __package__ or 'requestshook'

# write message to syslog
def write_syslog(*messages):
    if messages:
        if syslog:
            syslog.syslog(f'{PACKAGE_NAME}: {" ".join(messages)}')
        else:
            print(' '.join(messages))

# write text to file
def write_text(file, *messages):
    if messages:
        # create permission all file if not exists
        if not os.path.exists(file):
            mask = os.umask(0)
            Path(file).touch(mode=0o666, exist_ok=True)
            os.umask(mask)

        # write messages to file
        with open(file, 'a') as f:
            f.write('{0}\n'.format(' '.join(messages)))

# beautify json string
def beautify_json(body, indent=2):
    try:
        # string
        if isinstance(body, str): return json.dumps(json.loads(body), indent=indent)

        # bytes
        if isinstance(body, bytes): return json.dumps(json.loads(body.decode()), indent=indent)

        # object
        return json.dumps(body, indent=indent)
    except Exception as e:
        write_syslog(repr(e))
        return None

# format headers( headers should be dictionary type )
def format_header(headers):
    try:
        return '\n'.join(f'{k}: {v}' for k, v in headers.items())
    except:
        return repr(headers)


# format request/response body
def format_body(req_or_resp):
    body = req_or_resp.body
    if not body: return 'none'

    # try get json format
    try:
        return json.dumps(req_or_resp.json, indent=2)
    except:
        pass

    # decode text or bytes
    try:
        return body.decode()
    except (UnicodeDecodeError, AttributeError):
        return f"{body[:32]}..."


# get service name from url (devstack default environment)
def get_service_from_url(url):
    parsed_url = parse_url(url)
    if parsed_url.port == 8080: return 'swift-proxy-server'
    if parsed_url.port == 8779: return 'trove-api'
    if parsed_url.port == 9696: return 'neutron-server'
    if parsed_url.path.startswith('/identity'): return 'keystone'
    if parsed_url.path.startswith('/image'): return 'glance-api'
    if parsed_url.path.startswith('/volume'): return 'cinder-api'
    if parsed_url.path.startswith('/compute'): return 'nova-api'
    if parsed_url.path.startswith('/placement'): return 'placement-api'

    return parsed_url.path

# get service name from command line args
def get_current_service():

    try:
        p = psutil.Process(os.getpid())
        args = p.cmdline()

        # match command line exact?
        services = {
            'horizon': '(wsgi:horizon)', 
            'trove-api': '(wsgi:trove-api)', 
            'keystone': 'keystoneuWSGI', 
            'glance-api': 'glance-apiuWSGI',
            'cinder-api': 'cinder-apiuWSGI',
            'nova-api': 'nova-apiuWSGI',
            'placement-api': 'placementuWSGI',
            'neutron-server': 'neutron-server',
            'swift-proxy-server': 'swift-proxy-server',
        }

        matches = [service for arg in (args or []) for (service, tag) in services.items() if tag == arg or service in arg]
        return matches[0] if matches else p.name()
    except:
        return None


# parse 'x-requestshook-request-id' from header
def get_request_id(headers, fallback = None):
    try:
        return headers.get(X_REQUESTSHOOK_REQUEST_ID) or fallback
    except:
        return fallback

# parse 'x-requestshook-request-from' from header
def get_request_from(headers, fallback = None):
    try:
        return headers.get(X_REQUESTSHOOK_REQUEST_FROM) or fallback
    except:
        return fallback

# parse first user-agent
def get_user_agent(headers, fallback = None):
    try:
        return headers.get('User-Agent').split()[0] or fallback
    except:
        return fallback

# add request id to header
def add_request_id(headers, req_id):
    headers[X_REQUESTSHOOK_REQUEST_ID] = req_id

# add request from to header
def add_request_from(headers, req_from):
    headers[X_REQUESTSHOOK_REQUEST_FROM] = req_from