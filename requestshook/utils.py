import json
import os
import psutil

from pathlib import Path
from urllib3.util import parse_url

try:
    import syslog
except:
    syslog = None

# write message to syslog
def write_syslog(*messages):
    message = f"@{PACKAGE_NAME}: {' '.join(messages or [])}"
    syslog.syslog(f'{message}') if syslog else print(f'{message}\n')

# package name : requestshook
PACKAGE_NAME = __package__ or "requestshook"

# log path, config path
LOG_PATH = f'/var/log/{PACKAGE_NAME}' 
CONF_PATH = f'/etc/{PACKAGE_NAME}'
if os.name == 'nt': 
    LOG_PATH = os.path.expanduser(os.path.join('~', 'log', PACKAGE_NAME))
    CONF_PATH = os.path.expanduser(os.path.join('~', 'conf'))

CONF_FILE_PATH = os.path.join(CONF_PATH, f'{PACKAGE_NAME}.conf')
LOG_FILE_PATH = os.path.join(LOG_PATH, f'{PACKAGE_NAME}.log')
DIAGRAM_FILE_PATH = os.path.join(LOG_PATH, f'diagram.md')
DOC_FILE_PATH = os.path.join(LOG_PATH, f'body.md')

try:
    # create log path if not exists...
    if not os.path.exists(LOG_PATH):
        os.makedirs(LOG_PATH)
        if os.name == 'posix': os.chmod(LOG_PATH, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
except Exception as e:
    write_syslog(e)

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

# format headers( headers should be dictionary type )
def format_header(headers):
    try:
        return '\n'.join(f'{k}: {v}' for k, v in headers.items())
    except:
        return repr(headers)


# format request/response body
def format_body(req_or_resp):

    # no body
    if not req_or_resp.body: return 'none'

    # try to get body as json string
    try:
        return json.dumps(req_or_resp.json, indent=2)
    except:
        pass

    # try to get body as text/html or bytes(32)
    try:
        return req_or_resp.body.decode()
    except (UnicodeDecodeError, AttributeError):
        return f"{req_or_resp.body[:32]}..."


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

    return url

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
        return 'unknown'

# requestshook header parameters
X_REQUESTSHOOK_REQUEST_ID = 'X-Requestshook-Request-Id'
X_REQUESTSHOOK_REQUEST_FROM = 'X-Requestshook-Request-From'

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
